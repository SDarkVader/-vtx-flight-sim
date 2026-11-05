import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import './visual-phantom-animation.test.mjs';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {runwayCircuit,scheduleVisualRoute} from '../public/vtx-env/visual-air-routes.js';
import {buildTrafficRoute,sampleTrafficRoute} from '../public/vtx-env/traffic-path.js';
import {createVisualAirTraffic,clearOfPhysicalAircraft} from '../public/vtx-env/visual-air-traffic.js';
assert.equal(clearOfPhysicalAircraft([0,0,1],[0,0,0]),false);
assert.equal(clearOfPhysicalAircraft([20,0,1],[0,0,0]),true);
assert.equal(clearOfPhysicalAircraft([0,0,20],[0,0,0]),true);
assert.equal(clearOfPhysicalAircraft([0,0,1],null),true);
import {RIDE_JOURNEYS,buildRideJourney} from '../public/vtx-env/visual-ride-journeys.js';
import {buildRideTrajectory,sampleRideTrajectory,inspectRideClearance} from '../public/vtx-env/ride-trajectory.js';
// Offline Vercel previews must have a versioned, parseable world snapshot.
// The GLB must be INCLUDED in a Vercel Git deployment. An unanchored
// assets/ rule once excluded public/assets/** and silently stalled mobile.
const rootDir=fileURLToPath(new URL('../',import.meta.url));
const glb=readFileSync(new URL('../public/assets/phantom-a10.glb',import.meta.url));
assert.ok(glb.length>100000 && glb.readUInt32LE(0)===0x46546c67,'A10 GLB absent/invalid');
const ignoreModel=spawnSync('git',['-c','core.excludesFile=.vercelignore','check-ignore','-q','--no-index','public/assets/phantom-a10.glb'],{cwd:rootDir});
assert.equal(ignoreModel.status,1,'Vercel excludes the actual A10 GLB from the deployment');
const ignoreSource=spawnSync('git',['-c','core.excludesFile=.vercelignore','check-ignore','-q','--no-index','assets/offline-cad.blend'],{cwd:rootDir});
assert.equal(ignoreSource.status,0,'Vercel must still exclude the bulky root CAD assets');
const snapshot=JSON.parse(readFileSync(new URL('../public/vtx-env/ride-world.json',import.meta.url),'utf8'));
assert.equal(snapshot.half_m,500);
assert.equal(snapshot.heights_m.length,101);
assert.equal(snapshot.obstacles.length,38);
assert.ok(snapshot.heights_m.every(row=>row.length===101&&row.every(Number.isFinite)));
const frontend=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
assert.match(frontend,/fetch\('\/vtx-env\/ride-world\.json/);
assert.match(frontend,/if\(world&&!window\.__vtxNoRender\)renderer\.render/);
const circuit=runwayCircuit();
const cg=[-.15156246846624952,.00004531509472356366,.5529781802070567];
const pts=circuit.points.map(p=>[p[0],p[1],p[2]+cg[2]]);
assert.equal(pts.length,10);
for(const p of pts){assert.ok(Math.abs(p[0])<500&&Math.abs(p[1])<500,'preview outside world');}
assert.throws(()=>runwayCircuit({runwayId:'18/36'}));
const easy=scheduleVisualRoute(circuit.points,{cruiseSpeed:20,difficulty:'easy'});
const hard=scheduleVisualRoute(circuit.points,{cruiseSpeed:20,difficulty:'hard'});
assert.ok(easy.duration>hard.duration);
const speeds=[0,42,80,80,70,60,60,50,40,0];
const waypoints=pts.map((p,i)=>({position:p,speed:speeds[i],duration:i===0?0:Math.max(.25,2*Math.hypot(...p.map((v,j)=>v-pts[i-1][j]))/(speeds[i-1]+speeds[i]))}));
const route=buildTrafficRoute(waypoints);
for(let t=0;t<route.duration;t+=.25){
 const p=sampleTrafficRoute(route,t);
 assert.ok(p.position.every(Number.isFinite)&&Number.isFinite(p.speed),'nonfinite traffic pose');
 assert.ok(p.speed>=0,'negative speed');
}
for(const choice of RIDE_JOURNEYS){
 const left=buildRideJourney(choice.id,'left',cg[2]);
 const right=buildRideJourney(choice.id,'right',cg[2]);
 assert.equal(left.waypoints.length,right.waypoints.length);
 for(let i=0;i<left.waypoints.length;i++){
   const l=left.waypoints[i].position,r=right.waypoints[i].position;
   assert.ok(Math.abs(l[0])<500&&Math.abs(l[1])<500,'route outside terrain');
   assert.deepEqual([r[0],r[2]],[l[0],l[2]],'mirrored route changes altitude or runway');
   assert.ok(Math.abs(r[1]+l[1])<1e-9,'wrong hand is not mirrored');
 }
}
assert.throws(()=>buildRideJourney('unknown'));
assert.throws(()=>buildRideJourney('standard','up'));
// Every journey and both directions must remain within the modelled world,
// clearing raised terrain and every collider with inflated A10 body margins.
// A C1 spline cannot instantaneously rotate at a waypoint; continuous tangents
// and terminal zero speed are exercised at dense samples.
for (const spec of RIDE_JOURNEYS) for(const direction of ['left','right']){
 const plan=buildRideJourney(spec.id,direction,cg[2]);
 const smooth=buildRideTrajectory(plan.points,{cruiseSpeed:plan.speed});
 const audit=inspectRideClearance(smooth,snapshot);
 assert.equal(audit.totalFailures,0,JSON.stringify({route:spec.id,direction,fail:audit.failures}));
 assert.ok(audit.minAirClearance>20,'unsafe airborne terrain clearance');
 assert.ok(audit.maxHeadingStep<.09,'abrupt heading increment along smooth route');
 const start=sampleRideTrajectory(smooth,0),end=sampleRideTrajectory(smooth,smooth.duration);
 assert.ok(start.speed<1e-5&&end.speed<1e-5,'takeoff/landing must start and stop from rest');
 assert.ok(Math.abs(start.position[2]-cg[2])<1e-9,'departure should be on runway');
 assert.ok(Math.abs(end.position[2]-cg[2])<1e-9,'landing should be on runway');
 const early=sampleRideTrajectory(smooth,1);
 assert.ok(early.position[0]>start.position[0]&&early.speed>0,'no smooth takeoff ground acceleration');
 assert.ok(Math.abs(early.position[2]-start.position[2])<.1,'takeoff must roll before climbing');
 // Sample continuously across every segment join; no teleport in position.
 for(let i=0;i<smooth.segments.length-1;i++){
  const join=smooth.segments[i].start+smooth.segments[i].duration;
  const before=sampleRideTrajectory(smooth,join-.001),after=sampleRideTrajectory(smooth,join+.001);
  assert.ok(Math.hypot(...before.position.map((v,k)=>v-after.position[k]))<.3,'position jumps at waypoint');
  const angle=Math.atan2(Math.sin(after.heading-before.heading),Math.cos(after.heading-before.heading));
  assert.ok(Math.abs(angle)<.015,'heading jumps at waypoint');
 }
}
// Test failure detection on intentional incursions into the tower and raised terrain.
const tower=buildRideTrajectory([[100,115,1],[110,115,1],[120,115,1],[130,115,1]]);
assert.ok(inspectRideClearance(tower,snapshot).failures.some(x=>x.reason==='obstacle'&&x.id==='tower'));
const hillside=buildRideTrajectory([[330,330,1],[360,330,1],[390,330,1],[420,330,1]]);
assert.ok(inspectRideClearance(hillside,snapshot).failures.some(x=>x.reason==='terrain'));

const transforms=[];
class FakeVector{constructor(...v){this.v=v;}set(...v){this.v=v;return this;}}
class FakeQuat{setFromAxisAngle(){return this;}copy(){return this;}multiply(){return this;}}
class FakeGroup{constructor(){this.position=new FakeVector();this.quaternion=new FakeQuat();this.children=[];}add(x){this.children.push(x);}clear(){this.children=[];}clone(){return new FakeGroup();}}
const THREE={Group:FakeGroup,Vector3:FakeVector,Quaternion:FakeQuat};
let loads=0;
class Loader{load(url,onLoad){assert.equal(url,'/assets/phantom-a10.glb');loads++;onLoad({scene:new FakeGroup()});}}
const scene={add:o=>transforms.push(o),remove:()=>{}};
let updates=0,attached=0;
const traffic=createVisualAirTraffic({THREE,GLTFLoader:Loader,scene,aircraft:[{
 id:'test',asset:'/assets/phantom-a10.glb',cgLocal:cg,waypoints,
 onLoad:()=>{attached++;return {test:true};},onUpdate:(rig,p)=>{assert.equal(rig.test,true);assert.ok(p.speed>=0);updates++;}
}]});
await new Promise(setImmediate);
assert.equal(attached,1);
const t=10;
traffic.update(t);
const positionAtT=transforms[0].position.v;
traffic.update(t+route.duration);
assert.deepEqual(transforms[0].position.v,positionAtT,'non-deterministic replay');
assert.equal(updates,2);
traffic.setWaypoints('test',buildRideJourney('scenic','right',cg[2]).waypoints);
traffic.update(10);
assert.ok(transforms[0].position.v[0]!==positionAtT[0],'changing journey did not update aircraft');
assert.throws(()=>traffic.setWaypoints('nonexistent',waypoints));
assert.deepEqual(transforms[0].children[0].children[0].position.v,cg.map(v=>-v),'CG not at rotation pivot');
// A passenger flight must stop at the last point, not wrap to the first.
const actor2=[];
const stage2={add:o=>actor2.push(o),remove:()=>{}};
const oneShot=createVisualAirTraffic({THREE,GLTFLoader:Loader,scene:stage2,aircraft:[{
 id:'one-shot',asset:'/assets/phantom-a10.glb',cgLocal:cg,waypoints,loop:false
}]});
const smooth2=buildRideTrajectory(buildRideJourney('standard','left',cg[2]).points,{cruiseSpeed:35});
oneShot.setRoute('one-shot',smooth2);
await new Promise(setImmediate);
oneShot.update(smooth2.duration);
const landed=actor2[0].position.v;
oneShot.update(smooth2.duration+2);
assert.deepEqual(actor2[0].position.v,landed,'end of passenger ride loops/teleports');
oneShot.dispose();
traffic.dispose();
const beforeLoads=loads;
let prepared=0;
const shared=createVisualAirTraffic({THREE,GLTFLoader:Loader,scene,aircraft:[
 {id:'r6-a',asset:'/assets/phantom-a10.glb',cgLocal:cg,waypoints,prepareSource:()=>prepared++},
 {id:'r6-b',asset:'/assets/phantom-a10.glb',cgLocal:cg,waypoints,prepareSource:()=>prepared++}
]});
await new Promise(setImmediate);
assert.equal(loads,beforeLoads+1,'shared GLB should load once');
assert.equal(prepared,1,'shared R6 appearance should be prepared once before cloning');
assert.notEqual(shared.getActor('r6-a').pivot.children[0],shared.getActor('r6-b').pivot.children[0],'aircraft must have separate transforms');
shared.dispose();
console.log('Visual aircraft route bounds, CG pivot, timing, deterministic sampling and render wiring passed');
