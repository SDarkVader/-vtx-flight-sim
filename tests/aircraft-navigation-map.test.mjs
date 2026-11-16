import assert from 'node:assert/strict';
import {test} from 'node:test';
import {TacticalMinimap, aircraftMapFix, liveMapObservation} from '../public/vtx-env/tactical-minimap.js';

const phantom = {gnss_xy_m: [100, 40], attitude_deg: {yaw: 0}, velocity_world_m_s: [0, 3, 0]};

test('only the active live vehicle supplies the navigation fix', () => {
  const view = {active: true, observation: phantom};
  assert.equal(liveMapObservation(view, 50, false), phantom);
  assert.equal(liveMapObservation(view, 2001, false), null);
  assert.equal(liveMapObservation(view, 50, true), null);
  assert.equal(liveMapObservation({...view, active: false}, 50, false), null);
  assert.equal(aircraftMapFix({gnss_xy_m: [NaN, 0]}), null);
  assert.equal(aircraftMapFix({gnss_xy_m: [0, 0]}).heading, null);
});

test('compass follows each airframe’s forward axis', () => {
  for (const [yaw, expectedPhantom, expectedR6] of [[0,90,180],[90,0,90],[180,270,0],[-90,180,270]]) {
    assert.equal(aircraftMapFix({...phantom, attitude_deg: {yaw}}).heading, expectedPhantom);
    assert.equal(aircraftMapFix({gnss_xy_m:[0,0], attitude_xyz_deg:[0,0,yaw]}).heading, expectedR6);
  }
  assert.ok(Math.abs(aircraftMapFix({gnss_xy_m:[0,0], attitude_xyz_deg:[45,30,0]}).heading - 206.56505) < .00001);
  assert.equal(aircraftMapFix({gnss_xy_m:[0,0], attitude_xyz_deg:[90,0,0]}).heading, null);
});

function mapFixture(width, cssWidth) {
  const calls = [];
  const context = new Proxy({measureText: text => ({width: text.length * 6})}, {
    get(target, key) {return target[key] ?? ((...args) => calls.push([key, ...args]));},
  });
  const canvas = {width, height: width * .8, getContext: () => context, addEventListener() {},
    getBoundingClientRect: () => ({width:cssWidth, height:cssWidth * .8})};
  const map = new TacticalMinimap(canvas);
  map.buildBackgroundLayer = () => ({});
  const paint = observation => {
    calls.length = 0;
    map.render({id:'airport', half_m:4000}, {observation});
    return calls;
  };
  return {map, paint};
}

test('both chart sizes place the same readable marker at GNSS, with independent ground track', () => {
  for (const [width, cssWidth] of [[540, 270], [960, 720]]) {
    const {map, paint} = mapFixture(width, cssWidth);
    for (const zoom of [.12, .5, 1]) {
      map.zoom = zoom;
      const calls = paint(phantom), scale = width / cssWidth;
      const projection = map.getProjection();
      assert.deepEqual(calls.find(c => c[0] === 'translate'), ['translate', projection.px(100)/scale, projection.py(40)/scale]);
      assert.deepEqual(calls.find(c => c[0] === 'rotate'), ['rotate', Math.PI/2]);
      assert.ok(calls.some(c => c[0] === 'lineTo' && c[1] === 0 && c[2] === -projection.scaleM(6)/scale));
      assert.ok(calls.some(c => c[0] === 'moveTo' && c[2] === -11));
      assert.ok(calls.some(c => c[0] === 'fillText' && c[1] === 'Your aircraft'));
    }
    map.center = [50000, 40];
    const off = paint(phantom);
    assert.deepEqual(off.find(c => c[0] === 'translate'), ['translate', 12, cssWidth*.4]);
    assert.deepEqual(off.find(c => c[0] === 'rotate'), ['rotate', -Math.PI/2]);
    assert.ok(off.some(c => c[0] === 'fillText' && c[1] === 'Aircraft off map'));
    assert.ok(!paint(null).some(c => c[0] === 'fillText' && c[1].includes('aircraft')));
  }
});
