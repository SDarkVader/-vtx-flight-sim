// Sensor values only: absent measurements remain unavailable.
export function cockpitTelemetry(o = {}) {
  const finite = Number.isFinite;
  const radar = finite(o.radar_clearance_m) ? o.radar_clearance_m
    : finite(o.radar_altimeter_m) && finite(o.radar_altimeter_ground_reference_m)
      ? Math.max(0, o.radar_altimeter_m - o.radar_altimeter_ground_reference_m) : null;
  const velocity = o.velocity_world_m_s ?? o.gnss_velocity_mps;
  const vertical = Array.isArray(velocity) && finite(velocity[2]) ? velocity[2] : null;
  const speed = Array.isArray(velocity) && finite(velocity[0]) && finite(velocity[1])
    ? Math.hypot(velocity[0], velocity[1]) : null;
  const fuel = Array.isArray(o.fuel_kg) && o.fuel_kg.length && o.fuel_kg.every(finite)
    ? o.fuel_kg.reduce((sum, value) => sum + value, 0) : null;
  const format = value => value === null ? '—' : value.toFixed(2);
  return { altitude:format(radar), verticalSpeed:format(vertical), speed:format(speed), fuel:format(fuel) };
}
