// Sky dome, golden-hour lighting, clouds and image-based reflections.
import * as THREE from 'three';
import { cloudTexture, glowTexture, rng } from './textures.js';

export const SUN_DIR = new THREE.Vector3(-0.80, -0.50, 0.30).normalize(); // low evening sun, west-south-west
export const HAZE = new THREE.Color('#d9a37e');                           // horizon / fog colour

const skyMaterial = () => new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: { sunDir: { value: SUN_DIR.clone() } },
  vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader: `
    varying vec3 vDir; uniform vec3 sunDir;
    void main(){
      float h = vDir.z;
      vec3 zen = vec3(.035,.085,.21), mid = vec3(.17,.30,.50), hor = vec3(.92,.52,.30), band = vec3(.60,.34,.30);
      vec3 c = mix(hor, band, smoothstep(0.,.07,h));
      c = mix(c, mid, smoothstep(.04,.34,h));
      c = mix(c, zen, smoothstep(.30,.95,h));
      float s = max(dot(normalize(vDir), sunDir), 0.);
      c += vec3(1.,.55,.24)*pow(s,5.)*.55 + vec3(1.,.78,.5)*pow(s,40.)*.55 + vec3(1.,.93,.78)*pow(s,900.)*6.;
      if(h < 0.) c = mix(hor*.75, vec3(.26,.20,.20), smoothstep(0.,-.35,h));
      gl_FragColor = vec4(c,1.);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
});

export function buildSky(scene, renderer, { shadows = true, shadowSize = 2048 } = {}) {
  const group = new THREE.Group(); group.name = 'sky';
  const dome = new THREE.Mesh(new THREE.SphereGeometry(5200, 40, 20).rotateX(Math.PI / 2), skyMaterial());
  dome.renderOrder = -100; dome.frustumCulled = false; group.add(dome);

  // Reflections: bake the dome into a PMREM environment for metal, glass and wet ground.
  const envScene = new THREE.Scene(); envScene.add(new THREE.Mesh(dome.geometry, dome.material));
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromScene(envScene, 0, 10, 8000); pmrem.dispose();
  scene.environment = env.texture; scene.environmentIntensity = 0.85;

  scene.background = null; scene.fog = new THREE.Fog(HAZE, 140, 2700);

  // Cloud banks: soft billboards rimming the horizon, lit warm underneath.
  const clouds = new THREE.Group(); clouds.name = 'clouds';
  const r = rng(404), tex = [cloudTexture(3), cloudTexture(8), cloudTexture(21)];
  for (let i = 0; i < 26; i++) {
    const az = r() * Math.PI * 2, el = (3 + r() * 24) * Math.PI / 180, R = 4300;
    const m = new THREE.SpriteMaterial({ map: tex[i % 3], fog: false, depthWrite: false, transparent: true, opacity: .55 + r() * .35 });
    const toSun = Math.max(0, Math.cos(az - Math.atan2(SUN_DIR.y, SUN_DIR.x)));
    m.color = new THREE.Color().setRGB(.8 + .2 * toSun, .55 + .3 * toSun - el * .6, .5 + .12 * toSun + el * .8).multiplyScalar(1);
    const s = new THREE.Sprite(m);
    s.position.set(Math.cos(az) * Math.cos(el) * R, Math.sin(az) * Math.cos(el) * R, Math.sin(el) * R);
    const w = 1400 + r() * 1800; s.scale.set(w, w * .32, 1); s.renderOrder = -90;
    clouds.add(s);
  }
  group.add(clouds);

  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: '#ffc27a', fog: false, depthWrite: false, transparent: true, blending: THREE.AdditiveBlending, opacity: .85 }));
  glow.position.copy(SUN_DIR).multiplyScalar(4800); glow.scale.set(1400, 1400, 1); glow.renderOrder = -80; group.add(glow);
  scene.add(group);

  const hemi = new THREE.HemisphereLight('#8fa6d4', '#6a5646', 1.35); hemi.position.set(0, 0, 100); scene.add(hemi);
  const sun = new THREE.DirectionalLight('#ffd09a', 3.6);
  sun.castShadow = shadows;
  if (shadows) {
    sun.shadow.mapSize.set(shadowSize, shadowSize);
    Object.assign(sun.shadow.camera, { left: -95, right: 95, top: 95, bottom: -95, near: 1, far: 900 });
    sun.shadow.bias = -0.0003; sun.shadow.normalBias = 0.06; sun.shadow.camera.updateProjectionMatrix();
  }
  scene.add(sun, sun.target);

  return {
    group, sun, hemi, sunDir: SUN_DIR,
    // Keep the dome centred on the camera and drift the cloud banks very slowly.
    update(camera, seconds) {
      group.position.copy(camera.position);
      clouds.rotation.z = seconds * 0.0006;
    },
    // Move the shadow frustum with the aircraft (texel-snapped to avoid shimmer).
    follow(pos) {
      const step = (190 / shadowSize);
      const sx = Math.round(pos.x / step) * step, sy = Math.round(pos.y / step) * step;
      sun.target.position.set(sx, sy, pos.z);
      sun.position.set(sx, sy, pos.z).addScaledVector(SUN_DIR, 420);
    },
  };
}
