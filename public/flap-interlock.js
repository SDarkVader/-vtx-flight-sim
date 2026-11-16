// The plant reports why its actual flap target differs from the pilot command.
export function flapInterlockMessage(interlock) {
  if (!Array.isArray(interlock?.reasons)) return '';
  if (interlock.reasons.includes('airspeed_limit')) {
    const limit = Number.isFinite(interlock.max_speed_m_s) ? ` (${interlock.max_speed_m_s} m/s)` : '';
    return `Flaps limited to zero: airspeed limit${limit}.`;
  }
  if (interlock.reasons.includes('wing_unlocked')) return 'Flaps held at zero: wing not locked.';
  return '';
}
