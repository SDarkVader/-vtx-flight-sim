import assert from 'node:assert/strict';
import {circularPath, stoppingDistance, stepGroundVehicle} from '../public/vtx-env/traffic-path.js';
const path=circularPath({center:[60,45], radius:12, elevation:2, speedLimit:3});
assert.deepEqual(path.sample(0).position,[72,45,2]);
assert.ok(Math.abs(path.sample(Math.PI*6).heading-Math.PI)<1e-10);
assert.equal(stoppingDistance(6,3),6);
const spec={acceleration:1,braking:1.5,minTurnRadius:8,maxLateralAcceleration:1.2,length:2.6,width:1.3,cgOffset:0};
let state={distance:0,speed:0};
for(let i=0;i<100;i++){const prev=state;state=stepGroundVehicle(state,path,spec,.1,3);assert.ok(state.speed-prev.speed<=.10000001);assert.ok(state.speed<=3);}
assert.ok(state.distance>0);
for(let i=0;i<30;i++){const prev=state;state=stepGroundVehicle(state,path,spec,.1,0);assert.ok(prev.speed-state.speed<=.15000001);}
assert.equal(state.speed,0);
assert.throws(()=>stepGroundVehicle(state,path,{...spec,minTurnRadius:13},.1,3));
console.log('Ground path acceleration, braking, pose and steering checks passed');
