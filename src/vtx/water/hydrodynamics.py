"""Geometry-based 3D hull hydrodynamics, hydrostatic clipping, and force breakdown.

Computes exact submerged volume, centre of buoyancy, wetted surface area, and
separately identifiable hydrodynamic force/moment channels from watertight 3D
triangle meshes immersed in a `HybridWaterField` or uniform free surface.

No solver state is mutated; MuJoCo remains the sole rigid-body integrator.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from vtx.water.datum import (
    G_SI,
    NU_FRESHWATER_15C,
    RHO_FRESHWATER_15C,
    HydroCalibrationProfile,
)


def _cross3(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Fast 3D cross product without NumPy moveaxis/normalize_axis_tuple overhead."""
    if a.ndim == 1 and b.ndim == 1:
        return np.array([
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ], dtype=np.float64)
    ax, ay, az = a[..., 0], a[..., 1], a[..., 2]
    bx, by, bz = b[..., 0], b[..., 1], b[..., 2]
    out = np.empty(np.broadcast_shapes(a.shape, b.shape), dtype=np.float64)
    out[..., 0] = ay * bz - az * by
    out[..., 1] = az * bx - ax * bz
    out[..., 2] = ax * by - ay * bx
    return out


def _triangle_signed_volume(verts: np.ndarray, faces: np.ndarray) -> float:
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    return float(np.sum(np.einsum('ij,ij->i', v0, _cross3(v1, v2))) / 6.0)


@dataclass
class WatertightMesh:
    """Closed, outward-oriented triangle mesh in body-local SI coordinates (m)."""

    name: str
    vertices: np.ndarray  # (N, 3) float64
    faces: np.ndarray  # (M, 3) int32
    source_id: str = 'procedural'

    def __post_init__(self) -> None:
        self.vertices = np.ascontiguousarray(self.vertices, dtype=np.float64)
        self.faces = np.ascontiguousarray(self.faces, dtype=np.int32)
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError(f'{self.name}: expected vertices shape (N, 3), got {self.vertices.shape}')
        if self.faces.ndim != 2 or self.faces.shape[1] != 3:
            raise ValueError(f'{self.name}: expected faces shape (M, 3), got {self.faces.shape}')

        vol = _triangle_signed_volume(self.vertices, self.faces)
        if vol < 0.0:
            self.faces = self.faces[:, [0, 2, 1]].copy()
            vol = -vol
        self.gross_volume_m3 = float(vol)

        v0 = self.vertices[self.faces[:, 0]]
        v1 = self.vertices[self.faces[:, 1]]
        v2 = self.vertices[self.faces[:, 2]]
        e1 = v1 - v0
        e2 = v2 - v0
        cross = np.cross(e1, e2)
        areas = 0.5 * np.linalg.norm(cross, axis=1)
        self.face_areas_m2 = areas
        self.gross_area_m2 = float(np.sum(areas))
        self.bounds_min = np.min(self.vertices, axis=0)
        self.bounds_max = np.max(self.vertices, axis=0)
        self.length_m = float(self.bounds_max[0] - self.bounds_min[0])
        self.beam_m = float(self.bounds_max[1] - self.bounds_min[1])
        self.depth_m = float(self.bounds_max[2] - self.bounds_min[2])

        h = hashlib.sha256()
        h.update(np.round(self.vertices, 6).tobytes())
        h.update(self.faces.astype(np.int32).tobytes())
        self.geometry_sha256 = h.hexdigest()

    def is_watertight(self) -> bool:
        """Check closed oriented 2-manifold condition: every directed edge has one twin."""
        f = self.faces
        edges = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]], axis=0)
        directed = {(int(a), int(b)) for a, b in edges}
        if len(directed) != edges.shape[0]:
            return False
        for a, b in directed:
            if (b, a) not in directed:
                return False
        return True

    def subdivide(self, levels: int = 1) -> 'WatertightMesh':
        """1-to-4 planar triangle midpoint subdivision for resolution convergence tests."""
        verts = self.vertices.copy()
        faces = self.faces.copy()
        for _ in range(int(levels)):
            edge_cache: dict[tuple[int, int], int] = {}
            new_verts = list(verts)
            new_faces = []

            def midpoint(ia: int, ib: int) -> int:
                key = (ia, ib) if ia < ib else (ib, ia)
                idx = edge_cache.get(key)
                if idx is None:
                    idx = len(new_verts)
                    new_verts.append(0.5 * (new_verts[ia] + new_verts[ib]))
                    edge_cache[key] = idx
                return idx

            for a, b, c in faces:
                ab = midpoint(int(a), int(b))
                bc = midpoint(int(b), int(c))
                ca = midpoint(int(c), int(a))
                new_faces.extend([
                    (a, ab, ca),
                    (ab, b, bc),
                    (ca, bc, c),
                    (ab, bc, ca),
                ])
            verts = np.asarray(new_verts, dtype=np.float64)
            faces = np.asarray(new_faces, dtype=np.int32)
        return WatertightMesh(
            name=f'{self.name}_sub{levels}',
            vertices=verts,
            faces=faces,
            source_id=f'{self.source_id}:sub{levels}',
        )


@dataclass
class HullComponentMesh:
    """Associates a watertight mesh with its attachment body and hydrostatic scaling."""

    component_id: str
    mesh: WatertightMesh
    role: str = 'hull'
    local_offset: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))


@dataclass
class HydroBreakdown:
    """Separately identifiable hydrodynamic state, geometry metrics, and 6-DOF loads."""

    submerged_volume_m3: float
    wetted_area_m2: float
    centre_of_buoyancy_world: np.ndarray
    centre_of_buoyancy_body: np.ndarray
    waterline_z_world_mean: float
    draft_m: float
    freeboard_min_m: float
    submergence_ratio: float
    ground_clearance_m: float
    mean_water_depth_m: float

    # Forces (N) and torques about ref_point (N*m) in WORLD frame
    buoyancy_force_world: np.ndarray
    buoyancy_torque_world: np.ndarray
    resistance_force_world: np.ndarray
    resistance_torque_world: np.ndarray
    dynamic_lift_force_world: np.ndarray
    dynamic_lift_torque_world: np.ndarray
    added_mass_force_world: np.ndarray
    added_mass_torque_world: np.ndarray
    damping_force_world: np.ndarray
    damping_torque_world: np.ndarray
    wave_force_world: np.ndarray
    wave_torque_world: np.ndarray

    total_force_world: np.ndarray
    total_torque_world: np.ndarray
    munk_torque_body: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    component_loads: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_telemetry_dict(self) -> dict[str, Any]:
        return {
            'submerged_volume_m3': round(float(self.submerged_volume_m3), 6),
            'wetted_area_m2': round(float(self.wetted_area_m2), 5),
            'centre_of_buoyancy_world_m': [round(float(v), 5) for v in self.centre_of_buoyancy_world],
            'centre_of_buoyancy_body_m': [round(float(v), 5) for v in self.centre_of_buoyancy_body],
            'waterline_z_world_m': round(float(self.waterline_z_world_mean), 5),
            'draft_m': round(float(self.draft_m), 5),
            'freeboard_min_m': round(float(self.freeboard_min_m), 5),
            'submergence_ratio': round(float(self.submergence_ratio), 5),
            'ground_clearance_m': round(float(self.ground_clearance_m), 4),
            'mean_water_depth_m': round(float(self.mean_water_depth_m), 4),
            'munk_torque_body_nm': [round(float(x), 3) for x in self.munk_torque_body],
            'forces_world_n': {
                'buoyancy': [round(float(x), 3) for x in self.buoyancy_force_world],
                'resistance': [round(float(x), 3) for x in self.resistance_force_world],
                'dynamic_lift': [round(float(x), 3) for x in self.dynamic_lift_force_world],
                'added_mass': [round(float(x), 3) for x in self.added_mass_force_world],
                'damping': [round(float(x), 3) for x in self.damping_force_world],
                'wave_excitation': [round(float(x), 3) for x in self.wave_force_world],
                'total': [round(float(x), 3) for x in self.total_force_world],
            },
            'torques_world_nm': {
                'buoyancy': [round(float(x), 3) for x in self.buoyancy_torque_world],
                'resistance': [round(float(x), 3) for x in self.resistance_torque_world],
                'dynamic_lift': [round(float(x), 3) for x in self.dynamic_lift_torque_world],
                'added_mass': [round(float(x), 3) for x in self.added_mass_torque_world],
                'damping': [round(float(x), 3) for x in self.damping_torque_world],
                'wave_excitation': [round(float(x), 3) for x in self.wave_torque_world],
                'total': [round(float(x), 3) for x in self.total_torque_world],
            },
            'component_loads': self.component_loads,
        }


def _clip_submerged_triangles(
    verts_world: np.ndarray,
    faces: np.ndarray,
    s_verts: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | list[tuple[np.ndarray, np.ndarray]]]:
    """Vectorized triangle mesh clip against `s = eta - z >= 0`.

    Returns:
        wet_tris: (K, 3, 3) array of submerged/clipped triangle vertices in world frame.
        wet_blend: (K,) smooth partial wetting weight in (0, 1].
        src_face_idx: (K,) index into original `faces`.
        cap_segments: (C, 2, 3) oriented `(p_a, p_b)` waterline cap edges for Divergence Theorem closure.
    """
    f_s = s_verts[faces]  # (M, 3)
    all_dry = np.all(f_s <= 0.0, axis=1)
    all_wet = (~all_dry) & np.all(f_s >= 0.0, axis=1)
    bulk_idx = np.flatnonzero(all_wet)
    bulk_tris = verts_world[faces[bulk_idx]] if bulk_idx.size else np.zeros((0, 3, 3), dtype=np.float64)

    straddle_idx = np.flatnonzero((~all_dry) & (~all_wet))
    if straddle_idx.size == 0:
        if not bulk_idx.size:
            return (
                np.zeros((0, 3, 3), dtype=np.float64),
                np.zeros((0,), dtype=np.float64),
                np.zeros((0,), dtype=np.int32),
                np.zeros((0, 2, 3), dtype=np.float64),
            )
        return (
            bulk_tris,
            np.ones(bulk_tris.shape[0], dtype=np.float64),
            bulk_idx.astype(np.int32),
            np.zeros((0, 2, 3), dtype=np.float64),
        )

    s_faces = faces[straddle_idx]
    sf_s = f_s[straddle_idx]
    inside = sf_s > 0.0
    cnt = np.sum(inside, axis=1)
    rot = np.where(cnt == 1, np.argmax(inside, axis=1), np.argmax(~inside, axis=1))
    rows = np.arange(s_faces.shape[0])
    ia = s_faces[rows, rot]
    ib = s_faces[rows, (rot + 1) % 3]
    ic = s_faces[rows, (rot + 2) % 3]
    va, vb, vc = verts_world[ia], verts_world[ib], verts_world[ic]
    sa, sb, sc = s_verts[ia], s_verts[ib], s_verts[ic]

    tri_chunks: list[np.ndarray] = [bulk_tris] if bulk_idx.size else []
    idx_chunks: list[np.ndarray] = [bulk_idx.astype(np.int32)] if bulk_idx.size else []
    cap_chunks: list[np.ndarray] = []

    m1 = cnt == 1
    if np.any(m1):
        sa1, sb1, sc1 = sa[m1], sb[m1], sc[m1]
        va1, vb1, vc1 = va[m1], vb[m1], vc[m1]
        t_ab = sa1 / np.maximum(sa1 - sb1, 1e-12)
        t_ac = sa1 / np.maximum(sa1 - sc1, 1e-12)
        p_ab = va1 + t_ab[:, None] * (vb1 - va1)
        p_ac = va1 + t_ac[:, None] * (vc1 - va1)
        tri_chunks.append(np.stack([va1, p_ab, p_ac], axis=1))
        idx_chunks.append(straddle_idx[m1].astype(np.int32))
        cap_chunks.append(np.stack([p_ac, p_ab], axis=1))

    m2 = ~m1
    if np.any(m2):
        sa2, sb2, sc2 = sa[m2], sb[m2], sc[m2]
        va2, vb2, vc2 = va[m2], vb[m2], vc[m2]
        t_ab = sb2 / np.maximum(sb2 - sa2, 1e-12)
        t_ac = sc2 / np.maximum(sc2 - sa2, 1e-12)
        p_ba = vb2 + t_ab[:, None] * (va2 - vb2)
        p_ca = vc2 + t_ac[:, None] * (va2 - vc2)
        tri_chunks.append(np.stack([vb2, vc2, p_ca], axis=1))
        tri_chunks.append(np.stack([vb2, p_ca, p_ba], axis=1))
        idx2 = straddle_idx[m2].astype(np.int32)
        idx_chunks.append(idx2)
        idx_chunks.append(idx2)
        cap_chunks.append(np.stack([p_ba, p_ca], axis=1))

    tris_arr = tri_chunks[0] if len(tri_chunks) == 1 else np.concatenate(tri_chunks, axis=0)
    idx_arr = idx_chunks[0] if len(idx_chunks) == 1 else np.concatenate(idx_chunks, axis=0)
    caps_arr = cap_chunks[0] if len(cap_chunks) == 1 else (np.concatenate(cap_chunks, axis=0) if cap_chunks else np.zeros((0, 2, 3), dtype=np.float64))
    return tris_arr, np.ones(tris_arr.shape[0], dtype=np.float64), idx_arr, caps_arr


def _submerged_volume_and_centroid(
    wet_tris: np.ndarray,
    cap_segments: np.ndarray | list[tuple[np.ndarray, np.ndarray]],
    origin: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Compute exact submerged volume & CoB via closed Divergence Theorem."""
    if wet_tris.shape[0] == 0:
        return 0.0, origin.copy()

    # Translate to body origin first for floating-point conditioning
    t = wet_tris - origin[None, None, :]
    v0 = t[:, 0, :]
    v1 = t[:, 1, :]
    v2 = t[:, 2, :]

    if len(cap_segments) > 0:
        seg_pts = np.asarray(cap_segments, dtype=np.float64) - origin[None, None, :]
        cap_center = np.mean(seg_pts.reshape(-1, 3), axis=0)
        cap_v0 = np.broadcast_to(cap_center, (len(cap_segments), 3))
        cap_v1 = seg_pts[:, 0, :]
        cap_v2 = seg_pts[:, 1, :]
        a0 = np.concatenate([v0, cap_v0], axis=0)
        a1 = np.concatenate([v1, cap_v1], axis=0)
        a2 = np.concatenate([v2, cap_v2], axis=0)
    else:
        a0, a1, a2 = v0, v1, v2

    tet_vol6 = np.einsum('ij,ij->i', a0, _cross3(a1, a2))
    vol = float(np.sum(tet_vol6) / 6.0)
    if vol <= 1e-10:
        return 0.0, origin.copy()
    tet_centroids = 0.25 * (a0 + a1 + a2)
    cob_rel = np.sum(tet_vol6[:, None] * tet_centroids, axis=0) / (6.0 * vol)
    return vol, origin + cob_rel


def evaluate_mesh_hydrodynamics(
    component: HullComponentMesh,
    body_pos_world: np.ndarray,
    body_rot_world: np.ndarray,
    vel_world: np.ndarray,
    omega_world: np.ndarray,
    acc_world: np.ndarray,
    alpha_world: np.ndarray,
    ref_point_world: np.ndarray,
    water_field,
    t: float,
    calibration: HydroCalibrationProfile | None = None,
    rho_water: float = RHO_FRESHWATER_15C,
    nu_water: float = NU_FRESHWATER_15C,
    g: float = G_SI,
    body_mass_kg: float | None = None,
    body_inertia_diag: np.ndarray | None = None,
    external_non_hydro_force_world: np.ndarray | None = None,
    external_non_hydro_torque_world: np.ndarray | None = None,
    include_inertial_am: bool = True,
) -> HydroBreakdown:
    """Evaluate geometry-resolved hydrostatics & hydrodynamics for one closed hull mesh."""
    cal = calibration or HydroCalibrationProfile()
    mesh = component.mesh

    # Transform mesh vertices from body frame -> world frame
    verts_body = mesh.vertices + component.local_offset[None, :]
    verts_world = body_pos_world[None, :] + verts_body @ body_rot_world.T

    # Sample free surface at all hull vertices (typically 48..700 vertices -> fast vectorized call)
    w_samp = water_field.evaluate(verts_world[:, 0], verts_world[:, 1], z=verts_world[:, 2], t=t)
    eta_v = w_samp.eta
    depth_v = w_samp.depth
    s_verts = eta_v - verts_world[:, 2]

    # Freeboard & draft diagnostics
    mean_eta = float(np.mean(eta_v))
    mean_depth = float(np.mean(depth_v))
    keel_z_world = float(np.min(verts_world[:, 2]))
    deck_z_world = float(np.max(verts_world[:, 2]))
    draft_m = max(0.0, mean_eta - keel_z_world)
    freeboard_min_m = max(0.0, deck_z_world - mean_eta)
    ground_clearance_m = float(keel_z_world - (mean_eta - mean_depth))

    # Grazing transition band prevents discontinuity just before touching eta = z
    band = max(float(cal.wet_dry_blend_band_m), 1e-4)
    if float(np.max(s_verts)) <= 0.0:
        # Pure dry case — check ultra-thin film proximity fade only for smooth contact entry
        zero3 = np.zeros(3, dtype=np.float64)
        return HydroBreakdown(
            submerged_volume_m3=0.0,
            wetted_area_m2=0.0,
            centre_of_buoyancy_world=body_pos_world.copy(),
            centre_of_buoyancy_body=np.zeros(3, dtype=np.float64),
            waterline_z_world_mean=mean_eta,
            draft_m=0.0,
            freeboard_min_m=max(0.0, keel_z_world - mean_eta),
            submergence_ratio=0.0,
            ground_clearance_m=ground_clearance_m,
            mean_water_depth_m=mean_depth,
            buoyancy_force_world=zero3.copy(),
            buoyancy_torque_world=zero3.copy(),
            resistance_force_world=zero3.copy(),
            resistance_torque_world=zero3.copy(),
            dynamic_lift_force_world=zero3.copy(),
            dynamic_lift_torque_world=zero3.copy(),
            added_mass_force_world=zero3.copy(),
            added_mass_torque_world=zero3.copy(),
            damping_force_world=zero3.copy(),
            damping_torque_world=zero3.copy(),
            wave_force_world=zero3.copy(),
            wave_torque_world=zero3.copy(),
            total_force_world=zero3.copy(),
            total_torque_world=zero3.copy(),
        )

    wet_tris, _, _, cap_segments = _clip_submerged_triangles(verts_world, mesh.faces, s_verts)
    if wet_tris.shape[0] == 0:
        zero3 = np.zeros(3, dtype=np.float64)
        return HydroBreakdown(
            submerged_volume_m3=0.0,
            wetted_area_m2=0.0,
            centre_of_buoyancy_world=body_pos_world.copy(),
            centre_of_buoyancy_body=np.zeros(3, dtype=np.float64),
            waterline_z_world_mean=mean_eta,
            draft_m=draft_m,
            freeboard_min_m=freeboard_min_m,
            submergence_ratio=0.0,
            ground_clearance_m=ground_clearance_m,
            mean_water_depth_m=mean_depth,
            buoyancy_force_world=zero3.copy(),
            buoyancy_torque_world=zero3.copy(),
            resistance_force_world=zero3.copy(),
            resistance_torque_world=zero3.copy(),
            dynamic_lift_force_world=zero3.copy(),
            dynamic_lift_torque_world=zero3.copy(),
            added_mass_force_world=zero3.copy(),
            added_mass_torque_world=zero3.copy(),
            damping_force_world=zero3.copy(),
            damping_torque_world=zero3.copy(),
            wave_force_world=zero3.copy(),
            wave_torque_world=zero3.copy(),
            total_force_world=zero3.copy(),
            total_torque_world=zero3.copy(),
        )

    # Geometry integrals
    e1 = wet_tris[:, 1, :] - wet_tris[:, 0, :]
    e2 = wet_tris[:, 2, :] - wet_tris[:, 0, :]
    cross = _cross3(e1, e2)
    tri_norm_len = np.linalg.norm(cross, axis=1)
    tri_areas = 0.5 * tri_norm_len
    valid = tri_areas > 1e-10
    wet_tris = wet_tris[valid]
    cross = cross[valid]
    tri_norm_len = tri_norm_len[valid]
    tri_areas = tri_areas[valid]

    tri_normals = cross / np.maximum(tri_norm_len[:, None], 1e-12)
    tri_centers = np.mean(wet_tris, axis=1)
    wetted_area = float(np.sum(tri_areas))

    # Origin chosen inside hull (body_pos_world + mean vertex) for exact cancellation
    sub_vol, cob_world = _submerged_volume_and_centroid(wet_tris, cap_segments, body_pos_world)
    cob_body = body_rot_world.T @ (cob_world - body_pos_world)

    # Zero out water forces smoothly in totally dry shoreline cells
    f_samp = water_field.evaluate(tri_centers[:, 0], tri_centers[:, 1], z=tri_centers[:, 2], t=t)
    wet_mask = np.clip(f_samp.wet_fraction, 0.0, 1.0)
    sub_depth_f = np.maximum(0.0, f_samp.eta - tri_centers[:, 2])
    smooth_immersion = np.clip(sub_depth_f / band, 0.25, 1.0) * wet_mask
    eff_areas = tri_areas * wet_mask

    # Effective displaced volume & immersion fraction (scaled by local wet bed presence)
    mean_wet_frac = float(np.average(wet_mask, weights=np.maximum(tri_areas, 1e-9))) if wetted_area > 0.0 else 0.0
    eff_sub_vol = sub_vol * mean_wet_frac
    sub_ratio = float(np.clip(eff_sub_vol / max(mesh.gross_volume_m3, 1e-6), 0.0, 1.0))

    # 1. Hydrostatic Buoyancy
    f_buoy = np.array([0.0, 0.0, rho_water * g * eff_sub_vol], dtype=np.float64)
    tau_buoy = _cross3(cob_world - ref_point_world, f_buoy)

    # Moment arms relative to reference point (e.g. MuJoCo body CoM xipos)
    r_arms = tri_centers - ref_point_world[None, :]
    v_panel = vel_world[None, :] + _cross3(omega_world[None, :], r_arms)
    v_rel = v_panel - f_samp.velocity  # (K, 3) body relative to water
    v_mag = np.linalg.norm(v_rel, axis=1)

    # 2. Resistance (ITTC-57 skin friction * (1+k) + normal pressure drag + shallow blockage factor)
    # Shallow water blockage factor (Schlichting/Lackenby style depth/draft correction >= 1.0)
    mean_d_eff = max(float(np.mean(f_samp.depth)), 0.15)
    h_over_d = mean_d_eff / max(draft_m, 0.12)
    shallow_mult = 1.0 + 0.35 / max(h_over_d - 0.65, 0.45) ** 2 if draft_m > 0.05 else 1.0
    shallow_mult = float(np.clip(shallow_mult, 1.0, 3.2))

    l_char = max(mesh.length_m, 0.5)
    re = np.maximum(v_mag * l_char / max(nu_water, 1e-8), 2.0e4)
    cf = 0.075 / (np.log10(re) - 2.0) ** 2 + float(cal.skin_friction_roughness_allowance)
    cf_eff = cf * (1.0 + float(cal.form_factor_k)) * shallow_mult

    v_n = np.einsum('ij,ij->i', v_rel, tri_normals)
    v_tan = v_rel - v_n[:, None] * tri_normals
    v_tan_mag = np.linalg.norm(v_tan, axis=1)

    # Viscous shear drag opposing tangential flow on each wetted triangle
    f_visc_p = -0.5 * rho_water * cf_eff[:, None] * v_tan_mag[:, None] * v_tan * (eff_areas * smooth_immersion)[:, None]

    # Normal pressure drag (full Cd when panel advances into water v_n > 0; 0.35 base suction when v_n < 0)
    cd_n = np.where(v_n > 0.0, float(cal.pressure_drag_normal_cd), 0.35 * float(cal.pressure_drag_normal_cd))
    f_press_p = (
        -0.5
        * rho_water
        * cd_n[:, None]
        * np.abs(v_n)[:, None]
        * v_n[:, None]
        * tri_normals
        * (eff_areas * smooth_immersion)[:, None]
        * shallow_mult
    )

    f_res_panels = f_visc_p + f_press_p
    f_res = np.sum(f_res_panels, axis=0)
    tau_res = np.sum(_cross3(r_arms, f_res_panels), axis=0)

    # 3. Dynamic Lift & Planing Forces (strictly velocity-dependent hydrodynamic pressure)
    # Act on downward-facing wet surfaces (normals with negative world Z component) advancing into fluid
    impact_vel = np.maximum(v_n, 0.0)
    deadrise_up = np.maximum(-tri_normals[:, 2], 0.0)
    # Project dynamic lift along surface inward/upward normal minus horizontal drag already counted above
    lift_mag = (
        0.5
        * rho_water
        * float(cal.planing_lift_coeff)
        * impact_vel
        * v_mag
        * deadrise_up
        * eff_areas
        * smooth_immersion
    )
    # Planing pressure acts inward (-tri_normals), decomposed cleanly so vertical lift is explicit
    inward_up = np.stack([
        -0.15 * tri_normals[:, 0],
        -0.15 * tri_normals[:, 1],
        np.maximum(-tri_normals[:, 2], 0.0),
    ], axis=1)
    inward_len = np.linalg.norm(inward_up, axis=1, keepdims=True)
    inward_dir = np.where(inward_len > 1e-6, inward_up / np.maximum(inward_len, 1e-9), 0.0)
    f_lift_panels = lift_mag[:, None] * inward_dir
    f_lift = np.sum(f_lift_panels, axis=0)
    tau_lift = np.sum(_cross3(r_arms, f_lift_panels), axis=0)

    # 4. Wave Excitation (Froude-Krylov dynamic pressure + diffraction wave-slope force)
    fk_scale = float(cal.wave_froude_krylov_scale)
    # p_dyn acts inward (-tri_normals) on wetted shell
    f_wave_panels = -fk_scale * f_samp.dynamic_pressure[:, None] * tri_normals * eff_areas[:, None]
    f_wave = np.sum(f_wave_panels, axis=0)
    tau_wave = np.sum(_cross3(r_arms, f_wave_panels), axis=0)

    # 5. Added-mass tensor parameters & Kirchhoff-Munk velocity terms
    m_disp = rho_water * eff_sub_vol
    rx = max(0.28 * mesh.length_m, 0.25)
    ry = max(0.32 * mesh.beam_m, 0.15)
    ma_body = np.array([
        cal.added_mass_surge_factor * m_disp,
        cal.added_mass_sway_factor * m_disp,
        cal.added_mass_heave_factor * m_disp,
    ], dtype=np.float64)
    ia_body = np.array([
        cal.added_mass_roll_factor * m_disp * (ry * ry + 0.08),
        cal.added_mass_pitch_factor * m_disp * (rx * rx + 0.08),
        cal.added_mass_yaw_factor * m_disp * (rx * rx),
    ], dtype=np.float64)

    # Shallow-water added-mass increase in vertical heave/pitch when keel clearance is small
    if draft_m > 0.05 and ground_clearance_m < 2.0 * draft_m:
        keel_boost = 1.0 + 0.6 / max(ground_clearance_m / max(draft_m, 0.1), 0.25)
        ma_body[2] *= min(keel_boost, 2.5)
        ia_body[1] *= min(0.5 + 0.5 * keel_boost, 2.0)

    mean_water_vel = np.average(f_samp.velocity, axis=0, weights=np.maximum(eff_areas, 1e-9)) if wetted_area > 0 else np.zeros(3)
    mean_water_acc = np.average(f_samp.acceleration, axis=0, weights=np.maximum(eff_areas, 1e-9)) if wetted_area > 0 else np.zeros(3)

    # 3b. Slender-body aft skeg / stepped-hull directional Kutta lift (opposes Munk directional divergence)
    if component.role == 'hull' and draft_m > 0.01 and mean_wet_frac > 0.01:
        a_lat = min(0.45 * wetted_area, 0.65 * mesh.length_m * draft_m) * mean_wet_frac
        r_skeg_world = body_pos_world + body_rot_world @ np.array([-0.28 * mesh.length_m, 0.0, cob_body[2]], dtype=np.float64)
        v_skeg_body = body_rot_world.T @ (vel_world + _cross3(omega_world, r_skeg_world - ref_point_world) - mean_water_vel)
        u_fwd = abs(float(v_skeg_body[0]))
        u_eff = u_fwd * min(1.0, u_fwd / 0.4)
        f_skeg_y = -0.5 * rho_water * a_lat * float(cal.aft_skeg_lift_coeff) * u_eff * float(v_skeg_body[1])
        f_skeg_cap = 0.5 * rho_water * a_lat * float(cal.aft_skeg_lift_coeff) * max(u_fwd, 0.5) ** 2 * 0.65
        f_skeg_y = float(np.clip(f_skeg_y, -f_skeg_cap, f_skeg_cap))
        f_skeg_w = body_rot_world @ np.array([0.0, f_skeg_y, 0.0], dtype=np.float64)
        f_lift = f_lift + f_skeg_w
        tau_lift = tau_lift + _cross3(r_skeg_world - ref_point_world, f_skeg_w)

    v_cg_rel_body = body_rot_world.T @ (vel_world + _cross3(omega_world, cob_world - ref_point_world) - mean_water_vel)
    omega_body = body_rot_world.T @ omega_world
    p_trans = ma_body * v_cg_rel_body

    # 6. Radiation & Bilge/Chine Viscous Damping
    if m_disp > 1e-3:
        waterplane_proxy = max(0.45 * mesh.length_m * mesh.beam_m * (0.3 + 0.7 * math.sqrt(sub_ratio)), 0.05)
        k_heave = rho_water * g * waterplane_proxy
        c_heave = 2.0 * cal.linear_heave_damping_ratio * math.sqrt(max(k_heave * (m_disp + ma_body[2]), 0.0))
        c_roll = 2.0 * cal.linear_roll_damping_ratio * math.sqrt(max(m_disp * g * max(0.35 * mesh.beam_m, 0.15) * (ia_body[0] + m_disp * ry * ry), 0.0))
        c_pitch = 2.0 * cal.linear_pitch_damping_ratio * math.sqrt(max(m_disp * g * max(0.45 * mesh.length_m, 0.25) * (ia_body[1] + m_disp * rx * rx), 0.0))
        c_yaw = 0.35 * c_pitch

        smooth_sub = min(1.0, sub_vol / max(0.05 * mesh.gross_volume_m3, 1e-4)) * mean_wet_frac
        f_damp_body = np.array([
            -0.08 * c_heave * v_cg_rel_body[0],
            -0.35 * c_heave * v_cg_rel_body[1],
            -c_heave * v_cg_rel_body[2],
        ], dtype=np.float64) * smooth_sub
        tau_damp_body = np.array([
            -(c_roll * omega_body[0] + cal.quadratic_roll_damping * abs(omega_body[0]) * omega_body[0]),
            -c_pitch * omega_body[1],
            -c_yaw * omega_body[2],
        ], dtype=np.float64) * smooth_sub
        f_damp = body_rot_world @ f_damp_body
        tau_damp = body_rot_world @ tau_damp_body + _cross3(cob_world - ref_point_world, f_damp)
    else:
        f_damp = np.zeros(3, dtype=np.float64)
        tau_damp = np.zeros(3, dtype=np.float64)

    # 5b. Added-Mass inertial reaction (unconditionally stable coupled-mass solve when body_mass_kg given)
    f_am_vel_body = -_cross3(omega_body, p_trans)
    tau_munk_body = float(cal.munk_viscous_relief) * (-_cross3(v_cg_rel_body, p_trans))
    tau_am_vel_body = tau_munk_body - _cross3(omega_body, ia_body * omega_body)

    if not include_inertial_am:
        f_am_iner_body = np.zeros(3, dtype=np.float64)
        tau_am_iner_body = np.zeros(3, dtype=np.float64)
    elif body_mass_kg is not None and body_mass_kg > 1e-6:
        m_b = float(body_mass_kg)
        f_ext = np.zeros(3, dtype=np.float64) if external_non_hydro_force_world is None else np.asarray(external_non_hydro_force_world, dtype=np.float64)
        t_ext = np.zeros(3, dtype=np.float64) if external_non_hydro_torque_world is None else np.asarray(external_non_hydro_torque_world, dtype=np.float64)
        f_free_w = f_buoy + f_res + f_lift + f_wave + f_damp + (body_rot_world @ f_am_vel_body) + f_ext + np.array([0.0, 0.0, -m_b * g])
        tau_free_w = tau_buoy + tau_res + tau_lift + tau_wave + tau_damp + (body_rot_world @ tau_am_vel_body) + t_ext
        a_w_body = body_rot_world.T @ mean_water_acc
        a_rel_b = (body_rot_world.T @ f_free_w - m_b * a_w_body) / np.maximum(m_b + ma_body, 1e-6)
        f_am_iner_body = -ma_body * a_rel_b

        i_b = np.full(3, max(m_b * 0.5, 1.0), dtype=np.float64) if body_inertia_diag is None else np.maximum(np.asarray(body_inertia_diag, dtype=np.float64), 0.1)
        alpha_rel_b = (body_rot_world.T @ tau_free_w) / np.maximum(i_b + ia_body, 1e-6)
        tau_am_iner_body = -ia_body * alpha_rel_b
    else:
        a_cg_rel_body = body_rot_world.T @ (acc_world + _cross3(alpha_world, cob_world - ref_point_world) - mean_water_acc)
        alpha_body = body_rot_world.T @ alpha_world
        f_am_iner_body = -ma_body * a_cg_rel_body
        tau_am_iner_body = -ia_body * alpha_body

    f_am = body_rot_world @ (f_am_vel_body + f_am_iner_body)
    tau_am = body_rot_world @ (tau_am_vel_body + tau_am_iner_body) + _cross3(cob_world - ref_point_world, body_rot_world @ f_am_vel_body)

    f_tot = f_buoy + f_res + f_lift + f_am + f_damp + f_wave
    tau_tot = tau_buoy + tau_res + tau_lift + tau_am + tau_damp + tau_wave

    bd = HydroBreakdown(
        submerged_volume_m3=eff_sub_vol,
        wetted_area_m2=wetted_area,
        centre_of_buoyancy_world=cob_world,
        centre_of_buoyancy_body=cob_body,
        waterline_z_world_mean=mean_eta,
        draft_m=draft_m,
        freeboard_min_m=freeboard_min_m,
        submergence_ratio=sub_ratio,
        ground_clearance_m=ground_clearance_m,
        mean_water_depth_m=mean_depth,
        buoyancy_force_world=f_buoy,
        buoyancy_torque_world=tau_buoy,
        resistance_force_world=f_res,
        resistance_torque_world=tau_res,
        dynamic_lift_force_world=f_lift,
        dynamic_lift_torque_world=tau_lift,
        added_mass_force_world=f_am,
        added_mass_torque_world=tau_am,
        damping_force_world=f_damp,
        damping_torque_world=tau_damp,
        wave_force_world=f_wave,
        wave_torque_world=tau_wave,
        total_force_world=f_tot,
        total_torque_world=tau_tot,
        munk_torque_body=tau_munk_body,
    )
    bd._am_data = (ma_body, ia_body, mean_water_acc, m_disp, wetted_area)  # type: ignore[attr-defined]
    return bd


def evaluate_components_hydrodynamics(
    components: list[tuple[HullComponentMesh, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    ref_point_world: np.ndarray,
    water_field,
    t: float,
    calibration: HydroCalibrationProfile | None = None,
    rho_water: float = RHO_FRESHWATER_15C,
    nu_water: float = NU_FRESHWATER_15C,
    g: float = G_SI,
) -> HydroBreakdown:
    """Evaluate and aggregate hydrodynamics across multiple rigid hull/sponson bodies."""
    if not components:
        raise ValueError('At least one HullComponentMesh is required')

    breakdowns: list[tuple[str, HydroBreakdown]] = []
    for comp, pos, rot, vel, omega, acc, alpha in components:
        bd = evaluate_mesh_hydrodynamics(
            component=comp,
            body_pos_world=pos,
            body_rot_world=rot,
            vel_world=vel,
            omega_world=omega,
            acc_world=acc,
            alpha_world=alpha,
            ref_point_world=ref_point_world,
            water_field=water_field,
            t=t,
            calibration=calibration,
            rho_water=rho_water,
            nu_water=nu_water,
            g=g,
        )
        breakdowns.append((comp.component_id, bd))

    tot_vol = sum(bd.submerged_volume_m3 for _, bd in breakdowns)
    tot_area = sum(bd.wetted_area_m2 for _, bd in breakdowns)
    tot_gross = sum(comp.mesh.gross_volume_m3 for comp, *_ in components)
    if tot_vol > 1e-9:
        cob_w = sum(bd.submerged_volume_m3 * bd.centre_of_buoyancy_world for _, bd in breakdowns) / tot_vol
    else:
        cob_w = breakdowns[0][1].centre_of_buoyancy_world.copy()
    main_pos, main_rot = components[0][1], components[0][2]
    cob_b = main_rot.T @ (cob_w - main_pos)

    sum_vec = lambda attr: sum((getattr(bd, attr) for _, bd in breakdowns), np.zeros(3, dtype=np.float64))
    comp_dict = {
        cid: {
            'submerged_volume_m3': round(float(bd.submerged_volume_m3), 6),
            'wetted_area_m2': round(float(bd.wetted_area_m2), 5),
            'total_force_world_n': [round(float(x), 3) for x in bd.total_force_world],
            'buoyancy_z_n': round(float(bd.buoyancy_force_world[2]), 3),
        }
        for cid, bd in breakdowns
    }

    return HydroBreakdown(
        submerged_volume_m3=tot_vol,
        wetted_area_m2=tot_area,
        centre_of_buoyancy_world=cob_w,
        centre_of_buoyancy_body=cob_b,
        waterline_z_world_mean=breakdowns[0][1].waterline_z_world_mean,
        draft_m=max(bd.draft_m for _, bd in breakdowns),
        freeboard_min_m=breakdowns[0][1].freeboard_min_m,
        submergence_ratio=float(np.clip(tot_vol / max(tot_gross, 1e-6), 0.0, 1.0)),
        ground_clearance_m=min(bd.ground_clearance_m for _, bd in breakdowns),
        mean_water_depth_m=breakdowns[0][1].mean_water_depth_m,
        buoyancy_force_world=sum_vec('buoyancy_force_world'),
        buoyancy_torque_world=sum_vec('buoyancy_torque_world'),
        resistance_force_world=sum_vec('resistance_force_world'),
        resistance_torque_world=sum_vec('resistance_torque_world'),
        dynamic_lift_force_world=sum_vec('dynamic_lift_force_world'),
        dynamic_lift_torque_world=sum_vec('dynamic_lift_torque_world'),
        added_mass_force_world=sum_vec('added_mass_force_world'),
        added_mass_torque_world=sum_vec('added_mass_torque_world'),
        damping_force_world=sum_vec('damping_force_world'),
        damping_torque_world=sum_vec('damping_torque_world'),
        wave_force_world=sum_vec('wave_force_world'),
        wave_torque_world=sum_vec('wave_torque_world'),
        total_force_world=sum_vec('total_force_world'),
        total_torque_world=sum_vec('total_torque_world'),
        munk_torque_body=main_rot.T @ sum((rot @ bd.munk_torque_body for (_, _, rot, *_), (_, bd) in zip(components, breakdowns)), np.zeros(3, dtype=np.float64)),
        component_loads=comp_dict,
    )
