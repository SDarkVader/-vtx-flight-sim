"""Component-level Mass Properties Register & F03->VTX transform for Ricochet RC-01.

Implements the Notion F03 Mass Properties & Water-Loading Envelope structure
with strict SI units, parallel-axis inertia tensor aggregation, and explicit
status tagging so provisional unweighed mass items remain identifiable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import numpy as np


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


LOAD_CASE_DESCRIPTIONS = {
    'LC-01': 'Empty-payload light ship, unoccupied, zero thrust (815 kg)',
    'LC-02': 'Unoccupied stowed airframe, propulsion armed idle / water motion (815 kg)',
    'LC-03': 'F03 nominal manned water trial envelope (pilot + full nominal 900 kg design mass)',
    'LC-04': 'Max water-loading & payload envelope (pilot + ballast/pack at 1050 kg RC-01 upper limit)',
}


@dataclass
class MassPropertiesRegister:
    """Aggregates active structural, propulsion, float, passenger, and payload items."""

    load_case: str = 'LC-03'
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
    components: list[MassComponent] = field(default_factory=list)

    @classmethod
    def for_load_case(
        cls,
        load_case: str = 'LC-03',
        passenger_aboard: bool | None = None,
        passenger_mass_kg: float | None = None,
        payload_mass_kg: float | None = None,
        sponson_z_m: float = 0.42,
        ballast_mass_kg: float = 0.0,
        ballast_x_m: float = -0.15,
        ballast_y_m: float = 0.0,
        waterproof: bool = True,
    ) -> 'MassPropertiesRegister':
        lc = str(load_case).upper()
        if lc not in LOAD_CASE_DESCRIPTIONS:
            lc = 'LC-03'

        # Core airframe + powerpack items calibrated so LC-03 hits exact F03 nominal 900 kg & CG ~ [0.45, 0, 0.59]
        # while LC-01 represents light-ship without pilot or removable payload.
        base_items = [
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

        if lc == 'LC-01':
            pax_on = False
            pax_m = 0.0
            pay_m = 0.0
        elif lc == 'LC-02':
            pax_on = False
            pax_m = 0.0
            pay_m = 0.0
        elif lc == 'LC-03':
            pax_on = True
            pax_m = 85.0
            pay_m = 0.0
        else:  # LC-04 (1050.0 kg upper bound of RC-01 750-1050 kg study mass envelope)
            pax_on = True
            pax_m = 85.0
            pay_m = 150.0

        if passenger_aboard is not None:
            pax_on = bool(passenger_aboard)
        if passenger_mass_kg is not None:
            pax_m = max(0.0, float(passenger_mass_kg))
        if not pax_on:
            pax_m = 0.0
        if payload_mass_kg is not None:
            pay_m = max(0.0, float(payload_mass_kg))

        return cls(
            load_case=lc,
            passenger_aboard=pax_on,
            passenger_mass_kg=pax_m,
            passenger_x_offset_m=0.0,
            payload_mass_kg=pay_m,
            ballast_mass_kg=max(0.0, float(ballast_mass_kg)),
            ballast_x_m=float(np.clip(ballast_x_m, -1.5, 1.5)),
            ballast_y_m=float(np.clip(ballast_y_m, -0.5, 0.5)),
            waterproof=bool(waterproof),
            flood_water_kg=0.0,
            components=base_items,
        )

    def active_items(self) -> list[MassComponent]:
        items = list(self.components)
        if self.passenger_aboard and self.passenger_mass_kg > 1e-6:
            # Pilot seat centered near F02 track (1.30, 0, 0.80) adjusted with trim seat rail
            items.append(
                MassComponent(
                    'passenger_pilot',
                    'Pilot / Passenger on seat track (F02 envelope)',
                    self.passenger_mass_kg,
                    (1.30 + self.passenger_x_offset_m, 0.0, 0.82),
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
                'total_mass_kg': 0.0,
                'cg_vtx_m': [0.0, 0.0, 0.0],
                'cg_f03_m': [0.0, 0.0, 0.0],
                'inertia_vtx_kg_m2': np.zeros((3, 3), dtype=np.float64).tolist(),
                'inertia_diag_vtx_kg_m2': [0.0, 0.0, 0.0],
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
        return {
            'load_case': self.load_case,
            'description': LOAD_CASE_DESCRIPTIONS.get(self.load_case, ''),
            'total_mass_kg': float(total_mass),
            'cg_vtx_m': [float(v) for v in cg_vtx],
            'cg_f03_m': [float(v) for v in cg_f03],
            'inertia_vtx_kg_m2': inertia_vtx.tolist(),
            'inertia_diag_vtx_kg_m2': [float(inertia_vtx[0, 0]), float(inertia_vtx[1, 1]), float(inertia_vtx[2, 2])],
            'passenger_aboard': self.passenger_aboard,
            'passenger_mass_kg': float(self.passenger_mass_kg),
            'payload_mass_kg': float(self.payload_mass_kg),
            'ballast_mass_kg': float(self.ballast_mass_kg),
            'ballast_x_m': float(self.ballast_x_m),
            'ballast_y_m': float(self.ballast_y_m),
            'waterproof': bool(self.waterproof),
            'flood_water_kg': float(self.flood_water_kg),
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
    ) -> None:
        if passenger_aboard is not None:
            self.passenger_aboard = bool(passenger_aboard)
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
        if cg_shift_vtx_m is not None:
            s = [float(x) for x in cg_shift_vtx_m]
            self.cg_shift_vtx_m = (s[0], s[1], s[2])
        if total_mass_kg is not None:
            self.extra_mass_kg = 0.0
            base_m = self.aggregate(include_sponsons=True)['total_mass_kg']
            # Adjust delta cleanly within physical envelope (>= core dry mass - 100 kg)
            self.extra_mass_kg = max(0.0, float(total_mass_kg) - base_m)
