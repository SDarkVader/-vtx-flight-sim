import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createAirportOperations,inspectFleetSafety} from '../public/vtx-env/airport-operations.js';
const world=JSON.parse(readFileSync(new URL('../public/vtx-env/ride-world.json',import.meta.url)));
const fleet=createAirportOperations(world,{maxAircraft:10});assert.equal(fleet.actors.length,10);assert.equal(new Set(fleet.actors.map(a=>a.id)).size,10);
for(let count=0;count<=10;count++){fleet.setDensity(count);const visible=fleet.actors.filter(a=>fleet.isVisible(a.id));assert.equal(visible.length,count);if(count>=2){assert.ok(visible.some(a=>a.modelId==='r6'));assert.ok(visible.some(a=>a.modelId.startsWith('phantom')));}}
for(const actor of fleet.actors)for(const t of [0,80,160,fleet.cycle-1]){const pose=fleet.sample(actor.id,t);assert.ok(pose.position.every(Number.isFinite));assert.deepEqual(fleet.sample(actor.id,t),pose,'scheduled scenery is deterministic');}
const safety=inspectFleetSafety(fleet,world,{step:.5});assert.ok(safety.ok,JSON.stringify(safety.failures.slice(0,5)));
