// Track the Phantom's physical centre of mass, not its ground-level CAD origin.
// The vertical offset retains the existing framing without rotating with the body.
export function physicalCameraTarget(truth) {
  const cg = truth?.phantom && truth?.mass?.cg_world_m;
  if (Array.isArray(cg) && cg.length === 3 && cg.every(Number.isFinite)) {
    return [cg[0], cg[1], cg[2] + 0.94];
  }
  const origin = truth?.body_poses?.airframe?.position;
  return origin ? [origin[0], origin[1], origin[2] + 1.5] : null;
}
