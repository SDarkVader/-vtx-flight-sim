import assert from 'node:assert/strict';
import {primaryRunwayCues, resolvePrimaryRunway} from '../public/vtx-env/runway-layout.js';
import {TacticalMinimap} from '../public/vtx-env/tactical-minimap.js';

const airport = {id: 'stage1-extended-airfield-recovery', environment: 'airport', version: '5',
  half_m: 4000, seed: 41031, obstacles: [],
  runway: {id: '08/26', x0: -3900, x1: 3900, yc: 0, width: 30,
    shoulder_width: 4, elevation_m: 0, default_start: [-700, 0]}};
const cues = primaryRunwayCues(airport);
assert.deepEqual(cues.runway.default_start, [-700, 0], 'runway extension must preserve established takeoff point');
assert.equal(cues.surface.x - cues.surface.length / 2, -3900);
assert.equal(cues.surface.x + cues.surface.length / 2, 3900);
assert.equal(cues.surface.width, 38, 'painted shoulders must lie beyond the 30 m runway');
assert.deepEqual(cues.papi.map(p => [p.x, p.y]), [[-3600, -24], [3600, 24]], 'PAPI housings must follow both new thresholds');
for (const [x, y, color] of cues.edgeLights) {
  assert.ok(x >= -3900 && x <= 3900 && Math.abs(y) > 15 && Math.abs(y) < 19);
  assert.equal(color, Math.abs(x) > 3600 ? '#ffb822' : '#fff3d0', 'amber lighting must stay within the final 300 m');
}
assert.ok(cues.edgeLights.some(([x]) => x < -3800), 'west extension needs edge lights');
assert.ok(cues.edgeLights.some(([x]) => x > 3800), 'east end needs edge lights');
const green = cues.thresholdLights.filter(([, , color]) => color === '#35e060');
assert.deepEqual([...new Set(green.map(([x]) => x))], [-3899, 3898]);
assert.ok(cues.thresholdLights.every(([x, y]) => x >= -3900 && x <= 3900 && Math.abs(y) < 15));

// Metadata is authoritative even for another valid runway placement; it must
// not be overridden by new-Airport constants or by the visual traffic layout.
const shifted = {...airport, runway: {...airport.runway, x0: -2800, x1: 3200, yc: 40, elevation_m: 7}};
assert.deepEqual(primaryRunwayCues(shifted).surface, {x: 200, y: 40, length: 6000, width: 38, z: 7.021});
assert.deepEqual(resolvePrimaryRunway({}).center, [1592, 0], 'older recordings retain their previous painted bounds');
assert.equal(resolvePrimaryRunway({}).length, 4616);
assert.throws(() => resolvePrimaryRunway({...airport, runway: {...airport.runway, x1: -4000}}), /Invalid/);
assert.throws(() => resolvePrimaryRunway({...airport, runway: {...airport.runway, yc: NaN}}), /Invalid/);

// Exercise the real minimap drawing with an identity projection so assertions
// refer to metres. This catches hard-coded old endpoints in the consumer.
const calls = [];
const context = new Proxy({}, {
  get(target, key) {
    if (key in target) return target[key];
    return (...args) => calls.push({method: key, args, color: target.fillStyle});
  },
  set(target, key, value) {target[key] = value; return true;},
});
const makeCanvas = () => ({width: 900, height: 900, handlers: {}, getContext: () => context,
  getBoundingClientRect:()=>({width:900,height:900}),
  addEventListener(name, handler) {this.handlers[name] = handler;}});
globalThis.document = {createElement: makeCanvas};
const map = new TacticalMinimap(makeCanvas());
const projection = {px: x => x, py: y => -y, scaleM: m => m, w: 900, h: 900, unpx: x => x, unpy: y => -y};
map.buildBackgroundLayer(airport, projection);
assert.ok(calls.some(c => c.method === 'fillRect' && c.args.join() === '-3900,-15,7800,30'));
assert.ok(calls.some(c => c.method === 'fillText' && c.args.join() === '08,-3864,0'));
assert.ok(calls.some(c => c.method === 'fillText' && c.args.join() === '26,3864,0'));
assert.ok(calls.some(c => c.method === 'fillRect' && c.color === '#22e055' && c.args.join() === '-3900,-15,3,30'));
assert.ok(calls.some(c => c.method === 'fillRect' && c.color === '#ff2211' && c.args.join() === '3897,-15,3,30'));
calls.length = 0;
map.buildBackgroundLayer({id: 'stage1-valley', environment: 'sandbox'}, projection);
assert.ok(calls.some(c => c.method === 'fillRect' && c.args.join() === '-950,-21,1900,42'), 'Sandbox runway stays unchanged');
assert.ok(!calls.some(c => c.method === 'fillRect' && c.args.join() === '-3900,-15,7800,30'));

let backgrounds = 0;
const draw = map.buildBackgroundLayer.bind(map);
map.buildBackgroundLayer = (...args) => {backgrounds++; return draw(...args);};
map.render(airport, {});
map.render(airport, {});
assert.equal(backgrounds, 1, 'stable world should use cached map');
map.render({...airport, version: '6', runway: shifted.runway}, {});
assert.equal(backgrounds, 2, 'updated runway/environment must invalidate an existing map');
map.render(airport, {});
const doubleClick = () => map.canvas.handlers.dblclick({preventDefault() {}});
doubleClick();
assert.equal(map.tacticalMode, true);
doubleClick();
assert.equal(map.tacticalMode, false);
assert.equal(map.zoom, .12, 'leaving tactical view must restore the extended-Airport view');
const fitted = map.getProjection(airport.half_m);
for (const x of [-3900, 3900]) assert.ok(fitted.px(x) > 0 && fitted.px(x) < map.canvas.width,
  'both physical runway endpoints must remain on the map after toggling');
map.render({id: 'stage1-valley', environment: 'sandbox', half_m: 1000}, {});
doubleClick(); doubleClick();
assert.equal(map.zoom, 1, 'Sandbox must restore its own view');
assert.deepEqual(map.center, [0, 0]);
map.render({id: 'legacy-airport', half_m: 4000}, {});
doubleClick(); doubleClick();
assert.equal(map.zoom, .5, 'legacy world view must keep its old default');
console.log('Runway endpoints, lighting, legacy fallback, Sandbox isolation and actual minimap contract passed');
