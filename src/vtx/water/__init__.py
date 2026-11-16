"""VTX modular physical water environment subsystem.

Designed as a self-contained, vehicle-agnostic package so it can be reused by
Ricochet, future seaborne craft, and Vaderland without coupling to airframe-
specific code.
"""

from vtx.water.datum import (
    G_SI,
    NU_FRESHWATER_15C,
    RHO_AIR_ISA,
    RHO_FRESHWATER_15C,
    VERTICAL_DATUM,
    WATER_PHYSICS_REVISION,
    CoefficientEntry,
    HydroCalibrationProfile,
    WaterEnvironmentConfig,
)
from vtx.water.hydrodynamics import (
    HullComponentMesh,
    HydroBreakdown,
    WatertightMesh,
    evaluate_components_hydrodynamics,
    evaluate_mesh_hydrodynamics,
)
from vtx.water.lake_world import RicochetLakeWorld
from vtx.water.open_water import OpenWaterWaveField, WaveSample, solve_dispersion_wavenumber
from vtx.water.shallow_water import HybridWaterField, HybridWaterSample, ShallowWaterSolver

__all__ = [
    'G_SI',
    'NU_FRESHWATER_15C',
    'RHO_AIR_ISA',
    'RHO_FRESHWATER_15C',
    'VERTICAL_DATUM',
    'WATER_PHYSICS_REVISION',
    'CoefficientEntry',
    'HydroCalibrationProfile',
    'WaterEnvironmentConfig',
    'RicochetLakeWorld',
    'OpenWaterWaveField',
    'WaveSample',
    'solve_dispersion_wavenumber',
    'ShallowWaterSolver',
    'HybridWaterField',
    'HybridWaterSample',
    'WatertightMesh',
    'HullComponentMesh',
    'HydroBreakdown',
    'evaluate_mesh_hydrodynamics',
    'evaluate_components_hydrodynamics',
]
