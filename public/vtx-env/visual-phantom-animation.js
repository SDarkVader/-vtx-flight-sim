// Render-only staged animation of the original A10 CAD joints.
// Source q_rest, joint axes and mesh geometry remain authoritative.
// This is an animated flight demonstration, not physical actuator control.
import {attachPhantom,updatePhantom} from './phantom-look.js';
import {visualPhantomTargets} from './visual-phantom-targets.js';

export function attachVisualPhantom(model){return attachPhantom(model);}
export function animateVisualPhantom(rig,pose,{time=0,duration=83,bank=0}={}){
 if(!rig)return;
 const {joints}=visualPhantomTargets(rig,{...pose,time},{duration,bank});
 updatePhantom(rig,{phantom:{joints}});
}
