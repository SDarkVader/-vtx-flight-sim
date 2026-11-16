import * as THREE from 'three';

const CONFIG = '2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f';
const VARIANTS = new Set(['phantom-a10c-runway-20261112', 'phantom-a10c-vtol-20261112']);
const ASSET = '/assets/phantom-a10c-suspension-schematic.glb';
const CORNERS = ['FL', 'FR'];

// This descriptor belongs to the selected development revision. Historical
// frames and the original B/C visuals without it never acquire the schematic.
export function suspensionSchematicDescriptor(truth) {
  const descriptor = truth?.provenance?.flight_revision?.suspension_schematic;
  if (!VARIANTS.has(truth?.variant) || truth?.config_sha256 !== CONFIG ||
      descriptor?.schema !== 1 || descriptor.asset !== ASSET ||
      !/^[0-9a-f]{64}$/.test(descriptor.sha256 || '')) return null;
  return descriptor;
}

export function attachSuspensionSchematic(root, airframe) {
  const rig = {root, corners: [], status: 'unavailable', note: 'Measured suspension schematic; presentation only'};
  root.visible = false;
  if (!airframe || root.name !== 'VTX_A10C_SUSPENSION_SCHEMATIC') return rig;
  for (const side of CORNERS) {
    const pod = root.getObjectByName(`VTX_SCHEMATIC_${side}_POD`);
    const carrier = root.getObjectByName(`VTX_SCHEMATIC_${side}_CARRIER`);
    const connector = root.getObjectByName(`VTX_SCHEMATIC_${side}_CONNECTOR`);
    if (!pod || !carrier || !connector || carrier.parent !== pod || connector.parent !== pod ||
        pod.userData.schematic !== true || carrier.userData.schematic !== true ||
        carrier.userData.source_joint !== `pod_${side}_susp`) return rig;
    rig.corners.push({side, pod, carrier, connector, status: 'unavailable'});
  }
  airframe.add(root);
  rig.status = 'attached';
  return rig;
}

const valid = (a, n) => Array.isArray(a) && a.length === n && a.every(Number.isFinite);
function quaternion(pose) {
  const q = pose?.quaternion_wxyz;
  if (!valid(q, 4)) return null;
  const value = new THREE.Quaternion(q[1], q[2], q[3], q[0]);
  return value.lengthSq() > 1e-12 ? value.normalize() : null;
}

export function updateSuspensionSchematic(rig, truth, visible = true) {
  if (!rig) return;
  rig.root.visible = false;
  rig.status = 'unavailable';
  if (rig.corners.length !== 2 || !suspensionSchematicDescriptor(truth)) return;
  const frame = truth.body_poses?.airframe, rootQ = quaternion(frame);
  if (!valid(frame?.position, 3) || !rootQ) return;
  const inverse = rootQ.clone().invert(), origin = new THREE.Vector3().fromArray(frame.position);
  rig.root.position.set(0, 0, 0); rig.root.quaternion.identity(); rig.root.scale.set(1, 1, 1);
  for (const corner of rig.corners) {
    const podPose = truth.body_poses?.[`pod_${corner.side}`], podQ = quaternion(podPose);
    const wheelPose = truth.body_poses?.[`pod_${corner.side}_wheel`];
    const jointSlide = truth.phantom?.joints?.[`pod_${corner.side}_susp`];
    corner.pod.visible = false;
    corner.status = 'unavailable';
    corner.measured_slide_m = null;
    corner.joint_slide_m = Number.isFinite(jointSlide) ? jointSlide : null;
    if (!valid(podPose?.position, 3) || !podQ || !valid(wheelPose?.position, 3) || !Number.isFinite(jointSlide)) continue;
    // Body poses and q may straddle one 400 Hz integration step. The carrier
    // follows the measured wheel center in the same body-pose sample; q stays
    // available separately for diagnosis. This verified model has no offset
    // between pod and wheel origins except its +Z suspension slide.
    const displacement = new THREE.Vector3().fromArray(wheelPose.position).sub(new THREE.Vector3().fromArray(podPose.position)).applyQuaternion(podQ.clone().invert());
    if (Math.hypot(displacement.x, displacement.y) > .0002) continue;
    const slide = displacement.z;
    corner.pod.position.fromArray(podPose.position).sub(origin).applyQuaternion(inverse);
    corner.pod.quaternion.copy(inverse).multiply(podQ);
    corner.carrier.position.z = slide;
    corner.connector.position.z = Math.min(0, slide);
    corner.connector.scale.z = Math.abs(slide);
    corner.connector.visible = Math.abs(slide) > 1e-6;
    corner.pod.visible = true;
    corner.status = 'measured';
    corner.measured_slide_m = slide;
  }
  rig.status = rig.corners.every(c => c.status === 'measured') ? 'measured' : 'partially-unavailable';
  rig.root.visible = visible && rig.corners.some(c => c.status === 'measured');
}

// The caller supplies the loader and disposer so this module owns no network
// policy. loadAsset must verify the descriptor SHA before returning a scene.
export function createSuspensionSchematic({loadAsset, dispose}) {
  let rig = null, pending = null, key = null, target = null, generation = 0, loadError = null;
  function clear() {
    generation++; pending = null; key = null; target = null; loadError = null;
    if (rig) {rig.root.removeFromParent(); dispose(rig.root); rig = null;}
  }
  return {
    clear,
    get status() {return loadError ? {status:'unavailable', reason:loadError} : rig ? {
      status:rig.status, note:rig.note, corners:rig.corners.map(c => ({side:c.side, status:c.status, body_pose_slide_m:c.measured_slide_m, joint_slide_m:c.joint_slide_m})),
    } : {status:pending ? 'loading' : 'not-selected'};},
    update(model, truth, visible = true) {
      const descriptor = suspensionSchematicDescriptor(truth);
      const nextKey = descriptor ? descriptor.asset + ':' + descriptor.sha256 : null;
      const airframe = model?.getObjectByName('airframe');
      if (!descriptor || !airframe) {if (key !== null || rig || pending) clear(); return;}
      if (key !== nextKey || (target && target !== airframe)) clear();
      if (key === null) {
        key = nextKey;
        target = airframe;
        const token = generation;
        pending = Promise.resolve().then(() => loadAsset(descriptor)).then(root => {
          if (token !== generation || key !== nextKey) {dispose(root); return;}
          pending = null;
          rig = attachSuspensionSchematic(root, airframe);
          if (rig.corners.length !== 2 || rig.status !== 'attached') {
            loadError = 'Schematic asset binding is incompatible';
            root.removeFromParent(); dispose(root); rig = null;
          }
        }).catch(error => {if (token === generation) {pending = null; loadError = String(error?.message || error);}});
      }
      updateSuspensionSchematic(rig, truth, visible);
    },
  };
}
