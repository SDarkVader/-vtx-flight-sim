"""Phantom mass ledger: component records, kinematic tree, configuration mass properties.

Every component is a record (id, kind, source_status, mass, build-pose position, inertia about
its own COM in build-pose axes, attached body, limits, provenance, cad_object). The MuJoCo plant
is built from the same bodies so MuJoCo mass/CG/inertia equal the ledger (tested).
Run: python -m vtx.phantom.ledger  (writes the evidence JSON and the CG table).
"""
from __future__ import annotations
import json, math
from dataclasses import dataclass, field, asdict
import numpy as np
from .params import Params, ROOT
from .geometry import PODS, SIDE, FRONT, CAD_POD, CAD_LEG, WING_SIDES, WING_SIGN, CAD_SIDE, PINS, rot, box_inertia, cylinder_inertia

S = 'SYNTHETIC_UNVALIDATED'


@dataclass
class Body:
    name: str
    parent: str | None
    anchor: list
    joint: str | None = None
    axis: list = field(default_factory=lambda: [1, 0, 0])
    range: list | None = None
    cad: str | None = None


@dataclass
class Component:
    id: str
    kind: str
    body: str
    mass_kg: float
    position_m: list
    inertia_kg_m2: list
    source_status: str
    provenance: str
    cad_object: str | None = None
    limits: dict | None = None
    tags: list = field(default_factory=list)


def _c(id, kind, body, m, pos, I, label, src, cad=None, limits=None, tags=None):
    I = np.asarray(I, float)
    if I.shape == (3,):
        I = box_inertia(m, I)
    return Component(id, kind, body, float(m), [float(x) for x in pos], I.tolist(), label, src, cad, limits, tags or [])


class PhantomLedger:
    def __init__(self, params: Params, occupants: int | None = None):
        self.p = P = params
        self.occupants = int(occupants if occupants is not None else P['occupants.count'])
        g = P.geometry['objects']; H = P.handover
        hb = H['bodies_reference_pose']; hj = {j['name']: j for j in H['joints']}
        B = self.bodies = {}
        C = self.components = []

        def body(*a, **k):
            b = Body(*a, **k); B[b.name] = b; return b

        body('airframe', None, [0, 0, 0], cad='VTX_PHANTOM_A6_LOCKED_REFERENCE_BODY')
        hull = g['PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL']
        C.append(_c('hull_shell', 'structure', 'airframe', hull['area_m2'] * P['structure.hull_areal_density_kg_m2'], hull['area_centroid_m'], [2.4, 1.2, 0.5],
                    'DERIVED', f'measured area {hull["area_m2"]:.2f} m2 x hull areal density', 'PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL'))
        for cid, coll, dens, half, frac in [
                ('fenders_doors_panels', 'PHANTOM A6_02 SHAPED OVERLAPPING FENDER AND SIDE PANELS', 'panel', [2.2, 1.2, 0.3], 1.0),
                ('safety_tub', '02 INTERNAL BONDED CFRP SAFETY CELL', 'tub', [1.6, 0.7, 0.3], 0.5),
                ('nose_splitter', 'PHANTOM A6_03 V-SPLITTER CHEVRON AND LIGHTS', 'trim', [0.4, 0.8, 0.15], 1.0),
                ('canopy_glazing', 'PHANTOM A6_04 LOW ANGULAR CANOPY', 'glazing', [0.8, 0.6, 0.15], 1.0),
                ('tail_fins_fairings', 'PHANTOM A6_05 TWIN V TAIL AND REAR BOOSTER FAIRINGS', 'trim', [0.4, 0.6, 0.3], 1.0),
                ('rear_reaction_boxes', '07 REAR PROPULSION AND REACTION BULKHEAD', 'reaction_box', [0.4, 0.6, 0.2], 0.5)]:
            gr = P.geometry['collections'][coll]
            m = gr['area_m2'] * frac * P[f'structure.{dens}_areal_density_kg_m2']
            C.append(_c(cid, 'structure', 'airframe', m, gr['area_centroid_m'], half, 'DERIVED',
                        f'measured collection area {gr["area_m2"]:.2f} m2 x {frac} x {dens} areal density', coll))
        C.append(_c('console', 'interior', 'airframe', P['structure.console_mass_kg'], [0.48, 0, 0.57], [0.2, 0.4, 0.15], S, 'console', 'PHANTOM A7_10 DIRECT DRIVE CONTROL CONSOLE'))
        C.append(_c('harness', 'electrical', 'airframe', P['structure.harness_mass_kg'], P['structure.harness_position_m'], [1.8, 0.5, 0.2], S, 'harness'))
        fp = hb['chassis_A9_fixed_parts']
        C.append(_c('a9_cassette_fixed', 'structure', 'airframe', fp['mass_kg'], fp['com_world_m'], fp['inertia_about_com_world_axes_kg_m2'], 'DERIVED',
                    'a9_handover chassis_A9_fixed_parts', 'A9_01 TELESCOPIC WING CASSETTE'))
        for who, cushion in [('driver', 'SEAT_DRIVER_SEAT_CUSHION'), ('passenger', 'SEAT_PASSENGER_SEAT_CUSHION')]:
            cc = np.array(g[cushion]['area_centroid_m'])
            C.append(_c(f'seat_{who}', 'interior', 'airframe', P['structure.seat_mass_kg'], cc + [0, 0, 0.1], [0.25, 0.2, 0.3], S, 'seat', cushion))
            C.append(_c(f'occupant_{who}', 'occupant', 'airframe', P['occupants.mass_each_kg'], cc + np.array(P['occupants.seated_cg_offset_m']),
                        [0.2, 0.2, 0.35], S, 'occupant state mass (driver at -Y, physical right)', tags=['occupant']))
        C.append(_c('avionics_fcc', 'avionics', 'airframe', P['electrical.avionics_mass_kg'], P['electrical.avionics_position_m'], [0.2, 0.2, 0.1], S,
                    'FCC/IMU/air data', limits=dict(power_w=P['electrical.avionics_power_w'])))
        C.append(_c('hv_junction', 'electrical', 'airframe', P['electrical.hv_junction_mass_kg'], P['electrical.hv_junction_position_m'], [0.2, 0.2, 0.1], S,
                    'HV bus/contactors', limits=dict(voltage_v=P['electrical.bus_voltage_v'])))
        C.append(_c('radiator', 'cooling', 'airframe', P['thermal.radiator_mass_kg'], P['thermal.radiator_position_m'], [0.14, 0.41, 0.1], S,
                    'radiator core + coolant', 'THERMAL_FRONT_CENTRAL_DUAL_RADIATOR_CORE'))
        fpos = np.array(P['thermal.cooling_fan_position_m'])
        for s, nm in ((1, 'left'), (-1, 'right')):
            C.append(_c(f'cooling_fan_{nm}', 'cooling', 'airframe', P['thermal.cooling_fan_mass_kg'], fpos * [1, s, 1], [0.05, 0.12, 0.12], S,
                        'powered cooling fan', limits=dict(power_w=P['thermal.cooling_fan_power_w'] / 2)))
        for i in range(int(P['generators.count'])):
            C.append(_c(f'turbogenerator_{i + 1}', 'powertrain', 'airframe', P['generators.mass_each_kg'], P['generators.positions_m'][i], P['generators.box_half_m'],
                        P.label('generators.mass_each_kg'), 'turbogenerator incl. rectifier',
                        limits=dict(power_w=P['generators.power_each_w'], takeoff_power_w=P['generators.takeoff_power_each_w'])))
        bm = P['buffer.energy_j'] / 3600 / P['buffer.specific_energy_wh_kg']
        body('buffer', 'airframe', P['buffer.position_m'])
        C.append(_c('buffer_battery', 'powertrain', 'buffer', bm, P['buffer.position_m'], P['buffer.box_half_m'], 'DERIVED', 'energy / pack specific energy',
                    limits=dict(energy_j=P['buffer.energy_j'], p_cont_w=bm * P['buffer.specific_power_cont_w_kg'], p_peak_w=bm * P['buffer.specific_power_peak_w_kg'])))
        for i, side in enumerate(('left', 'right')):
            pos = P['fuel.positions_m'][i]
            C.append(_c(f'fuel_tank_{side}', 'fuel_system', 'airframe', P['fuel.tank_mass_kg'], pos, P['fuel.box_half_m'], S, 'cell structure'))
            body(f'fuel_{side}', 'airframe', pos)
            C.append(_c(f'fuel_{side}', 'fuel', f'fuel_{side}', P['fuel.tank_capacity_kg'], pos, P['fuel.box_half_m'], S, 'Jet A-1 state mass (full)', tags=['fuel']))
        pp = P.tree['pods']; R = P['pods.tyre_radius_m']; hw = P['pods.tyre_half_width_m']
        for k in PODS:
            s = SIDE[k]; x = P['pods.hinge_x_front_m'] if FRONT[k] else P['pods.hinge_x_rear_m']
            anc = [x, s * P['pods.hinge_y_m'], P['pods.hinge_z_m']]
            C.append(_c(f'pod_{k}_pylon', 'pod', 'airframe', P['structure.pod_pylon_mass_kg'], [x, s * (P['pods.hinge_y_m'] - 0.15), anc[2]], [0.1, 0.08, 0.08], S,
                        'fixed bracket, pin, pylon, tilt EMA stator', CAD_POD[k]))
            body(f'pod_{k}', 'airframe', anc, 'hinge', [1, 0, 0], sorted([0.0, s * math.pi / 2]), CAD_POD[k])
            for cid, mkey, half in [('structure', 'pod_structure_mass_kg', [R * 0.7, hw * 2, R * 0.7]), ('fan_motor_inverter', 'motor_inverter_mass_kg', [0.12, 0.08, 0.12]),
                                    ('hub_motor_stator', 'hub_motor_stator_mass_kg', [0.1, 0.04, 0.1]), ('brake', 'brake_mass_kg', [0.1, 0.03, 0.1])]:
                lim = dict(p_cont_w=P['pods.motor_power_cont_w'], p_peak_w=P['pods.motor_power_peak_w'], torque_nm=P['pods.motor_torque_peak_nm']) if cid == 'fan_motor_inverter' else None
                C.append(_c(f'pod_{k}_{cid}', 'pod', f'pod_{k}', pp[mkey]['v'], anc, half, pp[mkey]['l'], pp[mkey]['s'], limits=lim))
            ax = [0, s, 0]
            body(f'pod_{k}_fan', f'pod_{k}', anc, 'hinge', ax, None)
            I = cylinder_inertia(P['pods.rotor_mass_kg'], P['pods.fan_r_tip_m'] * 0.9, 0.03, ax)
            I *= P['pods.rotor_inertia_kg_m2'] / I[1][1]
            C.append(_c(f'pod_{k}_fan_rotor', 'rotor', f'pod_{k}_fan', P['pods.rotor_mass_kg'], anc, I, S, 'fan rotor; axial inertia = pods.rotor_inertia_kg_m2'))
            body(f'pod_{k}_wheel', f'pod_{k}', anc, 'hinge', ax, None)
            mw = P['pods.wheel_mass_kg'] + P['pods.hub_motor_rotor_mass_kg']
            C.append(_c(f'pod_{k}_wheel_tyre', 'wheel', f'pod_{k}_wheel', mw, anc, 0.8 * cylinder_inertia(mw, R, hw, ax), S, 'rim + tyre + hub-motor rotor'))
        for k in PODS:
            s = SIDE[k]; a0 = hj[CAD_LEG[k]]['anchor_world_m']
            anc = [a0[0], s * abs(a0[1]), a0[2]]
            C.append(_c(f'leg_{k}_cartridge', 'leg', 'airframe', P['structure.leg_fixed_mass_kg'], [anc[0], anc[1], anc[2] + 0.25], [0.05, 0.05, 0.2], S, 'cartridge + EMA', CAD_LEG[k]))
            body(f'leg_{k}', 'airframe', anc, 'slide', [0, 0, 1], [-P['contact.leg_extension_m'], 0.0], CAD_LEG[k])
            C.append(_c(f'leg_{k}_slider', 'leg', f'leg_{k}', P['structure.leg_moving_mass_kg'], [anc[0], anc[1], anc[2] + 0.1], [0.04, 0.04, 0.2], S, 'main slider'))
            body(f'leg_{k}_oleo', f'leg_{k}', anc, 'slide', [0, 0, 1], [0.0, P['contact.oleo_stroke_m']])
            fz = P['contact.foot_bottom_retracted_z_m'] + P['contact.foot_radius_m']
            C.append(_c(f'leg_{k}_oleo_foot', 'leg', f'leg_{k}_oleo', P['structure.oleo_moving_mass_kg'], [anc[0], anc[1], fz + 0.05], [0.06, 0.06, 0.08], S, 'oleo piston + foot'))
        for side in WING_SIDES:
            cs = CAD_SIDE[side]

            def addbody(jn, parent, bname, jtype, rng):
                j = hj[jn]; hbj = hb[jn]
                body(bname, parent, j['anchor_world_m'], jtype, j['axis_world'], rng, jn)
                C.append(_c(bname, 'a9_cassette', bname, hbj['mass_kg'], hbj['com_world_m'], hbj['inertia_about_com_world_axes_kg_m2'], 'DERIVED', f'a9_handover {jn}', jn))
            addbody(f'A9_JOINT_WING_{cs}_SLIDE', 'airframe', f'wing_{side}', 'slide', [-1.37, 0.0])
            for pin in PINS:
                addbody(f'A9_JOINT_WING_{cs}_LOCK_{pin}', f'wing_{side}' if pin.startswith('FRONT') else 'airframe', f'pin_{side}_{pin.lower()}', 'slide', [-0.07, 0.0])
            addbody(f'A9_JOINT_FLAP_{cs}', f'wing_{side}', f'flap_{side}', 'hinge', [math.radians(-5), math.radians(35)])
            addbody(f'A9_JOINT_AILERON_{cs}', f'wing_{side}', f'aileron_{side}', 'hinge', [math.radians(-20), math.radians(20)])
            addbody(f'A9_JOINT_CANARD_{cs}_FOLD', 'airframe', f'canard_{side}_fold', 'hinge', [math.radians(x) for x in hj[f'A9_JOINT_CANARD_{cs}_FOLD']['range_deg']])
            addbody(f'A9_JOINT_CANARD_{cs}_PITCH', f'canard_{side}_fold', f'canard_{side}', 'hinge', [math.radians(-20), math.radians(25)])
            addbody(f'A9_JOINT_HATCH_{cs}', 'airframe', f'hatch_{side}', 'hinge', [0.0, math.pi])
        bp = np.array(P['boosters.position_m'])
        for side in WING_SIDES:
            pos = bp * [1, WING_SIGN[side], 1]
            C.append(_c(f'booster_{side}_housing', 'booster', 'airframe', P['boosters.housing_mass_kg'], pos + [0.15, 0, 0], [0.2, 0.15, 0.15], S,
                        'EDF motor, inverter, duct', f'POWER_{CAD_SIDE[side]}_REAR_THRUST_NOZZLE', limits=dict(power_w=P['boosters.shaft_power_max_w'])))
            body(f'booster_{side}_rotor', 'airframe', pos, 'hinge', [1, 0, 0], None)
            Ir = P['boosters.rotor_inertia_kg_m2']
            C.append(_c(f'booster_{side}_rotor', 'rotor', f'booster_{side}_rotor', P['boosters.rotor_mass_kg'], pos, np.diag([Ir, Ir / 2, Ir / 2]), S, 'EDF rotor'))
        self.validate()

    def validate(self):
        ids = set()
        for c in self.components:
            I = np.array(c.inertia_kg_m2)
            assert c.id not in ids, c.id
            ids.add(c.id)
            assert c.mass_kg > 0 and math.isfinite(c.mass_kg), c.id
            assert np.all(np.isfinite(c.position_m)), c.id
            assert np.allclose(I, I.T, atol=1e-9) and np.linalg.eigvalsh(I).min() > -1e-9, c.id
            assert c.body in self.bodies, c.id

    def included(self, c, occupants=None):
        occ = self.occupants if occupants is None else occupants
        return not (c.id == 'occupant_passenger' and occ < 2)

    def body_poses(self, q: dict):
        poses = {}
        for name, b in self.bodies.items():
            if b.parent is None:
                poses[name] = (np.eye(3), np.array(b.anchor, float)); continue
            Rp, pp = poses[b.parent]
            p = pp + Rp @ (np.array(b.anchor) - self.bodies[b.parent].anchor)
            R = Rp; v = q.get(name, 0.0)
            if b.joint == 'hinge':
                R = Rp @ rot(b.axis, v)
            elif b.joint == 'slide':
                p = p + Rp @ (np.array(b.axis) / np.linalg.norm(b.axis) * v)
            poses[name] = (R, p)
        return poses

    def configuration(self, pods='vtol', legs='extended', wings='stowed', canards='folded'):
        q = {}
        for k in PODS:
            q[f'pod_{k}'] = SIDE[k] * math.pi / 2 if pods == 'vtol' else 0.0
            q[f'leg_{k}'] = -self.p['contact.leg_extension_m'] if legs == 'extended' else 0.0
        for side in WING_SIDES:
            q[f'wing_{side}'] = -1.37 if wings == 'stowed' else 0.0
            if wings == 'stowed':
                for pin in PINS:
                    q[f'pin_{side}_{pin.lower()}'] = -0.07
            q[f'hatch_{side}'] = math.pi if wings == 'stowed' else 0.0
            q[f'canard_{side}_fold'] = WING_SIGN[side] * math.pi / 2 if canards == 'folded' else 0.0
        return q

    def mass_properties(self, q=None, fuel_kg=None, occupants=None):
        q = self.configuration() if q is None else q
        poses = self.body_poses(q)
        cap = self.p['fuel.tank_capacity_kg']
        if fuel_kg is None:
            fuel = [cap, cap]
        elif np.ndim(fuel_kg):
            fuel = [float(x) for x in fuel_kg]
        else:
            fuel = [min(float(fuel_kg) / 2, cap)] * 2
        M = 0.0; mr = np.zeros(3); items = []
        for c in self.components:
            if not self.included(c, occupants):
                continue
            m = c.mass_kg; I = np.array(c.inertia_kg_m2)
            if 'fuel' in c.tags:
                f = fuel[0 if c.id.endswith('left') else 1]; I = I * (f / m); m = f
            if m <= 0:
                continue
            R, p = poses[c.body]
            r = p + R @ (np.array(c.position_m) - self.bodies[c.body].anchor)
            items.append((m, r, R @ I @ R.T)); M += m; mr += m * r
        cg = mr / M; J = np.zeros((3, 3))
        for m, r, I in items:
            d = r - cg; J += I + m * (d @ d * np.eye(3) - np.outer(d, d))
        return dict(mass_kg=M, cg_m=cg.tolist(), inertia_about_cg_kg_m2=J.tolist())

    def body_inertials(self, fuel=None):
        """Per MuJoCo body: (mass, COM in body frame, inertia about COM) at the build pose."""
        out = {}
        for name, b in self.bodies.items():
            cs = []
            for c in self.components:
                if c.body != name or not self.included(c):
                    continue
                m, I = c.mass_kg, np.array(c.inertia_kg_m2)
                if 'fuel' in c.tags and fuel is not None:
                    f = max(fuel[0 if c.id.endswith('left') else 1], 1e-6); I = I * f / m; m = f
                cs.append((m, np.array(c.position_m), I))
            M = sum(m for m, _, _ in cs)
            if M <= 0:
                out[name] = (1e-6, np.zeros(3), np.eye(3) * 1e-10); continue
            com = sum(m * r for m, r, _ in cs) / M
            J = np.zeros((3, 3))
            for m, r, I in cs:
                d = r - com; J += I + m * (d @ d * np.eye(3) - np.outer(d, d))
            out[name] = (M, com - np.array(b.anchor), J)
        return out

    def records(self):
        return [asdict(c) for c in self.components]


CONFIG_ROWS = [
    ('base: VTOL, legs ext., wings stowed, canards folded, fuel full, 2 occ.', dict(), None, None),
    ('road: pods 0, legs retracted', dict(pods='road', legs='retracted'), None, None),
    ('wings deployed', dict(wings='deployed'), None, None),
    ('canards deployed', dict(canards='deployed'), None, None),
    ('wings + canards deployed', dict(wings='deployed', canards='deployed'), None, None),
    ('fuel reserve', dict(), 'reserve', None),
    ('fuel empty', dict(), 0.0, None),
    ('1 occupant (driver)', dict(), None, 1),
    ('1 occupant, fuel reserve', dict(), 'reserve', 1),
]


def config_table(ledger: PhantomLedger):
    rows = []
    for name, cfg, fuel, occ in CONFIG_ROWS:
        f = ledger.p['fuel.reserve_kg'] if fuel == 'reserve' else fuel
        rows.append(dict(configuration=name, **ledger.mass_properties(ledger.configuration(**cfg), fuel_kg=f, occupants=occ)))
    for st, spec in ledger.p.tree.get('load_states', {}).items():
        if spec.get('fuel_kg') is None:
            continue
        rows.append(dict(configuration=f'load state {st} ({spec["occupants"]} occ., {spec["fuel_kg"]:.0f} kg fuel requested)',
                         **ledger.mass_properties(ledger.configuration(), fuel_kg=spec['fuel_kg'], occupants=spec['occupants'])))
    return rows


def pod_shares(p, cg_x):
    xf = p['pods.hinge_x_front_m']; xr = p['pods.hinge_x_rear_m']
    f = (cg_x - xr) / (xf - xr)
    return f / 2, (1 - f) / 2


def write_outputs():
    out = {}
    md = ['# Phantom CG ledger from the simulator build', '',
          'Generated by `python -m vtx.phantom.ledger` from `inputs/phantom_parameters_v1.json`; every component record is in `evidence/phantom/phantom_mass_ledger.json`.',
          'Frame: CAD = MuJoCo body frame, X forward, Y = physical LEFT, Z up (road tyre bottoms at z 0.06). Pod share = static share of weight per pod from CG between front and rear hinge lines.', '']
    for v in ('phantom', 'phantom-fx'):
        P = Params(v); L = PhantomLedger(P)
        rows = config_table(L)
        groups = {}
        for c in L.components:
            groups[c.kind] = groups.get(c.kind, 0.0) + c.mass_kg
        out[v] = dict(variant=v, config_sha256=P.config_sha256, notional_mass_kg=1300.0, components=L.records(),
                      group_totals_kg=groups, configurations=rows, design_proposals=P.variant_info.get('design_proposals'))
        md += [f'## Variant `{v}`', '', P.variant_info['description'], '',
               f'Built-up mass (base configuration) **{rows[0]["mass_kg"]:.0f} kg** vs notional 1,300 kg: **{rows[0]["mass_kg"] - 1300:+.0f} kg**.', '',
               '| Configuration | Mass kg | CG x | CG y | CG z | Ixx | Iyy | Izz | front / rear pod share (each) |', '|---|---|---|---|---|---|---|---|---|']
        for r in rows:
            I = r['inertia_about_cg_kg_m2']; f, b = pod_shares(P, r['cg_m'][0])
            md.append(f'| {r["configuration"]} | {r["mass_kg"]:.1f} | {r["cg_m"][0]:+.3f} | {r["cg_m"][1]:+.3f} | {r["cg_m"][2]:.3f} | {I[0][0]:.0f} | {I[1][1]:.0f} | {I[2][2]:.0f} | {f:.3f} / {b:.3f} |')
        md += ['', 'Group totals (kg): ' + ', '.join(f'{k} {m:.1f}' for k, m in sorted(groups.items(), key=lambda t: -t[1])), '']
    md += ['Buffer battery and fuel are separate MuJoCo bodies (future CG-trim sled). Fuel mass/CG/inertia update live during burn. A8 pod/leg CAD placeholder masses are not used; component build-ups replace them. Masses are SYNTHETIC_UNVALIDATED or DERIVED from MEASURED-K areas.', '']
    (ROOT / 'evidence/phantom/phantom_mass_ledger.json').write_text(json.dumps(out, indent=1))
    (ROOT / 'research_notes/Phantom CG compensation and test flights/cg_ledger_from_build.md').write_text('\n'.join(md), encoding='utf-8')
    return out


if __name__ == '__main__':
    for v, d in write_outputs().items():
        r = d['configurations'][0]
        print(v, round(r['mass_kg'], 1), [round(x, 3) for x in r['cg_m']])
