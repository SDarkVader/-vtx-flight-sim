// The R6 cabin looks along local -Y; its right side is local -X.
// Return commands in the aircraft's fixed actuation axes.
export function cockpitAxes(forward, right, cabinHeadingDegrees) {
  if (![forward, right, cabinHeadingDegrees].every(Number.isFinite)) throw new TypeError('Inputs must be finite');
  const a = cabinHeadingDegrees * Math.PI / 180;
  return [Math.cos(a)*forward + Math.sin(a)*right,
          Math.sin(a)*forward - Math.cos(a)*right];
}

// Euler angles describe the cabin's local XYZ orientation in world axes.
// Resolve the world vertical against the cabin-forward (-Y) camera basis.
export function cockpitHorizon(attitudeDegrees) {
  if (!Array.isArray(attitudeDegrees) || attitudeDegrees.length !== 3 || !attitudeDegrees.every(Number.isFinite)) throw new TypeError('Attitude must be three finite angles');
  const [x,y] = attitudeDegrees.map(v => v*Math.PI/180);
  const forwardZ = -Math.cos(y)*Math.sin(x);
  const rightZ = Math.sin(y);
  const upZ = Math.cos(y)*Math.cos(x);
  return {pitchDegrees: Math.asin(Math.max(-1,Math.min(1,forwardZ)))*180/Math.PI,
          bankDegrees: Math.atan2(rightZ,upZ)*180/Math.PI};
}
