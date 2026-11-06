// Run with: node --test tests/traffic-path.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildTrafficRoute, sampleTrafficRoute } from '../public/vtx-env/traffic-path.js';

test('reproducible endpoints, midpoint and velocity', () => {
  const route = buildTrafficRoute([
    { position: [0, 0, 0], speed: 0 },
    { position: [100, 0, 0], speed: 0, duration: 10 }
  ]);
  assert.deepEqual(sampleTrafficRoute(route, 0).position, [0, 0, 0]);
  assert.deepEqual(sampleTrafficRoute(route, 5).position, [50, 0, 0]);
  assert.deepEqual(sampleTrafficRoute(route, 10).position, [100, 0, 0]);
  assert.equal(sampleTrafficRoute(route, 5).speed, 15);
  assert.deepEqual(sampleTrafficRoute(route, 5), sampleTrafficRoute(route, 5));
});
test('uniform spatial and velocity scaling, time preserved', () => {
  const input = [
    { position: [0, 0, 0], speed: 0 },
    { position: [100, 0, 20], speed: 0, duration: 10 }
  ];
  const a = sampleTrafficRoute(buildTrafficRoute(input), 5);
  const b = sampleTrafficRoute(buildTrafficRoute(input, { scale: 0.1 }), 5);
  a.position.forEach((v, i) => assert.ok(Math.abs(b.position[i] - v * 0.1) < 1e-9));
  assert.ok(Math.abs(b.speed - a.speed * 0.1) < 1e-9);
  assert.ok(Math.abs(a.pitch - b.pitch) < 1e-12);
});
test('clamps before and after route and rejects bad inputs', () => {
  const route = buildTrafficRoute([
    { position: [0, 0, 0], speed: 0 },
    { position: [10, 0, 0], speed: 0, duration: 2 }
  ]);
  assert.deepEqual(sampleTrafficRoute(route, -10).position, [0, 0, 0]);
  assert.deepEqual(sampleTrafficRoute(route, 100).position, [10, 0, 0]);
  assert.throws(() => buildTrafficRoute([{ position: [0,0,0], speed: 0 }]));
  assert.throws(() => buildTrafficRoute([{ position: [0,0,0], speed: 0 }, { position: [0,0,0], speed: 0, duration: 1 }]));
});
