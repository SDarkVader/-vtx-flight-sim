import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {test} from 'node:test';

const threeUrl = new URL('../public/vendor/three.module.js', import.meta.url).href;
const effectsUrl = new URL('../public/vtx-env/phantom-effects.js', import.meta.url).href;
const source = (await readFile(new URL('../public/vtx-env/phantom-look.js', import.meta.url), 'utf8'))
  .replace("from '../vehicle-livery.js'", "from '"+new URL('../public/vehicle-livery.js',import.meta.url).href+"'").replace("from 'three'", `from '${threeUrl}'`)
  .replace("from './phantom-effects.js?v=1'", `from '${effectsUrl}'`);
const THREE = await import(threeUrl);
const {attachPhantom, updatePhantom} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

test('measured suspension and steering move the wheel, not the pod', () => {
  const model = new THREE.Group(), pod = new THREE.Group();
  pod.name = 'JOINT_WHEEL_POD_FR';
  pod.userData = {phantom_joint:'pod_FL', joint_type:'hinge', axis_parent:[1,0,0], q_rest:0};
  const tyre = new THREE.Mesh(new THREE.BoxGeometry(1,1,1), new THREE.MeshBasicMaterial());
  tyre.name = 'WHEEL_FR_CLOSED_TYRE';
  pod.add(tyre); model.add(pod);
  const rig = attachPhantom(model);
  updatePhantom(rig, {t_s:1, phantom:{joints:{pod_FL:0, pod_FL_susp:.12, pod_FL_steer:.2, pod_FL_wheel:.4}}});
  assert.equal(rig.wheels.length, 1);
  assert.ok(Math.abs(rig.wheels[0].suspension.position.z - .12) < 1e-12);
  assert.ok(Math.abs(rig.wheels[0].steering.quaternion.z - Math.sin(.1)) < 1e-12);
  assert.ok(Math.abs(pod.quaternion.z) < 1e-12);
  assert.equal(tyre.parent, rig.wheels[0].node);
});

test('physical presentation hides a wheel with missing joints and restores it from a later complete frame', () => {
  const model = new THREE.Group(), pod = new THREE.Group();
  pod.name = 'JOINT_WHEEL_POD_FR';
  pod.userData = {phantom_joint:'pod_FL', joint_type:'hinge', axis_parent:[1,0,0], q_rest:0};
  const tyre = new THREE.Mesh(new THREE.BoxGeometry(1,1,1), new THREE.MeshBasicMaterial());
  tyre.name = 'WHEEL_FR_CLOSED_TYRE'; pod.add(tyre); model.add(pod);
  const rig = attachPhantom(model), wheel = rig.wheels[0];
  const complete = {pod_FL:.3, pod_FL_susp:.12, pod_FL_steer:.2, pod_FL_wheel:.4};
  updatePhantom(rig, {phantom:{joints:complete}}, false, [], true);
  assert.equal(wheel.node.visible, true);
  assert.equal(wheel.fit.pose_status, 'measured');
  for (const name of Object.keys(complete)) {
    const joints = {...complete}; delete joints[name];
    updatePhantom(rig, {phantom:{joints}}, false, [], true);
    assert.equal(wheel.node.visible, false, name);
    assert.equal(wheel.fit.pose_status, 'unavailable');
    assert.deepEqual(wheel.fit.missing_joints, [name]);
    updatePhantom(rig, {phantom:{joints:complete}}, false, [], true);
    assert.equal(wheel.node.visible, true, name);
    assert.deepEqual(wheel.fit.missing_joints, []);
  }
  updatePhantom(rig, {phantom:{joints:{}}}, false, [], true);
  assert.equal(pod.visible, false);
  assert.deepEqual(pod.quaternion.toArray(), [0,0,0,1]);
  assert.equal(wheel.suspension.position.z, 0);
  assert.deepEqual(wheel.steering.quaternion.toArray(), [0,0,0,1]);
  assert.deepEqual(wheel.node.quaternion.toArray(), [0,0,0,1]);
  updatePhantom(rig, {phantom:{joints:complete}}, false, [], true);
  assert.equal(pod.visible, true);
  assert.equal(wheel.node.visible, true);
  assert.ok(Math.abs(wheel.suspension.position.z - .12) < 1e-12);
  assert.ok(Math.abs(wheel.steering.quaternion.z - Math.sin(.1)) < 1e-12);
  assert.ok(Math.abs(wheel.node.quaternion.y - Math.sin(.2)) < 1e-12);
  for (const invalid of [null, NaN, Infinity, -Infinity]) {
    updatePhantom(rig, {phantom:{joints:{...complete, pod_FL:invalid}}}, false, [], true);
    assert.equal(pod.visible, false);
    assert.deepEqual(pod.quaternion.toArray(), [0,0,0,1]);
    assert.equal(wheel.node.visible, false);
    updatePhantom(rig, {phantom:{joints:complete}}, false, [], true);
    assert.equal(pod.visible, true);
    assert.equal(wheel.node.visible, true);
  }
});

test('stabilator follows physical position without a second cosmetic controller', () => {
  const model = new THREE.Group(), drs = new THREE.Group();
  drs.name = 'VTX_VISUAL_DRS_HINGE';
  drs.userData = {axis_parent:[0,1,0], range_deg:[0,55]};
  model.add(drs);
  const rig = attachPhantom(model);
  updatePhantom(rig, {t_s:1, body_poses:{airframe:{position:[0,0,0]}}, phantom:{drs_deg:6}});
  updatePhantom(rig, {t_s:1.01, body_poses:{airframe:{position:[1,0,0]}},
    phantom:{drs_deg:36}, command:{brake:[0,0,0,0]}});
  assert.ok(Math.abs(drs.quaternion.y - Math.sin(Math.PI / 12)) < 1e-12);
  updatePhantom(rig, {t_s:2, body_poses:{airframe:{position:[30,0,0]}},
    phantom:{drs_deg:null}, command:{brake:[1,1,1,1]}});
  assert.ok(Math.abs(drs.quaternion.y) < 1e-12);
});
