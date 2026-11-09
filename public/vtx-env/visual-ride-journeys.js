// Deterministic passenger-demo flight plans. No control of Colin's physical aircraft.
// Uses the flat central 08/26 runway for both the ground roll and touchdown.
// Curves and swept-envelope checks are performed in ride-trajectory.js.
import {holdingPattern,teardropEntry,missedApproach} from './visual-air-routes.js';
import {LAYOUT} from './layout.js';
export const RIDE_JOURNEYS=Object.freeze([
 {id:'standard',label:'Airport circuit',peak:125,lateral:235,speed:22},
 {id:'training',label:'Training circuit',peak:110,lateral:205,speed:20},
 {id:'scenic',label:'High scenic circuit',peak:165,lateral:265,speed:22},
 {id:'extended',label:'Extended circuit',peak:145,lateral:255,speed:21},
 {id:'holding',label:'Holding pattern + arrival',peak:125,lateral:235,speed:20,procedure:'hold'},
 {id:'teardrop',label:'Teardrop entry + arrival',peak:125,lateral:235,speed:20,procedure:'teardrop'},
 {id:'go-around',label:'Missed approach + return',peak:125,lateral:235,speed:21,procedure:'missed'}
]);
export function buildRideJourney(id='standard',direction='left',cgHeight=.5529781802070567,runwayId='08/26'){
 const spec=RIDE_JOURNEYS.find(r=>r.id===id);
 if(!spec)throw Error('Unknown A10 journey');
 if(!['left','right'].includes(direction))throw Error('Choose left/right circuit');
 if(!Number.isFinite(cgHeight))throw Error('Invalid CG height');
 const side=direction==='left'?1:-1;
 const {peak,lateral,speed}=spec;
 // Position coordinates are X east / Y north / Z up, metres. Low runway
 // segments remain on the central flat airfield, not the raised scenic roads.
 const raw=[
  [-115,0,0],[-92,0,0],[-58,0,0],[-8,0,0],[55,0,0],
  [135,0,12],[205,0,65],[265,side*58,peak*.86],
  [280,side*(lateral*.60),peak],
  [235,side*lateral,peak],
  [115,side*lateral,peak],
  [-120,side*lateral,peak],
  [-237,side*lateral*.80,peak*.96],
  [-272,side*lateral*.40,peak*.83],
  [-238,side*25,peak*.70],
  [-205,0,82],[-170,0,62],[-122,0,40],[-65,0,17],
  [20,0,0],[130,0,0]
 ];
 if(spec.procedure==='hold'){
  const hold=holdingPattern({fix:[-120,lateral,peak],headingDeg:270,legLength:170,width:80});
  // Round the rectangular guide into a continuous racetrack loop. Starting
  // and ending tangent is westbound, matching the downwind circuit.
  const radius=(hold.points[0][0]-hold.points[1][0])/2;
  raw.splice(12,0,...Array.from({length:24},(_,i)=>{
   const a=Math.PI/2+2*Math.PI*(i+1)/24;
   return [-120+radius*Math.cos(a),side*(lateral-80+80*Math.sin(a)),peak];
  }));
 }
 if(spec.procedure==='teardrop'){
  const entry=teardropEntry({fix:[-120,lateral,peak],inboundHeadingDeg:270,length:130,offsetDeg:30});
  const length=Math.hypot(entry.points[1][0]+120,entry.points[1][1]-lateral);
  raw.splice(12,0,...Array.from({length:28},(_,i)=>{
   const a=2*Math.PI*(i+1)/28;
   return [-120-length*Math.sin(a)*(.75+.25*Math.cos(a)),side*(lateral-75*(1-Math.cos(a))),peak];
  }));
 }
 if(spec.procedure==='missed'){
  const climb=missedApproach({height:peak,extension:95,usableHalfLength:250}).points;
  raw.splice(19,2,...climb.slice(1),[375,side*18,peak],[380,side*70,peak],[340,side*150,peak],[280,side*210,peak],[235,side*lateral,peak],[-120,side*lateral,peak],[-237,side*lateral*.80,peak*.96],[-272,side*lateral*.40,peak*.83],[-238,side*25,peak*.70],[-205,0,82],[-170,0,62],[-122,0,40],[-65,0,17],[20,0,0],[130,0,0]);
 }
 const runway=LAYOUT.runways.find(r=>r.id===runwayId&&r.status==='open');
 if(!runway)throw Error('Unknown or closed arrival runway');
 // The active portion of 03/21 is kept inside the physical 500 m terrain.
 // The complete procedural graph (departure, hold and approach) uses the same
 // transform, so aircraft do not jump between unrelated route fragments.
 const scale=runwayId==='08/26'?1:.6, angle=runwayId==='08/26'?0:55*Math.PI/180;
 const c=Math.cos(angle),s=Math.sin(angle);
 const points=raw.map(([x,y,z])=>[runway.center[0]+scale*(x*c-y*s),runway.center[1]+scale*(x*s+y*c),z+cgHeight]);
 // Legacy renderer accepts per-point speeds; a smooth ride uses the same
 // geometry but evaluates time-continuous position and attitude instead.
 const waypoints=points.map((position,i)=>{
  const d=i?Math.hypot(...position.map((v,k)=>v-points[i-1][k])):0;
  return {position,speed:i===0||i===points.length-1?0:speed,
   duration:i?Math.max(1.1,d/speed):0};
 });
 return {id,label:spec.label,direction,runwayId,points,waypoints,speed};
}
