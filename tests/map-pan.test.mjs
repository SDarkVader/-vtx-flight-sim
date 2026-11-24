import assert from 'node:assert/strict';
import test from 'node:test';
import {TacticalMinimap} from '../public/vtx-env/tactical-minimap.js';

function mapFixture(t, isLarge) {
  const events = new Map();
  const frames = [];
  const originalRequest = globalThis.requestAnimationFrame;
  globalThis.requestAnimationFrame = fn => frames.push(fn);
  t.after(() => {
    if (originalRequest) globalThis.requestAnimationFrame = originalRequest;
    else delete globalThis.requestAnimationFrame;
  });
  const rect = {left: 20, top: 30, width: 450, height: isLarge ? 450 : 350};
  rect.right = rect.left + rect.width;
  rect.bottom = rect.top + rect.height;
  const captures = [];
  const canvas = {
    width: isLarge ? 900 : 540,
    height: isLarge ? 900 : 430,
    getContext: () => ({}),
    getBoundingClientRect: () => rect,
    addEventListener: (name, fn) => events.set(name, fn),
    setPointerCapture: id => captures.push(id)
  };
  let redraws = 0;
  const map = new TacticalMinimap(canvas, {isLarge, redraw: () => { redraws++; }});
  map.worldHalf = 8000;
  const send = (type, overrides = {}) => events.get(type)({
    type, pointerId: 1, pointerType: 'mouse', button: 0, buttons: 1, isTrusted: true,
    clientX: 220, clientY: 170, preventDefault() {}, ...overrides
  });
  const location = (x, y) => {
    const projection = map.getProjection();
    return [
      projection.unpx((x - rect.left) * canvas.width / rect.width),
      projection.unpy((y - rect.top) * canvas.height / rect.height)
    ];
  };
  return {map, send, location, frames, captures, redraws: () => redraws};
}

for (const isLarge of [false, true]) {
  test(`${isLarge ? 'Expanded' : 'Normal'} map pans with a primary drag and keeps click selection`, t => {
    const {map, send, location, frames, captures, redraws} = mapFixture(t, isLarge);
    const trustedClick = {isTrusted: true};
    const start = location(220, 170);
    send('pointerdown');
    send('pointermove', {clientX: 222, clientY: 168});
    send('pointerup', {clientX: 222, clientY: 168, buttons: 0});
    assert.deepEqual(location(220, 170), start, 'small pointer motion is still a click');
    assert.equal(map.isNavigationClick(trustedClick), false);

    send('pointerdown');
    send('pointermove', {clientX: 242, clientY: 183});
    send('pointermove', {clientX: 253, clientY: 195});
    send('pointerup', {clientX: 253, clientY: 195, buttons: 0});
    send('lostpointercapture');
    assert.ok(location(253, 195).every((coordinate, i) => Math.abs(coordinate - start[i]) < 1e-9));
    assert.deepEqual(captures, [1, 1]);
    assert.equal(map.isNavigationClick(trustedClick), true, 'the release click cannot select A or B');
    assert.equal(map.isNavigationClick({}), false, 'direct map click handlers still work');
    assert.equal(map.isNavigationClick({isTrusted: false}), false, 'synthetic map clicks still work');
    send('dblclick');
    assert.equal(map.tacticalMode, false, 'a drag cannot trigger the tactical toggle');
    assert.equal(frames.length, 1, 'pointer moves coalesce to one display update per frame');
    frames.shift()();
    assert.equal(redraws(), 1);

    send('pointerdown');
    send('pointerup', {buttons: 0});
    assert.equal(map.isNavigationClick(trustedClick), false, 'the next deliberate click selects normally');
    const anchor = location(220, 170);
    const zoom = map.zoom;
    send('wheel', {deltaY: -150});
    assert.ok(map.zoom > zoom);
    assert.ok(location(220, 170).every((coordinate, i) => Math.abs(coordinate - anchor[i]) < 1e-9));
  });
}

test('Touch still taps, pans and pinches without a waypoint click after navigation', t => {
  const {map, send} = mapFixture(t, true);
  const touch = (type, event = {}) => send(type, {pointerType: 'touch', ...event});
  touch('pointerdown');
  touch('pointerup', {buttons: 0});
  assert.equal(map.isNavigationClick({isTrusted: true}), false);
  touch('pointerdown');
  const center = [...map.center];
  touch('pointermove', {clientX: 240});
  touch('pointerup', {clientX: 240, buttons: 0});
  assert.ok(map.center[0] < center[0]);
  assert.equal(map.isNavigationClick({isTrusted: true}), true);

  const zoom = map.zoom;
  touch('pointerdown');
  touch('pointerdown', {pointerId: 2, clientX: 260, isPrimary: false});
  touch('pointermove', {pointerId: 2, clientX: 280, isPrimary: false});
  touch('pointerup', {pointerId: 2, clientX: 280, isPrimary: false, buttons: 0});
  touch('pointerup', {buttons: 0});
  assert.equal(map.zoom, zoom * 1.5);
  assert.equal(map.isNavigationClick({isTrusted: true}), true);
});

test('A secondary button or cancelled pointer cannot leave an active drag', t => {
  const {map, send, captures} = mapFixture(t, false);
  const center = [...map.center];
  send('pointerdown', {button: 2, buttons: 2});
  send('pointermove', {buttons: 2, clientX: 320});
  send('pointerup', {button: 2, buttons: 0, clientX: 320});
  assert.deepEqual(captures, []);
  assert.deepEqual(map.center, center);

  send('pointerdown');
  send('pointercancel');
  send('pointermove', {clientX: 320});
  assert.deepEqual(map.center, center);
  assert.equal(map.isNavigationClick({isTrusted: true}), true);
});
