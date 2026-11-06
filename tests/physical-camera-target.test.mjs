import assert from 'node:assert/strict';
import {physicalCameraTarget} from '../public/physical-camera-target.js';

// A body can rotate about a stationary CG while its CAD origin moves around it.
const first = {phantom: {}, mass: {cg_world_m: [10, 20, 30]}, body_poses: {airframe: {position: [10, 20, 29.44]}}};
const rotated = {phantom: {}, mass: {cg_world_m: [10, 20, 30]}, body_poses: {airframe: {position: [9.44, 20, 30]}}};
assert.deepEqual(physicalCameraTarget(first), [10, 20, 30.94]);
assert.deepEqual(physicalCameraTarget(rotated), physicalCameraTarget(first));
// Other aircraft and older snapshots retain their original framing.
assert.deepEqual(physicalCameraTarget({body_poses: {airframe: {position: [1, 2, 3]}}}), [1, 2, 4.5]);
assert.equal(physicalCameraTarget({}), null);
