import {test} from 'node:test';
import assert from 'node:assert/strict';
import {rotorVisualOffset} from '../public/rotor-visual.js';

const omega=1200*2*Math.PI/60;
test('20 Hz samples can alias while intermediate frames reveal actual spin',()=>{
 assert.ok(Math.abs(rotorVisualOffset(omega,50,1,true,false))<1e-12);
 assert.ok(Math.abs(rotorVisualOffset(omega,25,1,true,false)-Math.PI)<1e-12);
 assert.ok(Math.abs(rotorVisualOffset(-omega,25,1,true,false)+Math.PI)<1e-12);
});
test('paused, inactive and unknown speed do not invent motion',()=>{
 for(const args of [[omega,25,1,true,true],[omega,25,1,false,false],[NaN,25,1,true,false],[omega,25,0,true,false]]){
  assert.equal(rotorVisualOffset(...args),0);
 }
});
test('time scale and stale frame prediction are bounded',()=>{
 assert.ok(Math.abs(rotorVisualOffset(omega,40,.25,true,false)-.4*Math.PI)<1e-12);
 assert.equal(rotorVisualOffset(omega,1000,.25,true,false),rotorVisualOffset(omega,120,.25,true,false));
});
