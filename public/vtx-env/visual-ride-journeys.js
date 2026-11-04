// Deterministic passenger-demo flight plans. No control of Colin's physical aircraft.
// Uses the flat central 08/26 runway for both the ground roll and touchdown.
// Curves and swept-envelope checks are performed in ride-trajectory.js.
export const RIDE_JOURNEYS=Object.freeze([
 {id:'standard',label:'Airport circuit',peak:125,lateral:235,speed:35},
 {id:'training',label:'Training circuit',peak:110,lateral:205,speed:30},
 {id:'scenic',label:'High scenic circuit',peak:165,lateral:265,speed:34},
 {id:'extended',label:'Extended circuit',peak:145,lateral:255,speed:32}
]);
export function buildRideJourney(id='standard',direction='left',cgHeight=.5529781802070567){
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
 const points=raw.map(([x,y,z])=>[x,y,z+cgHeight]);
 // Legacy renderer accepts per-point speeds; a smooth ride uses the same
 // geometry but evaluates time-continuous position and attitude instead.
 const waypoints=points.map((position,i)=>{
  const d=i?Math.hypot(...position.map((v,k)=>v-points[i-1][k])):0;
  return {position,speed:i===0||i===points.length-1?0:speed,
   duration:i?Math.max(1.1,d/speed):0};
 });
 return {id,label:spec.label,direction,points,waypoints,speed};
}
