"""Physical constants, vertical datum, and calibration metadata for VTX water worlds.

All quantities use strict SI units (metres, kilograms, seconds, radians, newtons,
pascals) in a right-handed Z-up coordinate system:
    +X : East / Forward along open-water basin axis
    +Y : North / Port in nominal craft start heading
    +Z : Upward against gravity

Vertical Datum:
    z = 0.0 m is Mean Lake Datum (MLD), corresponding to nominal zero-offset
    calm lake surface (`water_level_m = 0.0`). Bathymetry elevations have z < 0
    for submerged bed and z > 0 for shorelines, quays, breakwater, and ramps.
    Local still-water depth is `max(0.0, water_level_m - terrain_z(x, y))`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

G_SI = 9.80665
RHO_FRESHWATER_15C = 999.1  # kg/m^3 (Kell / IAPWS freshwater at 15 deg C, ISA sea-level)
NU_FRESHWATER_15C = 1.139e-6  # m^2/s kinematic viscosity at 15 deg C
RHO_AIR_ISA = 1.225  # kg/m^3 at ISA sea-level (101325 Pa, 288.15 K)

VERTICAL_DATUM = {
    'name': 'VTX-MLD-SI',
    'units': 'm',
    'zero_elevation_m': 0.0,
    'description': (
        'Mean Lake Datum (MLD): z = 0.0 m is nominal still-water surface; '
        'bed bathymetry is negative (z < 0), banks/ramps/quays are positive (z > 0).'
    ),
    'positive_axes': {'x': 'East (+X)', 'y': 'North / Port (+Y)', 'z': 'Up (+Z)'},
}

WATER_PHYSICS_REVISION = 'vtx-water-multibody-1'


@dataclass(frozen=True)
class CoefficientEntry:
    """Tracks provenance, calibration status, and uncertainty for a hydrodynamic term."""

    name: str
    value: float
    units: str
    status: Literal['derived_geometry', 'standard_empirical', 'provisional_unverified', 'calibrated']
    source: str
    calibration_pathway: str
    uncertainty_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HydroCalibrationProfile:
    """Hydrodynamic model coefficient register with explicit calibration provenance.

    Note: Provisional values provide physically structured placeholders based on
    ITTC/strip-theory/Savitsky baselines where towing-tank or CFD data for the
    exact stepped-hull RC-01 F03 geometry are not yet available.
    """

    profile_id: str = 'f03-provisional-v1'
    skin_friction_roughness_allowance: float = 4.0e-4  # ITTC-57 delta-CF
    form_factor_k: float = 0.18
    pressure_drag_normal_cd: float = 1.05
    slamming_pressure_coeff: float = 0.45
    planing_lift_coeff: float = 0.35
    added_mass_heave_factor: float = 0.65
    added_mass_sway_factor: float = 0.85
    added_mass_surge_factor: float = 0.08
    added_mass_roll_factor: float = 0.25
    added_mass_pitch_factor: float = 0.55
    added_mass_yaw_factor: float = 0.45
    linear_heave_damping_ratio: float = 0.22
    linear_roll_damping_ratio: float = 0.36
    linear_pitch_damping_ratio: float = 0.28
    quadratic_roll_damping: float = 440.0
    munk_viscous_relief: float = 0.35
    aft_skeg_lift_coeff: float = 0.15
    wave_froude_krylov_scale: float = 1.0
    wave_diffraction_damping_scale: float = 0.25
    wet_dry_blend_band_m: float = 0.03

    def registry(self) -> list[CoefficientEntry]:
        return [
            CoefficientEntry(
                name='skin_friction_ittc57',
                value=self.skin_friction_roughness_allowance,
                units='dimensionless',
                status='standard_empirical',
                source='ITTC 1957 model-ship correlation line + surface allowance',
                calibration_pathway='Clean-hull resistance tow test at Re = 1e6..2e7',
                uncertainty_pct=15.0,
            ),
            CoefficientEntry(
                name='form_factor_k',
                value=self.form_factor_k,
                units='dimensionless',
                status='provisional_unverified',
                source='Provisional 3D viscous pressure form factor for faceted hull',
                calibration_pathway='Prohaska low-Fr tow test or RANS double-body CFD',
                uncertainty_pct=35.0,
            ),
            CoefficientEntry(
                name='pressure_drag_normal_cd',
                value=self.pressure_drag_normal_cd,
                units='dimensionless',
                status='provisional_unverified',
                source='Bluff/chined cross-flow drag coefficient per wetted facet',
                calibration_pathway='Oblique towing tank / planar motion mechanism (PMM)',
                uncertainty_pct=30.0,
            ),
            CoefficientEntry(
                name='planing_lift_coeff',
                value=self.planing_lift_coeff,
                units='dimensionless',
                status='provisional_unverified',
                source='Provisional semi-empirical Savitsky/deadrise dynamic lift factor',
                calibration_pathway='High-speed hump & planing run trim/rise calibration or VOF CFD',
                uncertainty_pct=45.0,
            ),
            CoefficientEntry(
                name='added_mass_factors',
                value=self.added_mass_heave_factor,
                units='ratio_to_displaced_mass',
                status='provisional_unverified',
                source='Provisional strip-theory / ellipsoid added-mass multipliers',
                calibration_pathway='Potential-flow BEM (Capytaine/WAMIT) or forced oscillation PMM',
                uncertainty_pct=35.0,
            ),
            CoefficientEntry(
                name='linear_and_quadratic_damping',
                value=self.linear_roll_damping_ratio,
                units='damping_ratio',
                status='provisional_unverified',
                source='Provisional radiation + bilge/chine vortex roll/pitch/heave damping',
                calibration_pathway='Calm-water free-decay test in roll, pitch, and heave',
                uncertainty_pct=40.0,
            ),
            CoefficientEntry(
                name='wave_froude_krylov_scale',
                value=self.wave_froude_krylov_scale,
                units='dimensionless',
                status='derived_geometry',
                source='Exact wet-facet dynamic pressure integral (-rho * dPhi/dt) * scale',
                calibration_pathway='Regular head/beam wave RAO tank validation for diffraction term',
                uncertainty_pct=20.0,
            ),
            CoefficientEntry(
                name='munk_viscous_relief',
                value=self.munk_viscous_relief,
                units='dimensionless',
                status='standard_empirical',
                source='Viscous Kutta stern separation relief on potential-flow Munk torque',
                calibration_pathway='Oblique towing tank yaw moment slope vs yaw angle',
                uncertainty_pct=25.0,
            ),
            CoefficientEntry(
                name='aft_skeg_lift_coeff',
                value=self.aft_skeg_lift_coeff,
                units='1/rad',
                status='provisional_unverified',
                source='Slender-body aft deadwood/step directional Kutta restoring lift',
                calibration_pathway='Pure-sway / oblique PMM weathercock stability derivative N_v',
                uncertainty_pct=30.0,
            ),
        ]

    def apply_overrides(self, overrides: dict[str, float]) -> 'HydroCalibrationProfile':
        """Return a new calibrated profile with explicit field overrides."""
        data = asdict(self)
        for key, val in overrides.items():
            if key not in data or key == 'profile_id':
                raise KeyError(f'Unknown calibration parameter: {key!r}')
            data[key] = float(val)
        data['profile_id'] = f"{self.profile_id}-calibrated"
        return HydroCalibrationProfile(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            'profile_id': self.profile_id,
            'parameters': asdict(self),
            'registry': [entry.to_dict() for entry in self.registry()],
        }


@dataclass
class WaterEnvironmentConfig:
    """User-configurable physical water, wind, current, and wave parameters."""

    water_level_m: float = 0.0
    wave_mode: Literal['still', 'regular', 'irregular'] = 'still'
    wave_height_m: float = 0.35
    wave_period_s: float = 4.0
    wave_direction_deg: float = 200.0  # Direction waves propagate toward (deg CCW from +X)
    wave_phase_rad: float = 0.0
    wave_seed: int = 41031
    wave_components: int = 24
    wind_speed_mps: float = 3.0
    wind_direction_deg: float = 200.0
    current_speed_mps: float = 0.0
    current_direction_deg: float = 0.0
    shallow_water_enabled: bool = True
    shallow_water_substeps: int = 2
    whirlpools_enabled: bool = True
    whirlpool_intensity: float = 1.0
    wake_enabled: bool = True
    rho_water_kg_m3: float = RHO_FRESHWATER_15C
    nu_water_m2_s: float = NU_FRESHWATER_15C
    g_m_s2: float = G_SI

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> 'WaterEnvironmentConfig':
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in payload.items() if k in valid_fields}
        return cls(**filtered)
