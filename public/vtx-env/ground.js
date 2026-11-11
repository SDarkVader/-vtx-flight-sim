// Ground model used to drape paint, inset lights and water EXACTLY onto the rendered ground.
// Inside +/-500 m the ground is the physics heightfield (world.py terrain_z: same samples,
// same lower-left/upper-right diagonal), so anything draped here sits on the physics surface.
// Outside +/-500 m (visual-only backdrop) it is the distant-hills mesh triangles.
// This module only READS world data; it never alters terrain, obstacles or pads.
import * as THREE from 'three';

const FLAT = 220; // world.py: heights are exactly 0 for max(|x|,|y|) <= 220 m

export function createGround(w, hillsMesh) {
  const n = w.heights_m.length, half = w.half_m, h = w.heights_m, step = 2 * half / (n - 1);
  const flatCell = Math.round((half - FLAT) / step); // first cell index of the flat square
  const gx = (i) => -half + i * step;
  // terrain vertex normals (same as the terrain mesh's computeVertexNormals: area-weighted)
  const tn = new Float32Array(n * n * 3);
  {
    const add = (a, b, c) => {
      const ax = gx(a % n), ay = gx((a / n) | 0), bx = gx(b % n), by = gx((b / n) | 0), cx = gx(c % n), cy = gx((c / n) | 0);
      const az = h[(a / n) | 0][a % n], bz = h[(b / n) | 0][b % n], cz = h[(c / n) | 0][c % n];
      const ux = bx - ax, uy = by - ay, uz = bz - az, vx = cx - ax, vy = cy - ay, vz = cz - az;
      const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      for (const k of [a, b, c]) { tn[k * 3] += nx; tn[k * 3 + 1] += ny; tn[k * 3 + 2] += nz; }
    };
    for (let j = 0; j < n - 1; j++) for (let i = 0; i < n - 1; i++) { const a = j * n + i; add(a, a + 1, a + n + 1); add(a, a + n + 1, a + n); }
    for (let k = 0; k < n * n; k++) { const l = Math.hypot(tn[k * 3], tn[k * 3 + 1], tn[k * 3 + 2]) || 1; tn[k * 3] /= l; tn[k * 3 + 1] /= l; tn[k * 3 + 2] /= l; }
  }
  const vtx = (i, j) => ({ x: gx(i), y: gx(j), z: h[j][i], n: [tn[(j * n + i) * 3], tn[(j * n + i) * 3 + 1], tn[(j * n + i) * 3 + 2]] });
  // the two triangles of terrain cell (i, j), counter-clockwise in xy
  const cellTris = (i, j) => [[vtx(i, j), vtx(i + 1, j), vtx(i + 1, j + 1)], [vtx(i, j), vtx(i + 1, j + 1), vtx(i, j + 1)]];

  // distant-hills triangles, binned (only near the field; paint never goes further)
  const BIN = 25, LIM = 1400, NB = Math.ceil(2 * LIM / BIN), bins = new Map(), hillTris = [];
  if (hillsMesh) {
    hillsMesh.updateMatrixWorld(true);
    const g = hillsMesh.geometry, p = g.attributes.position, nr = g.attributes.normal, idx = g.index.array;
    const V = (k) => ({ x: p.getX(k), y: p.getY(k), z: p.getZ(k), n: [nr.getX(k), nr.getY(k), nr.getZ(k)] });
    for (let t = 0; t < idx.length; t += 3) {
      let a = V(idx[t]), b = V(idx[t + 1]), c = V(idx[t + 2]);
      const area = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
      if (Math.abs(area) < 1e-9) continue;
      if (area < 0) { const s = b; b = c; c = s; }
      const x0 = Math.min(a.x, b.x, c.x), x1 = Math.max(a.x, b.x, c.x), y0 = Math.min(a.y, b.y, c.y), y1 = Math.max(a.y, b.y, c.y);
      if (x1 < -LIM || x0 > LIM || y1 < -LIM || y0 > LIM) continue;
      const tri = [a, b, c]; tri.normalUp = true; const id = hillTris.push(tri) - 1;
      for (let bi = Math.max(0, Math.floor((x0 + LIM) / BIN)); bi <= Math.min(NB - 1, Math.floor((x1 + LIM) / BIN)); bi++)
        for (let bj = Math.max(0, Math.floor((y0 + LIM) / BIN)); bj <= Math.min(NB - 1, Math.floor((y1 + LIM) / BIN)); bj++) {
          const key = bj * NB + bi; let l = bins.get(key); if (!l) bins.set(key, l = []); l.push(id);
        }
    }
  }
  const hillCandidates = (x0, y0, x1, y1) => {
    const out = new Set();
    for (let bi = Math.max(0, Math.floor((x0 + LIM) / BIN)); bi <= Math.min(NB - 1, Math.floor((x1 + LIM) / BIN)); bi++)
      for (let bj = Math.max(0, Math.floor((y0 + LIM) / BIN)); bj <= Math.min(NB - 1, Math.floor((y1 + LIM) / BIN)); bj++) {
        const l = bins.get(bj * NB + bi); if (l) for (const id of l) out.add(id);
      }
    return [...out].map((id) => hillTris[id]);
  };

  const bary = (tri, x, y) => {
    const [a, b, c] = tri, den = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y);
    const l1 = ((b.y - c.y) * (x - c.x) + (c.x - b.x) * (y - c.y)) / den, l2 = ((c.y - a.y) * (x - c.x) + (a.x - c.x) * (y - c.y)) / den;
    return [l1, l2, 1 - l1 - l2];
  };
  const inside = Math.abs;
  const terrainZ = (x, y) => { // world.py terrain_z, exactly
    const u = THREE.MathUtils.clamp((x + half) / (2 * half) * (n - 1), 0, n - 1.000001), v = THREE.MathUtils.clamp((y + half) / (2 * half) * (n - 1), 0, n - 1.000001);
    const i = Math.floor(u), j = Math.floor(v), a = u - i, b = v - j;
    return a > b ? (1 - a) * h[j][i] + (a - b) * h[j][i + 1] + b * h[j + 1][i + 1] : (1 - b) * h[j][i] + (b - a) * h[j + 1][i] + a * h[j + 1][i + 1];
  };
  const triAt = (x, y) => {
    if (Math.max(inside(x), inside(y)) <= half) {
      const i = Math.min(n - 2, Math.floor((x + half) / step)), j = Math.min(n - 2, Math.floor((y + half) / step));
      for (const t of cellTris(i, j)) { const l = bary(t, x, y); if (Math.min(...l) >= -1e-7) return t; }
      return cellTris(i, j)[0];
    }
    for (const t of hillCandidates(x, y, x, y)) { const l = bary(t, x, y); if (Math.min(...l) >= -1e-7) return t; }
    return null;
  };
  // rendered ground height (== physics terrain_z inside +/-500 m)
  const heightAt = (x, y) => {
    if (Math.max(inside(x), inside(y)) <= half) return terrainZ(x, y);
    const t = triAt(x, y); if (!t) return terrainZ(x, y);
    const l = bary(t, x, y); return l[0] * t[0].z + l[1] * t[1].z + l[2] * t[2].z;
  };
  const normalAt = (x, y, out = new THREE.Vector3()) => {
    const t = triAt(x, y); if (!t) return out.set(0, 0, 1);
    const l = bary(t, x, y);
    return out.set(l[0] * t[0].n[0] + l[1] * t[1].n[0] + l[2] * t[2].n[0], l[0] * t[0].n[1] + l[1] * t[1].n[1] + l[2] * t[2].n[1], l[0] * t[0].n[2] + l[1] * t[1].n[2] + l[2] * t[2].n[2]).normalize();
  };
  const isFlat = (x, y) => Math.max(inside(x), inside(y)) <= FLAT;

  // ---- polygon clipping (Sutherland-Hodgman) against a convex CCW polygon ------------
  // polygon vertex: {x, y, a: Float32 attrs (uv etc.)}
  const lerpV = (p, q, t) => { const a = new Array(p.a.length); for (let k = 0; k < a.length; k++) a[k] = p.a[k] + (q.a[k] - p.a[k]) * t; return { x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t, a }; };
  function clip(poly, clipPts) {
    let out = poly;
    for (let e = 0; e < clipPts.length && out.length; e++) {
      const A = clipPts[e], B = clipPts[(e + 1) % clipPts.length], inp = out; out = [];
      const side = (p) => (B.x - A.x) * (p.y - A.y) - (B.y - A.y) * (p.x - A.x);
      for (let k = 0; k < inp.length; k++) {
        const P = inp[k], Q = inp[(k + 1) % inp.length], sp = side(P), sq = side(Q);
        if (sp >= 0) out.push(P);
        if ((sp >= 0) !== (sq >= 0)) out.push(lerpV(P, Q, sp / (sp - sq)));
      }
    }
    return out;
  }
  const area2 = (poly) => { let s = 0; for (let k = 0; k < poly.length; k++) { const p = poly[k], q = poly[(k + 1) % poly.length]; s += p.x * q.y - q.x * p.y; } return s; };

  // Drape a set of world-space source triangles onto the ground.
  // src: array of triangles [[{x,y,a}, {x,y,a}, {x,y,a}], ...] in their original winding.
  // mode 'full' drapes everywhere; 'flat' keeps only the part on the physics-flat floor.
  function drapeTriangles(src, { offset = 0.02, mode = 'full' } = {}) {
    const pos = [], nor = [], att = [];
    const emit = (poly, tri, flip) => {
      if (poly.length < 3 || Math.abs(area2(poly)) < 1e-8) return;
      const vz = (p) => { if (!tri) return [0, [0, 0, 1]]; const l = bary(tri, p.x, p.y); return [l[0] * tri[0].z + l[1] * tri[1].z + l[2] * tri[2].z, [0, 1, 2].map((d) => l[0] * tri[0].n[d] + l[1] * tri[1].n[d] + l[2] * tri[2].n[d])]; };
      const P = poly.map((p) => { const [z, nn] = vz(p); const L = Math.hypot(...nn) || 1; return { p, z: z + offset * (nn[2] / L > 0 ? 1 / Math.max(.5, nn[2] / L) : 1), n: nn.map((c) => c / L) }; });
      for (let k = 1; k < P.length - 1; k++) {
        const tri3 = flip ? [P[0], P[k + 1], P[k]] : [P[0], P[k], P[k + 1]];
        for (const q of tri3) { pos.push(q.p.x, q.p.y, q.z); nor.push(...q.n); att.push(...q.p.a); }
      }
    };
    const flatSq = [{ x: -FLAT, y: -FLAT }, { x: FLAT, y: -FLAT }, { x: FLAT, y: FLAT }, { x: -FLAT, y: FLAT }];
    for (const t of src) {
      let poly = t.map((p) => ({ x: p.x, y: p.y, a: p.a }));
      const flip = area2(poly) < 0; if (flip) poly = poly.reverse();
      const x0 = Math.min(...poly.map((p) => p.x)), x1 = Math.max(...poly.map((p) => p.x)), y0 = Math.min(...poly.map((p) => p.y)), y1 = Math.max(...poly.map((p) => p.y));
      // 1. the flat floor: one polygon, z = 0
      if (x1 > -FLAT && x0 < FLAT && y1 > -FLAT && y0 < FLAT) emit(clip(poly, flatSq), null, flip);
      if (mode === 'flat') continue;
      // 2. sloped physics terrain cells (outside the flat square, inside +/-500)
      const i0 = Math.max(0, Math.floor((x0 + half) / step)), i1 = Math.min(n - 2, Math.floor((x1 + half) / step));
      const j0 = Math.max(0, Math.floor((y0 + half) / step)), j1 = Math.min(n - 2, Math.floor((y1 + half) / step));
      if (x1 > -half && x0 < half && y1 > -half && y0 < half) for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
        if (i >= flatCell && i < n - 1 - flatCell && j >= flatCell && j < n - 1 - flatCell) continue;
        for (const ct of cellTris(i, j)) emit(clip(poly, ct), ct, flip);
      }
      // 3. visual backdrop outside +/-500 m: the distant-hills triangles
      if (x0 < -half || x1 > half || y0 < -half || y1 > half) for (const ht of hillCandidates(x0, y0, x1, y1)) emit(clip(poly, ht), ht, flip);
    }
    return { pos, nor, att };
  }

  // Replace a flat mesh's geometry with its draped copy (world space; transform reset).
  // Works for any mesh whose parent chain has identity transform (airfield / service-road groups).
  function drapeMesh(mesh, { offset = 0.02, mode = 'full' } = {}) {
    mesh.updateMatrixWorld(true);
    const g = mesh.geometry, p = g.attributes.position, uv = g.attributes.uv, col = g.attributes.color;
    const nA = (uv ? 2 : 0) + (col ? 3 : 0), v = new THREE.Vector3();
    const idx = g.index ? g.index.array : null, count = idx ? idx.length : p.count, src = [];
    const groups = g.groups.length ? g.groups : [{ start: 0, count, materialIndex: 0 }];
    const mk = (k) => { v.fromBufferAttribute(p, k).applyMatrix4(mesh.matrixWorld); const a = []; if (uv) a.push(uv.getX(k), uv.getY(k)); if (col) a.push(col.getX(k), col.getY(k), col.getZ(k)); return { x: v.x, y: v.y, a }; };
    for (let t = 0; t < count; t += 3) { const k = idx ? [idx[t], idx[t + 1], idx[t + 2]] : [t, t + 1, t + 2]; src.push(k.map(mk)); }
    const r = drapeTriangles(src, { offset, mode });
    const out = new THREE.BufferGeometry();
    out.setAttribute('position', new THREE.Float32BufferAttribute(r.pos, 3));
    out.setAttribute('normal', new THREE.Float32BufferAttribute(r.nor, 3));
    if (nA) {
      const m = r.att.length / nA, U = [], C = [];
      for (let k = 0; k < m; k++) { let o = k * nA; if (uv) { U.push(r.att[o], r.att[o + 1]); o += 2; } if (col) C.push(r.att[o], r.att[o + 1], r.att[o + 2]); }
      if (uv) out.setAttribute('uv', new THREE.Float32BufferAttribute(U, 2));
      if (col) out.setAttribute('color', new THREE.Float32BufferAttribute(C, 3));
    }
    void groups;
    out.computeBoundingBox(); out.computeBoundingSphere();
    g.dispose(); mesh.geometry = out;
    mesh.position.set(0, 0, 0); mesh.rotation.set(0, 0, 0); mesh.scale.set(1, 1, 1); mesh.updateMatrix();
    if (mesh.parent) { mesh.parent.updateMatrixWorld(true); }
    mesh.visible = r.pos.length > 0;
    return mesh;
  }

  // Make a draped decal depth-tested against the terrain/buildings without z-fighting.
  function decalDepth(material, units = -4) {
    for (const m of Array.isArray(material) ? material : [material]) {
      m.depthTest = true; m.depthWrite = false; m.polygonOffset = true; m.polygonOffsetFactor = -1.5; m.polygonOffsetUnits = units; m.needsUpdate = true;
    }
  }

  return { heightAt, normalAt, terrainZ, isFlat, drapeTriangles, drapeMesh, decalDepth, FLAT, half };
}
