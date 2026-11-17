import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import assert from 'node:assert/strict';
import {test} from 'node:test';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const threeUrl = new URL('../public/vendor/three.module.js', import.meta.url).href;
const effectsUrl = new URL('../public/vtx-env/phantom-effects.js', import.meta.url).href;
const source = readFileSync(resolve(root, 'public/vtx-env/phantom-look.js'), 'utf8')
  .replace("from '../vehicle-livery.js'", "from '"+new URL('../public/vehicle-livery.js',import.meta.url).href+"'").replace("from 'three'", `from '${threeUrl}'`)
  .replace("from './phantom-effects.js?v=1'", `from '${effectsUrl}'`);
const THREE = await import(threeUrl);
const {attachPhantom, updatePhantom} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

// Reconstruct each authored tyre node and its exact stored position bounds from
// the original GLB. This does not rewrite the asset or depend on image loaders.
const glb = readFileSync(resolve(root, 'public/assets/phantom-a10b-visual.glb'));
const json = JSON.parse(glb.subarray(20, 20 + glb.readUInt32LE(12)).toString());
function assetRig() {
  const model = new THREE.Group(); model.name = 'airframe';
  for (const n of json.nodes.filter(n => /^pod_(FL|FR|RL|RR)$/.test(n.extras?.phantom_joint || ''))) {
    const p = new THREE.Group(); p.name = n.name; p.userData = n.extras;
    if (n.translation) p.position.fromArray(n.translation);
    if (n.rotation) p.quaternion.fromArray(n.rotation);
    model.add(p);
    const child = n.children.map(i => json.nodes[i]).find(x => /_CLOSED_TYRE$/.test(x.name || ''));
    const accessor = json.accessors[json.meshes[child.mesh].primitives[0].attributes.POSITION];
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute([...accessor.min, ...accessor.max], 3));
    const tyre = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial()); tyre.name = child.name;
    if (child.translation) tyre.position.fromArray(child.translation);
    if (child.rotation) tyre.quaternion.fromArray(child.rotation);
    p.add(tyre);
  }
  return model;
}

test('visual wheels preserve authored dimensions and attachment datums while following measured articulation', () => {
  const python = process.env.VTX_TEST_PYTHON || 'python';
  const cases = JSON.parse(execFileSync(python, [resolve(root, 'tests/wheel_pose_fixture.py')], {
    cwd: root, env: {...process.env, PYTHONPATH: resolve(root, 'src'), PYTHONDONTWRITEBYTECODE:'1'}, encoding:'utf8', maxBuffer: 4 * 1024 * 1024,
  }));
  for (const c of cases) {
    const model = assetRig(), rig = attachPhantom(model), air = c.truth.body_poses.airframe;
    model.position.fromArray(air.position);
    model.quaternion.set(air.quaternion_wxyz[1], air.quaternion_wxyz[2], air.quaternion_wxyz[3], air.quaternion_wxyz[0]).normalize();
    updatePhantom(rig, c.truth, false, [], true);
    model.updateMatrixWorld(true);
    assert.equal(rig.wheels.length, 4);
    for(const jet of rig.podJets){
      const rendered=new THREE.Vector3(0,0,1).applyQuaternion(jet.glow.getWorldQuaternion(new THREE.Quaternion()));
      const exhaust=new THREE.Vector3(...c.expected[jet.pod].fan_axis_world).negate();
      assert.ok(rendered.distanceTo(exhaust)<3e-5,`${c.variant} ${c.tilted} ${jet.pod} plume opposes the actual fan force axis`);
    }
    for (const wheel of rig.wheels) {
      const pod = ['FL', 'FR', 'RL', 'RR'][wheel.idx], expected = c.expected[pod];
      assert.equal(wheel.node.visible, true, `${c.variant} ${pod} wheel visible`);
      assert.equal(wheel.podJoint.node.visible, true, `${c.variant} ${pod} pod visible`);
      assert.equal(wheel.fit.pose_status, pod.startsWith('R') ? 'measured-fixed-steering' : 'measured');
      const actualPos = wheel.node.getWorldPosition(new THREE.Vector3());
      const authoredNode = json.nodes.find(n => n.extras?.phantom_joint === `pod_${pod}`);
      assert.ok(wheel.podJoint.node.position.distanceTo(new THREE.Vector3(...authoredNode.translation)) < 1e-12, 'original attachment remains intact');
      const airQ = new THREE.Quaternion(air.quaternion_wxyz[1], air.quaternion_wxyz[2], air.quaternion_wxyz[3], air.quaternion_wxyz[0]).normalize();
      const physicalAnchor = new THREE.Vector3(...c.truth.body_poses[`pod_${pod}`].position)
        .sub(new THREE.Vector3(...air.position)).applyQuaternion(airQ.clone().invert());
      const authoredOffset = new THREE.Vector3(...authoredNode.translation).sub(physicalAnchor);
      const expectedVisualPos = new THREE.Vector3(...expected.position).add(authoredOffset.clone().applyQuaternion(airQ));
      assert.ok(actualPos.distanceTo(expectedVisualPos) < 3e-5, `${c.variant} ${c.tilted} ${pod} authored center follows suspension`);
      const eq = expected.quaternion_wxyz;
      const actualQ = wheel.node.getWorldQuaternion(new THREE.Quaternion());
      const expectedQ = new THREE.Quaternion(eq[1], eq[2], eq[3], eq[0]);
      assert.ok(1 - Math.abs(actualQ.dot(expectedQ)) < 1e-8, `${c.variant} ${c.tilted} ${pod} orientation`);
      assert.equal(wheel.fit.status, 'authored-visual');
      const collider = c.truth.phantom.wheel_collision_geometry[pod];
      assert.deepEqual(wheel.node.scale.toArray(), [1,1,1], 'collision dimensions never resize the authored wheel');
      assert.ok(Math.abs(wheel.authored.radius_m - .36) < 1e-6);
      assert.deepEqual(wheel.fit.collider, collider, 'collider dimensions remain inspectable');
      assert.ok(new THREE.Vector3(...wheel.fit.visual_minus_collision_anchor_m).distanceTo(authoredOffset) < 1e-12);
      assert.equal(wheel.fit.size_comparison, Math.abs(wheel.authored.radius_m-collider.radius_m)<1e-5 && Math.abs(wheel.authored.half_width_m-collider.half_width_m)<1e-5 ? 'matches' : 'different');
    }
    const unknown = structuredClone(c.truth); unknown.variant = 'unknown-phantom';
    updatePhantom(rig, unknown, false, [], true);
    for (const wheel of rig.wheels.filter(w => w.idx >= 2)) {
      assert.equal(wheel.node.visible, false, 'unknown variant cannot assume rear steering is fixed');
      assert.equal(wheel.fit.pose_status, 'unavailable');
    }
    const mismatch = structuredClone(c.truth); mismatch.body_poses.pod_RL_wheel.quaternion_wxyz = [0, 1, 0, 0];
    updatePhantom(rig, mismatch, false, [], true);
    assert.equal(rig.wheels.find(w => w.idx === 2).node.visible, false, 'inconsistent wheel body pose cannot establish fixed steering');
    const wrongConfig = structuredClone(c.truth); wrongConfig.config_sha256 = 'unverified';
    updatePhantom(rig, wrongConfig, false, [], true);
    assert.equal(rig.wheels.find(w => w.idx === 2).node.visible, false, 'unverified configuration cannot assume fixed steering');
    // An old recording without collider/pose telemetry keeps its authored fit;
    // diagnostics must not carry a collider comparison over from another frame.
    updatePhantom(rig, {phantom: {joints: {}}});
    for (const wheel of rig.wheels) {
      assert.equal(wheel.fit.status, 'authored-visual');
      assert.equal(wheel.fit.size_comparison, 'unavailable');
      assert.equal(wheel.fit.collision_anchor_m, null);
      assert.deepEqual(wheel.node.scale.toArray(), [1, 1, 1]);
      assert.ok(wheel.podJoint.node.position.distanceTo(wheel.podJoint.pos) < 1e-12);
    }
  }
});

test('recorded rolling wheels retain measured body phase when joint sample is one physics step later', () => {
  // Recorded runway flight 20261112T132734-215fcf, physics audit t=19.95 s.
  // Both wheels were rolling; body quaternions and joint positions differ by
  // approximately one 2.5 ms solver step. Values are the original 6-decimal samples.
  const truth = {
    variant: 'phantom-a10c',
    config_sha256: '2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f',
    phantom: {joints: {
      pod_FL:.066448, pod_FL_steer:-.001702, pod_FL_susp:-.229099, pod_FL_wheel:207.944408,
      pod_RR:-.049621, pod_RR_susp:-.018753, pod_RR_wheel:-207.443379,
    }},
    body_poses: {
      pod_FL:{quaternion_wxyz:[.998891,.032946,-.033616,.00091]},
      pod_FL_wheel:{quaternion_wxyz:[-.980915,-.032109,-.191619,-.0075]},
      pod_RR:{quaternion_wxyz:[.999127,-.024771,-.033613,-.001032]},
      pod_RR_wheel:{quaternion_wxyz:[-.998035,.024789,.057546,.000438]},
    },
  };
  const model=assetRig(), rig=attachPhantom(model);
  updatePhantom(rig, truth, false, [], true);
  const quat = a => new THREE.Quaternion(a[1],a[2],a[3],a[0]).normalize();
  for (const pod of ['FL','RR']) {
    const wheel=rig.wheels.find(w=>['FL','FR','RL','RR'][w.idx]===pod);
    assert.equal(wheel.node.visible,true,`${pod} stays visible while rolling`);
    const measured=quat(truth.body_poses[`pod_${pod}`].quaternion_wxyz).invert()
      .multiply(quat(truth.body_poses[`pod_${pod}_wheel`].quaternion_wxyz));
    const rendered=wheel.steering.quaternion.clone().multiply(wheel.node.quaternion).normalize();
    assert.ok(1-Math.abs(rendered.dot(measured))<1e-10,`${pod} follows recorded wheel-body pose`);
    const jointOnly=new THREE.Quaternion().setFromAxisAngle(wheel.axis,truth.phantom.joints[`pod_${pod}_wheel`]);
    assert.ok(1-Math.abs(jointOnly.dot(wheel.node.quaternion))>1e-5,`${pod} body phase differs materially from later joint sample`);
  }
});
