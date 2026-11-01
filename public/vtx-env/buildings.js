// Vader's Taxis buildings. Every structure is dressed on top of an existing PHYSICAL
// obstacle box from world.py: the walls are textured planes exactly on the collider
// faces, and 3-D trim (sign boxes, door frames, piers, canopies) projects at most
// LAYOUT.maxTrimDepth from them. Nothing here adds or removes collision.
import * as THREE from 'three';
import { BUILDINGS, LAYOUT } from './layout.js';
import * as F from './facade.js';
import { stoneTexture, transgressionTexture, depotWhiteboardTexture, citationTexture } from './textures.js';

const V = THREE.Vector3, UP = new V(0, 0, 1);
const SIDES = { S: { n: [0, -1, 0], r: [1, 0, 0] }, N: { n: [0, 1, 0], r: [-1, 0, 0] }, E: { n: [1, 0, 0], r: [0, 1, 0] }, W: { n: [-1, 0, 0], r: [0, -1, 0] } };
const FRONT = { hangar: 'S', dispatch: 'S', tower: 'S', workshop: 'N', operations: 'N', terminal: 'S', arcade: 'S', freight: 'S', 'ridge-block': 'E' };
const OPPOSITE = { S: 'N', N: 'S', E: 'W', W: 'E' };

function wallFrame(o, side) {
  const [cx, cy, cz] = o.center, [hx, hy, hz] = o.half, s = SIDES[side], alongX = side === 'S' || side === 'N';
  const n = new V(...s.n), r = new V(...s.r);
  return { n, r, width: (alongX ? hx : hy) * 2, height: hz * 2, center: new V(cx, cy, cz).addScaledVector(n, alongX ? hy : hx) };
}
const basis = new THREE.Matrix4();
function orient(obj, fr) { basis.makeBasis(fr.r, UP, fr.n); obj.quaternion.setFromRotationMatrix(basis); }
// u = metres from the wall's left edge seen from outside, v = height above ground, out = metres off the wall
function place(obj, fr, u, v, out = 0) { obj.position.copy(fr.center).addScaledVector(fr.r, u - fr.width / 2).addScaledVector(UP, v - fr.height / 2).addScaledVector(fr.n, out); orient(obj, fr); return obj; }

const metal = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: .5, metalness: .55, ...extra });
const glowMat = (color, intensity = 2) => new THREE.MeshStandardMaterial({ color: '#000', emissive: color, emissiveIntensity: intensity });

// ----------------------------------------------------------------- face painters
function baseWall(kind, g, w, h) {
  if (kind === 'brick') F.brick(g, w, h);
  else if (kind === 'cargo' || kind === 'stack') F.containers(g, w, h, kind === 'stack' ? undefined : [F.YEL, '#25272b', '#4a5a40', '#c9c6bd']);
  else if (kind === 'tower' || kind === 'ops') F.concrete(g, w, h, kind === 'tower' ? '#8e9293' : '#b3b6b4');
  else if (kind === 'terminal') F.concrete(g, w, h, '#8f7f6a');
  else if (kind === 'workshop') F.corrugated(g, w, h, '#26343c');
  else if (kind === 'office') F.concrete(g, w, h, '#383c40');
  else F.corrugated(g, w, h);
  if (kind !== 'cargo' && kind !== 'stack') F.plinth(g, w, h, 1.1, true);
}

function paintFront(o, kind, g, e, w, h) {
  baseWall(kind, g, w, h);
  const name = BUILDINGS[o.id].name;
  if (kind === 'hangar') {
    const gy = h;
    F.bay(g, e, 5.5, gy - 10.5, 16.5, 10.5, { vehicle: 'taxi', seed: 4 });
    F.bay(g, e, 24, gy - 10.5, 16.5, 10.5, { vehicle: 'vtx', seed: 9 });
    g.fillStyle = '#2f6fa8'; g.fillRect(22, gy - 11.5, 2, 11.5);   // blue steel centre column
    F.hazard(g, 5.5, gy - .5, 35, .5, .4);
    // spill from the bays onto the apron edge
    F.text(g, e, 'VTX AVIATION DIVISION  ·  HANGAR 1', 23, gy - 11.9, .8, { color: '#d6d3c8', align: 'center', font: 'Impact,Arial', spacing: .1 });
  } else if (kind === 'office') {
    F.windowGrid(g, e, 2.4, 3.2, 5, 4, 3.2, 2.6, .85, 1.65, { seed: 5, lit: .75 });
    // glass entrance
    g.fillStyle = '#10161a'; g.fillRect(9.5, h - 4.4, 9, 4.4 - 1.1); F.windowGrid(g, e, 10, h - 4.1, 2, 1, 4, 2.7, .2, 0, { seed: 12, lit: 1 });
    F.taxiIcon(g, e, 11, h - 12, 6, F.YEL);
    F.text(g, e, 'DISPATCH  ·  24/7', w / 2, h - 7.1, 1.2, { color: F.YEL, align: 'center', font: 'Impact,Arial', spacing: .15 });
  } else if (kind === 'tower') {
    for (let y = 8; y < 44; y += 6) F.windowGrid(g, e, 3, y, 4, 1, 2.2, 1.4, 1.1, 0, { seed: y, lit: .5 });
    F.hazard(g, 0, h - 10, w, .9, .5);
    F.serviceBoard(g, e, 3.2, h - 26, 11.6, 4.6, ['VTX  CONTROL'], {});
  } else if (kind === 'workshop') {
    for (let i = 0; i < 3; i++) F.bay(g, e, 3 + i * 14.5, h - 6.4, 9.5, 6.4, { vehicle: i === 1 ? 'vtx' : 'taxi', seed: 20 + i });
    F.windowGrid(g, e, 3, 1.8, 11, 1, 3, 1.1, 1.25, 0, { seed: 14, lit: .8, cool: '#9fd8ff', coolP: .4 });
    F.text(g, e, 'VTX ENGINEERING  ·  PROTOTYPING  ·  R&D', w - 1, 2.6, .9, { color: F.WHITE, align: 'right', font: 'Impact,Arial', spacing: .1 });
  } else if (kind === 'ops') {
    g.fillStyle = F.YEL; g.fillRect(0, 5, w, .5); g.fillRect(0, 10, w, .5);
    F.windowGrid(g, e, 2, 6.2, 7, 1, 3, 2.6, 1.1, 0, { seed: 31, lit: .85, cool: '#9fd8ff', coolP: .3 });
    F.text(g, e, name, w / 2, 3.6, 1.7, { color: '#1a1d20', align: 'center', font: 'Impact,Arial', spacing: .2 });
    F.checker(g, 0, 4.1, w, .5, .25, F.YEL, F.BLK);
  } else if (kind === 'terminal') {
    F.windowGrid(g, e, 3, h - 7.2, 6, 1, 3.4, 5.6, .8, 0, { seed: 40, lit: .9, warm: ['#ffe2a8', '#ffd58a'] });
    F.text(g, e, name, w / 2, 3.1, 1.15, { color: F.YEL, align: 'center', font: 'Impact,Arial', spacing: .16, max: w - 3 });
    F.taxiIcon(g, e, w - 5, 3.2, 3, F.YEL);
  } else if (kind === 'brick') {
    F.windowGrid(g, e, 2.5, 3, 5, 1, 3.4, 3, 1.4, 0, { seed: 50, lit: .8, frame: '#2a1b18' });
    F.wordmark(g, e, 2, 7.6, w - 4, 3.2, { tagline: false, board: true });
    F.text(g, e, name, w / 2, 2.3, 1.1, { color: F.YEL, align: 'center', font: 'Impact,Arial', spacing: .2 });
  } else if (kind === 'cargo') {
    F.text(g, e, name, w / 2, h - 2.5, 2.2, { color: '#0b0c0e', align: 'center', font: 'Impact,Arial', spacing: .2 });
    F.hazard(g, 0, h - .6, w, .6, .5);
  } else if (kind === 'stack') {
    F.text(g, e, 'ODD PARTS', w / 2, 8, 5.2, { color: '#0b0c0e', align: 'center', font: 'Impact,Arial', spacing: .3 });
    F.text(g, e, 'BIG IDEAS', w / 2, 14.5, 5.2, { color: '#0b0c0e', align: 'center', font: 'Impact,Arial', spacing: .3 });
    F.text(g, e, 'FURTHER  MILES', w / 2, 21, 4, { color: F.YEL, align: 'center', font: 'Impact,Arial', spacing: .3 });
    F.checker(g, 4, 22.6, w - 8, .8, .4, F.YEL, F.BLK);
  }
}

function paintSide(o, kind, g, e, w, h, seed, flavour) {
  baseWall(kind, g, w, h);
  if (kind === 'hangar' && flavour === 'W') {
    F.text(g, e, 'VTX', w / 2, h - 3.8, 7.5, { color: F.WHITE, align: 'center', spacing: .5 });
    F.text(g, e, 'AVIATION  DIVISION', w / 2, h - 11.6, 1.6, { color: F.YEL, align: 'center', font: 'Impact,Arial', spacing: .35 });
    F.hazard(g, 1, 1, w - 2, .7, .5); F.checker(g, w - 10, 3, 9, .9, .3, F.YEL, F.BLK, e);
  } else if (kind === 'hangar' && flavour === 'E') { // wall of fame hung with company artwork (images are overlaid separately)
    F.text(g, e, 'THE PEOPLE BEHIND THE JOURNEY', w / 2, 2.8, 1.5, { color: F.YEL, align: 'center', font: 'Impact,Arial', spacing: .25 });
    F.checker(g, 0, 3.6, w, .6, .3, F.YEL, F.BLK);
    ['THE INTERN', 'FIELD TESTING', 'THE HEARING', 'STRATEGY ROOM', 'THE TEAM'].forEach((label, i) => {
      const x = .85 + i * 6.55; g.fillStyle = '#12161a'; g.fillRect(x - .25, 5.2, 6.1, 7.1); g.strokeStyle = '#d6a960'; g.lineWidth = .1; g.strokeRect(x - .25, 5.2, 6.1, 7.1);
      F.text(g, e, label, x + 2.8, 13.2, .6, { color: '#e6c68e', align: 'center', font: 'Georgia,serif', spacing: .05 });
    });
  } else if (kind === 'hangar') {
    F.text(g, e, 'VADER’S TAXIS', w / 2, h - 6, 3.4, { color: F.YEL, align: 'center' }); F.text(g, e, 'SAME PEOPLE · FURTHER PLACES', w / 2, h - 8.5, 1.1, { color: F.WHITE, align: 'center', font: 'Impact,Arial', spacing: .3 });
    for (let x = 5; x < w - 4; x += 9) F.windowGrid(g, e, x, 3, 1, 1, 3, 1.2, 0, 0, { seed: x, lit: .7 });
  } else if (kind === 'tower') {
    for (let y = 8; y < 44; y += 6) F.windowGrid(g, e, 3, y, 4, 1, 2.2, 1.4, 1.1, 0, { seed: y + seed, lit: .4 });
  } else if (kind === 'workshop' || kind === 'ops' || kind === 'office' || kind === 'terminal' || kind === 'brick') {
    const rows = Math.max(1, Math.floor((h - 4) / 4)), cols = Math.max(1, Math.floor((w - 3) / 5));
    F.windowGrid(g, e, (w - cols * 5 + 1.6) / 2, 2.2, cols, rows, 3.4, 2.2, 1.6, 1.8, { seed, lit: .55 });
  }
  if (kind !== 'tower') { g.fillStyle = F.YEL; g.fillRect(0, h - 1.4, w, .12); }
}

// ----------------------------------------------------------------- roofs
function paintRoof(o, g, w, h) {
  g.fillStyle = '#3c4044'; g.fillRect(0, 0, w, h);
  const r = (s) => { let v = s; return () => (v = (v * 16807) % 2147483647) / 2147483647; }, rr = r(o.center[0] * 7 + 3);
  for (let i = 0; i < w * h * 1.4; i++) { g.fillStyle = rr() < .5 ? 'rgba(0,0,0,.14)' : 'rgba(255,255,255,.06)'; g.fillRect(rr() * w, rr() * h, .35, .35); }
  g.lineWidth = .22; g.strokeStyle = F.YEL; g.strokeRect(.5, .5, w - 1, h - 1);
  if (o.landable) {
    const m = 4.5; g.setLineDash([1.4, 1]); g.lineWidth = .15; g.strokeStyle = 'rgba(245,184,0,.85)'; g.strokeRect(m, m, w - 2 * m, h - 2 * m); g.setLineDash([]);
    const cx = w / 2, cy = h / 2; g.strokeStyle = F.YEL; g.lineWidth = .28; g.beginPath(); g.arc(cx, cy, 3.4, 0, Math.PI * 2); g.stroke();
    g.beginPath(); g.arc(cx, cy, 2.6, 0, Math.PI * 2); g.lineWidth = .1; g.strokeStyle = '#e8e6d8'; g.stroke();
    F.text(g, null, 'VTX', cx, cy + .55, 1.5, { color: '#e8e6d8', align: 'center', glow: false });
  } else {
    g.strokeStyle = '#b8402c'; g.lineWidth = .45; for (let x = 4; x < w - 3; x += 9) { g.beginPath(); g.moveTo(x, 4); g.lineTo(x + 3, 7); g.moveTo(x + 3, 4); g.lineTo(x, 7); g.stroke(); }
  }
}

// ----------------------------------------------------------------- builder
export function buildBuildings(scene, world, { ppm = 24, quality = 1 } = {}) {
  const group = new THREE.Group(); group.name = 'vtx-buildings';
  const updaters = [];
  const trimMat = metal('#c9a000', { roughness: .45 });
  const dark = metal('#16191c', { roughness: .65 });
  const boxAt = (fr, u, v, w, h, d, mat, out = 0) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); place(b, fr, u, v, out + d / 2); b.castShadow = true; b.receiveShadow = true; group.add(b); return b; };

  for (const o of world.obstacles) {
    if (o.kind !== 'box' || !BUILDINGS[o.id]) continue;
    const { kind } = BUILDINGS[o.id], frontSide = FRONT[o.id] || 'S', hero = o.id === 'hangar';
    const roles = [[frontSide, 'front'], [OPPOSITE[frontSide], 'back']];
    const adj = frontSide === 'S' || frontSide === 'N' ? ['E', 'W'] : ['S', 'N'];
    adj.forEach((s) => roles.push([s, 'side']));
    let seed = o.center[0] * 3 + o.center[1];
    for (const [side, role] of roles) {
      const fr = wallFrame(o, side), emit = role === 'front' || (kind === 'hangar' && role === 'side') || kind === 'tower' || kind === 'workshop' || kind === 'ops' || kind === 'office' || kind === 'terminal' || kind === 'brick';
      const tex = F.paintTexture(fr.width, fr.height, role === 'front' ? ppm * (hero ? 1.5 : 1) : ppm * .55, (g, e, w, h) => {
        if (role === 'front') paintFront(o, kind, g, e, w, h); else paintSide(o, kind, g, e, w, h, (seed += 7), kind === 'hangar' ? side : '');
      }, { emit, maxDim: role === 'front' ? (hero ? 2048 : 1536) : 1024 });
      const mat = F.material(tex, role === 'front' ? 1.0 : .8);
      const wall = new THREE.Mesh(new THREE.PlaneGeometry(fr.width, fr.height), mat);
      wall.position.copy(fr.center); orient(wall, fr); wall.castShadow = true; wall.receiveShadow = true; mat.shadowSide = THREE.DoubleSide; group.add(wall);
      if (kind === 'hangar' && role === 'side' && side === 'E') addGallery(group, fr);
    }
    // roof
    const [cx, cy, cz] = o.center, [hx, hy, hz] = o.half;
    const rt = F.paintTexture(hx * 2, hy * 2, 8, (g, e, w, h) => paintRoof(o, g, w, h), { emit: false, maxDim: 768 });
    const roof = new THREE.Mesh(new THREE.PlaneGeometry(hx * 2, hy * 2), F.material(rt, 0, { roughness: .9 }));
    roof.position.set(cx, cy, cz + hz); roof.receiveShadow = true; roof.castShadow = true; roof.material.shadowSide = THREE.DoubleSide; group.add(roof);

    // ---- 3-D trim on the front wall (all within maxTrimDepth of the collider)
    const fr = wallFrame(o, frontSide), W = fr.width, H = fr.height;
    if (kind === 'hangar') {
      const signTex = F.paintTexture(38, 5.6, 40, (g, e, w, h) => F.wordmark(g, e, 0, 0, w, h, { tagline: true }), { maxDim: 2048 });
      const signMat = [dark, dark, dark, dark, F.material(signTex, 1.1, { roughness: .6 }), dark];
      const sign = new THREE.Mesh(new THREE.BoxGeometry(38, 5.6, .5), signMat); place(sign, fr, W / 2, 14.6, .25); sign.castShadow = true; group.add(sign);

      // Transgression Record blackboard (VT-2887 regarding the banana incident)
      const trTex = transgressionTexture();
      const trMat = new THREE.MeshStandardMaterial({ map: trTex, roughness: 0.6 });
      const trMesh = new THREE.Mesh(new THREE.BoxGeometry(2.4, 1.4, 0.08), trMat);
      place(trMesh, fr, 4.0, 3.2, 0.35); trMesh.castShadow = true; group.add(trMesh);

      // Steve Dark's Citation Certificate for Extraordinary Altruistic Heroism (31 Oct 2026)
      const citTex = citationTexture();
      const citMat = new THREE.MeshStandardMaterial({ map: citTex, roughness: 0.4 });
      const citMesh = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.6, 0.06), citMat);
      place(citMesh, fr, 1.6, 3.2, 0.35); citMesh.castShadow = true; group.add(citMesh);

      // The Gold Medal for Altruistic Heroism in navy velvet case
      const medalCase = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.65, 0.12), metal('#0f1b2b', { roughness: 0.85 }));
      const goldMedal = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.04, 24).rotateX(Math.PI / 2), metal('#d4af37', { roughness: 0.25, metalness: 0.9 }));
      goldMedal.position.set(0, 0, 0.07);
      medalCase.add(goldMedal);
      place(medalCase, fr, 1.6, 1.8, 0.35); medalCase.castShadow = true; group.add(medalCase);

      // Depot To-Do Whiteboard with checklist & odd parts big ideas
      const wbTex = depotWhiteboardTexture();
      const wbMat = new THREE.MeshStandardMaterial({ map: wbTex, roughness: 0.35 });
      const wbMesh = new THREE.Mesh(new THREE.BoxGeometry(2.6, 1.4, 0.08), wbMat);
      place(wbMesh, fr, 43.8, 3.2, 0.35); wbMesh.castShadow = true; group.add(wbMesh);

      // EXHIBIT A: The Banana on a Plinth outside Compliance
      const plinthGroup = new THREE.Group();
      const ped = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.95), metal('#45484c', { roughness: 0.8 }));
      ped.position.set(0, 0, 0.475); ped.castShadow = true; plinthGroup.add(ped);
      const plaque = new THREE.Mesh(new THREE.PlaneGeometry(0.35, 0.15), metal('#d4af37', { roughness: 0.3 }));
      plaque.position.set(0, -0.26, 0.5); plinthGroup.add(plaque);
      const bananaCurve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(-0.16, 0, 0.98),
        new THREE.Vector3(-0.06, 0.05, 0.96),
        new THREE.Vector3(0.06, 0.05, 0.96),
        new THREE.Vector3(0.16, 0, 0.99),
      ]);
      const banana = new THREE.Mesh(new THREE.TubeGeometry(bananaCurve, 12, 0.045, 8, false), new THREE.MeshStandardMaterial({ color: '#ffdd00', roughness: 0.4 }));
      banana.castShadow = true; plinthGroup.add(banana);
      const bSpot = new THREE.SpotLight('#fff0d0', 2.5, 4, Math.PI / 4, 0.5);
      bSpot.position.set(0, -0.6, 1.5); bSpot.target = banana;
      plinthGroup.add(bSpot, bSpot.target);
      place(plinthGroup, fr, 2.2, 0, 0.35); group.add(plinthGroup);
      for (const u0 of [5.5, 24]) { const bw = 16.5, bh = 10.5; boxAt(fr, u0 - .45, bh / 2, .5, bh, .5, trimMat); boxAt(fr, u0 + bw - .05, bh / 2, .5, bh, .5, trimMat); boxAt(fr, u0 + bw / 2, bh + .25, bw + 1.4, .5, .55, trimMat); }
      for (const [u, lines, title, checkerOn] of [[2, ['24/7 DISPATCH', 'FLEET SERVICING', 'VTOL CONVERSIONS', 'CUSTOM BUILDS', 'PROTOTYPING', 'FLIGHT SYSTEMS', 'PILOTS WELCOME'], null, false], [44, ['TAXIS', 'REPAIRS', 'MODIFICATIONS', 'DIAGNOSTICS', 'R&D'], null, true]]) {
        const pt = F.paintTexture(4, 18, 40, (g, e, w, h) => {
          g.drawImage(stoneImage(), 0, 0, w, h); F.serviceBoard(g, e, .3, 4, w - .6, 8.2, lines, { title: u < 10 ? null : null });
          if (checkerOn) { F.checker(g, .3, 12.6, 1.6, .8, .2, F.YEL, F.BLK, e); F.text(g, e, 'SAME PEOPLE', 2, 15, .5, { color: F.WHITE, font: 'Impact,Arial' }); F.text(g, e, 'FURTHER PLACES', 2, 15.7, .5, { color: F.WHITE, font: 'Impact,Arial' }); }
        }, { maxDim: 1024 });
        const pier = new THREE.Mesh(new THREE.BoxGeometry(4, 18, .6), [metal('#585550', { roughness: .9, metalness: 0 }), metal('#585550', { roughness: .9, metalness: 0 }), metal('#585550', { roughness: .9, metalness: 0 }), metal('#585550', { roughness: .9, metalness: 0 }), F.material(pt, 1, { metalness: 0 }), metal('#585550')]);
        place(pier, fr, u, 9, .3); pier.castShadow = true; pier.receiveShadow = true; group.add(pier);
      }
      // floodlight bar under the sign
      for (let i = 0; i < 7; i++) { const fx = 5 + i * 6; boxAt(fr, fx, 11.6, .9, .3, .5, dark); const lamp = new THREE.Mesh(new THREE.BoxGeometry(.7, .08, .4), glowMat('#ffe1a8', 4)); place(lamp, fr, fx, 11.42, .3); group.add(lamp); }
    } else {
      // generic sign box + door canopy
      const sw = Math.min(W - 3, 26), sh = 2.6, vTop = kind === 'tower' ? 42 : Math.min(H - 1.8, kind === 'office' ? 21.5 : H - 1.8);
      if (!['ops', 'terminal', 'brick', 'cargo', 'stack', 'tower'].includes(kind)) {
        const st = F.paintTexture(sw, sh, 36, (g, e, w, h) => F.wordmark(g, e, 0, 0, w, h, { tagline: false }), { maxDim: 1536 });
        const sg = new THREE.Mesh(new THREE.BoxGeometry(sw, sh, .4), [dark, dark, dark, dark, F.material(st, 1.1, { roughness: .6 }), dark]); place(sg, fr, W / 2, vTop - sh / 2, .2); sg.castShadow = true; group.add(sg);
      }
      if (kind === 'workshop') for (let i = 0; i < 3; i++) boxAt(fr, 3 + i * 14.5 + 4.75, 6.65, 10.4, .3, .7, trimMat);
      if (kind === 'office') {
        boxAt(fr, W / 2, 4.5, 11, .35, .8, dark);
        // Rooftop black cab weather vane
        const vaneGroup = new THREE.Group();
        const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 2.2, 8), metal('#1a1a1a'));
        rod.position.set(0, 0, 1.1); vaneGroup.add(rod);
        const cabShape = new THREE.Shape();
        cabShape.moveTo(-0.8, 0); cabShape.lineTo(0.8, 0); cabShape.lineTo(0.8, 0.3); cabShape.lineTo(0.45, 0.35); cabShape.lineTo(0.25, 0.65); cabShape.lineTo(-0.35, 0.65); cabShape.lineTo(-0.55, 0.35); cabShape.lineTo(-0.8, 0.3); cabShape.closePath();
        const cabMesh = new THREE.Mesh(new THREE.ExtrudeGeometry(cabShape, { depth: 0.04, bevelEnabled: false }), metal('#f5b800'));
        cabMesh.position.set(0, 0, 2.0); vaneGroup.add(cabMesh);
        vaneGroup.position.set(o.center[0], o.center[1], o.center[2] + o.half[2]);
        group.add(vaneGroup);
        updaters.push((t) => { cabMesh.rotation.z = Math.sin(t * 0.6) * 0.5; });
      }
      if (kind === 'tower') addTowerTop(group, o, updaters);
    }
  }
  scene.add(group);
  return { group, update: (t) => updaters.forEach((u) => u(t)) };
}

let _stone = null;
function stoneImage() { if (!_stone) { _stone = document.createElement('canvas'); _stone.width = _stone.height = 256; const g = _stone.getContext('2d'); g.fillStyle = '#6f6a62'; g.fillRect(0, 0, 256, 256); for (let y = 0; y < 256; y += 24) { let x = (y / 24 % 2) * 20; while (x < 256) { const w = 34 + Math.random() * 28; g.fillStyle = `hsl(35,${6 + Math.random() * 6}%,${34 + Math.random() * 12}%)`; g.fillRect(x + 1.5, y + 1.5, w - 3, 21); x += w; } } } return _stone; }

function addGallery(group, fr) {
  const loader = new THREE.TextureLoader(), files = ['1-68021.jpg', '2-67362.jpg', '3-67194.jpg', '4-66709.jpg', '5-67766.jpg'];
  files.forEach((file, i) => {
    const u = .85 + i * 6.55 + 2.8;
    loader.load('/assets/company/' + file, (t) => {
      t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
      const a = t.image.width / t.image.height, w = Math.min(5.7, 6.6 * a), h = w / a;
      const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshStandardMaterial({ map: t, roughness: .55, emissiveMap: t, emissive: '#ffffff', emissiveIntensity: .35, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
      place(m, fr, u, 8.75, .07); group.add(m);
    }, undefined, (e) => console.warn('Company artwork unavailable', file, e));
  });
}

function addTowerTop(group, o, updaters) {
  const [cx, cy, cz] = o.center, [hx, hy, hz] = o.half, top = cz + hz;
  const cab = new THREE.Mesh(new THREE.BoxGeometry(hx * 2 + 1.4, hy * 2 + 1.4, 6.5), new THREE.MeshStandardMaterial({ color: '#0b1a22', roughness: .08, metalness: .6, emissive: '#2a8fb0', emissiveIntensity: .45, envMapIntensity: 1.6 }));
  cab.position.set(cx, cy, top - 3.25); cab.castShadow = true; group.add(cab);
  const slab = new THREE.Mesh(new THREE.BoxGeometry(hx * 2 + 1.6, hy * 2 + 1.6, .6), metal('#4a4f52', { roughness: .8 })); slab.position.set(cx, cy, top + .3); group.add(slab);
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(.08, .12, 5, 6).rotateX(Math.PI / 2), metal('#9aa0a3')); mast.position.set(cx + 3, cy - 2, top + 2.9); group.add(mast);
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(.45, 12, 8), glowMat('#ff2a1a', 4)); beacon.position.set(cx, cy, top + .8); group.add(beacon);
  // Rotating radar scanner on mast
  const radar = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.35, 0.4), metal('#d8dde0'));
  radar.position.set(cx + 3, cy - 2, top + 5.5); group.add(radar);
  updaters.push((t) => { radar.rotation.z = t * 2.4; });
  updaters.push((t) => { beacon.material.emissiveIntensity = (Math.sin(t * 3.2) > .55) ? 6 : .25; });
}
