import * as THREE from 'three';

// Eye is above the authored bucket seat, behind the two MFDs and below the canopy.
// The offsets are render datums only, in Ricochet's X-forward/Y-port/Z-up body frame.
export const RICOCHET_EYE = Object.freeze([1.18, 0, 1.28]);
const finite = (values, n) => Array.isArray(values) && values.length === n && values.every(Number.isFinite);

export function boatCameraView(pose, {mode = 'cockpit', yaw = 0, pitch = 0} = {}) {
  const p = pose?.position, a = pose?.quaternion_wxyz;
  if (!finite(p, 3) || !finite(a, 4) || Math.abs(Math.hypot(...a) - 1) > .01 || !Number.isFinite(yaw) || !Number.isFinite(pitch)) return null;
  const q = new THREE.Quaternion(a[1], a[2], a[3], a[0]).normalize();
  const origin = new THREE.Vector3(...p), up = new THREE.Vector3(0, 0, 1).applyQuaternion(q);
  if (mode === 'cockpit') {
    const position = new THREE.Vector3(...RICOCHET_EYE).applyQuaternion(q).add(origin);
    const angle = pitch - .08, cp = Math.cos(angle);
    const sight = new THREE.Vector3(Math.cos(yaw) * cp, Math.sin(yaw) * cp, Math.sin(angle)).applyQuaternion(q);
    return {position: position.toArray(), target: position.clone().add(sight).toArray(), up: up.toArray()};
  }
  const position = new THREE.Vector3(-12, -8, 6).applyQuaternion(q).add(origin);
  return {position: position.toArray(), target: origin.add(up).toArray(), up: [0, 0, 1]};
}
