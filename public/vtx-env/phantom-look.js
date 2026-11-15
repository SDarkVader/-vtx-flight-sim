// Phantom render hook: drives the CAD joint empties of the Phantom GLB from rendering_truth.phantom.joints
// (MuJoCo joint values), plus the visual-pass systems from the plant's own state. Render only; no physics here.
// Each CAD-driven node carries glTF extras: phantom_joint, joint_type (hinge|slide), axis_parent, q_rest.
// Visual-pass systems (tools/phantom/refine_phantom_visual.py), all finite-rate:
//  * rear boosters: liner glow + directional blue plume (+ light) from booster thrust / thrust_max: a shallow glow at
//    low boost rising to a radiant blue jet; the conical petal cowl closes at low boost, opens at full boost and tilts
//    by the plant's booster vector angle;
//  * DRS / airbrake flap: follows the plant's stabilator state when modelled;
//  * brake lamps (tail lenses + DRS trailing-edge strip) brighten on the brake command;
//  * wheel-hub ember glow follows each pod's fan rpm.
import * as THREE from 'three';
import {thrustFraction, wheelAngle} from './phantom-effects.js?v=1';

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
        float along = 1.0 - vUv.y;                 // 1 at the nozzle exit -> 0 at the plume tip
        float rim = pow(abs(dot(vN, vV)), 1.6);    // bright core seen through the cone, soft edges
        float a = pow(along, 1.8) * rim * (0.25 + 0.75 * uBoost);
        vec3 c = mix(uColour, uCore, pow(along, 3.0) * uBoost);
        gl_FragColor = vec4(c * a * (0.6 + 1.6 * uBoost), a);
      }`,
  });
}

function heatCoreMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    uniforms: {uIntensity: {value: 0}},
    vertexShader: `varying vec2 vUv; void main(){vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader: `uniform float uIntensity; varying vec2 vUv;
      void main(){float a=pow(1.0-vUv.y,1.2)*uIntensity; gl_FragColor=vec4(vec3(.78,.94,1.)*a,a);}`
  });
}

// Appearance only: reuse the A10's existing surfaces and articulated geometry.
// Values are linear RGB, matching the glTF material factors. No lights, thrust
// effects, geometry, joints or simulation properties are added or changed.
const exteriorPalette={
  'A6 sharp graphite armour facet': {color:[.105,.12,.14],metalness:.76,roughness:.3},
  'A6 VTX Phantom satin gunmetal armour': {color:[.075,.085,.105],metalness:.72,roughness:.32},
  'A6 dark carbon structural CFRP': {color:[.035,.04,.05],metalness:.42,roughness:.4},
  'A6 dark wheel face and thrust cover': {color:[.035,.04,.05],metalness:.65,roughness:.3},
  'A6 amber accent light': {color:[1,.48,.025],emissive:[1,.35,.012],emissiveIntensity:1.15},
  'Vaders amber luminescent edge': {color:[1,.48,.025],emissive:[1,.35,.012],emissiveIntensity:1.15},
};

function stylePhantom(model){
  const variants=new Map();
  model.traverse(node=>{
    if(!node.isMesh||!node.material)return;
    const headlamp=/^FACE_[LR]_AMBER_CHEVRON_LAMP/.test(node.name);
    const style=material=>{
      const preset=headlamp?{color:[.8,.9,1],emissive:[.65,.8,1],emissiveIntensity:1.5}:exteriorPalette[material.name];
      if(!preset)return material;
      let pair=variants.get(material);
      if(!pair){pair={};variants.set(material,pair);}
      const key=headlamp?'headlamp':'exterior';
      if(pair[key])return pair[key];
      const copy=material.clone();
      if(preset.color)copy.color.setRGB(...preset.color);
      if(preset.emissive&&copy.emissive)copy.emissive.setRGB(...preset.emissive);
      if(preset.emissiveIntensity!==undefined)copy.emissiveIntensity=preset.emissiveIntensity;
      if(preset.metalness!==undefined)copy.metalness=preset.metalness;
      if(preset.roughness!==undefined)copy.roughness=preset.roughness;
      return pair[key]=copy;
    };
    node.material=Array.isArray(node.material)?node.material.map(style):style(node.material);
  });
}

// An exposed, faceted rear-deck detail, attached to the rendered airframe only.
// It is deliberately separate from the sliding wings and all simulation bodies.
function addRearDeckDetail(model){
  const airframe=model.getObjectByName('airframe');
  if(!airframe)return;
  const deck=new THREE.Group();
  deck.name='phantom_visual_rear_deck';
  const dark=new THREE.MeshStandardMaterial({color:0x111923,metalness:.72,roughness:.34});
  const edge=new THREE.MeshStandardMaterial({color:0xd09224,metalness:.75,roughness:.3});
  const ribGeometry=new THREE.BoxGeometry(.055,.56,.035);
  const trimGeometry=new THREE.BoxGeometry(.012,.54,.008);
  for(let i=0;i<5;i++){
    const rib=new THREE.Mesh(ribGeometry,dark);
    rib.position.set(-1.45-i*.105,0,.91+i*.008);
    deck.add(rib);
    const trim=new THREE.Mesh(trimGeometry,edge);
    trim.position.set(-1.424-i*.105,0,.93+i*.008);
    deck.add(trim);
  }
  airframe.add(deck);
}

export function attachPhantom(model) {
  if (model.getObjectByName('A10_WING_L_PANEL_CFRP_TORSION_BOX')) {
    stylePhantom(model);
    addRearDeckDetail(model);
  }
  const joints = [];
  model.traverse(n => {
    const u = n.userData;
    if (u && u.phantom_joint) {
      joints.push({ node: n, name: u.phantom_joint, type: u.joint_type, axis: V3(u.axis_parent), q0: +u.q_rest, pos: n.position.clone(), quat: n.quaternion.clone() });
    }
  });
  const scene = model.parent;
  const quality = scene?.userData?.quality || 'high';
  const rig = { joints, petals: [], drs: null, brakeMats: [], boosters: {}, hubs: [], wheels: [], podJets: [], drsDeg: 0, petalDeg: {}, lastT: null, lastPos: null, speed: 0 };

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

  // Build presentation pivots only for authored rotating tyre/rim parts.
  // The GLB uses mirrored CAD labels, so use the physics joint metadata on each pod.
  model.updateMatrixWorld(true);
  for (const j of joints) {
    if (!/^pod_(FL|FR|RL|RR)$/.test(j.name)) continue;
    const pod = j.name.slice(4), idx = PODS.indexOf(pod);
    const cad = j.node.name.replace('JOINT_WHEEL_POD_', '');
    const suspension = new THREE.Group();
    suspension.name = `VTX_RUNTIME_WHEEL_${pod}_SUSPENSION`;
    j.node.add(suspension);
    const steering = new THREE.Group();
    steering.name = `VTX_RUNTIME_WHEEL_${pod}_STEERING`;
    suspension.add(steering);
    const wheel = new THREE.Group();
    wheel.name = `VTX_RUNTIME_WHEEL_${pod}_SPIN`;
    steering.add(wheel);
    for (const suffix of ['AMBER_RING', 'CLOSED_TYRE', 'STRUCTURAL_DISK']) {
      const part = j.node.getObjectByName(`WHEEL_${cad}_${suffix}`);
      if (part) wheel.attach(part);
    }
    const spokes = j.node.getObjectByName(`VTX_VISUAL_WHEEL_${cad}_VTX_ALLOY_SPOKES`);
    if (spokes) wheel.attach(spokes);
    // Measure the authored tyre in wheel coordinates. The original asset remains
    // untouched; radial scaling is uniform around the physical wheel axis.
    const tyre = wheel.getObjectByName(`WHEEL_${cad}_CLOSED_TYRE`);
    let authored = null;
    if (tyre?.isMesh && tyre.geometry) {
      tyre.geometry.computeBoundingBox();
      wheel.updateWorldMatrix(true, true);
      const relative = new THREE.Matrix4().copy(wheel.matrixWorld).invert().multiply(tyre.matrixWorld);
      const bounds = tyre.geometry.boundingBox?.clone().applyMatrix4(relative);
      if (bounds && !bounds.isEmpty()) {
        const size = bounds.getSize(new THREE.Vector3()), center = bounds.getCenter(new THREE.Vector3());
        if (size.x > 0 && size.y > 0 && size.z > 0 && Math.abs(size.x - size.z) < Math.max(size.x, size.z) * .02 && center.length() < .005) {
          authored = {radius_m: (size.x + size.z) / 4, half_width_m: size.y / 2};
        }
      }
    }
    rig.wheels.push({node: wheel, suspension, steering, podJoint: j, idx, authored, fit: {status: 'unavailable'}, axis: new THREE.Vector3(0, pod.endsWith('L') ? 1 : -1, 0)});

    // Exhaust points opposite the force axis and turns with the actual pod joint.
    const jet = new THREE.Group();
    jet.name = `VTX_RUNTIME_POD_${pod}_EXHAUST`;
    jet.rotation.y = pod.endsWith('L') ? 0 : Math.PI;
    const geometry = new THREE.CylinderGeometry(.035, .19, 1, 24, 1, true);
    geometry.rotateX(Math.PI / 2); geometry.translate(0, 0, .5);
    const glow = new THREE.Mesh(geometry, plumeMaterial());
    glow.frustumCulled = false; glow.renderOrder = 10; glow.visible = false;
    jet.add(glow);
    const coreGeometry = new THREE.CylinderGeometry(.015, .085, 1, 20, 1, true);
    coreGeometry.rotateX(Math.PI / 2); coreGeometry.translate(0, 0, .5);
    const core = new THREE.Mesh(coreGeometry, heatCoreMaterial());
    core.frustumCulled = false; core.renderOrder = 11; jet.add(core);
    j.node.add(jet);
    rig.podJets.push({pod, idx, glow, core});
  }

  // boosters: per-side liner material (so the two sides can differ) + plume + optional light
  const plumeGeo = new THREE.CylinderGeometry(0.025, 0.135, 1, 28, 1, true);
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
    const coreGeo = new THREE.CylinderGeometry(.008, .05, 1, 24, 1, true);
    coreGeo.rotateZ(Math.PI / 2); coreGeo.translate(-.5, 0, 0);
    const core = new THREE.Mesh(coreGeo, heatCoreMaterial());
    core.frustumCulled = false; core.renderOrder = 11; exit.add(core);
    let light = null;
    if (quality !== 'low') {
      light = new THREE.PointLight('#4f9bff', 0, 4.5, 2);
      light.position.set(-0.45, 0, 0);
      exit.add(light);
    }
    host.add(exit);
    rig.boosters[side] = { liner, plume, core, light, exit, boost: 0 };
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
  // Record the actual past emitter positions as a short, purely visual wake.
  // Each wake lives in world space so it stays behind as the aircraft moves.
  rig.trails = [];
  if (scene) {
    rig.trailRoot = new THREE.Group();
    rig.trailRoot.name = 'VTX_RUNTIME_THRUST_TRAILS';
    scene.add(rig.trailRoot);
    for (const source of [...rig.podJets, ...Object.values(rig.boosters)]) {
      const line = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({
        color: 0x72ccff, transparent: true, opacity: .65, vertexColors: true,
        blending: THREE.AdditiveBlending, depthWrite: false
      }));
      line.frustumCulled = false; line.renderOrder = 9; rig.trailRoot.add(line);
      rig.trails.push({source, emitter: source.glow || source.exit, line, samples: [], lastT: null});
    }
  }
  if (typeof window !== 'undefined') window.__phantomRig = rig;   // inspection handle (console / tests)
  return rig;
}

const tmp = new THREE.Quaternion(); const ZUP = new THREE.Vector3(0,0,1);
// These recorded configurations have no rear steer joint. A missing value is
// accepted only if the measured body quaternions also confirm zero steering.
const fixedRearSteerConfigs = {
  'phantom-a10b': '3ecae1a925a637825d422886d5e0c1f94fdd674e5b9dd35f572590bd2b13cb01',
  'phantom-a10c': '2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f',
  'phantom-a10c-runway-20261112': '2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f',
  'phantom-a10c-vtol-20261112': '2fee0b4036382d033ed927ce7e56f48bd362a2c15893344f5c8c691b5587049f',
};
export function updatePhantom(rig, truth, parked = false, wheelOffsets = [], requireWheelPose = false) {
  if (!rig || !truth) return;
  const q = truth.phantom?.joints;
  if (q || parked) {
    for (const j of rig.joints) {
      const raw = q?.[j.name]; if (!Number.isFinite(raw) && !parked) continue; const v = parked && /^pod_(FL|FR|RL|RR)$/.test(j.name) ? (j.name.endsWith("L") ? Math.PI / 2 : -Math.PI / 2) : parked && j.name.startsWith("leg_") ? 0 : raw; if (!Number.isFinite(v) || !Number.isFinite(j.q0)) continue; const oleo = q?.[`${j.name}_oleo`]; const compression = /^leg_(FL|FR|RL|RR)$/.test(j.name) && !parked && Number.isFinite(oleo) ? oleo : 0; const d = v - j.q0 + compression;
      if (j.type === 'slide') { j.node.position.copy(j.pos).addScaledVector(j.axis, d); }
      else { tmp.setFromAxisAngle(j.axis, d); j.node.quaternion.copy(tmp).multiply(j.quat); }
    }
  }
  for (const wheel of rig.wheels) {
    const pod = PODS[wheel.idx];
    const rootPose = truth.body_poses?.airframe, podPose = truth.body_poses?.[`pod_${pod}`];
    const validArray = (a, n) => Array.isArray(a) && a.length === n && a.every(Number.isFinite);
    let anchorAligned = false;
    if (!parked && wheel.podJoint.node.parent?.name === 'airframe' && validArray(rootPose?.position, 3) && validArray(rootPose?.quaternion_wxyz, 4) && validArray(podPose?.position, 3)) {
      const r = rootPose.quaternion_wxyz;
      const inverse = new THREE.Quaternion(r[1], r[2], r[3], r[0]);
      if (inverse.lengthSq() > 1e-12) {
        inverse.normalize().invert();
        wheel.podJoint.node.position.fromArray(podPose.position).sub(new THREE.Vector3().fromArray(rootPose.position)).applyQuaternion(inverse);
        anchorAligned = true;
      }
    }
    if (!anchorAligned) wheel.podJoint.node.position.copy(wheel.podJoint.pos);
    const physical = truth.phantom?.wheel_collision_geometry?.[pod];
    if (!parked && wheel.authored && Number.isFinite(physical?.radius_m) && physical.radius_m > 0 && Number.isFinite(physical?.half_width_m) && physical.half_width_m > 0) {
      const radial = physical.radius_m / wheel.authored.radius_m, width = physical.half_width_m / wheel.authored.half_width_m;
      wheel.node.scale.set(radial, width, radial);
      wheel.fit = {status: anchorAligned ? 'collider-aligned' : 'collider-scaled-anchor-unavailable', authored: wheel.authored, collider: physical, radial_scale: radial, width_scale: width};
    } else {
      wheel.node.scale.set(1, 1, 1);
      wheel.fit = {status: anchorAligned ? 'anchor-aligned-size-unavailable' : 'unavailable'};
    }
    const suspension = q?.[`pod_${pod}_susp`];
    const steering = q?.[`pod_${pod}_steer`];
    const angle = wheelAngle(q?.[`pod_${pod}_wheel`], wheelOffsets[wheel.idx]);
    let confirmedFixedSteer = false, measuredSpin = null, measuredSteer = null;
    const knownConfig = Object.hasOwn(fixedRearSteerConfigs, truth.variant) && fixedRearSteerConfigs[truth.variant] === truth.config_sha256;
    if (knownConfig && Number.isFinite(q?.[`pod_${pod}_wheel`])) {
      const a = podPose?.quaternion_wxyz, b = truth.body_poses?.[`pod_${pod}_wheel`]?.quaternion_wxyz;
      if (validArray(a, 4) && validArray(b, 4)) {
        const podQ = new THREE.Quaternion(a[1], a[2], a[3], a[0]);
        const actualQ = new THREE.Quaternion(b[1], b[2], b[3], b[0]);
        if (podQ.lengthSq() > 1e-12 && actualQ.lengthSq() > 1e-12) {
          // MuJoCo body poses and joint positions can differ by one integration
          // step. Decompose the measured relative orientation into the wheel's
          // Y-axis spin and its Z-axis steering instead of mixing phases.
          const relative = podQ.normalize().invert().multiply(actualQ.normalize()).normalize();
          const spin = new THREE.Quaternion(0, relative.y, 0, relative.w);
          if (spin.lengthSq() > 1e-12) {
            spin.normalize();
            const steer = relative.clone().multiply(spin.clone().invert()).normalize();
            if (Math.hypot(steer.x, steer.y) < 1e-5) {
              if (pod.startsWith('R') && steering === undefined && Math.abs(steer.z) < 1e-5) {
                confirmedFixedSteer = true;
                measuredSpin = spin;
              } else if (pod.startsWith('F') && Number.isFinite(steering)) {
                measuredSpin = spin;
                measuredSteer = new THREE.Quaternion(0, 0, steer.z, steer.w).normalize();
              }
            }
          }
        }
      }
    }
    const missing = [
      [`pod_${pod}`, q?.[`pod_${pod}`]],
      [`pod_${pod}_susp`, suspension],
      [`pod_${pod}_steer`, confirmedFixedSteer ? 0 : steering],
      [`pod_${pod}_wheel`, q?.[`pod_${pod}_wheel`]],
    ].filter(([, value]) => !Number.isFinite(value)).map(([name]) => name);
    if (!Number.isFinite(wheel.podJoint.q0)) missing.push(`pod_${pod}_asset_rest`);
    // The physical view must not carry a wheel pose over from an earlier
    // snapshot when its joints are absent. The separate scripted animation
    // deliberately permits unmeasured, neutral wheel presentation.
    wheel.node.visible = !requireWheelPose || missing.length === 0;
    const podAvailable = Number.isFinite(q?.[`pod_${pod}`]) && Number.isFinite(wheel.podJoint.q0);
    wheel.podJoint.node.visible = !requireWheelPose || podAvailable;
    if (!podAvailable && requireWheelPose) wheel.podJoint.node.quaternion.copy(wheel.podJoint.quat);
    wheel.fit.pose_status = missing.length ? 'unavailable' : confirmedFixedSteer ? 'measured-fixed-steering' : 'measured';
    wheel.fit.missing_joints = missing;
    wheel.suspension.position.z = Number.isFinite(suspension) ? suspension : 0;
    if (measuredSteer) wheel.steering.quaternion.copy(measuredSteer);
    else if (Number.isFinite(steering)) wheel.steering.quaternion.setFromAxisAngle(ZUP, steering);
    else wheel.steering.quaternion.identity();
    if (measuredSpin) {
      // Start from the recorded wheel-body pose; velocity-derived sub-frame
      // motion is presentation-only and is zero during replay.
      wheel.node.quaternion.copy(measuredSpin);
      if (Number.isFinite(wheelOffsets[wheel.idx])) {
        wheel.node.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(wheel.axis, wheelOffsets[wheel.idx]));
      }
    } else if (angle !== null) wheel.node.quaternion.setFromAxisAngle(wheel.axis, angle);
    else wheel.node.quaternion.identity();
  }
  const fans = truth.propulsors || [], fanMax = truth.phantom?.fan_thrust_max_n;
  for (const jet of rig.podJets) {
    const fan = fans.find(f => f.pod === jet.pod);
    const b = thrustFraction(fan?.thrust_n, fanMax);
    jet.thrust = b;
    const on = b > .01;
    jet.glow.visible = jet.core.visible = on;
    if (on) {
      const length = .18 + 1.65 * Math.sqrt(b);
      jet.glow.scale.set(.65 + .6*b, .65 + .6*b, length);
      jet.glow.material.uniforms.uBoost.value = b;
      jet.core.scale.set(.6 + .45*b, .6 + .45*b, length * .58);
      jet.core.material.uniforms.uIntensity.value = .32 + .62*b;
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

  // boosters: glow, plume and light from simulated thrust / thrust_max
  const tmax = truth.phantom?.booster_thrust_max_n || 0;
  const bs = truth.boosters || [];
  const col = new THREE.Color();
  ['left', 'right'].forEach((side, j) => {
    const B = rig.boosters[side]; if (!B) return;
    const target = thrustFraction(bs[j]?.thrust_n, tmax);
    B.boost = dt > 0 ? approach(B.boost, target, 3 * dt) : target;     // visual smoothing only (plant already spools)
    const b = B.boost;
    linerColour(b, col);
    B.liner.material.emissive.copy(col);
    B.liner.material.emissiveIntensity = 0.18 + 3.4 * Math.pow(b, 1.3);
    const on = b > 0.04;
    B.plume.visible = B.core.visible = on;
    if (on) {
      B.plume.scale.set(0.3 + 2.6 * Math.pow(b, 0.9), 0.75 + 0.35 * b, 0.75 + 0.35 * b);
      B.plume.material.uniforms.uBoost.value = b;
      B.core.scale.set((0.3 + 2.6 * Math.pow(b, 0.9)) * .55, .8 + .45*b, .8 + .45*b);
      B.core.material.uniforms.uIntensity.value = .35 + .6*b;
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

  // DRS / airbrake: use the plant's actual finite-rate state, not a second
  // cosmetic controller driven by the brake command.
  if (rig.drs) {
    // P6 on: the plant flies the flap (trailing edge up); the GLB rest pose sits at 6 deg.
    const plantDeg = truth.phantom?.drs_deg;
    rig.drsDeg = Number.isFinite(plantDeg) ? plantDeg - 6 : 0;
    tmp.setFromAxisAngle(rig.drs.axis, THREE.MathUtils.degToRad(rig.drsDeg)); rig.drs.node.quaternion.copy(tmp).multiply(rig.drs.quat);
  }
  // brake lamps
  for (const m of rig.brakeMats) m.mat.emissiveIntensity = braking ? m.base * 2.8 : m.base;
  // wheel-hub ember glow follows each pod's fan rpm
  const rpm = truth.phantom?.fan_rpm, rmax = truth.phantom?.fan_rpm_max || 0;
  if (rpm && rmax > 0) for (const h of rig.hubs) if (h.idx >= 0) h.mesh.material.emissiveIntensity = h.base * (0.25 + 2.2 * clamp01(rpm[h.idx] / rmax));

  if (Number.isFinite(t) && rig.trails.length) {
    for (const trail of rig.trails) {
      if (trail.lastT !== null && t < trail.lastT) { trail.samples = []; trail.lastT = null; }
      if (trail.lastT === null || t - trail.lastT >= .08) {
        const strength = trail.source.thrust ?? trail.source.boost ?? 0;
        if (strength > .02) {
          const point = new THREE.Vector3();
          trail.emitter.getWorldPosition(point);
          trail.samples.push({point, t, strength});
        }
        trail.samples = trail.samples.filter(sample => t - sample.t <= 2).slice(-32);
        trail.lastT = t;
        const positions = [], colors = [];
        for (const sample of trail.samples) {
          positions.push(sample.point.x, sample.point.y, sample.point.z);
          const brightness = sample.strength * Math.max(0, 1 - (t - sample.t) / 2);
          colors.push(brightness, brightness, brightness);
        }
        trail.line.geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        trail.line.geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        trail.line.visible = trail.samples.length > 1;
      }
    }
  }
}

export function detachPhantomEffects(rig) {
  if (!rig?.trailRoot) return;
  rig.trailRoot.removeFromParent();
  for (const trail of rig.trails) { trail.line.geometry.dispose(); trail.line.material.dispose(); }
  rig.trails = []; rig.trailRoot = null;
}
