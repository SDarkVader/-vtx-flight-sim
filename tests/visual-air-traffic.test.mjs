import assert from 'node:assert/strict';
import {runwayCircuit,scheduleVisualRoute} from '../public/vtx-env/visual-air-routes.js';
import {buildTrafficRoute,sampleTrafficRoute} from '../public/vtx-env/traffic-path.js';
import {createVisualAirTraffic} from '../public/vtx-env/visual-air-traffic.js';
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
const transforms=[];
class FakeVector{constructor(...v){this.v=v;}set(...v){this.v=v;return this;}}
class FakeQuat{setFromAxisAngle(){return this;}copy(){return this;}multiply(){return this;}}
class FakeGroup{constructor(){this.position=new FakeVector();this.quaternion=new FakeQuat();this.children=[];}add(x){this.children.push(x);}clear(){this.children=[];}}
const THREE={Group:FakeGroup,Vector3:FakeVector,Quaternion:FakeQuat};
class Loader{load(url,onLoad){assert.equal(url,'/assets/phantom-a10.glb');onLoad({scene:new FakeGroup()});}}
const scene={add:o=>transforms.push(o),remove:()=>{}};
let updates=0,attached=0;
const traffic=createVisualAirTraffic({THREE,GLTFLoader:Loader,scene,aircraft:[{
 id:'test',asset:'/assets/phantom-a10.glb',cgLocal:cg,waypoints,
 onLoad:()=>{attached++;return {test:true};},onUpdate:(rig,p)=>{assert.equal(rig.test,true);assert.ok(p.speed>=0);updates++;}
}]});
assert.equal(attached,1);
const t=10;
traffic.update(t);
const positionAtT=transforms[0].position.v;
traffic.update(t+route.duration);
assert.deepEqual(transforms[0].position.v,positionAtT,'non-deterministic replay');
assert.equal(updates,2);
assert.deepEqual(transforms[0].children[0].children[0].position.v,cg.map(v=>-v),'CG not at rotation pivot');
traffic.dispose();
console.log('Visual aircraft route bounds, CG pivot, timing, deterministic sampling and render wiring passed');
