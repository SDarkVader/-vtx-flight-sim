// Airfield surfaces: apron, runways, curved Bézier taxiways, holding points,
// expanded training aprons, stands, service roads, light fittings and underground portal.
// Everything on the ground is painted FLUSH on the central terrain (z = 0), so it adds
// zero solid physics collisions. Surfaces are drawn with deterministic renderOrder.
import * as THREE from 'three';
import { LAYOUT } from './layout.js';
import {sampleTerrainHeight} from './ride-trajectory.js';
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

// =========================================================================
// CUBIC BÉZIER MATHEMATICAL EVALUATION
// B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3
// =========================================================================
function evalCubicBezier(p0, p1, p2, p3, t) {
  const mt = 1 - t;
  const mt2 = mt * mt, mt3 = mt2 * mt;
  const t2 = t * t, t3 = t2 * t;
  return [
    mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0],
    mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]
  ];
}

function evalCubicBezierTangent(p0, p1, p2, p3, t) {
  const mt = 1 - t;
  const dx = 3 * mt * mt * (p1[0] - p0[0]) + 6 * mt * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0]);
  const dy = 3 * mt * mt * (p1[1] - p0[1]) + 6 * mt * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1]);
  const len = Math.hypot(dx, dy) || 1e-6;
  return [dx / len, dy / len];
}

// Builds a continuous smooth ribbon mesh along a cubic Bézier curve
function buildBezierRibbon(group, cps, width, asphTex, lights, opts = {}) {
  const N = opts.n || 44;
  const halfW = width / 2;
  const pos = [], uvs = [], indices = [];
  const centerPos = [], centerIndices = [];
  const halfCenterW = 0.22; // 0.44m yellow centerline
  
  let dist = 0;
  let lastPt = cps[0];
  let lastLightDist = -999;
  
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    const pt = evalCubicBezier(cps[0], cps[1], cps[2], cps[3], t);
    const [tx, ty] = evalCubicBezierTangent(cps[0], cps[1], cps[2], cps[3], t);
    const nx = -ty, ny = tx;
    
    if (i > 0) {
      dist += Math.hypot(pt[0] - lastPt[0], pt[1] - lastPt[1]);
      lastPt = pt;
    }
    
    // Left and right asphalt edges
    pos.push(pt[0] + nx * halfW, pt[1] + ny * halfW, Z + 0.001);
    pos.push(pt[0] - nx * halfW, pt[1] - ny * halfW, Z + 0.001);
    const v = dist / 8.0;
    uvs.push(0, v, 1, v);
    
    if (i < N) {
      const b = i * 2;
      indices.push(b, b + 1, b + 2, b + 2, b + 1, b + 3);
    }
    
    // Yellow centerline vertices
    centerPos.push(pt[0] + nx * halfCenterW, pt[1] + ny * halfCenterW, Z + 0.002);
    centerPos.push(pt[0] - nx * halfCenterW, pt[1] - ny * halfCenterW, Z + 0.002);
    if (i < N) {
      const cb = i * 2;
      centerIndices.push(cb, cb + 1, cb + 2, cb + 2, cb + 1, cb + 3);
    }
    
    // Taxiway blue edge lights spaced every ~16m
    if (dist - lastLightDist >= 16 || i === 0 || i === N) {
      lights.push([pt[0] + nx * (halfW - 0.4), pt[1] + ny * (halfW - 0.4), '#2588ff']);
      lights.push([pt[0] - nx * (halfW - 0.4), pt[1] - ny * (halfW - 0.4), '#2588ff']);
      lastLightDist = dist;
    }
  }
  
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geom.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geom.setIndex(indices);
  geom.computeVertexNormals();
  const mat = new THREE.MeshStandardMaterial({
    map: asphTex.map,
    roughness: 0.42,
    metalness: 0.05,
    depthTest: false,
    depthWrite: false
  });
  const mesh = new THREE.Mesh(geom, mat);
  mesh.renderOrder = -42;
  mesh.receiveShadow = true;
  group.add(mesh);
  
  const cgeom = new THREE.BufferGeometry();
  cgeom.setAttribute('position', new THREE.Float32BufferAttribute(centerPos, 3));
  cgeom.setIndex(centerIndices);
  cgeom.computeVertexNormals();
  const cmesh = new THREE.Mesh(cgeom, new THREE.MeshBasicMaterial({ color: '#ffc726', depthTest: false, depthWrite: false }));
  cmesh.renderOrder = -41;
  group.add(cmesh);
}

// Builds a straight polyline taxiway ribbon
function buildPolylineRibbon(group, p0, p1, width, asphTex, lights) {
  const dx = p1[0] - p0[0], dy = p1[1] - p0[1];
  const len = Math.hypot(dx, dy);
  const ang = Math.atan2(dy, dx);
  
  decal(group, len, width, (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, surface(len, width, 4, (g, w, h) => {
    patternFill(g, asphTex.map, w, h, 8);
    // Yellow centerline
    g.fillStyle = '#ffc726';
    g.fillRect(0, h / 2 - 0.22, w, 0.44);
    // Edge markings
    g.fillRect(0, 0.45, w, 0.22);
    g.fillRect(0, h - 0.67, w, 0.22);
  }, { roughness: 0.42 }), { rot: ang, z: Z + 0.001 });
  
  // Blue edge lights along polyline
  const nx = -Math.sin(ang) * (width / 2 - 0.4);
  const ny = Math.cos(ang) * (width / 2 - 0.4);
  for (let s = 10; s <= len - 10; s += 20) {
    const px = p0[0] + Math.cos(ang) * s;
    const py = p0[1] + Math.sin(ang) * s;
    lights.push([px + nx, py + ny, '#2588ff']);
    lights.push([px - nx, py - ny, '#2588ff']);
  }
}

// Illuminated Runway Holding Position Sign (3D unit with red/white and yellow/black faces)
function makeHoldSign(group, px, py, rwyText, twyText, rot = 0) {
  const signGroup = new THREE.Group();
  signGroup.position.set(px, py, 0);
  signGroup.rotation.z = rot;
  
  // Canvas texture for sign face
  const c = makeCanvas(384, 128), g = c.getContext('2d');
  // Left: Red background for runway mandatory instruction
  g.fillStyle = '#cc1100';
  g.fillRect(0, 0, 240, 128);
  g.fillStyle = '#ffffff';
  g.font = 'bold 64px "Arial Black", Impact, sans-serif';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(rwyText, 120, 64);
  
  // Right: Yellow background for taxiway location
  g.fillStyle = '#ffb800';
  g.fillRect(240, 0, 144, 128);
  g.fillStyle = '#111315';
  g.fillText(twyText, 312, 64);
  
  // Outer frame
  g.strokeStyle = '#000000';
  g.lineWidth = 6;
  g.strokeRect(3, 3, 378, 122);
  
  const faceTex = toTexture(c, { aniso: 4 });
  const signMat = new THREE.MeshBasicMaterial({ map: faceTex });
  const boxMat = new THREE.MeshStandardMaterial({ color: '#2a2d30', roughness: 0.6 });
  const mats = [boxMat, boxMat, signMat, signMat, boxMat, boxMat];
  
  const box = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.25, 0.85), mats);
  box.position.set(0, 0, 0.75);
  box.castShadow = true;
  signGroup.add(box);
  
  // Two mounting posts
  const postMat = new THREE.MeshStandardMaterial({ color: '#1a1c1e', roughness: 0.5 });
  for (const sx of [-0.5, 0.5]) {
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.75, 8), postMat);
    post.rotateX(Math.PI / 2);
    post.position.set(sx, 0, 0.375);
    signGroup.add(post);
  }
  
  // Amber warning guard lamp on top
  const lamp = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.08, 8), new THREE.MeshBasicMaterial({ color: '#ff9900' }));
  lamp.position.set(0, 0, 1.12);
  signGroup.add(lamp);
  
  group.add(signGroup);
}

// CAT I Runway Holding Position Marking: double solid + double dashed lines across taxiway
function makeHoldPositionMarking(group, px, py, width, heading) {
  const ang = heading;
  decal(group, width, 3.2, px, py, surface(width, 3.2, 16, (g, w, h) => {
    g.clearRect(0, 0, w, h);
    g.fillStyle = '#ffc726';
    // Double solid lines (on taxiway side facing runway)
    g.fillRect(0, 0.4, w, 0.35);
    g.fillRect(0, 1.1, w, 0.35);
    // Double dashed lines (on runway side)
    for (let x = 0.2; x < w; x += 1.8) {
      g.fillRect(x, 1.8, 0.9, 0.35);
      g.fillRect(x, 2.5, 0.9, 0.35);
    }
  }, { cutout: true }), { rot: ang, z: Z + 0.003 });
}

export function buildAirfield(scene, { ppm = 11, world } = {}) {
  const group = new THREE.Group(); group.name = 'vtx-airfield';
  const asph = asphaltTextures(), conc = concreteTextures();
  const { apron, runways, roads, pads, stands, undergroundPortal: U, taxiways_network, aprons_expanded, stands_expanded } = LAYOUT;
  const lights = []; // flush light discs: [x, y, color]

  // =========================================================================
  // CENTRAL OPERATIONAL APRON (Original Hangar Frontage)
  // =========================================================================
  const aw = apron.x1 - apron.x0, ah = apron.y1 - apron.y0;
  decal(group, aw, ah, (apron.x0 + apron.x1) / 2, (apron.y0 + apron.y1) / 2, surface(aw, ah, ppm, (g, w, h) => {
    patternFill(g, conc.map, w, h, 12);
    g.strokeStyle = 'rgba(30,32,34,.45)'; g.lineWidth = .07;
    for (let x = 0; x <= w; x += 12) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); }
    for (let y = 0; y <= h; y += 12.5) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
    F.hazard(g, 0, h - .55, w, .55, .5);
    g.fillStyle = F.YEL; g.fillRect(0, 0, w, .22); g.fillRect(0, 0, .22, h); g.fillRect(w - .22, 0, .22, h);
    for (const [u0, u1] of [[67.5, 84], [86, 102.5]]) {
      const gr = g.createLinearGradient(0, 0, 0, 16);
      gr.addColorStop(0, 'rgba(255,196,110,.38)'); gr.addColorStop(1, 'rgba(255,196,110,0)');
      g.fillStyle = gr; g.fillRect(u0 - apron.x0 - 1, 0, u1 - u0 + 2, 16);
    }
    for (const s of stands) {
      const sx = s.x - apron.x0 - s.size / 2, sy = apron.y1 - s.y - s.size / 2;
      g.strokeStyle = F.YEL; g.lineWidth = .18; g.strokeRect(sx, sy, s.size, s.size);
      for (const [cx, cy] of [[sx, sy], [sx + s.size, sy], [sx, sy + s.size], [sx + s.size, sy + s.size]]) {
        g.fillStyle = F.YEL; g.fillRect(cx - .5, cy - .5, 1, 1);
      }
      F.text(g, null, 'VTX STAND', sx + s.size / 2, sy + s.size - 1, .9, { color: '#e8e6d8', align: 'center', font: 'Impact,Arial', glow: false, spacing: .1 });
    }
  }, { roughness: .5, env: 1.2 }));

  // =========================================================================
  // DUAL CROSSING RUNWAYS (Gloucestershire EGBJ Operational Topology)
  // =========================================================================

  // ---- 1. Primary Runway 08/26: 1,432m length x 30m width (heading 090°, X-aligned)
  const rwy0826_len = 1432, rwy0826_w = 30 + 8;
  decal(group, rwy0826_len, rwy0826_w, 0, 0, surface(rwy0826_len, rwy0826_w, 2.5, (g, w, h) => {
    patternFill(g, asph.map, w, h, 8);
    g.fillStyle = 'rgba(60,62,65,.4)'; g.fillRect(0, 0, w, 4); g.fillRect(0, h - 4, w, 4);
    const cy = h / 2; g.fillStyle = '#f0eee2';
    g.fillRect(0, 4.2, w, .45); g.fillRect(0, h - 4.65, w, .45);
    for (let x = 20; x < w - 20; x += 30) g.fillRect(x, cy - .25, 14, .5);
    for (const dir of [1, -1]) {
      const x0 = dir > 0 ? 3 : w - 3;
      for (let i = 0; i < 8; i++) g.fillRect(dir > 0 ? x0 : x0 - 14, cy - 11.5 + i * 3, 14, 1.5);
      const aimX = dir > 0 ? 300 : w - 300 - 45;
      for (const sgn of [-1, 1]) g.fillRect(aimX, cy + sgn * 6 - (sgn > 0 ? 0 : 3.0), 45, 3.0);
    }
    for (const [label, px, rot] of [['08', 36, Math.PI / 2], ['26', w - 36, -Math.PI / 2]]) {
      g.save(); g.translate(px, cy); g.rotate(rot);
      F.text(g, null, label, 0, 4.5, 12, { color: '#f0eee2', align: 'center', glow: false });
      g.restore();
    }
    const r = rng(108);
    for (const aimX of [300, w - 300]) {
      for (let i = 0; i < 28; i++) {
        g.fillStyle = 'rgba(15,15,16,.28)';
        g.fillRect(aimX + (r() - .5) * 55, cy + (r() - .5) * 14, 8 + r() * 16, .6 + r() * 1.4);
      }
    }
    F.text(g, null, 'VTX AVIATION', w / 2, cy + 3.8, 9, { color: 'rgba(245,184,0,.75)', align: 'center', glow: false });
  }, { roughness: .4, env: 1.4 }), { z: Z + .001 });

  // ---- 2. Secondary Crossing Runway 03/21: 980m length x 23m width (heading 055°, crossing at [235, 0])
  const rwy0321_len = 980, rwy0321_w = 23 + 7;
  const rwy0321_rot = Math.atan2(0.81915204, 0.57357644);
  const secondaryRunway=decal(group, rwy0321_len, rwy0321_w, 235, 0, surface(rwy0321_len, rwy0321_w, 3.2, (g, w, h) => {
    patternFill(g, asph.map, w, h, 8);
    g.fillStyle = 'rgba(60,62,65,.4)'; g.fillRect(0, 0, w, 3.5); g.fillRect(0, h - 3.5, w, 3.5);
    const cy = h / 2; g.fillStyle = '#f0eee2';
    g.fillRect(0, 3.7, w, .4); g.fillRect(0, h - 4.1, w, .4);
    for (let x = 18; x < w - 18; x += 30) g.fillRect(x, cy - .22, 14, .45);
    for (const dir of [1, -1]) {
      const x0 = dir > 0 ? 3 : w - 3;
      for (let i = 0; i < 6; i++) g.fillRect(dir > 0 ? x0 : x0 - 12, cy - 8.5 + i * 3, 12, 1.4);
      const aimX = dir > 0 ? 220 : w - 220 - 35;
      for (const sgn of [-1, 1]) g.fillRect(aimX, cy + sgn * 5 - (sgn > 0 ? 0 : 2.4), 35, 2.4);
    }
    for (const [label, px, rot] of [['03', 32, Math.PI / 2], ['21', w - 32, -Math.PI / 2]]) {
      g.save(); g.translate(px, cy); g.rotate(rot);
      F.text(g, null, label, 0, 4.2, 10.5, { color: '#f0eee2', align: 'center', glow: false });
      g.restore();
    }
    const r = rng(321);
    for (const aimX of [220, w - 220]) {
      for (let i = 0; i < 22; i++) {
        g.fillStyle = 'rgba(15,15,16,.25)';
        g.fillRect(aimX + (r() - .5) * 45, cy + (r() - .5) * 12, 6 + r() * 14, .5 + r() * 1.2);
      }
    }
  }, { roughness: .42, env: 1.4 }), { rot: rwy0321_rot, z: Z + .002 });
  if(world){
    // Keep the rendered crossing strip on the same physical heightfield used
    // by 03/21 arrival and ground-contact clearance checks.
    secondaryRunway.geometry.dispose();
    secondaryRunway.geometry=new THREE.PlaneGeometry(rwy0321_len,rwy0321_w,128,4);
    const p=secondaryRunway.geometry.attributes.position,c=Math.cos(rwy0321_rot),s=Math.sin(rwy0321_rot);
    for(let i=0;i<p.count;i++){
      const x=p.getX(i),y=p.getY(i),wx=235+x*c-y*s,wy=x*s+y*c;
      p.setZ(i,sampleTerrainHeight(world,Math.max(-world.half_m,Math.min(world.half_m,wx)),Math.max(-world.half_m,Math.min(world.half_m,wy))));
    }
    p.needsUpdate=true;secondaryRunway.geometry.computeVertexNormals();
  }

  // ---- 3. Closed Former Runway 18/36: 800m length x 18m width (north-south at x = -180m)
  const rwy1836_len = 800, rwy1836_w = 18 + 4;
  decal(group, rwy1836_len, rwy1836_w, -180, 0, surface(rwy1836_len, rwy1836_w, 2.8, (g, w, h) => {
    patternFill(g, asph.map, w, h, 10);
    g.fillStyle = 'rgba(35,36,38,.5)'; g.fillRect(0, 0, w, h);
    for (let x = 70; x < w - 50; x += 140) {
      g.save(); g.translate(x, h / 2);
      g.strokeStyle = '#d49800'; g.lineWidth = 1.6;
      g.beginPath(); g.moveTo(-10, -8); g.lineTo(10, 8); g.moveTo(10, -8); g.lineTo(-10, 8); g.stroke();
      g.restore();
    }
  }, { roughness: .55, env: 1.1 }), { rot: Math.PI / 2, z: Z });

  // =========================================================================
  // CURVED BÉZIER TAXIWAY NETWORK (14m Width, R >= 25m, ICAO Compliant)
  // =========================================================================
  if (taxiways_network) {
    for (const twy of taxiways_network) {
      if (twy.kind === 'cubic_bezier') {
        buildBezierRibbon(group, twy.control_points, twy.width || 14, asph, lights, { n: 44 });
      } else if (twy.kind === 'polyline' && twy.points) {
        buildPolylineRibbon(group, twy.points[0], twy.points[1], twy.width || 14, asph, lights);
      }
      // Holdpoints & illuminated signs
      if (twy.holdpoint) {
        const hp = twy.holdpoint;
        makeHoldPositionMarking(group, hp.pt[0], hp.pt[1], twy.width || 14, hp.heading || 0);
        // Place illuminated signs on left and right sides of holding line
        makeHoldSign(group, hp.pt[0] - 9.5, hp.pt[1], hp.rwy || '08-26', hp.twy || 'A', 0);
        makeHoldSign(group, hp.pt[0] + 9.5, hp.pt[1], hp.rwy || '08-26', hp.twy || 'A', Math.PI);
      }
    }
    // Central Runway 08/26 Holding Point on Taxiway B
    makeHoldPositionMarking(group, 30, 16, 14, 0);
    makeHoldSign(group, 30 - 8.2, 16, '08-26', 'B', 0);
    makeHoldSign(group, 30 + 8.2, 16, '08-26', 'B', Math.PI);
  }

  // =========================================================================
  // EXPANDED FLIGHT ACADEMY & REMOTE APRONS
  // =========================================================================
  if (aprons_expanded) {
    for (const ap of aprons_expanded) {
      const [wM, hM] = ap.size;
      const [cx, cy] = ap.center;
      decal(group, wM, hM, cx, cy, surface(wM, hM, 4, (g, w, h) => {
        patternFill(g, conc.map, w, h, 14);
        // Concrete expansion joint grid every 14m
        g.strokeStyle = 'rgba(30,32,34,.35)'; g.lineWidth = .08;
        for (let x = 0; x <= w; x += 14) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); }
        for (let y = 0; y <= h; y += 14) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
        // Yellow perimeter boundary line
        g.strokeStyle = '#ffc726'; g.lineWidth = .35;
        g.strokeRect(1, 1, w - 2, h - 2);
        // Apron name badge
        F.text(g, null, ap.name || ap.id, w / 2, 8, 3.8, { color: 'rgba(235,230,215,.65)', align: 'center', glow: false });
        // Hazard margin edging along southern taxiway side
        F.hazard(g, 1, h - 1.2, w - 2, 1.2, 0.6);
        // Warm apron floodlight spill pools
        for (let x = 40; x < w - 30; x += 75) {
          const gr = g.createRadialGradient(x, 20, 5, x, 20, 55);
          gr.addColorStop(0, 'rgba(255,210,130,.32)');
          gr.addColorStop(1, 'rgba(255,210,130,0)');
          g.fillStyle = gr; g.fillRect(x - 55, 0, 110, 75);
        }
      }, { roughness: .48, env: 1.2 }), { z: Z + .001 });
    }
  }

  // =========================================================================
  // EXPANDED VTOL / AIRCRAFT STANDS (Stands 1 to 6)
  // =========================================================================
  if (stands_expanded) {
    for (let idx = 0; idx < stands_expanded.length; idx++) {
      const st = stands_expanded[idx];
      const s = st.radius * 2 + 2;
      const mat = surface(s, s, 14, (g, w, h) => {
        const c = w / 2; g.clearRect(0, 0, w, h);
        // Stand base circle
        g.fillStyle = 'rgba(48,52,56,0.92)';
        g.beginPath(); g.arc(c, c, st.radius, 0, Math.PI * 2); g.fill();
        // Dashed yellow outer guide ring
        g.strokeStyle = '#ffc726'; g.lineWidth = 0.45; g.setLineDash([1.4, 1.4]);
        g.beginPath(); g.arc(c, c, st.radius - 0.5, 0, Math.PI * 2); g.stroke();
        g.setLineDash([]);
        // Solid yellow inner boundary
        g.strokeStyle = '#ffc726'; g.lineWidth = 0.3;
        g.beginPath(); g.arc(c, c, st.radius - 2.0, 0, Math.PI * 2); g.stroke();
        // Crosshairs
        g.strokeStyle = 'rgba(255,255,255,0.7)'; g.lineWidth = 0.25;
        g.beginPath();
        g.moveTo(c - 8, c); g.lineTo(c + 8, c);
        g.moveTo(c, c - 8); g.lineTo(c, c + 8);
        g.stroke();
        // 6 cyan aircraft landing-gear contact pads (1.9m radius)
        g.fillStyle = 'rgba(56,228,255,.9)';
        for (let a = 0; a < 6; a++) {
          const an = a * Math.PI / 3;
          g.beginPath();
          g.arc(c + Math.cos(an) * 1.9, c + Math.sin(an) * 1.9, 0.25, 0, Math.PI * 2);
          g.fill();
        }
        // Stand ID
        F.text(g, null, `STAND ${idx + 1}`, c, c + 4.8, 1.8, { color: '#ffc726', align: 'center', font: 'Impact,Arial', glow: false });
        F.text(g, null, 'VTX AVIATION', c, c - 3.8, 1.2, { color: '#e8e6d8', align: 'center', font: 'Impact,Arial', glow: false });
      }, { roughness: .45, cutout: true });
      decal(group, s, s, st.center[0], st.center[1], mat, { z: Z + .003 });
    }
  }

  // ---- original taxiway links for central apron
  const origTwy = LAYOUT.taxiways || [];
  for (const t of origTwy) {
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

  // ---- original pads: VTX stand-1 (default spawn) and pad B
  for (const p of pads) {
    const s = p.r * 2 + 2;
    const mat = surface(s, s, 16, (g, w, h) => {
      const c = w / 2; g.clearRect(0, 0, w, h);
      g.fillStyle = 'rgba(52,56,60,1)'; g.beginPath(); g.arc(c, c, p.r, 0, Math.PI * 2); g.fill();
      g.strokeStyle = F.YEL; g.lineWidth = .5; g.beginPath(); g.arc(c, c, p.r - .5, 0, Math.PI * 2); g.stroke();
      g.save(); g.beginPath(); g.arc(c, c, p.r - .8, 0, Math.PI * 2); g.arc(c, c, p.r - 1.5, 0, Math.PI * 2, true); g.clip(); F.hazard(g, 0, 0, w, h, .6); g.restore();
      g.strokeStyle = '#e8e6d8'; g.lineWidth = .3; g.beginPath(); g.arc(c, c, p.r * .55, 0, Math.PI * 2); g.stroke();
      F.text(g, null, 'VTX', c, c + 1.2, 3.6, { color: '#e8e6d8', align: 'center', glow: false });
      g.fillStyle = 'rgba(56,228,255,.85)'; for (let a = 0; a < 6; a++) { const an = a * Math.PI / 3; g.beginPath(); g.arc(c + Math.cos(an) * 1.9, c + Math.sin(an) * 1.9, .22, 0, Math.PI * 2); g.fill(); }
    }, { roughness: .45, cutout: true });
    decal(group, s, s, p.x, p.y, mat, { z: Z + .002 });
  }

  // ---- reserved Phase-2 underground portal
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

  // =========================================================================
  // RUNWAY LIGHTING & TAXIWAY BLUE EDGE LIGHTS
  // =========================================================================
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

  // Taxiway edge lights for original apron connectors
  for (const t of origTwy) for (let y = t.y0 + 1; y <= t.y1 - 1; y += 7) { add(t.x - t.width / 2 + .3, y, '#2588ff'); add(t.x + t.width / 2 - .3, y, '#2588ff'); }
  for (let x = apron.x0 + 4; x <= apron.x1 - 4; x += 10) add(x, apron.y0 + .8, '#2588ff');

  // PAPI (Precision Approach Path Indicator) 4-box arrays
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

  // Instanced flush lights mesh
  const mat = new THREE.MeshBasicMaterial({ color: '#fff', depthTest: false, depthWrite: false, toneMapped: false });
  const inst = new THREE.InstancedMesh(disc, mat, lights.length), m = new THREE.Matrix4(), col = new THREE.Color();
  lights.forEach(([x, y, c], i) => { m.makeTranslation(x, y, Z + .02); inst.setMatrixAt(i, m); inst.setColorAt(i, col.set(c).multiplyScalar(2.2)); });
  inst.renderOrder = -1; group.add(inst);

  // ---- 3D Illuminated Windsock
  const sockGroup = new THREE.Group();
  sockGroup.position.set(-112, -38, 0);
  const poleMat = new THREE.MeshStandardMaterial({ color: '#55595d', metalness: 0.8, roughness: 0.4 });
  const sockPole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 6.5, 8).rotateX(Math.PI / 2), poleMat); // upright
  sockPole.position.set(0, 0, 3.25); sockGroup.add(sockPole);
  const sockCone = new THREE.Mesh(new THREE.ConeGeometry(0.55, 3.4, 12, 1, true), new THREE.MeshStandardMaterial({ map: windsockTexture(), roughness: 0.7, side: THREE.DoubleSide }));
  sockCone.rotateZ(-Math.PI / 2); // mouth at the pole, tail streaming downwind sockCone.position.set(1.7, 0, 6.2); sockGroup.add(sockCone);
  const sockLamp = new THREE.PointLight('#fff2d4', 1.8, 12); sockLamp.position.set(0, 0, 6.6); sockGroup.add(sockLamp);
  group.add(sockGroup);

  // (GPU cart and step ladder near Stand 1 removed: visible props with no collider beside a landing pad.)

  scene.add(group);
  return { group, lightCount: lights.length };
}
