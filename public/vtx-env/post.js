// Post-processing for the desktop-app quality tier: ambient occlusion, bloom and a colour grade.
// Visual only. Lower tiers skip this module's work entirely and render directly.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

const LOOKS = {
  day: { bloom: 0.22, radius: 0.5, threshold: 0.9, ao: 1.0, lift: [0, 0.004, 0.012], gain: [1.0, 1.01, 1.03], sat: 1.06, vig: 0.3 },
  night: { bloom: 0.55, radius: 0.5, threshold: 0.78, ao: 0.8, lift: [0.004, 0.008, 0.02], gain: [0.98, 1.0, 1.06], sat: 1.08, vig: 0.42 },
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

export function createPost(renderer, scene, camera, quality) {
  if (!quality.post) return null;
  const size = renderer.getDrawingBufferSize(new THREE.Vector2());
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const ao = new GTAOPass(scene, camera, size.x, size.y);
  ao.updateGtaoMaterial({ radius: 1.6, distanceExponent: 1.2, thickness: 1.5, scale: 1.0, samples: quality.aoSamples ?? 12 });
  composer.addPass(ao);
  const bloom = new UnrealBloomPass(size.clone(), 0.22, 0.5, 0.9); composer.addPass(bloom);
  composer.addPass(new OutputPass());
  const grade = new ShaderPass(GRADE); composer.addPass(grade);
  const api = {
    composer,
    render() { composer.render(); },
    setSize(w, h) { composer.setPixelRatio(renderer.getPixelRatio()); composer.setSize(w, h); },
    setLook(name) {
      const k = LOOKS[name] || LOOKS.day;
      bloom.strength = k.bloom; bloom.radius = k.radius; bloom.threshold = k.threshold; ao.blendIntensity = k.ao;
      grade.uniforms.lift.value.set(...k.lift); grade.uniforms.gain.value.set(...k.gain); grade.uniforms.sat.value = k.sat; grade.uniforms.vig.value = k.vig;
    },
  };
  api.setLook('day');
  return api;
}
