"""RC-01 F03-to-VTX *contract*, not an installed water-force runtime.

No hidden lift, no changes to existing VTX physics. Positions are SI and +Z up.
VTX body convention is +X forward, +Y left, +Z up (see Phantom integration).
F03 labelled its body +Y starboard, so transform polar vs axial quantities
explicitly and validate signs before using F03 loads in a MuJoCo integrator.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

G = 9.80665
ISA_P0_PA = 101325.0
ISA_T0_K = 288.15
F03_WATER_DENSITY_KGM3 = 999.1
F03_WATER_Z_M = 0.0
EXPECTED_LAKE_CENTRE_M = (-265.0, 30.0)
EXPECTED_LAKE_HALF_EXTENTS_M = (28.0, 80.0)

class UnsupportedPhysics(RuntimeError):
    """Explicit refusal when no physical lake/forces are present."""

@dataclass(frozen=True)
class ReferenceLake:
    centre_xy_m: tuple[float, float]
    half_extents_xy_m: tuple[float, float]
    surface_z_m: float = F03_WATER_Z_M
    assumed_bed_z_m: float = -3.0  # F03 VIRTUAL bathymetry only

    def contains(self, x_m: float, y_m: float, clearance_m: float = 0.0) -> bool:
        hx, hy = self.half_extents_xy_m
        cx, cy = self.centre_xy_m
        return abs(x_m - cx) <= hx - clearance_m and abs(y_m - cy) <= hy - clearance_m


def world_lake_reference(world_public: dict) -> ReferenceLake:
    """Read exactly the existing VTX water extents. Do not change world.py."""
    w = world_public['water']
    lake = ReferenceLake((float(w['x']), float(w['y'])),
                         (float(w['half_x']), float(w['half_y'])))
    if lake.centre_xy_m != EXPECTED_LAKE_CENTRE_M or lake.half_extents_xy_m != EXPECTED_LAKE_HALF_EXTENTS_M:
        raise ValueError('VTX environment water geometry changed: rebaseline required')
    return lake


def assert_physical_water_supported(world_public: dict) -> None:
    """Fail closed: existing water is visual. An explicit physics revision is required."""
    if world_public.get('water_physics_revision') is None or not world_public.get('bathymetry_verified', False):
        raise UnsupportedPhysics('Visual-only VTX water: no certified bathymetry or buoyancy forces; keep isolated F03')
    if world_public.get('water_physics_revision') not in ('vtx-water-multibody-1',):
        raise UnsupportedPhysics('Unknown water solver revision: do not inject provisional F03 forces')


def polar_body_f03_to_vtx(v):
    """Reflect F03 polar XYZ body coordinates to VTX +Y port/left body axes."""
    x, y, z = map(float, v)
    return (x, -y, z)


def axial_body_f03_to_vtx(v):
    """Pseudovector transform det(R) R, R=diag(1,-1,1): torque, omega, H."""
    x, y, z = map(float, v)
    return (-x, y, -z)


def inertia_tensor_f03_to_vtx(tensor):
    """I' = R I R^T for reflection R=diag(1,-1,1)."""
    if len(tensor) != 3 or any(len(row) != 3 for row in tensor):
        raise ValueError('Need 3x3 inertia tensor')
    s = (1, -1, 1)
    return [[float(tensor[i][j]) * s[i] * s[j] for j in range(3)] for i in range(3)]


def f03_to_world_position(record: dict, lake: ReferenceLake):
    """Lab world axes follow VTX world XY; only add origin, do NOT mirror world Y."""
    return (lake.centre_xy_m[0] + float(record['x_m']),
            lake.centre_xy_m[1] + float(record['y_m']),
            float(record['z_origin_m']))


def f03_world_heading_deg(record: dict) -> float:
    """F03 CSV yaw is relative to the initial +Y heading; restore +90 degrees."""
    return float(record['yaw_deg']) + 90.0


def f03_velocity_body_projection(record: dict) -> tuple[float,float]:
    """World +X,+Y -> forward/side under corrected *world* heading.
    Positive side is mathematical body left for right-handed world; label explicitly.
    """
    yaw = math.radians(f03_world_heading_deg(record))
    vx, vy = float(record['vx_mps']), float(record['vy_mps'])
    return (vx * math.cos(yaw) + vy * math.sin(yaw),
            -vx * math.sin(yaw) + vy * math.cos(yaw))


def integration_status() -> dict:
    return dict(level='ISOLATED_ONLY',engine='F03 reduced-order Python, not VTX MuJoCo',
                water_support='NOT_AVAILABLE_IN_MAIN',
                hull='F03 closed geometric hull, physical shell/bonds not validated',
                joints='F02 keepouts, not flexural/joint dynamics',
                next_gate='MuJoCo water coupling + hydrostatics force checks + frame parity + regression suite')
