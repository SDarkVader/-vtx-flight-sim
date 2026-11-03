// Trees for the PHYSICAL tree obstacles (world.py cylinders) and small service props that
// sit directly against a building wall. Tree trunks use the collider's own radius and
// height; crowns are only modestly wider than the trunk so what you can see is what you
// can hit.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/BufferGeometryUtils.js';
import { rng, makeCanvas, toTexture } from './textures.js';
import { LAYOUT } from './layout.js';
import * as F from './facade.js';

function shaded(geom, dark, light) {
  geom.computeBoundingBox(); const { min, max } = geom.boundingBox, c = new THREE.Color(), cols = [];
  const p = geom.attributes.position;
  for (let i = 0; i < p.count; i++) { const t = (p.getZ(i) - min.z) / Math.max(1e-6, max.z - min.z); c.copy(dark).lerp(light, t); cols.push(c.r, c.g, c.b); }
  geom.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3)); return geom;
}
function blobGeometry(seed) {
  const g = new THREE.IcosahedronGeometry(1, 2), p = g.attributes.position, r = rng(seed);
  const jit = new Map();
  for (let i = 0; i < p.count; i++) {
    const key = `${p.getX(i).toFixed(3)},${p.getY(i).toFixed(3)},${p.getZ(i).toFixed(3)}`;
    if (!jit.has(key)) jit.set(key, .82 + r() * .3);
    const k = jit.get(key); p.setXYZ(i, p.getX(i) * k, p.getY(i) * k, p.getZ(i) * k * .85);
  }
  g.computeVertexNormals(); return g;
}

// Fit a unit-space tree part inside the unit cylinder (radius <= .96, z in [z0, z1]).
function fitUnit(g, z0, z1, rMax = .96) {
  const p = g.attributes.position; let m = 0, lo = Infinity, hi = -Infinity;
  for (let i = 0; i < p.count; i++) { m = Math.max(m, Math.hypot(p.getX(i), p.getY(i))); lo = Math.min(lo, p.getZ(i)); hi = Math.max(hi, p.getZ(i)); }
  for (let i = 0; i < p.count; i++) p.setXYZ(i, p.getX(i) * rMax / m, p.getY(i) * rMax / m, z0 + (p.getZ(i) - lo) / (hi - lo) * (z1 - z0));
  g.computeVertexNormals(); return g;
}

// Trees are dressed onto the physical cylinders (world.py): every crown and trunk is built in
// unit space and scaled by the collider's own radius and height, so the whole tree stays
// INSIDE its collider (nothing visible outside what the aircraft can hit). Three columnar
// species keep the variety: spruce, cypress and a fastigiate broadleaf.
export function buildTrees(scene, world, opts = {}) {
  const group = new THREE.Group(); group.name = 'vtx-trees';
  const trees = world.obstacles.filter((o) => o.kind === 'cylinder');
  if (!trees.length) return { group };
  const cone = (r, h, z, s = 9) => new THREE.ConeGeometry(r, h, s).rotateX(Math.PI / 2).translate(0, 0, z + h / 2).toNonIndexed();
  const spruce = shaded(fitUnit(mergeGeometries([cone(1, .34, 0), cone(.82, .32, .2), cone(.64, .3, .4), cone(.45, .3, .58), cone(.26, .26, .76)]), .16, 1), new THREE.Color('#1c3526'), new THREE.Color('#507d56'));
  const cypressProfile = []; for (let k = 0; k <= 10; k++) { const t = k / 10; cypressProfile.push(new THREE.Vector2(Math.max(.02, Math.sin(Math.PI * Math.pow(t, .8)) * (1 - .35 * t)), t)); }
  const cypress = shaded(fitUnit(new THREE.LatheGeometry(cypressProfile, 9).rotateX(Math.PI / 2), .08, 1), new THREE.Color('#203a26'), new THREE.Color('#5d8a4f'));
  const broad = shaded(fitUnit(blobGeometry(3).scale(1, 1, 1.9), .3, 1), new THREE.Color('#566a2a'), new THREE.Color('#c39a34'));
  const trunkGeo = fitUnit(new THREE.CylinderGeometry(.75, 1, 1, 7).rotateX(Math.PI / 2).translate(0, 0, .5), 0, .4, .24);
  const mk = (geo, mat, n) => { const m = new THREE.InstancedMesh(geo, mat, Math.max(1, n)); m.count = n; m.castShadow = true; m.receiveShadow = true; m.frustumCulled = false; group.add(m); return m; };
  const kindOf = (i) => (i % 3 === 2 ? 2 : i % 3 === 1 ? 1 : 0);
  const counts = [0, 0, 0]; trees.forEach((o, i) => counts[kindOf(i)]++);
  const trunks = mk(trunkGeo, new THREE.MeshStandardMaterial({ color: '#4a3524', roughness: 1 }), trees.length);
  const leaf = (rough) => new THREE.MeshStandardMaterial({ vertexColors: true, roughness: rough });
  const crowns = [mk(spruce, leaf(.95), counts[0]), mk(cypress, leaf(.92), counts[1]), mk(broad, leaf(.88), counts[2])];
  crowns.forEach((c, k) => { c.name = ['tree-spruce', 'tree-cypress', 'tree-broadleaf'][k]; }); trunks.name = 'tree-trunks';
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), col = new THREE.Color(), r = rng(66), at = [0, 0, 0];
  trees.forEach((o, i) => {
    const [x, y, z] = o.center, rad = o.half[0], H = o.half[2] * 2, base = z - o.half[2], k = kindOf(i);
    q.setFromAxisAngle(new THREE.Vector3(0, 0, 1), r() * 6.28);
    m4.compose(new THREE.Vector3(x, y, base), q, new THREE.Vector3(rad, rad, H));
    trunks.setMatrixAt(i, m4);
    crowns[k].setMatrixAt(at[k], m4);
    const hue = [.33 + r() * .04, .27 + r() * .05, .1 + r() * .09][k];
    crowns[k].setColorAt(at[k]++, col.setHSL(hue, k === 2 ? .55 : .35, k === 2 ? .5 + r() * .15 : .8 + r() * .3));
  });
  scene.add(group); return { group };
}

// A garage-style forecourt against the hangar's west wall: fuel/charging pumps, cones, barrels.
// Everything stays within LAYOUT.maxTrimDepth of the wall, so it never sits in open airspace.
export function buildForecourt(scene, world) {
  const hangar = world.obstacles.find((o) => o.id === 'hangar'); if (!hangar) return null;
  const group = new THREE.Group(); group.name = 'vtx-forecourt';
  const wallX = hangar.center[0] - hangar.half[0], y0 = hangar.center[1] - hangar.half[1];  // west wall, southern end
  const d = LAYOUT.maxTrimDepth, mk = (g, m) => { const o = new THREE.Mesh(g, m); o.castShadow = true; o.receiveShadow = true; group.add(o); return o; };
  const white = new THREE.MeshStandardMaterial({ color: '#d9dcdc', roughness: .4, metalness: .2 }), dark = new THREE.MeshStandardMaterial({ color: '#16191c', roughness: .5, metalness: .3 });
  const screen = new THREE.MeshStandardMaterial({ color: '#000', emissive: '#38e4ff', emissiveIntensity: 2.2 });
  for (let i = 0; i < 3; i++) {
    const y = y0 + 4 + i * 2.4, x = wallX - d / 2 - .02;
    const body = mk(new THREE.BoxGeometry(d * .8, .7, 1.9), [white, white, white, white, white, white]); body.position.set(x, y, .95);
    const top = mk(new THREE.BoxGeometry(d * .82, .72, .22), dark); top.position.set(x, y, 1.85);
    const scr = mk(new THREE.BoxGeometry(.04, .42, .34), screen); scr.position.set(x - d * .4 - .01, y, 1.35);
    const band = mk(new THREE.BoxGeometry(d * .81, .71, .12), new THREE.MeshStandardMaterial({ color: ['#f5b800', '#2b6a9a', '#2e9a57'][i], roughness: .5 })); band.position.set(x, y, .45);
  }
  // price board: ELECTRIC / HYBRID / DIESEL / HYDROGEN? WHY NOT?
  const tex = F.paintTexture(1.4, 2, 120, (g, e, w, h) => { F.serviceBoard(g, e, 0, 0, w, h, ['ELECTRIC', 'HYBRID', 'DIESEL', 'HYDROGEN', 'WHY NOT?'], {}); }, { maxDim: 256 });
  const board = mk(new THREE.BoxGeometry(.06, 1.4, 2), [dark, F.material(tex, 1, {}), dark, dark, dark, dark]);
  board.position.set(wallX - .1, y0 + 2.2, 1.0);
  // cones and barrels
  const cone = new THREE.ConeGeometry(.2, .6, 10).rotateX(Math.PI / 2).translate(0, 0, .3), coneMat = new THREE.MeshStandardMaterial({ color: '#ff6a1a', roughness: .6 });
  for (const [x, y] of [[wallX - .6, y0 + 1], [wallX - .6, y0 + 11.8], [wallX - .45, y0 + 12.8]]) { const c = mk(cone, coneMat); c.position.set(x, y, 0); }
  const barrel = new THREE.CylinderGeometry(.28, .28, .9, 12).rotateX(Math.PI / 2).translate(0, 0, .45);
  [['#f5b800', 14.2], ['#25272b', 14.9], ['#3d5a6d', 15.6]].forEach(([c, dy]) => { const b = mk(barrel, new THREE.MeshStandardMaterial({ color: c, roughness: .55, metalness: .3 })); b.position.set(wallX - .35, y0 + dy, 0); });
  scene.add(group); return { group };
}
