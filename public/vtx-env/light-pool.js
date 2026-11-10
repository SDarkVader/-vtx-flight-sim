// Local-light LOD. Every decorative point light in the world is registered here and hidden;
// a fixed number of pooled lights (per quality tier) is re-aimed each frame at the nearest
// eligible sources. A fixed count keeps shader programs stable (no recompiles), and phones
// (tier low: 0 slots) evaluate no local lights at all. Emissive surfaces stay lit regardless.
import * as THREE from 'three';

export function createLightPool(scene, slots = 0) {
  const sources = [], pool = [], tmp = new THREE.Vector3();
  for (let i = 0; i < slots; i++) {
    const l = new THREE.PointLight('#ffffff', 0, 1, 2); l.name = `local-light-pool-${i}`; l.castShadow = false;
    scene.add(l); pool.push(l);
  }
  return {
    slots,
    // eligible(cameraPosition) -> bool decides whether a source may light the scene now.
    register(light, { eligible = null, reach = null } = {}) {
      if (!light || !light.isLight) return;
      light.visible = false;
      sources.push({ light, eligible, reach: reach ?? (light.distance || 40) });
    },
    update(camera) {
      if (!pool.length) return;
      const cp = camera.position, ranked = [];
      for (const s of sources) {
        if (s.eligible && !s.eligible(cp)) continue;
        s.light.getWorldPosition(tmp);
        const d = tmp.distanceTo(cp);
        if (d > s.reach * 3 + 60) continue;
        ranked.push([d / Math.max(1, s.reach), s, tmp.clone()]);
      }
      ranked.sort((a, b) => a[0] - b[0]);
      for (let i = 0; i < pool.length; i++) {
        const p = pool[i], r = ranked[i];
        if (!r) { p.intensity = 0; continue; }
        const L = r[1].light;
        p.position.copy(r[2]); p.color.copy(L.color); p.distance = L.distance; p.decay = L.decay;
        // fade with distance so swaps are not visible
        const fade = THREE.MathUtils.clamp(1 - (r[0] - 2) / 1.0, 0, 1);
        p.intensity = L.intensity * fade;
      }
    },
    get sourceCount() { return sources.length; },
    clear() { sources.length = 0; for (const p of pool) p.intensity = 0; },
  };
}
