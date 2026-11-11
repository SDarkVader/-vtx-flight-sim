// Day / night presentation. Visual only: it changes lights, sky, fog and emissive strength, and restores them exactly.
import * as THREE from 'three';

export function createTimeOfDay({ scene, sky, renderer, getPost, environment }) {
  let mode = 'day', saved = null, stars = null;
  const boosted = new Map();
  function makeStars() {
    const n = 1400, pos = new Float32Array(n * 3); let s = 9173;
    const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < n; i++) {
      const az = r() * Math.PI * 2, el = Math.asin(0.06 + r() * 0.94), R = 5000;
      pos.set([Math.cos(az) * Math.cos(el) * R, Math.sin(az) * Math.cos(el) * R, Math.sin(el) * R], i * 3);
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const p = new THREE.Points(g, new THREE.PointsMaterial({ color: '#cfd8ff', size: 2.2, sizeAttenuation: false, fog: false, depthWrite: false, transparent: true, opacity: 0.85 }));
    p.name = 'night-stars'; p.frustumCulled = false; p.renderOrder = -95; return p;
  }
  function night() {
    saved = { skyVisible: sky.group.children.map((c) => c.visible), background: scene.background, fog: scene.fog.color.clone(),
      sunI: sky.sun.intensity, sunC: sky.sun.color.clone(), hemiI: sky.hemi.intensity, hemiC: sky.hemi.color.clone(), hemiG: sky.hemi.groundColor.clone(),
      env: scene.environmentIntensity, exposure: renderer.toneMappingExposure };
    sky.group.children.forEach((c) => { c.visible = false; });
    if (!stars) { stars = makeStars(); } sky.group.add(stars); stars.visible = true;
    scene.background = new THREE.Color().setRGB(0.006, 0.010, 0.026, THREE.LinearSRGBColorSpace);
    scene.fog.color.setRGB(0.010, 0.014, 0.030, THREE.LinearSRGBColorSpace);
    sky.sun.intensity = 0.45; sky.sun.color.set('#9fb4ff');            // moonlight
    sky.hemi.intensity = 0.22; sky.hemi.color.set('#3a4f80'); sky.hemi.groundColor.set('#1a1410');
    scene.environmentIntensity = 0.12; renderer.toneMappingExposure = 1.15;
    scene.traverse((o) => {
      const ms = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      for (const m of ms) if (m.emissive && !boosted.has(m) && (m.emissive.r + m.emissive.g + m.emissive.b) > 0.05) { boosted.set(m, m.emissiveIntensity ?? 1); m.emissiveIntensity = (m.emissiveIntensity ?? 1) * 1.8; }
    });
  }
  function day() {
    if (!saved) return;
    sky.group.children.forEach((c, i) => { if (c !== stars) c.visible = saved.skyVisible[i] ?? true; });
    if (stars) { stars.visible = false; sky.group.remove(stars); }
    scene.background = saved.background; scene.fog.color.copy(saved.fog);
    sky.sun.intensity = saved.sunI; sky.sun.color.copy(saved.sunC); sky.hemi.intensity = saved.hemiI; sky.hemi.color.copy(saved.hemiC); sky.hemi.groundColor.copy(saved.hemiG);
    scene.environmentIntensity = saved.env; renderer.toneMappingExposure = saved.exposure;
    for (const [m, v] of boosted) m.emissiveIntensity = v;
    boosted.clear(); saved = null;
  }
  return {
    get mode() { return mode; },
    // Re-applies the current mode (call after the world is rebuilt so new materials are included).
    refresh() { if (mode === 'night') { day(); night(); } environment.kit?.setNight(mode === 'night'); getPost()?.setLook(mode); },
    set(next) { if (next === mode) return; mode = next === 'night' ? 'night' : 'day'; if (mode === 'night') night(); else day(); environment.kit?.setNight(mode === 'night'); getPost()?.setLook(mode); },
    toggle() { this.set(mode === 'night' ? 'day' : 'night'); return mode; },
  };
}
