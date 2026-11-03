import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const source=await readFile(new URL('../public/cockpit-axes.js',import.meta.url),'utf8');
const {cockpitAxes,cockpitHorizon}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const near=(x,y)=>assert.ok(Math.abs(x-y)<1e-9,`${x} vs ${y}`);
for (const [heading, forward, right] of [[0,[1,0],[0,-1]],[90,[0,1],[1,0]],[180,[-1,0],[0,1]]]) {
  cockpitAxes(1,0,heading).forEach((v,i)=>near(v,forward[i]));
  cockpitAxes(0,1,heading).forEach((v,i)=>near(v,right[i]));
}
let h=cockpitHorizon([10,0,0]);near(h.pitchDegrees,-10);near(h.bankDegrees,0);
h=cockpitHorizon([0,10,0]);near(h.pitchDegrees,0);near(h.bankDegrees,10);
h=cockpitHorizon([0,0,90]);near(h.pitchDegrees,0);near(h.bankDegrees,0);
assert.throws(()=>cockpitHorizon([NaN,0,0]));
