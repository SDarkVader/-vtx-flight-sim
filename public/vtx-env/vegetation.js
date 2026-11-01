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

export function buildTrees(scene, world) {
  const group = new THREE.Group(); group.name = 'vtx-trees';
  const trees = world.obstacles.filter((o) => o.kind === 'cylinder');
  if (!trees.length) return { group };
  const cone = (r, h, z) => new THREE.ConeGeometry(r, h, 8).rotateX(Math.PI / 2).translate(0, 0, z + h / 2);
  const conifer = shaded(mergeGeometries([cone(1, .5, 0), cone(.78, .45, .3), cone(.55, .42, .6)].map((g) => g.toNonIndexed())), new THREE.Color('#1f3a2a'), new THREE.Color('#4d7a52'));
  const broad = shaded(blobGeometry(3).translate(0, 0, 1), new THREE.Color('#5d6b2a'), new THREE.Color('#c79a2c'));
  const trunkGeo = new THREE.CylinderGeometry(.8, 1, 1, 8).rotateX(Math.PI / 2).translate(0, 0, .5);
  const mk = (geo, mat, n) => { const m = new THREE.InstancedMesh(geo, mat, n); m.castShadow = true; m.receiveShadow = true; m.frustumCulled = false; group.add(m); return m; };
  const isBroad = (o, i) => i % 3 === 2;
  const nB = trees.filter(isBroad).length, nC = trees.length - nB;
  const trunks = mk(trunkGeo, new THREE.MeshStandardMaterial({ color: '#4a3524', roughness: 1 }), trees.length);
  const cm = mk(conifer, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .95 }), Math.max(1, nC));
  const bm = mk(broad, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .9 }), Math.max(1, nB));
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), col = new THREE.Color(), r = rng(66);
  let ic = 0, ib = 0;
  trees.forEach((o, i) => {
    const [x, y, z] = o.center, rad = o.half[0], H = o.half[2] * 2, base = z - o.half[2];
    q.setFromAxisAngle(new THREE.Vector3(0, 0, 1), r() * 6.28);
    m4.compose(new THREE.Vector3(x, y, base), q, new THREE.Vector3(rad, rad, H * .55)); trunks.setMatrixAt(i, m4);
    if (isBroad(o, i)) { const R = rad * 1.9 + .6, h = H * .5; m4.compose(new THREE.Vector3(x, y, base + H * .45), q, new THREE.Vector3(R, R, h * .9)); bm.setMatrixAt(ib, m4); bm.setColorAt(ib++, col.setHSL(.1 + r() * .09, .55, .5 + r() * .15)); }
    else { const R = rad * 1.8 + .5; m4.compose(new THREE.Vector3(x, y, base + H * .12), q, new THREE.Vector3(R, R, H * .92)); cm.setMatrixAt(ic, m4); cm.setColorAt(ic++, col.setHSL(.33 + r() * .04, .35, .8 + r() * .35)); }
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
