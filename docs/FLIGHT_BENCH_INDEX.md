# Phantom A10 plant bench runs

These are flat-strip MuJoCo plant test cases with canned pilot schedules, distinct from timestamped live cockpit sorties. Full source data remains in the local repository checkout. None establishes a controlled landing or aircraft qualification.

## Baseline take-off series

| Run | Technique | Wheels off (m/s) | Max height (m) | Crash flag |
| --- | --- | ---: | ---: | --- |
| `takeoff:takeoff_r50` | raw pitch 1.0, rate-damping, rotate 50 m/s | 74.37 | — | true |
| `takeoff:takeoff` | raw pitch 1.0, rate-damping, rotate 60 m/s | 69.28 | — | true |
| `takeoff:takeoff_r70` | raw pitch 1.0, rate-damping, rotate 70 m/s | 79.05 | — | true |
| `takeoff_att:to_att55` | attitude 9 deg, rotate 55, Kp1.2/Kd0.25, canard trim 10 | 89.54 | 17.56 | true |
| `takeoff_att:to_att60` | attitude 9 deg, rotate 60, Kp1.2/Kd0.25, canard trim 10 | — | — | false |
| `takeoff_att:to_att65` | attitude 9 deg, rotate 65, Kp1.2/Kd0.25, canard trim 10 | — | — | false |
| `gain_kp3_kd0.6:to_att60` | attitude 9 deg, rotate 60, Kp3/Kd0.6, canard trim 10 | 90.65 | 32.44 | false |
| `gain_kp5_kd1.0:to_att60` | attitude 9 deg, rotate 60, Kp5/Kd1.0, canard trim 10 | — | — | false |
| `gain_kp8_kd1.6:to_att60` | attitude 9 deg, rotate 60, Kp8/Kd1.6, canard trim 10 | 84.87 | 20.79 | true |
| `climb_fbw:climb` | P-T1a: attitude 10 deg @70, Kp3/Kd0.8, trim 0 | 103.02 | 6.16 | true |
| `climb_pt1:climb` | P-T1: as P-T1a + larger EDF boosters (SYNTHETIC) | 106.37 | 5.98 | true |

[Full baseline series](../evidence/phantom/a10_takeoff_series_20261104.json).

## P6/P7/P8 and control-gain series

| Run | Configuration | Wheels off (m/s) | Max height (m) | Crash flag |
| --- | --- | ---: | ---: | --- |
| `p6_edf` | P6 + EDF boosters | 118.71 | 4.57 | false |
| `p6_fj33` | P6 + FJ33-5A | 89.43 | 0.01 | false |
| `p6_fj33_kp3` | P6 + FJ33-5A, Kp3/Kd0.8 | 125.12 | 11.54 | true |
| `p6_tj150` | P6 + 4x TJ150 | 111.48 | 0.01 | false |
| `p6_tj150_kp3` | P6 + 4x TJ150, Kp3/Kd0.8 | 116.79 | 0.04 | false |
| `p8_7_fj33` | P6+P7 FJ33+P8 7 deg | 67.57 | 19.52 | true |
| `p8_7_tj150` | P6+P7 TJ150+P8 7 deg | 83.61 | 0.01 | false |
| `p8_9_fj33` | P6+P7 FJ33+P8 9 deg | 59.84 | 19.31 | true |
| `p8_9_tj150` | P6+P7 TJ150+P8 9 deg | 64.84 | 0.87 | true |
| `sw_e1_kp0.6_kd0.5` | sweep P6+P8 7 deg + 4x TJ150, Kp 0.6 / Kd 0.5 | 94.89 | 5.81 | true |
| `sw_e1_kp0.6_kd1.0` | sweep P6+P8 7 deg + 4x TJ150, Kp 0.6 / Kd 1.0 | 70.75 | 21.11 | true |
| `sw_e1_kp1.2_kd1.0` | sweep P6+P8 7 deg + 4x TJ150, Kp 1.2 / Kd 1.0 | 94.39 | 11.70 | true |
| `sw_e1_kp2.0_kd1.2` | sweep P6+P8 7 deg + 4x TJ150, Kp 2.0 / Kd 1.2 | 85.53 | 23.36 | true |
| `sw_e2_kp0.6_kd0.5` | sweep P6+P8 7 deg + FJ33-5A, Kp 0.6 / Kd 0.5 | 69.40 | 20.44 | true |
| `sw_e2_kp0.6_kd1.0` | sweep P6+P8 7 deg + FJ33-5A, Kp 0.6 / Kd 1.0 | 93.82 | 10.73 | true |
| `sw_e2_kp1.2_kd1.0` | sweep P6+P8 7 deg + FJ33-5A, Kp 1.2 / Kd 1.0 | 86.27 | 0.33 | true |
| `sw_e2_kp2.0_kd1.2` | sweep P6+P8 7 deg + FJ33-5A, Kp 2.0 / Kd 1.2 | 86.17 | 2.34 | true |

[Full proposal series](../evidence/phantom/a10_p6_p7_p8_series_20261104.json). A `crashed: false` flag does not mean a successful flight; some runs bounced or reached the end of the strip. See the [analysis](phantom/A10_FIRST_FLIGHTS_20261104.md).
