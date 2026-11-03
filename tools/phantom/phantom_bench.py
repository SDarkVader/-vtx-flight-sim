"""Phantom Phase-1 bench (canned inputs; physics tests only, not piloted flights or missions).

Writes evidence/phantom/phantom_bench_results.json. Usage:
  PYTHONPATH=src python tools/phantom/phantom_bench.py [--variants phantom phantom-fx]
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
from vtx.phantom.geometry import PODS, SIDE, WING_SIDES

W = TestWorld()


def run(a, seconds):
    for _ in range(int(round(seconds / DT))):
        a.step()


def plant(variant, **kw):
    a = PhantomAircraft(W, variant, **kw); a.spawn(0, 0, W.surface_z(0, 0)); return a


def zero_power(variant):
    out = {}
    for start in ('vtol', 'road'):
        a = plant(variant, start_configuration=start, engines_running=False)
        z0 = a.data.qpos[2]; run(a, 8)
        att = a.attitude()
        out[start] = dict(dz_m=float(a.data.qpos[2] - z0), roll_deg=math.degrees(att['roll']), pitch_deg=math.degrees(att['pitch_up']),
                          speed_m_s=float(np.linalg.norm(a.data.qvel[:3])), support=a.support, crashed=a.crashed,
                          passed=bool(a.support_count() >= 4 and np.linalg.norm(a.data.qvel[:3]) < 0.05 and not a.crashed))
    return out


def freefall(variant):
    a = PhantomAircraft(W, variant, engines_running=False); a.spawn(0, 0, 60.0)
    a.data.qpos[2] = 80.0; v0 = 0.0
    import mujoco as mj
    mj.mj_forward(a.model, a.data)
    e0 = None; t0 = a.data.time; z0 = a.data.qpos[2]
    run(a, 1.0)
    acc = 2 * (a.data.qpos[2] - z0) / (a.data.time - t0) ** 2
    return dict(mean_vertical_accel_m_s2=float(acc), expected=-a.P['atmosphere.gravity_m_s2'], body_drag_included=True,
                passed=bool(abs(acc + 9.80665) < 0.15))


def joint_travel(variant):
    a = plant(variant); res = {}
    def time_to(name, target, tol, maxt, cmd):
        # tol covers position-servo droop under load (F/kp), reported separately as achieved value
        a.set_command(cmd); t0 = a.data.time
        while a.data.time - t0 < maxt:
            run(a, 0.05)
            if abs(a.joint(name)[0] - target) < tol:
                return float(a.data.time - t0)
        return None
    a.set_command(dict(pod_tilt_deg=[0.0] * 4)); run(a, 2.5)   # tyres down first, then the legs are unloaded
    res['legs_retract'] = dict(t_s=time_to('leg_FL', 0.0, 0.01, 6, dict(leg_extension_m=[0.0] * 4)), min_t_s=0.52 / a.P['contact.leg_rate_m_s'])
    res['legs_extend'] = dict(t_s=time_to('leg_FL', -0.52, 0.03, 6, dict(leg_extension_m=[0.52] * 4)), min_t_s=0.49 / a.P['contact.leg_rate_m_s'])
    run(a, 1.0); res['legs_extend']['achieved_m'] = float(-a.joint('leg_FL')[0]); res['legs_extend']['note'] = 'lifting the vehicle off its tyres; residual = servo droop under load'
    res['pods_to_fan'] = dict(t_s=time_to('pod_FL', math.pi / 2, 0.01, 6, dict(pod_tilt_deg=[90.0] * 4)), min_t_s=(math.pi / 2) / a.P['pods.tilt_rate_rad_s'])
    res['pods_to_road'] = dict(t_s=time_to('pod_FL', 0.0, 0.01, 6, dict(pod_tilt_deg=[0.0] * 4)), min_t_s=(math.pi / 2) / a.P['pods.tilt_rate_rad_s'])
    res['canards_deploy'] = dict(t_s=time_to('canard_left_fold', 0.0, 0.01, 6, dict(canard_fold='deployed')), min_t_s=(math.pi / 2) / math.radians(60))
    res['canard_pitch_max'] = dict(t_s=time_to('canard_left', math.radians(25), 0.01, 6, dict(canard_pitch_deg=[25, 25])), min_t_s=math.radians(25) / math.radians(40))
    res['canard_pitch_min'] = dict(t_s=time_to('canard_left', math.radians(-20), 0.01, 6, dict(canard_pitch_deg=[-20, -20])), min_t_s=math.radians(45) / math.radians(40))
    a.set_command(dict(canard_pitch_deg=[0, 0])); run(a, 1.5)
    t0 = a.data.time; a.set_command(dict(wing='deploy'))
    while a.data.time - t0 < 15 and a.wing_state['left'] != 'locked':
        run(a, 0.05)
    res['wing_deploy_sequence'] = dict(t_s=float(a.data.time - t0), state=dict(a.wing_state), lock_eq=a.data.eq_active.tolist(),
                                       min_t_s=1.0 + 1.37 / 0.30 + 0.5, slide_m=float(a.joint('wing_left')[0]))
    res['flap_full'] = dict(t_s=time_to('flap_left', math.radians(35), 0.01, 6, dict(flap_deg=[35, 35])), min_t_s=35 / 15)
    res['aileron_trim_max'] = dict(t_s=time_to('aileron_left', math.radians(20), 0.01, 6, dict(aileron_trim_deg=[20, -20])), min_t_s=20 / 80)
    a.set_command(dict(flap_deg=[0, 0], aileron_trim_deg=[0, 0])); run(a, 3)
    t0 = a.data.time; a.set_command(dict(wing='stow'))
    while a.data.time - t0 < 15 and a.wing_state['left'] != 'stowed':
        run(a, 0.05)
    res['wing_stow_sequence'] = dict(t_s=float(a.data.time - t0), state=dict(a.wing_state), min_t_s=0.5 + 1.37 / 0.30 + 1.0)
    for k, v in res.items():
        if 't_s' in v and 'min_t_s' in v:
            v['passed'] = bool(v['t_s'] is not None and v['t_s'] >= 0.95 * v['min_t_s'])
    return res


def thrust_and_gyro(variant):
    out = {}
    a = plant(variant)
    a.model.opt.gravity[:] = 0
    a.data.qpos[2] += 5
    a.set_command(dict(collective=0.3, stability_mode='off', brake=[0] * 4)); run(a, 2.0)
    a.set_command(dict(pod_tilt_deg=[60, 90, 90, 90])); run(a, 1.5)
    ax = a.pod_axis('FL'); F = None
    st = a.fan_state[0]
    tilt = abs(a.joint('pod_FL')[0])
    expect = np.array([0, math.cos(tilt), math.sin(tilt)])           # +Y outboard for FL
    out['thrust_direction'] = dict(pod='FL', tilt_deg=math.degrees(tilt), axis_world=ax.tolist(), expected=(a.R() @ expect).tolist(),
                                   thrust_n=st['thrust_n'], passed=bool(np.allclose(ax, a.R() @ expect, atol=1e-3) and st['thrust_n'] > 0))
    # gyro sign: spin one fan, tilt its pod, compare airframe angular acceleration with spin reversed
    res = []
    for sense in (1, -1):
        b = PhantomAircraft(W, variant, overrides={'pods': {'rotor_spin_sense': {'v': {'FL': sense, 'FR': 1, 'RL': 1, 'RR': 1}, 'u': '-', 'l': 'SYNTHETIC_UNVALIDATED', 's': 'bench'}}})
        b.spawn(0, 0, 50); b.model.opt.gravity[:] = 0
        fid = b.model.jnt_dofadr[b.jid['pod_FL_fan']]
        b.data.qvel[fid] = sense * 800.0
        b.set_command(dict(collective=0.0, pod_tilt_deg=[90, 90, 90, 90]))
        b.fcc.cmd['engine'] = 0.0
        run(b, 0.02)
        ax0 = b.pod_axis('FL').copy()
        b.set_command(dict(pod_tilt_deg=[30, 90, 90, 90])); w0 = b.rates_body().copy(); run(b, 0.3)
        ax1 = b.pod_axis('FL'); tilt_dir = np.cross(ax0, ax1); tilt_dir /= np.linalg.norm(tilt_dir)
        res.append((b.rates_body() - w0, b.R().T @ np.cross(tilt_dir, sense * ax0)))
    # The spin-antisymmetric part isolates the gyroscopic coupling from the (spin-independent) tilt reaction.
    # Rotor precession torque = w_tilt x H; the airframe receives the opposite.
    gyro = (res[0][0] - res[1][0]) / 2
    expect = -res[0][1]
    out['gyro_sign'] = dict(delta_body_rates_spin_pos=res[0][0].tolist(), delta_body_rates_spin_neg=res[1][0].tolist(), gyro_part_body=gyro.tolist(),
                            expected_direction_body=expect.tolist(),
                            passed=bool(float(gyro @ expect) > 0 and np.linalg.norm(gyro) > 1e-4))
    return out


def power_limited(variant):
    a = plant(variant, buffer_soc=0.11)
    a.set_command(dict(collective=1.0, stability_mode='rate_damping', brake=[0] * 4, engine=0.3)); run(a, 3)
    b = a.bus.last
    cmd = sum(a.alloc['thrust']); ach = sum(s.get('thrust_n', 0) for s in a.fan_state)
    return dict(engine_lever=0.3, soc_start=0.11, soc_end=a.bus.soc, demand_w=b['demand_w'], delivered_w=b['delivered_w'], unmet_w=b['unmet_w'],
                propulsion_scale=b['propulsion_scale'], thrust_cmd_n=cmd, thrust_achieved_n=ach, soc_never_below_min=bool(a.bus.soc >= a.P['buffer.soc_min'] - 1e-6),
                passed=bool(ach < 0.9 * cmd and b['unmet_w'] > 0 and a.bus.soc >= 0))


def mass_update(variant):
    a = plant(variant)
    m0 = a.mass_properties(); a.fuel[:] = [a.fuel[0] * 0.2, a.fuel[1] * 0.2]; a.apply_fuel_mass(force=True)
    import mujoco as mj
    mj.mj_forward(a.model, a.data); m1 = a.mass_properties()
    l0 = a.L.mass_properties(a.L.configuration(), fuel_kg=list(a.fuel_initial)); l1 = a.L.mass_properties(a.L.configuration(), fuel_kg=list(a.fuel))
    b = PhantomAircraft(W, variant, occupants=1); b.spawn(0, 0, 0)
    return dict(mass_full=m0['mass_kg'], mass_burned=m1['mass_kg'], cg_full=m0['cg_body_m'], cg_burned=m1['cg_body_m'],
                Izz_full=m0['inertia_body_kg_m2'][2][2], Izz_burned=m1['inertia_body_kg_m2'][2][2], ledger_mass_burned=l1['mass_kg'],
                one_occupant_mass=b.mass_properties()['mass_kg'], one_occupant_cg_y=b.mass_properties()['cg_body_m'][1],
                passed=bool(abs(m1['mass_kg'] - l1['mass_kg']) < 1e-4 and m1['mass_kg'] < m0['mass_kg']))


def contact_jumps(variant):
    a = plant(variant); prev = a.data.qpos[:3].copy(); jump = 0.0
    a.set_command(dict(pod_tilt_deg=[0.0] * 4)); run(a, 2.5)          # pods to road (tyres below hull) before retracting the legs
    prev = a.data.qpos[:3].copy(); a.set_command(dict(leg_extension_m=[0.0] * 4))
    for _ in range(int(3 / DT)):
        a.step(); jump = max(jump, float(np.linalg.norm(a.data.qpos[:3] - prev))); prev = a.data.qpos[:3].copy()
    a.set_command(dict(brake=[0.0] * 4, wheel_drive=[0.3] * 4))
    for _ in range(int(3 / DT)):
        a.step(); jump = max(jump, float(np.linalg.norm(a.data.qpos[:3] - prev))); prev = a.data.qpos[:3].copy()
    v_roll = float(a.vel_body()[0])
    a.set_command(dict(brake=[1.0] * 4, wheel_drive=[0.0] * 4)); run(a, 3)
    return dict(max_step_displacement_m=jump, speed_bound_per_step_m=40 * DT, rolling_speed_m_s=v_roll, after_brake_speed_m_s=float(np.linalg.norm(a.data.qvel[:3])),
                support_after=a.support, crashed=a.crashed, passed=bool(jump < 0.02 and not a.crashed))


def hover(variant, load_state=None, seconds=10.0):
    a = plant(variant, load_state=load_state)
    W_n = float(sum(a.model.body_mass)) * a.P['atmosphere.gravity_m_s2']
    z0 = a.data.qpos[2]
    a.set_command(dict(stability_mode='attitude_vs', collective=0.6, vertical_speed_m_s=1.0, brake=[0] * 4))
    run(a, seconds)
    f = a.fan; mp = a.L.mass_properties(None, fuel_kg=list(a.fuel))
    xf, xr = a.P['pods.hinge_x_front_m'], a.P['pods.hinge_x_rear_m']
    share = (mp['cg_m'][0] - xr) / (xf - xr)
    worst = max(share, 1 - share) / 2
    b = a.bus.last
    return dict(variant=variant, load_state=load_state, mass_kg=W_n / 9.80665, cg_x_m=mp['cg_m'][0], height_gain_m=float(a.data.qpos[2] - z0), vz_m_s=float(a.data.qvel[2]),
                left_ground=bool(a.data.qpos[2] - z0 > 0.5), thrust_max_per_pod_n=f.thrust_max, collective_margin=4 * f.thrust_max / W_n - 1,
                worst_pod_margin=f.thrust_max / (worst * W_n) - 1, generator_w=b['generator_w'], buffer_w=b['buffer_w'], unmet_w=b['unmet_w'],
                soc=a.bus.soc, saturated=a.fcc.last.get('saturated'), roll_deg=math.degrees(a.attitude()['roll']), pitch_deg=math.degrees(a.attitude()['pitch_up']),
                crashed=a.crashed, energy_balance_residual_j=a.bus.energy['residual_j'], fuel_used_kg=float(a.fuel_initial.sum() - a.fuel.sum()))


def allocator_ceiling(variant, load_state=None, seconds=3.0):
    """Thrust the FBW allocator actually delivers at full collective, as a fraction of weight.

    `collective_margin` in hover() is the ideal 4*T_max/W - 1. It ignores the CG pod share, the
    attitude-priority desaturation and the motor/generator power limits, so it overstated the
    as-drawn aircraft (flight campaign D-9: bench 0.79 W against a live ceiling of 0.53 W)."""
    a = plant(variant, load_state=load_state)
    W_n = float(sum(a.model.body_mass)) * a.P['atmosphere.gravity_m_s2']
    a.set_command(dict(stability_mode='attitude', collective=1.0, brake=[0] * 4))
    peak = 0.0; per_pod = [0.0] * 4
    for _ in range(int(round(seconds / DT))):
        a.step()
        T = [s.get('thrust_n', 0.0) * abs(float(a.pod_axis(k)[2])) for k, s in zip(PODS, a.fan_state)]
        if sum(T) > peak:
            peak = sum(T); per_pod = T
    return dict(variant=variant, load_state=load_state, delivered_peak_w=peak / W_n, ideal_w=4 * a.fan.thrust_max / W_n,
                per_pod_n=per_pod, left_ground=bool(not a.support), power_limited=bool(a.prop_scale < 0.999))


def energy_residual(variant):
    a = plant(variant)
    a.set_command(dict(collective=0.4, stability_mode='rate_damping', brake=[0] * 4)); run(a, 3)
    E = a.bus.energy
    return dict(bus_residual_j=E['residual_j'], generator_j=E['generator_j'], buffer_out_j=E['buffer_out_j'], buffer_in_j=E['buffer_in_j'], unmet_j=E['unmet_j'],
                passed=bool(abs(E['residual_j']) < 1e-3 * max(1.0, E['generator_j'])))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--variants', nargs='+', default=['phantom', 'phantom-fx']); a = ap.parse_args()
    t = time.time(); out = dict(schema='phantom-bench-1', note='Canned-input physics benches; not missions or piloted flights.', results={})
    for v in a.variants:
        r = out['results'][v] = {}
        for name, fn in [('zero_power_on_gear', zero_power), ('fixture_freefall', freefall), ('joint_travel', joint_travel), ('thrust_and_gyro', thrust_and_gyro),
                         ('power_limited_thrust', power_limited), ('mass_update', mass_update), ('contact_no_pose_jumps', contact_jumps), ('energy_residual', energy_residual)]:
            r[name] = fn(v); print(v, name, 'done', round(time.time() - t, 1), flush=True)
        r['hover'] = [hover(v)] + ([hover(v, 'FX-C'), hover(v, 'FX-A')] if v == 'phantom-fx' else [])
        r['allocator_ceiling'] = allocator_ceiling(v)
    out['wall_s'] = time.time() - t
    (ROOT / 'evidence/phantom/phantom_bench_results.json').write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({v: {k: (x.get('passed') if isinstance(x, dict) and 'passed' in x else '...') for k, x in r.items()} for v, r in out['results'].items()}, indent=1))


if __name__ == '__main__':
    main()
