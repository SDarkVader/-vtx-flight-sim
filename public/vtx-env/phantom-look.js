// Phantom render hook: drives the CAD joint empties of the Phantom GLB from rendering_truth.phantom.joints
// (MuJoCo joint values), plus the visual-pass systems from the plant's own state. Render only; no physics here.
// Each CAD-driven node carries glTF extras: phantom_joint, joint_type (hinge|slide), axis_parent, q_rest.
// Visual-pass systems (tools/phantom/refine_phantom_visual.py), all finite-rate:
//  * rear boosters: liner glow + directional blue plume (+ light) from booster thrust / thrust_max: a shallow glow at
//    low boost rising to a radiant blue jet; the conical petal cowl closes at low boost, opens at full boost and tilts
//    by the plant's booster vector angle;
//  * DRS / airbrake flap: deploys from the brake command above 12 m/s (actuator rate 140 deg/s);
//  * brake lamps (tail lenses + DRS trailing-edge strip) brighten on the brake command;
//  * wheel-hub ember glow follows each pod's fan rpm.
import * as THREE from 'three';

const PODS = ['FL', 'FR', 'RL', 'RR'];
const V3 = (a) => new THREE.Vector3(...a).normalize();
const clamp01 = (x) => Math.min(1, Math.max(0, x));
const approach = (x, target, maxStep) => x + Math.max(-maxStep, Math.min(maxStep, target - x));

// liner colour ramp for the "blue part": deep indigo (shallow glow) -> electric blue -> cyan-white (full boost)
const LINER = [new THREE.Color('#1c1460'), new THREE.Color('#2b6dff'), new THREE.Color('#c4ecff')];
function linerColour(b, out) {
  return b < 0.5 ? out.copy(LINER[0]).lerp(LINER[1], b / 0.5) : out.copy(LINER[1]).lerp(LINER[2], (b - 0.5) / 0.5);
}

function plumeMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: { uColour: { value: new THREE.Color('#3a8dff') }, uCore: { value: new THREE.Color('#d8f2ff') }, uBoost: { value: 0 } },
    vertexShader: `varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      void main(){ vUv=uv; vec4 mv=modelViewMatrix*vec4(position,1.); vN=normalize(normalMatrix*normal); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }`,
    fragmentShader: `uniform vec3 uColour; uniform vec3 uCore; uniform float uBoost; varying vec2 vUv; varying vec3 vN; varying vec3 vV;
      void main(){
        float along = vUv.y;                       // 1 at the nozzle exit -> 0 at the plume tip
        float rim = pow(abs(dot(vN, vV)), 1.6);    // bright core seen through the cone, soft edges
        float a = pow(along, 1.8) * rim * (0.25 + 0.75 * uBoost);
        vec3 c = mix(uColour, uCore, pow(along, 3.0) * uBoost);
        gl_FragColor = vec4(c * a * (0.6 + 1.6 * uBoost), a);
      }`,
  });
}

export function attachPhantom(model) {
  const joints = [];
  model.traverse(n => {
    const u = n.userData;
    if (u && u.phantom_joint) {
      joints.push({ node: n, name: u.phantom_joint, type: u.joint_type, axis: V3(u.axis_parent), q0: +u.q_rest, pos: n.position.clone(), quat: n.quaternion.clone() });
    }
  });
  const scene = model.parent;
  const quality = scene?.userData?.quality || 'high';
  const rig = { joints, petals: [], drs: null, brakeMats: [], boosters: {}, hubs: [], drsDeg: 0, petalDeg: {}, lastT: null, lastPos: null, speed: 0 };

  model.traverse(n => {
    const u = n.userData || {};
    if (n.name === 'VTX_VISUAL_DRS_HINGE') rig.drs = { node: n, axis: V3(u.axis_parent), quat: n.quaternion.clone(), max: (u.range_deg || [0, 55])[1] };
    if (/^VTX_VISUAL_BOOSTER_[LR]_PETAL_\d+_HINGE$/.test(n.name)) {
      rig.petals.push({ node: n, axis: V3(u.axis_parent), quat: n.quaternion.clone(), theta: THREE.MathUtils.degToRad(u.theta_deg || 0), side: u.booster, lo: u.range_deg[0], hi: u.range_deg[1] });
    }
    if (n.isMesh && n.material && /red LED (brake strip|tail-lamp lens)/.test(n.material.name || '')) {
      if (!rig.brakeMats.some(m => m.mat === n.material)) rig.brakeMats.push({ mat: n.material, base: n.material.emissiveIntensity });
    }
  });

  // boosters: per-side liner material (so the two sides can differ) + plume + optional light
  const plumeGeo = new THREE.CylinderGeometry(0.135, 0.025, 1, 28, 1, true);
  plumeGeo.rotateZ(Math.PI / 2);                 // cylinder axis -> body x
  plumeGeo.translate(-0.5, 0, 0);                // starts at the origin, extends aft (-x)
  for (const [side, tag] of [['left', 'R'], ['right', 'L']]) {   // plant: physical left = +Y = CAD "R"
    const liner = model.getObjectByName(`POWER_${tag}_CERAMIC_EXHAUST_LINER`);
    if (!liner || !liner.isMesh) continue;
    liner.material = liner.material.clone();
    const host = liner.parent;
    const exit = new THREE.Group(); exit.name = `VTX_RUNTIME_BOOSTER_${tag}_PLUME`;
    exit.position.set(-2.60, liner.position.y, liner.position.z);
    const plume = new THREE.Mesh(plumeGeo, plumeMaterial());
    plume.frustumCulled = false; plume.renderOrder = 10; plume.visible = false;
    exit.add(plume);
    let light = null;
    if (quality !== 'low') {
      light = new THREE.PointLight('#4f9bff', 0, 4.5, 2);
      light.position.set(-0.45, 0, 0);
      exit.add(light);
    }
    host.add(exit);
    rig.boosters[side] = { liner, plume, light, exit, boost: 0 };
    rig.petalDeg[side] = 0;
  }

  // wheel-hub ember glow per pod (CAD wheel names are mirrored: read the pod joint above each hub)
  model.traverse(n => {
    if (!/_CORE_GLOW$/.test(n.name) || !n.isMesh) return;
    let p = n.parent, pod = null;
    while (p && !pod) { if (p.userData?.phantom_joint?.startsWith('pod_')) pod = p.userData.phantom_joint.slice(4); p = p.parent; }
    if (!pod) return;
    n.material = n.material.clone();
    rig.hubs.push({ mesh: n, idx: PODS.indexOf(pod), base: n.material.emissiveIntensity });
  });
  if (typeof window !== 'undefined') window.__phantomRig = rig;   // inspection handle (console / tests)
  return rig;
}

const tmp = new THREE.Quaternion();
export function updatePhantom(rig, truth) {
  if (!rig || !truth) return;
  const q = truth.phantom?.joints;
  if (q) {
    for (const j of rig.joints) {
      const v = q[j.name]; if (v === undefined) continue; const d = v - j.q0;
      if (j.type === 'slide') { j.node.position.copy(j.pos).addScaledVector(j.axis, d); }
      else { tmp.setFromAxisAngle(j.axis, d); j.node.quaternion.copy(tmp).multiply(j.quat); }
    }
  }
  // time step and ground speed from the plant's own clock and airframe pose
  const t = truth.t_s, pos = truth.body_poses?.airframe?.position;
  let dt = 0;
  if (rig.lastT != null && t > rig.lastT) {
    dt = Math.min(0.5, t - rig.lastT);
    if (pos && rig.lastPos) rig.speed = Math.hypot(pos[0] - rig.lastPos[0], pos[1] - rig.lastPos[1]) / (t - rig.lastT);
  }
  rig.lastT = t; if (pos) rig.lastPos = pos.slice();
  const cmd = truth.command || {};
  const brake = Array.isArray(cmd.brake) ? cmd.brake.reduce((a, b) => a + b, 0) / cmd.brake.length : 0;
  const braking = brake > 0.3;

  // boosters: glow, plume, light from thrust / thrust_max (fallback: commanded throttle)
  const tmax = truth.phantom?.booster_thrust_max_n || 0;
  const bs = truth.boosters || [];
  const col = new THREE.Color();
  ['left', 'right'].forEach((side, j) => {
    const B = rig.boosters[side]; if (!B) return;
    const thr = bs[j]?.thrust_n, thrCmd = cmd.booster_throttle?.[j] ?? 0;
    const target = tmax > 0 && thr != null ? clamp01(thr / tmax) : clamp01(thrCmd);
    B.boost = dt > 0 ? approach(B.boost, target, 3 * dt) : target;     // visual smoothing only (plant already spools)
    const b = B.boost;
    linerColour(b, col);
    B.liner.material.emissive.copy(col);
    B.liner.material.emissiveIntensity = 0.18 + 3.4 * Math.pow(b, 1.3);
    const on = b > 0.04;
    B.plume.visible = on;
    if (on) {
      B.plume.scale.set(0.3 + 2.6 * Math.pow(b, 0.9), 0.75 + 0.35 * b, 0.75 + 0.35 * b);
      B.plume.material.uniforms.uBoost.value = b;
      linerColour(Math.max(0.35, b), B.plume.material.uniforms.uColour.value);
    }
    if (B.light) B.light.intensity = on ? 2.5 * Math.pow(b, 1.2) : 0;
    // cone cowl: closed at low boost, open at full; tilted by the plant's booster vector angle (pitch)
    const close = 10 - 14 * b, vec = truth.phantom?.booster_vector_deg || 0;
    const tilt = THREE.MathUtils.degToRad(vec);
    B.exit.rotation.set(0, -tilt, 0);
    rig.petalDeg[side] = dt > 0 ? approach(rig.petalDeg[side], close, 60 * dt) : close;
    for (const p of rig.petals) {
      if (p.side !== side) continue;
      const deg = THREE.MathUtils.clamp(rig.petalDeg[side] + vec * Math.cos(p.theta), p.lo, p.hi);
      tmp.setFromAxisAngle(p.axis, THREE.MathUtils.degToRad(deg)); p.node.quaternion.copy(tmp).multiply(p.quat);
    }
  });

  // DRS / airbrake: brake command above 12 m/s, finite actuator rate
  if (rig.drs) {
    // P6 on: the plant flies the flap (truth.phantom.drs_deg, trailing edge up); the GLB rest pose sits at 6 deg
    const plantDeg = truth.phantom?.drs_deg;
    const target = plantDeg != null ? plantDeg - 6 : (braking && rig.speed > 12 ? rig.drs.max : 0);
    rig.drsDeg = dt > 0 ? approach(rig.drsDeg, target, 140 * dt) : target;
    tmp.setFromAxisAngle(rig.drs.axis, THREE.MathUtils.degToRad(rig.drsDeg)); rig.drs.node.quaternion.copy(tmp).multiply(rig.drs.quat);
  }
  // brake lamps
  for (const m of rig.brakeMats) m.mat.emissiveIntensity = braking ? m.base * 2.8 : m.base;
  // wheel-hub ember glow follows each pod's fan rpm
  const rpm = truth.phantom?.fan_rpm, rmax = truth.phantom?.fan_rpm_max || 0;
  if (rpm && rmax > 0) for (const h of rig.hubs) if (h.idx >= 0) h.mesh.material.emissiveIntensity = h.base * (0.25 + 2.2 * clamp01(rpm[h.idx] / rmax));
}
