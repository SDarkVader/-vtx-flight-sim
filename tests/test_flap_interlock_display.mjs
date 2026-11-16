import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {test} from 'node:test';

const source = await readFile(new URL('../public/flap-interlock.js', import.meta.url));
const {flapInterlockMessage} = await import('data:text/javascript;base64,' + source.toString('base64'));
test('the cockpit explains actual flap interlocks without inventing a limit', () => {
  assert.equal(flapInterlockMessage({reasons:['airspeed_limit',null],max_speed_m_s:75}),
    'Flaps limited to zero: airspeed limit (75 m/s).');
  assert.equal(flapInterlockMessage({reasons:['wing_unlocked','wing_unlocked']}),
    'Flaps held at zero: wing not locked.');
  assert.equal(flapInterlockMessage({reasons:[null,null]}), '');
  assert.equal(flapInterlockMessage(null), '');
});
