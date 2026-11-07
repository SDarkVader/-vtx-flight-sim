// Terrain surface, distant landscape (hills, crag and castle, town skyline, far forest) and water.
// The ground mesh uses exactly the same heightfield samples as the physics heightfield;
// the distant landscape lives entirely OUTSIDE the physical +/-500 m test area.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/BufferGeometryUtils.js';
import { grassTexture, rng, makeCanvas, toTexture } from './textures.js';

// ---- value noise -------------------------------------------------------------
function hash(ix, iy) { let h = (ix * 374761393 + iy * 668265263) | 0; h = (h ^ (h >>> 13)) * 1274126177 | 0; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }
export function noise2(x, y) {
  const ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
  const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
  const a = hash(ix, iy), b = hash(ix + 1, iy), c = hash(ix, iy + 1), d = hash(ix + 1, iy + 1);
  return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
}
export function fbm(x, y, oct = 4) { let v = 0, a = .5, f = 1; for (let i = 0; i < oct; i++) { v += a * noise2(x * f, y * f); f *= 2.03; a *= .5; } return v; }
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export function heightfieldZ(w, x, y) {
  const n = w.heights_m.length, half = w.half_m, h = w.heights_m;
  const u = THREE.MathUtils.clamp((x + half) / (2 * half) * (n - 1), 0, n - 1.00001), v = THREE.MathUtils.clamp((y + half) / (2 * half) * (n - 1), 0, n - 1.00001);
  const i = Math.floor(u), j = Math.floor(v), a = u - i, b = v - j;
  return a > b ? (1 - a) * h[j][i] + (a - b) * h[j][i + 1] + b * h[j + 1][i + 1] : (1 - b) * h[j][i] + (b - a) * h[j + 1][i] + a * h[j + 1][i + 1];
}

// ---- physical-terrain visual surface --------------------------------------------
export function buildTerrain(w) {
  const n = w.heights_m.length, vertices = [], uvs = [], colors = [], indices = [];
  const grass = new THREE.Color('#d9d79a'), mown = new THREE.Color('#ecdfa6'), heather = new THREE.Color('#b0987a'), rock = new THREE.Color('#aaa59c'), moss = new THREE.Color('#bdd08f');
  const c = new THREE.Color();
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
    const x = -w.half_m + i / (n - 1) * w.half_m * 2, y = -w.half_m + j / (n - 1) * w.half_m * 2, z = w.heights_m[j][i];
    vertices.push(x, y, z); uvs.push(x / 16, y / 16);
    const f = fbm(x / 60, y / 60), g = fbm(x / 17 + 9, y / 17);
    c.copy(grass).lerp(mown, smooth(.45, .75, f)).lerp(moss, smooth(.5, .8, g) * .6);
    c.lerp(heather, smooth(10, 32, z) * .75).lerp(rock, smooth(34, 55, z) * (.5 + .5 * g));
    c.multiplyScalar(.9 + .22 * fbm(x / 8, y / 8));
    colors.push(c.r, c.g, c.b);
  }
  for (let j = 0; j < n - 1; j++) for (let i = 0; i < n - 1; i++) { const a = j * n + i; indices.push(a, a + 1, a + n + 1, a, a + n + 1, a + n); }
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  geom.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geom.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geom.setIndex(indices); geom.computeVertexNormals();
  const mesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ map: grassTexture(), vertexColors: true, roughness: 1, metalness: 0 }));
  mesh.receiveShadow = true; mesh.renderOrder = -70; mesh.name = 'terrain-visual';
  return mesh;
}

// ---- distant hills ------------------------------------------------------------------
const CRAG = { x: -380, y: 1480, r: 150, h: 175 };       // castle-rock silhouette (visual only, far outside the test area)
const SEAT = { x: 760, y: 1320, r: 520, h: 250 };        // large hill mass
export function makeHills(w) {
  const E = w.half_m, edge = (th) => { const m = Math.max(Math.abs(Math.cos(th)), Math.abs(Math.sin(th))); return [E * Math.cos(th) / m, E * Math.sin(th) / m]; };
  const hillZ = (x, y, th, dist, e) => {
    const north = Math.exp(-(((th - Math.PI / 2 + Math.PI * 3) % (Math.PI * 2) - Math.PI) ** 2) / .5);
    const A = (150 + 170 * (.5 + .5 * Math.sin(1.7 * th + .6))) * (1 - .78 * north);
    let h = e * (1 - smooth(0, 380, dist)) + A * smooth(260, 1700, dist) * (.5 + .5 * fbm(x / 520 + 3, y / 520)) + 22 * fbm(x / 90, y / 90) * smooth(0, 300, dist);
    h += SEAT.h * Math.exp(-(((x - SEAT.x) ** 2 + (y - SEAT.y) ** 2) / (SEAT.r * SEAT.r)));
    h += CRAG.h * Math.exp(-(((x - CRAG.x) ** 2 + (y - CRAG.y) ** 2) / (CRAG.r * CRAG.r)) * 1.0);
    return h;
  };
  const na = 240, nr = 56, L = 3600, vertices = [], colors = [], indices = [];
  const col = new THREE.Color(), low = new THREE.Color('#9aa464'), mid = new THREE.Color('#8f7d62'), high = new THREE.Color('#8f8a84');
  const edgeH = []; for (let i = 0; i <= na; i++) { const [bx, by] = edge(i / na * Math.PI * 2); edgeH.push(heightfieldZ(w, bx, by)); }
  for (let i = 0; i <= na; i++) {
    const th = i / na * Math.PI * 2, [bx, by] = edge(th), dx = Math.cos(th), dy = Math.sin(th);
    for (let k = 0; k <= nr; k++) {
      const dist = Math.pow(k / nr, 1.7) * L, x = bx + dx * dist, y = by + dy * dist, z = hillZ(x, y, th, dist, edgeH[i % na]);
      vertices.push(x, y, z);
      col.copy(low).lerp(mid, smooth(40, 150, z)).lerp(high, smooth(150, 320, z)).multiplyScalar(.85 + .3 * fbm(x / 40, y / 40));
      colors.push(col.r, col.g, col.b);
    }
  }
  for (let i = 0; i < na; i++) for (let k = 0; k < nr; k++) { const a = i * (nr + 1) + k, b = a + nr + 1; indices.push(a, a + 1, b, b, a + 1, b + 1); }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  g.setIndex(indices); g.computeVertexNormals();
  const mesh = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, side: THREE.DoubleSide }));
  mesh.name = 'distant-hills'; mesh.renderOrder = -70;
  const heightAt = (x, y) => { const th = Math.atan2(y, x), [bx, by] = edge(th < 0 ? th + Math.PI * 2 : th); const dist = Math.hypot(x, y) - Math.hypot(bx, by); const idx = Math.round(((th < 0 ? th + Math.PI * 2 : th) / (Math.PI * 2)) * na) % na; return hillZ(x, y, th < 0 ? th + Math.PI * 2 : th, Math.max(0, dist), edgeH[idx]); };
  return { mesh, heightAt };
}

// ---- castle + town skyline -----------------------------------------------------------
function windowGrid() {
  const c = makeCanvas(64, 64), g = c.getContext('2d'), r = rng(2);
  g.fillStyle = '#000'; g.fillRect(0, 0, 64, 64);
  for (let y = 4; y < 60; y += 8) for (let x = 4; x < 60; x += 8) if (r() < .55) { g.fillStyle = r() < .8 ? '#ffc766' : '#8fd2ff'; g.fillRect(x, y, 4, 5); }
  return toTexture(c, { wrap: true });
}
export function makeSkyline(heightAt) {
  const group = new THREE.Group(); group.name = 'skyline';
  const r = rng(909);
  const stone = new THREE.MeshStandardMaterial({ color: '#4b4543', roughness: .95, emissive: '#ffffff', emissiveMap: windowGrid(), emissiveIntensity: .35 });
  stone.emissiveMap.repeat.set(2, 3);
  const box = new THREE.BoxGeometry(1, 1, 1).translate(0, 0, .5);
  const N = 520, town = new THREE.InstancedMesh(box, stone, N), m = new THREE.Matrix4(), q = new THREE.Quaternion(), tint = new THREE.Color();
  for (let i = 0; i < N; i++) {
    const x = -1500 + r() * 2300, y = 1450 + r() * 700, h = 8 + r() * 20 * (r() < .12 ? 1.8 : 1), sx = 14 + r() * 22, sy = 14 + r() * 22;
    const base = heightAt(x, y) - 2;
    q.setFromAxisAngle(new THREE.Vector3(0, 0, 1), Math.round(r() * 2) * Math.PI / 2 + (r() - .5) * .08);
    m.compose(new THREE.Vector3(x, y, base), q, new THREE.Vector3(sx, sy, h)); town.setMatrixAt(i, m);
    town.setColorAt(i, tint.setHSL(.07 + r() * .04, .12, .17 + r() * .09));
  }
  town.castShadow = false; group.add(town);
  // Gothic spires
  const spire = new THREE.ConeGeometry(4, 62, 6).rotateX(Math.PI / 2).translate(0, 0, 31);
  const spires = new THREE.InstancedMesh(spire, new THREE.MeshStandardMaterial({ color: '#34302f', roughness: .9 }), 9);
  for (let i = 0; i < 9; i++) { const x = -560 + i * 120 + (r() - .5) * 40, y = 1260 + r() * 360; m.compose(new THREE.Vector3(x, y, heightAt(x, y) + 24), new THREE.Quaternion(), new THREE.Vector3(1 + r(), 1 + r(), .8 + r() * .9)); spires.setMatrixAt(i, m); }
  group.add(spires);
  // The castle on its rock
  const topZ = heightAt(CRAG.x, CRAG.y), castle = new THREE.Group(); castle.position.set(CRAG.x, CRAG.y, topZ - 4);
  const wall = new THREE.MeshStandardMaterial({ color: '#5d5551', roughness: .95, emissive: '#ffffff', emissiveMap: windowGrid(), emissiveIntensity: .3 });
  const part = (sx, sy, sz, x, y, z, mat = wall) => { const b = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), mat); b.position.set(x, y, z + sz / 2); castle.add(b); return b; };
  part(150, 52, 30, 0, 0, 0); part(60, 40, 52, -30, 6, 20); part(26, 26, 78, 30, 0, 22);
  for (const [x, y] of [[-70, -22], [70, -22], [-70, 24], [70, 24]]) { const t = new THREE.Mesh(new THREE.CylinderGeometry(9, 10, 44, 10).rotateX(Math.PI / 2), wall); t.position.set(x, y, 22); castle.add(t); const cap = new THREE.Mesh(new THREE.ConeGeometry(11, 16, 10).rotateX(Math.PI / 2), new THREE.MeshStandardMaterial({ color: '#2d2927', roughness: .9 })); cap.position.set(x, y, 52); castle.add(cap); }
  group.add(castle);
  return group;
}

// ---- far forest (outside the physical area; visual only) -------------------------------------
export function makeFarForest(heightAt, count = 1700, physicalHalf = 500) {
  const r = rng(515), crown = mergeGeometries([
    new THREE.ConeGeometry(7, 14, 7).rotateX(Math.PI / 2).translate(0, 0, 8),
    new THREE.ConeGeometry(5.2, 12, 7).rotateX(Math.PI / 2).translate(0, 0, 15),
    new THREE.ConeGeometry(3.4, 10, 7).rotateX(Math.PI / 2).translate(0, 0, 22),
  ]);
  const mesh = new THREE.InstancedMesh(crown, new THREE.MeshStandardMaterial({ color: '#304832', roughness: 1 }), count), m = new THREE.Matrix4(), col = new THREE.Color();
  let n = 0;
  while (n < count) {
    const th = r() * Math.PI * 2, d = 40 + Math.pow(r(), .8) * 1500, E = physicalHalf, mx = Math.max(Math.abs(Math.cos(th)), Math.abs(Math.sin(th)));
    const x = (E / mx + d) * Math.cos(th), y = (E / mx + d) * Math.sin(th);
    if (fbm(x / 140, y / 140) < .48) continue;                      // forest patches, not a uniform carpet
    if (y > 1100 && Math.abs(x) < 1300) continue;                   // keep the town clear
    const z = heightAt(x, y); if (z > 300) continue;
    const s = .8 + r() * 1.1; m.compose(new THREE.Vector3(x, y, z - 1), new THREE.Quaternion(), new THREE.Vector3(s, s, s * (.9 + r() * .5)));
    mesh.setMatrixAt(n, m); mesh.setColorAt(n, col.setHSL(.27 + r() * .06, .3, .16 + r() * .08)); n++;
  }
  mesh.frustumCulled = false; mesh.name = 'far-forest';
  return mesh;
}

export function makeWater(w, z) {
  const mat = new THREE.MeshPhysicalMaterial({ color: '#2a5a66', roughness: .05, metalness: 0, envMapIntensity: 2.2, clearcoat: 1, transparent: true, opacity: .93 });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w.water.half_x * 2, w.water.half_y * 2), mat);
  m.position.set(w.water.x, w.water.y, z); m.receiveShadow = true; m.name = 'water';
  return m;
}
