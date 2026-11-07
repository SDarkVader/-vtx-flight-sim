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
    const wheel = new THREE.Group();
    wheel.name = `VTX_RUNTIME_WHEEL_${pod}_SPIN`;
    j.node.add(wheel);
    for (const suffix of ['AMBER_RING', 'CLOSED_TYRE', 'STRUCTURAL_DISK']) {
      const part = j.node.getObjectByName(`WHEEL_${cad}_${suffix}`);
      if (part) wheel.attach(part);
    }
    const spokes = j.node.getObjectByName(`VTX_VISUAL_WHEEL_${cad}_VTX_ALLOY_SPOKES`);
    if (spokes) wheel.attach(spokes);
    rig.wheels.push({node: wheel, idx, axis: new THREE.Vector3(0, 0, pod.endsWith('L') ? -1 : 1)});

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

const tmp = new THREE.Quaternion();
export function updatePhantom(rig, truth, parked = false, wheelOffsets = []) {
  if (!rig || !truth) return;
  const q = truth.phantom?.joints;
  if (q || parked) {
    for (const j of rig.joints) {
      const raw = q?.[j.name]; if (raw === undefined && !parked) continue; const v = parked && /^pod_(FL|FR|RL|RR)$/.test(j.name) ? (j.name.endsWith("L") ? Math.PI / 2 : -Math.PI / 2) : parked && j.name.startsWith("leg_") ? 0 : raw; if (v === undefined) continue; const d = v - j.q0;
      if (j.type === 'slide') { j.node.position.copy(j.pos).addScaledVector(j.axis, d); }
      else { tmp.setFromAxisAngle(j.axis, d); j.node.quaternion.copy(tmp).multiply(j.quat); }
    }
  }
  for (const wheel of rig.wheels) {
    const pod = PODS[wheel.idx];
    const angle = wheelAngle(q?.[`pod_${pod}_wheel`], wheelOffsets[wheel.idx]);
    if (angle !== null) wheel.node.quaternion.setFromAxisAngle(wheel.axis, angle);
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
