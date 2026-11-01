// Render-only, bounded extrapolation of a measured MuJoCo rotor joint speed.
// The next authoritative body pose replaces this estimate on every update.
export function rotorVisualOffset(omegaRadS,elapsedMs,timeScale,active,paused){
 if(!active||paused||!Number.isFinite(omegaRadS)||!Number.isFinite(elapsedMs)||!Number.isFinite(timeScale)||timeScale<=0)return 0;
 const dt=Math.min(Math.max(elapsedMs,0),120)*timeScale/1000;
 return omegaRadS*dt%(2*Math.PI);
}
