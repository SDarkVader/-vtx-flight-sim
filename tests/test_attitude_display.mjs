import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {test} from 'node:test';

const load = async path => import('data:text/javascript;base64,' +
  Buffer.from(await readFile(new URL(path, import.meta.url))).toString('base64'));
const {physicalCockpitAttitude, renderAttitudeIndicator} = await load('../public/attitude-display.js');
const {cockpitHorizon} = await load('../public/cockpit-axes.js');
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`);
const frame = (q, phantom = true) => ({t_s: 12.5, body_poses: {cabin: {quaternion_wxyz: q}}, ...(phantom ? {phantom: {}} : {})});
const axis = (axis, degrees) => {
  const angle = degrees * Math.PI / 360, q = [Math.cos(angle), 0, 0, 0];
  q[axis] = Math.sin(angle);
  return q;
};

test('Phantom pitch and bank follow its physical axes in both directions', () => {
  for (const pitch of [-20, 0, 20]) near(physicalCockpitAttitude(frame(axis(2, -pitch))).pitchDegrees, pitch);
  for (const bank of [-30, 0, 30]) near(physicalCockpitAttitude(frame(axis(1, bank))).bankDegrees, bank);
  const yawed = physicalCockpitAttitude(frame(axis(3, 90)));
  near(yawed.pitchDegrees, 0); near(yawed.bankDegrees, 0);
});

test('R6 quaternion output agrees with the existing cabin-axis convention', () => {
  for (const x of [-25, 0, 25]) for (const y of [-15, 0, 15]) {
    const hx = x * Math.PI / 360, hy = y * Math.PI / 360;
    const q = [Math.cos(hx)*Math.cos(hy), Math.sin(hx)*Math.cos(hy),
      Math.cos(hx)*Math.sin(hy), -Math.sin(hx)*Math.sin(hy)];
    const expected = cockpitHorizon([x,y,0]);
    const actual = physicalCockpitAttitude(frame(q, false));
    near(actual.pitchDegrees, expected.pitchDegrees); near(actual.bankDegrees, expected.bankDegrees);
  }
});

test('missing, malformed or zero quaternions never appear as level attitude', () => {
  for (const invalid of [undefined, {}, frame([0,0,0,0]), frame([1,0,NaN,0]), frame([1,0,0])]) {
    assert.equal(physicalCockpitAttitude(invalid), null);
  }
});

test('live, replay, stale and unavailable states are visible and recover', () => {
  const elements = {indicator:{dataset:{},setAttribute(k,v){this[k]=v;}}, horizon:{style:{}}, angles:{}, status:{}};
  renderAttitudeIndicator(elements, frame(axis(2,-10)), 'LIVE');
  assert.equal(elements.indicator.dataset.status, 'live');
  assert.match(elements.status.textContent, /LIVE · 12\.5s/);
  assert.match(elements.angles.textContent, /P 10\.0°/);
  renderAttitudeIndicator(elements, frame(axis(1,20)), 'REPLAY');
  assert.equal(elements.indicator.dataset.status, 'replay');
  assert.match(elements.angles.textContent, /B 20\.0°/);
  renderAttitudeIndicator(elements, frame(axis(1,20)), 'STALE');
  assert.equal(elements.status.textContent, 'STALE · 12.5s');
  renderAttitudeIndicator(elements, null, 'LIVE');
  assert.equal(elements.status.textContent, 'UNAVAILABLE');
  assert.equal(elements.horizon.style.visibility, 'hidden');
  renderAttitudeIndicator(elements, frame([1,0,0,0]), 'LIVE');
  assert.equal(elements.horizon.style.visibility, 'visible');
  assert.equal(elements.indicator.dataset.status, 'live');
});
