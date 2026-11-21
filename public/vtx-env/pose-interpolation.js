// Presentation-only smoothing of the aircraft between telemetry samples.
//
// The server sends rendering truth at about 10 Hz (nearer 9 Hz on Windows, where asyncio sleeps round up to
// the 15.6 ms timer tick). Drawn as-is, the airframe steps 10 times a second however fast the browser renders.
// This draws each body between the two most recent true poses, one sample interval behind, the same way the
// boats are drawn. Every drawn pose lies between two physical states: nothing is predicted or extrapolated,
// and the physics, records and evidence are untouched.
//
// Rotors keep the latest orientation, because a rotor turns a whole revolution or more between samples and
// interpolating it would alias; their sub-frame spin is added from measured angular velocity as before.

const MAX_JUMP_M = 60;          // a larger step between samples is a reset or teleport: show it at once
const MIN_INTERVAL_MS = 25, MAX_INTERVAL_MS = 400;

export function createPoseInterpolator({ maxJumpM = MAX_JUMP_M } = {}) {
  let prev = null, cur = null, prevMs = 0, curMs = 0, interval = 100;

  function receive(truth, receivedMs) {
    if (!truth?.body_poses) { prev = cur = null; return; }
    if (cur && truth !== cur) {
      prev = cur; prevMs = curMs;
      const gap = receivedMs - prevMs;
      if (gap > 0) interval = Math.min(MAX_INTERVAL_MS, Math.max(MIN_INTERVAL_MS, 0.7 * interval + 0.3 * gap));
    }
    cur = truth; curMs = receivedMs;
  }

  function present(nowMs, { frozen = false } = {}) {
    if (!cur) return null;
    // A clock that went backwards is a new run or a restored checkpoint: never blend across it.
    if (frozen || !prev || !(Number(cur.t_s) >= Number(prev.t_s))) return cur;
    const alpha = Math.min(1, Math.max(0, (nowMs - curMs) / interval));
    if (alpha >= 1) return cur;
    const poses = {};
    for (const [name, pose] of Object.entries(cur.body_poses)) {
      const before = prev.body_poses?.[name];
      if (!before || jump(before.position, pose.position) > maxJumpM) return cur;
      poses[name] = {
        ...pose,
        position: lerp3(before.position, pose.position, alpha),
        quaternion_wxyz: /^rotor[1-4]$/.test(name) ? pose.quaternion_wxyz : slerp(before.quaternion_wxyz, pose.quaternion_wxyz, alpha),
      };
    }
    const out = { ...cur, body_poses: poses, presentation: { interpolated: true, alpha } };
    // The camera follows the centre of mass: it must move with the drawn airframe, not ahead of it.
    const cgA = prev.mass?.cg_world_m, cgB = cur.mass?.cg_world_m;
    if (isVec3(cgA) && isVec3(cgB)) out.mass = { ...cur.mass, cg_world_m: lerp3(cgA, cgB, alpha) };
    return out;
  }

  return { receive, present, get intervalMs() { return interval; } };
}

function isVec3(v) { return Array.isArray(v) && v.length === 3 && v.every(Number.isFinite); }
function jump(a, b) { return Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]); }
function lerp3(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }

export function slerp(a, b, t) {
  let [aw, ax, ay, az] = a, [bw, bx, by, bz] = b;
  let dot = aw * bw + ax * bx + ay * by + az * bz;
  if (dot < 0) { bw = -bw; bx = -bx; by = -by; bz = -bz; dot = -dot; }
  let ka, kb;
  if (dot > 0.9995) { ka = 1 - t; kb = t; }
  else { const th = Math.acos(dot), s = Math.sin(th); ka = Math.sin((1 - t) * th) / s; kb = Math.sin(t * th) / s; }
  const q = [ka * aw + kb * bw, ka * ax + kb * bx, ka * ay + kb * by, ka * az + kb * bz];
  const n = Math.hypot(...q);
  return q.map(v => v / n);
}
