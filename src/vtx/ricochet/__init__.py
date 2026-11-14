"""Ricochet RC-01 MuJoCo vehicle plant, mass register, hulls, and test scenarios."""

from vtx.ricochet.hull_geometry import HullGeometryRegistry, HullVariantBundle, load_f03_main_hull_mesh
from vtx.ricochet.mass_register import MassComponent, MassPropertiesRegister, polar_f03_to_vtx, axial_f03_to_vtx
from vtx.ricochet.plant import RicochetCraft, SOLVER_VERSION, is_ricochet_variant
from vtx.ricochet.scenarios import SCENARIO_CATALOG, run_ricochet_scenario

__all__ = [
    'HullGeometryRegistry',
    'HullVariantBundle',
    'load_f03_main_hull_mesh',
    'MassComponent',
    'MassPropertiesRegister',
    'polar_f03_to_vtx',
    'axial_f03_to_vtx',
    'RicochetCraft',
    'SOLVER_VERSION',
    'is_ricochet_variant',
    'SCENARIO_CATALOG',
    'run_ricochet_scenario',
]
