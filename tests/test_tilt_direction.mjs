import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const source = await readFile(new URL('../public/tilt-direction.js', import.meta.url), 'utf8');
const {tiltFromDirection} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
for (const [angle,x,y] of [[0,20,0],[90,0,20],[180,-20,0],[270,0,-20],[360,20,0]]) {
  const [actualX,actualY]=tiltFromDirection(20,angle);
  assert.ok(Math.abs(actualX-x)<1e-9 && Math.abs(actualY-y)<1e-9, `direction ${angle}`);
}
assert.deepEqual(tiltFromDirection(-1,0),[0,0]);
assert.deepEqual(tiltFromDirection(50,0),[20,0]);
assert.throws(()=>tiltFromDirection(NaN,0));
console.log('Tilt-direction mapping passed');
