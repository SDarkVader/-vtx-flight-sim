// Sky dome, golden-hour lighting, aerial perspective (sun-aware height fog), clouds,
// image-based reflections and a view-fitted sun shadow. Visual only.
import * as THREE from 'three';
import { cloudTexture, glowTexture, rng } from './textures.js';
import { tierOf } from './quality.js';

export const SUN_DIR = new THREE.Vector3(-0.80, -0.50, 0.30).normalize(); // low evening sun, west-south-west
// Linear (pre-tone-mapping) radiances shared by the sky shader and the fog, so distant
// terrain fades exactly into the sky behind it.
const HOR = [0.92, 0.50, 0.30];      // horizon haze away from the sun
const HOR_SUN = [1.50, 0.70, 0.32];  // horizon haze toward the sun (forward scattering)
const ZEN = [0.050, 0.120, 0.300];   // zenith
export const HAZE = new THREE.Color().setRGB(...HOR, THREE.LinearSRGBColorSpace); // fog colour (linear)
const v3 = (a) => `vec3(${a.map((x) => x.toFixed(4)).join(',')})`;
const SKY_FN = `
  vec3 vtxHaze(vec3 d){
    float mu = max(dot(d, ${v3(SUN_DIR.toArray())}), 0.0);
    return mix(${v3(HOR)}, ${v3(HOR_SUN)}, pow(mu, 5.0));
  }`;

// Replace three's fog chunks (once, before any program compiles) with:
//  - a world-space ray so the fog colour can follow the sun direction (aerial perspective);
//  - optional exponential height fog (denser in the valley, clearer up high);
//  - the fog colour tone-mapped and encoded like the sky, because three applies fog after
//    tone mapping. Falls back silently to the stock chunks if the r170 text is not found.
let fogInstalled = null;
function installFog(heightFog) {
  if (fogInstalled !== null) return fogInstalled;
  const C = THREE.ShaderChunk;
  if (!/vFogDepth = - mvPosition\.z;/.test(C.fog_vertex) || !/gl_FragColor\.rgb = mix\( gl_FragColor\.rgb, fogColor, fogFactor \);/.test(C.fog_fragment)) return (fogInstalled = false);
  C.fog_pars_vertex = '#ifdef USE_FOG\n\tvarying float vFogDepth;\n\tvarying vec3 vFogWorld;\n#endif';
  C.fog_vertex = '#ifdef USE_FOG\n\tvFogDepth = - mvPosition.z;\n\tvFogWorld = ( mvPosition.xyz - viewMatrix[3].xyz ) * mat3( viewMatrix );\n#endif';
  C.fog_pars_fragment = C.fog_pars_fragment.replace('varying float vFogDepth;', `varying float vFogDepth;\n\tvarying vec3 vFogWorld;\n${SKY_FN}`);
  C.fog_fragment = `#ifdef USE_FOG
  vec3 vtxRay = vFogWorld - cameraPosition; float vtxDist = max(length(vtxRay), 1e-3);
  #ifdef FOG_EXP2
    float vtxK = ${(1 / 260).toFixed(6)};
    float vtxH0 = max(cameraPosition.z, -20.0), vtxH1 = max(vFogWorld.z, -20.0), vtxDh = vtxH1 - vtxH0;
    float vtxHf = abs(vtxDh) > 0.05 ? (exp(-vtxK * vtxH0) - exp(-vtxK * vtxH1)) / (vtxK * vtxDh) : exp(-vtxK * vtxH0);
    float fogFactor = 1.0 - exp( - fogDensity * vtxDist * ${heightFog ? 'vtxHf' : '1.0'} );
  #else
    float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
  #endif
  vec3 vtxFog = vtxHaze(vtxRay / vtxDist) * (fogColor / ${v3(HOR)});
  #ifdef TONE_MAPPING
    vtxFog = toneMapping( vtxFog );
  #endif
  gl_FragColor.rgb = mix( gl_FragColor.rgb, linearToOutputTexel( vec4( vtxFog, 1.0 ) ).rgb, fogFactor );
#endif`;
  return (fogInstalled = true);
}

const skyMaterial = () => new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: { sunDir: { value: SUN_DIR.clone() } },
  vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader: `
    varying vec3 vDir; uniform vec3 sunDir;
    ${SKY_FN}
    void main(){
      vec3 d = normalize(vDir); float h = d.z, mu = dot(d, sunDir);
      vec3 haze = vtxHaze(d);
      // horizon-weighted blend to the zenith, with a cooler band above the warm haze
      float t = pow(1.0 - clamp(h, 0.0, 1.0), 5.0);
      vec3 c = mix(${v3(ZEN)}, mix(vec3(.30,.38,.52), haze, smoothstep(.25,.9,t)), smoothstep(0.0, 1.0, t));
      // Mie glow around the sun and the sun disc
      float m = max(mu, 0.0);
      c += vec3(1.0,.62,.30) * (pow(m, 12.0) * .30 + pow(m, 80.0) * .45);
      c += vec3(22.0,16.0,10.0) * smoothstep(.99955, .99975, mu);
      // below the horizon: haze darkening into the ground bounce
      if (h < 0.0) c = mix(haze, haze * vec3(.55,.48,.44), smoothstep(0.0, -.25, h));
      gl_FragColor = vec4(c, 1.);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,

});

export function buildSky(scene, renderer, opts = {}) {
  const q = tierOf(opts), shadows = opts.shadows ?? q.shadows, shadowSize = opts.shadowSize ?? q.shadowSize ?? 2048;
  const heightFog = q.heightFog !== false;
  const lowTier = q.name === 'low'; if (!lowTier) installFog(heightFog);
  const group = new THREE.Group(); group.name = 'sky';
  const dome = new THREE.Mesh(new THREE.SphereGeometry(5200, lowTier ? 40 : 48, lowTier ? 20 : 24).rotateX(Math.PI / 2), skyMaterial());
  dome.renderOrder = -100; dome.frustumCulled = false; group.add(dome);

  // Reflections: bake the dome into a PMREM environment for metal, glass and wet ground.
  const envScene = new THREE.Scene(); envScene.add(new THREE.Mesh(dome.geometry, dome.material));
  // a dark ground disc in the environment so reflections are not lit from below by the sky
  const envGround = new THREE.Mesh(new THREE.CircleGeometry(4000, 32).translate(0, 0, -60), new THREE.MeshBasicMaterial({ color: new THREE.Color().setRGB(.16, .14, .11), side: THREE.DoubleSide }));
  envScene.add(envGround);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromScene(envScene, 0, 10, 8000); pmrem.dispose();
  scene.environment = env.texture; scene.environmentIntensity = 0.75;

  scene.background = null;
  scene.fog = heightFog ? new THREE.FogExp2(HAZE.clone(), 0.00036) : new THREE.Fog(lowTier ? new THREE.Color('#d9a37e') : HAZE.clone(), lowTier ? 140 : 160, lowTier ? 2700 : 2900);

  // Cloud banks: soft billboards rimming the horizon, lit warm on the sun side.
  const clouds = new THREE.Group(); clouds.name = 'clouds';
  const r = rng(404), tex = [cloudTexture(3), cloudTexture(8), cloudTexture(21)], nClouds = q.clouds ?? 26;
  const sunAz = Math.atan2(SUN_DIR.y, SUN_DIR.x);
  for (let i = 0; i < nClouds; i++) {
    const az = r() * Math.PI * 2, el = (2.5 + r() * 22) * Math.PI / 180, R = 4300;
    const m = new THREE.SpriteMaterial({ map: tex[i % 3], fog: false, depthWrite: false, transparent: true, opacity: .45 + r() * .4 });
    const toSun = Math.pow(Math.max(0, Math.cos(az - sunAz)), 2);
    // backlit toward the sun (bright rim, warm), cooler and greyer away from it and higher up
    m.color = new THREE.Color().setRGB(.78 + .5 * toSun, .58 + .32 * toSun - el * .5, .55 + .1 * toSun + el * .6);
    const s = new THREE.Sprite(m);
    s.position.set(Math.cos(az) * Math.cos(el) * R, Math.sin(az) * Math.cos(el) * R, Math.sin(el) * R);
    const w = 1200 + r() * 1900; s.scale.set(w, w * (.22 + r() * .14), 1); s.renderOrder = -90;
    clouds.add(s);
  }
  group.add(clouds);

  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: '#ffc27a', fog: false, depthWrite: false, transparent: true, blending: THREE.AdditiveBlending, opacity: .7 }));
  glow.position.copy(SUN_DIR).multiplyScalar(4800); glow.scale.set(1500, 1500, 1); glow.renderOrder = -80; group.add(glow);
  scene.add(group);

  // Sky fill: cool from above, warm earth bounce from below.
  const hemi = new THREE.HemisphereLight('#9db3dc', '#7a6248', 1.05); hemi.position.set(0, 0, 100); scene.add(hemi);
  const sun = new THREE.DirectionalLight('#ffcf98', 3.9);
  sun.castShadow = !!shadows;
  if (shadows) {
    sun.shadow.mapSize.set(shadowSize, shadowSize);
    Object.assign(sun.shadow.camera, { left: -95, right: 95, top: 95, bottom: -95, near: 1, far: 1400 });
    sun.shadow.bias = -0.00025; sun.shadow.normalBias = 0.05; sun.shadow.radius = 2; sun.shadow.camera.updateProjectionMatrix();
  }
  scene.add(sun, sun.target);

  // light-space basis for texel snapping
  const lz = SUN_DIR.clone(), lx = new THREE.Vector3(0, 0, 1).cross(lz).normalize(), ly = lz.clone().cross(lx).normalize();
  const focus = new THREE.Vector3(0, 0, 1.5), aim = new THREE.Vector3(), fwd = new THREE.Vector3();
  let lastHalf = 0;
  function fitShadow(camera) {
    if (!shadows) return;
    // Centre on the aircraft when the camera is near it; otherwise on the ground ahead of the camera.
    const dA = camera.position.distanceTo(focus);
    if (dA < 260) aim.copy(focus);
    else { camera.getWorldDirection(fwd); aim.copy(camera.position).addScaledVector(fwd, 140); aim.z = Math.max(0, Math.min(aim.z, 40)); }
    const dist = camera.position.distanceTo(aim);
    const half = Math.min(260, Math.max(48, Math.ceil((dist * 0.9 + 36) / 8) * 8));
    if (half !== lastHalf) {
      Object.assign(sun.shadow.camera, { left: -half, right: half, top: half, bottom: -half });
      sun.shadow.camera.updateProjectionMatrix(); lastHalf = half;
      sun.shadow.normalBias = 0.6 * (2 * half / shadowSize) + 0.02;
    }
    const texel = 2 * half / shadowSize;
    const u = aim.dot(lx), v = aim.dot(ly), w = aim.dot(lz);
    const su = Math.round(u / texel) * texel, sv = Math.round(v / texel) * texel;
    const c = new THREE.Vector3().addScaledVector(lx, su).addScaledVector(ly, sv).addScaledVector(lz, w);
    sun.target.position.copy(c); sun.position.copy(c).addScaledVector(SUN_DIR, 650);
    sun.target.updateMatrixWorld(); sun.updateMatrixWorld();
  }

  return {
    group, sun, hemi, sunDir: SUN_DIR, quality: q.name, fogPatched: fogInstalled,
    // Keep the dome centred on the camera, drift the cloud banks, fit the shadow to the view.
    update(camera, seconds) {
      group.position.copy(camera.position);
      clouds.rotation.z = seconds * 0.0006;
      fitShadow(camera);
    },
    // The aircraft position (the shadow focus when the camera is close to it).
    follow(pos) { focus.copy(pos); },
  };
}
