// Airfield surfaces: apron, runway, taxiways, roads, pads, stands, light fittings and the
// reserved Phase-2 underground portal marking. Everything is painted FLUSH on the flat
// central ground (z = 0), so it adds no solid geometry. Surfaces are drawn as opaque
// "decals" with depth testing off in a fixed render order, which removes z-fighting with the
// terrain entirely; markings that need transparency use alpha-to-coverage cut-outs.
import * as THREE from 'three';
import { LAYOUT } from './layout.js';
import { asphaltTextures, concreteTextures, makeCanvas, toTexture, rng } from './textures.js';
import * as F from './facade.js';

const Z = 0.02;
let order = -60;

function decalMaterial(map, { roughness = .5, metalness = 0, env = 1.2, cutout = false } = {}) {
  return new THREE.MeshStandardMaterial({ map, roughness, metalness, envMapIntensity: env, depthTest: false, depthWrite: false, alphaTest: cutout ? .5 : 0, alphaToCoverage: cutout });
}
function decal(group, w, h, x, y, material, { rot = 0, z = Z, shadow = true } = {}) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), material);
  m.position.set(x, y, z); m.rotation.z = rot; m.receiveShadow = shadow; m.renderOrder = Math.min(order++, -2);
  group.add(m); return m;
}
function surface(wM, hM, ppm, paint, opt) {
  const k = Math.min(ppm, 4096 / Math.max(wM, hM)), c = makeCanvas(Math.round(wM * k), Math.round(hM * k)), g = c.getContext('2d');
  g.scale(k, k); paint(g, wM, hM);
  return decalMaterial(toTexture(c, { aniso: 8 }), opt);
}
const patternFill = (g, tex, w, h, tileM) => { const p = g.createPattern(tex.image, 'repeat'), s = tileM / tex.image.width; p.setTransform(new DOMMatrix().scale(s, s)); g.fillStyle = p; g.fillRect(0, 0, w, h); };

export function buildAirfield(scene, { ppm = 11 } = {}) {
  const group = new THREE.Group(); group.name = 'vtx-airfield';
  const asph = asphaltTextures(), conc = concreteTextures();
  const { apron, runway, taxiways, roads, pads, stands, undergroundPortal: U } = LAYOUT;
  const lights = []; // flush light discs: [x, y, color]

  // ---- apron (concrete) with slab joints, stands, hazard edging and light spill from the hangar bays
  const aw = apron.x1 - apron.x0, ah = apron.y1 - apron.y0;
  decal(group, aw, ah, (apron.x0 + apron.x1) / 2, (apron.y0 + apron.y1) / 2, surface(aw, ah, ppm, (g, w, h) => {
    patternFill(g, conc.map, w, h, 12);
    g.strokeStyle = 'rgba(30,32,34,.45)'; g.lineWidth = .07; for (let x = 0; x <= w; x += 12) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); } for (let y = 0; y <= h; y += 12.5) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
    // yellow-and-black kerb along the southern edge; plain edge line elsewhere
    F.hazard(g, 0, h - .55, w, .55, .5);
    g.fillStyle = F.YEL; g.fillRect(0, 0, w, .22); g.fillRect(0, 0, .22, h); g.fillRect(w - .22, 0, .22, h);
    // warm spill from the open hangar bays (hangar front wall is at the apron's northern edge)
    for (const [u0, u1] of [[67.5, 84], [86, 102.5]]) { const gr = g.createLinearGradient(0, 0, 0, 16); gr.addColorStop(0, 'rgba(255,196,110,.38)'); gr.addColorStop(1, 'rgba(255,196,110,0)'); g.fillStyle = gr; g.fillRect(u0 - apron.x0 - 1, 0, u1 - u0 + 2, 16); }
    // painted parking stands (apron coordinates: x from x0, y from the top = y1)
    for (const s of stands) {
      const sx = s.x - apron.x0 - s.size / 2, sy = apron.y1 - s.y - s.size / 2;
      g.strokeStyle = F.YEL; g.lineWidth = .18; g.strokeRect(sx, sy, s.size, s.size);
      for (const [cx, cy] of [[sx, sy], [sx + s.size, sy], [sx, sy + s.size], [sx + s.size, sy + s.size]]) { g.fillStyle = F.YEL; g.fillRect(cx - .5, cy - .5, 1, 1); }
      F.text(g, null, 'VTX STAND', sx + s.size / 2, sy + s.size - 1, .9, { color: '#e8e6d8', align: 'center', font: 'Impact,Arial', glow: false, spacing: .1 });
    }
    // oil stains and tyre scuffs
    const r = rng(77); for (let i = 0; i < 70; i++) { const x = r() * w, y = r() * h, rad = .6 + r() * 2.2, gr = g.createRadialGradient(x, y, 0, x, y, rad); gr.addColorStop(0, 'rgba(25,24,24,.28)'); gr.addColorStop(1, 'rgba(25,24,24,0)'); g.fillStyle = gr; g.fillRect(x - rad, y - rad, rad * 2, rad * 2); }
  }, { roughness: .42, env: 1.5 }));

  // ---- runway: asphalt, shoulders, threshold bars, centreline, numbers, touchdown zones
  const rw = runway.x1 - runway.x0, rh = runway.width + 8;
  decal(group, rw, rh, (runway.x0 + runway.x1) / 2, runway.yc, surface(rw, rh, ppm * .9, (g, w, h) => {
    patternFill(g, asph.map, w, h, 8);
    g.fillStyle = 'rgba(80,82,80,.35)'; g.fillRect(0, 0, w, 4); g.fillRect(0, h - 4, w, 4);               // shoulders
    const cy = h / 2; g.fillStyle = '#e9e7da';
    g.fillRect(0, 4.2, w, .35); g.fillRect(0, h - 4.55, w, .35);                                        // edge lines
    for (let x = 14; x < w - 14; x += 30) g.fillRect(x, cy - .2, 14, .4);                                   // centreline
    for (const dir of [1, -1]) {                                                                         // thresholds + touchdown bars
      const x0 = dir > 0 ? 2.5 : w - 2.5;
      for (let i = 0; i < 8; i++) g.fillRect(dir > 0 ? x0 : x0 - 14, cy - 11.5 + i * 3, 14, 1.5);
      for (const sgn of [-1, 1]) { g.fillRect(dir > 0 ? x0 + 38 : x0 - 38 - 7, cy + sgn * 5 - (sgn > 0 ? 0 : 1.2), 7, 1.2); g.fillRect(dir > 0 ? x0 + 56 : x0 - 56 - 5, cy + sgn * 5 - (sgn > 0 ? 0 : 1.2), 5, 1.2); }
    }
    // heading numbers read from the approach end: the top of the glyphs points down the runway
    for (const [label, px, rot] of [['09', 28, Math.PI / 2], ['27', w - 28, -Math.PI / 2]]) { g.save(); g.translate(px, cy); g.rotate(rot); F.text(g, null, label, 0, 4, 11, { color: '#e9e7da', align: 'center', glow: false }); g.restore(); }
    // rubber at touchdown
    const r = rng(5); for (const x0 of [34, w - 34]) for (let i = 0; i < 14; i++) { g.fillStyle = 'rgba(18,18,18,.25)'; g.fillRect(x0 + (r() - .5) * 18, cy + (r() - .5) * 16, 4 + r() * 8, .5 + r() * 1.2); }
    F.text(g, null, 'VTX', w / 2, cy + 3.2, 8, { color: 'rgba(245,184,0,.82)', align: 'center', glow: false });
  }, { roughness: .4, env: 1.4 }));

  // ---- taxiways
  for (const t of taxiways) {
    const len = t.y1 - t.y0 + 14, w = t.width;
    decal(group, w, len, t.x, (t.y0 + t.y1) / 2, surface(w, len, ppm, (g, ww, hh) => {
      patternFill(g, asph.map, ww, hh, 8);
      g.fillStyle = F.YEL; g.fillRect(ww / 2 - .1, 0, .2, hh); g.fillRect(.5, 0, .14, hh); g.fillRect(ww - .64, 0, .14, hh);
      g.fillStyle = F.YEL; g.fillRect(ww / 2 - 1.3, hh / 2 - 2.2, 2.6, 3); F.text(g, null, t.id, ww / 2, hh / 2 + .15, 2.2, { color: F.BLK, align: 'center', glow: false });
    }, { roughness: .42 }));
  }

  // ---- roads
  const dir = new THREE.Vector2();
  for (const road of roads) {
    for (let i = 0; i < road.pts.length - 1; i++) {
      const [x0, y0] = road.pts[i], [x1, y1] = road.pts[i + 1]; dir.set(x1 - x0, y1 - y0); const len = dir.length() + road.width, ang = Math.atan2(dir.y, dir.x);
      decal(group, len, road.width, (x0 + x1) / 2, (y0 + y1) / 2, surface(len, road.width, ppm, (g, w, h) => {
        patternFill(g, asph.map, w, h, 8);
        g.fillStyle = '#d8d6c8'; g.fillRect(0, .35, w, .12); g.fillRect(0, h - .47, w, .12);
        g.fillStyle = F.YEL; for (let x = road.width / 2; x < w - road.width / 2 - 1; x += 6) g.fillRect(x, h / 2 - .1, 3, .2);
        g.fillStyle = 'rgba(0,0,0,.12)'; g.fillRect(0, 0, w, .3); g.fillRect(0, h - .3, w, .3);
      }, { roughness: .45 }), { rot: ang });
    }
  }

  // ---- pads: VTX stand-1 (default spawn) and pad B
  for (const p of pads) {
    const s = p.r * 2 + 2;
    const mat = surface(s, s, 16, (g, w, h) => {
      const c = w / 2; g.clearRect(0, 0, w, h);
      g.fillStyle = 'rgba(52,56,60,1)'; g.beginPath(); g.arc(c, c, p.r, 0, Math.PI * 2); g.fill();
      g.strokeStyle = F.YEL; g.lineWidth = .5; g.beginPath(); g.arc(c, c, p.r - .5, 0, Math.PI * 2); g.stroke();
      g.save(); g.beginPath(); g.arc(c, c, p.r - .8, 0, Math.PI * 2); g.arc(c, c, p.r - 1.5, 0, Math.PI * 2, true); g.clip(); F.hazard(g, 0, 0, w, h, .6); g.restore();
      g.strokeStyle = '#e8e6d8'; g.lineWidth = .3; g.beginPath(); g.arc(c, c, p.r * .55, 0, Math.PI * 2); g.stroke();
      F.text(g, null, 'VTX', c, c + 1.2, 3.6, { color: '#e8e6d8', align: 'center', glow: false });
      // six landing-contact marks matching the aircraft's six-foot ground footprint (radius 1.9 m)
      g.fillStyle = 'rgba(56,228,255,.85)'; for (let a = 0; a < 6; a++) { const an = a * Math.PI / 3; g.beginPath(); g.arc(c + Math.cos(an) * 1.9, c + Math.sin(an) * 1.9, .22, 0, Math.PI * 2); g.fill(); }
    }, { roughness: .45, cutout: true });
    decal(group, s, s, p.x, p.y, mat, { z: Z + .002 });
  }

  // ---- reserved Phase-2 underground portal: floor marking only, nothing solid
  {
    const [cx, cy] = U.center, [uw, ul] = U.size;
    decal(group, uw, ul, cx, cy, surface(uw, ul, 14, (g, w, h) => {
      g.fillStyle = '#30353a'; g.fillRect(0, 0, w, h);
      F.hazard(g, 0, 0, w, 1, .6); F.hazard(g, 0, h - 1, w, 1, .6); F.hazard(g, 0, 0, 1, h, .6); F.hazard(g, w - 1, 0, 1, h, .6);
      g.strokeStyle = 'rgba(245,184,0,.8)'; g.lineWidth = .35;
      for (let i = 0; i < 4; i++) { const y = h - 4 - i * 5.5; g.beginPath(); g.moveTo(w / 2 - 3.4, y); g.lineTo(w / 2, y - 3); g.lineTo(w / 2 + 3.4, y); g.stroke(); }
      F.text(g, null, 'VTX DEEP BAY', w / 2, 8.2, 1.6, { color: F.YEL, align: 'center', font: 'Impact,Arial', glow: false, spacing: .2 });
      F.text(g, null, 'ACCESS RESERVED', w / 2, 10.4, 1.15, { color: '#e8e6d8', align: 'center', font: 'Impact,Arial', glow: false, spacing: .2 });
      F.text(g, null, 'PHASE 2', w / 2, 12.2, .9, { color: '#9aa0a3', align: 'center', font: 'Impact,Arial', glow: false, spacing: .2 });
    }, { roughness: .5 }));
  }

  // ---- flush light fittings (flat emissive discs; they do not project above the surface)
  const disc = new THREE.CircleGeometry(.22, 10);
  const add = (x, y, col) => lights.push([x, y, col]);
  for (let x = runway.x0 + 2; x <= runway.x1 - 2; x += 15) { add(x, runway.yc - runway.width / 2 - .2, '#fff3d0'); add(x, runway.yc + runway.width / 2 + .2, '#fff3d0'); }
  for (let y = -15; y <= 15; y += 3) { add(runway.x0 + .6, runway.yc + y, '#35e060'); add(runway.x1 - .6, runway.yc + y, '#ff3a2a'); }
  for (const t of taxiways) for (let y = t.y0 + 1; y <= t.y1 - 1; y += 7) { add(t.x - t.width / 2 + .3, y, '#3d6cff'); add(t.x + t.width / 2 - .3, y, '#3d6cff'); }
  for (let x = apron.x0 + 4; x <= apron.x1 - 4; x += 10) add(x, apron.y0 + .8, '#3d6cff');
  const mat = new THREE.MeshBasicMaterial({ color: '#fff', depthTest: false, depthWrite: false, toneMapped: false });
  const inst = new THREE.InstancedMesh(disc, mat, lights.length), m = new THREE.Matrix4(), col = new THREE.Color();
  lights.forEach(([x, y, c], i) => { m.makeTranslation(x, y, Z + .02); inst.setMatrixAt(i, m); inst.setColorAt(i, col.set(c).multiplyScalar(2.2)); });
  inst.renderOrder = -1; group.add(inst);

  scene.add(group);
  return { group, lightCount: lights.length };
}
