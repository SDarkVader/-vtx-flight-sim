import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {airportViewSelection,sceneryPoseAt} from '../public/scenery-view.js';
import {physicalAircraftPosition} from '../public/physical-camera-target.js';
import {clearOfPhysicalAircraft} from '../public/vtx-env/visual-air-traffic.js';

assert.deepEqual(airportViewSelection(),{id:'physical-plant',scenery:false,passenger:false});
assert.deepEqual(airportViewSelection('a10-primary'),{id:'a10-primary',scenery:true,passenger:false});
assert.equal(airportViewSelection('a10-primary',{passenger:true}).passenger,true);
assert.equal(airportViewSelection('r6-training',{passenger:true}).passenger,false);
assert.throws(()=>airportViewSelection('missing'));

// Alternate passenger poses drive BOTH visibility clearance and presentation.
const sampleOperations=()=>({position:[500,500,50],mode:'scripted'});
const sampleRide=(_,time)=>({position:[time,0,1],heading:time/100});
const input={actorId:'a10-primary',time:100,sceneTime:100,rideTime:5,passengerRide:true,rideRoute:{},sampleRide,sampleOperations};
const pose=sceneryPoseAt(input);
assert.deepEqual(pose.position,[5,0,1]);
assert.equal(clearOfPhysicalAircraft(pose.position,[0,0,0]),false);
assert.equal(clearOfPhysicalAircraft(sampleOperations().position,[0,0,0]),true);
assert.equal(sceneryPoseAt({...input,time:100.25}).heading,.0525,'bank lookahead follows passenger time');
assert.deepEqual(sceneryPoseAt({...input,passengerRide:false}).position,[500,500,50]);
assert.deepEqual(sceneryPoseAt({...input,actorId:'r6-training'}).position,[500,500,50]);
assert.deepEqual(physicalAircraftPosition({body_poses:{airframe:{position:[1,2,3]}}}),[1,2,3]);
assert.deepEqual(physicalAircraftPosition({phantom:{},mass:{cg_world_m:[4,5,6]}}),[4,5,6]);
assert.equal(physicalAircraftPosition({body_poses:{airframe:{position:[NaN,0,0]}}}),null);

const app=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
assert.match(app,/selectedVehicleId='physical-plant',passengerRide=false/);
assert.doesNotMatch(app,/actors\.filter\(actor=>actor\.id!=='a10-primary'\)/);
assert.match(app,/clearOfPhysicalAircraft\(poseAt\(sceneTime\)\.position,physical\)/);
assert.match(app,/if\(replayFrames\|\|\(world\?\.environment\|\|currentEnvironment\)!=='airport'\)return false/);
assert.match(app,/if\(model\)model\.visible=modelReady&&loadedAsset===requestedAsset/);
assert.match(app,/SCENERY VIEW · PHYSICAL INSTRUMENTS & CONTROLS/);
const selection=app.slice(app.indexOf(' function selectAirportView('),app.indexOf(" $('airport-aircraft').value='physical-plant'"));
assert.doesNotMatch(selection,/api\(|fetch\(|\/api\/|\$\('airframe'\)|\$\('pilot'\)/);
const traffic=app.slice(app.indexOf('  const specs=airportOperations.actors.map'),app.indexOf('  visualTraffic=createVisualAirTraffic'));
assert.doesNotMatch(traffic,/\$\('loading'\)|\$\('view-sync'\)/,'scenery loading cannot replace physical-ownship identity/status');
const sceneryHud=app.slice(app.indexOf('  if(ridePose){'),app.indexOf(" }else if(visualTraffic&&now-"));
assert.doesNotMatch(sceneryHud,/\$\('(?:cockpit-|alt|vs|speed|fuel|power|angles)/,'scenery cannot supply physical instruments');
console.log('Scenery camera selection, passenger clearance and physical-ownship boundaries passed');
