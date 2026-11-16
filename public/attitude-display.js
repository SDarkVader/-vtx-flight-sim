// Resolve the cockpit's physical pose, shared by live rendering and replay.
// Quaternions are MuJoCo's [w, x, y, z], with Z up.
export function physicalCockpitAttitude(snapshot) {
  const q = snapshot?.body_poses?.cabin?.quaternion_wxyz;
  if (!Array.isArray(q) || q.length !== 4 || !q.every(Number.isFinite)) return null;
  const magnitude = Math.hypot(...q);
  if (magnitude < 1e-12) return null;
  const [w, x, y, z] = q.map(value => value / magnitude);
  const r20 = 2 * (x * z - w * y);
  const r21 = 2 * (y * z + w * x);
  const r22 = 1 - 2 * (x * x + y * y);
  const phantom = !!snapshot.phantom || snapshot.variant?.startsWith('phantom') ||
    snapshot.provenance?.airframe_variant?.startsWith('phantom');
  // Phantom looks along +X; R6's gimballed cabin looks along -Y. The
  // Phantom conventions match plant.attitude(): nose-up and right-down +.
  const forwardZ = phantom ? r20 : -r21;
  const rightZ = phantom ? r21 : -r20;
  const degrees = 180 / Math.PI;
  return {
    pitchDegrees: Math.asin(Math.max(-1, Math.min(1, forwardZ))) * degrees,
    bankDegrees: Math.atan2(rightZ, r22) * degrees,
    timeSeconds: Number.isFinite(snapshot.t_s) ? snapshot.t_s : null,
  };
}

export function renderAttitudeIndicator(elements, snapshot, mode) {
  const {indicator, horizon, angles, status} = elements;
  const attitude = physicalCockpitAttitude(snapshot);
  indicator.dataset.status = attitude ? mode.toLowerCase() : 'unavailable';
  horizon.style.visibility = attitude ? 'visible' : 'hidden';
  if (!attitude) {
    angles.textContent = 'ATTITUDE —';
    status.textContent = 'UNAVAILABLE';
    indicator.setAttribute('aria-label', 'Attitude unavailable');
    return;
  }
  const {pitchDegrees, bankDegrees, timeSeconds} = attitude;
  horizon.style.transform = `translateY(${pitchDegrees * 1.2}px) rotate(${-bankDegrees}deg)`;
  angles.textContent = `P ${pitchDegrees.toFixed(1)}° · B ${bankDegrees.toFixed(1)}°`;
  status.textContent = mode + (timeSeconds === null ? '' : ` · ${timeSeconds.toFixed(1)}s`);
  indicator.setAttribute('aria-label', `${mode} attitude, pitch ${pitchDegrees.toFixed(1)} degrees, bank ${bankDegrees.toFixed(1)} degrees`);
}
