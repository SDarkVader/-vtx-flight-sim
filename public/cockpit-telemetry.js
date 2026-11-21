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

const unavailable = '—';

export function phantomCockpitAuthority(view, status, {stale, recording} = {}) {
  const mode = (label, tone = 'inactive', canTake = false, canCommand = false) => ({label,tone,canTake,canCommand});
  if (recording) return mode('Flight replay');
  if (stale || !view) return mode('Telemetry stale · controls locked', 'fault');
  if (!view.active) return mode('No active flight');
  if (view.paused) return mode('Flight paused · controls locked', 'warning');
  if (view.authority !== 'manual') return mode(view.authority === 'colin' ? 'Colin has control' : 'External pilot has control');
  if (!status?.available) return mode('Aircraft controls unavailable');
  if (!status.engaged) return mode('Manual available · take control', 'warning', true);
  if (status.rejected) return mode('Manual engaged · command rejected', 'fault', true);
  if (view.observation?.warning_lamps?.includes('COMMAND_LEASE_EXPIRED'))
    return mode('Manual engaged · command lease expired', 'warning', true, !status.waiting);
  if (status.waiting) return mode('Manual engaged · command pending', 'warning', true);
  return mode('Manual control active', 'active', true, true);
}

export function phantomCockpitSwitches(truth = {}) {
  const command = truth.command ?? {};
  const four = value => Array.isArray(value) && value.length === 4 && value.every(Number.isFinite);
  const group = (field, label, value) => ({label, selected:value === 0, patch:{[field]:Array(4).fill(value)}});
  const single = (field, label, value, selected) => ({label, selected, patch:{[field]:value}});
  const pods = command.pod_tilt_deg;
  const legs = command.leg_extension_m;
  const brake = command.brake;
  const airbrake = truth.phantom?.transition_ecu && (command.airbrake ?? truth.phantom.transition_ecu.airbrake);
  return {
    brakes: four(brake) ? brake.some(value => value > 0)
      ? group('brake', 'Release', 0) : group('brake', 'Apply', 1) : null,
    gear: four(pods) ? pods.every(value => value > 45)
      ? group('pod_tilt_deg', 'Set road', 0) : group('pod_tilt_deg', 'Set VTOL', 90) : null,
    legs: four(legs) ? legs.every(value => value > .26)
      ? group('leg_extension_m', 'Retract', 0) : group('leg_extension_m', 'Extend', .52) : null,
    wings: command.wing === 'deploy' ? single('wing', 'Stow', 'stow', true)
      : command.wing === 'stow' ? single('wing', 'Deploy', 'deploy', false) : null,
    canards: command.canard_fold === 'deployed' ? single('canard_fold', 'Fold', 'folded', true)
      : command.canard_fold === 'folded' ? single('canard_fold', 'Deploy', 'deployed', false) : null,
    airbrake: airbrake === 'on' ? single('airbrake', 'Release', 'off', true)
      : airbrake === 'off' ? single('airbrake', 'Engage', 'on', false) : null,
  };
}

export function phantomSystemIndications(states) {
  const signal = (value, on, off) => {
    if (!value || value === unavailable || value.includes(unavailable)) return 'inactive';
    if (on.includes(value)) return 'active';
    return off.includes(value) ? 'inactive' : 'transit';
  };
  return {
    brakes: states.brakes && ![unavailable, 'Released'].includes(states.brakes) ? 'active' : 'inactive',
    gear: signal(states.gear, ['Road · 0°', 'VTOL · 90°'], []),
    legs: signal(states.legs, ['Extended'], ['Retracted']),
    wings: signal(states.wings, ['locked'], ['stowed']),
    canards: signal(states.canards, ['Deployed'], ['Folded']),
    airbrake: signal(states.airbrake, ['On'], ['Off']),
  };
}

export function phantomCockpitStates(observation = {}, truth = {}) {
  const range = (values, count, display) => {
    if (!Array.isArray(values) || values.length !== count || !values.every(Number.isFinite)) return unavailable;
    return display(Math.min(...values), Math.max(...values));
  };
  const span = (min, max, format) => format(min) === format(max) ? format(min) : `${format(min)}–${format(max)}`;
  const degrees = (value) => `${Math.round(value)}°`;
  const wingCaption = value => typeof value === 'string' ? value.replaceAll('_', ' ') : unavailable;
  const wing = observation.wing_state ?? truth.phantom?.wing_state;
  const left = wingCaption(wing?.left), right = wingCaption(wing?.right);
  const airbrake = truth.phantom?.transition_ecu?.airbrake;
  const percent = value => Number.isFinite(value)
    ? value > 0 && value < .005 ? '<1%' : `${Math.round(100 * value)}%` : unavailable;
  const brakes = range(truth.command?.brake, 4, (min, max) =>
    max <= 0 ? 'Released' : min >= 1 ? 'Full' : span(min, max, percent));
  const target = (values, min, max, tolerance) => {
    const first = values?.[0];
    return Number.isFinite(first) && values.length === 4 && values.every(value => value === first)
      && Math.max(Math.abs(first - min), Math.abs(first - max)) > tolerance ? first : null;
  };
  const gear = range(observation.pod_tilt_deg, 4, (min, max) => {
    const demanded = target(truth.command?.pod_tilt_deg,min,max,2);
    if (demanded !== null) return `${span(min,max,degrees)} → ${degrees(demanded)}`;
    return max <= 2 ? 'Road · 0°' : min >= 88 ? 'VTOL · 90°' : span(min,max,degrees);
  });
  const legs = range(observation.leg_extension_m, 4, (min, max) => {
    const demanded = target(truth.command?.leg_extension_m,min,max,.02);
    const measured = span(min,max,value=>value.toFixed(2));
    if (demanded !== null) return `${measured} → ${demanded.toFixed(2)} m`;
    return max <= .02 ? 'Retracted' : min >= .5 ? 'Extended' : `${measured} m`;
  });
  const fold = observation.canard_fold_deg;
  const foldAngles = Array.isArray(fold) && fold.every(Number.isFinite) ? fold.map(Math.abs) : null;
  const canards = range(foldAngles, 2, (min, max) =>
    max <= 3 ? 'Deployed' : min >= 87 ? 'Folded' : span(min, max, degrees));
  const stick = ['pitch', 'roll', 'yaw'].map(axis => percent(truth.command?.[axis]));
  const boostFeedback = Array.isArray(truth.boosters) ? truth.boosters : [];
  const boosters = ['left', 'right'].map(side =>
    percent(boostFeedback.find(booster => booster?.side === side)?.spool));
  const wheels = truth.phantom?.wheel_rad_s;
  const wheelRpm = index => Number.isFinite(wheels?.[index])
    ? String(Math.round(Math.abs(wheels[index]) * 60 / (2 * Math.PI))) : unavailable;
  const rudder = truth.phantom?.rudder_deg;
  const actualAilerons = observation.aileron_deg;
  return { brakes, gear, legs, wings: left === right ? left : `L ${left} / R ${right}`,
    canards, airbrake: airbrake === 'on' ? 'On' : airbrake === 'off' ? 'Off' : unavailable,
    stick: stick.every(value => value === unavailable) ? unavailable : stick.join(' / '),
    boosters: boosters.every(value => value === unavailable) ? unavailable : boosters.join(' / '),
    frontWheels: [0,1].some(index => Number.isFinite(wheels?.[index])) ? [0,1].map(wheelRpm).join(' / ') : unavailable,
    rearWheels: [2,3].some(index => Number.isFinite(wheels?.[index])) ? [2,3].map(wheelRpm).join(' / ') : unavailable,
    rudder: Number.isFinite(rudder) ? degrees(rudder) : unavailable,
    ailerons: Array.isArray(actualAilerons) && actualAilerons.length === 2 && actualAilerons.every(Number.isFinite)
      ? actualAilerons.map(degrees).join(' / ') : unavailable };
}
