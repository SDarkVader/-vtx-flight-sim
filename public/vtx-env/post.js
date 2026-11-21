// Ambient occlusion is exclusive to Ultra. Parallax Court uses bloom and grading at dusk and night.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

const LOOKS = {
  day: { bloom: 0.22, radius: 0.5, threshold: 0.9, ao: 1.0, lift: [0, 0.004, 0.012], gain: [1.0, 1.01, 1.03], sat: 1.06, vig: 0.3 },
  dusk: { bloom: 0.37, radius: 0.48, threshold: 0.87, ao: 0.94, lift: [0.001,0.003,0.010], gain: [1.02,1.0,1.04], sat: 1.06, vig: 0.32 },
  night: { bloom: 0.55, radius: 0.5, threshold: 0.78, ao: 0.8, lift: [0.004, 0.008, 0.02], gain: [0.98, 1.0, 1.06], sat: 1.08, vig: 0.42 },
};
const COURT_LOOKS = {
  dusk: { ...LOOKS.dusk, bloom: .48, radius: .30, threshold: .96, sat: 1.15, vig: .16 },
  night: { ...LOOKS.night, bloom: .56, radius: .32, threshold: .93, sat: 1.13, vig: .21 },
};
const GRADE = {
  uniforms: { tDiffuse: { value: null }, lift: { value: new THREE.Vector3() }, gain: { value: new THREE.Vector3(1, 1, 1) }, sat: { value: 1 }, vig: { value: 0.3 } },
  vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform sampler2D tDiffuse; uniform vec3 lift; uniform vec3 gain; uniform float sat; uniform float vig; varying vec2 vUv;
    void main(){ vec3 c = texture2D(tDiffuse, vUv).rgb; c = lift + c * (gain - lift);
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); c = mix(vec3(l), c, sat);
      vec2 d = vUv - 0.5; c *= 1.0 - vig * smoothstep(0.25, 0.85, dot(d, d) * 2.2);
      gl_FragColor = vec4(c, 1.0); }`,
};

// The stock bloom blur uses a Gaussian with sigma equal to its tap count, cut off at one sigma: nearly flat,
// so the separable horizontal and vertical passes act as a box blur and every bright light gets a square halo.
// A Gaussian is the only separable kernel that is round; cut off at 3 sigma (edge step about 2 %, not 66 %) the halo is round.
function roundBloom(bloom) {
  for (const material of bloom.separableBlurMaterials || []) {
    const taps = material.defines?.KERNEL_RADIUS, sigma = taps / 3;
    if (!taps || !material.uniforms?.gaussianCoefficients) continue;
    material.uniforms.gaussianCoefficients.value = Array.from({length: taps}, (_, i) => 0.39894 * Math.exp(-0.5 * i * i / (sigma * sigma)) / sigma);
  }
}

export function createPost(renderer, scene, camera, quality) {
  if (!quality.post && !quality.glow) return null;
  let pipeline, enabled = false;
  function createPipeline() {
    const size = renderer.getDrawingBufferSize(new THREE.Vector2());
    const composer = new EffectComposer(renderer);
    const source = new RenderPass(scene, camera);
    composer.addPass(source);
    let ao;
    if (quality.post) {
      ao = new GTAOPass(scene, camera, size.x, size.y);
      ao.updateGtaoMaterial({ radius: 1.6, distanceExponent: 1.2, thickness: 1.5, scale: 1.0, samples: quality.aoSamples ?? 12 });
      composer.addPass(ao);
    }
    const bloom = new UnrealBloomPass(size.clone(), 0.22, 0.5, 0.9);
    roundBloom(bloom);
    composer.addPass(bloom);
    composer.addPass(new OutputPass());
    const grade = new ShaderPass(GRADE);
    composer.addPass(grade);
    return {composer, source, ao, bloom, grade};
  }
  const api = {
    get composer() { return pipeline?.composer; },
    get enabled() { return enabled; },
    render(view = camera) {
      if (!enabled) {
        renderer.render(scene, view);
        return;
      }
      const {composer, source, ao} = pipeline;
      source.camera = view;
      if (ao) ao.camera = view;
      composer.render();
    },
    setSize(w, h) {
      const composer = pipeline?.composer;
      if (!composer) return;
      composer.setPixelRatio(renderer.getPixelRatio());
      composer.setSize(w, h);
    },
    setLook(name, cityGlow = false) {
      const court = cityGlow && COURT_LOOKS[name];
      enabled = !!(quality.post || court);
      if (!enabled) return;
      pipeline ??= createPipeline();
      const {bloom, ao, grade} = pipeline;
      const k = court || LOOKS[name] || LOOKS.day;
      bloom.strength = k.bloom; bloom.radius = k.radius; bloom.threshold = k.threshold;
      if (ao) ao.blendIntensity = k.ao;
      grade.uniforms.lift.value.set(...k.lift); grade.uniforms.gain.value.set(...k.gain);
      grade.uniforms.sat.value = k.sat; grade.uniforms.vig.value = k.vig;
    },
  };
  api.setLook('day');
  return api;
}
