// Consolidated Ricochet Lake (2000 x 1200 m) bathymetry, Vaderland surroundings,
// islands, whirlpools, dynamic hybrid free-surface water mesh, and craft visual.
// Shares exact meter coordinates & VTX-MLD-SI vertical datum with RicochetLakeWorld.
import {
  brushedMetalTexture,
  cautionSignTexture,
  concreteTextures,
  corrugatedTexture,
  volcanoBasaltTexture,
} from './textures.js?v=1';

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function buildVaderlandSign(THREE, x, y, zBase, facingYaw, title, lines, warning = true, scale = 1.0) {
  const pivot = new THREE.Group();
  pivot.position.set(x, y, zBase);
  pivot.rotation.z = facingYaw + Math.PI / 2;

  const pw = 3.2 * scale;
  const ph = 2.0 * scale;
  const postH = ph + 1.45 * scale;
  const postMat = new THREE.MeshStandardMaterial({ color: '#475569', roughness: 0.55, metalness: 0.6 });
  for (const sx of [-pw * 0.36, pw * 0.36]) {
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.08 * scale, 0.1 * scale, postH, 8), postMat);
    post.rotation.x = Math.PI / 2;
    post.position.set(sx, 0.08 * scale, postH * 0.5);
    post.castShadow = true;
    pivot.add(post);
  }

  const plate = new THREE.Mesh(
    new THREE.BoxGeometry(pw + 0.18 * scale, 0.1 * scale, ph + 0.18 * scale),
    new THREE.MeshStandardMaterial({ color: warning ? '#78350f' : '#1e293b', roughness: 0.7, metalness: 0.25 })
  );
  plate.position.set(0, 0.06 * scale, postH - ph * 0.52);
  plate.castShadow = true;
  pivot.add(plate);

  const tex = cautionSignTexture(title, lines, warning);
  const face = new THREE.Mesh(
    new THREE.PlaneGeometry(pw, ph),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 0.45, metalness: 0.08 })
  );
  face.rotation.x = Math.PI / 2;
  face.position.set(0, -0.005 * scale, postH - ph * 0.52);
  pivot.add(face);
  return pivot;
}

function makeWaterRippleNormalTexture(THREE) {
  const n = 64;
  const h = new Float32Array(n * n);
  for (let j = 0; j < n; j++) {
    const v = (j / n) * Math.PI * 2;
    for (let i = 0; i < n; i++) {
      const u = (i / n) * Math.PI * 2;
      h[j * n + i] =
        0.45 * Math.sin(2 * u + 3 * v) +
        0.30 * Math.cos(5 * u - 2 * v) +
        0.18 * Math.sin(7 * u + 5 * v) +
        0.07 * Math.cos(9 * u - 8 * v);
    }
  }
  const data = new Uint8Array(n * n * 4);
  for (let j = 0; j < n; j++) {
    const jm = (j - 1 + n) % n;
    const jp = (j + 1) % n;
    for (let i = 0; i < n; i++) {
      const im = (i - 1 + n) % n;
      const ip = (i + 1) % n;
      const dhdx = (h[j * n + ip] - h[j * n + im]) * 0.42;
      const dhdy = (h[jp * n + i] - h[jm * n + i]) * 0.42;
      const inv = 1.0 / Math.hypot(dhdx, dhdy, 1.0);
      const idx = (j * n + i) * 4;
      data[idx] = Math.round(((-dhdx * inv) * 0.5 + 0.5) * 255);
      data[idx + 1] = Math.round(((-dhdy * inv) * 0.5 + 0.5) * 255);
      data[idx + 2] = Math.round((inv * 0.5 + 0.5) * 255);
      data[idx + 3] = 255;
    }
  }
  const tex = new THREE.DataTexture(data, n, n, THREE.RGBAFormat);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.needsUpdate = true;
  return tex;
}

function makeLocalPatchAlphaTexture(THREE) {
  const n = 64;
  const data = new Uint8Array(n * n * 4);
  for (let j = 0; j < n; j++) {
    const y = (j / (n - 1)) * 2 - 1;
    const fy = Math.max(0, Math.min(1, (1 - Math.abs(y)) / 0.18));
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 2 - 1;
      const fx = Math.max(0, Math.min(1, (1 - Math.abs(x)) / 0.18));
      const edge = fx * fy;
      const smooth = edge * edge * (3 - 2 * edge);
      const a = Math.round(255 * smooth);
      const idx = (j * n + i) * 4;
      data[idx] = a;
      data[idx + 1] = a;
      data[idx + 2] = a;
      data[idx + 3] = 255;
    }
  }
  const tex = new THREE.DataTexture(data, n, n, THREE.RGBAFormat);
  tex.needsUpdate = true;
  return tex;
}

function buildWhirlpoolVisual(THREE, wp, wl) {
  const group = new THREE.Group();
  group.name = `whirlpool_${wp.id}`;
  group.position.set(wp.x, wp.y, wl);

  const nr = 22;
  const nt = 44;
  const rInner = 1.6;
  const rOuter = Math.max(wp.r_influence_m || 85, rInner + 10);
  const positions = new Float32Array((nr + 1) * (nt + 1) * 3);
  const colors = new Float32Array((nr + 1) * (nt + 1) * 3);
  const radialMeta = new Float32Array((nr + 1) * (nt + 1) * 2);
  const indices = [];

  for (let ir = 0; ir <= nr; ir++) {
    const fr = ir / nr;
    // Quadratic clustering near the throat so the funnel wall is crisp
    const r = rInner + (rOuter - rInner) * Math.pow(fr, 1.45);
    for (let it = 0; it <= nt; it++) {
      const th = (it / nt) * Math.PI * 2;
      const idx = ir * (nt + 1) + it;
      positions[idx * 3] = r * Math.cos(th);
      positions[idx * 3 + 1] = r * Math.sin(th);
      positions[idx * 3 + 2] = 0.0;
      radialMeta[idx * 2] = r;
      radialMeta[idx * 2 + 1] = th;
      const coreMix = Math.exp(-r / Math.max(6, wp.r_core_m * 0.9));
      colors[idx * 3] = 0.05 + 0.45 * Math.exp(-Math.pow((r - wp.r_core_m * 0.9) / 14, 2)) - 0.03 * coreMix;
      colors[idx * 3 + 1] = 0.24 + 0.52 * Math.exp(-Math.pow((r - wp.r_core_m * 0.9) / 16, 2));
      colors[idx * 3 + 2] = 0.34 + 0.56 * Math.exp(-Math.pow((r - wp.r_core_m * 0.9) / 18, 2));
    }
  }
  for (let ir = 0; ir < nr; ir++) {
    for (let it = 0; it < nt; it++) {
      const a = ir * (nt + 1) + it;
      const b = a + nt + 1;
      indices.push(a, b, b + 1, a, b + 1, a + 1);
    }
  }

  const funnelGeo = new THREE.BufferGeometry();
  funnelGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  funnelGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  funnelGeo.setIndex(indices);

  const funnelMat = new THREE.MeshStandardMaterial({
    vertexColors: true,
    roughness: 0.18,
    metalness: 0.22,
    transparent: true,
    opacity: 0.86,
    side: THREE.DoubleSide,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
  });
  const funnelMesh = new THREE.Mesh(funnelGeo, funnelMat);
  funnelMesh.renderOrder = 2;
  group.add(funnelMesh);

  // Rotating spiral foam arms inside the throat
  const foamGroup = new THREE.Group();
  for (let arm = 0; arm < 3; arm++) {
    const pts = [];
    const baseA = (arm / 3) * Math.PI * 2;
    for (let k = 0; k <= 30; k++) {
      const t = k / 30;
      const rr = Math.max(2.2, (wp.r_core_m * 2.1) * (1 - 0.84 * t));
      const ang = baseA + (wp.spin || 1) * t * Math.PI * 2.6;
      const ratio = rr / Math.max(1.0, wp.r_core_m);
      const dropMag = Math.abs(Number(wp.core_drop_m ?? 1.45));
      const drop = -dropMag * ((1 - Math.exp(-(ratio * ratio))) / Math.max(ratio * ratio, 0.28));
      pts.push(new THREE.Vector3(rr * Math.cos(ang), rr * Math.sin(ang), drop * 0.72 + 0.08));
    }
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: '#c8f5ff', transparent: true, opacity: 0.78 })
    );
    foamGroup.add(line);
  }
  group.add(foamGroup);

  // Perimeter danger circle
  const ringPts = [];
  for (let k = 0; k <= 48; k++) {
    const a = (k / 48) * Math.PI * 2;
    ringPts.push(new THREE.Vector3(rOuter * Math.cos(a), rOuter * Math.sin(a), 0.14));
  }
  const perimRing = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(ringPts),
    new THREE.LineBasicMaterial({ color: '#f59e0b', transparent: true, opacity: 0.6 })
  );
  group.add(perimRing);

  return {
    group,
    funnelGeo,
    funnelMat,
    foamGroup,
    perimRing,
    radialMeta,
    nr,
    nt,
    spec: wp,
    angle: 0,
    lastIntensity: -1,
  };
}

function buildLocalWaterPatchMesh(THREE, wl, rippleNormalTex) {
  const nx = 65;
  const ny = 65;
  const positions = new Float32Array(nx * ny * 3);
  const colors = new Float32Array(nx * ny * 3);
  const uvs = new Float32Array(nx * ny * 2);
  const indices = [];

  for (let j = 0; j < ny; j++) {
    const fv = j / (ny - 1);
    for (let i = 0; i < nx; i++) {
      const fu = i / (nx - 1);
      const k = j * nx + i;
      positions[k * 3] = (fu - 0.5) * 128.0;
      positions[k * 3 + 1] = (fv - 0.5) * 128.0;
      positions[k * 3 + 2] = wl;
      uvs[k * 2] = fu;
      uvs[k * 2 + 1] = fv;
      colors[k * 3] = 0.055;
      colors[k * 3 + 1] = 0.415;
      colors[k * 3 + 2] = 0.553;
    }
  }
  for (let j = 0; j < ny - 1; j++) {
    for (let i = 0; i < nx - 1; i++) {
      const a = j * nx + i;
      indices.push(a, a + 1, a + nx + 1, a, a + nx + 1, a + nx);
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
  geo.setIndex(indices);
  geo.computeVertexNormals();

  const mat = new THREE.MeshStandardMaterial({
    color: '#ffffff',
    vertexColors: true,
    normalMap: rippleNormalTex,
    normalScale: new THREE.Vector2(0.24, 0.24),
    alphaMap: makeLocalPatchAlphaTexture(THREE),
    emissive: '#041f2d',
    emissiveIntensity: 0.28,
    roughness: 0.14,
    metalness: 0.26,
    transparent: true,
    opacity: 0.88,
    side: THREE.DoubleSide,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.name = 'ricochet_local_water_patch';
  mesh.receiveShadow = true;
  mesh.visible = false;
  mesh.renderOrder = 2;
  return { mesh, geo, mat, nx, ny };
}

export function buildRicochetLake(THREE, world) {
  const root = new THREE.Group();
  root.name = 'ricochet_lake_world';

  const nx = world.nx || world.n || 401;
  const ny = world.ny || nx;
  const hx = world.half_x || world.half_m || 1000;
  const hy = world.half_y || world.half_m || 600;
  const h = world.heights_m || world.heights;
  const wl = Number(world.water_level ?? 0);

  // 1. Bathymetry & shoreline terrain mesh indexed identically to RicochetLakeWorld (j=0..ny-1, i=0..nx-1)
  const stride = (nx > 220) ? 2 : 1;
  const sx = Math.floor((nx - 1) / stride) + 1;
  const sy = Math.floor((ny - 1) / stride) + 1;
  const positions = new Float32Array(sx * sy * 3);
  const colors = new Float32Array(sx * sy * 3);
  const col = new THREE.Color();

  for (let jj = 0; jj < sy; jj++) {
    const j = Math.min(ny - 1, jj * stride);
    const y = -hy + (j / (ny - 1)) * 2 * hy;
    for (let ii = 0; ii < sx; ii++) {
      const i = Math.min(nx - 1, ii * stride);
      const x = -hx + (i / (nx - 1)) * 2 * hx;
      const z = h[j][i];
      const idx = (jj * sx + ii) * 3;
      positions[idx] = x;
      positions[idx + 1] = y;
      positions[idx + 2] = z;

      if (z < -6.0) {
        col.setRGB(0.08, 0.17, 0.24); // Deep basin silt
      } else if (z < -1.0) {
        const t = (z + 6.0) / 5.0;
        col.setRGB(0.10 + 0.18 * t, 0.20 + 0.18 * t, 0.24 + 0.06 * t); // Shallow sand shelf
      } else if (z <= wl + 0.35) {
        col.setRGB(0.56, 0.50, 0.36); // Wet/dry sand & slipway apron
      } else {
        const t = Math.min(1, (z - 0.35) / 14.0);
        col.setRGB(0.22 - 0.04 * t, 0.36 + 0.10 * t, 0.20 - 0.04 * t); // Vegetated shoreline banks
      }
      colors[idx] = col.r;
      colors[idx + 1] = col.g;
      colors[idx + 2] = col.b;
    }
  }

  const indices = [];
  for (let jj = 0; jj < sy - 1; jj++) {
    for (let ii = 0; ii < sx - 1; ii++) {
      const a = jj * sx + ii;
      const b = a + 1;
      const c = a + sx;
      const d = c + 1;
      indices.push(a, b, d, a, d, c);
    }
  }

  const bedGeo = new THREE.BufferGeometry();
  bedGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  bedGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  bedGeo.setIndex(indices);
  bedGeo.computeVertexNormals();
  const bedMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.92, metalness: 0.02 });
  const bedMesh = new THREE.Mesh(bedGeo, bedMat);
  bedMesh.receiveShadow = true;
  bedMesh.name = 'lake_bathymetry';
  root.add(bedMesh);

  // 2. Collidable Marina Quay, Finger Piers, Headwalk, Breakwater, and Beacon
  for (const s of world.structures || []) {
    const [cx, cy, cz] = s.center;
    const [ex, ey, ez] = s.half_extents;
    const geo = new THREE.BoxGeometry(ex * 2, ey * 2, ez * 2);
    const mat = new THREE.MeshStandardMaterial({
      color: s.color || '#6a727c',
      roughness: s.kind === 'pier' ? 0.78 : 0.88,
      metalness: s.kind === 'beacon' ? 0.35 : 0.08,
    });
    const m = new THREE.Mesh(geo, mat);
    m.position.set(cx, cy, cz);
    m.rotation.z = ((s.yaw_deg || 0) * Math.PI) / 180;
    m.castShadow = true;
    m.receiveShadow = true;
    m.name = s.id;
    root.add(m);
  }

  // 3. Physical Mooring & Channel Buoys + Accel/Turning Markers
  for (const b of world.buoys || []) {
    const r = b.radius_m || 0.75;
    const bh = b.height_m || 1.4;
    const g = new THREE.Group();
    g.name = `buoy_${b.id}`;
    g.position.set(b.x, b.y, wl + 0.15);
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(r * 0.75, r, bh, 14),
      new THREE.MeshStandardMaterial({ color: b.color || '#f59e0b', roughness: 0.45, metalness: 0.15 })
    );
    body.rotation.x = Math.PI / 2; // Cylinder defaults to Y-up in Three.js -> rotate to Z-up
    body.castShadow = true;
    g.add(body);
    root.add(g);
  }

  // 4. Concrete Launch & Recovery Ramp Aprons (Flush with terrain ramp slope)
  for (const r of world.ramps || []) {
    const len = Math.abs(r.x_toe - r.x_dry);
    const midX = 0.5 * (r.x_toe + r.x_dry);
    const zDry = 2.4;
    const dz = r.slope_ratio * len;
    const slopeAng = Math.atan2(dz, len);
    const ramp = new THREE.Mesh(
      new THREE.BoxGeometry(len, r.width_m, 0.25),
      new THREE.MeshStandardMaterial({ color: '#8e969e', roughness: 0.85, metalness: 0.05 })
    );
    ramp.position.set(midX, r.y_center, zDry - 0.5 * dz + 0.06);
    ramp.rotation.y = slopeAng;
    ramp.receiveShadow = true;
    ramp.name = r.id;
    root.add(ramp);
  }

  // 5. Dynamic Hybrid Free-Surface Water Mesh (driven directly by server water_frame)
  const wnx = 41;
  const wny = 25;
  const wPos = new Float32Array(wnx * wny * 3);
  const wUvs = new Float32Array(wnx * wny * 2);
  for (let j = 0; j < wny; j++) {
    const y = -hy + (j / (wny - 1)) * 2 * hy;
    for (let i = 0; i < wnx; i++) {
      const x = -hx + (i / (wnx - 1)) * 2 * hx;
      const k = j * wnx + i;
      const idx = k * 3;
      wPos[idx] = x;
      wPos[idx + 1] = y;
      wPos[idx + 2] = wl;
      wUvs[k * 2] = (x + hx) / 16.0;
      wUvs[k * 2 + 1] = (y + hy) / 16.0;
    }
  }
  const wIdx = [];
  for (let j = 0; j < wny - 1; j++) {
    for (let i = 0; i < wnx - 1; i++) {
      const a = j * wnx + i;
      wIdx.push(a, a + 1, a + wnx + 1, a, a + wnx + 1, a + wnx);
    }
  }
  const wGeo = new THREE.BufferGeometry();
  wGeo.setAttribute('position', new THREE.BufferAttribute(wPos, 3));
  wGeo.setAttribute('uv', new THREE.BufferAttribute(wUvs, 2));
  const wColors = new Float32Array(wnx * wny * 3);
  for (let i = 0; i < wnx * wny; i++) {
    wColors[i * 3] = 0.055;
    wColors[i * 3 + 1] = 0.415;
    wColors[i * 3 + 2] = 0.553;
  }
  wGeo.setAttribute('color', new THREE.BufferAttribute(wColors, 3));
  wGeo.setIndex(wIdx);
  wGeo.computeVertexNormals();
  const rippleNormalTex = makeWaterRippleNormalTexture(THREE);
  const wMat = new THREE.MeshStandardMaterial({
    color: '#ffffff',
    vertexColors: true,
    normalMap: rippleNormalTex,
    normalScale: new THREE.Vector2(0.18, 0.18),
    emissive: '#041f2d',
    emissiveIntensity: 0.3,
    roughness: 0.14,
    metalness: 0.28,
    transparent: true,
    opacity: 0.8,
    side: THREE.DoubleSide,
  });
  const waterMesh = new THREE.Mesh(wGeo, wMat);
  waterMesh.name = 'ricochet_water_surface';
  waterMesh.receiveShadow = true;
  root.add(waterMesh);

  // 6. Test Zone Floating / Shoreline Perimeter Rings
  for (const z of world.zones || []) {
    const pts = [];
    const zz = wl + 0.12;
    if (z.kind === 'rect') {
      pts.push(
        new THREE.Vector3(z.x_min, z.y_min, zz),
        new THREE.Vector3(z.x_max, z.y_min, zz),
        new THREE.Vector3(z.x_max, z.y_max, zz),
        new THREE.Vector3(z.x_min, z.y_max, zz),
        new THREE.Vector3(z.x_min, z.y_min, zz)
      );
    } else if (z.kind === 'circle' || z.kind === 'ellipse') {
      const rx = z.r || z.rx;
      const ry = z.r || z.ry;
      for (let k = 0; k <= 48; k++) {
        const a = (k / 48) * Math.PI * 2;
        pts.push(new THREE.Vector3(z.cx + rx * Math.cos(a), z.cy + ry * Math.sin(a), zz));
      }
    }
    if (pts.length) {
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: z.color || '#38bdf8', transparent: true, opacity: 0.65 })
      );
      line.name = `zone_${z.id}`;
      root.add(line);
    }
  }

  // 7. Vaderland Basalt Rim Crags, Caldera Fissures & Perimeter Navigation Masts
  const rand = mulberry32(41031);
  const basaltTex = volcanoBasaltTexture();
  basaltTex.repeat.set(6, 6);
  const basaltMat = new THREE.MeshStandardMaterial({
    map: basaltTex,
    color: '#46413e',
    roughness: 0.94,
    metalness: 0.04,
  });
  const rimGroup = new THREE.Group();
  rimGroup.name = 'vaderland_caldera_rim';
  const cragCount = 26;
  for (let i = 0; i < cragCount; i++) {
    const ang = (i / cragCount) * Math.PI * 2 + (rand() - 0.5) * 0.14;
    const rx = (hx + 150) + rand() * 240;
    const ry = (hy + 120) + rand() * 190;
    const cx = Math.cos(ang) * rx;
    const cy = Math.sin(ang) * ry;
    const baseR = 55 + rand() * 85;
    const peakH = 26 + rand() * 68;
    const peak = new THREE.Mesh(
      new THREE.CylinderGeometry(baseR * (0.12 + rand() * 0.18), baseR, peakH, 7),
      basaltMat
    );
    peak.rotation.x = Math.PI / 2;
    peak.rotation.y = rand() * Math.PI * 2;
    peak.position.set(cx, cy, peakH * 0.42 - 2.0);
    peak.castShadow = true;
    peak.receiveShadow = true;
    rimGroup.add(peak);

    if (i % 8 === 2) {
      const seam = new THREE.Mesh(
        new THREE.CircleGeometry(baseR * 0.34, 8),
        new THREE.MeshStandardMaterial({
          color: '#381206',
          emissive: '#c83e0b',
          emissiveIntensity: 0.55,
          roughness: 0.85,
        })
      );
      seam.position.set(cx * 0.96, cy * 0.96, 1.5);
      rimGroup.add(seam);
    }
  }
  const mastMat = new THREE.MeshStandardMaterial({ color: '#94a3b8', roughness: 0.5, metalness: 0.6 });
  const beaconMat = new THREE.MeshStandardMaterial({
    color: '#f59e0b',
    emissive: '#f59e0b',
    emissiveIntensity: 1.4,
    roughness: 0.3,
  });
  for (const [mx, my] of [[-1035, -625], [1035, -625], [1035, 625], [-1035, 625]]) {
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.38, 18.0, 8), mastMat);
    pole.rotation.x = Math.PI / 2;
    pole.position.set(mx, my, 10.5);
    rimGroup.add(pole);
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.65, 10, 10), beaconMat);
    bulb.position.set(mx, my, 19.8);
    rimGroup.add(bulb);
  }
  root.add(rimGroup);

  // 8. Vaderland Dockside Gantry Crane, Telemetry Winch Shed & Caution Signs (on solid service_quay_wall top z=1.55 & slipway crest)
  const dockGroup = new THREE.Group();
  dockGroup.name = 'vaderland_dock_yard';
  const conc = concreteTextures();
  const metalTex = brushedMetalTexture();
  const shedTex = corrugatedTexture('#232e39', '#324150');

  // Apron topping service_quay_wall (center [-845, -242.5], half [18, 95], top z = +1.55m)
  const apron = new THREE.Mesh(
    new THREE.BoxGeometry(30, 148, 0.22),
    new THREE.MeshStandardMaterial({ map: conc.map, roughnessMap: conc.rough, roughness: 0.88, metalness: 0.04 })
  );
  apron.position.set(-846, -240, 1.56);
  apron.receiveShadow = true;
  dockGroup.add(apron);

  // Gantry crane frame perched on service_quay_wall north corner adjacent to slipway
  const gantrySteel = new THREE.MeshStandardMaterial({ map: metalTex, color: '#cbd5e1', roughness: 0.4, metalness: 0.72 });
  const hazardYellow = new THREE.MeshStandardMaterial({ color: '#eab308', roughness: 0.45, metalness: 0.35 });
  for (const gx of [-847, -835]) {
    for (const gy of [-124.0, -104.0]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.55, 9.2), gantrySteel);
      leg.position.set(gx, gy, 2.35 + 4.6);
      leg.castShadow = true;
      dockGroup.add(leg);
    }
    const header = new THREE.Mesh(new THREE.BoxGeometry(0.7, 21.5, 0.8), hazardYellow);
    header.position.set(gx, -114, 11.4);
    header.castShadow = true;
    dockGroup.add(header);
  }
  const trolley = new THREE.Mesh(new THREE.BoxGeometry(13.2, 1.4, 0.9), hazardYellow);
  trolley.position.set(-841, -114, 12.1);
  dockGroup.add(trolley);
  const hookCable = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 4.0, 6), gantrySteel);
  hookCable.rotation.x = Math.PI / 2;
  hookCable.position.set(-837, -114, 9.7);
  dockGroup.add(hookCable);

  // Vaderland Telemetry & Winch Control Shed solidly on service_quay_wall (top z = +1.55m)
  const shed = new THREE.Mesh(
    new THREE.BoxGeometry(11.5, 8.5, 4.4),
    new THREE.MeshStandardMaterial({ map: shedTex, roughness: 0.62, metalness: 0.42 })
  );
  shed.position.set(-849, -182, 1.67 + 2.2);
  shed.castShadow = true;
  shed.receiveShadow = true;
  dockGroup.add(shed);
  const obsWindow = new THREE.Mesh(
    new THREE.PlaneGeometry(5.6, 1.5),
    new THREE.MeshStandardMaterial({ color: '#93c5fd', emissive: '#38bdf8', emissiveIntensity: 0.45, roughness: 0.15 })
  );
  obsWindow.rotation.x = Math.PI / 2;
  obsWindow.rotation.y = Math.PI / 2;
  obsWindow.position.set(-843.2, -182, 4.3);
  dockGroup.add(obsWindow);

  // Vaderland engineering signs on solid quay & slipway shoulder facing east (+X)
  dockGroup.add(buildVaderlandSign(
    THREE,
    -832,
    -126,
    2.25,
    0,
    'VADERLAND SLIPWAY #1',
    ['CHECK WATERTIGHT SEAL BEFORE LAUNCH', 'UNSEALED HULLS SINK (AS ADVERTISED)'],
    true,
    1.15
  ));
  dockGroup.add(buildVaderlandSign(
    THREE,
    -830,
    -245,
    1.67,
    0,
    'RICOCHET QUAY BERTHS',
    ['MAX APPROACH SPEED 4 KNOTS', 'BALLAST PINS LOCKED PRIOR TO PLANING'],
    false,
    1.15
  ));
  root.add(dockGroup);

  // 9. Archipelago Islands: Basalt Boulders, Solar Weather Masts & Vaderland Signs
  const islandGroup = new THREE.Group();
  islandGroup.name = 'ricochet_islands';
  const islLightMat = new THREE.MeshStandardMaterial({
    color: '#34d399',
    emissive: '#10b981',
    emissiveIntensity: 1.35,
    roughness: 0.25,
  });
  for (let idx = 0; idx < (world.islands || []).length; idx++) {
    const isl = world.islands[idx];
    const peakZ = Math.max(1.0, Number(isl.z_peak_actual_m ?? isl.peak_m ?? 4.0));
    const rIsl = Math.max(14, Number(isl.radius_m || 45));
    for (let b = 0; b < 7; b++) {
      const a = (b / 7) * Math.PI * 2 + idx * 0.7;
      const dist = (0.14 + (b % 3) * 0.13) * rIsl;
      const br = 2.4 + (b % 3) * 1.6;
      const rock = new THREE.Mesh(
        new THREE.DodecahedronGeometry(br, 0),
        basaltMat
      );
      rock.scale.set(1.3, 1.05, 0.72);
      rock.position.set(
        isl.x + dist * Math.cos(a),
        isl.y + dist * Math.sin(a),
        Math.max(wl + 0.3, peakZ * (0.55 - 0.05 * (b % 3)))
      );
      rock.rotation.set(rand() * 2, rand() * 2, rand() * 2);
      rock.castShadow = true;
      rock.receiveShadow = true;
      islandGroup.add(rock);
    }
    // Solar navigation cairn mast at peak
    const mastH = 3.8;
    const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.18, mastH, 8), mastMat);
    mast.rotation.x = Math.PI / 2;
    mast.position.set(isl.x, isl.y, peakZ + mastH * 0.45);
    islandGroup.add(mast);
    const lantern = new THREE.Mesh(new THREE.SphereGeometry(0.35, 10, 10), islLightMat);
    lantern.position.set(isl.x, isl.y, peakZ + mastH * 0.96);
    islandGroup.add(lantern);

    // Vaderland humorous/practical island signboard facing south (-Y)
    const signZ = Math.max(wl + 0.65, peakZ * 0.42);
    islandGroup.add(buildVaderlandSign(
      THREE,
      isl.x,
      isl.y - rIsl * 0.42,
      signZ,
      -Math.PI / 2,
      isl.sign_title || isl.name || 'VADERLAND ATOLL',
      Array.isArray(isl.sign_lines) ? isl.sign_lines : ['VOLCANIC BASALT', 'DO NOT BEACH AT 40 KTS'],
      idx !== 1,
      1.3
    ));
  }
  root.add(islandGroup);

  // 10. Dynamic Rotating Whirlpool Vortex Funnels, Perimeter Spars & Local Kelvin Wake
  const whirlpoolGroups = [];
  const sparMat = new THREE.MeshStandardMaterial({ color: '#f97316', roughness: 0.45, metalness: 0.18 });
  for (const wp of world.whirlpools || []) {
    const wpVis = buildWhirlpoolVisual(THREE, wp, wl);
    root.add(wpVis.group);
    whirlpoolGroups.push(wpVis);

    // Floating warning spar post just outside whirlpool influence perimeter
    const sparX = wp.x - (wp.r_influence_m + 18.0);
    const sparY = wp.y;
    const sparFloat = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.9, 2.2, 12), sparMat);
    sparFloat.rotation.x = Math.PI / 2;
    sparFloat.position.set(sparX, sparY, wl + 0.3);
    root.add(sparFloat);
    root.add(buildVaderlandSign(
      THREE,
      sparX,
      sparY,
      wl + 1.1,
      Math.PI,
      'VORTEX HAZARD',
      [wp.name || wp.id, wp.warning || `SWIRL ${wp.max_swirl_mps} m/s · STAY CLEAR`],
      true,
      1.15
    ));
  }

  const localPatchData = buildLocalWaterPatchMesh(THREE, wl, rippleNormalTex);
  root.add(localPatchData.mesh);

  waterMesh.userData = {
    nx: wnx,
    ny: wny,
    hx,
    hy,
    waterLevel: wl,
    whirlpoolGroups,
    localPatchData,
    rippleNormalTex,
    lastWaterFrame: null,
  };

  return { group: root, waterMesh };
}

function _applyWhirlpoolDeform(vis, intensity, enabled) {
  vis.group.visible = Boolean(enabled && intensity > 0.02);
  if (!vis.group.visible) return;
  if (Math.abs(vis.lastIntensity - intensity) < 0.01) return;
  vis.lastIntensity = intensity;
  const { funnelGeo, radialMeta, spec, nr, nt } = vis;
  const pos = funnelGeo.attributes.position;
  const rc = Math.max(1.0, Number(spec.r_core_m || 24.0));
  const dropAmp = intensity * Math.abs(Number(spec.core_drop_m ?? 1.45));
  const spin = Number(spec.spin || 1);
  const count = (nr + 1) * (nt + 1);
  for (let i = 0; i < count; i++) {
    const r = radialMeta[i * 2];
    const th = radialMeta[i * 2 + 1];
    const rRatio = r / rc;
    const r2 = Math.max(rRatio * rRatio, 0.25);
    const baseDrop = -dropAmp * ((1.0 - Math.exp(-r2)) / r2);
    const spiral = 0.08 * intensity * Math.exp(-0.4 * rRatio) * Math.sin(4.0 * th - spin * 5.2 * Math.log(1.0 + rRatio));
    pos.setZ(i, baseDrop + spiral);
  }
  pos.needsUpdate = true;
  funnelGeo.computeVertexNormals();
  vis.funnelMat.opacity = Math.min(0.92, 0.55 + 0.3 * Math.min(1.5, intensity));
  vis.foamGroup.scale.set(1, 1, Math.min(1.8, Math.max(0.25, intensity)));
}

function _updateDynamicOverlays(waterMesh) {
  const ud = waterMesh?.userData;
  if (!ud) return;
  const wf = ud.lastWaterFrame;
  const wc = wf?.water_config || {};
  const wl = Number(wf?.water_level_m ?? ud.waterLevel ?? 0);
  const simT = Number(wf?.t_s ?? 0);

  // Deform & deterministically orient 3D whirlpool funnels strictly from solver t_s
  const wpEnabled = wc.whirlpools_enabled !== false;
  const wpInt = Number(wc.whirlpool_intensity ?? 1.0);
  for (const vis of ud.whirlpoolGroups || []) {
    vis.group.position.z = wl;
    _applyWhirlpoolDeform(vis, wpInt, wpEnabled);
    if (vis.group.visible) {
      const spinDir = Number(vis.spec.spin || 1);
      const omega = spinDir * (0.45 + 0.55 * Math.min(2.0, wpInt));
      vis.group.rotation.z = omega * simT;
      vis.foamGroup.rotation.z = -0.35 * omega * simT;
    }
  }
}

export function animateRicochetWater(waterMesh, _truth = null, _dt = 0, _running = true) {
  _updateDynamicOverlays(waterMesh);
}

export function updateWaterSurface(waterMesh, waterFrame) {
  if (!waterMesh || !waterFrame || !Array.isArray(waterFrame.elevation_m)) return;
  const grid = waterFrame.elevation_m;
  const ny = waterFrame.ny || grid.length;
  const nx = waterFrame.nx || (grid[0] ? grid[0].length : 0);
  const pos = waterMesh.geometry.attributes.position;
  const col = waterMesh.geometry.attributes.color;
  if (!nx || !ny || pos.count !== nx * ny) return;

  const wl = Number(waterFrame.water_level_m ?? 0);
  const simT = Number(waterFrame.t_s ?? 0);
  const { x_min_m, x_max_m, y_min_m, y_max_m } = waterFrame;
  for (let j = 0; j < ny; j++) {
    const y = y_min_m + (j / Math.max(1, ny - 1)) * (y_max_m - y_min_m);
    const row = grid[j];
    for (let i = 0; i < nx; i++) {
      const x = x_min_m + (i / Math.max(1, nx - 1)) * (x_max_m - x_min_m);
      const z = Number(row[i]);
      const k = j * nx + i;
      pos.setXYZ(k, x, y, z);
      if (col) {
        const dz = z - wl;
        if (dz >= 0) {
          const crest = Math.min(1.0, dz / 0.35);
          col.setXYZ(k, 0.055 + 0.22 * crest, 0.415 + 0.32 * crest, 0.553 + 0.28 * crest);
        } else {
          const trough = Math.min(1.0, -dz / 0.65);
          col.setXYZ(k, 0.055 - 0.04 * trough, 0.415 - 0.24 * trough, 0.553 - 0.26 * trough);
        }
      }
    }
  }
  pos.needsUpdate = true;
  if (col) col.needsUpdate = true;
  waterMesh.geometry.computeVertexNormals();

  // Craft-centered high-resolution SWE + wave free-surface patch driven strictly from server solver grid
  const lpd = waterMesh.userData?.localPatchData;
  const lp = waterFrame.local_patch;
  let meanU = 0;
  let meanV = 0;
  let velSamples = 0;
  if (lpd && lp && Array.isArray(lp.elevation_m)) {
    const lpGrid = lp.elevation_m;
    const lpDepth = Array.isArray(lp.depth_m) ? lp.depth_m : null;
    const lpU = Array.isArray(lp.u_mps) ? lp.u_mps : null;
    const lpV = Array.isArray(lp.v_mps) ? lp.v_mps : null;
    const lpNy = lp.ny || lpGrid.length;
    const lpNx = lp.nx || (lpGrid[0] ? lpGrid[0].length : 0);
    const lpPos = lpd.geo.attributes.position;
    const lpCol = lpd.geo.attributes.color;
    const xMin = lp.x_min_m ?? (lp.center_x_m != null && lp.half_extent_m != null ? lp.center_x_m - lp.half_extent_m : null);
    const xMax = lp.x_max_m ?? (lp.center_x_m != null && lp.half_extent_m != null ? lp.center_x_m + lp.half_extent_m : null);
    const yMin = lp.y_min_m ?? (lp.center_y_m != null && lp.half_extent_m != null ? lp.center_y_m - lp.half_extent_m : null);
    const yMax = lp.y_max_m ?? (lp.center_y_m != null && lp.half_extent_m != null ? lp.center_y_m + lp.half_extent_m : null);
    if (lpNx > 1 && lpNy > 1 && lpPos.count === lpNx * lpNy && xMin != null && xMax != null && yMin != null && yMax != null) {
      for (let j = 0; j < lpNy; j++) {
        const y = yMin + (j / (lpNy - 1)) * (yMax - yMin);
        const zRow = lpGrid[j];
        const dRow = lpDepth ? lpDepth[j] : null;
        const uRow = lpU ? lpU[j] : null;
        const vRow = lpV ? lpV[j] : null;
        for (let i = 0; i < lpNx; i++) {
          const x = xMin + (i / (lpNx - 1)) * (xMax - xMin);
          const z = Number(zRow[i]);
          const depth = dRow ? Number(dRow[i]) : 2.0;
          const u = uRow ? Number(uRow[i]) : 0.0;
          const v = vRow ? Number(vRow[i]) : 0.0;
          meanU += u;
          meanV += v;
          velSamples += 1;
          const k = j * lpNx + i;
          lpPos.setXYZ(k, x, y, z);
          const dz = z - wl;
          const speed = Math.hypot(u, v);
          const foam = Math.min(1.0, Math.max(0.0, dz / 0.25) * 0.65 + Math.max(0.0, speed - 0.5) * 0.25);
          const shallow = depth < 1.2 ? Math.min(1.0, (1.2 - depth) / 1.2) * 0.35 : 0.0;
          lpCol.setXYZ(
            k,
            Math.min(1.0, 0.06 + 0.55 * foam + 0.18 * shallow),
            Math.min(1.0, 0.44 + 0.44 * foam + 0.14 * shallow),
            Math.min(1.0, 0.58 + 0.36 * foam - 0.10 * shallow)
          );
        }
      }
      lpPos.needsUpdate = true;
      lpCol.needsUpdate = true;
      lpd.geo.computeVertexNormals();
      lpd.mesh.visible = true;
    } else {
      lpd.mesh.visible = false;
    }
  } else if (lpd) {
    lpd.mesh.visible = false;
  }

  const rippleTex = waterMesh.userData?.rippleNormalTex;
  if (rippleTex) {
    if (velSamples > 0) {
      meanU /= velSamples;
      meanV /= velSamples;
    } else {
      const wc = waterFrame.water_config || {};
      const cs = Number(wc.current_speed_mps ?? 0);
      const cRad = (Number(wc.current_direction_deg ?? 0) * Math.PI) / 180;
      meanU = cs * Math.cos(cRad);
      meanV = cs * Math.sin(cRad);
    }
    rippleTex.offset.set(((meanU * simT) / 16.0) % 1.0, ((meanV * simT) / 16.0) % 1.0);
  }

  waterMesh.userData.lastWaterFrame = waterFrame;
  _updateDynamicOverlays(waterMesh);
}

export function buildRicochetVisual(THREE, modelPayload) {
  const root = new THREE.Group();
  root.name = 'ricochet_craft_visual';
  const bodies = new Map();
  const ensureBody = (bodyName) => {
    if (!bodies.has(bodyName)) {
      const g = new THREE.Group();
      g.name = bodyName;
      g.userData.physical_body = bodyName;
      root.add(g);
      bodies.set(bodyName, g);
    }
    return bodies.get(bodyName);
  };

  // Exact physics-pinned triangle meshes from MuJoCo/hydro bundle with PBR material roles & seam-crisp paint
  const makeRoleMat = (mSpec, hasVC) => {
    const role = mSpec.material_role || 'hull_default';
    const base = hasVC ? '#ffffff' : (mSpec.color || '#1e232a');
    if (role === 'carbon_satin') {
      return new THREE.MeshPhysicalMaterial({
        color: base,
        vertexColors: hasVC,
        roughness: 0.34,
        metalness: 0.22,
        clearcoat: 0.90,
        clearcoatRoughness: 0.12,
        reflectivity: 0.88,
        sheen: 0.14,
      });
    }
    if (role === 'vtx_gold') {
      return new THREE.MeshPhysicalMaterial({
        color: base,
        vertexColors: hasVC,
        roughness: 0.20,
        metalness: 0.78,
        clearcoat: 0.95,
        clearcoatRoughness: 0.08,
        reflectivity: 0.95,
      });
    }
    if (role === 'titanium_strut') {
      return new THREE.MeshPhysicalMaterial({
        color: base,
        vertexColors: hasVC,
        roughness: 0.24,
        metalness: 0.84,
        clearcoat: 0.35,
        clearcoatRoughness: 0.20,
      });
    }
    if (role === 'canopy_glass') {
      return new THREE.MeshPhysicalMaterial({
        color: hasVC ? '#ffffff' : (mSpec.color || '#2b5575'),
        vertexColors: hasVC,
        roughness: 0.05,
        metalness: 0.10,
        ior: 1.58,
        reflectivity: 0.98,
        clearcoat: 1.0,
        clearcoatRoughness: 0.04,
        transparent: true,
        opacity: 0.44,
        depthWrite: false,
      });
    }
    if (role === 'cockpit_detail') {
      return new THREE.MeshStandardMaterial({ color: base, vertexColors: hasVC, roughness: 0.62, metalness: 0.18 });
    }
    if (role === 'avionics_glow') {
      return new THREE.MeshStandardMaterial({
        color: base,
        vertexColors: hasVC,
        emissive: '#0ea5e9',
        emissiveIntensity: 1.45,
        roughness: 0.18,
        metalness: 0.25,
      });
    }
    if (role === 'fan_rotor') {
      return new THREE.MeshPhysicalMaterial({
        color: base,
        vertexColors: hasVC,
        roughness: 0.26,
        metalness: 0.74,
        clearcoat: 0.45,
        clearcoatRoughness: 0.18,
      });
    }
    return new THREE.MeshPhysicalMaterial({
      color: hasVC ? '#ffffff' : (mSpec.color || '#dfe7ee'),
      vertexColors: hasVC,
      roughness: 0.32,
      metalness: 0.20,
      clearcoat: 0.65,
      clearcoatRoughness: 0.18,
    });
  };

  for (const mSpec of modelPayload.meshes || []) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(mSpec.vertices, 3));
    const hasVC = Array.isArray(mSpec.vertex_colors) && mSpec.vertex_colors.length === mSpec.vertices.length;
    if (hasVC) {
      geo.setAttribute('color', new THREE.Float32BufferAttribute(mSpec.vertex_colors, 3));
    }
    const hasNorms = Array.isArray(mSpec.normals) && mSpec.normals.length === mSpec.vertices.length;
    if (hasNorms) {
      geo.setAttribute('normal', new THREE.Float32BufferAttribute(mSpec.normals, 3));
    }
    geo.setIndex(mSpec.faces);
    if (!hasNorms) {
      geo.computeVertexNormals();
    }
    const mat = makeRoleMat(mSpec, hasVC);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = mSpec.name;
    if (Array.isArray(mSpec.offset) && mSpec.offset.length === 3) {
      mesh.position.set(mSpec.offset[0], mSpec.offset[1], mSpec.offset[2]);
    }
    mesh.castShadow = mSpec.material_role !== 'canopy_glass';
    mesh.receiveShadow = true;
    ensureBody(mSpec.body).add(mesh);
  }

  // Structural appendages (wing, canopy, pylon, h-tail, twin ducted fans)
  for (const bSpec of modelPayload.boxes || []) {
    const [hx, hy, hz] = bSpec.half;
    const geo = new THREE.BoxGeometry(hx * 2, hy * 2, hz * 2);
    const isCanopy = bSpec.name === 'cabin_canopy';
    const mat = new THREE.MeshStandardMaterial({
      color: bSpec.color || '#cfd9e2',
      roughness: isCanopy ? 0.12 : 0.42,
      metalness: isCanopy ? 0.65 : 0.25,
      transparent: isCanopy,
      opacity: isCanopy ? 0.72 : 1.0,
    });
    const m = new THREE.Mesh(geo, mat);
    m.name = bSpec.name;
    m.position.set(...bSpec.pos);
    const [rx, ry, rz] = (bSpec.euler_deg || [0, 0, 0]).map((d) => (d * Math.PI) / 180);
    m.rotation.set(rx, ry, rz, 'XYZ');
    m.castShadow = true;
    ensureBody(bSpec.body).add(m);
  }

  return root;
}

const WATER_ZONE_PRESETS = [
  { id: 'open_water', label: 'Deep Basin · 10.5 m depth (40, 0)', xy: [40, 0] },
  { id: 'accel_start', label: 'Accel Lane · ~9.5 m depth (-320, 0)', xy: [-320, 0] },
  { id: 'turning_entry', label: 'Turning Circle · NE leg (310, 180)', xy: [310, 180] },
  { id: 'shallow_shelf', label: 'Shallow Shelf · ~0.65 m depth (-360, 220)', xy: [-360, 220] },
  { id: 'marina_berth_2', label: 'Marina Quay Approach · ~3.4 m (-772, -220)', xy: [-772, -220] },
  { id: 'ramp_approach', label: 'Recovery Ramp Toe · (-798, -110)', xy: [-798, -110] },
];

export function createRicochetPanel({ api, toast, onZoneSelect }) {
  const container = document.getElementById('ricochet-panel');
  if (!container) return null;

  container.innerHTML = `
    <div class="section-label">02 / RICOCHET MARINE & HYDRODYNAMICS</div>
    <div class="control-heading">
      <h2>Lake, Wave &amp; Hull Controls</h2>
      <span id="rico-hull-badge">PROVISIONAL</span>
    </div>
    <p class="muted small" style="margin:0 0 .5rem">Controls update the live coupled 400 Hz MuJoCo + hybrid wave/SWE solver without bypassing rigid-body physics.</p>

    <div class="section-label">PROPULSION &amp; SURFACE CONTROLS (ricochet-1 · hold_until_changed)</div>
    <label class="range-label">Fan throttle <output id="rico-throttle-val">0%</output><input id="rico-throttle" type="range" min="0" max="1" step="0.01" value="0"></label>
    <label class="range-label">Differential thrust <output id="rico-diff-val">0.00</output><input id="rico-diff" type="range" min="-1" max="1" step="0.02" value="0"></label>
    <label class="range-label">Rudder angle <output id="rico-rudder-val">0.0°</output><input id="rico-rudder" type="range" min="-30" max="30" step="0.5" value="0"></label>
    <label class="range-label">Elevator angle <output id="rico-elev-val">0.0°</output><input id="rico-elev" type="range" min="-20" max="20" step="0.5" value="0"></label>
    <label class="range-label">Aileron angle <output id="rico-ail-val">0.0°</output><input id="rico-ail" type="range" min="-25" max="25" step="0.5" value="0"></label>
    <label class="range-label">Reverse bucket <output id="rico-rev-val">0%</output><input id="rico-rev" type="range" min="0" max="1" step="0.05" value="0"></label>
    <div id="rico-surface-feedback" class="muted small" style="margin:.2rem 0 .35rem;font:11px/1.35 ui-monospace,monospace">Achieved surfaces: awaiting telemetry…</div>
    <div class="map-tools" style="margin:0 0 .5rem;display:flex;gap:.35rem;align-items:center">
      <input id="rico-cmd-text" type="text" placeholder="Pilot cmd: e.g. half throttle, hard port rudder, nose up 10" style="flex:1;min-width:0">
      <button id="rico-cmd-send" type="button">Send cmd</button>
    </div>

    <div class="section-label">ENVIRONMENT &amp; WATER FIELD</div>
    <label class="control-label">WATER DEPTH / TEST ZONE
      <select id="rico-zone-select">
        ${WATER_ZONE_PRESETS.map((z) => `<option value="${z.xy.join(',')}">${z.label}</option>`).join('')}
      </select>
    </label>
    <label class="control-label">WAVE MODE
      <select id="rico-wave-mode">
        <option value="still">Still water (calm baseline)</option>
        <option value="regular">Regular directional Stokes-like waves</option>
        <option value="irregular">Seeded JONSWAP-like irregular spectrum</option>
      </select>
    </label>
    <label class="range-label">Water level datum shift <output id="rico-wl-val">0.00 m</output><input id="rico-wl" type="range" min="-1.5" max="1.5" step="0.05" value="0"></label>
    <label class="range-label">Significant wave height <output id="rico-wh-val">0.35 m</output><input id="rico-wh" type="range" min="0" max="2.5" step="0.05" value="0.35"></label>
    <div class="vector-controls">
      <label class="range-label">Wave period <output id="rico-wp-val">4.0 s</output><input id="rico-wp" type="range" min="1.5" max="12" step="0.1" value="4.0"></label>
      <label class="range-label">Wave dir <output id="rico-wd-val">200°</output><input id="rico-wd" type="range" min="0" max="360" step="5" value="200"></label>
    </div>
    <div class="vector-controls">
      <label class="range-label">Wind speed <output id="rico-ws-val">3.0 m/s</output><input id="rico-ws" type="range" min="0" max="25" step="0.5" value="3.0"></label>
      <label class="range-label">Wind dir <output id="rico-wdir-val">200°</output><input id="rico-wdir" type="range" min="0" max="360" step="5" value="200"></label>
    </div>
    <div class="vector-controls">
      <label class="range-label">Current speed <output id="rico-cs-val">0.0 m/s</output><input id="rico-cs" type="range" min="0" max="4" step="0.1" value="0"></label>
      <label class="range-label">Current dir <output id="rico-cdir-val">0°</output><input id="rico-cdir" type="range" min="0" max="360" step="5" value="0"></label>
    </div>
    <label><input id="rico-wake-enabled" type="checkbox" checked> Dynamic Kelvin wake &amp; heave ripples</label>
    <label><input id="rico-whirlpools-enabled" type="checkbox" checked> Active whirlpools (Alpha / Bravo)</label>
    <label class="range-label">Whirlpool intensity <output id="rico-whirlpool-int-val">1.0×</output><input id="rico-whirlpool-int" type="range" min="0" max="2" step="0.1" value="1"></label>

    <div class="section-label">MASS, BALLAST, CG &amp; WATERTIGHT INTEGRITY</div>
    <label class="control-label">LOAD CASE
      <select id="rico-load-case">
        <option value="LC-01" selected>LC-01 · Passenger aboard, underway (~900 kg)</option>
        <option value="LC-02">LC-02 · Unoccupied &amp; stowed, propulsion off (~815 kg)</option>
        <option value="LC-03">LC-03 · Empty-payload flotation, no passenger (~815 kg + fuel)</option>
        <option value="LC-04">LC-04 · Propulsion installation comparison</option>
        <option value="LC-MAX">LC-MAX · Max water-loading envelope (~1050 kg)</option>
      </select>
    </label>
    <div class="vector-controls">
      <label class="control-label">PROPULSION INSTALL
        <select id="rico-propulsion-installation">
          <option value="baseline_pack" selected>Baseline forward pack (1.62 m)</option>
          <option value="fuel_cell_paired">Paired fuel cells (-1.05, ±0.23 m)</option>
          <option value="energy_pack_alternate">Alternate aft pack (-1.02 m)</option>
        </select>
      </label>
      <label class="control-label">FUEL STATE
        <select id="rico-fuel-state">
          <option value="dry" selected>Dry (0.0 kg)</option>
          <option value="short_test">Short test (5.0 kg)</option>
          <option value="nominal">Nominal (10.0 kg)</option>
          <option value="full">Full (20.0 kg)</option>
          <option value="custom" disabled>Custom (API)</option>
        </select>
      </label>
    </div>
    <div id="rico-loading-meta" class="muted small" style="margin:.15rem 0 .4rem;font:11px/1.35 ui-monospace,monospace">rc01-f03-lc-v2 · LC-01 · baseline_pack · dry (0.0 kg) · PROP ARMED</div>
    <div class="coordinates">
      <label>TOTAL MASS (kg)<input id="rico-mass-kg" type="number" min="400" max="3500" step="5" value="900"></label>
      <label>PAYLOAD (kg)<input id="rico-payload-kg" type="number" min="0" max="500" step="5" value="0"></label>
    </div>
    <div class="coordinates">
      <label>BALLAST (kg)<input id="rico-ballast-kg" type="number" min="0" max="1500" step="5" value="0"></label>
      <label class="range-label">Ballast X <output id="rico-ballast-x-val">-0.15 m</output><input id="rico-ballast-x" type="range" min="-1.5" max="1.5" step="0.05" value="-0.15"></label>
    </div>
    <div class="vector-controls">
      <label class="range-label">CG shift X <output id="rico-cgx-val">0.00 m</output><input id="rico-cgx" type="range" min="-0.6" max="0.6" step="0.02" value="0"></label>
      <label class="range-label">CG shift Z <output id="rico-cgz-val">0.00 m</output><input id="rico-cgz" type="range" min="-0.4" max="0.4" step="0.02" value="0"></label>
    </div>
    <label><input id="rico-passenger" type="checkbox" checked> Passenger aboard (85 kg)</label>
    <label><input id="rico-waterproof" type="checkbox" checked> Waterproof hull seal (uncheck to breach / flood)</label>
    <div class="map-tools" style="margin-top:.45rem">
      <button id="rico-apply-mass" type="button">Apply mass &amp; ballast</button>
      <button id="rico-bilge-pump" type="button">Bilge Pump (Drain)</button>
      <button id="rico-export" type="button">Export JSON run</button>
    </div>

    <div id="rico-warning-banner" hidden style="margin:.45rem 0;padding:.4rem .55rem;border-radius:6px;background:#7c2d12;border:1px solid #f59e0b;color:#fef3c7;font:600 11px/1.35 ui-monospace,monospace"></div>
    <div class="section-label">HYDRODYNAMIC TELEMETRY</div>
    <pre id="rico-telemetry" class="muted small" style="white-space:pre-wrap;font:11px/1.35 ui-monospace,monospace;background:#0e1e1c;padding:.5rem;border-radius:6px;max-height:280px;overflow:auto">Awaiting telemetry…</pre>
  `;

  const el = (id) => document.getElementById(id);
  const cmdState = {
    throttle: 0,
    differential_thrust: 0,
    rudder_deg: 0,
    elevator_deg: 0,
    aileron_deg: 0,
    reverse_bucket: 0,
  };
  let cmdDirty = false;
  let visible = false;
  let lastView = null;
  let syncingFromServer = false;
  let lastCommandSyncKey = '';

  let lastServerTotalMass = 900;
  let totalMassEdited = false;

  const sendTextCommand = async () => {
    const input = el('rico-cmd-text');
    const text = input?.value?.trim();
    if (!text) return;
    if (!lastView?.active) {
      toast?.('Start a Ricochet Lake mission to send pilot commands.');
      return;
    }
    try {
      await api('/api/action', {
        schema: 'ricochet-1',
        authority: 'manual',
        expected_run_id: lastView?.run_id,
        observation_id: lastView?.observation?.observation_id,
        text,
        reason: 'Ricochet pilot text command',
      });
      cmdDirty = false;
      toast?.(`Pilot command sent: ${text}`);
    } catch (e) {
      toast?.(`Pilot command failed: ${e.message}`);
    }
  };

  el('rico-cmd-send')?.addEventListener('click', sendTextCommand);
  el('rico-cmd-text')?.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      sendTextCommand();
    }
  });

  const updateLabels = () => {
    el('rico-throttle-val').value = `${Math.round(Number(el('rico-throttle').value) * 100)}%`;
    el('rico-diff-val').value = Number(el('rico-diff').value).toFixed(2);
    el('rico-rudder-val').value = `${Number(el('rico-rudder').value).toFixed(1)}°`;
    el('rico-elev-val').value = `${Number(el('rico-elev').value).toFixed(1)}°`;
    el('rico-ail-val').value = `${Number(el('rico-ail').value).toFixed(1)}°`;
    el('rico-rev-val').value = `${Math.round(Number(el('rico-rev').value) * 100)}%`;
    el('rico-wl-val').value = `${Number(el('rico-wl').value).toFixed(2)} m`;
    el('rico-wh-val').value = `${Number(el('rico-wh').value).toFixed(2)} m`;
    el('rico-wp-val').value = `${Number(el('rico-wp').value).toFixed(1)} s`;
    el('rico-wd-val').value = `${Number(el('rico-wd').value).toFixed(0)}°`;
    el('rico-ws-val').value = `${Number(el('rico-ws').value).toFixed(1)} m/s`;
    el('rico-wdir-val').value = `${Number(el('rico-wdir').value).toFixed(0)}°`;
    el('rico-cs-val').value = `${Number(el('rico-cs').value).toFixed(1)} m/s`;
    el('rico-cdir-val').value = `${Number(el('rico-cdir').value).toFixed(0)}°`;
    el('rico-whirlpool-int-val').value = `${Number(el('rico-whirlpool-int').value).toFixed(1)}×`;
    el('rico-ballast-x-val').value = `${Number(el('rico-ballast-x').value).toFixed(2)} m`;
    el('rico-cgx-val').value = `${Number(el('rico-cgx').value).toFixed(2)} m`;
    el('rico-cgz-val').value = `${Number(el('rico-cgz').value).toFixed(2)} m`;
  };

  for (const [id, key] of [
    ['rico-throttle', 'throttle'],
    ['rico-diff', 'differential_thrust'],
    ['rico-rudder', 'rudder_deg'],
    ['rico-elev', 'elevator_deg'],
    ['rico-ail', 'aileron_deg'],
    ['rico-rev', 'reverse_bucket'],
  ]) {
    el(id).addEventListener('input', () => {
      cmdState[key] = Number(el(id).value);
      updateLabels();
      cmdDirty = true;
    });
  }

  let waterTimer = null;
  const pushWaterConfig = () => {
    if (syncingFromServer) return;
    clearTimeout(waterTimer);
    waterTimer = setTimeout(async () => {
      try {
        await api('/api/water/config', {
          water_level_m: Number(el('rico-wl').value),
          wave_mode: el('rico-wave-mode').value,
          wave_height_m: Number(el('rico-wh').value),
          wave_period_s: Number(el('rico-wp').value),
          wave_direction_deg: Number(el('rico-wd').value),
          wind_speed_mps: Number(el('rico-ws').value),
          wind_direction_deg: Number(el('rico-wdir').value),
          current_speed_mps: Number(el('rico-cs').value),
          current_direction_deg: Number(el('rico-cdir').value),
          wake_enabled: el('rico-wake-enabled').checked,
          whirlpools_enabled: el('rico-whirlpools-enabled').checked,
          whirlpool_intensity: Number(el('rico-whirlpool-int').value),
        });
      } catch (e) {
        toast?.(`Water config update failed: ${e.message}`);
      }
    }, 60);
  };

  for (const id of [
    'rico-wave-mode',
    'rico-wl',
    'rico-wh',
    'rico-wp',
    'rico-wd',
    'rico-ws',
    'rico-wdir',
    'rico-cs',
    'rico-cdir',
    'rico-wake-enabled',
    'rico-whirlpools-enabled',
    'rico-whirlpool-int',
  ]) {
    el(id).addEventListener('input', () => {
      updateLabels();
      pushWaterConfig();
    });
    el(id).addEventListener('change', pushWaterConfig);
  }

  el('rico-zone-select').addEventListener('change', async () => {
    const xy = el('rico-zone-select').value.split(',').map(Number);
    if (xy.length === 2 && xy.every(Number.isFinite)) {
      await onZoneSelect?.(xy);
    }
  });

  el('rico-mass-kg').addEventListener('input', () => {
    totalMassEdited = true;
  });
  el('rico-ballast-kg').addEventListener('input', () => {
    totalMassEdited = false;
  });
  el('rico-payload-kg').addEventListener('input', () => {
    totalMassEdited = false;
  });
  el('rico-passenger').addEventListener('change', () => {
    totalMassEdited = false;
  });
  el('rico-ballast-x').addEventListener('input', updateLabels);
  el('rico-cgx').addEventListener('input', updateLabels);
  el('rico-cgz').addEventListener('input', updateLabels);

  const syncMassPropertiesUI = (mp, force = false) => {
    if (!mp) return;
    const activeId = document.activeElement?.id || '';
    if (mp.load_case && el('rico-load-case') && (force || activeId !== 'rico-load-case')) {
      const lcSel = el('rico-load-case');
      const lcVal = String(mp.load_case);
      if ([...lcSel.options].some((opt) => opt.value === lcVal)) {
        lcSel.value = lcVal;
      }
    }
    if (mp.propulsion_installation && el('rico-propulsion-installation') && (force || activeId !== 'rico-propulsion-installation')) {
      const instSel = el('rico-propulsion-installation');
      const instVal = String(mp.propulsion_installation);
      if ([...instSel.options].some((opt) => opt.value === instVal)) {
        instSel.value = instVal;
      }
    }
    if (el('rico-fuel-state') && (force || activeId !== 'rico-fuel-state')) {
      const fsSel = el('rico-fuel-state');
      const fsVal = mp.fuel_state ? String(mp.fuel_state) : 'dry';
      if ([...fsSel.options].some((opt) => opt.value === fsVal)) {
        fsSel.value = fsVal;
      }
    }
    if (mp.passenger_aboard != null && el('rico-passenger') && (force || activeId !== 'rico-passenger')) {
      el('rico-passenger').checked = Boolean(mp.passenger_aboard);
    }
    if (mp.payload_mass_kg != null && el('rico-payload-kg') && (force || (!totalMassEdited && activeId !== 'rico-payload-kg'))) {
      el('rico-payload-kg').value = Math.round(Number(mp.payload_mass_kg || 0));
    }
    if (mp.total_mass_kg != null && (force || (!totalMassEdited && !['rico-mass-kg', 'rico-ballast-kg', 'rico-ballast-x', 'rico-payload-kg'].includes(activeId)))) {
      lastServerTotalMass = Math.round(Number(mp.total_mass_kg));
      el('rico-mass-kg').value = lastServerTotalMass;
      if (mp.ballast_mass_kg != null) el('rico-ballast-kg').value = Math.round(Number(mp.ballast_mass_kg));
      if (mp.ballast_x_m != null) el('rico-ballast-x').value = Number(mp.ballast_x_m);
      if (mp.waterproof != null) el('rico-waterproof').checked = Boolean(mp.waterproof);
      updateLabels();
    }
    const metaNode = el('rico-loading-meta');
    if (metaNode) {
      const regVer = mp.register_version || 'rc01-f03-lc-v2';
      const lc = mp.load_case || 'LC-01';
      const inst = mp.propulsion_installation || 'baseline_pack';
      const fs = mp.fuel_state || 'dry';
      const fm = Number(mp.fuel_mass_kg ?? 0).toFixed(1);
      const propMode = mp.propulsion_off ? 'PROP OFF' : 'PROP ARMED';
      metaNode.textContent = `${regVer} · ${lc} · ${inst} · fuel ${fs} (${fm} kg) · ${propMode}`;
    }
  };

  el('rico-load-case').addEventListener('change', async () => {
    try {
      const res = await api('/api/water/mass', { load_case: el('rico-load-case').value });
      if (res?.mass_properties) {
        totalMassEdited = false;
        syncMassPropertiesUI(res.mass_properties, true);
        toast?.(`Applied ${res.mass_properties.load_case} (${res.mass_properties.total_mass_kg.toFixed(1)} kg, ${res.mass_properties.propulsion_installation || 'baseline_pack'})`);
      }
    } catch (e) {
      toast?.(`Load case update failed: ${e.message}`);
    }
  });

  el('rico-propulsion-installation').addEventListener('change', async () => {
    try {
      const inst = el('rico-propulsion-installation').value;
      const body = { propulsion_installation: inst };
      const clearedFuel = inst === 'energy_pack_alternate' && el('rico-fuel-state').value !== 'dry';
      if (clearedFuel) {
        body.fuel_state = 'dry';
        body.fuel_mass_kg = 0.0;
      }
      const res = await api('/api/water/mass', body);
      if (res?.mass_properties) {
        totalMassEdited = false;
        syncMassPropertiesUI(res.mass_properties, true);
        toast?.(
          `Installation ${res.mass_properties.propulsion_installation} (${res.mass_properties.total_mass_kg.toFixed(1)} kg)${clearedFuel ? '; fuel reset to dry (F02 mutually exclusive)' : ''}`
        );
      }
    } catch (e) {
      toast?.(`Propulsion installation update failed: ${e.message}`);
    }
  });

  el('rico-fuel-state').addEventListener('change', async () => {
    const fs = el('rico-fuel-state').value;
    if (fs === 'custom') return;
    try {
      const res = await api('/api/water/mass', { fuel_state: fs });
      if (res?.mass_properties) {
        totalMassEdited = false;
        syncMassPropertiesUI(res.mass_properties, true);
        toast?.(`Fuel state ${res.mass_properties.fuel_state} (${Number(res.mass_properties.fuel_mass_kg || 0).toFixed(1)} kg)`);
      }
    } catch (e) {
      toast?.(`Fuel state update failed: ${e.message}`);
      const prevMp = lastView?.rendering_truth?.mass_properties || lastView?.observation;
      if (prevMp) syncMassPropertiesUI(prevMp, true);
    }
  });

  const pushMassUpdate = async (extra = {}) => {
    try {
      const payload = {
        payload_mass_kg: Number(el('rico-payload-kg').value),
        ballast_mass_kg: Number(el('rico-ballast-kg').value),
        ballast_x_m: Number(el('rico-ballast-x').value),
        passenger_aboard: el('rico-passenger').checked,
        waterproof: el('rico-waterproof').checked,
        cg_shift_vtx_m: [Number(el('rico-cgx').value), 0.0, Number(el('rico-cgz').value)],
        ...extra,
      };
      if (totalMassEdited) {
        payload.total_mass_kg = Number(el('rico-mass-kg').value);
      }
      const res = await api('/api/water/mass', payload);
      if (res?.mass_properties) {
        totalMassEdited = false;
        syncMassPropertiesUI(res.mass_properties, true);
        toast?.(
          `Mass ${res.mass_properties.total_mass_kg.toFixed(1)} kg (ballast ${Number(res.mass_properties.ballast_mass_kg || 0).toFixed(0)} kg, ${res.mass_properties.waterproof ? 'SEALED' : 'UNSEALED'})`
        );
      }
    } catch (e) {
      toast?.(`Mass update failed: ${e.message}`);
    }
  };

  el('rico-apply-mass').addEventListener('click', () => pushMassUpdate());
  el('rico-waterproof').addEventListener('change', () => pushMassUpdate());
  el('rico-bilge-pump').addEventListener('click', async () => {
    try {
      const res = await api('/api/water/mass', { bilge_pump: true });
      if (res?.mass_properties) {
        syncMassPropertiesUI(res.mass_properties, true);
      }
      toast?.('Bilge pump activated: ingressed flood water drained to 0 kg.');
    } catch (e) {
      toast?.(`Bilge pump failed: ${e.message}`);
    }
  });

  el('rico-export').addEventListener('click', async () => {
    try {
      const bundle = await api('/api/water/export');
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ricochet-water-run-${bundle.run_id || 'inspection'}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast?.('Exported Ricochet Lake telemetry & configuration bundle.');
    } catch (e) {
      toast?.(`Export failed: ${e.message}`);
    }
  });

  return {
    show(nextVisible) {
      visible = Boolean(nextVisible);
      container.hidden = !visible;
      container.style.display = visible ? '' : 'none';
      const panel = document.querySelector('.controls-panel');
      if (!panel) return;
      for (const child of panel.children) {
        if (child.id === 'ricochet-panel' || child.id === 'decisions' || child.classList.contains('decisions-label') || child.id === 'objective-form' || child.id === 'objective-current' || child.id === 'objective-pilot') {
          continue;
        }
        child.hidden = visible;
        child.style.display = visible ? 'none' : '';
      }
    },
    isVisible() {
      return visible;
    },
    getCommand() {
      return { schema: 'ricochet-1', ...cmdState };
    },
    consumeDirty() {
      const d = cmdDirty;
      cmdDirty = false;
      return d;
    },
    markDirty() {
      cmdDirty = true;
    },
    update(view) {
      lastView = view;
      const o = view?.observation;
      if (!o || o.action_schema !== 'ricochet-1') return;
      const rt = view?.rendering_truth || {};
      const h = rt.hydrodynamics || o.hydrodynamics || {};
      const f = h.forces_world_n || {};
      const m = h.torques_world_nm || {};
      const wc = o.water_config || rt.water_config || {};
      const cons = o.water_conservation || rt.water_conservation || {};
      const mp = rt.mass_properties || o.mass_properties || {};
      const att = rt.attachment_loads || o.attachment_loads || {};
      const wp = o.whirlpool_hazard || rt.whirlpool_hazard || {};
      const wake = o.vessel_wake || rt.vessel_wake || {};
      const surf = o.control_surfaces || rt.aero?.surfaces || {};
      const surfLim = o.surface_limits || {};
      const fanRpm = Array.isArray(o.fan_rpm) ? o.fan_rpm : (Array.isArray(rt.fan_rpm) ? rt.fan_rpm : [0, 0]);
      const lamps = Array.isArray(o.warning_lamps) ? o.warning_lamps : [];

      // Bind slider mechanical stops to authoritative surface_limits
      const bindRange = (id, bounds) => {
        const node = el(id);
        if (!node || !bounds) return;
        const bMin = Array.isArray(bounds) ? bounds[0] : bounds.min;
        const bMax = Array.isArray(bounds) ? bounds[1] : bounds.max;
        if (bMin != null && bMax != null) {
          node.min = String(bMin);
          node.max = String(bMax);
        }
      };
      bindRange('rico-rudder', surfLim.rudder_deg);
      bindRange('rico-elev', surfLim.elevator_deg);
      bindRange('rico-ail', surfLim.aileron_deg);

      // Sync commanded controls when server command updates and operator is not dragging a slider
      const srvCmd = o.command || rt.command;
      const activeId = document.activeElement?.id || '';
      const draggingControl = ['rico-throttle', 'rico-diff', 'rico-rudder', 'rico-elev', 'rico-ail', 'rico-rev'].includes(activeId);
      if (srvCmd && !cmdDirty && !draggingControl) {
        const key = JSON.stringify(srvCmd);
        if (key !== lastCommandSyncKey) {
          lastCommandSyncKey = key;
          const setSlider = (id, field, fallback) => {
            const val = Number(srvCmd[field] ?? fallback);
            if (!Number.isFinite(val)) return;
            cmdState[field] = val;
            if (el(id)) el(id).value = String(val);
          };
          setSlider('rico-throttle', 'throttle', 0);
          setSlider('rico-diff', 'differential_thrust', 0);
          setSlider('rico-rudder', 'rudder_deg', 0);
          setSlider('rico-elev', 'elevator_deg', 0);
          setSlider('rico-ail', 'aileron_deg', 0);
          setSlider('rico-rev', 'reverse_bucket', 0);
          updateLabels();
        }
      }

      const fbNode = el('rico-surface-feedback');
      if (fbNode) {
        const rud = Number(surf.rudder?.achieved_deg ?? 0).toFixed(1);
        const elev = Number(surf.elevator?.achieved_deg ?? 0).toFixed(1);
        const ailP = Number(surf.aileron?.port_achieved_deg ?? 0).toFixed(1);
        const ailS = Number(surf.aileron?.stbd_achieved_deg ?? 0).toFixed(1);
        const revPct = Math.round(Number(surf.reverse_bucket?.achieved_frac ?? 0) * 100);
        const revP = Number(surf.reverse_bucket?.port_achieved_deg ?? 0).toFixed(0);
        const revS = Number(surf.reverse_bucket?.stbd_achieved_deg ?? 0).toFixed(0);
        const rpm0 = Number(fanRpm[0] ?? 0).toFixed(0);
        const rpm1 = Number(fanRpm[1] ?? 0).toFixed(0);
        const fuel = Array.isArray(o.fuel_kg) ? o.fuel_kg.reduce((a, b) => a + Number(b || 0), 0).toFixed(2) : '—';
        fbNode.textContent = `Fans ${rpm0}/${rpm1} RPM · Fuel ${fuel} kg · Rud ${rud}° · Elev ${elev}° · Ail ${ailP}°/${ailS}° · Rev ${revPct}% (${revP}°/${revS}°)`;
      }

      if (wc.wave_mode && document.activeElement?.id !== 'rico-wave-mode') {
        syncingFromServer = true;
        el('rico-wave-mode').value = wc.wave_mode;
        el('rico-wl').value = wc.water_level_m ?? 0;
        el('rico-wh').value = wc.wave_height_m ?? 0.35;
        el('rico-wp').value = wc.wave_period_s ?? 4.0;
        el('rico-wd').value = wc.wave_direction_deg ?? 200;
        el('rico-ws').value = wc.wind_speed_mps ?? 3.0;
        el('rico-wdir').value = wc.wind_direction_deg ?? 200;
        el('rico-cs').value = wc.current_speed_mps ?? 0;
        el('rico-cdir').value = wc.current_direction_deg ?? 0;
        el('rico-wake-enabled').checked = wc.wake_enabled !== false;
        el('rico-whirlpools-enabled').checked = wc.whirlpools_enabled !== false;
        el('rico-whirlpool-int').value = wc.whirlpool_intensity ?? 1.0;
        updateLabels();
        syncingFromServer = false;
      }

      const mpSync = {
        load_case: o.load_case ?? o.configuration?.load_case,
        register_version: o.register_version ?? o.configuration?.register_version,
        fuel_state: o.fuel_state ?? o.configuration?.fuel_state,
        fuel_mass_kg: o.fuel_mass_kg ?? o.configuration?.fuel_mass_kg,
        propulsion_installation: o.propulsion_installation ?? o.configuration?.propulsion_installation,
        propulsion_off: o.propulsion_off ?? o.configuration?.propulsion_off,
        ...mp,
      };
      syncMassPropertiesUI(mpSync, false);

      const banner = el('rico-warning-banner');
      if (banner) {
        if (lamps.length > 0) {
          banner.hidden = false;
          banner.textContent = `ACTIVE ALERTS: ${lamps.join(' · ')}`;
          banner.style.background = lamps.includes('SINKS') || lamps.includes('WHIRLPOOL_CAPTURE') ? '#7f1d1d' : '#78350f';
        } else {
          banner.hidden = true;
          banner.textContent = '';
        }
      }

      const hullVariant = o.configuration?.hull_variant || 'f03';
      el('rico-hull-badge').textContent = hullVariant.toUpperCase();
      if (mpSync.load_case) {
        el('rico-load-case').disabled = false;
        el('rico-mass-kg').disabled = false;
      }

      const fmtVec = (v) => (Array.isArray(v) ? `[${v.map((x) => Number(x).toFixed(0)).join(', ')}]` : '—');
      const sealOk = mp.waterproof != null ? mp.waterproof : o.waterproof_seal;
      const floodKg = mp.flood_water_kg != null ? mp.flood_water_kg : o.flood_water_kg;
      const sealStr = sealOk === false ? 'BREACHED' : 'SEALED';
      const whirlStr = wp.in_influence
        ? `${wp.whirlpool_name || wp.whirlpool_id} (${Number(wp.distance_m ?? 0).toFixed(1)} m, swirl ${Number(wp.swirl_mps ?? 0).toFixed(2)} m/s, suck ${Number(wp.suction_mps ?? 0).toFixed(2)} m/s)`
        : `Clear (${Number(wp.distance_m ?? 999).toFixed(0)} m)`;
      const spoolArr = Array.isArray(o.spool_fraction) ? o.spool_fraction : [o.spool_fraction ?? 0];
      const spoolStr = spoolArr.map((s) => `${(Number(s || 0) * 100).toFixed(0)}%`).join(' / ');
      const lines = [
        `Pos XY: ${o.gnss_xy_m?.[0]?.toFixed(2) ?? '—'}, ${o.gnss_xy_m?.[1]?.toFixed(2) ?? '—'} m | Z: ${o.baro_m?.toFixed(3) ?? '—'} m`,
        `Vel XYZ: ${o.gnss_velocity_mps?.map((x) => x.toFixed(2)).join(', ') ?? '—'} m/s | Wake: ${Number(wake.speed_mps ?? 0).toFixed(2)} m/s`,
        `Att R/P/Y: ${o.attitude_xyz_deg?.map((x) => x.toFixed(2)).join('°, ') ?? '—'}°`,
        `Fans P/S: ${Number(fanRpm[0] ?? 0).toFixed(0)} / ${Number(fanRpm[1] ?? 0).toFixed(0)} RPM | Spool ${spoolStr}`,
        `Draft: ${(o.hull_draft_m ?? h.draft_m)?.toFixed(3) ?? '—'} m | Freeboard: ${(o.freeboard_min_m ?? h.freeboard_min_m)?.toFixed(3) ?? '—'} m`,
        `Depth: ${(o.water_depth_m ?? h.mean_water_depth_m)?.toFixed(2) ?? '—'} m | Keel clr: ${(o.radar_clearance_m ?? h.ground_clearance_m)?.toFixed(2) ?? '—'} m`,
        `Displaced Vol: ${h.submerged_volume_m3?.toFixed(4) ?? '—'} m³ | Wetted: ${h.wetted_area_m2?.toFixed(2) ?? '—'} m²`,
        `Load: ${mpSync.load_case || '—'} (${mpSync.register_version || '—'}) | Inst: ${mpSync.propulsion_installation || '—'} | Fuel: ${mpSync.fuel_state || 'dry'} (${Number(mpSync.fuel_mass_kg ?? 0).toFixed(1)} kg)`,
        `Mass: ${mp.total_mass_kg?.toFixed(1) ?? '—'} kg | Resv Buoy: ${mp.reserve_buoyancy_kg?.toFixed(0) ?? '—'} kg (Max ${mp.max_buoyancy_kg?.toFixed(0) ?? '—'})`,
        `Seal: ${sealStr} | Flood: ${Number(floodKg ?? 0).toFixed(1)} kg | Ballast: ${Number(mp.ballast_mass_kg ?? 0).toFixed(0)} kg @ X=${Number(mp.ballast_x_m ?? 0).toFixed(2)} m`,
        `Whirlpool: ${whirlStr}`,
        `Buoyancy F: ${fmtVec(f.buoyancy)} N | M: ${fmtVec(m.buoyancy)} N·m`,
        `Resistance F: ${fmtVec(f.resistance)} N | Lift F: ${fmtVec(f.dynamic_lift)} N`,
        `Munk Body M: ${fmtVec(h.munk_torque_body_nm)} N·m | WaveExcit F: ${fmtVec(f.wave_excitation)} N`,
        `Port Sponson: ${fmtVec(att.sponson_port?.force_n)} N | Stbd: ${fmtVec(att.sponson_stbd?.force_n)} N`,
        `SWE Mass Rel Err: ${Number(cons.relative_mass_error ?? 0).toExponential(2)} | Hash: ${(o.configuration?.hull_geometry_sha256 || '').slice(0, 10)}`,
      ];
      el('rico-telemetry').textContent = lines.join('\n');
    },
  };
}
