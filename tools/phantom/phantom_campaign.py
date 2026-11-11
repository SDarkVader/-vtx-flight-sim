"""Phantom performance campaign on the MuJoCo plant: budget, booster ignition, road acceleration, aero sweep,
rolling take-off and VTOL ceiling. Canned commands on a flat 8 km strip (no terrain, no obstacles): physics tests,
not piloted flights. Writes evidence/phantom/campaign_<variant>.json and prints a summary.

  PYTHONPATH=src python tools/phantom/phantom_campaign.py [--variant phantom] [--overrides '{"...": ...}'] [--tag name]
"""
from __future__ import annotations
import argparse, json, math, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from vtx.world import TestWorld
from vtx.aircraft import DT
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.surface_aero import SurfaceAero

G = 9.80665


class FlatWorld(TestWorld):
    """8 km x 8 km flat test strip: zero heightfield, no obstacles, water far outside the strip."""
    id = 'flat-test-strip'; version = '1'; half = 4000.; n = 11

    def __init__(self):
        self.seed = 0
        self.heights = np.zeros((self.n, self.n))
        self.obstacles = []
        self.water = dict(x=1e6, y=1e6, half_x=1.0, half_y=1.0)


W = FlatWorld()


def plant(variant, overrides=None, **kw):
    a = PhantomAircraft(W, variant, overrides=overrides, **kw)
    a.spawn(-3500.0, 0.0, 0.0)          # start near one end of the strip, heading +x
    return a


def run(a, seconds, every=0.1, log=None, stop=None):
    n = int(round(seconds / DT)); k = max(1, int(round(every / DT)))
    for i in range(n):
        a.step()
        if log is not None and i % k == 0:
            log(a)
        if stop is not None and i % k == 0 and stop(a):
            return True
    return False


def weight(a):
    return a.mass_properties()['mass_kg'] * G


def snapshot(a):
    v = a.vel_body(); att = a.attitude(); F = np.asarray(a.aero_out['force_body'])
    wing_lift = sum(s['force_n'][2] for s in a.aero_out['surfaces'] if s.get('name', '').startswith(('wing_', 'flap_', 'aileron_')) and 'force_n' in s)
    return dict(t=round(float(a.data.time), 3), x=round(float(a.data.qpos[0]), 2), z=round(float(a.data.qpos[2]), 3), u=round(float(v[0]), 3),
                pitch_deg=round(math.degrees(att['pitch_up']), 3), aero_fz=round(float(F[2]), 1), aero_fx=round(float(F[0]), 1),
                wing_lift=round(float(wing_lift), 1), supports=a.support_count(),
                booster_t=[round(float(s.get('thrust_n', 0.0)), 1) for s in a.booster_state],
                fan_t=[round(float(s.get('thrust_n', 0.0)), 1) for s in a.fan_state],
                bus_w=round(float((a.bus.last or {}).get('delivered_w', 0.0)), 0))


# ----------------------------------------------------------------------------------------- tests
def budget(variant, overrides):
    a = plant(variant, overrides, start_configuration='road')
    P = a.P; mp = a.mass_properties()
    fan, bst = a.fan, a.booster
    gen = P['generators.count'] * P['generators.power_each_w'] * P['generators.efficiency']
    Wn = mp['mass_kg'] * G
    def p_for(T, f):                       # ideal-with-FM momentum power for thrust T (same law as the plant's fan model)
        return T ** 1.5 / (f.fm_open * math.sqrt(2 * f.rho * f.area_m2))
    def t_for(Pw, f):
        return (Pw * f.fm_open * math.sqrt(2 * f.rho * f.area_m2)) ** (2 / 3)
    t_pow = t_for(gen / 4, fan)
    return dict(mass_kg=mp['mass_kg'], weight_n=Wn, cg_body_m=mp['cg_body_m'],
                generator_electrical_w=gen, fan_thrust_cap_each_n=fan.thrust_max, fan_area_m2=fan.area_m2,
                fan_disk_loading_at_hover_n_m2=Wn / 4 / fan.area_m2, booster_thrust_cap_each_n=bst.thrust_max,
                hover_power_required_w=4 * p_for(Wn / 4, fan), hover_tw_thrust_capped=4 * fan.thrust_max / Wn,
                hover_tw_power_capped_all_generator_to_fans=4 * t_pow / Wn,
                max_hover_mass_kg_power_capped=4 * t_pow / G, max_hover_mass_kg_thrust_capped=4 * fan.thrust_max / G)


def booster_ignition(variant, overrides):
    """brakes on, road stance; boosters 0 -> 1 at t0: thrust rise times, steady thrust, electrical power."""
    out = {}
    for level in (0.5, 1.0):
        a = plant(variant, overrides, start_configuration='road')
        a.set_command(dict(brake=[1.0] * 4)); run(a, 2.0)
        t0 = float(a.data.time); a.set_command(dict(booster_throttle=[level, level]))
        trace = []
        run(a, 8.0, every=0.02, log=lambda a: trace.append((float(a.data.time) - t0, float(sum(s.get('thrust_n', 0.0) for s in a.booster_state)),
                                                              float(sum(s.get('power_w', 0.0) for s in a.booster_state)))))
        T = np.array([r[1] for r in trace]); tt = np.array([r[0] for r in trace]); Pw = np.array([r[2] for r in trace])
        ss = float(T[-25:].mean())
        def t_at(f):
            i = np.argmax(T >= f * ss) if ss > 0 and (T >= f * ss).any() else None
            return float(tt[i]) if i is not None else None
        out[f'throttle_{level}'] = dict(steady_thrust_total_n=ss, steady_shaft_power_w=float(Pw[-25:].mean()), t10_s=t_at(0.1), t50_s=t_at(0.5),
                                        t90_s=t_at(0.9), still_held_by_brakes=bool(abs(a.vel_body()[0]) < 0.2), tw=ss / weight(a))
    return out


def road_accel(variant, overrides, boosters=False, seconds=45.0):
    a = plant(variant, overrides, start_configuration='road')
    a.set_command(dict(brake=[1.0] * 4)); run(a, 2.0)
    t0 = float(a.data.time)
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4, booster_throttle=[1.0, 1.0] if boosters else [0.0, 0.0]))
    log = []; run(a, seconds, every=0.1, log=lambda a: log.append(snapshot(a)))
    u = np.array([r['u'] for r in log]); t = np.array([r['t'] for r in log]) - t0
    def t_to(v):
        i = np.argmax(u >= v) if (u >= v).any() else None
        return float(t[i]) if i is not None else None
    acc = np.gradient(u, t)
    sup_min = min(r['supports'] for r in log)
    return dict(boosters=boosters, t_0_100_kmh=t_to(100 / 3.6), t_0_60_mph=t_to(60 * 0.44704), t_0_160_kmh=t_to(160 / 3.6),
                t_0_200_kmh=t_to(200 / 3.6), speed_at_s={str(s): float(np.interp(s, t, u)) for s in (5, 10, 20, 30, 45) if s <= seconds},
                peak_accel_g=float(acc[5:].max() / G), max_speed_m_s=float(u.max()), distance_m=float(log[-1]['x'] - log[0]['x']),
                pitch_deg_by_speed={str(v): float(np.interp(v, u, [r['pitch_deg'] for r in log])) for v in (0, 20, 40, 60) if u.max() >= v},
                min_supports=sup_min, crashed=a.crashed, flags=sorted(a.flags), trace=log[::5])


def aero_sweep(variant, overrides):
    """quasi-static: the plant's SurfaceAero with wings deployed and locked; whole-vehicle lift/drag/moment."""
    a = plant(variant, overrides, start_configuration='road')
    SA = a.aero if hasattr(a, 'aero') else SurfaceAero(a.P)
    Wn = weight(a); cg = np.array(a.mass_properties()['cg_body_m'])
    out = []
    for flap in (0.0, 30.0):
        for alpha in (-2, 0, 2, 4, 6, 8, 10, 12, 14):
            V = 60.0; th = math.radians(alpha)
            vb = np.array([V * math.cos(th), 0.0, -V * math.sin(th)])
            st = dict(wing_frac=dict(left=1.0, right=1.0), wing_locked=dict(left=True, right=True),
                      flap=dict(left=math.radians(flap), right=math.radians(flap)), aileron=dict(left=0.0, right=0.0),
                      canard_pitch=dict(left=0.0, right=0.0), canard_deployed=dict(left=True, right=True))
            r = SA.compute(vb, np.zeros(3), np.zeros(3), st)
            F = r['force_body']; M = r['moment_body'] - np.cross(cg, F)
            # lift/drag in wind axes
            dd = -vb / V; ld = np.array([math.sin(th), 0, math.cos(th)])
            L, D = float(F @ ld), float(-(F @ dd)) * -1
            q = 0.5 * SA.rho * V * V; S = a.P.handover['aero_surfaces']['wing']['S_ref_m2']
            out.append(dict(flap_deg=flap, alpha_deg=alpha, CL=L / (q * S), CD=float(-(F @ -dd)) / (q * S) if False else float(F @ (-dd) * -1) / (q * S),
                            Cm_cg_nose_up=float(-M[1]) / (q * S * a.P.handover['aero_surfaces']['wing']['mac_m']),
                            V_for_L_eq_W=math.sqrt(Wn / max(1e-6, 0.5 * SA.rho * S * (L / (q * S)))) if L > 0 else None))
    return out


def takeoff(variant, overrides, flap=30.0, rotate_pitch=1.0, canard_deg=10.0, rotate_speed=60.0, seconds=60.0, mode='rate_damping'):
    """road start: deploy wings, flaps, canards; full wheel drive + boosters; rotate at rotate_speed (or lift >= 0.8 W)."""
    a = plant(variant, overrides, start_configuration='road')
    a.set_command(dict(brake=[1.0] * 4, wing='deploy', canard_fold='deployed')); run(a, 9.0)
    a.set_command(dict(flap_deg=[flap, flap], canard_pitch_deg=[canard_deg, canard_deg])); run(a, 2.5)
    wing_ok = dict(a.wing_state) if hasattr(a, 'wing_state') else None
    Wn = weight(a); t0 = float(a.data.time)
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4, booster_throttle=[1.0, 1.0], stability_mode=mode, pitch=0.0))
    log = []; state = dict(rotated=None, liftoff=None, airborne_since=None)

    def watch(a):
        s = snapshot(a); log.append(s)
        lift = -0.0 + s['aero_fz']
        if state['rotated'] is None and (lift >= 0.8 * Wn or s['u'] >= rotate_speed):
            state['rotated'] = s['t'] - t0; a.set_command(dict(pitch=rotate_pitch))
        if s['supports'] == 0:
            state['airborne_since'] = state['airborne_since'] or s['t']
            if state['liftoff'] is None and s['t'] - state['airborne_since'] > 1.0:
                state['liftoff'] = dict(t_s=state['airborne_since'] - t0, u_m_s=s['u'], x_m=s['x'] - log[0]['x'])
        else:
            state['airborne_since'] = None
        return state['liftoff'] is not None and s['t'] - t0 > state['liftoff']['t_s'] + 6

    run(a, seconds, every=0.1, stop=watch)
    u = np.array([r['u'] for r in log]); fz = np.array([r['aero_fz'] for r in log])
    i_lw = int(np.argmax(fz >= Wn)) if (fz >= Wn).any() else None
    flaps = [math.degrees(a.joint(f'flap_{sd}')[0]) for sd in ('left', 'right')]
    climb = [r for r in log if state['liftoff'] and r['t'] - t0 >= state['liftoff']['t_s']]
    return dict(weight_n=Wn, mode=mode, rotate_pitch=rotate_pitch, wing_state=wing_ok, rotate_speed_m_s=rotate_speed,
                height_gain_after_liftoff_m=(max(r['z'] for r in climb) - climb[0]['z']) if climb else None,
                pitch_after_liftoff_deg=[r['pitch_deg'] for r in climb[::5]] if climb else None, rotate_at_s=state['rotated'], liftoff=state['liftoff'], flap_deg_end=flaps,
                max_pitch_deg=float(max(r['pitch_deg'] for r in log)),
                speed_when_aero_lift_eq_weight=float(u[i_lw]) if i_lw is not None else None,
                max_aero_lift_over_weight=float(fz.max() / Wn), max_speed_m_s=float(u.max()), final=log[-1] if log else None,
                crashed=a.crashed, flags=sorted(a.flags), events=[e for e in a.events if e.get('event') in ('liftoff', 'touchdown', 'hard_landing', 'crash')][-6:],
                trace=log[::5])


def takeoff_climb(variant, overrides, flap=30.0, rotate_speed=70.0, rotate_pitch=1.0, climb_pitch=0.7, post_s=25.0, seconds=90.0):
    """Pilot schedule: attitude mode, canard trim 0, flaps 30; full wheel drive + boosters; rotate to rotate_pitch
    (x 10 deg) at rotate_speed; after wheels leave, hold climb_pitch for post_s. Records the airborne phase."""
    a = plant(variant, overrides, start_configuration='road')
    a.set_command(dict(brake=[1.0] * 4, wing='deploy', canard_fold='deployed')); run(a, 9.0)
    a.set_command(dict(flap_deg=[flap, flap], canard_pitch_deg=[0.0, 0.0])); run(a, 2.5)
    Wn = weight(a); t0 = float(a.data.time)
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[1.0] * 4, booster_throttle=[1.0, 1.0], stability_mode='attitude', pitch=0.0))
    log = []; st = dict(rot=None, off=None, off_u=None, off_x=None, climb_set=False, contacts_after=0)

    def watch(a):
        s = snapshot(a); log.append(s); t = s['t'] - t0
        if st['rot'] is None and s['u'] >= rotate_speed:
            st['rot'] = t; a.set_command(dict(pitch=rotate_pitch))
        if st['off'] is None and s['supports'] == 0 and (st['rot'] is not None or s['u'] > 30.0):   # incidence wings can lift before rotation
            st['off'] = t; st['off_u'] = s['u']; st['off_x'] = s['x'] - log[0]['x']
        if st['off'] is not None:
            if not st['climb_set'] and t - st['off'] > 0.5:
                st['climb_set'] = True; a.set_command(dict(pitch=climb_pitch, wheel_drive=[0.0] * 4))
            if s['supports'] > 0 and t - st['off'] > 1.0:
                st['contacts_after'] += 1
            return t - st['off'] > post_s or a.crashed
        return False

    run(a, seconds, every=0.1, stop=watch)
    air = [r for r in log if st['off'] is not None and r['t'] - t0 >= st['off']]
    z0 = log[0]['z']
    return dict(weight_n=Wn, mass_kg=Wn / G, rotate_speed=rotate_speed, rotate_at_s=st['rot'], liftoff_t_s=st['off'], liftoff_u_m_s=st['off_u'],
                liftoff_ground_roll_m=st['off_x'], airborne_s=(air[-1]['t'] - air[0]['t']) if air else 0.0,
                max_height_m=(max(r['z'] for r in air) - z0) if air else 0.0, end_height_m=(air[-1]['z'] - z0) if air else 0.0,
                end_u_m_s=air[-1]['u'] if air else None, pitch_range_deg=[min(r['pitch_deg'] for r in air), max(r['pitch_deg'] for r in air)] if air else None,
                ground_contacts_after_liftoff=st['contacts_after'], crashed=a.crashed, flags=sorted(a.flags),
                trace=[r for r in log[::5]] + ([] if not air else air[::2]))


def flight_metrics(trace, t0=None):
    """trace-derived metrics (independent of the pilot schedule's own bookkeeping)."""
    if not trace:
        return {}
    t0 = trace[0]['t'] if t0 is None else t0; z0 = trace[0]['z']
    air = [r for r in trace if r['supports'] == 0 and r['u'] > 20.0]
    first = air[0] if air else None
    return dict(first_wheels_off_t_s=(first['t'] - t0) if first else None, first_wheels_off_u_m_s=first['u'] if first else None,
                ground_roll_m=(first['x'] - trace[0]['x']) if first else None, max_height_m=max(r['z'] for r in trace) - z0,
                airborne_samples=len(air), pitch_range_deg=[min(r['pitch_deg'] for r in trace), max(r['pitch_deg'] for r in trace)],
                max_speed_m_s=max(r['u'] for r in trace))


def vtol_ceiling(variant, overrides, seconds=6.0):
    a = plant(variant, overrides, start_configuration='vtol')
    a.set_command(dict(stability_mode='attitude_vs', collective=1.0, vertical_speed_m_s=3.0, brake=[0.0] * 4)); log = []
    run(a, seconds, every=0.1, log=lambda a: log.append(snapshot(a)))
    Wn = weight(a)
    tf = np.array([sum(r['fan_t']) for r in log])
    return dict(fan_thrust_total_n_late=float(tf[-10:].mean()), tw=float(tf[-10:].mean() / Wn), max_height_gain_m=float(max(r['z'] for r in log) - log[0]['z']),
                supports_end=log[-1]['supports'], bus_w_end=log[-1]['bus_w'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='phantom'); ap.add_argument('--overrides', default=None); ap.add_argument('--tag', default=None)
    ap.add_argument('--only', default=None)
    a = ap.parse_args()
    ov = json.loads(a.overrides) if a.overrides else None
    tests = dict(budget=lambda: budget(a.variant, ov), boosters=lambda: booster_ignition(a.variant, ov),
                 drive=lambda: road_accel(a.variant, ov, False), drive_boost=lambda: road_accel(a.variant, ov, True),
                 aero=lambda: aero_sweep(a.variant, ov), takeoff=lambda: takeoff(a.variant, ov),
                 takeoff_r50=lambda: takeoff(a.variant, ov, rotate_speed=50.0), takeoff_r70=lambda: takeoff(a.variant, ov, rotate_speed=70.0),
                 climb=lambda: takeoff_climb(a.variant, ov),
                 climb_inc=lambda: takeoff_climb(a.variant, ov, rotate_speed=80.0, rotate_pitch=0.3, climb_pitch=0.3),
                 to_att55=lambda: takeoff(a.variant, ov, rotate_speed=55.0, rotate_pitch=0.9, mode='attitude'),
                 to_att60=lambda: takeoff(a.variant, ov, rotate_speed=60.0, rotate_pitch=0.9, mode='attitude'),
                 to_att65=lambda: takeoff(a.variant, ov, rotate_speed=65.0, rotate_pitch=0.9, mode='attitude'), vtol=lambda: vtol_ceiling(a.variant, ov))
    sel = a.only.split(',') if a.only else list(tests)
    res = dict(variant=a.variant, overrides=ov, world=W.id, dt=DT)
    for k in sel:
        t = time.time(); res[k] = tests[k](); res[k + '_wall_s'] = round(time.time() - t, 1)
        print(k, 'done', res[k + '_wall_s'], 's', flush=True)
    name = f"campaign_{a.tag or a.variant}.json"
    (ROOT / 'evidence/phantom' / name).write_text(json.dumps(res, indent=1, default=float))
    print('wrote', name)


if __name__ == '__main__':
    main()
