// Node test for the deterministic voice grammar (run: node tests/js/voice_pilot.test.mjs)
import assert from 'node:assert/strict';
import { normalise, parseUtterance, statusReadback } from '../../public/voice-pilot.js';

const P = (t) => parseUtterance(t);
const near = (a, b, e = 1e-3) => assert.ok(Math.abs(a - b) < e, `${a} != ${b}`);

assert.equal(normalise('Boost fifty percent').trim(), 'boost 50 percent');
assert.equal(normalise('flaps one hundred and five').trim(), 'flaps 105');
assert.equal(normalise('canards minus six').trim(), 'canards -6');
assert.equal(normalise('climb one point five').trim(), 'climb 1.5');
assert.equal(normalise('boost 75%').trim(), 'boost 75 percent');

// boosters: spoken value is thrust; throttle = sqrt(thrust fraction)
let r = P('boost fifty percent'); assert.equal(r.intent, 'boost'); near(r.patch.booster_throttle[0], Math.sqrt(0.5));
r = P('full boost'); assert.deepEqual(r.patch.booster_throttle, [1, 1]);
r = P('boosters off'); assert.deepEqual(r.patch.booster_throttle, [0, 0]);
r = P('cut the boost'); assert.deepEqual(r.patch.booster_throttle, [0, 0]);

r = P('brakes off'); assert.deepEqual(r.patch.brake, [0, 0, 0, 0]);
r = P('stop'); assert.deepEqual(r.patch.brake, [1, 1, 1, 1]); assert.deepEqual(r.patch.wheel_drive, [0, 0, 0, 0]);
r = P('drive eighty percent'); assert.deepEqual(r.patch.wheel_drive, [0.8, 0.8, 0.8, 0.8]); assert.deepEqual(r.patch.brake, [0, 0, 0, 0]);
r = P('reverse twenty'); assert.deepEqual(r.patch.wheel_drive, [-0.2, -0.2, -0.2, -0.2]);

r = P('take off configuration'); assert.equal(r.intent, 'takeoff_config'); assert.equal(r.patch.wing, 'deploy'); assert.deepEqual(r.patch.flap_deg, [30, 30]);
r = P('deploy the wings'); assert.equal(r.patch.wing, 'deploy'); assert.ok(!r.risky);
r = P('stow wings'); assert.equal(r.patch.wing, 'stow'); assert.ok(r.risky);
r = P('flaps thirty'); assert.deepEqual(r.patch.flap_deg, [30, 30]);
r = P('flaps up'); assert.deepEqual(r.patch.flap_deg, [0, 0]);
r = P('flaps fifty'); assert.deepEqual(r.patch.flap_deg, [35, 35]);            // clamped to travel

r = P('downforce'); assert.deepEqual(r.patch.canard_pitch_deg, [-6, -6]); assert.equal(r.patch.canard_fold, 'deployed');
r = P('max downforce'); assert.deepEqual(r.patch.canard_pitch_deg, [-10, -10]);
r = P('canards minus eight'); assert.deepEqual(r.patch.canard_pitch_deg, [-8, -8]);
r = P('fold the canards'); assert.equal(r.patch.canard_fold, 'folded'); assert.ok(r.risky);

r = P('nose up eight'); assert.equal(r.patch.stability_mode, 'attitude'); near(r.patch.pitch, 0.8);
r = P('nose down three degrees'); near(r.patch.pitch, -0.3);
r = P('climb two'); assert.equal(r.patch.stability_mode, 'attitude_vs'); assert.equal(r.patch.vertical_speed_m_s, 2);
r = P('climb nine'); assert.equal(r.patch.vertical_speed_m_s, 3);            // clamped to the FBW limit
r = P('descend one point five'); assert.equal(r.patch.vertical_speed_m_s, -1.5);
r = P('hold altitude'); assert.equal(r.patch.vertical_speed_m_s, 0);

r = P('retract the legs'); assert.ok(r.risky); assert.deepEqual(r.patch.leg_extension_m, [0, 0, 0, 0]);
r = P('road mode'); assert.ok(r.risky); assert.deepEqual(r.patch.pod_tilt_deg, [0, 0, 0, 0]);
r = P('engine off'); assert.ok(r.risky); assert.equal(r.patch.engine, 0);
r = P('stability off'); assert.ok(r.risky);

assert.equal(P('confirm').intent, 'confirm');
assert.equal(P('cancel').intent, 'cancel');
assert.equal(P('status report').intent, 'status');
assert.equal(P('make me a sandwich').intent, 'unknown');

const say = statusReadback({ observation: { airspeed_m_s: 50, radar_altimeter_m: 12.34, weight_on_wheels: false, buffer_soc: 0.81, warning_lamps: ['POWER_LIMITED'] } });
assert.match(say, /airspeed 50 metres per second, 112 miles per hour/); assert.match(say, /airborne/); assert.match(say, /power limited/);
console.log('voice pilot grammar: all assertions passed');
