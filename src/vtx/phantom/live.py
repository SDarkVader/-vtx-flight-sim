"""Phantom branch of the live Laboratory (kept out of live_server.py so legacy paths stay untouched).

Evidence per run folder (in addition to the legacy metadata.json / model.xml / events.jsonl /
summary.json / pilot memory copies): phantom_parameters.json (resolved parameter snapshot),
phantom_ledger.json, phantom_steps.csv.gz (100 Hz FBW internals, effectors, rigid body, power,
aero; the per-step channel list of flight_test_methods.md s3 where feasible) and, on a crash or
lease abort, crash_ring.npz (20 s pre-event ring buffer of truth channels at 400 Hz).
"""
from __future__ import annotations
import gzip, json, math, time
from datetime import datetime, timezone
import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .params import VARIANTS, Params
from .experiment_config import build_overrides
from .plant import PhantomAircraft
from .ledger import config_table

LEASE_S = 5.0
CG_GATE_SETTLE_S = 1.0          # the aircraft spawns ~0.06 m above its compressed gear (D-3, D-10)
CG_GATE_MAX_SPEED_M_S = 0.05
LANDED_GEAR_LOAD_FRACTION = 0.8  # weight on the gear required to call a landing (D-8)


class PhantomOptions(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    occupants: Literal[1, 2] | None = None
    load_state: Literal['nominal', 'FX-A', 'FX-C'] | None = None
    fuel_kg: float | None = Field(default=None, ge=0, le=200)
    start_configuration: Literal['vtol', 'road'] = 'vtol'
    p6_enabled: bool | None = None  # explicit historical A10-A choice; None keeps the live default
    experimental_overrides: dict[str, object] | None = None
    buffer_soc: float | None = Field(default=None, ge=0.1, le=1)
    engines_running: bool = True
    wind_world_m_s: list[float] | None = None
    policy_version: str | None = Field(default=None, max_length=200)
    card_id: str | None = Field(default=None, max_length=200)
    attempt: int | None = Field(default=None, ge=0, le=10000)


def is_phantom_variant(v):
    return v in VARIANTS


def make_aircraft(world, request, *, enable_a10_surfaces=True):
    o = request.phantom or PhantomOptions()
    # Mission.fuel_kg defaults to the four-fan 10 kg; it is Phantom fuel only when the operator set it
    # explicitly (flight campaign D-2). Otherwise: load-state fuel, else full tanks.
    explicit = 'fuel_kg' in request.model_fields_set
    fuel = o.fuel_kg if o.fuel_kg is not None else (None if o.load_state in ('FX-A', 'FX-C') or not explicit else request.fuel_kg)
    # Do not alter a variant that already owns P6. Explicit historical P6-off is
    # supported only for a variant whose own parameter tree leaves it disabled.
    base_p6 = Params(request.airframe_variant)['proposals.p6_drs_stabilator'] >= 0.5
    if o.p6_enabled is False and base_p6:
        raise ValueError('This aircraft variant includes P6; select an A10-A variant for a P6-off run')
    if o.p6_enabled is True and request.airframe_variant.endswith('-a9'):
        raise ValueError('P6 is not offered for the A9 variant')
    force_p6 = (enable_a10_surfaces and o.p6_enabled is not False
                and not request.airframe_variant.endswith('-a9') and not base_p6)
    p6_override = {'proposals': {'p6_drs_stabilator': {'v': 1.0}}} if force_p6 else None
    overrides = build_overrides(request.airframe_variant, p6_override, o.experimental_overrides)
    aircraft = PhantomAircraft(world, request.airframe_variant, fuel_kg=fuel, occupants=o.occupants, start_configuration=o.start_configuration,
                           engines_running=o.engines_running, buffer_soc=o.buffer_soc, wind=o.wind_world_m_s,
                           load_state=None if o.load_state == 'nominal' else o.load_state,
                           overrides=overrides)
    if enable_a10_surfaces and o.start_configuration != 'road' and not request.airframe_variant.endswith('-a9'):
        aircraft.set_command({'canard_fold': 'deployed'})
    return aircraft


def after_start(lab, request):
    p = lab.aircraft
    (lab.log_path / 'phantom_parameters.json').write_text(json.dumps(p.P.snapshot(), indent=1))
    led = dict(components=p.L.records(), configurations=config_table(p.L),
               live_mass_kg=float(sum(p.model.body_mass)), actual_start_mass_properties=p.mass_properties())
    (lab.log_path / 'phantom_ledger.json').write_text(json.dumps(led, indent=1))
    p.step_log = gzip.open(lab.log_path / 'phantom_steps.csv.gz', 'wt')
    lab.phantom_cg_gate = None
    lab.phantom_wall = dict(started=time.monotonic())
    lab.log('phantom_run_keys', dict(variant=p.variant, config_sha256=p.P.config_sha256, parameter_file_sha256=p.P.file_sha256,
                                     design_proposals=p.P.variant_info.get('design_proposals'), time_scale=lab.time_scale,
                                     fbw_mode=p.fcc.cmd['stability_mode'], fbw_gains={k: v['v'] for k, v in p.P.tree['fbw'].items()},
                                     load_state=p.load_state, occupants=p.L.occupants, fuel_kg=p.fuel.tolist(),
                                     options=(request.phantom.model_dump() if request.phantom else None),
                                     cg_gate=dict(status='pending', evaluate_after_s=CG_GATE_SETTLE_S,
                                                  note='evaluated once settled on the gear, logged as cg_gate'),
                                     source_status_map={k: v['l'] for k, v in _flat(p.P.tree).items()}))


def _flat(t, pre=''):
    out = {}
    for k, v in t.items():
        if isinstance(v, dict) and 'v' in v and 'l' in v:
            out[pre + k] = v
        elif isinstance(v, dict):
            out.update(_flat(v, pre + k + '.'))
    return out


def leg_load_cg_gate(p):
    """Pre-takeoff go/no-go: CG x estimated from the four oleo strokes (leg load cells)."""
    k = p.P['contact.oleo_stiffness_n_m']; pre = p.P['contact.oleo_preload_n']
    loads = {}; xs = {}
    for name in ('FL', 'FR', 'RL', 'RR'):
        q = p.joint(f'leg_{name}_oleo')[0]
        loads[name] = max(0.0, pre + k * q) if q > 0 else 0.0
        xs[name] = p.L.bodies[f'leg_{name}'].anchor[0]
    tot = sum(loads.values())
    if tot <= 0:
        return dict(status='no_weight_on_legs')
    cg = sum(loads[n] * xs[n] for n in loads) / tot
    xf, xr = p.P['pods.hinge_x_front_m'], p.P['pods.hinge_x_rear_m']
    off = cg - (xf + xr) / 2
    gate = p.P['fbw.leg_loadcell_cg_gate_m']
    return dict(status='GO' if abs(off) <= gate else 'NO_GO', cg_x_estimate_m=cg, pod_centroid_offset_m=off, gate_m=gate, leg_loads_n=loads)


def maybe_evaluate_cg_gate(lab):
    """Run the leg load-cell CG gate once, after the spawn drop has settled and before lift-off."""
    if getattr(lab, 'phantom_cg_gate', None) is not None:
        return lab.phantom_cg_gate
    p = lab.aircraft
    if lab.left_ground or p.airborne:
        lab.phantom_cg_gate = dict(status='not_evaluated_before_liftoff', t_s=float(p.data.time))
    elif p.data.time >= CG_GATE_SETTLE_S and float(np.linalg.norm(p.data.qvel[:3])) < CG_GATE_MAX_SPEED_M_S:
        lab.phantom_cg_gate = dict(leg_load_cg_gate(p), t_s=float(p.data.time))
    else:
        return None
    lab.log('cg_gate', lab.phantom_cg_gate)
    return lab.phantom_cg_gate


def gear_weight_fraction(p):
    """Share of the weight NOT carried by the lift fans: 1 - (vertical fan thrust / weight).

    Uses the modelled fan thrust (smooth) rather than single-step contact forces, which scatter by
    +-20 % between solver steps. Boosters are excluded: they thrust along the body x axis."""
    from .geometry import PODS
    w = float(sum(p.model.body_mass)) * p.P['atmosphere.gravity_m_s2']
    lift = sum(float(st.get('thrust_n', 0.0)) * abs(float(p.pod_axis(k)[2])) for k, st in zip(PODS, p.fan_state))
    return max(0.0, 1.0 - lift / w) if w > 0 else 0.0


def sensor_observation(lab):
    p = lab.aircraft; d = p.data
    obs = p.sensor_observation(lab.sensor_rng)
    obs.update(observation_id=lab.obs_id, t_s=round(float(d.time), 3), wall_utc=datetime.now(timezone.utc).isoformat(),
               command_mode='hold_until_changed', scheduler_backlog_s=round(lab.clock_lag_s, 3), time_scale=lab.time_scale,
               action_schema='phantom-fbw-1', mission=lab.mission, authority=lab.authority, active=lab.active, paused=lab.paused,
               configuration=dict(airframe_variant=p.variant, airframe_revision=p.provenance['revision'], config_sha256=p.P.config_sha256,
                                  load_state=p.load_state, occupants=p.L.occupants, initial_fuel_kg=float(p.fuel_initial.sum())),
               sensor_status='Provisional modelled sensors: GNSS, baro, radar altimeter (ray along gravity), AHRS, body-axis gyro, fan rpm, pod/leg/surface position, power, fuel; no truth forces')
    return obs


def accept_timing(lab, row):
    d = lab.aircraft.data; obs = row.get('observation') or {}
    row['timing'] = dict(observation_sim_t_s=obs.get('t_s'), observation_wall_utc=obs.get('wall_utc'), accept_wall_utc=datetime.now(timezone.utc).isoformat(),
                         accept_sim_t_s=float(d.time), apply_sim_t_s=row['apply_t_s'], observation_age_s=(float(d.time) - obs['t_s']) if obs else None,
                         command_mode='hold_until_changed', scheduler_backlog_s=lab.clock_lag_s,
                         time_scale=lab.time_scale)


def integrate(lab):
    p = lab.aircraft
    while lab.next_pending_action < len(lab.action_log):
        row = lab.action_log[lab.next_pending_action]
        if row.get('cancelled'):
            lab.next_pending_action += 1; continue
        if p.data.time < row['apply_t_s']:
            break
        lab.next_pending_action += 1
        if row['issued']['authority'] != lab.authority:
            row['cancelled'] = True
            lab.log('control_cancelled', dict(sequence=row['sequence'], reason='Control authority changed before application')); continue
        n0 = len(p.events)
        p.set_command(row['issued']); row['applied'] = True
        lab.log('control_applied', dict(sequence=row['sequence'], requested=row['issued'], applied_sim_t_s=float(p.data.time)))
        for e in p.fcc.pti.log:
            if not e.get('_logged'):
                e['_logged'] = True; lab.log('pti_event', {k: v for k, v in e.items() if k != '_logged'})
    was_crashed = p.crashed; nev = len(p.events)
    p.step()
    for e in p.events[nev:]:
        lab.log('phantom_event', e)
    for e in p.fcc.pti.log:
        if not e.get('_logged'):
            e['_logged'] = True; lab.log('pti_event', {k: v for k, v in e.items() if k != '_logged'})
    if p.crashed and not was_crashed:
        p.dump_ring(lab.log_path / 'crash_ring.npz')
        lab.log('crash_capture', dict(file='crash_ring.npz', impact_velocity_m_s=p.data.qvel[:3].tolist(), attitude=p.attitude(), max_contact_force_n=p.max_impact_n))
    if p.data.time - lab.last_audit_t >= .05:
        lab.last_audit_t = float(p.data.time)
        lab.log('physics_audit', p.physical_snapshot())
        lab.sensor_observation()
        lab.checkpoint()
        maybe_evaluate_cg_gate(lab)
        support = p.support_count()
        speed = float(np.linalg.norm(p.data.qvel[:3]))
        level = float(p.R()[2, 2]) > .98
        # Distinguish gear-supported settling from touch while the fans carry the load.
        loaded = gear_weight_fraction(p) >= LANDED_GEAR_LOAD_FRACTION
        lab.update_landing_evidence(support=support,level=level,speed=speed,loaded=loaded)



def checkpoint_plant(p):
    return p.checkpoint_state()


def summary_extras(lab):
    p = lab.aircraft
    if p.step_log is not None:
        p.step_log.close(); p.step_log = None
    mp = p.mass_properties(); E = p.bus.energy
    return dict(variant=p.variant, config_sha256=p.P.config_sha256, time_scale=lab.time_scale, load_state=p.load_state,
                mass_start_kg=p.provenance['ledger_mass_kg'], mass_end_kg=mp['mass_kg'], energy=E, events=p.events[-100:], faults=p.faults,
                lease_expired=lab.lease_expired, cg_gate=getattr(lab, 'phantom_cg_gate', None),
                landing_site=getattr(lab, 'phantom_landing_site', None), crash_capture='crash_ring.npz' if p.crashed else None,
                material_synthetic_assumptions=['pod fan FM_open and duct sigma', 'turbogenerator mass/SFC/spool', 'buffer power/energy density',
                                               'component masses (ledger)', 'wing polars (handover, SYNTHETIC)', 'ground effect model'])
