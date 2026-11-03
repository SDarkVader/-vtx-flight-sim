// Format only the current simulator observation. Missing readings stay missing.
const value = (x, digits=1) => Number.isFinite(x) ? Number(x).toFixed(digits) : '—';
export function avionicsReadings(o) {
  if (!o) return null;
  const velocity=Array.isArray(o.gnss_velocity_mps) ? o.gnss_velocity_mps : [];
  const speed=Number.isFinite(velocity[0]) && Number.isFinite(velocity[1]) ? Math.hypot(velocity[0],velocity[1]) : null;
  const fuel=Array.isArray(o.fuel_kg) && o.fuel_kg.length && o.fuel_kg.every(Number.isFinite) ? o.fuel_kg.reduce((a,b)=>a+b,0) : null;
  const rpms=Array.isArray(o.rotor_rpm) && o.rotor_rpm.length===4 ? o.rotor_rpm.map(x=>value(x,0)).join(' / ') : '—';
  const meanRpm=Array.isArray(o.rotor_rpm) && o.rotor_rpm.length===4 && o.rotor_rpm.every(Number.isFinite) ? o.rotor_rpm.reduce((a,b)=>a+b,0)/4 : null;
  let level='OFF';
  if(o.cabin_level_enabled) level=o.cabin_level_limited?'TRAVEL LIMIT':o.cabin_level_powered?'POWERED':'PASSIVE';
  return {time:value(o.t_s,1), state:o.active?(o.paused?'PAUSED':'LIVE'):'LAST STATE', clearance:value(o.radar_clearance_m,2),
          vertical:value(velocity[2],1),speed:value(speed,1), power:value(o.engine_shaft_kw,1),
          fuel:value(fuel,1),rpms,meanRpm,verticalValue:Number.isFinite(velocity[2])?velocity[2]:null,
          level,warnings:Array.isArray(o.warning_lamps)?o.warning_lamps:[]};
}
