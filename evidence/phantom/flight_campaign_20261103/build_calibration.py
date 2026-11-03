"""Builds evidence/phantom/phantom_calibration_20261103.json from the campaign analysis files (run from repo root)."""
import json
C = 'evidence/phantom/flight_campaign_20261103/'
A = {r: json.load(open(C + f'analysis_{r}.json')) for r in ['20261103T194858-35a724', '20261103T192918-14ade4', '20261103T190252-3ef734', '20261103T144853-5e8e48']}
M = 'MEASURED_SIM'; D = 'DERIVED'
K = ('height_m', 'mass_kg', 'collective_applied', 'T_over_W', 'front_share', 'elec_power_kw', 'W_per_N', 'P_over_T15', 'soc_rate_per_s', 'roll_deg', 'pitch_deg')
pick = lambda t: {k: t[k] for k in K}
out = dict(
    schema='phantom-calibration-20261103-1', date='2026-11-03',
    label_key={M: 'read from the simulator run logs (phantom_steps.csv.gz 100 Hz FBW/plant channels, events.jsonl); simulator output, not aircraft data',
               D: 'computed by the test pilot from MEASURED_SIM values with the stated formula or assumption'},
    caveat='All values come from a SYNTHETIC_UNVALIDATED model (inputs/phantom_parameters_v1.json). They are not validated aircraft performance.',
    server=dict(host='127.0.0.1:8766', data_root=C, time_scale_used=[0.25, 0.1]),
    runs={'20261103T144211-55c7ac': 'phantom G-3 attempt voided: the operator-panel heartbeat overrode the collective, and the legacy 10 kg fuel default applied',
          '20261103T144550-be8193': 'phantom (as drawn, 110 kg fuel): G-2/G-3 and 2 lift-off attempts; no lift-off',
          '20261103T144853-5e8e48': 'phantom-fx FX-C: G-2/G-3/G-4, H-1 #1',
          '20261103T145427-98fc81': 'phantom-fx FX-C: H-1 #2, H-2 at 1.4/3 m, then an UNPLANNED X-1 lease-expiry crash from 3.1 m',
          '20261103T190252-3ef734': 'phantom-fx FX-C: O-1, O-2, O-3 PTIs, L-1 (1.6/3.1/4.8 m/s forward, 2.2 m/s aft), landing',
          '20261103T192918-14ade4': 'phantom-fx FX-C: T-2X hop 200 m east; landed at B',
          '20261103T194858-35a724': 'phantom-fx FX-A: H-1, O-2, part of O-3, X-5 rungs'},
    ground_thrust_calibration_G3={
        'phantom': dict(label=M, run='20261103T144550-be8193', mass_kg=1897,
                        steps=[dict(collective=0.2, thrust_n=[422, 423, 1111, 1111], T_over_W=0.165, elec_kw=256),
                               dict(collective=0.4, thrust_n=[812, 812, 2143, 2142], T_over_W=0.318, elec_kw=612),
                               dict(collective=0.6, thrust_n=[1208, 1207, 3202, 3206], T_over_W=0.474, elec_kw=1088),
                               dict(collective=0.8, thrust_n=[1385, 1386, 3531, 3533], T_over_W=0.529, elec_kw=1254, saturated=True),
                               dict(collective=1.0, thrust_n=[1384, 1384, 3533, 3532], T_over_W=0.529, elec_kw=1253, saturated=True),
                               dict(mode='attitude_vs VS +0.5', T_over_W=0.525, elec_kw=1245, saturated=True)],
                        max_T_over_W=0.529,
                        limit='The rear pods top out at about 3530 N (8480 rpm) with the generators at their 1.2 MW cap. Attitude-priority desaturation then scales the front pods down to hold the pitch moment, so total thrust plateaus at 53% of weight.',
                        note_vs_bench='The bench (phantom_bench_results.json) reports a collective margin of -0.208 (0.79 W). The live G-3 ceiling is 0.53 W. Logged as defect D-9.'),
        'phantom-fx FX-C': dict(label=M, run='20261103T144853-5e8e48', mass_kg=1734,
                                steps=[dict(collective=c, T_over_W=t, elec_kw=p) for c, t, p in [(0.1, 0.167, 119), (0.2, 0.316, 244), (0.3, 0.465, 403), (0.4, 0.616, 588), (0.5, 0.771, 808), (0.6, 0.925, 1055)]],
                                thrust_per_collective_over_W=dict(v=1.54, label=D, formula='slope of T/W against collective'),
                                front_share=dict(v=0.458, label=M))},
    hover_trim_table=[dict(variant='phantom-fx', load='FX-C', condition='IGE 1.9 m', label=M, **pick(A['20261103T144853-5e8e48']['trim_points'][0]))]
    + [dict(variant='phantom-fx', load='FX-C', condition='OGE', label=M, **pick(t)) for t in A['20261103T190252-3ef734']['trim_points'][:6]]
    + [dict(variant='phantom-fx', load='FX-A', condition='OGE 5.6 m', label=M, **pick(A['20261103T194858-35a724']['trim_points'][0])),
       dict(variant='phantom-fx', load='FX-C', condition='cruise 4.8 m/s at 18 m (hop)', label=M, **pick(A['20261103T192918-14ade4']['trim_points'][0]))],
    pilot_trim_stick=dict(label=M,
                          fxC_roll_stick_for_wings_level=dict(v=-0.13, range=[-0.12, -0.16], note='The attitude loop is proportional only. With one occupant the lateral CG is at y -0.014 m, which leaves about 2 deg of right bank with zero stick.'),
                          fxA_roll_stick=0.0, pitch_trim_stick_hover=0.0,
                          per_pod_split=dict(front_share_FX_C=0.458, front_share_FX_A=0.460, phantom_as_drawn_required_front=0.27,
                                             note='phantom-fx splits thrust 0.46/0.54 front/rear, matching the ledger CG at -0.15 m. As drawn, the rear pods would need 0.73 of the thrust, and they saturate.')),
    control_response_identified=dict(label=M,
                                     note='attitude_vs (M2). Commanded attitude is stick x 15 deg for roll and stick x 10 deg for pitch. Delay is the first time the on-axis rate exceeds 10% of its peak. Produced by analyse.py.',
                                     fxC=A['20261103T190252-3ef734']['pti'], fxA=A['20261103T194858-35a724']['pti'], on_gear_G4_fxC=A['20261103T144853-5e8e48']['pti'],
                                     summary=dict(label=D,
                                                  roll=dict(peak_accel_deg_s2='20-35', peak_rate_3deg_doublet_deg_s=15.6, doublet_attitude_overshoot_ratio=2.2, step_time_constant_s=0.50, step_steady_error_frac=0.04, delay_s='0.07-0.12', off_axis_ratio='0.18-0.43'),
                                                  pitch=dict(peak_accel_deg_s2='6-12', peak_rate_3deg_doublet_deg_s=8.0, doublet_attitude_overshoot_ratio=1.7, step_time_constant_s='0.96-1.08', step_peak_over_command='1.66 (3 deg) / 1.71 (5 deg)', step_steady_over_command='1.10 / 1.18', delay_s='0.10-0.15', off_axis_ratio='0.01-0.15'),
                                                  yaw=dict(commanded_rate_deg_s=8, achieved_peak_rate_deg_s=4.0, ratio=0.50, delay_s=0.17, note='Yaw authority is about half the command. Heading creeps 0.3-1 deg/s with zero pedal, because there is no heading hold.'),
                                                  heave=dict(commanded_m_s=0.51, achieved_m_s=0.57, delay_s=0.14),
                                                  damping_note='Doublet responses overshoot 1.7-2.2x. A sustained pitch oscillation of +/-3 to 8 deg (q up to +/-10 deg/s, period about 2-3 s) appeared after pitch inputs in translation (L-1 rearward, hop deceleration) with no PTI active.',
                                                  fbw_transport_delay_s=dict(v=0.02, label='parameter fbw.transport_delay_s'))),
    power_vs_thrust=dict(label=D, formula='P_elec / T^1.5 from trim points (W per N^1.5)',
                         fxC_OGE=0.547, fxA_OGE=0.560, fxC_IGE_1p9m=0.561, fxC_cruise_4p8_m_s=0.522,
                         on_gear_fxC_W_per_N=[41.7, 45.4, 50.9, 56.1, 61.7, 67.1],
                         hover_W_per_N=dict(fxC=71.3, fxA=76.1, phantom_as_drawn_at_0p53W=127.4),
                         ground_effect=dict(gef_FL_at_1p9m=1.0019, label=M, note='No useful IGE benefit at the heights flown: the fans sit high and ground effect is capped.')),
    low_speed_L1_fxC=dict(label=M, points=[dict(speed_m_s=1.6, pitch_deg=-1.6), dict(speed_m_s=3.1, pitch_deg=-3.6), dict(speed_m_s=4.8, pitch_deg=-4.0, elec_kw=1154),
                                           dict(speed_m_s=-2.2, pitch_deg='+2 commanded; actual oscillated +6.6/-1.6')],
                          derived=dict(label=D, trim_pitch_deg_per_m_s=-1.0, note='Ram drag dominates at low speed. Electrical power falls about 5% from hover to 4.8 m/s.')),
    energy_and_endurance=dict(
        buffer=dict(energy_j=288e6, soc_initial=0.9, soc_min=0.1, continuous_w=311 * 2572, peak_w=311 * 3858, label='parameter'),
        hover_buffer_draw_kw=dict(fxC=310, fxA=470, label=M),
        predicted_OGE_hover_endurance_s=dict(fxC=517, fxA=397, label=D,
                                             formula='Buffer from SOC 0.9 to 0.1 (288 MJ x 0.8). 300 s at the 900 kW take-off rating, then 600 kW continuous. FX-A post-rating draw of 807 kW exceeds the 800 kW continuous buffer limit.'),
        hop_T2X=dict(label=M, sim_s=116.2, propulsion_j=131477287, generator_j=101666368, buffer_out_j=32787623, fuel_kg=10.17, soc=[0.90, 0.78], energy_residual_j=0.0)),
    variant_comparison=dict(
        phantom=dict(lift_off=False, max_T_over_W=0.529, label=M),
        fxC=dict(lift_off=True, hover_collective=0.648, hover_kw=1210, front_share=0.458, roll_trim_stick=-0.13, endurance_s_pred=517),
        fxA=dict(lift_off=True, hover_collective=0.706, hover_kw=1407, front_share=0.460, roll_trim_stick=0.0, endurance_s_pred=397)),
    pilot_loop=dict(label=M, note='sim seconds between deliberate pilot decisions; keep-alive holds every ~0.1 s sim',
                    fxC_O_L_sortie=dict(p50=7.55, p95=10.37), hop=dict(p50=5.75, p95=16.65), fxA=dict(p50=6.05, p95=12.95), keepalive_p95=0.107),
    touchdowns=dict(label=M, events=[dict(run='20261103T145427-98fc81', sink_m_s=7.14, outcome='collision, 863 kN peak contact (lease expiry from 3.1 m)'),
                                     dict(run='20261103T144853-5e8e48', sink_m_s=0.25),
                                     dict(run='20261103T190252-3ef734', sink_m_s=0.35),
                                     dict(run='20261103T192918-14ade4', sink_m_s=0.40, outcome='landed at B, 1.4 m from the point'),
                                     dict(run='20261103T194858-35a724', sink_m_s=[0.47, 1.75, 2.91], max_contact_n=17286, bounce_up_m_s=1.04)]),
)
json.dump(out, open('evidence/phantom/phantom_calibration_20261103.json', 'w'), indent=1)
print('ok')
