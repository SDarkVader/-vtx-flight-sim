"""Phantom A10-C fan-assisted air-braking, 90 deg decelerating turn and transition to hover, flown through the
transition ECU (inputs/phantom_overlays/transition_ecu_v1.json). Offline engineering test on a flat strip.

The pilot makes discrete cockpit inputs only (an input card): no collective inputs and no feedback laws in the
test. Every input is logged with its time and the cue the pilot acted on:
  1. 'airbrake: on', pitch stick centred            at t0
  2. roll stick held at 2/3 (bank request)          when indicated airspeed < 60 m/s   (9 Nov cue)
  3. roll stick centred, pedal 1/2 right            when indicated airspeed < 15 m/s and the turn is not complete
                                                    (below wing-borne speed the bank no longer turns the aircraft)
  4. roll stick and pedal centred                   when the heading indicator shows 90 deg of turn (no lead)
The ECU coordinates fans, pods, boosters, spoilerons, DRS stabilator, canards, rudders, TVC and the attitude,
vertical-speed and turn loops.

Starts (airborne, 300 m, 95 m/s, wings locked):
  reference  9 Nov V2/V3 initial state: pitch +4 deg, pods already at 90 deg, fans pre-spun to 5 % of the weight,
             boosters off, generator on its take-off rating
  cruise     A10-C cruise: pitch +4 deg, pods stowed, fans stopped, turbojets spooled at the throttle that balances the
             initial drag, generator at its cruise output; the ECU must tilt the pods and spool the fans itself
ECU options: 'on' (A10-C + transition_ecu_v1) or 'off' (A10-C as loaded live; same inputs, the airbrake command is
ignored by the aircraft, so the card is replaced by its manual equivalent: pods 90, boosters 0, vertical-speed mode,
collective lever up, pitch stick centred; inputs 2-4 unchanged).

  python tools/phantom/a10c_airbrake_test.py --start reference --ecu on --out results/run.json

--variant phantom-a10d flies the A10-D test aircraft (inputs/phantom_test_variants_v1.json), which carries the same
overlay in its definition instead of as overrides; it has the ECU, so it takes --ecu on only.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, sys
from pathlib import Path
import numpy as np
import mujoco as mj

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from vtx.world import TestWorld
from vtx.aircraft import DT
from vtx.phantom import overlays
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.geometry import PODS, SIDE, WING_SIDES

G = 9.80665
VARIANT = 'phantom-a10c'
ECU_VARIANT = 'phantom-a10d'   # test aircraft: phantom-a10c + transition_ecu_v1 in its definition
LIVE_CONFIG_SHA = '2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f'


class FlatWorld(TestWorld):
    """8 km x 8 km flat strip, no obstacles (as the 9 Nov campaign)."""
    id = 'flat-test-strip'; version = '1'; half = 4000.; n = 11

    def __init__(self):
        self.seed = 0; self.heights = np.zeros((self.n, self.n)); self.obstacles = []
        self.water = dict(x=1e6, y=1e6, half_x=1.0, half_y=1.0)


def steps(a, seconds, every=None, cb=None):
    n = int(round(seconds / DT)); k = max(1, int(round((every or seconds) / DT)))
    for i in range(n):
        a.step()
        if cb is not None and i % k == 0 and cb(a):
            return True
    return False


def build(ecu, start, variant=VARIANT):
    if variant == ECU_VARIANT and ecu != 'on':
        raise ValueError(f'{ECU_VARIANT} has the ECU by definition; the aircraft without it is {VARIANT}')
    ov = overlays.load('transition_ecu_v1') if ecu == 'on' and variant == VARIANT else None
    a = PhantomAircraft(FlatWorld(), variant, start_configuration='road', overrides=ov); a.spawn(-3500.0, 0.0, 0.0)
    m, d, P = a.model, a.data, a.P
    a.set_command(dict(brake=[1.0] * 4, wing='deploy', canard_fold='deployed')); steps(a, 9.0)   # wings locked on the ground
    assert all(a.wing_state[s] == 'locked' for s in WING_SIDES), a.wing_state
    W = a.mass_properties()['mass_kg'] * G
    d.qpos[2] += 300.0; th = math.radians(4.0); d.qpos[3:7] = [math.cos(th / 2), 0, -math.sin(th / 2), 0]
    d.qvel[:] = 0.0; d.qvel[0] = 95.0
    cmd = dict(stability_mode='attitude', pitch=0.4, roll=0.0, yaw=0.0, wheel_drive=[0.] * 4, brake=[0.] * 4, flap_deg=[0., 0.])
    if start == 'reference':
        for k in PODS:
            a.set_q(f'pod_{k}', SIDE[k] * math.pi / 2); a.targets[f'pod_{k}'] = SIDE[k] * math.pi / 2
            d.qvel[m.jnt_dofadr[a.jid[f'pod_{k}_fan']]] = P['pods.rotor_spin_sense'][k] * a.fan.omega_for_thrust(0.05 * W / 4)
        a.bus.gen_power = [P['generators.takeoff_power_each_w']] * len(a.bus.gen_power)
        cmd.update(collective=0.05, booster_throttle=[0., 0.], pod_tilt_deg=[90.] * 4)
    else:
        mj.mj_forward(m, d); a.control_update(4 * DT)
        drag = -float(a.aero_out['force_body'][0])
        lapse = 1.0 - 95.0 / a.jet['vj_m_s']; thr = float(np.clip(drag / (2 * a.jet['t0_station_n'] * lapse), a.jet['idle'], 1.0))
        a.jet_spool = [thr, thr]
        a.bus.gen_power = [P['generators.power_each_w'] * 0.15] * len(a.bus.gen_power)
        cmd.update(collective=0.0, booster_throttle=[thr, thr], pod_tilt_deg=[0.] * 4)
    mj.mj_forward(m, d)
    a.set_command(cmd)
    return a


def row(a, t0, z0):
    d = a.data; att = a.attitude(); vb = a.vel_body(); w = a.rates_body(); fl = a.fcc.last or {}; b = a.bus.last or {}
    va = vb - a.R().T @ a.wind; V = float(np.linalg.norm(va))
    F = np.asarray(a.aero_out['force_body']); M = np.asarray(a.aero_out['moment_body'])
    j = lambda n: float(a.joint(n)[0])
    return dict(
        t=round(float(d.time) - t0, 3), x=float(d.qpos[0]), y=float(d.qpos[1]), alt=float(d.qpos[2]) - z0, vz=float(d.qvel[2]),
        airspeed=V, u=float(vb[0]), ground_speed=float(np.linalg.norm(d.qvel[:2])),
        pitch=math.degrees(att['pitch_up']), roll=math.degrees(att['roll']), hdg=math.degrees(att['yaw_left']),
        p=math.degrees(w[0]), q=-math.degrees(w[1]), r=math.degrees(w[2]),
        alpha=math.degrees(math.atan2(-va[2], max(abs(va[0]), 1e-3))), beta=math.degrees(math.atan2(va[1], max(abs(va[0]), 1e-3))),
        mode=fl.get('mode'), airbrake=fl.get('airbrake'), w_tr=fl.get('transition_weight'), att_cmd=fl.get('attitude_cmd_deg'),
        yaw_rate_cmd=fl.get('yaw_rate_cmd_deg_s'), demand=fl.get('moment_demand'), saturated=bool(fl.get('saturated')),
        coll=fl.get('collective_applied'), trim=fl.get('trim_collective_estimate'), lift_est=fl.get('other_lift_estimate_n'), lift_relief=fl.get('lift_relief_n'),
        fan_T=[s.get('thrust_n', 0.0) for s in a.fan_state], fan_Tcmd=list(a.alloc.get('thrust') or [0] * 4),
        fan_rpm=[abs(a.joint(f'pod_{k}_fan')[1]) * 60 / (2 * math.pi) for k in PODS], ram=[s.get('ram_drag_n', 0.0) for s in a.fan_state],
        tilt=[math.degrees(abs(j(f'pod_{k}'))) for k in PODS], tilt_cmd=list(a.alloc.get('tilt_deg') or [0] * 4),
        ail=[math.degrees(j(f'aileron_{s}')) for s in WING_SIDES], ail_cmd=list(a.alloc.get('aileron_deg') or [0, 0]),
        canard=[math.degrees(j(f'canard_{s}')) for s in WING_SIDES], canard_cmd=list(a.alloc.get('canard_deg') or [0, 0]),
        stab=math.degrees(a.stab_te_up), stab_ab_cmd=fl.get('stab_airbrake_te_up_deg'), rudder=math.degrees(a.rudder), tvc=[math.degrees(x) for x in a.tvc],
        booster_T=[s.get('thrust_n', 0.0) for s in a.booster_state], jet_spool=list(a.jet_spool), booster_cmd=list(a.fcc.cmd['booster_throttle']),
        aero_F=F.tolist(), aero_M=M.tolist(),
        gen_w=b.get('generator_w'), gen_avail_w=b.get('generator_available_w'), buffer_w=b.get('buffer_w'), delivered_w=b.get('delivered_w'),
        unmet_w=b.get('unmet_w'), soc=a.bus.soc, fuel_kg=float(a.fuel.sum()), prop_scale=a.prop_scale, support=a.support_count(), crashed=a.crashed)


def fly(start, ecu, out, variant=VARIANT):
    a = build(ecu, start, variant); d = a.data; mass0 = a.mass_properties()['mass_kg']
    t0 = float(d.time); z0 = float(d.qpos[2]); log = []; card = []; st = dict(phase='brake', hdg0=None)
    def pilot_input(cue, action):
        card.append(dict(t=round(float(d.time) - t0, 3), cue=cue, input=action)); a.set_command(action)
    if ecu == 'on':
        pilot_input('t0', dict(airbrake='on', pitch=0.0))
    else:
        pilot_input('t0 (manual equivalent of airbrake on)', dict(pod_tilt_deg=[90.] * 4, booster_throttle=[0., 0.], stability_mode='attitude_vs',
                                                                    vertical_speed_m_s=0.0, collective=0.5, pitch=0.0))
    def cb(a):
        r = row(a, t0, z0); log.append(r)
        # degrees turned in the commanded direction (roll right / nose right = heading 'yaw_left' decreasing)
        turned = -(((r['hdg'] - st['hdg0'] + 180) % 360) - 180) if st['hdg0'] is not None else 0.0
        if st['phase'] == 'brake' and r['airspeed'] < 60.0:
            st['phase'] = 'turn'; st['hdg0'] = r['hdg']; st['t_turn'] = r['t']
            pilot_input(f"airspeed indicator {r['airspeed']:.1f} m/s < 60", dict(roll=2 / 3))
        elif st['phase'] == 'turn' and turned >= 90.0:
            st['phase'] = 'hover'; st['t_release'] = r['t']
            pilot_input(f"heading indicator {turned:.1f} deg of turn", dict(roll=0.0, yaw=0.0))
        elif st['phase'] == 'turn' and r['airspeed'] < 15.0 and not st.get('pedal'):
            st['pedal'] = r['t']   # below wing-borne speed the bank no longer turns the aircraft: finish on the pedals
            pilot_input(f"airspeed indicator {r['airspeed']:.1f} m/s < 15, heading {turned:.1f} deg of turn", dict(roll=0.0, yaw=0.5))
        end = st['phase'] == 'hover' and r['t'] > st['t_release'] + 20.0
        return a.crashed or abs(r['pitch']) > 60 or abs(r['roll']) > 80 or r['alt'] < -250 or end or r['t'] > 90.0
    steps(a, 120.0, every=0.05, cb=cb)
    res = dict(test=f'{variant} fan-assisted air-braking, 90 deg turn, transition to hover', start=start, ecu=ecu,
               variant=variant, **({'ecu_fitted_by': 'variant definition (inputs/phantom_test_variants_v1.json)'} if variant == ECU_VARIANT else {}),
               config_sha256=a.P.config_sha256, live_config_sha256=LIVE_CONFIG_SHA,
               overlays=['transition_ecu_v1'] if ecu == 'on' else [], model_xml_sha256=a.provenance['model_xml_sha256'],
               mass_kg=mass0, mass_end_kg=a.mass_properties()['mass_kg'], input_card=card, phases={k: v for k, v in st.items() if k != 'phase'},
               end_phase=st['phase'], crashed=a.crashed, events=[e for e in a.events if e.get('event') not in ('wing_state',)][-50:], log=log)
    res['metrics'] = metrics(res)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out if out.endswith('.gz') else out + '.gz', 'wt') as f:
        json.dump(res, f)
    return res


def metrics(res):
    L = res['log']; ph = res['phases']
    def at(t): return min(L, key=lambda r: abs(r['t'] - t))
    k = 20   # 1 s window at 20 Hz
    dec = [((L[i]['u'] - L[i + k]['u']) / (L[i + k]['t'] - L[i]['t']) / G, L[i]['t']) for i in range(len(L) - k)]
    t_turn = ph.get('t_turn'); t_rel = ph.get('t_release')
    brake = [r for r in L if t_turn is None or r['t'] <= t_turn]
    turn = [r for r in L if t_turn is not None and t_turn <= r['t'] <= (t_rel or 1e9)]
    tail = [r for r in L if t_rel is not None and r['t'] >= L[-1]['t'] - 5.0]
    e0, e1 = L[0], L[-1]
    m = dict(duration_s=e1['t'], u_at_6s=at(6.0)['u'], airspeed_at_6s=at(6.0)['airspeed'], peak_decel_g=max(x for x, _ in dec) if dec else None,
             t_peak_decel_s=max(dec)[1] if dec else None,
             braking_pitch_range_deg=[min(r['pitch'] for r in brake), max(r['pitch'] for r in brake)],
             max_abs_q_deg_s=max(abs(r['q']) for r in L), max_abs_p_deg_s=max(abs(r['p']) for r in L),
             alt_range_m=[min(r['alt'] for r in L), max(r['alt'] for r in L)], max_abs_vz_m_s=max(abs(r['vz']) for r in L),
             turn_started_s=t_turn, turn_released_s=t_rel,
             turn_heading_change_deg=(turn[-1]['hdg'] - turn[0]['hdg']) if turn else None, turn_duration_s=(t_rel - t_turn) if t_rel and t_turn else None,
             turn_speed_m_s=[turn[0]['airspeed'], turn[-1]['airspeed']] if turn else None,
             turn_max_bank_deg=max(abs(r['roll']) for r in turn) if turn else None, turn_max_abs_beta_deg=max(abs(r['beta']) for r in turn if r['airspeed'] > 10) if turn else None,
             hover_end=dict(ground_speed_m_s=e1['ground_speed'], vz_m_s=e1['vz'], pitch_deg=e1['pitch'], roll_deg=e1['roll'], alt_m=e1['alt'],
                            max_ground_speed_last5s=max(r['ground_speed'] for r in tail) if tail else None,
                            max_abs_vz_last5s=max(abs(r['vz']) for r in tail) if tail else None,
                            hdg_change_total_deg=e1['hdg'] - e0['hdg']),
             max_fan_thrust_n=max(max(r['fan_T']) for r in L), max_fan_rpm=max(max(r['fan_rpm']) for r in L),
             saturated_fraction=sum(r['saturated'] for r in L) / len(L), max_unmet_w=max((r['unmet_w'] or 0) for r in L),
             min_prop_scale=min(r['prop_scale'] for r in L), soc=[e0['soc'], e1['soc']], fuel_used_kg=e0['fuel_kg'] - e1['fuel_kg'],
             max_delivered_w=max((r['delivered_w'] or 0) for r in L), max_stab_deg=max(r['stab'] for r in L),
             min_ail_deg=min(min(r['ail']) for r in L), canard_range_deg=[min(min(r['canard']) for r in L), max(max(r['canard']) for r in L)],
             booster_thrust_at=[[t, at(t)['booster_T']] for t in (0, 1, 2, 4, 6)], crashed=res['crashed'])
    return m


def summary(res):
    m = res['metrics']; L = res['log']
    print(f"== start={res['start']} ecu={res['ecu']} config {res['config_sha256'][:8]} (live A10-C {LIVE_CONFIG_SHA[:8]}) xml {res['model_xml_sha256'][:8]} mass {res['mass_kg']:.1f} kg; end phase {res['end_phase']}")
    for c in res['input_card']:
        print(f"   input t+{c['t']:5.2f}  {c['input']}   <- {c['cue']}")
    for r in L[::max(1, len(L) // 22)] + [L[-1]]:
        print('  t+%5.1f V %5.1f u %+5.1f gs %5.1f alt %+6.1f vz %+5.2f pitch %+5.1f roll %+5.1f hdg %+6.1f beta %+6.1f wtr %.2f coll %.2f liftE %5.0f fanT %s tilt %s ail %s can %s stab %4.1f rud %+5.1f Tb %s P %4.0fkW unmet %3.0f soc %.3f' %
              (r['t'], r['airspeed'], r['u'], r['ground_speed'], r['alt'], r['vz'], r['pitch'], r['roll'], r['hdg'], r['beta'], r['w_tr'] or 0, r['coll'] or 0, r['lift_est'] or 0,
               [round(x) for x in r['fan_T']], [round(x) for x in r['tilt']], [round(x, 1) for x in r['ail']], [round(x, 1) for x in r['canard']], r['stab'], r['rudder'],
               [round(x) for x in r['booster_T']], (r['delivered_w'] or 0) / 1e3, (r['unmet_w'] or 0) / 1e3, r['soc']))
    print('  metrics', json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k not in ('hover_end', 'booster_thrust_at')}))
    print('  hover_end', {k: round(v, 3) if isinstance(v, float) else v for k, v in m['hover_end'].items()})
    print('  booster thrust', [[t, [round(x) for x in b]] for t, b in m['booster_thrust_at']])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', choices=('reference', 'cruise'), default='reference')
    ap.add_argument('--ecu', choices=('on', 'off'), default='on')
    ap.add_argument('--variant', choices=(VARIANT, ECU_VARIANT), default=VARIANT)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if a.variant == ECU_VARIANT and a.ecu != 'on':
        ap.error(f'{ECU_VARIANT} has the ECU by definition; fly {VARIANT} for the aircraft without it')
    summary(fly(a.start, a.ecu, a.out, a.variant))
