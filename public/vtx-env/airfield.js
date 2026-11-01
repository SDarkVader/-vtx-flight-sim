// Airfield surfaces: apron, runway, taxiways, roads, pads, stands, light fittings and the
// reserved Phase-2 underground portal marking. Everything is painted FLUSH on the flat
// central ground (z = 0), so it adds no solid geometry. Surfaces are drawn as opaque
// "decals" with depth testing off in a fixed render order, which removes z-fighting with the
// terrain entirely; markings that need transparency use alpha-to-coverage cut-outs.
import * as THREE from 'three';
import { LAYOUT } from './layout.js';
import { asphaltTextures, concreteTextures, makeCanvas, toTexture, rng, windsockTexture } from './textures.js';
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

  // =========================================================================
  // DUAL CROSSING RUNWAYS (Gloucestershire EGBJ Operational Topology)
  // =========================================================================

  // ---- 1. Primary Runway 08/26: 1,432m length x 30m width (heading 090°, X-aligned)
  const rwy0826_len = 1432, rwy0826_w = 30 + 8; // 30m runway + 4m shoulders on each side
  decal(group, rwy0826_len, rwy0826_w, 0, 0, surface(rwy0826_len, rwy0826_w, 2.5, (g, w, h) => {
    patternFill(g, asph.map, w, h, 8);
    // Shoulders
    g.fillStyle = 'rgba(60,62,65,.4)'; g.fillRect(0, 0, w, 4); g.fillRect(0, h - 4, w, 4);
    const cy = h / 2; g.fillStyle = '#f0eee2';
    // Solid runway edge lines
    g.fillRect(0, 4.2, w, .45); g.fillRect(0, h - 4.65, w, .45);
    // Centreline dashes (14m dash, 16m gap)
    for (let x = 20; x < w - 20; x += 30) g.fillRect(x, cy - .25, 14, .5);
    // Threshold piano keys (8 stripes per end, 14m x 1.5m)
    for (const dir of [1, -1]) {
      const x0 = dir > 0 ? 3 : w - 3;
      for (let i = 0; i < 8; i++) g.fillRect(dir > 0 ? x0 : x0 - 14, cy - 11.5 + i * 3, 14, 1.5);
      // Touchdown aiming point markings (300m from thresholds)
      const aimX = dir > 0 ? 300 : w - 300 - 45;
      for (const sgn of [-1, 1]) g.fillRect(aimX, cy + sgn * 6 - (sgn > 0 ? 0 : 3.0), 45, 3.0);
    }
    // Heading designators: '08' at west threshold, '26' at east threshold
    for (const [label, px, rot] of [['08', 36, Math.PI / 2], ['26', w - 36, -Math.PI / 2]]) {
      g.save(); g.translate(px, cy); g.rotate(rot);
      F.text(g, null, label, 0, 4.5, 12, { color: '#f0eee2', align: 'center', glow: false });
      g.restore();
    }
    // Touchdown tyre rubber burnouts
    const r = rng(108);
    for (const aimX of [300, w - 300]) {
      for (let i = 0; i < 28; i++) {
        g.fillStyle = 'rgba(15,15,16,.28)';
        g.fillRect(aimX + (r() - .5) * 55, cy + (r() - .5) * 14, 8 + r() * 16, .6 + r() * 1.4);
      }
    }
    // VTX Aviation watermark at intersection
    F.text(g, null, 'VTX AVIATION', w / 2, cy + 3.8, 9, { color: 'rgba(245,184,0,.75)', align: 'center', glow: false });
  }, { roughness: .4, env: 1.4 }), { z: Z + .001 });

  // ---- 2. Secondary Crossing Runway 03/21: 980m length x 23m width (heading 055°, crossing at [235, 0])
  const rwy0321_len = 980, rwy0321_w = 23 + 7; // 23m runway + 3.5m shoulders
  const rwy0321_rot = Math.atan2(0.81915204, 0.57357644); // ~0.95993 rad = 55.0 deg
  decal(group, rwy0321_len, rwy0321_w, 235, 0, surface(rwy0321_len, rwy0321_w, 3.2, (g, w, h) => {
    patternFill(g, asph.map, w, h, 8);
    // Shoulders
    g.fillStyle = 'rgba(60,62,65,.4)'; g.fillRect(0, 0, w, 3.5); g.fillRect(0, h - 3.5, w, 3.5);
    const cy = h / 2; g.fillStyle = '#f0eee2';
    // Edge lines
    g.fillRect(0, 3.7, w, .4); g.fillRect(0, h - 4.1, w, .4);
    // Centreline
    for (let x = 18; x < w - 18; x += 30) g.fillRect(x, cy - .22, 14, .45);
    // Threshold piano keys
    for (const dir of [1, -1]) {
      const x0 = dir > 0 ? 3 : w - 3;
      for (let i = 0; i < 6; i++) g.fillRect(dir > 0 ? x0 : x0 - 12, cy - 8.5 + i * 3, 12, 1.4);
      const aimX = dir > 0 ? 220 : w - 220 - 35;
      for (const sgn of [-1, 1]) g.fillRect(aimX, cy + sgn * 5 - (sgn > 0 ? 0 : 2.4), 35, 2.4);
    }
    // Heading numbers: '03' at SW threshold, '21' at NE threshold
    for (const [label, px, rot] of [['03', 32, Math.PI / 2], ['21', w - 32, -Math.PI / 2]]) {
      g.save(); g.translate(px, cy); g.rotate(rot);
      F.text(g, null, label, 0, 4.2, 10.5, { color: '#f0eee2', align: 'center', glow: false });
      g.restore();
    }
    // Touchdown tyre rubber
    const r = rng(321);
    for (const aimX of [220, w - 220]) {
      for (let i = 0; i < 22; i++) {
        g.fillStyle = 'rgba(15,15,16,.25)';
        g.fillRect(aimX + (r() - .5) * 45, cy + (r() - .5) * 12, 6 + r() * 14, .5 + r() * 1.2);
      }
    }
  }, { roughness: .42, env: 1.4 }), { rot: rwy0321_rot, z: Z + .002 });

  // ---- 3. Decommissioned Former Cross Runway 18/36: 800m length x 18m width (CLOSED, yellow X crosses)
  const rwy1836_len = 800, rwy1836_w = 18 + 4;
  decal(group, rwy1836_len, rwy1836_w, -180, 0, surface(rwy1836_len, rwy1836_w, 3.5, (g, w, h) => {
    // Weathered, aged cracked asphalt
    patternFill(g, asph.map, w, h, 8);
    g.fillStyle = 'rgba(70,60,50,.35)'; g.fillRect(0, 0, w, h); // weathered oxidation
    const cy = h / 2;
    // Faded centreline remnants
    g.fillStyle = 'rgba(200,195,180,.25)';
    for (let x = 20; x < w - 20; x += 35) g.fillRect(x, cy - .2, 12, .4);
    // Prominent yellow 'X' closed runway crosses every 140m per ICAO Annex 14
    for (let x = 80; x < w - 60; x += 140) {
      g.save(); g.translate(x, cy);
      g.strokeStyle = '#d49800'; g.lineWidth = 1.6;
      g.beginPath(); g.moveTo(-10, -8); g.lineTo(10, 8); g.moveTo(10, -8); g.lineTo(-10, 8); g.stroke();
      g.restore();
    }
  }, { roughness: .55, env: 1.1 }), { rot: Math.PI / 2, z: Z });

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
      F.text(g, null, 'VTX BASEMENT & VOLCANO ASCENT', w / 2, 8.2, 1.3, { color: F.YEL, align: 'center', font: 'Impact,Arial', glow: false, spacing: .1 });
      F.text(g, null, 'KEEP OUT STEVE · COMPLIANCE DIRECTIVE', w / 2, 10.4, 1.0, { color: '#e8e6d8', align: 'center', font: 'Impact,Arial', glow: false, spacing: .1 });
      F.text(g, null, 'RAYMOND WINSTON & ARTHUR FINCH ONLY', w / 2, 12.2, .85, { color: '#f5b800', align: 'center', font: 'Impact,Arial', glow: false, spacing: .1 });
    }, { roughness: .5 }));
  }

  // ---- flush light fittings (flat emissive discs; they do not project above the surface)
  const disc = new THREE.CircleGeometry(.22, 10);
  const add = (x, y, col) => lights.push([x, y, col]);

  // Runway 08/26 Edge Lights: white along runway, amber on last 300m of each end
  for (let x = -710; x <= 710; x += 25) {
    const isAmber = Math.abs(x) > 410;
    const col = isAmber ? '#ffb822' : '#fff3d0';
    add(x, -15.4, col); add(x, 15.4, col);
  }
  // Runway 08/26 Threshold Lights (Green entrance / Red end)
  for (let y = -14; y <= 14; y += 3.5) {
    add(-715, y, '#35e060'); // 08 threshold green
    add(715, y, '#ff3a2a');  // 26 end red
    add(-716, y, '#ff3a2a'); // 08 end red (from reverse)
    add(714, y, '#35e060');  // 26 threshold green (from reverse)
  }

  // Runway 03/21 Edge Lights along rotated axis
  const cos21 = Math.cos(rwy0321_rot), sin21 = Math.sin(rwy0321_rot);
  for (let s = -480; s <= 480; s += 25) {
    const isAmber = Math.abs(s) > 280;
    const col = isAmber ? '#ffb822' : '#fff3d0';
    for (const offset of [-11.8, 11.8]) {
      const lx = 235 + s * cos21 - offset * sin21;
      const ly = s * sin21 + offset * cos21;
      add(lx, ly, col);
    }
  }
  // Runway 03/21 Threshold Green / Red
  for (const sgn of [-1, 1]) {
    const s = sgn * 485;
    for (let offset = -10; offset <= 10; offset += 3.2) {
      const lx = 235 + s * cos21 - offset * sin21;
      const ly = s * sin21 + offset * cos21;
      add(lx, ly, sgn < 0 ? '#35e060' : '#ff3a2a');
    }
  }

  // Taxiway edge lights (blue) & apron edge lights
  for (const t of taxiways) for (let y = t.y0 + 1; y <= t.y1 - 1; y += 7) { add(t.x - t.width / 2 + .3, y, '#3d6cff'); add(t.x + t.width / 2 - .3, y, '#3d6cff'); }
  for (let x = apron.x0 + 4; x <= apron.x1 - 4; x += 10) add(x, apron.y0 + .8, '#3d6cff');

  // PAPI (Precision Approach Path Indicator) 4-box arrays (white/red units)
  const papiBox = (px, py, ang) => {
    const bg = new THREE.Group(); bg.position.set(px, py, Z + 0.1);
    bg.rotation.z = ang;
    for (let b = 0; b < 4; b++) {
      const bx = (b - 1.5) * 2.2;
      const housing = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.6, 0.45), new THREE.MeshStandardMaterial({ color: '#f5b800', roughness: 0.5 }));
      housing.position.set(bx, 0, 0.22); bg.add(housing);
      const lamp = new THREE.Mesh(new THREE.CircleGeometry(0.18, 8), new THREE.MeshBasicMaterial({ color: b < 2 ? '#ffffff' : '#ff2211' }));
      lamp.position.set(bx, -0.31, 0.22); lamp.rotateX(Math.PI / 2); bg.add(lamp);
    }
    group.add(bg);
  };
  papiBox(-416, -24, 0); // RWY 08 PAPI
  papiBox(416, 24, Math.PI); // RWY 26 PAPI
  const mat = new THREE.MeshBasicMaterial({ color: '#fff', depthTest: false, depthWrite: false, toneMapped: false });
  const inst = new THREE.InstancedMesh(disc, mat, lights.length), m = new THREE.Matrix4(), col = new THREE.Color();
  lights.forEach(([x, y, c], i) => { m.makeTranslation(x, y, Z + .02); inst.setMatrixAt(i, m); inst.setColorAt(i, col.set(c).multiplyScalar(2.2)); });
  inst.renderOrder = -1; group.add(inst);

  // ---- 3D Illuminated Windsock (near runway threshold)
  const sockGroup = new THREE.Group();
  sockGroup.position.set(-112, -38, 0);
  const poleMat = new THREE.MeshStandardMaterial({ color: '#55595d', metalness: 0.8, roughness: 0.4 });
  const sockPole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 6.5, 8), poleMat);
  sockPole.position.set(0, 0, 3.25); sockGroup.add(sockPole);

  const sockMat = new THREE.MeshStandardMaterial({
    map: windsockTexture(),
    roughness: 0.7,
    side: THREE.DoubleSide
  });
  const sockCone = new THREE.Mesh(new THREE.ConeGeometry(0.55, 3.4, 12, 1, true), sockMat);
  sockCone.rotateZ(Math.PI / 2);
  sockCone.position.set(1.7, 0, 6.2);
  sockGroup.add(sockCone);

  const sockLamp = new THREE.PointLight('#fff2d4', 1.8, 12);
  sockLamp.position.set(0, 0, 6.6); sockGroup.add(sockLamp);
  group.add(sockGroup);

  // ---- Ground Support Equipment (GSE) parked safely on apron edge
  const gseMat = new THREE.MeshStandardMaterial({ color: '#f5b800', roughness: 0.5, metalness: 0.2 });
  const darkMat = new THREE.MeshStandardMaterial({ color: '#16191c', roughness: 0.7 });

  // GPU Trailer (Ground Power Unit)
  const gpuGroup = new THREE.Group();
  gpuGroup.position.set(16, 12, 0);
  const gpuBody = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.2, 0.9), gseMat);
  gpuBody.position.set(0, 0, 0.65); gpuBody.castShadow = true; gpuGroup.add(gpuBody);
  // Wheels
  for (const [wx, wy] of [[-0.7, 0.65], [-0.7, -0.65], [0.7, 0.65], [0.7, -0.65]]) {
    const wMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.16, 12), darkMat);
    wMesh.rotateX(Math.PI / 2); wMesh.position.set(wx, wy, 0.24); gpuGroup.add(wMesh);
  }
  group.add(gpuGroup);

  // Airframe Service Stepladder Stand
  const ladderGroup = new THREE.Group();
  ladderGroup.position.set(22, 16, 0);
  const plat = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.4, 0.1), gseMat);
  plat.position.set(0, 0, 2.2); ladderGroup.add(plat);
  for (const [lx, ly] of [[-0.5, -0.6], [0.5, -0.6], [-0.5, 0.6], [0.5, 0.6]]) {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 2.2, 6), darkMat);
    leg.position.set(lx, ly, 1.1); ladderGroup.add(leg);
  }
  ladderGroup.castShadow = true;
  group.add(ladderGroup);

  scene.add(group);
  return { group, lightCount: lights.length };
}
