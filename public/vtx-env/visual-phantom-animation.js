// Render-only animation of the Phantom's existing GLB joint empties.
// Uses the CAD's q_rest values, not duplicated mesh geometry or physics.
import {attachPhantom,updatePhantom} from './phantom-look.js';

const clamp01=v=>Math.max(0,Math.min(1,v));
export function attachVisualPhantom(model){ return attachPhantom(model); }

export function animateVisualPhantom(rig,pose,{bank=0,cgHeight=.553}={}){
  if(!rig)return;
  const airborne=pose.position[2]>cgHeight+1;
  // The visual route enters climb only after its 80 m/s rotation waypoint.
  const deploy=airborne?1:clamp01((pose.speed-35)/40);
  const joints={};
  for(const j of rig.joints){
    const n=j.name;
    if(n.startsWith('wing_')||n.startsWith('hatch_')||
       n.startsWith('pin_')||n.endsWith('_fold')){
      // Rest pose is stowed; exported joint position zero is deployed.
      joints[n]=j.q0*(1-deploy);
    } else if(n.startsWith('flap_')){
      joints[n]=airborne?0:Math.PI/15*deploy; // max 12 degrees, visual only
    } else if(n==='aileron_left'){
      joints[n]=Math.max(-.20,Math.min(.20,-bank*.35));
    } else if(n==='aileron_right'){
      joints[n]=Math.max(-.20,Math.min(.20,bank*.35));
    }
  }
  updatePhantom(rig,{phantom:{joints}});
}
