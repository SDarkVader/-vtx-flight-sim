// Deterministic, render-only traffic in the existing physical world's coordinates.
// The inner runway is used because the visual 1432 m runway exceeds the
// physical +/-500 m heightfield. All actors stay inside a 480 m envelope.
import {buildRideJourney} from './visual-ride-journeys.js';
import {buildRideTrajectory,sampleRideTrajectory,inspectRideClearance,sampleTerrainHeight} from './ride-trajectory.js';
import {LAYOUT} from './layout.js';
import {DEFAULT_VISUAL_MODEL,vehicleModel} from './vehicle-registry.js';

const AIRCRAFT=[
 {id:'a10-primary',modelId:DEFAULT_VISUAL_MODEL,route:'standard',direction:'left',stand:[-45,-50]},
 {id:'r6-flight',modelId:'r6',route:'holding',direction:'left',runwayId:'03/21',alternateIndex:0,stand:[190,-90]},
 {id:'r6-training',modelId:'r6',route:'training',direction:'right',stand:[-15,-50]},
 {id:'r6-teardrop',modelId:'r6',route:'teardrop',direction:'left',runwayId:'03/21',alternateIndex:1,stand:[220,-90]},
 {id:'r6-go-around',modelId:'r6',route:'go-around',direction:'left',runwayId:'03/21',alternateIndex:2,stand:[250,-90]}
];
const ease=u=>u*u*(3-2*u), clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
const collide=(a,b,pad=6)=>a[0]<b[1]+pad&&b[0]<a[1]+pad;
function taxiSeconds(actor){
 if(actor.runwayId==='03/21')return 12+8+actor.alternateIndex*4;
 const lane=Math.max(12,Math.abs(actor.stand[0]+90)/5);
 const queue=Math.max(8,Math.abs((-25-15*actor.index)+35)/5);
 return 6+lane+queue+2+8;
}
function runwaySchedule(aircraft){
 const occupied=[],returns=[],items=[];
 for(let i=0;i<aircraft.length;i++){
  const actor=aircraft[i],duration=actor.route.duration;
  let departure=38+i*20;
  // Reserve runway entry/takeoff and landing, including a six-second wake gap.
  while(true){
   const entry=actor.runwayId==='03/21'?8+actor.alternateIndex*4:8;
   const slots=[[departure-entry,departure+10],[departure+duration-12,departure+duration+4]];
   const outbound=[departure-taxiSeconds(actor),departure-entry];
   if(!slots.some(slot=>occupied.some(other=>collide(slot,other)))&&
      !returns.some(other=>collide(outbound,other,0))){
    occupied.push(...slots);returns.push([departure+duration,departure+duration+(actor.runwayId==='03/21'?76:51)]);
    items.push({departure,arrival:departure+duration});break;
   }
   departure+=4;
  }
 }
 return {items,occupied,cycle:Math.ceil((Math.max(...items.map((i,n)=>i.arrival+(aircraft[n].runwayId==='03/21'?80:55))))/20)*20};
}
function groundPose(a,b,t,duration,z){
 const u=clamp(t/duration,0,1),s=ease(u),ds=6*u*(1-u)/duration;
 const dx=b[0]-a[0],dy=b[1]-a[1],startZ=a[2]??z,dz=(b[2]??z)-startZ;
 return {position:[a[0]+dx*s,a[1]+dy*s,startZ+dz*s],velocity:[dx*ds,dy*ds,dz*ds],heading:Math.atan2(dy,dx),pitch:0,bank:0,speed:Math.hypot(dx,dy,dz)*ds};
}
function fixedPose(point,heading=0){return {position:[...point],velocity:[0,0,0],heading,pitch:0,bank:0,speed:0};}
function routePose(route,time){
 const p=sampleRideTrajectory(route,clamp(time,0,route.duration));
 const before=sampleRideTrajectory(route,clamp(time-.05,0,route.duration));
 const after=sampleRideTrajectory(route,clamp(time+.05,0,route.duration));
 const d=Math.max(.001,after.time-before.time);
 return {...p,velocity:p.position.map((v,i)=>(after.position[i]-before.position[i])/d),operation:time<15?'takeoff':time>route.duration-16?'landing':time>route.duration-36?'approach':'circuit'};
}
function sampleAircraft(actor,t,cycle){
 const {departure,arrival}=actor.schedule,stand=[...actor.stand,actor.ground+actor.cgHeight],alternate=actor.runwayId==='03/21';
 const hold=alternate?[180,-70,stand[2]]:[-90,-25-15*actor.index,stand[2]];
 const runwayStart=actor.route.points[0],runwayEnd=actor.route.points.at(-1),local=((t%cycle)+cycle)%cycle;
 let pose,operation;
 const laneY=-35;
 const laneStart=[actor.stand[0],laneY,stand[2]],queue=[-90,laneY,stand[2]];
 const laneSeconds=Math.max(12,Math.abs(actor.stand[0]+90)/5);
 const queueSeconds=Math.max(8,Math.abs(hold[1]+35)/5);
 const taxiStart=departure-(6+laneSeconds+queueSeconds+2+8);
 if(alternate){
  const entry=8+actor.alternateIndex*4,short=[actor.stand[0],-70,stand[2]],start=departure-entry-12;
  if(local<start){pose=fixedPose(stand);operation='stand';}
  else if(local<start+8){pose=groundPose(stand,short,local-start,8,stand[2]);operation='taxi';}
  else if(local<departure-entry){pose=fixedPose(short);operation='hold short';}
  else if(local<departure){pose=groundPose(short,runwayStart,local-(departure-entry),entry,stand[2]);operation='runway entry';}
  else if(local<=arrival){pose=routePose(actor.route,local-departure);operation=pose.operation;}
  else if(local<arrival+76){
   const exit=[350,75,stand[2]],turn=[350,-60,stand[2]],lane=[actor.stand[0],-60,stand[2]],u=local-arrival;
   pose=u<10?groundPose(runwayEnd,exit,u,10,stand[2]):u<43?groundPose(exit,turn,u-10,33,stand[2]):u<68?groundPose(turn,lane,u-43,25,stand[2]):groundPose(lane,stand,u-68,8,stand[2]);operation='taxi to stand';
  }else{pose=fixedPose(stand);operation='stand';}
 }
 else if(local<taxiStart){pose=fixedPose(stand);operation='stand';}
 else if(local<taxiStart+6){pose=groundPose(stand,laneStart,local-taxiStart,6,stand[2]);operation='taxi';}
 else if(local<taxiStart+6+laneSeconds){pose=groundPose(laneStart,queue,local-taxiStart-6,laneSeconds,stand[2]);operation='taxi';}
 else if(local<departure-10){pose=groundPose(queue,hold,local-(taxiStart+6+laneSeconds),queueSeconds,stand[2]);operation='taxi';}
 else if(local<departure-8){pose=fixedPose(hold,Math.atan2(-hold[1],runwayStart[0]-hold[0]));operation='hold short';}
 else if(local<departure){pose=groundPose(hold,runwayStart,local-(departure-8),8,stand[2]);operation='runway entry';}
 else if(local<=arrival){pose=routePose(actor.route,local-departure);operation=pose.operation;}
 else if(local<arrival+51){
  // Return along the south service lane, then turn into the assigned stand;
  // never drive through another parked aircraft's occupied stand.
  const u=local-arrival;
  const exit=[130,-27,stand[2]],lane=[actor.stand[0],-27,stand[2]];
  pose=u<8?groundPose(runwayEnd,exit,u,8,stand[2]):u<43?groundPose(exit,lane,u-8,35,stand[2]):groundPose(lane,stand,u-43,8,stand[2]);operation='taxi to stand';
 }else {pose=fixedPose(stand);operation='stand';}
 return {...pose,operation,routeId:actor.routeId,runwayId:actor.runwayId||'08/26',modelId:actor.modelId,vehicleId:actor.id,mode:'scripted',animationTime:Math.max(0,local-(departure-18))};
}
function sampleGround(actor,t,world){
 const points=actor.points,legs=points.length-1,period=legs*16*2+10,u=((t+actor.offset)%period+period)%period;
 let a,b,legT;
 if(u<legs*16){const i=Math.min(legs-1,Math.floor(u/16));a=points[i];b=points[i+1];legT=u-i*16;}
 else if(u<legs*32){const i=Math.min(legs-1,Math.floor((u-legs*16)/16));a=points[legs-i];b=points[legs-i-1];legT=u-legs*16-i*16;}
 else {a=points[0];b=a;legT=0;}
 const z=sampleTerrainHeight(world,a[0],a[1])+1;
 return {...groundPose(a,b,legT,16,z),operation:'ground service',routeId:actor.road,modelId:actor.modelId,vehicleId:actor.id,mode:'scripted'};
}
export function createAirportOperations(world){
 if(!world||world.half_m<480)throw Error('Airport traffic requires the 500 m physical terrain');
 const aircraft=AIRCRAFT.map((spec,index)=>{
  const model=vehicleModel(spec.modelId),journey=buildRideJourney(spec.route,spec.direction,model.cgLocal[2],spec.runwayId||'08/26');
  const route=buildRideTrajectory(journey.points,{cruiseSpeed:journey.speed});
  if(spec.runwayId==='03/21')route.terrainFollowWorld=world;
  const clearance=inspectRideClearance(route,world,{runwayId:spec.runwayId||'08/26',horizontalMargin:Math.max(8,model.dimensions_m[1]/2+4),verticalMargin:Math.max(5,model.dimensions_m[2]+3)});
  if(!clearance.ok)throw Error(`${spec.id} route unsafe: ${clearance.failures[0].reason}`);
  return {...spec,index,route,routeId:spec.route,cgHeight:model.cgLocal[2],ground:sampleTerrainHeight(world,...spec.stand),clearance};
 });
 const schedule=runwaySchedule(aircraft);aircraft.forEach((actor,i)=>actor.schedule=schedule.items[i]);
 const ground=[];
 const all=[...aircraft,...ground];
 let density=all.length;
 return {
  actors:all,aircraft,ground,cycle:schedule.cycle,runwaySlots:schedule.occupied,
  setDensity(value){density=clamp(Math.round(Number(value)||0),2,all.length);},
  get density(){return density;},
  sample(id,time){const a=all.find(actor=>actor.id===id);if(!a)throw Error('Unknown vehicle '+id);return aircraft.includes(a)?sampleAircraft(a,time,schedule.cycle):sampleGround(a,time,world);},
  isVisible(id){return all.findIndex(a=>a.id===id)<density;}
 };
}

// Sample full vehicle envelopes rather than centre points. Ground service
// roads are trimmed before walls and the inner runway is the only active one.
export function inspectFleetSafety(operations,world,{step=.5,margin=2}={}){
 const failures=[];
 for(let t=0;t<operations.cycle;t+=step){
  const states=operations.actors.map(actor=>{
   const model=vehicleModel(actor.modelId),pose=operations.sample(actor.id,t);
   const [length,width,height]=model.dimensions_m;
   return {actor,pose,radius:Math.hypot(length/2,width/2),height};
  });
  for(const state of states){
   const [x,y,z]=state.pose.position;
   if(Math.max(Math.abs(x),Math.abs(y))+state.radius>=world.half_m-10)failures.push({t,id:state.actor.id,reason:'bounds'});
   for(const obstacle of world.obstacles){
    const [ox,oy,oz]=obstacle.center,[hx,hy,hz]=obstacle.half;
    const dx=Math.max(0,Math.abs(x-ox)-hx),dy=Math.max(0,Math.abs(y-oy)-hy);
    if(Math.hypot(dx,dy)<state.radius+margin&&z-state.height/2<oz+hz+1){
     failures.push({t,id:state.actor.id,reason:'obstacle',obstacle:obstacle.id});break;
    }
   }
  }
  for(let i=0;i<states.length;i++)for(let j=i+1;j<states.length;j++){
   const a=states[i],b=states[j],pa=a.pose.position,pb=b.pose.position;
   if(Math.hypot(pa[0]-pb[0],pa[1]-pb[1])<a.radius+b.radius+margin&&
      Math.abs(pa[2]-pb[2])<(a.height+b.height)/2+margin)
    failures.push({t,reason:'separation',a:a.actor.id,b:b.actor.id});
  }
  if(failures.length>=20)break;
 }
 return {ok:failures.length===0,failures};
}
