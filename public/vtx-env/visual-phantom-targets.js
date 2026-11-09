// Pure deterministic targets for the 28 authored A10 joints.
// No Three.js dependency: tested in CI against the actual glTF metadata.
const clamp01=v=>Math.min(1,Math.max(0,v));
const ease=v=>{const t=clamp01(v);return t*t*(3-2*t);};
const phase=(t,start,end)=>Number.isFinite(start)&&Number.isFinite(end)?ease((t-start)/(end-start)):0;

// Staged ground-to-flight configuration. Smoothstep has zero velocity at both
// ends, so no visible snapping at hatch, slide, hinge or lock transitions.
export function visualPhantomTargets(rig,pose,{bank=0,duration=83,flightStart=0,flightEnd=duration,retractStart=Infinity}={}){
 if(!rig||!pose||!Number.isFinite(pose.time)||!Number.isFinite(duration)||duration<=0||
    !Number.isFinite(bank))throw Error('Invalid A10 animation state');
 const t=Math.max(0,Math.min(duration,pose.time));
 const hatch=phase(t,.5,3.5)*(1-phase(t,retractStart+12,retractStart+16));
 const extend=phase(t,3.5,13.5)*(1-phase(t,retractStart+2,retractStart+12));
 const lock=phase(t,13.5,16)*(1-phase(t,retractStart,retractStart+2));
 const takeoffFlap=phase(t,10,14)*(1-phase(t,23,28));
 const approachFlap=phase(t,flightEnd-27,flightEnd-20)*(1-phase(t,flightEnd-4,flightEnd));
 const flap=Math.max(takeoffFlap,approachFlap);
 const wheelDown=phase(t,flightStart+18,flightStart+24)*(1-phase(t,flightEnd-18,flightEnd-10));
 const joints={};
 for(const j of rig.joints){
  const n=j.name;
  if(n.startsWith('wing_')||n.endsWith('_fold')){
   joints[n]=j.q0*(1-extend);
  }else if(n==='canard_left'||n==='canard_right'){
   const pitch=Number.isFinite(pose.pitch)?pose.pitch:0;
   const incidence=pitch*.6+takeoffFlap*.13+approachFlap*.09+(n==='canard_left'?-bank:bank)*.2;
   joints[n]=extend*Math.max(-20*Math.PI/180,Math.min(25*Math.PI/180,incidence));
  }else if(n.startsWith('hatch_')){
   joints[n]=j.q0*(1-hatch);
  }else if(n.startsWith('pin_')){
   joints[n]=j.q0*(1-lock);
  }else if(n.startsWith('flap_')){
   // Mirrored authoring axes already account for port/starboard symmetry.
   joints[n]=Math.PI/15*flap;
  }else if(n==='aileron_left'){
   // Opposed port/starboard commands, retaining the original A10 rig mapping.
   joints[n]=Math.max(-.15,Math.min(.15,-bank*.35));
  }else if(n==='aileron_right'){
   joints[n]=Math.max(-.15,Math.min(.15,bank*.35));
  }else if(n.startsWith('pod_')){
   // The mirrored pod hinges turn wheel faces toward the ground in flight.
   joints[n]=j.q0+(n.endsWith('L')?-1:1)*Math.PI/2*wheelDown;
  }else if(n.startsWith('leg_')){
   joints[n]=j.q0+.10*wheelDown;
  }
 }
 return {joints,phase:{hatch,extend,lock,flap,wheelDown}};
}
