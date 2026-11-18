"""Sensitivity of the braking transient to the ECU wing-unloading gain, its filter, the spoileron and the offset
limit (8 s of braking after 'airbrake: on', both starts). Run from anywhere:
    python evidence/phantom/a10c_airbrake_ecu_20261118/scripts/unload_sweep.py
Output columns: start, gain (rad per unit collective), tau (s), spoileron (deg), limit (deg) -> airspeed at 6 s,
peak deceleration (0.2 s window), braking pitch range over the first 6 s, altitude range."""
import copy, sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src')); sys.path.insert(0, str(ROOT / 'tools/phantom'))
import a10c_airbrake_test as T   # noqa: E402
from vtx.phantom import overlays   # noqa: E402

G = 9.80665
_orig = overlays.load


def run(args):
    start, gain, tau, sp, mx = args
    def load(name):
        ov = copy.deepcopy(_orig(name)); f = ov['fbw_transition']
        f['unload_pitch_rad_per_collective']['v'] = gain; f['unload_pitch_tau_s']['v'] = tau
        f['spoileron_deg']['v'] = sp; f['unload_pitch_max_deg']['v'] = mx
        return ov
    T.overlays.load = load
    a = T.build('on', start); d = a.data; t0 = float(d.time); z0 = float(d.qpos[2])
    a.set_command(dict(airbrake='on', pitch=0.0))
    V = []; P = []; Z = []
    for i in range(int(8.0 / T.DT)):
        a.step()
        if i % 20 == 0:
            r = T.row(a, t0, z0); V.append((r['t'], r['airspeed'])); P.append(r['pitch']); Z.append(r['alt'])
    dec = [-(V[i + 2][1] - V[i - 2][1]) / (V[i + 2][0] - V[i - 2][0]) / G for i in range(2, len(V) - 2)]
    u6 = min(V, key=lambda x: abs(x[0] - 6.0))[1]
    return (start, gain, tau, sp, mx, round(u6, 1), round(max(dec), 3), round(min(P[:120]), 1), round(max(P[:120]), 1), round(min(Z), 2), round(max(Z), 2))


if __name__ == '__main__':
    cases = [(s, g, t, sp, mx) for s in ('reference', 'cruise') for (g, t, sp, mx) in
             [(0.6, 0.5, 12, 6), (0.3, 0.5, 12, 6), (0.3, 1.0, 12, 6), (0.15, 1.0, 12, 6), (0.6, 0.5, 6, 6), (0.3, 1.0, 6, 6), (0.3, 1.0, 12, 3)]]
    with Pool(7) as p:
        for r in p.imap(run, cases):
            print('start %-9s gain %.2f tau %.1f spoil %2d max %d -> u6 %5.1f peak %.3f g pitch %5.1f..%4.1f alt %5.2f..%5.2f' % r, flush=True)
