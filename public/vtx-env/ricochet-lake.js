// Consolidated Ricochet Lake (2000 x 1200 m) bathymetry, marina structures,
// dynamic hybrid free-surface water mesh, and physics-pinned Ricochet craft visual.
// Shares exact meter coordinates & VTX-MLD-SI vertical datum with RicochetLakeWorld.

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
  for (let j = 0; j < wny; j++) {
    const y = -hy + (j / (wny - 1)) * 2 * hy;
    for (let i = 0; i < wnx; i++) {
      const x = -hx + (i / (wnx - 1)) * 2 * hx;
      const idx = (j * wnx + i) * 3;
      wPos[idx] = x;
      wPos[idx + 1] = y;
      wPos[idx + 2] = wl;
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
  wGeo.setIndex(wIdx);
  wGeo.computeVertexNormals();
  const wMat = new THREE.MeshStandardMaterial({
    color: '#0e6a8d',
    emissive: '#041f2d',
    emissiveIntensity: 0.35,
    roughness: 0.16,
    metalness: 0.25,
    transparent: true,
    opacity: 0.78,
    side: THREE.DoubleSide,
  });
  const waterMesh = new THREE.Mesh(wGeo, wMat);
  waterMesh.name = 'ricochet_water_surface';
  waterMesh.receiveShadow = true;
  waterMesh.userData = { nx: wnx, ny: wny, hx, hy };
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

  return { group: root, waterMesh };
}

export function updateWaterSurface(waterMesh, waterFrame) {
  if (!waterMesh || !waterFrame || !Array.isArray(waterFrame.elevation_m)) return;
  const grid = waterFrame.elevation_m;
  const ny = waterFrame.ny || grid.length;
  const nx = waterFrame.nx || (grid[0] ? grid[0].length : 0);
  const pos = waterMesh.geometry.attributes.position;
  if (!nx || !ny || pos.count !== nx * ny) return;

  const { x_min_m, x_max_m, y_min_m, y_max_m } = waterFrame;
  for (let j = 0; j < ny; j++) {
    const y = y_min_m + (j / Math.max(1, ny - 1)) * (y_max_m - y_min_m);
    const row = grid[j];
    for (let i = 0; i < nx; i++) {
      const x = x_min_m + (i / Math.max(1, nx - 1)) * (x_max_m - x_min_m);
      const k = j * nx + i;
      pos.setXYZ(k, x, y, Number(row[i]));
    }
  }
  pos.needsUpdate = true;
  waterMesh.geometry.computeVertexNormals();
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
  { id: 'accel_start', label: 'Accel Lane · ~9.5 m depth (-620, 0)', xy: [-620, 0] },
  { id: 'turning_entry', label: 'Turning Circle · ~10.8 m depth (350, 0)', xy: [350, 0] },
  { id: 'shallow_shelf', label: 'Shallow Shelf · ~0.65 m depth (-360, 220)', xy: [-360, 220] },
  { id: 'marina_berth_2', label: 'Marina Berth 2 · ~3.4 m (-560, 290)', xy: [-560, 290] },
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

    <div class="section-label">PROPULSION &amp; SURFACE CONTROLS (ricochet-1)</div>
    <label class="range-label">Fan throttle <output id="rico-throttle-val">0%</output><input id="rico-throttle" type="range" min="0" max="1" step="0.01" value="0"></label>
    <label class="range-label">Differential thrust <output id="rico-diff-val">0.00</output><input id="rico-diff" type="range" min="-1" max="1" step="0.02" value="0"></label>
    <label class="range-label">Rudder angle <output id="rico-rudder-val">0.0°</output><input id="rico-rudder" type="range" min="-30" max="30" step="0.5" value="0"></label>
    <label class="range-label">Elevator angle <output id="rico-elev-val">0.0°</output><input id="rico-elev" type="range" min="-20" max="20" step="0.5" value="0"></label>
    <label class="range-label">Aileron angle <output id="rico-ail-val">0.0°</output><input id="rico-ail" type="range" min="-25" max="25" step="0.5" value="0"></label>
    <label class="range-label">Reverse bucket <output id="rico-rev-val">0%</output><input id="rico-rev" type="range" min="0" max="1" step="0.05" value="0"></label>

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

    <div class="section-label">MASS, CG &amp; PAYLOAD STATE</div>
    <label class="control-label">LOAD CASE
      <select id="rico-load-case">
        <option value="LC-01">LC-01 · Empty hull (~815 kg)</option>
        <option value="LC-02">LC-02 · Unoccupied stowed</option>
        <option value="LC-03" selected>LC-03 · Pilot nominal (~900 kg)</option>
        <option value="LC-04">LC-04 · Pilot + cargo (~960 kg)</option>
      </select>
    </label>
    <div class="coordinates">
      <label>TOTAL MASS (kg)<input id="rico-mass-kg" type="number" min="400" max="1500" step="5" value="900"></label>
      <label>PAYLOAD (kg)<input id="rico-payload-kg" type="number" min="0" max="300" step="5" value="0"></label>
    </div>
    <div class="vector-controls">
      <label class="range-label">CG shift X <output id="rico-cgx-val">0.00 m</output><input id="rico-cgx" type="range" min="-0.6" max="0.6" step="0.02" value="0"></label>
      <label class="range-label">CG shift Z <output id="rico-cgz-val">0.00 m</output><input id="rico-cgz" type="range" min="-0.4" max="0.4" step="0.02" value="0"></label>
    </div>
    <label><input id="rico-passenger" type="checkbox" checked> Passenger aboard (85 kg)</label>
    <div class="map-tools" style="margin-top:.45rem">
      <button id="rico-apply-mass" type="button">Apply mass &amp; CG</button>
      <button id="rico-export" type="button">Export JSON run</button>
    </div>

    <div class="section-label">HYDRODYNAMIC TELEMETRY</div>
    <pre id="rico-telemetry" class="muted small" style="white-space:pre-wrap;font:11px/1.35 ui-monospace,monospace;background:#0e1e1c;padding:.5rem;border-radius:6px;max-height:260px;overflow:auto">Awaiting telemetry…</pre>
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
        });
      } catch (e) {
        toast?.(`Water config update failed: ${e.message}`);
      }
    }, 60);
  };

  for (const id of ['rico-wave-mode', 'rico-wl', 'rico-wh', 'rico-wp', 'rico-wd', 'rico-ws', 'rico-wdir', 'rico-cs', 'rico-cdir']) {
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

  el('rico-cgx').addEventListener('input', updateLabels);
  el('rico-cgz').addEventListener('input', updateLabels);
  el('rico-load-case').addEventListener('change', async () => {
    try {
      const res = await api('/api/water/mass', { load_case: el('rico-load-case').value });
      if (res?.mass_properties) {
        el('rico-mass-kg').value = Math.round(res.mass_properties.total_mass_kg);
        el('rico-payload-kg').value = Math.round(res.mass_properties.payload_mass_kg || 0);
        el('rico-passenger').checked = Boolean(res.mass_properties.passenger_aboard);
        toast?.(`Applied ${res.mass_properties.load_case} (${res.mass_properties.total_mass_kg.toFixed(1)} kg)`);
      }
    } catch (e) {
      toast?.(`Load case update failed: ${e.message}`);
    }
  });

  el('rico-apply-mass').addEventListener('click', async () => {
    try {
      const res = await api('/api/water/mass', {
        total_mass_kg: Number(el('rico-mass-kg').value),
        payload_mass_kg: Number(el('rico-payload-kg').value),
        passenger_aboard: el('rico-passenger').checked,
        cg_shift_vtx_m: [Number(el('rico-cgx').value), 0.0, Number(el('rico-cgz').value)],
      });
      toast?.(`Updated mass ${res.mass_properties.total_mass_kg.toFixed(1)} kg, CG X=${res.mass_properties.cg_vtx_m[0].toFixed(3)} m`);
    } catch (e) {
      toast?.(`Mass update failed: ${e.message}`);
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
      const panel = document.querySelector('.controls-panel');
      if (!panel) return;
      for (const child of panel.children) {
        if (child.id === 'ricochet-panel' || child.id === 'decisions' || child.classList.contains('decisions-label') || child.id === 'objective-form' || child.id === 'objective-current' || child.id === 'objective-pilot') {
          continue;
        }
        child.hidden = visible;
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
      const h = o.hydrodynamics || {};
      const f = h.forces_world_n || {};
      const m = h.torques_world_nm || {};
      const wc = o.water_config || {};
      const cons = o.water_conservation || {};
      const mp = o.mass_properties || {};
      const att = o.attachment_loads || {};

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
        updateLabels();
        syncingFromServer = false;
      }

      const hullVariant = o.configuration?.hull_variant || 'f03';
      el('rico-hull-badge').textContent = hullVariant.toUpperCase();
      if (mp.load_case) {
        const disabledMass = Boolean(view.active);
        el('rico-load-case').disabled = false;
        el('rico-mass-kg').disabled = disabledMass && false;
      }

      const fmtVec = (v) => (Array.isArray(v) ? `[${v.map((x) => Number(x).toFixed(0)).join(', ')}]` : '—');
      const lines = [
        `Pos XY: ${o.gnss_xy_m?.[0]?.toFixed(2) ?? '—'}, ${o.gnss_xy_m?.[1]?.toFixed(2) ?? '—'} m | Z: ${o.baro_m?.toFixed(3) ?? '—'} m`,
        `Vel XYZ: ${o.gnss_velocity_mps?.map((x) => x.toFixed(2)).join(', ') ?? '—'} m/s`,
        `Att R/P/Y: ${o.attitude_xyz_deg?.map((x) => x.toFixed(2)).join('°, ') ?? '—'}°`,
        `Draft: ${h.draft_m?.toFixed(3) ?? '—'} m | Freeboard: ${h.freeboard_min_m?.toFixed(3) ?? '—'} m`,
        `Depth: ${h.mean_water_depth_m?.toFixed(2) ?? '—'} m | Keel clr: ${h.ground_clearance_m?.toFixed(2) ?? '—'} m`,
        `Displaced Vol: ${h.submerged_volume_m3?.toFixed(4) ?? '—'} m³ | Wetted: ${h.wetted_area_m2?.toFixed(2) ?? '—'} m²`,
        `Waterline Z: ${h.waterline_z_world_m?.toFixed(3) ?? '—'} m | Mass: ${mp.total_mass_kg?.toFixed(1) ?? '—'} kg`,
        `Buoyancy F: ${fmtVec(f.buoyancy)} N | M: ${fmtVec(m.buoyancy)} N·m`,
        `Resistance F: ${fmtVec(f.resistance)} N | Lift F: ${fmtVec(f.dynamic_lift)} N`,
        `AddedMass F: ${fmtVec(f.added_mass)} N | Damp F: ${fmtVec(f.damping)} N`,
        `WaveExcit F: ${fmtVec(f.wave_excitation)} N | Total F: ${fmtVec(f.total)} N`,
        `Port Sponson: ${fmtVec(att.sponson_port?.force_n)} N | Stbd: ${fmtVec(att.sponson_stbd?.force_n)} N`,
        `SWE Mass Rel Err: ${Number(cons.relative_mass_error ?? 0).toExponential(2)} | Hash: ${(o.configuration?.hull_geometry_sha256 || '').slice(0, 10)}`,
      ];
      el('rico-telemetry').textContent = lines.join('\n');
    },
  };
}
