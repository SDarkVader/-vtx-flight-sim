// Additive Main Airport harbour. Boat meshes follow the fleet's body poses;
// no aircraft selection, flight command or independent motion is generated here.
import * as THREE from 'three';
import {harbourWorldPoint} from './harbour-map.js?v=20261116-harbour-1';

const finiteArray = (values, length) => Array.isArray(values) && values.length === length && values.every(Number.isFinite);

export function harbourOverviewView(harbour, {aspect = 1, fov = 48} = {}) {
  const points = harbour.layout.outer.map(point => harbourWorldPoint(harbour, point));
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const width = x1 - x0, height = y1 - y0, extent = Math.max(width, height);
  const altitude = Math.max(width / aspect, height) / (2 * Math.tan(THREE.MathUtils.degToRad(fov / 2))) * 1.2;
  const target = [(x0 + x1) / 2, (y0 + y1) / 2, harbour.waterLevelM];
  return {target, position: [target[0], target[1] - altitude * .18, target[2] + altitude],
    near: Math.max(10, altitude * .001), far: altitude + extent * 2, fogNear: altitude * .9, fogDensity: .15 / altitude};
}

export function harbourWaterGeometry(harbour) {
  const ring = points => points.map(point => new THREE.Vector2(...harbourWorldPoint(harbour, point)));
  const shape = new THREE.Shape(ring(harbour.layout.outer));
  for (const island of harbour.layout.islands || []) shape.holes.push(new THREE.Path(ring(island.ring)));
  return new THREE.ShapeGeometry(shape);
}

export function buildBoatRig(payload) {
  if (!payload || !Array.isArray(payload.meshes)) throw Error('Boat geometry unavailable');
  const root = new THREE.Group(), bodies = new Map(); root.name = 'harbour-boat';
  const body = name => {
    if (!bodies.has(name)) {const node = new THREE.Group(); node.name = name; node.visible = false; bodies.set(name, node); root.add(node);}
    return bodies.get(name);
  };
  for (const spec of payload.meshes) {
    if (!Array.isArray(spec.vertices) || spec.vertices.length < 9 || spec.vertices.length % 3 ||
        !spec.vertices.every(Number.isFinite) || !Array.isArray(spec.faces) || spec.faces.length % 3 ||
        !spec.faces.every(i => Number.isInteger(i) && i >= 0 && i < spec.vertices.length / 3)) throw Error('Invalid physical boat mesh');
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(spec.vertices, 3)); geometry.setIndex(spec.faces);
    if (Array.isArray(spec.normals) && spec.normals.length === spec.vertices.length && spec.normals.every(Number.isFinite)) geometry.setAttribute('normal', new THREE.Float32BufferAttribute(spec.normals, 3));
    else geometry.computeVertexNormals();
    const vertexColors = Array.isArray(spec.vertex_colors) && spec.vertex_colors.length === spec.vertices.length && spec.vertex_colors.every(Number.isFinite);
    if (vertexColors) geometry.setAttribute('color', new THREE.Float32BufferAttribute(spec.vertex_colors, 3));
    const glass = spec.material_role === 'canopy_glass';
    const material = new THREE.MeshStandardMaterial({color: vertexColors ? '#ffffff' : spec.color || '#dfe7ee', vertexColors,
      roughness: glass ? .18 : .48, metalness: .15, transparent: glass, opacity: glass ? .65 : 1, side: THREE.DoubleSide});
    const mesh = new THREE.Mesh(geometry, material); mesh.name = spec.name || spec.body;
    if (finiteArray(spec.offset, 3)) mesh.position.set(...spec.offset);
    mesh.castShadow = true; mesh.receiveShadow = true; body(spec.body || 'airframe').add(mesh);
  }
  for (const spec of payload.boxes || []) {
    if (!finiteArray(spec.half, 3) || !finiteArray(spec.pos, 3)) throw Error('Invalid physical boat box');
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...spec.half.map(x => 2 * x)), new THREE.MeshStandardMaterial({color: spec.color || '#dfe7ee', roughness: .5}));
    mesh.name = spec.name; mesh.position.set(...spec.pos);
    if (finiteArray(spec.euler_deg, 3)) mesh.rotation.set(...spec.euler_deg.map(THREE.MathUtils.degToRad));
    mesh.castShadow = true; body(spec.body || 'airframe').add(mesh);
  }
  return {root, bodies, geometrySha256: payload.geometry_sha256};
}

const previousPosition = new THREE.Vector3(), previousRotation = new THREE.Quaternion();

export function applyBoatPoses(rig, poses, previous = null, fraction = 1) {
  const missing = [];
  for (const [name, node] of rig.bodies) {
    const pose = poses?.[name], p = pose?.position || pose?.position_world_m, q = pose?.quaternion_wxyz;
    const valid = finiteArray(p, 3) && finiteArray(q, 4) && Math.abs(Math.hypot(...q) - 1) < .01;
    node.visible = valid;
    if (!valid) {missing.push(name); continue;}
    node.position.set(...p); node.quaternion.set(q[1], q[2], q[3], q[0]).normalize();
    const before = previous?.[name], bp = before?.position || before?.position_world_m, bq = before?.quaternion_wxyz;
    if (fraction < 1 && finiteArray(bp, 3) && finiteArray(bq, 4) && Math.abs(Math.hypot(...bq) - 1) < .01) {
      node.position.lerp(previousPosition.fromArray(bp), 1 - fraction);
      node.quaternion.slerp(previousRotation.set(bq[1], bq[2], bq[3], bq[0]).normalize(), 1 - fraction);
    }
  }
  return missing;
}

function disposeTree(root) {
  const geometries = new Set(), materials = new Set();
  root.traverse(node => {if (node.geometry) geometries.add(node.geometry); for (const material of [].concat(node.material || [])) materials.add(material);});
  geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose());
  root.removeFromParent();
}

export function buildHarbour(world, {fetchModel, onError = () => {}} = {}) {
  if (!world?.harbour?.layout?.outer) return null;
  const harbour = world.harbour, root = new THREE.Group(); root.name = 'airport-harbour';
  const water = new THREE.Mesh(harbourWaterGeometry(harbour), new THREE.MeshPhysicalMaterial({color: '#2f8296', roughness: .23,
    metalness: .08, side: THREE.DoubleSide}));
  water.name = 'harbour-water'; water.position.z = harbour.waterLevelM; water.receiveShadow = true; root.add(water);
  const routes = new THREE.Group(); routes.name = 'harbour-routes'; root.add(routes);
  for (const [index, route] of (harbour.layout.routes || []).entries()) {
    const color = ['#efd48b', '#a4ddd2', '#b9b7ee'][index % 3];
    const points = route.points.map(point => new THREE.Vector3(...harbourWorldPoint(harbour, point), harbour.waterLevelM + .12));
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineDashedMaterial({color, dashSize: 10, gapSize: 8, transparent: true, opacity: .7}));
    line.computeLineDistances(); line.name = `harbour-route-${route.id}`; routes.add(line);
    for (const stop of route.stops || []) {
      const point = route.points[stop.index]; if (!point) continue;
      const mark = new THREE.Mesh(new THREE.RingGeometry(3, 4, 20), new THREE.MeshBasicMaterial({color, side: THREE.DoubleSide}));
      mark.position.set(...harbourWorldPoint(harbour, point), harbour.waterLevelM + .13); mark.name = `harbour-stop-${route.id}-${stop.index}`; routes.add(mark);
    }
  }
  const structures = new THREE.Group(), structureNodes = new Map(); structures.name = 'harbour-structures'; root.add(structures);
  const addBox = (id, center, length, width, heading, top = harbour.waterLevelM + 1.2, height = 1.2) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({color: '#b8a17d', roughness: .85}));
    mesh.name = `harbour-structure-${id}`; mesh.position.set(...center, top - height / 2); mesh.rotation.z = heading; mesh.scale.set(length, width, height);
    mesh.castShadow = true; mesh.receiveShadow = true; structures.add(mesh); structureNodes.set(id, mesh); return mesh;
  };
  // Same immutable box contract as HarbourWorld; runtime snapshots below also
  // provide authoritative world centers/extents for restored water settings.
  for (const pier of harbour.docks?.piers || []) addBox(pier.id, harbourWorldPoint(harbour, pier.center), pier.length, pier.width, -pier.heading);
  for (const path of harbour.docks?.access || []) for (let i = 1; i < path.points.length; i++) {
    const a = path.points[i - 1], b = path.points[i];
    addBox(`${path.id}-${i - 1}`, harbourWorldPoint(harbour, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]),
      Math.hypot(b[0] - a[0], b[1] - a[1]), path.width, -Math.atan2(b[1] - a[1], b[0] - a[0]));
  }
  if (harbour.accessPath?.length > 1) {
    const vertices = harbour.accessPath.map(([x, y]) => new THREE.Vector3(x, y, worldSurface(world, x, y) + .05));
    const path = new THREE.Line(new THREE.BufferGeometry().setFromPoints(vertices), new THREE.LineBasicMaterial({color: '#d8c0a2'}));
    path.name = 'airport-harbour-walkway'; root.add(path);
  }
  const berthNodes = new Map();
  for (const berth of harbour.docks?.berths || []) {
    const mark = new THREE.Mesh(new THREE.RingGeometry(2, 2.6, 24), new THREE.MeshBasicMaterial({color: '#8ce3c8', side: THREE.DoubleSide}));
    mark.position.set(...harbourWorldPoint(harbour, [berth.x, berth.y]), harbour.waterLevelM + .14);
    mark.name = `harbour-berth-${berth.id}`; root.add(mark); berthNodes.set(berth.id, mark);
  }
  const boats = new Map(), pending = new Map(), retryAt = new Map(); let disposed = false, latest = null, boatsVisible = true;
  const boatIdentity = boat => `${boat.variant}:${boat.configuration?.geometry_sha256 || ''}:${boat.configuration?.model_xml_sha256 || ''}`;
  const load = async boat => {
    if (!fetchModel || pending.has(boat.id) || Date.now() < (retryAt.get(boat.id) || 0)) return;
    const identity = boatIdentity(boat);
    pending.set(boat.id, identity);
    try {
      const geometry = await fetchModel(boat.id);
      if (disposed || pending.get(boat.id) !== identity || !(latest?.boats || []).some(b => b.id === boat.id && boatIdentity(b) === identity)) return;
      if (boat.configuration?.geometry_sha256 && geometry.geometry_sha256 !== boat.configuration.geometry_sha256) throw Error('Boat geometry differs from physical identity');
      const rig = buildBoatRig(geometry); rig.root.name = `harbour-boat-${boat.id}`; rig.identity = identity;
      const previous = boats.get(boat.id); if (previous) disposeTree(previous.root);
      boats.set(boat.id, rig); root.add(rig.root);
      const current = latest.boats.find(b => b.id === boat.id);
      rig.poses = current.body_poses;
      applyBoatPoses(rig, rig.poses); rig.root.visible = boatsVisible && !!latest?.available;
    } catch (error) {retryAt.set(boat.id, Date.now() + 5000); if (!disposed) onError(boat.id, error);}
    finally {if (pending.get(boat.id) === identity) pending.delete(boat.id);}
  };
  return {
    root, water, routes, boats, berthNodes, structureNodes,
    update(state, {snap = false, now = performance.now()} = {}) {
      const advancing = latest?.available && latest.generation === state?.generation &&
        Number.isFinite(latest.t_s) && state?.t_s > latest.t_s;
      latest = state;
      if (Number.isFinite(state?.water_level_m)) {
        water.position.z = state.water_level_m; routes.position.z = state.water_level_m - harbour.waterLevelM;
        for (const mark of berthNodes.values()) mark.position.z = state.water_level_m + .14;
      }
      for (const spec of state?.structures || []) {
        if (!finiteArray(spec.center, 3) || !finiteArray(spec.half_extents, 3) || !Number.isFinite(spec.yaw_deg)) continue;
        const node = structureNodes.get(spec.id) || addBox(spec.id, spec.center.slice(0, 2), 1, 1, 0);
        node.position.set(...spec.center); node.scale.set(...spec.half_extents.map(v => 2 * v)); node.rotation.z = THREE.MathUtils.degToRad(spec.yaw_deg);
      }
      const ids = new Set((state?.boats || []).map(b => b.id));
      for (const [id, rig] of boats) if (!ids.has(id)) {disposeTree(rig.root); boats.delete(id);}
      for (const boat of state?.boats || []) {
        const rig = boats.get(boat.id), identity = boatIdentity(boat);
        if (!state.available) {if (rig) rig.root.visible = false; continue;}
        if (!rig || rig.identity !== identity) {if (rig) rig.root.visible = false; void load(boat);}
        else {
          const interval = now - rig.receivedAt;
          rig.previous = !snap && advancing && interval > 0 && interval < 300 ? rig.poses : null;
          rig.poses = boat.body_poses; rig.receivedAt = now; rig.interval = interval;
          rig.missingBodies = applyBoatPoses(rig, rig.poses, rig.previous, rig.previous ? 0 : 1);
          rig.root.visible = boatsVisible && state.available;
        }
      }
      for (const [id, mark] of berthNodes) mark.material.color.set(state?.occupancy?.[id] ? '#e5b56d' : '#8ce3c8');
    },
    animate(now) {
      for (const rig of boats.values()) {
        if (!rig.previous || !rig.root.visible) continue;
        const fraction = THREE.MathUtils.clamp((now - rig.receivedAt) / rig.interval, 0, 1);
        applyBoatPoses(rig, rig.poses, rig.previous, fraction);
        if (fraction === 1) rig.previous = null;
      }
    },
    setBoatsVisible(visible) {boatsVisible = visible; for (const rig of boats.values()) rig.root.visible = visible && !!latest?.available;},
    setRoutesVisible(visible) {routes.visible = !!visible;},
    dispose() {disposed = true; pending.clear(); disposeTree(root); boats.clear();},
  };
}

function worldSurface(world, x, y) {
  const heights = world.heights_m, n = heights?.length, half = world.half_m;
  if (!n || !Number.isFinite(half)) return 0;
  const u = THREE.MathUtils.clamp((x + half) / (2 * half) * (n - 1), 0, n - 1.000001), v = THREE.MathUtils.clamp((y + half) / (2 * half) * (n - 1), 0, n - 1.000001);
  const i = Math.floor(u), j = Math.floor(v), a = u - i, b = v - j;
  return a > b ? (1 - a) * heights[j][i] + (a - b) * heights[j][i + 1] + b * heights[j + 1][i + 1]
    : (1 - b) * heights[j][i] + (b - a) * heights[j + 1][i] + a * heights[j + 1][i + 1];
}

export function createHarbourControls({host, api, toast = () => {}, onState = () => {}, onFocus = () => {}, onRoutes = () => {}, document: doc = globalThis.document}) {
  const panel = doc.createElement('details'); panel.id = 'harbour-panel'; panel.className = 'harbour-panel'; panel.hidden = true;
  panel.innerHTML = `<summary>Airport harbour · boats and docks</summary>
    <p class="harbour-intro">Choose a boat, then approach a free berth slowly and align with it.</p>
    <div class="harbour-actions"><button type="button" data-harbour="activate">Initialize two Concept A boats</button><button type="button" data-harbour="lake">View harbour</button></div>
    <label>Boat<select data-harbour="boat"><option value="">Choose a boat</option></select></label>
    <p data-harbour="telemetry" class="harbour-readout">No boat selected.</p>
    <button type="button" data-harbour="focus">View selected boat</button>
    <label>Berth<select data-harbour="berth"><option value="">Choose a berth</option></select></label>
    <div class="harbour-actions"><button type="button" data-harbour="dock">Dock at berth</button><button type="button" data-harbour="undock">Release mooring</button></div>
    <fieldset><legend>Helm</legend>
      <label>Throttle <output data-value="throttle">0%</output><input data-command="throttle" aria-label="Boat throttle" type="range" min="0" max="1" step=".01" value="0"></label>
      <label>Rudder <output data-value="rudder_deg">0°</output><input data-command="rudder_deg" aria-label="Boat rudder angle" type="range" min="-30" max="30" step=".5" value="0"></label>
      <label>Reverse bucket <output data-value="reverse_bucket">0%</output><input data-command="reverse_bucket" aria-label="Boat reverse bucket" type="range" min="0" max="1" step=".05" value="0"></label>
      <button type="button" data-harbour="cut">Cut throttle</button>
      <details><summary>Surface trim</summary>
        <label>Differential thrust <output data-value="differential_thrust">0%</output><input data-command="differential_thrust" aria-label="Boat differential thrust" type="range" min="-1" max="1" step=".02" value="0"></label>
        <label>Elevator <output data-value="elevator_deg">0°</output><input data-command="elevator_deg" aria-label="Boat elevator angle" type="range" min="-20" max="20" step=".5" value="0"></label>
        <label>Ailerons <output data-value="aileron_deg">0°</output><input data-command="aileron_deg" aria-label="Boat aileron angle" type="range" min="-25" max="25" step=".5" value="0"></label>
      </details>
    </fieldset>
    <label class="harbour-route-toggle"><input type="checkbox" data-harbour="routes" checked> Show marked boat routes</label>
    <div class="harbour-actions"><button type="button" data-harbour="save">Save harbour</button><button type="button" data-harbour="restore">Restore saved harbour</button></div>
    <p data-harbour="status" class="harbour-message" role="status" aria-live="polite">Harbour unavailable.</p>`;
  if (!doc.getElementById('harbour-style')) {
    const style = doc.createElement('style'); style.id = 'harbour-style';
    style.textContent = `.harbour-panel{margin:1rem 0;padding:.8rem;border:1px solid #5b8276;border-radius:.6rem;background:#152d28;color:#e6f0e8;max-width:100%;box-sizing:border-box}.harbour-panel[hidden]{display:none!important}.harbour-panel>summary{cursor:pointer;font-weight:650;line-height:1.4}.harbour-panel p{font-size:.82rem;line-height:1.45;margin:.6rem 0}.harbour-panel label{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.3rem;margin:.65rem 0;font-size:.85rem}.harbour-panel select,.harbour-panel input[type=range]{grid-column:1/-1;width:100%;min-width:0;box-sizing:border-box}.harbour-panel select{white-space:nowrap;text-overflow:ellipsis}.harbour-panel button{max-width:100%;min-width:0;white-space:normal;line-height:1.3}.harbour-panel fieldset{margin:.8rem 0;padding:.5rem .7rem;border:1px solid #56766b;min-width:0;border-radius:.4rem}.harbour-panel legend{font-size:.85rem;padding:0 .3rem}.harbour-panel details details{margin:.7rem 0}.harbour-panel .harbour-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.4rem;margin:.6rem 0}.harbour-panel .harbour-route-toggle{display:flex;align-items:center;gap:.4rem}.harbour-panel .harbour-route-toggle input{width:auto}.harbour-readout{font-variant-numeric:tabular-nums}.harbour-message{min-height:2.4em;color:#c4dbcf}.harbour-panel button:disabled,.harbour-panel input:disabled,.harbour-panel select:disabled{opacity:.5}@media(max-width:420px){.harbour-panel{padding:.65rem}.harbour-panel .harbour-actions{gap:.3rem}.harbour-panel button{font-size:.78rem;padding:.5rem .35rem}}`;
    doc.head.append(style);
  }
  host.append(panel);
  const el = name => panel.querySelector(`[data-harbour="${name}"]`), fields = [...panel.querySelectorAll('[data-command]')];
  let world = null, state = null, enabled = false, disposed = false, pendingActions = 0, pendingGets = 0;
  let revision = 0, worldEpoch = 0, lastSuccess = 0, status = '', helmTimer = null, helmBoat = null, helmPatch = {}, chain = Promise.resolve();
  const dirty = new Map();
  const selected = () => state?.boats?.find(boat => boat.id === state.selectedId);
  const ready = () => enabled && state?.available && !state.error && state?.initialized !== false && (state?.boats?.length || 0) > 0 && Date.now() - lastSuccess < 2000;
  const format = (key, value) => key.endsWith('_deg') ? `${value.toFixed(1)}°` : `${Math.round(value * 100)}%`;
  const option = (value, text, disabled = false) => {const node = doc.createElement('option'); node.value = value; node.textContent = text; node.disabled = disabled; return node;};
  const setOptions = (select, options, value) => {
    const signature = options.map(o => `${o.value}:${o.textContent}:${o.disabled}`).join('|');
    if (select.dataset.options !== signature) {select.replaceChildren(...options); select.dataset.options = signature;}
    select.value = value || '';
  };
  const render = () => {
    panel.hidden = !world?.harbour;
    if (panel.hidden) return;
    const boat = selected(), busy = pendingActions > 0, live = ready() && !busy;
    setOptions(el('boat'), [option('', 'Choose a boat'), ...(state?.boats || []).map(b => option(b.id, b.name || b.variant || b.id))], state?.selectedId);
    const berthChoice = el('berth').value;
    setOptions(el('berth'), [option('', 'Choose a berth'), ...(state?.berths || []).map(b => {
      const owner = b.occupiedBy || state?.occupancy?.[b.id], ownerName = state?.boats?.find(c => c.id === owner)?.name || owner;
      const compatible = !boat || !b.compatibleProfileIds?.length || b.compatibleProfileIds.includes(boat.variant);
      return option(b.id, `${b.name || b.id}${owner ? ` · ${ownerName}` : ''}${!compatible ? ' · size not compatible' : ''}`, !!(owner && owner !== boat?.id) || !compatible);
    })], berthChoice);
    el('boat').disabled = !live;
    el('berth').disabled = !live || !boat;
    el('activate').hidden = !!state?.initialized || (state?.boats?.length || 0) > 0;
    el('activate').disabled = !enabled || !state?.available || busy;
    el('dock').disabled = !live || !boat || !!boat.dockedAt || !el('berth').value;
    el('undock').disabled = !live || !boat?.dockedAt;
    el('focus').disabled = !boat || !finiteArray(boat.position, 3);
    el('lake').disabled = !world?.harbour;
    el('cut').disabled = !live || !boat;
    el('save').disabled = !live;
    el('restore').disabled = !enabled || !state?.available || !state.saved || busy;
    for (const input of fields) {
      const key = input.dataset.command;
      input.disabled = !ready() || !boat;
      if (!dirty.has(key) && doc.activeElement !== input && Number.isFinite(boat?.command?.[key])) input.value = String(boat.command[key]);
      panel.querySelector(`[data-value="${key}"]`).textContent = format(key, Number(input.value));
    }
    el('telemetry').textContent = boat ? `${boat.name || boat.id} · ${Number.isFinite(boat.speed_mps) ? boat.speed_mps.toFixed(2) + ' m/s' : 'speed unavailable'} · ${boat.dockedAt ? 'Moored at ' + (state.berths?.find(b => b.id === boat.dockedAt)?.name || boat.dockedAt) : 'Under way'}` : 'No boat selected.';
    el('status').textContent = !enabled ? 'Boat controls are unavailable in this view.' : state?.error ? 'Harbour stopped: ' + state.error : Date.now() - lastSuccess >= 2000 && state?.initialized ? 'Harbour data is stale. Controls unavailable.' : status || (state?.initialized ? 'Boat positions and moorings are retained when you switch boats.' : 'Initialize the two boats to use the harbour.');
  };
  const refresh = async ({snap = false} = {}) => {
    if (!enabled || !world?.harbour || disposed) return;
    const ticket = ++revision; pendingGets++;
    try {
      const next = await api('/api/harbour');
      if (ticket !== revision || disposed || !enabled) return;
      state = next; lastSuccess = Date.now(); onState(state, {snap}); render();
    } catch (error) {
      if (ticket === revision) {status = 'Harbour unavailable: ' + error.message; render();}
    } finally {pendingGets--;}
  };
  const send = payload => {
    const epoch = worldEpoch;
    chain = chain.catch(() => {}).then(async () => {
      if (!enabled || disposed || epoch !== worldEpoch) return;
      pendingActions++; render();
      try {
        const response = await api('/api/harbour/action', payload);
        if (response?.ok === false) throw Error(response.reason || 'Harbour action refused');
        status = response?.reason || ({save: 'Harbour saved.', restore: 'Saved harbour restored.', dock: 'Mooring secured.', undock: 'Mooring released.'}[payload.action] || '');
        await refresh({snap: payload.action === 'restore' || payload.action === 'dock'});
      } catch (error) {status = error.message; toast(error.message);}
      finally {pendingActions--; render();}
    });
    return chain;
  };
  const discardHelm = () => {
    clearTimeout(helmTimer); helmTimer = null; helmPatch = {}; helmBoat = null; dirty.clear();
  };
  const flushHelm = () => {
    clearTimeout(helmTimer); helmTimer = null;
    if (!helmBoat || !Object.keys(helmPatch).length) return chain;
    const command = helmPatch, boatId = helmBoat, versions = new Map([...dirty]); helmPatch = {}; helmBoat = null;
    return send({action: 'command', boatId, command}).finally(() => {
      for (const key of Object.keys(command)) if (dirty.get(key) === versions.get(key)) dirty.delete(key);
      render();
    });
  };
  for (const input of fields) input.addEventListener('input', () => {
    const boat = selected(); if (!boat || !ready()) return;
    if (helmBoat && helmBoat !== boat.id) flushHelm();
    const key = input.dataset.command; helmBoat = boat.id; helmPatch[key] = Number(input.value); dirty.set(key, (dirty.get(key) || 0) + 1);
    panel.querySelector(`[data-value="${key}"]`).textContent = format(key, Number(input.value));
    if (helmTimer === null) helmTimer = setTimeout(flushHelm, 60);
  });
  el('boat').addEventListener('change', () => {flushHelm(); if (el('boat').value) void send({action: 'select', boatId: el('boat').value});});
  el('berth').addEventListener('change', render);
  el('activate').addEventListener('click', () => void send({action: 'activate'}));
  el('dock').addEventListener('click', () => {flushHelm(); void send({action: 'dock', boatId: state.selectedId, berthId: el('berth').value});});
  el('undock').addEventListener('click', () => void send({action: 'undock', boatId: state.selectedId}));
  el('cut').addEventListener('click', () => {flushHelm(); void send({action: 'command', boatId: state.selectedId, command: {throttle: 0}});});
  el('save').addEventListener('click', () => {flushHelm(); void send({action: 'save'});});
  el('restore').addEventListener('click', () => {discardHelm(); void send({action: 'restore'});});
  el('focus').addEventListener('click', () => {const boat = selected(); if (boat) onFocus(boat.position, 'boat');});
  el('lake').addEventListener('click', () => {
    const h = world.harbour; onFocus([...harbourWorldPoint(h, [2200, 1300]), h.waterLevelM], 'harbour');
  });
  el('routes').addEventListener('change', () => onRoutes(el('routes').checked));
  panel.addEventListener('keydown', event => event.stopPropagation());
  panel.addEventListener('keyup', event => event.stopPropagation());
  const timer = setInterval(() => {
    if (!pendingGets && !pendingActions && (state?.initialized || Date.now() - lastSuccess >= 1000)) void refresh();
    if (state && Date.now() - lastSuccess >= 2000) {onState({...state, available: false}); render();}
  }, 100);
  return {
    panel, refresh, get state() {return enabled && Date.now() - lastSuccess < 2000 ? state : null;},
    setWorld(next) {worldEpoch++; revision++; discardHelm(); world = next; state = null; status = ''; lastSuccess = 0; onRoutes(el('routes').checked); render(); if (enabled) void refresh();},
    setEnabled(next) {if (enabled === !!next) return; enabled = !!next; revision++; if (!enabled) {worldEpoch++; discardHelm(); onState(null);} else void refresh(); render();},
    dispose() {disposed = true; revision++; clearInterval(timer); clearTimeout(helmTimer); panel.remove();},
  };
}
