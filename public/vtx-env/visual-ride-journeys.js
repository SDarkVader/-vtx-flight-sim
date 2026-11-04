// Visual-only A10 cockpit journeys. These are simulated routes, not physical flight plans.
// A route/direction change resets the demo to the runway; Colin's aircraft is untouched.
import {runwayCircuit} from './visual-air-routes.js';

export const RIDE_JOURNEYS = Object.freeze([
  {id:'standard', label:'Airport circuit', height:35, extension:55, lateral:110, usableHalfLength:350, speedFactor:1},
  {id:'training', label:'Short training circuit', height:25, extension:25, lateral:75, usableHalfLength:245, speedFactor:.7},
  {id:'scenic', label:'High scenic circuit', height:85, extension:60, lateral:185, usableHalfLength:325, speedFactor:.9},
  {id:'extended', label:'Extended airfield circuit', height:55, extension:70, lateral:155, usableHalfLength:350, speedFactor:.9}
]);

export function buildRideJourney(id='standard', direction='left', cgHeight=.5529781802070567) {
  const spec=RIDE_JOURNEYS.find(route=>route.id===id);
  if(!spec) throw Error('Unknown A10 journey');
  if(direction!=='left'&&direction!=='right') throw Error('Choose a left-hand or right-hand circuit');
  if(!Number.isFinite(cgHeight)) throw Error('Invalid aircraft CG height');
  const {height,extension,lateral,usableHalfLength,speedFactor}=spec;
  const base=runwayCircuit({height,extension,lateral,usableHalfLength});
  // Runway 08/26 is centred at (0,0), aligned along X. Mirror only the
  // crosswind/downwind side to fly the same departure/arrival in either hand.
  const points=base.points.map(([x,y,z])=>[x,direction==='right'?-y:y,z+cgHeight]);
  const speeds=[0,42,80,80,70,60,60,50,40,0].map(v=>v*speedFactor);
  const waypoints=points.map((position,i)=>{
    const distance=i?Math.hypot(...position.map((v,j)=>v-points[i-1][j])):0;
    return {position, speed:speeds[i],
      duration:i===0?0:Math.max(.25,2*distance/(speeds[i-1]+speeds[i]))};
  });
  return {id,direction,label:spec.label,waypoints};
}
