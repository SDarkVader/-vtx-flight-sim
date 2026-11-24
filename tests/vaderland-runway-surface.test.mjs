import assert from 'node:assert/strict';
import {test} from 'node:test';
import * as THREE from 'three';
import {buildAirport} from '../public/vtx-env/vaderland/airfield.js';

test('surveyed runway pavement and markings share the collision plane', (t) => {
  const context = new Proxy({}, {get: () => () => {}});
  const previous = globalThis.document;
  globalThis.document = {createElement: () => ({getContext: () => context})};
  t.after(() => { globalThis.document = previous; });

  const scene = new THREE.Group();
  const runway = {
    id: '08/26', x0: -3900, x1: 3900, yc: 0, width: 30,
    shoulder_width: 4, elevation_m: 0, default_start: [-3885, 0],
  };
  const world = {
    runway, obstacles: [],
    vaderland: {arrivals: true, routes: [], airfield: {aprons: [], lamps: [], pads: []}},
  };
  const uniforms = Object.fromEntries(['tree0', 'tree1', 'tree2'].map(name => [name, {value: null}]));
  buildAirport(scene, world, uniforms, '', () => {});
  scene.updateMatrixWorld(true);

  const asphalt = scene.getObjectByName('Meridian runway');
  const markings = scene.getObjectByName('Meridian runway markings');
  for (const mesh of [asphalt, markings]) {
    const points = mesh.geometry.getAttribute('position');
    assert.ok(points.count > 0);
    for (let i = 0; i < points.count; i++) assert.equal(points.getZ(i), runway.elevation_m);
    assert.equal(mesh.material.depthTest, true);
  }
  assert.equal(asphalt.material.polygonOffset, false);
  assert.equal(asphalt.material.depthWrite, true);
  assert.equal(markings.material.depthWrite, false);
  assert.ok(asphalt.renderOrder < markings.renderOrder && markings.renderOrder < 0);
  for (const y of [-18.9, -15.1, -14.9, -3.3, 14.9, 15.1, 18.9]) {
    const ray = new THREE.Raycaster(new THREE.Vector3(-3851.78, y, 1), new THREE.Vector3(0, 0, -1));
    const hits = ray.intersectObject(asphalt);
    assert.equal(hits.length, 1, `single surface at y=${y}`);
    assert.equal(hits[0].point.z, runway.elevation_m);
  }
  assert.equal(scene.children.filter(child => child.material?.map?.isCanvasTexture
    && child.geometry.parameters?.width === 15.5 && child.position.z === runway.elevation_m).length, 2);
});
