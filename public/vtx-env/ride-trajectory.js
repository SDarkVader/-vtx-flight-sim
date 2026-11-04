// Smooth, deterministic kinematic demo path. Not a rigid-body flight controller.
// Cubic Hermite position with shared node tangents makes position AND heading
// continuous through every route waypoint; speed begins and ends at zero.
const norm=(v)=>Math.hypot(...v);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const EPS=1e-9;
export function buildRideTrajectory(waypoints,{cruiseSpeed=65}={}){
 if(!Array.isArray(waypoints)||waypoints.length<4||!Number.isFinite(cruiseSpeed)||cruiseSpeed<=0)
  throw Error('Invalid smooth ride geometry or speed');
 const points=waypoints.map(v=>{
  const p=Array.isArray(v)?v:v.position;
  if(!Array.isArray(p)||p.length!==3||!p.every(Number.isFinite))throw Error('Nonfinite waypoint');
  return [...p];
 });
 const times=[0];
 for(let i=1;i<points.length;i++){
  const d=norm(points[i].map((v,k)=>v-points[i-1][k]));
  if(d<EPS)throw Error('Duplicate flight waypoint');
  // Do not simulate rotor/engine acceleration: duration is a visual pacing parameter.
  times.push(times.at(-1)+Math.max(4,d/cruiseSpeed));
 }
 const tangents=points.map((p,i)=>{
  if(i===0||i===points.length-1)return [0,0,0];
  const h=times[i+1]-times[i-1];
  return p.map((_,k)=>{
   const before=(points[i][k]-points[i-1][k])/(times[i]-times[i-1]);
   const after=(points[i+1][k]-points[i][k])/(times[i+1]-times[i]);
   // Monotone vertical Hermite: no spurious negative altitude while rolling.
   if(k===2&&(before*after<=0))return 0;
   return (points[i+1][k]-points[i-1][k])/h;
  });
 });
 const segments=[];
 for(let i=1;i<points.length;i++)segments.push({
  a:points[i-1],b:points[i],v0:tangents[i-1],v1:tangents[i],
  start:times[i-1],duration:times[i]-times[i-1]
 });
 return {kind:'smooth-ride',segments,duration:times.at(-1),points};
}
function evaluate(route,t){
 const time=clamp(t,0,route.duration);
 const segments=route.segments;
 const i=segments.findIndex(s=>time<s.start+s.duration);
 const index=i<0?segments.length-1:i;
 const s=segments[index],h=s.duration,u=clamp((time-s.start)/h,0,1);
 const u2=u*u,u3=u2*u;
 const h00=2*u3-3*u2+1,h10=u3-2*u2+u,h01=-2*u3+3*u2,h11=u3-u2;
 const dh00=(6*u2-6*u)/h,dh10=3*u2-4*u+1,dh01=(-6*u2+6*u)/h,dh11=3*u2-2*u;
 const position=s.a.map((p,k)=>h00*p+h10*h*s.v0[k]+h01*s.b[k]+h11*h*s.v1[k]);
 const velocity=s.a.map((p,k)=>dh00*p+dh10*s.v0[k]+dh01*s.b[k]+dh11*s.v1[k]);
 return {time,position,velocity,segment:index};
}
export function sampleRideTrajectory(route,t){
 if(route.kind!=='smooth-ride'||!Number.isFinite(t))throw Error('Invalid smooth ride sample');
 const p=evaluate(route,t),v=p.velocity;
 // On stationary endpoints, look down the nearby segment rather than resetting yaw.
 const headingVector=norm(v.slice(0,2))>.001?v:evaluate(route,clamp(p.time+(p.time===0?.3:-.3),0,route.duration)).velocity;
 const heading=Math.atan2(headingVector[1],headingVector[0]);
 const pitch=Math.atan2(v[2],Math.hypot(v[0],v[1]));
 return {time:p.time,position:p.position,speed:norm(v),heading,pitch,bank:0,segment:p.segment};
}
export function sampleTerrainHeight(world,x,y){
 const n=world.heights_m.length,half=world.half_m;
 if(Math.abs(x)>half||Math.abs(y)>half)throw Error('Route leaves modelled terrain');
 const sx=clamp((x+half)/(2*half)*(n-1),0,n-1.000001),sy=clamp((y+half)/(2*half)*(n-1),0,n-1.000001);
 const i=Math.floor(sx),j=Math.floor(sy),a=sx-i,b=sy-j,h=world.heights_m;
 return a>b?(1-a)*h[j][i]+(a-b)*h[j][i+1]+b*h[j+1][i+1]:
  (1-b)*h[j][i]+(b-a)*h[j+1][i]+a*h[j+1][i+1];
}
// Swept-envelope approximation, sampled at <= 0.12 seconds along the full path.
// Physical colliders used only as obstacles; runway ground contact is permitted.
export function inspectRideClearance(route,world,{horizontalMargin=14,verticalMargin=8}={}){
 if(!world||!Array.isArray(world.obstacles)||!Array.isArray(world.heights_m))throw Error('Missing physical terrain');
 const failures=[];let minAirClearance=Infinity,maxHeadingStep=0,lastHeading=null;
 const samples=Math.ceil(route.duration/.12);
 for(let i=0;i<=samples;i++){
  const t=route.duration*i/samples,pose=sampleRideTrajectory(route,t);
  const [x,y,z]=pose.position;
  if(Math.abs(x)>=world.half_m-10||Math.abs(y)>=world.half_m-10){failures.push({t,reason:'bounds'});continue;}
  const surface=sampleTerrainHeight(world,x,y),clearance=z-surface;
  const onRunway=Math.abs(y)<10&&x>=-145&&x<=160;
  if(clearance<verticalMargin&&(clearance<.2||!onRunway))failures.push({t,reason:'terrain',x,y,z,clearance});
  if(!onRunway)minAirClearance=Math.min(minAirClearance,clearance);
  for(const o of world.obstacles){
   const [ox,oy,oz]=o.center,[hx,hy,hz]=o.half;
   const roof=oz+hz;
   const dx=Math.max(0,Math.abs(x-ox)-hx);
   const dy=Math.max(0,Math.abs(y-oy)-hy);
   // All A10 airframe bounds are approximated with an inflated swept circle.
   if(Math.hypot(dx,dy)<=horizontalMargin&&z-verticalMargin<roof+3){
    failures.push({t,reason:'obstacle',id:o.id,x,y,z});break;
   }
  }
  if(lastHeading!==null){
   const angle=Math.atan2(Math.sin(pose.heading-lastHeading),Math.cos(pose.heading-lastHeading));
   maxHeadingStep=Math.max(maxHeadingStep,Math.abs(angle));
  }
  lastHeading=pose.heading;
 }
 return {ok:failures.length===0,failures:failures.slice(0,20),
  totalFailures:failures.length,minAirClearance,maxHeadingStep,samples};
}
