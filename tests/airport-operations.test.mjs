import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {createAirportOperations,inspectFleetSafety} from '../public/vtx-env/airport-operations.js';
import {VEHICLE_MODELS,DEFAULT_VISUAL_MODEL} from '../public/vtx-env/vehicle-registry.js';

const world=JSON.parse(readFileSync(new URL('../public/vtx-env/ride-world.json',import.meta.url)));
const airport=createAirportOperations(world);
assert.equal(airport.actors.length,5);
assert.equal(airport.aircraft.length,5);
assert.equal(airport.ground.length,0);
assert.equal(airport.aircraft.filter(a=>a.modelId==='r6').length,4);
assert.equal(VEHICLE_MODELS.r6.sourceRevision,'P0-V4A-assembly-r6');
assert.equal(VEHICLE_MODELS.r6.calibrationId,'ARGON-R6-LIVE-STABILITY-CALIBRATION-20261101');
assert.deepEqual(VEHICLE_MODELS.r6.cgLocal,[-0.0003,0.0792,1.4097]);
const r6=readFileSync(new URL('../public/assets/airframe-r6.glb',import.meta.url));
assert.equal(createHash('sha256').update(r6).digest('hex'),VEHICLE_MODELS.r6.sha256);
const r6Manifest=JSON.parse(r6.subarray(20,20+r6.readUInt32LE(12)).toString());
assert.equal(r6Manifest.meshes.length,731);
for(const name of ['airframe','cabin',...Array.from({length:4},(_,i)=>`rotor${i+1}`),...Array.from({length:6},(_,i)=>`gear${i+1}`)])
 assert.ok(r6Manifest.nodes.some(n=>n.name===name),`R6 ${name} missing`);
assert.ok(airport.aircraft.some(a=>a.runwayId==='03/21'&&a.routeId==='holding'));
assert.ok(airport.aircraft.some(a=>a.runwayId==='03/21'&&a.routeId==='teardrop'));
assert.ok(airport.aircraft.some(a=>a.runwayId==='03/21'&&a.routeId==='go-around'));
assert.ok(airport.aircraft.some(a=>!a.runwayId),'main runway lacks scheduled arrivals');
assert.deepEqual(airport.sample('a10-primary',0).position.slice(0,2),[-45,-50]);
assert.deepEqual(airport.sample('r6-flight',0).position.slice(0,2),[190,-90]);
assert.equal(DEFAULT_VISUAL_MODEL,'phantom-a10-81c823e2');
const current=VEHICLE_MODELS[DEFAULT_VISUAL_MODEL];
const glb=readFileSync(new URL('../public'+current.asset,import.meta.url));
assert.equal(glb.readUInt32LE(0),0x46546c67);
const jsonLength=glb.readUInt32LE(12);
const manifest=JSON.parse(glb.subarray(20,20+jsonLength).toString());
assert.ok(manifest.nodes.length>400&&manifest.animations.length===28,'latest model joint/geometry mismatch');
assert.equal(manifest.nodes.filter(n=>n.extras?.phantom_joint).length,28,'A10 control joints missing');
assert.ok(manifest.materials.some(m=>m.name?.includes('smoked inspection glazing')&&m.alphaMode==='BLEND'),'glass roof is opaque');
for(let i=0;i<airport.runwaySlots.length;i++)for(let j=i+1;j<airport.runwaySlots.length;j++){
 const [a,b]=[airport.runwaySlots[i],airport.runwaySlots[j]];
 assert.ok(a[1]+6<=b[0]||b[1]+6<=a[0],`runway conflict ${i}/${j}`);
}
for(const actor of airport.actors)for(let t=0;t<airport.cycle;t+=.5){
 const pose=airport.sample(actor.id,t),[x,y,z]=pose.position;
 assert.ok([x,y,z,...pose.velocity,pose.heading,pose.speed].every(Number.isFinite),`${actor.id} nonfinite pose`);
 assert.ok(Math.abs(x)<480&&Math.abs(y)<480,`${actor.id} escaped physical terrain`);
 assert.ok(z>=-1,`${actor.id} below terrain`);
}
let peakAirborne=0;
for(let t=0;t<airport.cycle;t+=.5){
 const airborne=airport.aircraft.filter(a=>['takeoff','circuit','approach','landing'].includes(airport.sample(a.id,t).operation)).length;
 peakAirborne=Math.max(peakAirborne,airborne);
}
assert.ok(peakAirborne>=2,'R6 traffic never flies alongside A10');
airport.setDensity(3);
assert.equal(airport.actors.filter(a=>airport.isVisible(a.id)).length,3);
assert.equal(airport.sample('a10-primary',70).mode,'scripted');
const safety=inspectFleetSafety(airport,world);
assert.ok(safety.ok,JSON.stringify(safety.failures));
console.log('Unified airport fleet, versioned A10, terrain containment and runway scheduling passed');
