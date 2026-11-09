// Visual cues only: never substitute these values for physical data.
export function thrustFraction(thrust, maximum) {
  if (!Number.isFinite(thrust) || !Number.isFinite(maximum) || maximum <= 0) return 0;
  return Math.max(0, Math.min(1, thrust / maximum));
}
export function wheelAngle(position, offset) {
  if (!Number.isFinite(position)) return null;
  return position + (Number.isFinite(offset) ? offset : 0);
}
