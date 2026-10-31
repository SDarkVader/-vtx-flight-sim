// Polar control of the existing two-axis actuator command plane.
export function tiltFromDirection(magnitude, directionDegrees) {
  if (!Number.isFinite(magnitude) || !Number.isFinite(directionDegrees)) throw new TypeError('Tilt must be finite');
  const r = Math.max(0, Math.min(20, magnitude));
  const a = directionDegrees * Math.PI / 180;
  return [r * Math.cos(a), r * Math.sin(a)];
}
