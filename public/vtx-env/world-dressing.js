// Post-build visual dressing of the world, applied once after every builder has run.
//  - drapes airfield paint, inset lights, service-road paint and the water exactly onto the
//    rendered ground (== the physics heightfield inside +/-500 m), see ground.js;
//  - registers decorative point lights with the local-light pool (light LOD);
//  - fixes canvas textures that were missing their sRGB colour space;
//  - adds a world-space macro variation to the terrain colour (no geometry change).
// Nothing here moves, resizes or reshapes anything with a physics counterpart.
import * as THREE from 'three';
import { glowTexture } from './textures.js';
import { tierOf } from './quality.js';

const PAINT_GROUPS = ['vtx-airfield', 'vtx-service-roads'];

function worldZRange(mesh) {
  const p = mesh.geometry.attributes.position, v = new THREE.Vector3(); let lo = Infinity, hi = -Infinity;
  mesh.updateMatrixWorld(true);
  for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i).applyMatrix4(mesh.matrixWorld); lo = Math.min(lo, v.z); hi = Math.max(hi, v.z); }
  return [lo, hi];
}
// true when every vertex lies within tol of the (clamped) physics terrain: paint, not a prop
function isGroundPaint(mesh, ground, tol) {
  const p = mesh.geometry.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i).applyMatrix4(mesh.matrixWorld); if (Math.abs(v.z - ground.heightAt(v.x, v.y)) > tol) return false; }
  return p.count > 0;
}

export function dressWorld(scene, w, ground, opts = {}) {
  const q = tierOf(opts), mode = q.drape || 'full', pool = opts.lightPool;
  const stats = { draped: 0, hiddenOffFloor: 0, lights: 0, srgb: 0 };
  scene.updateMatrixWorld(true);

  // 1. airfield paint (was drawn at z = 0.02 with depthTest off, painting through the hills)
  const af = scene.getObjectByName('vtx-airfield');
  if (af) {
    const decals = [];
    af.traverse((o) => { if (o.isMesh && !o.isInstancedMesh && o.parent === af) { const [lo, hi] = worldZRange(o); if (hi - lo < 0.02 && hi < 0.2) decals.push(o); } });
    for (const m of decals) { ground.drapeMesh(m, { offset: 0.02, mode }); ground.decalDepth(m.material); stats.draped++; if (!m.visible) stats.hiddenOffFloor++; }
    // inset light discs: sit on the ground, aligned with it, depth-tested
    af.traverse((o) => {
      if (!o.isInstancedMesh) return;
      const m4 = new THREE.Matrix4(), pos = new THREE.Vector3(), nrm = new THREE.Vector3(), qq = new THREE.Quaternion(), up = new THREE.Vector3(0, 0, 1), one = new THREE.Vector3(1, 1, 1), zero = new THREE.Vector3();
      const glowPos = [], glowCol = [], c = new THREE.Color();
      for (let i = 0; i < o.count; i++) {
        o.getMatrixAt(i, m4); pos.setFromMatrixPosition(m4);
        if (mode === 'flat' && !ground.isFlat(pos.x, pos.y)) { m4.compose(pos, qq.identity(), zero); o.setMatrixAt(i, m4); stats.hiddenOffFloor++; continue; }
        ground.normalAt(pos.x, pos.y, nrm); qq.setFromUnitVectors(up, nrm);
        pos.z = ground.heightAt(pos.x, pos.y) + 0.03 / Math.max(.5, nrm.z);
        m4.compose(pos, qq, one); o.setMatrixAt(i, m4);
        if (o.instanceColor) { o.getColorAt(i, c); glowPos.push(pos.x, pos.y, pos.z + 0.12); glowCol.push(c.r * .45, c.g * .45, c.b * .45); }
      }
      o.instanceMatrix.needsUpdate = true; o.computeBoundingSphere?.();
      ground.decalDepth(o.material, -6);
      if (q.glow && glowPos.length) {
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(glowPos, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(glowCol, 3));
        const pts = new THREE.Points(g, new THREE.PointsMaterial({ size: 2.2, map: glowTexture(), vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false, sizeAttenuation: true }));
        pts.name = 'inset-light-glow'; pts.renderOrder = 5; af.add(pts);
      }
    });
  }
  // 2. service-road paint (ribbons followed the clamped heightfield per vertex; now draped per triangle)
  const sr = scene.getObjectByName('vtx-service-roads');
  if (sr) {
    const paint = [];
    sr.traverse((o) => {
      if (!o.isMesh || o.isInstancedMesh) return;
      for (let p = o; p && p !== sr; p = p.parent) if (/^vtx-gsv/.test(p.name)) return;
      if (isGroundPaint(o, ground, 0.3)) paint.push(o);
    });
    for (const m of paint) {
      // reparent to the (identity) service-road group so the drape is in world space
      if (m.parent !== sr) { m.updateMatrixWorld(true); const mw = m.matrixWorld.clone(); sr.add(m); m.matrix.copy(mw); m.matrix.decompose(m.position, m.quaternion, m.scale); }
      ground.drapeMesh(m, { offset: 0.05, mode }); stats.draped++;
      for (const mat of Array.isArray(m.material) ? m.material : [m.material]) { mat.polygonOffset = true; mat.polygonOffsetFactor = Math.min(mat.polygonOffsetFactor || 0, -1.5); mat.polygonOffsetUnits = Math.min(mat.polygonOffsetUnits || 0, -4); }
    }
  }
  // 3. water: draped onto the physics ground (it floated up to ~2.4 m over the slope)
  const water = scene.getObjectByName('water');
  if (water) { ground.drapeMesh(water, { offset: 0.04, mode: 'full' }); water.material.polygonOffset = true; water.material.polygonOffsetFactor = -1; water.material.polygonOffsetUnits = -4; stats.draped++; }

  // 4. local lights -> pool; spot light only above the low tier
  const VC = [-30, 220];
  scene.traverse((o) => {
    if (o.isSpotLight && o.parent) { if (!q.localLights) o.visible = false; return; }
    if (!o.isPointLight || /^local-light-pool/.test(o.name)) return;
    const p = o.getWorldPosition(new THREE.Vector3()), interior = Math.hypot(p.x - VC[0], p.y - VC[1]) < 56;
    if (pool) pool.register(o, { eligible: interior ? (cp) => Math.hypot(cp.x - VC[0], cp.y - VC[1]) < 75 && cp.z < 45 : null });
    else o.visible = false;
    stats.lights++;
  });

  // 5. sRGB colour space for colour canvases (signs, stencils, markers)
  const fix = (t) => { if (t && t.isCanvasTexture && t.colorSpace === THREE.NoColorSpace) { t.colorSpace = THREE.SRGBColorSpace; t.needsUpdate = true; stats.srgb++; } };
  const groups = ['vtx-buildings', 'vtx-facilities-complex', 'vtx-service-roads', 'vtx-airfield', 'vtx-volcano-basement', 'vtx-sky-whale'];
  scene.traverse((o) => {
    let ok = o.isSprite && o.parent === scene;
    for (let p = o; p && !ok; p = p.parent) if (groups.includes(p.name)) ok = true;
    if (!ok || !o.material) return;
    for (const m of Array.isArray(o.material) ? o.material : [o.material]) { fix(m.map); fix(m.emissiveMap); }
  });
  for (const t of opts.extraTextures || []) fix(t);

  // 6. terrain: world-space macro variation against texture tiling (medium/high), no geometry change
  const terr = scene.getObjectByName('terrain-visual');
  if (terr && q.name !== 'low' && q.name !== 'lite') {
    const mat = terr.material;
    mat.onBeforeCompile = (sh) => {
      sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vTerrW;').replace('#include <project_vertex>', '#include <project_vertex>\n\tvTerrW = (modelMatrix * vec4(transformed, 1.0)).xyz;');
      sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
varying vec3 vTerrW;
float vtxH(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vtxN(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(vtxH(i), vtxH(i+vec2(1,0)), f.x), mix(vtxH(i+vec2(0,1)), vtxH(i+vec2(1,1)), f.x), f.y); }`)
        .replace('#include <color_fragment>', `#include <color_fragment>
  { float m = vtxN(vTerrW.xy / 95.0) * .6 + vtxN(vTerrW.xy / 21.0) * .4;
    diffuseColor.rgb *= mix(vec3(.86,.90,.84), vec3(1.10,1.06,.96), m); }`);
    };
    mat.customProgramCacheKey = () => 'vtx-terrain-macro'; mat.needsUpdate = true;
  }
  return stats;
}
