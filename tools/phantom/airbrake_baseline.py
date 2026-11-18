"""Baseline: the 9 Nov 2026 V3 'turn_fan' schedule (reference/phantom_a10b_20261109/scripts/v3_a10b.py), unchanged
test-pilot laws, run on any Phantom variant with the current plant. Offline engineering test on a flat strip.

  python tools/phantom/airbrake_baseline.py <variant> <out.json>
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
import mujoco as mj

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from vtx.world import TestWorld
from vtx.aircraft import DT
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.geometry import PODS, SIDE


class FlatWorld(TestWorld):
    id = 'flat-test-strip'; version = '1'; half = 4000.; n = 11

    def __init__(self):
        self.seed = 0; self.heights = np.zeros((self.n, self.n)); self.obstacles = []
        self.water = dict(x=1e6, y=1e6, half_x=1.0, half_y=1.0)


def run(a, seconds, every=0.05, stop=None):
    n = int(round(seconds / DT)); k = max(1, int(round(every / DT)))
    for i in range(n):
        a.step()
        if stop is not None and i % k == 0 and stop(a):
            return


def main(variant, out):
    a = PhantomAircraft(FlatWorld(), variant, start_configuration='road'); a.spawn(-3500.0, 0.0, 0.0)
    m, d, P = a.model, a.data, a.P
    a.set_command(dict(brake=[1.0] * 4, wing='deploy', canard_fold='deployed')); run(a, 9.0)
    W = a.mass_properties()['mass_kg'] * 9.80665
    d.qpos[2] += 300.0; th = math.radians(4.0); d.qpos[3:7] = [math.cos(th / 2), 0, -math.sin(th / 2), 0]
    d.qvel[:] = 0.0; d.qvel[0] = 95.0
    for k in PODS:
        a.set_q(f'pod_{k}', SIDE[k] * math.pi / 2); a.targets[f'pod_{k}'] = SIDE[k] * math.pi / 2
        d.qvel[m.jnt_dofadr[a.jid[f'pod_{k}_fan']]] = P['pods.rotor_spin_sense'][k] * a.fan.omega_for_thrust(0.05 * W / 4)
    a.bus.gen_power = [P['generators.takeoff_power_each_w']] * len(a.bus.gen_power)
    mj.mj_forward(m, d); z_ref = float(d.qpos[2])
    a.set_command(dict(stability_mode='attitude', pitch=0.4, collective=0.05, booster_throttle=[0., 0.], wheel_drive=[0.] * 4, brake=[0.] * 4,
                       pod_tilt_deg=[90.] * 4, flap_deg=[0., 0.]))
    log = []; st = dict(t0=None, hdg0=None, turn=None, done=None)

    def pilot(a):
        att = a.attitude(); vb = a.vel_body(); b = a.bus.last or {}; t = float(d.time)
        r = dict(t=round(t, 2), u=round(float(vb[0]), 2), z=round(float(d.qpos[2]) - z_ref, 2), vz=round(float(d.qvel[2]), 2),
                 pitch=round(math.degrees(att['pitch_up']), 2), roll=round(math.degrees(att['roll']), 2), hdg=round(math.degrees(att['yaw_left']), 2),
                 alpha=round(math.degrees(math.atan2(-vb[2], max(abs(vb[0]), 1e-3))), 2), beta=round(math.degrees(math.atan2(vb[1], max(abs(vb[0]), 1e-3))), 2),
                 fanT=[round(s.get('thrust_n', 0)) for s in a.fan_state], Tb=[round(s.get('thrust_n', 0)) for s in a.booster_state],
                 bus_kw=round(b.get('delivered_w', 0) / 1e3), unmet_kw=round(b.get('unmet_w', 0) / 1e3), soc=round(a.bus.soc, 4),
                 coll=round(a.fcc.last.get('collective_applied', 0), 3), sat=bool(a.fcc.last.get('saturated')))
        log.append(r)
        if st['t0'] is None: st['t0'] = t
        a.set_command(dict(collective=float(np.clip(0.71 * (1 - min(1, (r['u'] / 95.0) ** 2)) / max(math.cos(math.radians(r['roll'])), 0.5)
                                                    + 0.03 + 0.03 * (-r['z']) - 0.08 * r['vz'], 0, 1))))
        if st['turn'] is None and r['u'] < 60.0:
            st['turn'] = t; st['hdg0'] = r['hdg']; a.set_command(dict(roll=30.0 / 45.0))
        if st['turn'] is not None:
            ph = math.radians(max(abs(r['roll']), 1.0))
            a.set_command(dict(yaw=float(np.clip(math.degrees(9.80665 * math.tan(ph) / max(r['u'], 15)) / 20.0, 0, 1))))
            if st['done'] is None and abs(r['hdg'] - st['hdg0']) >= 90.0: st['done'] = t
        return abs(r['pitch']) > 60 or abs(r['roll']) > 80 or a.crashed or (st['done'] and t > st['done'] + 2) or t - st['t0'] > 60
    run(a, 200, stop=pilot)
    Path(out).write_text(json.dumps(dict(variant=variant, config_sha256=P.config_sha256, model_xml_sha256=a.provenance['model_xml_sha256'],
                                         mass_kg=W / 9.80665, st=st, log=log)))
    L = log; t0 = L[0]['t']
    print(variant, P.config_sha256[:8], 'mass', round(W / 9.80665, 1), 'turn', st['turn'] and round(st['turn'] - t0, 1), 'done', st['done'] and round(st['done'] - t0, 1))
    for r in L[::max(1, len(L) // 16)] + [L[-1]]:
        print('  t+%5.1f u %6.1f z %+6.1f vz %+5.1f pitch %+5.1f roll %+5.1f beta %+6.1f hdg %+6.1f coll %.2f fanT %s Tb %s bus %d unmet %d sat %d' %
              (r['t'] - t0, r['u'], r['z'], r['vz'], r['pitch'], r['roll'], r['beta'], r['hdg'], r['coll'], r['fanT'], r['Tb'], r['bus_kw'], r['unmet_kw'], r['sat']))
    i6 = min(range(len(L)), key=lambda i: abs(L[i]['t'] - t0 - 6.0))
    dec = [(L[i]['u'] - L[i + 20]['u']) / (L[i + 20]['t'] - L[i]['t']) / 9.80665 for i in range(0, len(L) - 20, 20)]
    print('  u at 6 s %.1f; peak 1 s decel %.2f g' % (L[i6]['u'], max(dec)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
