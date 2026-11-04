// Deterministic, visual-only route catalogue derived from the shared airport layout.
// Procedures are game previews, NOT published instrument procedures or ATC clearances.
import {LAYOUT} from './layout.js';
import {buildTrafficRoute} from './traffic-path.js';

const RAD=Math.PI/180;
const point=(x,y,z,speed,duration)=>({position:[x,y,z],speed,duration});
const runway=(id)=>{
  const r=LAYOUT.runways.find(v=>v.id===id);
  if(!r||r.status!=='open')throw Error('Unknown or closed runway: '+id);
  const axis=r.axis||[Math.sin(r.heading*RAD),Math.cos(r.heading*RAD)];
  return {...r,axis};
};
export const TRAFFIC_DIFFICULTIES=Object.freeze({
  easy:Object.freeze({speedFactor:.65,turnFactor:.65}),
  normal:Object.freeze({speedFactor:.85,turnFactor:.85}),
  hard:Object.freeze({speedFactor:1,turnFactor:1})
});
// Convert route geometry to a deterministic timing schedule. Max speeds are
// explicit caller-supplied limits; these are not computed aircraft performance.
export function scheduleVisualRoute(points,{cruiseSpeed,difficulty='normal'}={}){
  const level=TRAFFIC_DIFFICULTIES[difficulty];
  if(!level||!(cruiseSpeed>0)||!Number.isFinite(cruiseSpeed))throw Error('Invalid speed or difficulty');
  const speed=cruiseSpeed*level.speedFactor;
  const waypoints=points.map((p,i)=>{
    if(!Array.isArray(p)||p.length!==3||!p.every(Number.isFinite))throw Error('Invalid route point');
    const d=i?Math.hypot(...p.map((v,j)=>v-points[i-1][j])):0;
    if(i&&d===0)throw Error('Duplicate route point');
    return {position:p,speed,duration:i?d/speed:0};
  });
  return buildTrafficRoute(waypoints);
}
export function runwayCircuit({runwayId='08/26',height=35,extension=55,lateral=110,usableHalfLength=350}={}){
  const r=runway(runwayId);
  if(!(height>0&&extension>0&&lateral>0&&usableHalfLength>0))throw Error('Invalid circuit geometry');
  const [ax,ay]=r.axis, [cx,cy]=r.center;
  const x=(along,side,z)=>[cx+ax*along-ay*side,cy+ay*along+ax*side,z];
  // Only the central runway portion belongs to the +/-500 m physics region.
  // The visual runway is longer. Clipping the preview does not alter its physical model.
  const half=Math.min(r.length/2,usableHalfLength);
  return {kind:'visual-circuit',runwayId,points:[
    x(-half,0,0),x(-half*.55,0,0),x(0,0,0),x(half*.4,0,height*.5),
    x(half+extension,0,height),x(half+extension,lateral,height),
    x(-half-extension,lateral,height),x(-half-extension,0,height),
    x(-half*.65,0,height*.5),x(-half*.45,0,0)
  ]};
}
export function holdingPattern({fix=[0,0,120],headingDeg=90,legLength=250,width=100}={}){
  if(!Array.isArray(fix)||fix.length!==3||!fix.every(Number.isFinite)||!(legLength>0&&width>0))throw Error('Invalid hold');
  const a=headingDeg*RAD,dx=Math.sin(a),dy=Math.cos(a),[x,y,z]=fix;
  // Rectangular guide with sampled corners; not a certified constant-radius hold.
  return {kind:'visual-hold',points:[[x,y,z],[x+dx*legLength,y+dy*legLength,z],
    [x+dx*legLength-dy*width,y+dy*legLength+dx*width,z],
    [x-dy*width,y+dx*width,z],[x,y,z]]};
}
export function missedApproach({runwayId='08/26',height=150,extension=350,usableHalfLength}={}){
  const r=runway(runwayId);
  if(!(height>0&&extension>0))throw Error('Invalid missed approach');
  const [ax,ay]=r.axis,[cx,cy]=r.center,half=Math.min(r.length/2,usableHalfLength??r.length/2);
  const p=(d,z)=>[cx+ax*d,cy+ay*d,z];
  return {kind:'visual-missed-approach',runwayId,points:[
    p(-half*.4,25),p(0,45),p(half*.5,height*.65),p(half+extension,height)]};
}
export function teardropEntry({fix=[0,0,120],inboundHeadingDeg=90,length=240,offsetDeg=30}={}){
  if(!Array.isArray(fix)||fix.length!==3||!fix.every(Number.isFinite)||!(length>0)||!(offsetDeg>0&&offsetDeg<90))throw Error('Invalid entry');
  const a=inboundHeadingDeg*RAD,b=a+Math.PI+offsetDeg*RAD,[x,y,z]=fix;
  const d=(angle,dist)=>[x+Math.sin(angle)*dist,y+Math.cos(angle)*dist,z];
  return {kind:'visual-teardrop',points:[[x,y,z],d(b,length),d(a+Math.PI,length*.7),[x,y,z]]};
}
