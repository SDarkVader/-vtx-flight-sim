"""Component-level Mass Properties Register & F03->VTX transform for Ricochet RC-01.

Implements the Notion F03 Mass Properties & Water-Loading Envelope structure
with strict SI units, parallel-axis inertia tensor aggregation, versioned loading
contracts (``rc01-f03-lc-v2`` vs historical ``rc01-lc-v1``), and explicit
status tagging so provisional unweighed mass items remain identifiable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Literal

import numpy as np


DEFAULT_REGISTER_VERSION = 'rc01-f03-lc-v2'
LEGACY_REGISTER_VERSION = 'rc01-lc-v1'
SUPPORTED_REGISTER_VERSIONS: tuple[str, ...] = (
    DEFAULT_REGISTER_VERSION,
    LEGACY_REGISTER_VERSION,
)

PropulsionInstallation = Literal['baseline_pack', 'fuel_cell_paired', 'energy_pack_alternate']
PROPULSION_INSTALLATIONS: tuple[PropulsionInstallation, ...] = (
    'baseline_pack',
    'fuel_cell_paired',
    'energy_pack_alternate',
)


def polar_f03_to_vtx(vec: np.ndarray | list[float] | tuple[float, float, float]) -> np.ndarray:
    """Transform body-frame polar vector from F03 (+Y stbd) to VTX (+Y port)."""
    v = np.asarray(vec, dtype=np.float64)
    return np.array([v[0], -v[1], v[2]], dtype=np.float64)


def axial_f03_to_vtx(vec: np.ndarray | list[float] | tuple[float, float, float]) -> np.ndarray:
    """Transform angular velocity / torque pseudovector from F03 (+Y stbd) to VTX (+Y port)."""
    v = np.asarray(vec, dtype=np.float64)
    return np.array([-v[0], v[1], -v[2]], dtype=np.float64)


def inertia_f03_to_vtx(inertia_3x3: np.ndarray) -> np.ndarray:
    """Apply Y-reflection similarity transform S * I * S to 3x3 inertia tensor."""
    s = np.diag([1.0, -1.0, 1.0])
    return s @ np.asarray(inertia_3x3, dtype=np.float64) @ s


@dataclass
class MassComponent:
    """Single rigid/variable mass item defined in F03 coordinates (+X fwd, +Y stbd, +Z up)."""

    component_id: str
    label: str
    mass_kg: float
    cg_f03_m: tuple[float, float, float]
    local_inertia_diag_kg_m2: tuple[float, float, float]
    status: Literal['derived_geometry', 'envelope_nominal', 'provisional_unverified'] = 'provisional_unverified'
    movable: bool = False
    notes: str = ''

    def cg_vtx_m(self) -> np.ndarray:
        return polar_f03_to_vtx(self.cg_f03_m)

    def to_dict(self) -> dict[str, Any]:
        return {
            'component_id': self.component_id,
            'label': self.label,
            'mass_kg': round(float(self.mass_kg), 3),
            'cg_f03_m': [round(float(v), 5) for v in self.cg_f03_m],
            'cg_vtx_m': [round(float(v), 5) for v in self.cg_vtx_m()],
            'local_inertia_diag_kg_m2': [round(float(v), 3) for v in self.local_inertia_diag_kg_m2],
            'status': self.status,
            'movable': self.movable,
            'notes': self.notes,
        }


# F02 keepout coordinates & bounds verbatim from experiments/ricochet/rc01_f03/model/blendstra_rebuild.py:222-225
F02_KEEPOUT_ENVELOPES: dict[str, dict[str, Any]] = {
    'PILOT_SEAT_TRACK': {
        'mode': 'linear X +/-0.12',
        'center_f03_m': (1.30, 0.0, 0.80),
        'bounds_m': (0.66, 0.70, 0.88),
        'mass_placeholder_kg': 85.0,
        'notes': 'F02 seat track linear X +/-0.12 m; pilot mass used only in sensitivity example',
    },
    'FUEL_CELL_PORT': {
        'mode': 'fluid fill/slosh',
        'center_f03_m': (-1.05, -0.23, 0.55),
        'bounds_m': (0.80, 0.27, 0.40),
        'mass_placeholder_kg': None,
        'notes': 'density, usable mass, slosh and tanks unverified',
    },
    'FUEL_CELL_STARBOARD': {
        'mode': 'fluid fill/slosh',
        'center_f03_m': (-1.05, 0.23, 0.55),
        'bounds_m': (0.80, 0.27, 0.40),
        'mass_placeholder_kg': None,
        'notes': 'paired fill must conserve lateral CG',
    },
    'ENERGY_PACK_ALTERNATE': {
        'mode': 'installation/service',
        'center_f03_m': (-1.02, 0.0, 0.69),
        'bounds_m': (0.95, 0.50, 0.34),
        'mass_placeholder_kg': None,
        'notes': 'ALTERNATIVE to competing fuel-envelope, not simultaneous',
    },
}

# Provisional fuel-state presets for LC-03 paired F02 fuel-cell bays.
# Per F02 (blendstra_rebuild.py:223-224), fuel cell tank density, usable capacity,
# and slosh remain provisional_unverified; 'nominal' aligns with plant.py fuel_initial (10 kg).
FUEL_STATE_MASSES_KG: dict[str, float] = {
    'dry': 0.0,
    'short_test': 5.0,
    'nominal': 10.0,
    'full': 20.0,
}

PROPULSION_INSTALLATION_SPECS: dict[str, dict[str, Any]] = {
    'baseline_pack': {
        'subcase_id': 'LC-04A_baseline_pack',
        'label': 'Forward hull bilge energy pack (F03 baseline)',
        'keepout_ids': ['energy_propulsion_pack'],
        'centers_f03_m': {'energy_propulsion_pack': (1.62, 0.0, 0.40)},
        'bounds_m': {},
        'mutually_exclusive_with': ['fuel_cell_paired', 'energy_pack_alternate'],
        'thrust_vector_f03': [1.0, 0.0, 0.0],
        'propulsor_component_ids': ['ducted_fan_port', 'ducted_fan_stbd', 'tail_pylon_t_tail'],
        'mass_conservation_note': 'Declared 170.0 kg energy_propulsion_pack at forward bilge (1.62, 0.0, 0.40)',
        'unverified_subsystems': [
            'motor/gearbox/cooling/controllers',
            'plumbing/cabling/reinforcement',
            'thrust_torque_power_map',
            'vibration_and_mount_reactions',
        ],
        'status': 'provisional_unverified',
    },
    'fuel_cell_paired': {
        'subcase_id': 'LC-04B_fuel_cell_paired',
        'label': 'Paired aft fuel-cell bays (F02 FUEL_CELL_PORT / FUEL_CELL_STARBOARD)',
        'keepout_ids': ['FUEL_CELL_PORT', 'FUEL_CELL_STARBOARD'],
        'centers_f03_m': {
            'FUEL_CELL_PORT': (-1.05, -0.23, 0.55),
            'FUEL_CELL_STARBOARD': (-1.05, 0.23, 0.55),
        },
        'bounds_m': {
            'FUEL_CELL_PORT': (0.80, 0.27, 0.40),
            'FUEL_CELL_STARBOARD': (0.80, 0.27, 0.40),
        },
        'mutually_exclusive_with': ['baseline_pack', 'energy_pack_alternate'],
        'thrust_vector_f03': [1.0, 0.0, 0.0],
        'propulsor_component_ids': ['ducted_fan_port', 'ducted_fan_stbd', 'tail_pylon_t_tail'],
        'mass_conservation_note': (
            'Conserves declared 170.0 kg energy_propulsion_pack split symmetrically (85.0 kg port + 85.0 kg stbd) '
            'plus declared fuel_mass_kg at (-1.05, +/-0.23, 0.55); tank/plumbing weights unverified per F02'
        ),
        'unverified_subsystems': [
            'fuel_cell_tank_density_and_capacity',
            'motor/gearbox/cooling/controllers',
            'plumbing/cabling/reinforcement',
            'thrust_torque_power_map',
            'vibration_and_mount_reactions',
        ],
        'status': 'provisional_unverified',
    },
    'energy_pack_alternate': {
        'subcase_id': 'LC-04C_energy_pack_alternate',
        'label': 'Alternate aft energy pack bay (F02 ENERGY_PACK_ALTERNATE)',
        'keepout_ids': ['ENERGY_PACK_ALTERNATE'],
        'centers_f03_m': {'ENERGY_PACK_ALTERNATE': (-1.02, 0.0, 0.69)},
        'bounds_m': {'ENERGY_PACK_ALTERNATE': (0.95, 0.50, 0.34)},
        'mutually_exclusive_with': ['baseline_pack', 'fuel_cell_paired'],
        'thrust_vector_f03': [1.0, 0.0, 0.0],
        'propulsor_component_ids': ['ducted_fan_port', 'ducted_fan_stbd', 'tail_pylon_t_tail'],
        'mass_conservation_note': (
            'Relocates declared 170.0 kg energy_propulsion_pack to (-1.02, 0.0, 0.69); '
            'mutually exclusive with FUEL_CELL_* per F02'
        ),
        'unverified_subsystems': [
            'motor/gearbox/cooling/controllers',
            'plumbing/cabling/reinforcement',
            'thrust_torque_power_map',
            'vibration_and_mount_reactions',
        ],
        'status': 'provisional_unverified',
    },
}

LOAD_CASE_DESCRIPTIONS_V1: dict[str, str] = {
    'LC-01': 'Empty-payload light ship, unoccupied, zero thrust (815 kg)',
    'LC-02': 'Unoccupied stowed airframe, propulsion armed idle / water motion (815 kg)',
    'LC-03': 'F03 nominal manned water trial envelope (pilot + full nominal 900 kg design mass)',
    'LC-04': 'Max water-loading & payload envelope (pilot + ballast/pack at 1050 kg RC-01 upper limit)',
}

LOAD_CASE_DESCRIPTIONS_V2: dict[str, str] = {
    'LC-01': (
        'Passenger aboard, underway (85 kg passenger on F02 seat track (1.30, 0.0, 0.80), '
        'nominal 900.0 kg F03 manned trial; reduced-order F03 target CG ~ [0.45, 0.0, 0.59])'
    ),
    'LC-02': 'Unoccupied and stowed on water, propulsion off/stowed, motion caused by water (815.0 kg)',
    'LC-03': (
        'Empty-payload flotation without passenger, with declared fuel state in paired F02 '
        'FUEL_CELL_PORT/STARBOARD keepouts conserving lateral CG y=0 (815.0 kg dry + fuel, provisional_unverified)'
    ),
    'LC-04': (
        'Propulsion installation comparison across mutually exclusive F02 keepouts '
        '(baseline_pack vs fuel_cell_paired vs energy_pack_alternate, provisional_unverified)'
    ),
    'LC-MAX': (
        'Maximum-payload RC-01 experiment (85 kg passenger + 150 kg payload = 1050.0 kg; '
        'upper bound of RC01_F03_mass_cg_sensitivity.csv, alias LC-05_MAX_PAYLOAD)'
    ),
}

LOAD_CASE_DESCRIPTIONS = LOAD_CASE_DESCRIPTIONS_V2

LOAD_CASE_DESCRIPTIONS_BY_VERSION: dict[str, dict[str, str]] = {
    LEGACY_REGISTER_VERSION: LOAD_CASE_DESCRIPTIONS_V1,
    DEFAULT_REGISTER_VERSION: LOAD_CASE_DESCRIPTIONS_V2,
}

LOAD_CASE_ALIASES_V2: dict[str, str] = {
    'LC-01': 'LC-01',
    'LC-02': 'LC-02',
    'LC-03': 'LC-03',
    'LC-04': 'LC-04',
    'LC-MAX': 'LC-MAX',
    'LC-05_MAX_PAYLOAD': 'LC-MAX',
    'LC-05': 'LC-MAX',
}

LOAD_CASE_ALIASES_V1: dict[str, str] = {
    'LC-01': 'LC-01',
    'LC-02': 'LC-02',
    'LC-03': 'LC-03',
    'LC-04': 'LC-04',
    'LC-MAX': 'LC-04',
    'LC-05_MAX_PAYLOAD': 'LC-04',
    'LC-05': 'LC-04',
}


def normalize_register_version(register_version: str | None) -> str:
    """Validate and return canonical loading-contract version identifier."""
    if register_version is None:
        return DEFAULT_REGISTER_VERSION
    ver = str(register_version).strip()
    if ver not in SUPPORTED_REGISTER_VERSIONS:
        raise ValueError(
            f'Unknown register_version {register_version!r}; expected one of {SUPPORTED_REGISTER_VERSIONS}'
        )
    return ver


def normalize_load_case(
    load_case: str | None,
    register_version: str = DEFAULT_REGISTER_VERSION,
) -> str:
    """Resolve canonical load-case key for the given register_version."""
    ver = normalize_register_version(register_version)
    if load_case is None or str(load_case).strip() == '':
        return 'LC-01' if ver == DEFAULT_REGISTER_VERSION else 'LC-03'
    raw = str(load_case).strip().upper()
    aliases = LOAD_CASE_ALIASES_V2 if ver == DEFAULT_REGISTER_VERSION else LOAD_CASE_ALIASES_V1
    if raw not in aliases:
        valid = sorted(set(aliases.values()))
        raise ValueError(f'Unknown load_case {load_case!r} for {ver}; expected one of {valid}')
    return aliases[raw]


def describe_load_case(load_case: str, register_version: str = DEFAULT_REGISTER_VERSION) -> str:
    """Return human-readable description for load_case under register_version."""
    ver = normalize_register_version(register_version)
    table = LOAD_CASE_DESCRIPTIONS_BY_VERSION[ver]
    return table.get(load_case, '')


def resolve_fuel_state(
    fuel_state: str | None = None,
    fuel_mass_kg: float | None = None,
) -> tuple[str, float]:
    """Resolve declared fuel_state preset and/or explicit fuel_mass_kg (kg)."""
    state_norm: str | None = None
    if fuel_state is not None:
        state_norm = str(fuel_state).strip().lower()
        if state_norm == '':
            state_norm = None
        elif state_norm != 'custom' and state_norm not in FUEL_STATE_MASSES_KG:
            raise ValueError(
                f'Unknown fuel_state {fuel_state!r}; expected one of {list(FUEL_STATE_MASSES_KG) + ["custom"]}'
            )

    if fuel_mass_kg is not None:
        mass = float(fuel_mass_kg)
        if not math.isfinite(mass) or mass < 0.0:
            raise ValueError(f'fuel_mass_kg must be finite and >= 0.0, got {fuel_mass_kg!r}')
        if state_norm is None or state_norm == 'custom':
            resolved_state = 'dry' if mass <= 1e-9 else 'custom'
        else:
            preset = FUEL_STATE_MASSES_KG[state_norm]
            resolved_state = state_norm if abs(mass - preset) <= 1e-6 else 'custom'
        return resolved_state, mass

    if state_norm is None:
        return 'dry', 0.0
    if state_norm == 'custom':
        raise ValueError("fuel_mass_kg is required when fuel_state='custom'")
    return state_norm, float(FUEL_STATE_MASSES_KG[state_norm])


def normalize_propulsion_installation(
    propulsion_installation: str | None,
    load_case: str = 'LC-01',
    register_version: str = DEFAULT_REGISTER_VERSION,
) -> PropulsionInstallation:
    """Validate and resolve propulsion installation key for load_case and register_version."""
    ver = normalize_register_version(register_version)
    if propulsion_installation is None or str(propulsion_installation).strip() == '':
        if ver == DEFAULT_REGISTER_VERSION and load_case == 'LC-04':
            return 'energy_pack_alternate'
        return 'baseline_pack'
    inst = str(propulsion_installation).strip().lower()
    if inst not in PROPULSION_INSTALLATIONS:
        raise ValueError(
            f'Unknown propulsion_installation {propulsion_installation!r}; '
            f'expected one of {PROPULSION_INSTALLATIONS}'
        )
    return inst  # type: ignore[return-value]


def _box_inertia_diag(mass_kg: float, bounds_m: tuple[float, float, float]) -> tuple[float, float, float]:
    m = max(0.0, float(mass_kg))
    dx, dy, dz = bounds_m
    return (
        m * (dy * dy + dz * dz) / 12.0,
        m * (dx * dx + dz * dz) / 12.0,
        m * (dx * dx + dy * dy) / 12.0,
    )


def _base_f03_components(sponson_z_m: float = 0.42) -> list[MassComponent]:
    """Existing F01/F02/F03 mass register items summing to 815.0 kg light ship."""
    return [
        MassComponent(
            'hull_primary_shell',
            'CFRP hull frame, bulkheads & open cockpit tub shell',
            332.0,
            (0.62, 0.0, 0.44),
            (92.0, 600.0, 640.0),
            status='provisional_unverified',
            notes='F01/F02 structural hull + cockpit tub (not weighed)',
        ),
        MassComponent(
            'canopy_glass',
            'Panoramic tinted polycarbonate/glass canopy dome',
            16.0,
            (1.36, 0.0, 1.24),
            (2.2, 6.4, 5.8),
            status='derived_geometry',
            notes='Attached canopy dome shell over open cockpit tub',
        ),
        MassComponent(
            'cockpit_avionics',
            'Pilot seat, harness, control stick & dual MFD console',
            14.0,
            (1.22, 0.0, 0.78),
            (1.4, 3.2, 3.0),
            status='derived_geometry',
            notes='Attached cockpit seat, stick & glass avionics pod',
        ),
        MassComponent(
            'wing_assembly',
            '9.6 m main wing, winglets & carry-through spars',
            155.0,
            (0.18, 0.0, 0.96),
            (505.0, 88.0, 565.0),
            status='provisional_unverified',
            notes='Spanwise CFRP box + ribs + winglets',
        ),
        MassComponent(
            'strut_port',
            'Port titanium main & diagonal sponson strut',
            5.0,
            (-0.26, -3.55, 0.78),
            (0.6, 0.5, 0.3),
            status='derived_geometry',
            notes='Attached port wing-to-sponson structural strut (F03 +Y stbd -> -3.55 port)',
        ),
        MassComponent(
            'strut_stbd',
            'Starboard titanium main & diagonal sponson strut',
            5.0,
            (-0.26, 3.55, 0.78),
            (0.6, 0.5, 0.3),
            status='derived_geometry',
            notes='Attached starboard wing-to-sponson structural strut',
        ),
        MassComponent(
            'tail_pylon_t_tail',
            'Swept vertical tail pylon, H-tail & lateral fan mounts',
            38.0,
            (-2.05, 0.0, 1.72),
            (18.0, 42.0, 36.0),
            status='derived_geometry',
            notes='Attached T-tail stabilizer + vertical fin',
        ),
        MassComponent(
            'ducted_fan_port',
            'Port Ø0.90 m ducted fan shroud, stator, 9-blade rotor & motor',
            28.0,
            (-2.05, -0.78, 1.56),
            (4.8, 4.2, 4.2),
            status='envelope_nominal',
            notes='Documented Ø0.90 m aft ducted fan unit (port)',
        ),
        MassComponent(
            'ducted_fan_stbd',
            'Starboard Ø0.90 m ducted fan shroud, stator, 9-blade rotor & motor',
            28.0,
            (-2.05, 0.78, 1.56),
            (4.8, 4.2, 4.2),
            status='envelope_nominal',
            notes='Documented Ø0.90 m aft ducted fan unit (starboard)',
        ),
        MassComponent(
            'energy_propulsion_pack',
            'Energy storage pack & drive wiring (provisional)',
            170.0,
            (1.62, 0.0, 0.40),
            (14.0, 28.0, 32.0),
            status='envelope_nominal',
            notes='Positioned forward inside hull bilge bay to balance aft pylon moment',
        ),
        MassComponent(
            'sponson_port',
            'Port outboard chined sponson float (structural + actuator)',
            12.0,
            (-0.34, -3.80, float(sponson_z_m)),
            (0.8, 1.6, 1.6),
            status='envelope_nominal',
            movable=True,
            notes='F02 keepout nominal 12 kg placeholder',
        ),
        MassComponent(
            'sponson_stbd',
            'Starboard outboard chined sponson float (structural + actuator)',
            12.0,
            (-0.34, 3.80, float(sponson_z_m)),
            (0.8, 1.6, 1.6),
            status='envelope_nominal',
            movable=True,
            notes='F02 keepout nominal 12 kg placeholder',
        ),
    ]


@dataclass
class MassPropertiesRegister:
    """Aggregates active structural, propulsion, float, passenger, fuel, and payload items."""

    load_case: str = 'LC-01'
    register_version: str = DEFAULT_REGISTER_VERSION
    passenger_aboard: bool = True
    passenger_mass_kg: float = 85.0
    passenger_x_offset_m: float = 0.0
    payload_mass_kg: float = 0.0
    extra_mass_kg: float = 0.0
    cg_shift_vtx_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    ballast_mass_kg: float = 0.0
    ballast_x_m: float = -0.15
    ballast_y_m: float = 0.0
    waterproof: bool = True
    flood_water_kg: float = 0.0
    fuel_state: str | None = 'dry'
    fuel_mass_kg: float = 0.0
    propulsion_installation: PropulsionInstallation = 'baseline_pack'
    propulsion_off: bool = False
    components: list[MassComponent] = field(default_factory=list)

    @classmethod
    def for_load_case(
        cls,
        load_case: str | None = None,
        passenger_aboard: bool | None = None,
        passenger_mass_kg: float | None = None,
        payload_mass_kg: float | None = None,
        sponson_z_m: float = 0.42,
        ballast_mass_kg: float = 0.0,
        ballast_x_m: float = -0.15,
        ballast_y_m: float = 0.0,
        waterproof: bool = True,
        register_version: str = DEFAULT_REGISTER_VERSION,
        fuel_state: str | None = None,
        fuel_mass_kg: float | None = None,
        propulsion_installation: PropulsionInstallation | None = None,
        propulsion_off: bool | None = None,
    ) -> 'MassPropertiesRegister':
        ver = normalize_register_version(register_version)
        lc = normalize_load_case(load_case, register_version=ver)
        base_items = _base_f03_components(sponson_z_m=sponson_z_m)

        if ver == LEGACY_REGISTER_VERSION:
            if lc in ('LC-01', 'LC-02'):
                pax_on, pax_m, pay_m = False, 0.0, 0.0
            elif lc == 'LC-03':
                pax_on, pax_m, pay_m = True, 85.0, 0.0
            else:  # LC-04 (1050.0 kg upper bound in legacy v1 contract)
                pax_on, pax_m, pay_m = True, 85.0, 150.0
            default_prop_off = False
        else:
            if lc == 'LC-01':
                pax_on, pax_m, pay_m = True, 85.0, 0.0
                default_prop_off = False
            elif lc == 'LC-02':
                pax_on, pax_m, pay_m = False, 0.0, 0.0
                default_prop_off = True
            elif lc == 'LC-03':
                pax_on, pax_m, pay_m = False, 0.0, 0.0
                default_prop_off = False
            elif lc == 'LC-04':
                pax_on, pax_m, pay_m = True, 85.0, 0.0
                default_prop_off = False
            else:  # LC-MAX (1050.0 kg upper bound of RC01_F03_mass_cg_sensitivity.csv)
                pax_on, pax_m, pay_m = True, 85.0, 150.0
                default_prop_off = False

        if passenger_aboard is not None:
            pax_on = bool(passenger_aboard)
            if pax_on and passenger_mass_kg is None and pax_m <= 1e-6:
                pax_m = 85.0
        if passenger_mass_kg is not None:
            pax_m = max(0.0, float(passenger_mass_kg))
        if not pax_on:
            pax_m = 0.0
        if payload_mass_kg is not None:
            pay_m = max(0.0, float(payload_mass_kg))

        inst = normalize_propulsion_installation(propulsion_installation, load_case=lc, register_version=ver)
        if ver == LEGACY_REGISTER_VERSION and fuel_state is None and fuel_mass_kg is None:
            resolved_fuel_state: str | None = None
            resolved_fuel_mass = 0.0
        else:
            resolved_fuel_state, resolved_fuel_mass = resolve_fuel_state(fuel_state=fuel_state, fuel_mass_kg=fuel_mass_kg)

        if inst == 'energy_pack_alternate' and resolved_fuel_mass > 1e-6:
            raise ValueError(
                'F02 ENERGY_PACK_ALTERNATE (-1.02, 0.0, 0.69) and FUEL_CELL_PORT/STARBOARD '
                '(-1.05, +/-0.23, 0.55) are mutually exclusive; fuel_mass_kg must be 0.0 '
                'or select propulsion_installation="fuel_cell_paired"'
            )

        prop_off = default_prop_off if propulsion_off is None else bool(propulsion_off)

        return cls(
            load_case=lc,
            register_version=ver,
            passenger_aboard=pax_on,
            passenger_mass_kg=pax_m,
            passenger_x_offset_m=0.0,
            payload_mass_kg=pay_m,
            ballast_mass_kg=max(0.0, float(ballast_mass_kg)),
            ballast_x_m=float(np.clip(ballast_x_m, -1.5, 1.5)),
            ballast_y_m=float(np.clip(ballast_y_m, -0.5, 0.5)),
            waterproof=bool(waterproof),
            flood_water_kg=0.0,
            fuel_state=resolved_fuel_state,
            fuel_mass_kg=resolved_fuel_mass,
            propulsion_installation=inst,
            propulsion_off=prop_off,
            components=base_items,
        )

    def _propulsion_and_fuel_items(self, pack: MassComponent) -> list[MassComponent]:
        """Resolve mutually exclusive F02 propulsion-energy keepout & paired fuel items."""
        out: list[MassComponent] = []
        fuel_m = max(0.0, float(self.fuel_mass_kg))
        if self.propulsion_installation == 'baseline_pack':
            out.append(pack)
            if fuel_m > 1e-6:
                half_f = 0.5 * fuel_m
                f_inert = _box_inertia_diag(half_f, F02_KEEPOUT_ENVELOPES['FUEL_CELL_PORT']['bounds_m'])
                out.append(
                    MassComponent(
                        'fuel_cell_port',
                        f'Port paired fuel-cell fill ({self.fuel_state or "custom"})',
                        half_f,
                        F02_KEEPOUT_ENVELOPES['FUEL_CELL_PORT']['center_f03_m'],
                        f_inert,
                        status='provisional_unverified',
                        movable=True,
                        notes='Paired F02 FUEL_CELL_PORT fill conserving y=0; density/slosh/capacity unverified',
                    )
                )
                out.append(
                    MassComponent(
                        'fuel_cell_starboard',
                        f'Starboard paired fuel-cell fill ({self.fuel_state or "custom"})',
                        half_f,
                        F02_KEEPOUT_ENVELOPES['FUEL_CELL_STARBOARD']['center_f03_m'],
                        f_inert,
                        status='provisional_unverified',
                        movable=True,
                        notes='Paired F02 FUEL_CELL_STARBOARD fill conserving y=0; density/slosh/capacity unverified',
                    )
                )
        elif self.propulsion_installation == 'energy_pack_alternate':
            out.append(
                MassComponent(
                    'energy_pack_alternate',
                    'Alternate aft energy storage pack (F02 ENERGY_PACK_ALTERNATE keepout)',
                    pack.mass_kg,
                    F02_KEEPOUT_ENVELOPES['ENERGY_PACK_ALTERNATE']['center_f03_m'],
                    pack.local_inertia_diag_kg_m2,
                    status='provisional_unverified',
                    movable=True,
                    notes=(
                        'Relocates declared 170.0 kg energy_propulsion_pack to F02 ENERGY_PACK_ALTERNATE '
                        '(-1.02, 0.0, 0.69); mutually exclusive with FUEL_CELL_*; unverified'
                    ),
                )
            )
        else:  # fuel_cell_paired
            half_pack = 0.5 * pack.mass_kg
            half_fuel = 0.5 * fuel_m
            half_tot = half_pack + half_fuel
            f_inert = _box_inertia_diag(half_fuel, F02_KEEPOUT_ENVELOPES['FUEL_CELL_PORT']['bounds_m'])
            local_inert = (
                0.5 * pack.local_inertia_diag_kg_m2[0] + f_inert[0],
                0.5 * pack.local_inertia_diag_kg_m2[1] + f_inert[1],
                0.5 * pack.local_inertia_diag_kg_m2[2] + f_inert[2],
            )
            note = (
                f'Conserves declared {pack.mass_kg:.1f} kg energy_propulsion_pack symmetrically '
                f'({half_pack:.1f} kg/side) + {half_fuel:.2f} kg/side declared fuel ({self.fuel_state or "dry"}); '
                'F02 tank/density/slosh unverified'
            )
            out.append(
                MassComponent(
                    'fuel_cell_port',
                    'Port paired fuel-cell powerpack & fill (F02 FUEL_CELL_PORT keepout)',
                    half_tot,
                    F02_KEEPOUT_ENVELOPES['FUEL_CELL_PORT']['center_f03_m'],
                    local_inert,
                    status='provisional_unverified',
                    movable=True,
                    notes=note,
                )
            )
            out.append(
                MassComponent(
                    'fuel_cell_starboard',
                    'Starboard paired fuel-cell powerpack & fill (F02 FUEL_CELL_STARBOARD keepout)',
                    half_tot,
                    F02_KEEPOUT_ENVELOPES['FUEL_CELL_STARBOARD']['center_f03_m'],
                    local_inert,
                    status='provisional_unverified',
                    movable=True,
                    notes=note,
                )
            )
        return out

    def active_items(self) -> list[MassComponent]:
        items: list[MassComponent] = []
        base_components = self.components or _base_f03_components()
        pack_found = False
        for c in base_components:
            if c.component_id == 'energy_propulsion_pack':
                pack_found = True
                items.extend(self._propulsion_and_fuel_items(c))
            else:
                items.append(c)

        if not pack_found and self.propulsion_installation == 'baseline_pack' and self.fuel_mass_kg > 1e-6:
            half_f = 0.5 * self.fuel_mass_kg
            f_inert = _box_inertia_diag(half_f, F02_KEEPOUT_ENVELOPES['FUEL_CELL_PORT']['bounds_m'])
            for cid, keepout_key in (('fuel_cell_port', 'FUEL_CELL_PORT'), ('fuel_cell_starboard', 'FUEL_CELL_STARBOARD')):
                items.append(
                    MassComponent(
                        cid,
                        f'Paired fuel-cell fill ({self.fuel_state or "custom"})',
                        half_f,
                        F02_KEEPOUT_ENVELOPES[keepout_key]['center_f03_m'],
                        f_inert,
                        status='provisional_unverified',
                        movable=True,
                    )
                )

        if self.passenger_aboard and self.passenger_mass_kg > 1e-6:
            # v2 aligns strictly with F02 PILOT_SEAT_TRACK (1.30, 0.0, 0.80); v1 keeps historical z=0.82
            pax_z = 0.82 if self.register_version == LEGACY_REGISTER_VERSION else 0.80
            items.append(
                MassComponent(
                    'passenger_pilot',
                    'Pilot / Passenger on seat track (F02 envelope)',
                    self.passenger_mass_kg,
                    (1.30 + self.passenger_x_offset_m, 0.0, pax_z),
                    (6.5, 8.0, 5.0),
                    status='envelope_nominal',
                    movable=True,
                    notes='F02 seat track linear X +/-0.12 m',
                )
            )
        if self.payload_mass_kg > 1e-6:
            items.append(
                MassComponent(
                    'payload_bay',
                    'Payload / test instrumentation / water-ballast',
                    self.payload_mass_kg,
                    (0.35, 0.0, 0.55),
                    (5.0, 7.0, 6.0),
                    status='envelope_nominal',
                    movable=True,
                )
            )
        if abs(self.extra_mass_kg) > 1e-6:
            items.append(
                MassComponent(
                    'operator_mass_delta',
                    'Live operator test mass adjustment',
                    max(0.0, self.extra_mass_kg),
                    (0.45, 0.0, 0.59),
                    (2.0, 4.0, 4.0),
                    status='envelope_nominal',
                    movable=True,
                )
            )
        if self.ballast_mass_kg > 1e-6:
            m_b = float(self.ballast_mass_kg)
            items.append(
                MassComponent(
                    'trim_ballast',
                    'Movable hull bilge trim ballast pack',
                    m_b,
                    (self.ballast_x_m, self.ballast_y_m, 0.34),
                    (max(0.5, 0.04 * m_b), max(0.8, 0.06 * m_b), max(0.8, 0.06 * m_b)),
                    status='envelope_nominal',
                    movable=True,
                    notes='Operator-adjustable internal keel trim ballast',
                )
            )
        if self.flood_water_kg > 1e-6:
            m_f = float(self.flood_water_kg)
            items.append(
                MassComponent(
                    'ingressed_flood_water',
                    'Ingressed cockpit/bilge water mass (non-waterproof hull)',
                    m_f,
                    (0.58, 0.0, 0.28),
                    (max(1.0, 0.07 * m_f), max(2.0, 0.14 * m_f), max(2.0, 0.16 * m_f)),
                    status='envelope_nominal',
                    movable=True,
                    notes='Pooled bilge/cockpit ingress when hull seal is breached/open',
                )
            )
        return items

    def core_body_items(self) -> list[MassComponent]:
        """All items strictly rigidly attached to main airframe (excluding independent sponson bodies)."""
        return [c for c in self.active_items() if c.component_id not in ('sponson_port', 'sponson_stbd')]

    def aggregate(self, include_sponsons: bool = True) -> dict[str, Any]:
        """Compute total mass, CG (VTX & F03), and 3x3 inertia tensor in VTX frame (+Y port)."""
        items = self.active_items() if include_sponsons else self.core_body_items()
        total_mass = sum(max(c.mass_kg, 0.0) for c in items)
        if total_mass <= 1e-9:
            return {
                'register_version': self.register_version,
                'load_case': self.load_case,
                'description': describe_load_case(self.load_case, self.register_version),
                'total_mass_kg': 0.0,
                'cg_vtx_m': [0.0, 0.0, 0.0],
                'cg_f03_m': [0.0, 0.0, 0.0],
                'inertia_vtx_kg_m2': np.zeros((3, 3), dtype=np.float64).tolist(),
                'inertia_diag_vtx_kg_m2': [0.0, 0.0, 0.0],
                'fuel_state': self.fuel_state,
                'fuel_mass_kg': float(self.fuel_mass_kg),
                'propulsion_installation': self.propulsion_installation,
                'propulsion_off': bool(self.propulsion_off),
                'propulsion_stowed': bool(self.propulsion_off),
                'items': [],
            }

        cg_vtx = (
            sum(c.mass_kg * c.cg_vtx_m() for c in items) / total_mass
            + np.asarray(self.cg_shift_vtx_m, dtype=np.float64)
        )

        # Parallel-axis theorem in VTX coordinates (+X fwd, +Y port, +Z up)
        inertia_vtx = np.zeros((3, 3), dtype=np.float64)
        shift_vtx = np.asarray(self.cg_shift_vtx_m, dtype=np.float64)
        for c in items:
            m = c.mass_kg
            if m <= 0.0:
                continue
            r = (c.cg_vtx_m() + shift_vtx) - cg_vtx
            i_local = np.diag(c.local_inertia_diag_kg_m2)
            r2 = float(np.dot(r, r))
            inertia_vtx += i_local + m * (r2 * np.eye(3) - np.outer(r, r))

        cg_f03 = np.array([cg_vtx[0], -cg_vtx[1], cg_vtx[2]], dtype=np.float64)
        is_provisional = (
            self.register_version == DEFAULT_REGISTER_VERSION
            and (
                self.load_case in ('LC-03', 'LC-04')
                or self.fuel_mass_kg > 1e-6
                or self.propulsion_installation != 'baseline_pack'
            )
        )
        contract_status = 'provisional_unverified' if is_provisional else 'envelope_nominal'
        arch_spec = PROPULSION_INSTALLATION_SPECS[self.propulsion_installation]
        return {
            'register_version': self.register_version,
            'load_case': self.load_case,
            'description': describe_load_case(self.load_case, self.register_version),
            'status': contract_status,
            'total_mass_kg': float(total_mass),
            'cg_vtx_m': [float(v) for v in cg_vtx],
            'cg_f03_m': [float(v) for v in cg_f03],
            'inertia_vtx_kg_m2': inertia_vtx.tolist(),
            'inertia_diag_vtx_kg_m2': [float(inertia_vtx[0, 0]), float(inertia_vtx[1, 1]), float(inertia_vtx[2, 2])],
            'passenger_aboard': self.passenger_aboard,
            'passenger_mass_kg': float(self.passenger_mass_kg),
            'passenger_x_offset_m': float(self.passenger_x_offset_m),
            'payload_mass_kg': float(self.payload_mass_kg),
            'extra_mass_kg': float(self.extra_mass_kg),
            'ballast_mass_kg': float(self.ballast_mass_kg),
            'ballast_x_m': float(self.ballast_x_m),
            'ballast_y_m': float(self.ballast_y_m),
            'waterproof': bool(self.waterproof),
            'flood_water_kg': float(self.flood_water_kg),
            'fuel_state': self.fuel_state,
            'fuel_mass_kg': float(self.fuel_mass_kg),
            'propulsion_installation': self.propulsion_installation,
            'propulsion_off': bool(self.propulsion_off),
            'propulsion_stowed': bool(self.propulsion_off),
            'propulsion_architecture': {
                'installation': self.propulsion_installation,
                'subcase_id': arch_spec['subcase_id'],
                'keepout_ids': arch_spec['keepout_ids'],
                'status': 'provisional_unverified' if is_provisional else 'envelope_nominal',
            },
            'cg_shift_vtx_m': [float(v) for v in self.cg_shift_vtx_m],
            'items': [c.to_dict() for c in items],
        }

    def set_runtime_override(
        self,
        total_mass_kg: float | None = None,
        cg_shift_vtx_m: tuple[float, float, float] | list[float] | None = None,
        passenger_aboard: bool | None = None,
        passenger_mass_kg: float | None = None,
        payload_mass_kg: float | None = None,
        ballast_mass_kg: float | None = None,
        ballast_x_m: float | None = None,
        ballast_y_m: float | None = None,
        waterproof: bool | None = None,
        flood_water_kg: float | None = None,
        register_version: str | None = None,
        fuel_state: str | None = None,
        fuel_mass_kg: float | None = None,
        propulsion_installation: PropulsionInstallation | None = None,
        propulsion_off: bool | None = None,
    ) -> None:
        target_ver = (
            normalize_register_version(register_version)
            if register_version is not None
            else self.register_version
        )
        target_inst = (
            normalize_propulsion_installation(
                propulsion_installation, load_case=self.load_case, register_version=target_ver
            )
            if propulsion_installation is not None
            else self.propulsion_installation
        )
        if fuel_state is not None or fuel_mass_kg is not None:
            target_fuel_state, target_fuel_mass = resolve_fuel_state(
                fuel_state=fuel_state,
                fuel_mass_kg=fuel_mass_kg,
            )
        else:
            target_fuel_state, target_fuel_mass = self.fuel_state, self.fuel_mass_kg

        if target_inst == 'energy_pack_alternate' and target_fuel_mass > 1e-6:
            raise ValueError(
                'F02 ENERGY_PACK_ALTERNATE (-1.02, 0.0, 0.69) and FUEL_CELL_PORT/STARBOARD '
                '(-1.05, +/-0.23, 0.55) are mutually exclusive; fuel_mass_kg must be 0.0 '
                'or select propulsion_installation="fuel_cell_paired"'
            )

        shift_parsed: tuple[float, float, float] | None = None
        if cg_shift_vtx_m is not None:
            s = [float(x) for x in cg_shift_vtx_m]
            if len(s) != 3 or not all(math.isfinite(x) for x in s):
                raise ValueError(f'cg_shift_vtx_m must be 3 finite floats, got {cg_shift_vtx_m!r}')
            shift_parsed = (s[0], s[1], s[2])

        self.register_version = target_ver
        self.propulsion_installation = target_inst
        self.fuel_state = target_fuel_state
        self.fuel_mass_kg = target_fuel_mass

        if propulsion_off is not None:
            self.propulsion_off = bool(propulsion_off)
        if passenger_aboard is not None:
            self.passenger_aboard = bool(passenger_aboard)
            if self.passenger_aboard and passenger_mass_kg is None and self.passenger_mass_kg <= 1e-6:
                self.passenger_mass_kg = 85.0
            elif not self.passenger_aboard and passenger_mass_kg is None:
                self.passenger_mass_kg = 0.0
        if passenger_mass_kg is not None:
            self.passenger_mass_kg = max(0.0, float(passenger_mass_kg))
        if payload_mass_kg is not None:
            self.payload_mass_kg = max(0.0, float(payload_mass_kg))
        if ballast_mass_kg is not None:
            self.ballast_mass_kg = max(0.0, float(ballast_mass_kg))
        if ballast_x_m is not None:
            self.ballast_x_m = float(np.clip(float(ballast_x_m), -1.5, 1.5))
        if ballast_y_m is not None:
            self.ballast_y_m = float(np.clip(float(ballast_y_m), -0.5, 0.5))
        if waterproof is not None:
            self.waterproof = bool(waterproof)
        if flood_water_kg is not None:
            self.flood_water_kg = max(0.0, float(flood_water_kg))
        if shift_parsed is not None:
            self.cg_shift_vtx_m = shift_parsed
        if total_mass_kg is not None:
            self.extra_mass_kg = 0.0
            base_m = self.aggregate(include_sponsons=True)['total_mass_kg']
            # Adjust delta cleanly within physical envelope (>= core dry mass - 100 kg)
            self.extra_mass_kg = max(0.0, float(total_mass_kg) - base_m)


def compare_propulsion_installations(
    load_case: str = 'LC-04',
    passenger_aboard: bool = True,
    passenger_mass_kg: float = 85.0,
    payload_mass_kg: float = 0.0,
    sponson_z_m: float = 0.42,
    fuel_state: str | None = 'dry',
    fuel_mass_kg: float | None = None,
    include_sponsons: bool = True,
    register_version: str = DEFAULT_REGISTER_VERSION,
) -> dict[str, Any]:
    """Compare all three mutually exclusive F02 propulsion installations (LC-04).

    Compares ``baseline_pack`` (1.62, 0.0, 0.40), ``fuel_cell_paired`` (-1.05, +/-0.23, 0.55),
    and ``energy_pack_alternate`` (-1.02, 0.0, 0.69) using exact parallel-axis CG and
    3x3 inertia tensor shifts while conserving declared ``energy_propulsion_pack`` mass
    (170.0 kg) and declared ``fuel_mass_kg``. All unweighed F02 entries are tagged
    ``provisional_unverified``.
    """
    ver = normalize_register_version(register_version)
    lc = normalize_load_case(load_case, register_version=ver)
    resolved_fuel_state, resolved_fuel_mass = resolve_fuel_state(
        fuel_state=fuel_state,
        fuel_mass_kg=fuel_mass_kg,
    )

    installations: dict[str, dict[str, Any]] = {}
    for inst in PROPULSION_INSTALLATIONS:
        # Fuel fluid fill applies only to fuel_cell_paired; baseline_pack and
        # energy_pack_alternate represent battery/energy pack alternatives (0 kg fluid fuel).
        inst_fuel_state = resolved_fuel_state if inst == 'fuel_cell_paired' else 'dry'
        inst_fuel_mass = resolved_fuel_mass if inst == 'fuel_cell_paired' else 0.0

        mr = MassPropertiesRegister.for_load_case(
            load_case=lc,
            passenger_aboard=passenger_aboard,
            passenger_mass_kg=passenger_mass_kg,
            payload_mass_kg=payload_mass_kg,
            sponson_z_m=sponson_z_m,
            register_version=ver,
            fuel_state=inst_fuel_state,
            fuel_mass_kg=inst_fuel_mass,
            propulsion_installation=inst,
        )
        agg = mr.aggregate(include_sponsons=include_sponsons)
        iner_vtx = np.asarray(agg['inertia_vtx_kg_m2'], dtype=np.float64)
        iner_f03 = inertia_f03_to_vtx(iner_vtx)
        spec = PROPULSION_INSTALLATION_SPECS[inst]
        prop_items = [
            item
            for item in agg['items']
            if item['component_id'] in (
                'energy_propulsion_pack',
                'energy_pack_alternate',
                'fuel_cell_port',
                'fuel_cell_starboard',
                'ducted_fan_port',
                'ducted_fan_stbd',
                'tail_pylon_t_tail',
            )
        ]
        installations[inst] = {
            **spec,
            'total_mass_kg': agg['total_mass_kg'],
            'fuel_state': inst_fuel_state,
            'fuel_mass_kg': inst_fuel_mass,
            'cg_f03_m': agg['cg_f03_m'],
            'cg_vtx_m': agg['cg_vtx_m'],
            'inertia_vtx_kg_m2': agg['inertia_vtx_kg_m2'],
            'inertia_diag_vtx_kg_m2': agg['inertia_diag_vtx_kg_m2'],
            'inertia_f03_kg_m2': iner_f03.tolist(),
            'propulsion_items': prop_items,
            'status': 'provisional_unverified',
        }

    base = installations['baseline_pack']
    base_cg_f03 = np.asarray(base['cg_f03_m'], dtype=np.float64)
    base_cg_vtx = np.asarray(base['cg_vtx_m'], dtype=np.float64)
    base_i_vtx = np.asarray(base['inertia_vtx_kg_m2'], dtype=np.float64)

    deltas_vs_baseline: dict[str, dict[str, Any]] = {}
    for inst, entry in installations.items():
        cg_f03 = np.asarray(entry['cg_f03_m'], dtype=np.float64)
        cg_vtx = np.asarray(entry['cg_vtx_m'], dtype=np.float64)
        i_vtx = np.asarray(entry['inertia_vtx_kg_m2'], dtype=np.float64)
        di_vtx = i_vtx - base_i_vtx
        deltas_vs_baseline[inst] = {
            'delta_mass_kg': float(entry['total_mass_kg'] - base['total_mass_kg']),
            'delta_cg_f03_m': [float(v) for v in (cg_f03 - base_cg_f03)],
            'delta_cg_vtx_m': [float(v) for v in (cg_vtx - base_cg_vtx)],
            'delta_inertia_vtx_kg_m2': di_vtx.tolist(),
            'delta_inertia_diag_vtx_kg_m2': [float(di_vtx[0, 0]), float(di_vtx[1, 1]), float(di_vtx[2, 2])],
        }

    return {
        'register_version': ver,
        'load_case': lc,
        'status': 'provisional_unverified',
        'include_sponsons': bool(include_sponsons),
        'baseline_installation': 'baseline_pack',
        'notes': (
            'Mutually exclusive F02 propulsion keepouts; declared 170.0 kg energy_propulsion_pack conserved '
            'without inventing unweighed hardware masses. Fuel tank density/capacity and gearbox/cooling/mount '
            'details remain provisional_unverified per F02.'
        ),
        'installations': installations,
        'deltas_vs_baseline': deltas_vs_baseline,
    }
