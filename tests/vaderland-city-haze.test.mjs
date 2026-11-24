import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import * as THREE from 'three';
import {buildAtmosphere, citySkyGlow} from '../public/vtx-env/vaderland/atmosphere.js';
import {buildCityLife} from '../public/vtx-env/vaderland/city-life.js';

test('city atmosphere retains the point effects without adding any fog geometry', (t) => {
  const context = {
    createImageData: (width, height) => ({data: new Uint8ClampedArray(width * height * 4)}),
    putImageData() {},
    drawImage() {},
  };
  const previous = globalThis.document;
  globalThis.document = {createElement: () => ({getContext: () => context})};
  t.after(() => { globalThis.document = previous; });

  const scene = new THREE.Group();
  const atmosphere = buildAtmosphere(scene, {}, {nx: 1, ny: 1, level: [.5]});
  const effects = [];
  scene.traverse(object => {
    assert.ok(!object.isMesh, `unexpected atmospheric mesh ${object.name}`);
    if (object.isPoints) effects.push(object);
  });
  assert.deepEqual(effects.map(object => object.name).sort(), ['Light motes', 'Rain cells']);

  atmosphere.update(57);
  for (const effect of effects) {
    assert.equal(effect.material.uniforms.time.value, 57);
    const weather = effect.material.uniforms.weather.value;
    assert.ok(weather >= 0 && weather <= 1);
  }
});

test('the sky glow is wired to the existing opaque sky and gated to the photographic rooftop city', async () => {
  assert.match(citySkyGlow, /float\s+meridianSkyGlow\(vec3\s+ray\)/);
  const source = await readFile(new URL('../public/vtx-env/vaderland/landscape.js', import.meta.url), 'utf8');
  assert.match(source, /import\s*\{[^}]*\bcitySkyGlow\b[^}]*\}\s*from\s*['"]\.\/atmosphere\.js['"]/);
  const start = source.indexOf('const dome=new THREE.Mesh');
  const end = source.indexOf('terrainTiles(group,w,uniforms);', start);
  assert.ok(start >= 0 && end > start, 'found the background sky before the terrain draw');
  const sky = source.slice(start, end);
  assert.match(sky, /side:\s*THREE\.BackSide\s*,\s*depthWrite:\s*false\s*,\s*depthTest:\s*false/);
  assert.doesNotMatch(sky, /transparent:\s*true/);
  assert.match(sky, /gl_FragColor\s*=\s*vec4\(c,\s*1\.\)/);
  assert.match(sky, /\bcitySkyGlow\b/);
  assert.match(sky, /if\s*\(\s*photographic\s*>\s*\.5\s*\)\s*\{[^}]*if\s*\(\s*rooftopPass\s*>\s*\.5\s*\)\s*\{[^}]*meridianSkyGlow\(d\)\s*\*\s*night/);
  assert.equal((source.match(/\bmeridianSkyGlow\(/g) ?? []).length, 1);
  assert.match(source, /atmosphere\?\.update\(seconds\)/);
});

test('the city lamp glow still uses depth-tested additive light', () => {
  const scene = new THREE.Group();
  const world = {
    half_m: 1000, heights_m: [[0, 0], [0, 0]], obstacles: [],
    vaderland: {routes: [{kind: 'street', width_m: 28, points: [[0, 600], [80, 600]]}]},
  };
  buildCityLife(scene, world, {night: {value: 1}}, {sample: () => 1});
  const lamps = scene.getObjectByName('Street lamps');
  assert.ok(lamps.geometry.instanceCount > 0);
  assert.equal(lamps.material.blending, THREE.AdditiveBlending);
  assert.equal(lamps.material.depthTest, true);
  assert.equal(lamps.material.depthWrite, false);
  const pools = scene.getObjectByName('Street light pools');
  const axes = pools.geometry.getAttribute('poolAxes');
  assert.ok(pools.geometry.instanceCount > 0);
  assert.equal(axes.count, pools.geometry.instanceCount);
  for (let i = 0; i < axes.count; i++) {
    assert.equal(axes.getX(i), 1);
    assert.equal(axes.getY(i), 0);
    assert.ok(axes.getZ(i) > axes.getW(i), 'light spreads farther along the surveyed street');
  }
});

test('occupied western frontages get warm road spill without lighting the open outskirts', () => {
  const lampsAt = (name, density) => {
    const scene = new THREE.Group();
    const world = {
      half_m: 1000, heights_m: [[0, 0], [0, 0]], obstacles: [],
      vaderland: {routes: [{name, kind: 'boulevard', width_m: 37, points: [[-840, 820], [-440, 820]]}]},
    };
    buildCityLife(scene, world, {night: {value: 1}}, {sample: () => density});
    return scene.getObjectByName('Street light pools').geometry;
  };
  const occupied = lampsAt('West Exchange Crescent', .15);
  assert.ok(occupied.instanceCount > 0);
  for (let i = 0; i < occupied.instanceCount; i++) {
    assert.equal(occupied.getAttribute('pool').getW(i), 1, 'warm sodium treatment');
    assert.ok(occupied.getAttribute('level').getX(i) > .03);
  }
  assert.equal(lampsAt('West Exchange Crescent', .06).instanceCount, 0);
  assert.equal(lampsAt('Other street', .15).instanceCount, 0);
});
