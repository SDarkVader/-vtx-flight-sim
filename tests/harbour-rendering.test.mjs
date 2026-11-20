import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {harbourWorldPoint, drawHarbourMap, drawHarbourBoats} from '../public/vtx-env/harbour-map.js';

// Use the exact repository Three build headlessly; production uses its import map.
const threeUrl = new URL('../public/vendor/three.module.js', import.meta.url).href;
const mapUrl = new URL('../public/vtx-env/harbour-map.js', import.meta.url).href;
const lanternSource = (await readFile(new URL('../public/vtx-env/lantern-marks.js', import.meta.url), 'utf8'))
  .replace("from 'three'", `from '${threeUrl}'`);
const lanternUrl = 'data:text/javascript;base64,' + Buffer.from(lanternSource).toString('base64');
const source = (await readFile(new URL('../public/vtx-env/harbour.js', import.meta.url), 'utf8'))
  .replace("from 'three'", `from '${threeUrl}'`)
  .replace(/from '\.\/harbour-map\.js(?:\?[^']*)?'/, `from '${mapUrl}'`)
  .replace("from './lantern-marks.js'", `from '${lanternUrl}'`);
const {harbourWaterGeometry, harbourOverviewView, buildBoatRig, applyBoatPoses, buildHarbour} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const THREE = await import(threeUrl);
const harbour = {origin: [100, -200], waterLevelM: 7,
  layout: {outer: [[0, 0], [200, 0], [200, 100], [0, 100]], islands: [{name: 'Island', ring: [[30, 30], [40, 30], [40, 40], [30, 40]]}],
    routes: [{id: 'route', points: [[10, 20], [100, 80]], stops: [{index: 0}]}]},
  docks: {piers: [{id: 'pier', center: [10, 20], length: 10, width: 2, heading: Math.PI / 2}],
    berths: [{id: 'berth', x: 15, y: 20}], craftFixtures: [{id: 'unverified-fixture'}]}};
assert.deepEqual(harbourWorldPoint(harbour, [10, 20]), [110, -220]);
for (const aspect of [.6, 1.1, 2]) {
  const view = harbourOverviewView(harbour, {aspect}), camera = new THREE.PerspectiveCamera(48, aspect, view.near, view.far);
  camera.up.set(0, 0, 1); camera.position.set(...view.position); camera.lookAt(...view.target); camera.updateMatrixWorld(true);
  for (const point of harbour.layout.outer) {
    const p = new THREE.Vector3(...harbourWorldPoint(harbour, point), 7).project(camera);
    assert.ok(Math.abs(p.x) < 1 && Math.abs(p.y) < 1 && p.z > -1 && p.z < 1, 'whole shoreline must fit in a portrait or desktop overview');
  }
  assert.ok(view.near >= 10, 'overview needs sufficient depth precision to separate shallow lake bed from water');
}
const water = harbourWaterGeometry(harbour), p = water.attributes.position, ix = water.index.array;
let area = 0;
for (let i = 0; i < ix.length; i += 3) {
  const a = ix[i], b = ix[i + 1], c = ix[i + 2];
  area += Math.abs((p.getX(b) - p.getX(a)) * (p.getY(c) - p.getY(a)) - (p.getY(b) - p.getY(a)) * (p.getX(c) - p.getX(a))) / 2;
}
assert.equal(area, 19900, 'water geometry must subtract the dry island');
const payload = {geometry_sha256: 'known', meshes: [{name: 'rudder', body: 'rudder', vertices: [0, 0, 0, 1, 0, 0, 0, 1, 0], faces: [0, 1, 2], offset: [2, 0, 0]}], boxes: []};
const rig = buildBoatRig(payload), q = [Math.SQRT1_2, 0, 0, Math.SQRT1_2];
assert.deepEqual(applyBoatPoses(rig, {rudder: {position: [10, 20, 7], quaternion_wxyz: q}}), []);
rig.root.updateMatrixWorld(true);
const measured = new THREE.Vector3(1, 0, 0).applyMatrix4(rig.bodies.get('rudder').children[0].matrixWorld);
assert.ok(measured.distanceTo(new THREE.Vector3(10, 23, 7)) < 1e-8, 'mesh offset must follow actual body quaternion');
assert.deepEqual(applyBoatPoses(rig, {}), ['rudder']); assert.equal(rig.bodies.get('rudder').visible, false);
applyBoatPoses(rig, {rudder: {position: [10, 20, 7], quaternion_wxyz: [2, 0, 0, 0]}}); assert.equal(rig.bodies.get('rudder').visible, false);
applyBoatPoses(rig, {rudder: {position: [10, 20, 7], quaternion_wxyz: [1, 0, 0, 0]}}); assert.equal(rig.bodies.get('rudder').visible, true);
let resolve, errors = [];
const layer = buildHarbour({harbour}, {fetchModel: () => new Promise(r => {resolve = r;}), onError: (id, error) => errors.push(error.message)});
assert.equal(layer.boats.size, 0, 'planned fixture boats must never replace physical fleet state');
assert.equal(layer.root.getObjectByName('harbour-route-route').geometry.attributes.position.getX(0), 110);
const boat = {id: 'actual', variant: 'ricochet-concept-a', configuration: {geometry_sha256: 'known'}, body_poses: {rudder: {position: [10, 20, 7], quaternion_wxyz: [1, 0, 0, 0]}}};
layer.update({available: true, boats: [boat], occupancy: {berth: 'actual'}});
resolve(payload); await new Promise(r => setTimeout(r, 0)); assert.equal(layer.boats.size, 1);
layer.update({available: true, boats: [boat], structures: [{id: 'pier', center: [110, -220, 7.6], half_extents: [5, 1, .6], yaw_deg: -90}], water_level_m: 7});
assert.deepEqual(layer.structureNodes.get('pier').position.toArray(), [110, -220, 7.6]);
assert.deepEqual(layer.structureNodes.get('pier').scale.toArray(), [10, 2, 1.2], 'structure renderer must use authoritative physical extents');
const sample = (time, x) => ({
  available: true, t_s: time,
  boats: [{...boat, body_poses: {rudder: {position: [x, 20, 7], quaternion_wxyz: [1, 0, 0, 0]}}}]
});
const rudder = layer.boats.get('actual').bodies.get('rudder');
layer.update(sample(1, 10), {now: 1000});
layer.update(sample(1.1, 12), {now: 1100});
layer.animate(1150);
assert.equal(rudder.position.x, 11, 'draw intermediate positions between measured boat snapshots');
layer.animate(1400);
assert.equal(rudder.position.x, 12, 'never extrapolate beyond the last physical sample');
layer.update(sample(.5, 8), {now: 1410});
assert.equal(rudder.position.x, 8, 'restoring an earlier simulation time must snap to the saved boat');
layer.update(sample(2, 13), {now: 1460, snap: true});
assert.equal(rudder.position.x, 13, 'an explicit restore must also snap when its saved time is newer');
layer.update({available: true, boats: [{...boat, body_poses: {}}]}); assert.equal(layer.boats.get('actual').bodies.get('rudder').visible, false);
layer.update({available: false, boats: [boat]}); assert.equal(layer.boats.get('actual').root.visible, false, 'stale fleet cannot appear current');
layer.dispose();
const late = buildHarbour({harbour}, {fetchModel: () => new Promise(r => {resolve = r;})});
late.update({available: true, boats: [boat]}); late.dispose(); resolve(payload); await new Promise(r => setTimeout(r, 0));
assert.equal(late.boats.size, 0, 'late geometry response must not repopulate a disposed airport');
const bad = buildHarbour({harbour}, {fetchModel: async () => ({...payload, geometry_sha256: 'wrong'}), onError: (id, error) => errors.push(error.message)});
bad.update({available: true, boats: [boat]}); await new Promise(r => setTimeout(r, 0)); assert.equal(bad.boats.size, 0); assert.match(errors.at(-1), /identity/); bad.dispose();
let modelLoads = 0;
const changed = buildHarbour({harbour}, {fetchModel: async () => {modelLoads++; return payload;}});
changed.update({available: true, boats: [{...boat, configuration: {...boat.configuration, model_xml_sha256: 'first'}}]});
await new Promise(r => setTimeout(r, 0)); const previousRig = changed.boats.get(boat.id);
changed.update({available: true, boats: [{...boat, configuration: {...boat.configuration, model_xml_sha256: 'second'}}]});
await new Promise(r => setTimeout(r, 0));
assert.equal(modelLoads, 2, 'changed physical model must reload model-dependent appendage geometry');
assert.notEqual(changed.boats.get(boat.id), previousRig); changed.dispose();
const calls = [], ctx = new Proxy({}, {get: (target, key) => key in target ? target[key] : (...args) => calls.push([key, ...args]), set: (t, k, v) => {t[k] = v; return true;}});
drawHarbourMap(ctx, {px: x => x, py: y => -y, scaleM: x => x}, harbour);
assert.ok(calls.some(c => c[0] === 'fill' && c[1] === 'evenodd'));
calls.length = 0; drawHarbourBoats(ctx, {px: x => x, py: y => -y, scaleM: x => x}, {available: true, boats: [{id: 'boat', position: [110, -220, 7], heading_rad: Math.PI / 2}]});
assert.ok(calls.some(c => c[0] === 'translate' && c[1] === 110 && c[2] === 220)); assert.ok(calls.some(c => c[0] === 'rotate' && c[1] === -Math.PI / 2));
console.log('Harbour island holes, world/map parity, physical body poses, identity and asynchronous teardown passed');
