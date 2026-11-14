"""Ricochet RC-01 Hull & Sponson Geometry Registry (F03 baseline + Concept A slot).

Loads the watertight F03 reference loft from `RC01_F03_cad_stations.npz`,
constructs watertight outboard sponson ellipsoids, converts F03 (+Y stbd) to
VTX (+Y port), supports GLB/NPZ hull imports and triangle subdivision, and
provides a quantitative variant comparison slot for Concept A.
"""

from __future__ import annotations

import json
import math
import pathlib
import struct
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from vtx.water.hydrodynamics import HullComponentMesh, WatertightMesh

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
F03_STATIONS_NPZ = _REPO_ROOT / 'experiments' / 'ricochet' / 'rc01_f03' / 'model' / 'RC01_F03_cad_stations.npz'
CONCEPT_A_GLB = _REPO_ROOT / 'public' / 'assets' / 'ricochet-concept-a.glb'

# F03 sponson dimensions & VTX mount centers (+X fwd, +Y port, +Z up)
SPONSON_RADII_M = (0.56, 0.18, 0.14)
SPONSON_PORT_MOUNT_VTX_M = (-0.34, 3.80, 0.42)
SPONSON_STBD_MOUNT_VTX_M = (-0.34, -3.80, 0.42)
# Concept A Pass 3 mount: sponson bottom at z_body=0.36m -> 0.20m submerged at 0.56m calm draft
SPONSON_CONCEPT_A_MOUNT_VTX_M = (-0.34, 3.80, 0.48)
SPONSON_CONCEPT_A_STBD_MOUNT_VTX_M = (-0.34, -3.80, 0.48)


def build_uv_ellipsoid_mesh(
    name: str,
    radii: tuple[float, float, float],
    n_u: int = 20,
    n_v: int = 12,
    source_id: str = 'parametric_ellipsoid',
) -> WatertightMesh:
    """Build a closed, outward-oriented triangle ellipsoid centered at (0, 0, 0)."""
    rx, ry, rz = float(radii[0]), float(radii[1]), float(radii[2])
    verts: list[tuple[float, float, float]] = [(0.0, 0.0, rz)]  # north pole index 0
    for j in range(1, n_v):
        phi = math.pi * j / n_v
        sp, cp = math.sin(phi), math.cos(phi)
        for i in range(n_u):
            th = 2.0 * math.pi * i / n_u
            verts.append((rx * sp * math.cos(th), ry * sp * math.sin(th), rz * cp))
    verts.append((0.0, 0.0, -rz))  # south pole last index
    south_idx = len(verts) - 1

    faces: list[tuple[int, int, int]] = []
    # Top cap
    for i in range(n_u):
        ni = (i + 1) % n_u
        faces.append((0, 1 + i, 1 + ni))
    # Rings
    for j in range(1, n_v - 1):
        r0 = 1 + (j - 1) * n_u
        r1 = 1 + j * n_u
        for i in range(n_u):
            ni = (i + 1) % n_u
            faces.append((r0 + i, r1 + i, r1 + ni))
            faces.append((r0 + i, r1 + ni, r0 + ni))
    # Bottom cap
    last_ring = 1 + (n_v - 2) * n_u
    for i in range(n_u):
        ni = (i + 1) % n_u
        faces.append((last_ring + i, south_idx, last_ring + ni))

    return WatertightMesh(
        name=name,
        vertices=np.asarray(verts, dtype=np.float64),
        faces=np.asarray(faces, dtype=np.int32),
        source_id=source_id,
    )


def _loft_closed_stations(xs: np.ndarray, rings: np.ndarray, flip_y: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Loft (S, K, 2) station rings along X with sealed bow/stern fan caps."""
    n_st, n_ring, _ = rings.shape
    verts: list[tuple[float, float, float]] = []
    for j in range(n_st):
        x = float(xs[j])
        for k in range(n_ring):
            y_raw = float(rings[j, k, 0])
            z = float(rings[j, k, 1])
            y = -y_raw if flip_y else y_raw
            verts.append((x, y, z))

    faces: list[tuple[int, int, int]] = []
    for j in range(n_st - 1):
        for k in range(n_ring):
            a = j * n_ring + k
            b = j * n_ring + (k + 1) % n_ring
            c = (j + 1) * n_ring + k
            d = (j + 1) * n_ring + (k + 1) % n_ring
            faces.append((a, c, b))
            faces.append((b, c, d))
    # Front cap (station 0)
    for k in range(1, n_ring - 1):
        faces.append((0, k, k + 1))
    # Aft cap (last station)
    base = (n_st - 1) * n_ring
    for k in range(1, n_ring - 1):
        faces.append((base, base + k + 1, base + k))

    return np.asarray(verts, dtype=np.float64), np.asarray(faces, dtype=np.int32)


def load_f03_main_hull_mesh(subdivide_levels: int = 0) -> WatertightMesh:
    """Load exact F03 48-vertex / 92-face watertight hull converted to VTX +Y port."""
    data = np.load(F03_STATIONS_NPZ)
    verts, faces = _loft_closed_stations(data['xs'], data['rings'], flip_y=True)
    mesh = WatertightMesh(
        name='rc01_f03_main_hull',
        vertices=verts,
        faces=faces,
        source_id='RC01_F03_cad_stations.npz',
    )
    if subdivide_levels > 0:
        mesh = mesh.subdivide(subdivide_levels)
    return mesh


def build_parametric_concept_a_proxy_mesh(subdivide_levels: int = 0) -> WatertightMesh:
    """Flared-bow / wider-chine parametric comparison hull proxy derived from F03.

    IMPORTANT PROVENANCE NOTE: The proprietary Concept A Blendstra studio model
    (`version_c798acaed...`) requires workspace authentication and could not be
    downloaded directly. This variant modifies F03 station deadrise & bow flare
    as a deterministic geometry-comparison harness placeholder until the
    authoritative Blendstra `.glb` export is provided.
    """
    data = np.load(F03_STATIONS_NPZ)
    xs = data['xs'].copy()
    rings = data['rings'].copy()
    # Slight bow/midship beam flare (+10% beam at chine/sheer) and 2 cm deeper V-keel forward
    for j in range(rings.shape[0]):
        flare = 1.10 if j in (1, 2, 3) else 1.04
        rings[j, :, 0] *= flare
        if j <= 2:
            rings[j, 0, 1] -= 0.025
    verts, faces = _loft_closed_stations(xs, rings, flip_y=True)
    mesh = WatertightMesh(
        name='rc01_concept_a_proxy_hull',
        vertices=verts,
        faces=faces,
        source_id='SYNTHETIC_BENCHMARK_PROXY_AWAITING_BLENDSTRA_EXPORT',
    )
    if subdivide_levels > 0:
        mesh = mesh.subdivide(subdivide_levels)
    return mesh


def load_glb_watertight_mesh(
    glb_path: str | pathlib.Path,
    name: str | None = None,
    y_up_gltf: bool = True,
    node_name: str | None = None,
) -> WatertightMesh:
    """Zero-dependency binary glTF (.glb) triangle mesh loader pinned to Physics/MuJoCo."""
    path = pathlib.Path(glb_path)
    raw = path.read_bytes()
    magic, _, _ = struct.unpack('<III', raw[:12])
    if magic != 0x46546C67:
        raise ValueError(f'{path} is not a valid glTF binary (.glb)')

    offset = 12
    json_chunk = b''
    bin_chunk = b''
    while offset < len(raw):
        c_len, c_type = struct.unpack('<II', raw[offset:offset + 8])
        c_data = raw[offset + 8:offset + 8 + c_len]
        offset += 8 + c_len
        if c_type == 0x4E4F534A:
            json_chunk = c_data
        elif c_type == 0x004E4942:
            bin_chunk = c_data

    gltf = json.loads(json_chunk.decode('utf-8'))
    accessors = gltf['accessors']
    buffer_views = gltf['bufferViews']
    nodes = gltf.get('nodes', [])
    meshes = gltf.get('meshes', [])

    def read_accessor(acc_idx: int) -> np.ndarray:
        acc = accessors[acc_idx]
        bv = buffer_views[acc['bufferView']]
        comp_type = acc['componentType']
        dtype_map = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
        dt = dtype_map[comp_type]
        type_count = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[acc['type']]
        start = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
        count = acc['count']
        arr = np.frombuffer(bin_chunk, dtype=dt, count=count * type_count, offset=start)
        return arr.reshape((count, type_count)) if type_count > 1 else arr

    target_mesh_indices: list[int] = []
    if node_name is not None:
        for n in nodes:
            if n.get('name') == node_name and 'mesh' in n:
                target_mesh_indices.append(int(n['mesh']))
        if not target_mesh_indices:
            raise KeyError(f'Mesh node {node_name!r} not found in {path}')
    else:
        target_mesh_indices = list(range(len(meshes)))

    all_verts = []
    all_norms = []
    all_colors = []
    all_faces = []
    v_off = 0
    has_colors = True
    has_normals = True
    for midx in target_mesh_indices:
        mesh_obj = meshes[midx]
        for prim in mesh_obj.get('primitives', []):
            pos_arr = read_accessor(prim['attributes']['POSITION']).astype(np.float64)
            if y_up_gltf:
                # Standard glTF Y-up (+X fwd, +Y up, -Z port) -> VTX Z-up (+X fwd, +Y port, +Z up)
                pos_arr = np.stack([pos_arr[:, 0], -pos_arr[:, 2], pos_arr[:, 1]], axis=1)
            all_verts.append(pos_arr)
            if 'NORMAL' in prim['attributes']:
                n_arr = read_accessor(prim['attributes']['NORMAL']).astype(np.float32)
                if y_up_gltf:
                    n_arr = np.stack([n_arr[:, 0], -n_arr[:, 2], n_arr[:, 1]], axis=1)
                all_norms.append(n_arr)
            else:
                has_normals = False
            if 'COLOR_0' in prim['attributes']:
                c_arr = read_accessor(prim['attributes']['COLOR_0']).astype(np.float32)
                all_colors.append(c_arr[:, :3])
            else:
                has_colors = False
            if 'indices' in prim:
                idx = read_accessor(prim['indices']).astype(np.int32).reshape(-1, 3) + v_off
            else:
                idx = np.arange(pos_arr.shape[0], dtype=np.int32).reshape(-1, 3) + v_off
            all_faces.append(idx)
            v_off += pos_arr.shape[0]

    vis_verts = np.concatenate(all_verts, axis=0)
    vis_faces = np.concatenate(all_faces, axis=0)
    vis_norms = np.concatenate(all_norms, axis=0) if has_normals and all_norms else None
    vis_colors = np.concatenate(all_colors, axis=0) if has_colors and all_colors else None

    # Keep visual face winding outward-consistent with signed physics volume
    vis_vol = float(np.sum(np.einsum('ij,ij->i', vis_verts[vis_faces[:, 0]], np.cross(vis_verts[vis_faces[:, 1]], vis_verts[vis_faces[:, 2]]))) / 6.0)
    if vis_vol < 0.0:
        vis_faces = vis_faces[:, [0, 2, 1]].copy()
        if vis_norms is not None:
            vis_norms = -vis_norms

    verts = vis_verts.copy()
    faces = vis_faces.copy()
    vcolors = vis_colors.copy() if vis_colors is not None else None
    # Weld split vertices (paint/crease seams) so MuJoCo & hydrostatic manifold watertightness holds
    _, uniq_idx, inv = np.unique(np.round(verts, 5), axis=0, return_index=True, return_inverse=True)
    if len(uniq_idx) < len(verts):
        verts = verts[uniq_idx]
        if vcolors is not None:
            vcolors = vcolors[uniq_idx]
        faces = inv[faces].astype(np.int32)
        faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]

    wmesh = WatertightMesh(
        name=name or node_name or path.stem,
        vertices=verts,
        faces=faces,
        source_id=f'{path.name}:{node_name}' if node_name else str(path.name),
    )
    if not wmesh.is_watertight():
        raise ValueError(f'Loaded GLB mesh {wmesh.name!r} from {path} is NOT manifold-watertight')
    wmesh._vertex_colors_rgb = vcolors  # type: ignore[attr-defined]
    wmesh._visual_vertices = vis_verts  # type: ignore[attr-defined]
    wmesh._visual_faces = vis_faces  # type: ignore[attr-defined]
    wmesh._visual_normals = vis_norms  # type: ignore[attr-defined]
    wmesh._visual_colors_rgb = vis_colors  # type: ignore[attr-defined]
    return wmesh


CONCEPT_A_AIRFRAME_NODE_SPECS: tuple[tuple[str, str, str, bool, tuple[float, float, float]], ...] = (
    ('wing_port', 'Ricochet_Wing_Port', 'carbon_satin', True, (0.0, 0.0, 0.0)),
    ('wing_stbd', 'Ricochet_Wing_Stbd', 'carbon_satin', True, (0.0, 0.0, 0.0)),
    ('winglet_port', 'Ricochet_Winglet_Port', 'carbon_satin', True, (0.0, 0.0, 0.0)),
    ('winglet_stbd', 'Ricochet_Winglet_Stbd', 'carbon_satin', True, (0.0, 0.0, 0.0)),
    ('strut_port', 'Ricochet_Strut_Port', 'titanium_strut', True, (0.0, 0.0, 0.0)),
    ('strut_stbd', 'Ricochet_Strut_Stbd', 'titanium_strut', True, (0.0, 0.0, 0.0)),
    ('tail_pylon_t_tail', 'Ricochet_Tail_Pylon_T_Tail', 'carbon_satin', True, (0.0, 0.0, 0.0)),
    ('duct_port', 'Ricochet_Duct_Port', 'carbon_satin', True, (0.0, 0.0, 0.0)),
    ('duct_stbd', 'Ricochet_Duct_Stbd', 'carbon_satin', True, (0.0, 0.0, 0.0)),
    ('fan_rotor_port', 'Ricochet_Fan_Rotor_Port', 'fan_rotor', True, (-2.05, 0.78, 1.56)),
    ('fan_rotor_stbd', 'Ricochet_Fan_Rotor_Stbd', 'fan_rotor', True, (-2.05, -0.78, 1.56)),
    ('fan_spinner_port', 'Ricochet_Fan_Spinner_Port', 'vtx_gold', True, (-2.05, 0.78, 1.56)),
    ('fan_spinner_stbd', 'Ricochet_Fan_Spinner_Stbd', 'vtx_gold', True, (-2.05, -0.78, 1.56)),
    ('canopy_glass', 'Ricochet_Canopy_Glass', 'canopy_glass', True, (0.0, 0.0, 0.0)),
    ('cockpit_interior', 'Ricochet_Cockpit_Interior', 'cockpit_detail', True, (0.0, 0.0, 0.0)),
    ('avionics_display', 'Ricochet_Avionics_Display', 'avionics_glow', True, (0.0, 0.0, 0.0)),
)


@dataclass
class HullVariantBundle:
    variant_id: str
    provenance: str
    main_hull: HullComponentMesh
    port_sponson: HullComponentMesh
    stbd_sponson: HullComponentMesh
    airframe_meshes: dict[str, dict[str, Any]] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            'variant_id': self.variant_id,
            'provenance': self.provenance,
            'main_hull_vertices': int(self.main_hull.mesh.vertices.shape[0]),
            'main_hull_faces': int(self.main_hull.mesh.faces.shape[0]),
            'main_hull_watertight': self.main_hull.mesh.is_watertight(),
            'main_hull_gross_volume_m3': round(self.main_hull.mesh.gross_volume_m3, 6),
            'main_hull_geometry_sha256': self.main_hull.mesh.geometry_sha256,
            'sponson_volume_each_m3': round(self.port_sponson.mesh.gross_volume_m3, 6),
            'airframe_mesh_count': len(self.airframe_meshes),
        }


class HullGeometryRegistry:
    """Provides verified F03 baseline and Concept A / custom GLB comparison bundles."""

    @staticmethod
    def build_variant(
        variant_id: str = 'f03_baseline',
        subdivide_levels: int = 0,
        concept_a_glb_path: str | pathlib.Path | None = None,
    ) -> HullVariantBundle:
        key = str(variant_id).strip().lower()
        airframe_meshes: dict[str, dict[str, Any]] = {}
        if key in ('f03', 'f03_baseline', 'rc01_f03'):
            hull_mesh = load_f03_main_hull_mesh(subdivide_levels=subdivide_levels)
            spn_p = build_uv_ellipsoid_mesh('sponson_port_mesh', SPONSON_RADII_M, source_id='F03_SPN_P')
            spn_s = build_uv_ellipsoid_mesh('sponson_stbd_mesh', SPONSON_RADII_M, source_id='F03_SPN_S')
            provenance = 'VERIFIED_F03_CAD_STATIONS'
            vid = 'f03_baseline'
        elif key in ('concept_a', 'concept_a_glb', 'concept_a_proxy', 'f03_flared_proxy'):
            glb_target = pathlib.Path(concept_a_glb_path) if concept_a_glb_path is not None else CONCEPT_A_GLB
            if glb_target.exists():
                hull_mesh = load_glb_watertight_mesh(glb_target, name='rc01_concept_a_hull', node_name='Ricochet_ConceptA_Hull_Cabin' if glb_target == CONCEPT_A_GLB else None)
                if subdivide_levels > 0:
                    hull_mesh = hull_mesh.subdivide(subdivide_levels)
                if glb_target == CONCEPT_A_GLB:
                    spn_p = load_glb_watertight_mesh(glb_target, name='sponson_port_mesh', node_name='Ricochet_Sponson_Port')
                    spn_s = load_glb_watertight_mesh(glb_target, name='sponson_stbd_mesh', node_name='Ricochet_Sponson_Stbd')
                    for part_key, node_name, mat_role, pin_mj, offset in CONCEPT_A_AIRFRAME_NODE_SPECS:
                        part_mesh = load_glb_watertight_mesh(glb_target, name=f'{part_key}_mesh', node_name=node_name)
                        airframe_meshes[part_key] = {
                            'mesh': part_mesh,
                            'material_role': mat_role,
                            'pin_to_mujoco': pin_mj,
                            'offset': list(offset),
                        }
                else:
                    spn_p = build_uv_ellipsoid_mesh('sponson_port_mesh', SPONSON_RADII_M, source_id='F03_SPN_P')
                    spn_s = build_uv_ellipsoid_mesh('sponson_stbd_mesh', SPONSON_RADII_M, source_id='F03_SPN_S')
                provenance = f'PINNED_GLB:{glb_target.name}'
            else:
                hull_mesh = build_parametric_concept_a_proxy_mesh(subdivide_levels=subdivide_levels)
                spn_p = build_uv_ellipsoid_mesh('sponson_port_mesh', SPONSON_RADII_M, source_id='F03_SPN_P')
                spn_s = build_uv_ellipsoid_mesh('sponson_stbd_mesh', SPONSON_RADII_M, source_id='F03_SPN_S')
                provenance = 'SYNTHETIC_BENCHMARK_PROXY_AWAITING_BLENDSTRA_EXPORT'
            vid = 'concept_a'
        else:
            raise ValueError(f'Unknown hull variant: {variant_id!r}')

        return HullVariantBundle(
            variant_id=vid,
            provenance=provenance,
            main_hull=HullComponentMesh('main_hull', hull_mesh, role='hull'),
            port_sponson=HullComponentMesh('sponson_port', spn_p, role='float'),
            stbd_sponson=HullComponentMesh('sponson_stbd', spn_s, role='float'),
            airframe_meshes=airframe_meshes,
        )
