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
