// Deterministic, render-only aircraft trajectory sampler.
// Coordinates: world metres, x east, y north, z up. Time: seconds.
// This module does not command the live Phantom or alter its physics.
export function buildTrafficRoute(waypoints, { scale = 1 } = {}) {
  if (!Array.isArray(waypoints) || waypoints.length < 2 || !(scale > 0)) throw new Error('Need at least two waypoints and positive scale');
  const points = waypoints.map((p, i) => {
    if (!Array.isArray(p.position) || p.position.length !== 3 || p.position.some(v => !Number.isFinite(v)) ||
        !Number.isFinite(p.speed) || p.speed < 0 || (i && !(p.duration > 0))) throw new Error('Invalid waypoint');
    return { position: p.position.map(v => v * scale), speed: p.speed * scale, duration: i ? p.duration : 0 };
  });
  const segments = [];
  let elapsed = 0;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i], duration = b.duration;
    const delta = b.position.map((v, j) => v - a.position[j]);
    const distance = Math.hypot(...delta);
    if (!(distance > 0)) throw new Error('Zero-length segment');
    // Hermite interpolation of distance along a straight segment.
    // Endpoint velocities are clamped to prevent reverse travel / overshoot.
    const v0 = Math.min(a.speed, 3 * distance / duration);
    const v1 = Math.min(b.speed, 3 * distance / duration);
    segments.push({ a, b, delta, distance, duration, start: elapsed, v0, v1 });
    elapsed += duration;
  }
  return { segments, duration: elapsed };
}

export function sampleTrafficRoute(route, timeSeconds) {
  if (!Number.isFinite(timeSeconds)) throw new Error('Invalid time');
  const t = Math.max(0, Math.min(route.duration, timeSeconds));
  const seg = route.segments.find(s => t < s.start + s.duration) ?? route.segments.at(-1);
  const u = Math.max(0, Math.min(1, (t - seg.start) / seg.duration));
  const d = seg.distance, h = seg.duration, m0 = seg.v0 * h, m1 = seg.v1 * h;
  const u2 = u*u, u3 = u2*u;
  const s = (-2*u3+3*u2)*d + (u3-2*u2+u)*m0 + (u3-u2)*m1;
  const dsdu = (-6*u2+6*u)*d + (3*u2-4*u+1)*m0 + (3*u2-2*u)*m1;
  const fraction = Math.max(0, Math.min(1, s/d));
  const position = seg.a.position.map((v, j) => v + fraction*seg.delta[j]);
  const horizontal = Math.hypot(seg.delta[0], seg.delta[1]);
  const heading = Math.atan2(seg.delta[1], seg.delta[0]);
  const pitch = Math.atan2(seg.delta[2], horizontal);
  return { time: t, position, speed: Math.max(0, dsdu/h), heading, pitch, bank: 0,
    segment: route.segments.indexOf(seg) };
}

// World frame: X east, Y north, Z up; distances in metres, time in seconds.
// A circular path is a reusable geometric reference, not aircraft control.
export function circularPath({center, radius, elevation=0, speedLimit=4}) {
  if (!Array.isArray(center) || center.length !== 2 || !center.every(Number.isFinite) || !Number.isFinite(radius) || radius <= 0 || !Number.isFinite(elevation) || !Number.isFinite(speedLimit) || speedLimit <= 0) throw Error('Invalid circular path');
  return {center, radius, elevation, speedLimit, length: 2*Math.PI*radius,
    sample(distance) {
      const angle = distance / radius;
      return {position:[center[0]+radius*Math.cos(angle), center[1]+radius*Math.sin(angle), elevation], heading:angle+Math.PI/2, curvature:1/radius};
    }};
}
export function stoppingDistance(speed, braking) {
  if (!Number.isFinite(speed) || speed < 0 || !Number.isFinite(braking) || braking <= 0) throw Error('Invalid braking parameters');
  return speed*speed/(2*braking);
}
// Kinematic ground-traffic model, not a rigid-body collision model.
export function stepGroundVehicle(state, path, vehicle, dt, requestedSpeed) {
  if (!Number.isFinite(dt) || dt < 0 || !Number.isFinite(requestedSpeed) || requestedSpeed < 0 || !Number.isFinite(vehicle.acceleration) || vehicle.acceleration <= 0 || !Number.isFinite(vehicle.braking) || vehicle.braking <= 0 || !Number.isFinite(vehicle.minTurnRadius) || vehicle.minTurnRadius <= 0 || !Number.isFinite(vehicle.maxLateralAcceleration) || vehicle.maxLateralAcceleration <= 0) throw Error('Invalid vehicle constraints');
  if (!Number.isFinite(vehicle.width) || vehicle.width <= 0 || !Number.isFinite(vehicle.length) || vehicle.length <= 0 || !Number.isFinite(vehicle.cgOffset) || Math.abs(vehicle.cgOffset) > vehicle.length/2) throw Error('Invalid vehicle dimensions or centre of gravity');
  // Conservative inside-edge clearance for the body envelope.
  if (path.radius - vehicle.width/2 < vehicle.minTurnRadius) throw Error('Path exceeds steering clearance');
  const limit = Math.min(path.speedLimit, Math.sqrt(vehicle.maxLateralAcceleration * path.radius), requestedSpeed);
  const next = Math.max(0, Math.min(state.speed + vehicle.acceleration*dt, Math.max(limit, state.speed - vehicle.braking*dt)));
  const distance = state.distance + (state.speed+next)*dt/2;
  return {distance, speed:next, pose:path.sample(distance)};
}
