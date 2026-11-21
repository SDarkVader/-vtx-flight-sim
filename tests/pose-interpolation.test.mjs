import test from 'node:test';
import assert from 'node:assert/strict';
import { createPoseInterpolator, slerp } from '../public/vtx-env/pose-interpolation.js';

const half = Math.SQRT1_2;
const clock = { r1: 0, r2: 0 };
const truth = (x, yawQ, run = 'r1', rotorQ = [1, 0, 0, 0]) => ({
  t_s: (run === 'r1' ? 100 : 0) + (clock[run] += 0.1), mass: { cg_world_m: [x, 0, 10.5] },
  body_poses: { airframe: { position: [x, 0, 10], quaternion_wxyz: yawQ }, rotor1: { position: [x, 1, 10], quaternion_wxyz: rotorQ } },
});

test('draws between the two latest true poses, one interval behind', () => {
  const p = createPoseInterpolator();
  p.receive(truth(0, [1, 0, 0, 0]), 0);
  p.receive(truth(10, [half, 0, 0, half]), 100);
  const mid = p.present(150);
  assert.ok(Math.abs(mid.body_poses.airframe.position[0] - 5) < 1e-9);
  const q = mid.body_poses.airframe.quaternion_wxyz, yaw = 2 * Math.atan2(q[3], q[0]);
  assert.ok(Math.abs(yaw - Math.PI / 4) < 1e-9, 'half of a 90 degree turn');
  assert.equal(mid.mass.cg_world_m[0], 5, 'camera target moves with the drawn airframe');
  assert.equal(p.present(100).body_poses.airframe.position[0], 0, 'starts at the previous true pose');
  assert.equal(p.present(260).body_poses.airframe.position[0], 10, 'never runs past the latest true pose');
});

test('never extrapolates and keeps rotors on their latest orientation', () => {
  const p = createPoseInterpolator();
  p.receive(truth(0, [1, 0, 0, 0], 'r1', [1, 0, 0, 0]), 0);
  p.receive(truth(10, [1, 0, 0, 0], 'r1', [0, 0, 0, 1]), 100);
  for (const t of [100, 130, 170, 199, 500]) {
    const x = p.present(t).body_poses.airframe.position[0];
    assert.ok(x >= 0 && x <= 10);
  }
  assert.deepEqual(p.present(150).body_poses.rotor1.quaternion_wxyz, [0, 0, 0, 1]);
  assert.equal(p.present(150).body_poses.rotor1.position[0], 5, 'rotor still travels with the airframe');
});

test('resets, new runs and pauses show the latest truth at once', () => {
  const p = createPoseInterpolator();
  p.receive(truth(0, [1, 0, 0, 0]), 0);
  p.receive(truth(500, [1, 0, 0, 0]), 100);
  assert.equal(p.present(150).body_poses.airframe.position[0], 500, 'a 500 m step is a teleport');
  p.receive(truth(0, [1, 0, 0, 0], 'r2'), 200);
  assert.equal(p.present(250).body_poses.airframe.position[0], 0, 'a clock that went back (new run) is not blended with the old one');
  p.receive(truth(4, [1, 0, 0, 0], 'r2'), 300);
  assert.equal(p.present(350, { frozen: true }).body_poses.airframe.position[0], 4);
});

test('an early packet does not advance the pose or camera on arrival', () => {
  const p = createPoseInterpolator();
  const q = [1, 0, 0, 0];
  p.receive(truth(0, q), 0);
  p.receive(truth(10, q), 100);
  const before = p.present(145);
  p.receive(truth(14, q), 145);
  const after = p.present(145);
  assert.deepEqual(after.body_poses.airframe.position, before.body_poses.airframe.position);
  assert.deepEqual(after.mass.cg_world_m, before.mass.cg_world_m);
  assert.ok(p.present(160).body_poses.airframe.position[0] > before.body_poses.airframe.position[0]);
  assert.equal(p.present(350).body_poses.airframe.position[0], 14);
});

test('slerp is unit length and takes the short way round', () => {
  const q = slerp([1, 0, 0, 0], [-half, 0, 0, -half], 0.5);
  assert.ok(Math.abs(Math.hypot(...q) - 1) < 1e-12);
  assert.ok(Math.abs(2 * Math.atan2(q[3], q[0]) - Math.PI / 4) < 1e-9);
});
