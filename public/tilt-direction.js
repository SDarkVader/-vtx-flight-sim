// Polar control of the existing two-axis actuator command plane.
export function tiltFromDirection(magnitude, directionDegrees) {
  if (!Number.isFinite(magnitude) || !Number.isFinite(directionDegrees)) throw new TypeError('Tilt must be finite');
  const r = Math.max(0, Math.min(20, magnitude));
  const a = directionDegrees * Math.PI / 180;
  return [r * Math.cos(a), r * Math.sin(a)];
}

// Cockpit keyboard mixing (audit F14). The cockpit camera looks along cabin -Y, so the
// pilot's right is cabin -X. The airframe command plane (nacelle tilt X/Y and the
// pitch/roll collective differential) is body-fixed, so pilot-relative inputs are
// rotated by the cabin yaw joint: body = Rz(cabinYaw) * (forward, -right).
// At zero cabin yaw this leaves forward/back and pitch unchanged and reverses only the
// lateral channel, which was the measured left/right reversal.
export function cockpitToBody(forward, right, cabinYawDeg = 0) {
  const a = (Number.isFinite(cabinYawDeg) ? cabinYawDeg : 0) * Math.PI / 180;
  const x = forward, y = -right, c = Math.cos(a), s = Math.sin(a);
  return [c * x - s * y + 0, s * x + c * y + 0];
}
