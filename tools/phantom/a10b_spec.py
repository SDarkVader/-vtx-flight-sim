"""Phantom A10-B model characteristics, computed from the canonical variant (phantom-a10b) so the spec cannot drift
from the model. Writes evidence/phantom/a10b_characteristics.json and prints a summary.

  PYTHONPATH=src python tools/phantom/a10b_spec.py
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from vtx.phantom.params import Params                                    # noqa: E402
from vtx.phantom.plant import PhantomAircraft, suspension_design, steering_design   # noqa: E402
from vtx.phantom.propulsion import DuctedFan                             # noqa: E402
from vtx.phantom.surface_aero import SurfaceAero                         # noqa: E402
from vtx.world import TestWorld                                          # noqa: E402

OUT = ROOT / 'evidence/phantom/a10b_characteristics.json'
RHO, G = 1.225, 9.80665


def static_derivatives(P, cg, V):
    SA = SurfaceAero(P); w = P.handover['aero_surfaces']['wing']; q = 0.5 * RHO * V * V
    st = dict(wing_frac=dict(left=1., right=1.), wing_locked=dict(left=True, right=True), flap=dict(left=0., right=0.),
              aileron=dict(left=0., right=0.), canard_pitch=dict(left=0., right=0.), canard_deployed=dict(left=True, right=True),
              stab_te_up=math.radians(P['proposals.p6_stab_rest_te_up_deg']))
    def mom(al, be, **kw):
        s = dict(st, **kw); a_, b_ = math.radians(al), math.radians(be)
        v = V * np.array([math.cos(a_) * math.cos(b_), math.sin(b_), -math.sin(a_) * math.cos(b_)])
        r = SA.compute(v, np.zeros(3), np.zeros(3), s)
        M = r['moment_body'] - np.cross(cg, r['force_body'])
        return -M[1], M[2], r['force_body']
    cma = (mom(4, 0)[0] - mom(0, 0)[0]) / math.radians(4) / (q * w['S_ref_m2'] * w['mac_m'])
    cnb = (mom(2, 2)[1] - mom(2, -2)[1]) / math.radians(4) / (q * w['S_ref_m2'] * w['span_m'])
    pitch = {al: round(mom(al, 0)[0]) for al in (-4, 0, 4, 8, 12)}
    lift = {al: round(mom(al, 0)[2][2]) for al in (0, 4, 8)}
    return dict(V_m_s=V, q_pa=round(q), Cm_alpha_per_rad=round(cma, 3), Cn_beta_per_rad=round(cnb, 4),
                pitch_moment_free_Nm_vs_body_alpha_deg=pitch, aero_lift_N_vs_body_alpha_deg=lift)


def main():
    P = Params('phantom-a10b')
    a = PhantomAircraft(TestWorld(), 'phantom-a10b', start_configuration='road')
    mp = a.mass_properties(); cg = np.array(mp['cg_body_m']); M = mp['mass_kg']
    fan = DuctedFan.pod(P); boo = DuctedFan.booster(P); H = P.handover['aero_surfaces']; hl = P.handover['control_limits']
    w = H['wing']
    inert = a.L.body_inertials()
    spec = dict(
        variant='phantom-a10b', config_sha256=P.config_sha256, parameter_file_sha256=P.file_sha256,
        release_stage=P.variant_info['release_stage'], description=P.variant_info['description'],
        inherits='phantom-fx (A10-A geometry and powertrain)', overlays=P.variant_info.get('overlay_files'),
        mass=dict(mass_kg=round(M, 2), cg_body_m=[round(x, 4) for x in cg], inertia_body_kg_m2=[[round(v, 1) for v in r] for r in mp['inertia_body_kg_m2']],
                  added_components=[dict(id=c['id'], mass_kg=c['mass_kg'], label=c['label']) for c in (P.get('effectors.added_components') or [])]),
        geometry=dict(length_m=4.89, max_body_width_m=2.50, wheelbase_m=round(abs(a.L.bodies['pod_FL_wheel'].anchor[0] - a.L.bodies['pod_RL_wheel'].anchor[0]), 3),
                      track_m=round(2 * a.L.bodies['pod_FL_wheel'].anchor[1], 3), tyre_radius_m=P['pods.tyre_radius_m'],
                      wing=dict(S_ref_m2=w['S_ref_m2'], span_m=w['span_m'], mac_m=w['mac_m'], aspect_ratio=round(w['span_m'] ** 2 / w['S_ref_m2'], 2),
                                x_ac_m=w['x_ac_mac_m'], incidence_deg=P['proposals.p8_wing_incidence_deg'], CLalpha_per_rad=w['CLalpha_per_rad_M0'],
                                CLmax_clean=w['CLmax_clean'], CLmax_flap=w['CLmax_flap'], wing_loading_pa=round(M * G / w['S_ref_m2'])),
                      canards=dict(area_each_m2=H['canard']['area_each_m2'], x_m=H['canard']['x_pivot_m'], travel_deg=hl['canard_pitch']['travel_deg']),
                      stabilator=dict(area_m2=P['proposals.p6_stab_area_m2'], x_m=P['proposals.p6_stab_position_m'][0], travel_deg=P['proposals.p6_stab_travel_deg']),
                      fins=dict(area_each_m2=P['aero.fin_area_each_m2'], x_m=P['aero.fin_position_m'][0], rudder_tau=P['effectors.rudder.tau'],
                                rudder_travel_deg=P['effectors.rudder.travel_deg']),
                      hull_lift=dict(k_pitch_m2=P['aero.hull_lift.k_pitch_m2'], x_cp_pitch_m=P['aero.hull_lift.x_cp_pitch_m'],
                                     k_yaw_m2=P['aero.hull_lift.k_yaw_m2'], x_cp_yaw_m=P['aero.hull_lift.x_cp_yaw_m'])),
        aero=dict(at_60=static_derivatives(P, cg, 60.0), at_95=static_derivatives(P, cg, 95.0)),
        propulsion=dict(lift_fans=dict(count=4, thrust_max_each_n=round(fan.thrust_max), disk_area_each_m2=round(fan.area_m2, 3),
                                       thrust_to_weight=round(4 * fan.thrust_max / (M * G), 3), rotor_inertia_kg_m2=P['pods.rotor_inertia_kg_m2']),
                        boosters=dict(count=2, kind='EDF', static_thrust_each_n=round(boo.state(boo.omega_max, 0, 0, None, 0)['thrust_n']),
                                      thrust_each_at_95_m_s_n=round(boo.state(boo.omega_max, 95, 0, None, 0)['thrust_n']),
                                      tvc_travel_deg=P['effectors.tvc.travel_deg'], tvc_rate_deg_s=P['effectors.tvc.rate_deg_s']),
                        wheel_drive=dict(torque_each_nm=P['pods.hub_motor_torque_nm'], power_each_w=P['pods.hub_motor_power_w'],
                                         traction_slip_max=P['drive.traction_slip_max'])),
        power=dict(generator_continuous_w=P['generators.power_each_w'] * P['generators.count'], generator_takeoff_w=P['generators.takeoff_power_each_w'],
                   takeoff_rating_s=P['generators.takeoff_time_s'], buffer_energy_kwh=round(P['buffer.energy_j'] / 3.6e6, 1),
                   buffer_position_m=P['buffer.position_m']),
        chassis=dict(suspension=suspension_design(P, a.L, inert), steering=steering_design(P),
                     steering_schedule=dict(max_deg=P['effectors.steering.max_deg'], rate_deg_s=P['effectors.steering.rate_deg_s'],
                                            lat_accel_max_g=P['effectors.steering.lat_accel_max_g'])),
        flight_control=dict(wingborne=dict(q_blend_pa=P['fbw_wingborne.q_blend_pa'], attitude_gain=P['fbw_wingborne.attitude_gain'],
                                           rate_gain_s=P['fbw_wingborne.rate_gain_s'], beta_gain_per_rad=P['fbw_wingborne.beta_gain_per_rad'],
                                           bank_max_deg=P['fbw_wingborne.bank_max_deg']),
                            actuator_rates_deg_s=dict(canard=P['effectors.canard_rate_deg_s'], stabilator=P['proposals.p6_stab_rate_deg_s'],
                                                      rudder=P['effectors.rudder.rate_deg_s'], tvc=P['effectors.tvc.rate_deg_s'])),
        wing_deployment=dict(sequence_s=round(180 / hl['hatch']['rate_deg_s'] + hl['wing_slide']['stroke_m'] / hl['wing_slide']['max_speed_m_s'] + hl['locks']['engage_time_s'], 2),
                             transit_q_limit_pa=hl['wing_slide']['transit_q_limit_Pa'],
                             transit_speed_limit_m_s=round(math.sqrt(2 * hl['wing_slide']['transit_q_limit_Pa'] / RHO), 1),
                             guard='refuse to start if the predicted speed at lock exceeds the limit; close the hatch if blocked; flag transit exceedance'))
    OUT.write_text(json.dumps(spec, indent=1, default=float))
    print(json.dumps({k: spec[k] for k in ('variant', 'config_sha256', 'mass', 'aero')}, indent=1, default=float))


if __name__ == '__main__':
    main()
