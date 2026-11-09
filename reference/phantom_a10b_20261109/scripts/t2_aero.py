"""Test 2: per-surface lift and wing/flap state on the roll; maximum nose-up authority vs required."""
import sys, json, math, numpy as np
sys.path.insert(0, sys.argv[1]); import camp as C
P6 = {'proposals': {'p6_drs_stabilator': {'v': 1.0}}}
a = C.plant('phantom-fx', P6, start_configuration='road'); d = a.data
a.set_command(dict(brake=[1.0]*4, wing='deploy', canard_fold='deployed')); C.run(a, 9.0)
a.set_command(dict(flap_deg=[30., 30.], canard_pitch_deg=[0., 0.])); C.run(a, 2.5)
print('after deploy: wing_state', getattr(a, 'wing_state', None), 'slide', [round(a.joint(f'wing_{s}')[0], 3) for s in ('left', 'right')],
      'locked', {s: a.wing_locked(s) for s in ('left', 'right')}, 'flap_deg', [round(math.degrees(a.joint(f'flap_{s}')[0]), 1) for s in ('left', 'right')])
a.set_command(dict(brake=[0.]*4, wheel_drive=[1.]*4, booster_throttle=[1., 1.], stability_mode='attitude', pitch=0.0))
W = a.mass_properties()['mass_kg'] * 9.80665
def show(tag):
    out = a.aero_out; Rb = a.R()
    rows = []
    for o in out['surfaces']:
        f = np.array(o.get('force_n', [0, 0, 0]))
        rows.append((o['name'], round(o.get('alpha_deg', o.get('delta_deg', 0)), 1), round(o.get('cl', o.get('dcl', 0)), 3), round(f[2]), round(f[0])))
    print(tag, 'u', round(float(a.vel_body()[0]), 1), 'aero Fz', round(out['force_body'][2]), '(W', round(W), ')', 'locked', {s: a.wing_locked(s) for s in ('left', 'right')},
          'flap_deg', [round(math.degrees(a.joint(f'flap_{s}')[0]), 1) for s in ('left', 'right')], 'slide', [round(a.joint(f'wing_{s}')[0], 3) for s in ('left', 'right')])
    for r in rows: print('   ', r)
marks = [40, 80, 115]; k = [0]
def watch(a):
    u = float(a.vel_body()[0])
    if k[0] < len(marks) and u >= marks[k[0]]: show(f'@{marks[k[0]]}'); k[0] += 1
    return k[0] >= len(marks)
C.run(a, 90, every=0.1, stop=watch)
# static authority sweep at the current state (115 m/s, pitch 0) about the rear tyre contact
w = a.wing_locked
vb = a.vel_body(); st0 = None
