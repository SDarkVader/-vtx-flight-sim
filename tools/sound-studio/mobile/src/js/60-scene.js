// =====================================================================================
// SCENE BENCH: ambience as looping beds and random one-shots, with crossfades between scenes
// =====================================================================================
const uid = () => Math.random().toString(36).slice(2, 8);
const GAPS = [0.5, 1, 2, 3, 4, 6, 8, 12, 20, 30, 60];
const FADES = [0.25, 0.5, 1, 2, 3, 5, 8, 12];
const SCENE_LENS = [10, 20, 30, 60, 90, 120];
const LD = {
  level: { label: 'Level', min: -48, max: 6, step: 1, fine: 0.1, fmt: fmtDb, def: -12 },
  pitch: { label: 'Pitch', min: 0.5, max: 2, step: 0.05, fine: 0.01, fmt: v => round(v, 2) + 'x', def: 1 },
  pan: { label: 'Pan', min: -1, max: 1, step: 0.1, fine: 0.02, fmt: panText, def: 0 },
  gMin: { label: 'Gap min', list: GAPS, text: GAPS.map(g => g + ' s'), def: 4 },
  gMax: { label: 'Gap max', list: GAPS, text: GAPS.map(g => g + ' s'), def: 7 },
  pitchRand: { label: 'Pitch drift', min: 0, max: 50, step: 5, fine: 1, fmt: v => '±' + v + '%', def: 10 },
  levelRand: { label: 'Level drift', min: 0, max: 12, step: 1, fine: 0.5, fmt: v => '±' + v + ' dB', def: 3 },
  spread: { label: 'Spread', min: 0, max: 1, step: 0.05, fine: 0.01, fmt: pct, def: 0.6 },
};
const SD_LEVEL = { label: 'Scene level', min: -24, max: 6, step: 1, fine: 0.1, fmt: fmtDb, def: 0 };
const SD_FADE = { label: 'Fade', list: FADES, text: FADES.map(f => f + ' s'), def: 3 };
const SD_LEN = { label: 'Bounce length', list: SCENE_LENS, text: SCENE_LENS.map(s => s + ' s'), def: 2 };
const newScene = (name = 'Airfield') => ({ id: uid(), name, level: 0, fade: 3, len: 2, seed: (Math.random() * 2 ** 31) | 0, layers: [] });
const newLayer = take => ({ id: uid(), take, mode: 'loop', on: true, level: -12, pitch: 1, pan: 0, smooth: true, gMin: 4, gMax: 7, pitchRand: 10, levelRand: 3, spread: 0.6 });
const scenes = Array.isArray(saved.scenes) && saved.scenes.length ? saved.scenes.map(s => Object.assign(newScene(), s, { layers: (s.layers || []).map(l => Object.assign(newLayer(''), l)) })) : [newScene()];
let sceneIdx = clamp(saved.sceneIdx | 0, 0, scenes.length - 1);
const running = new Map();   // scene id -> running handle
const cur = () => scenes[sceneIdx];
function mulberry32(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// ---------- running a scene ----------
async function startScene(scene) {
  audio();
  const fade = FADES[scene.fade];
  for (const h of [...running.values()]) if (h.scene.id !== scene.id) stopHandle(h, fade);   // crossfade from whatever is playing
  if (running.has(scene.id)) return;
  const h = { scene, alive: true, timers: new Set(), sources: new Set(), layers: new Map(), out: ctx.createGain(), rng: mulberry32((Math.random() * 2 ** 32) >>> 0) };
  running.set(scene.id, h);
  const t = ctx.currentTime;
  h.out.gain.setValueAtTime(0, t); h.out.gain.linearRampToValueAtTime(dbToLin(scene.level), t + fade);
  h.out.connect(ambBus);
  sceneButtons();
  for (const layer of scene.layers) if (layer.on && layer.take) await startLayer(h, layer);
}
function stopHandle(h, fade = FADES[h.scene.fade]) {
  if (!h.alive) return;
  h.alive = false; running.delete(h.scene.id);
  h.timers.forEach(clearTimeout); h.timers.clear();
  const t = ctx.currentTime;
  h.out.gain.cancelScheduledValues(t); h.out.gain.setValueAtTime(h.out.gain.value, t); h.out.gain.linearRampToValueAtTime(0, t + fade);
  setTimeout(() => { for (const s of h.sources) { try { s.stop(); } catch {} } try { h.out.disconnect(); } catch {} }, (fade + 0.3) * 1000);
  sceneButtons();
}
function stopScenes() { for (const h of [...running.values()]) stopHandle(h); }
async function startLayer(h, layer) {
  if (!h.alive || !layer.take || !takes.has(layer.take)) return;
  const pan = makePanner(ctx), g = ctx.createGain();
  pan.set(layer.pan);
  g.gain.value = dbToLin(layer.level); g.connect(pan.input); pan.output.connect(h.out);
  const rec = { g, pan, layer };
  h.layers.set(layer.id, rec);
  if (layer.mode === 'loop') {
    let src;
    try { src = await loopSource(layer.take, layer.smooth); } catch { say('Could not read ' + layer.take); return; }
    if (!h.alive || h.layers.get(layer.id) !== rec || !src) return;
    const node = ctx.createBufferSource();
    node.buffer = src.buffer; node.loop = true; node.loopStart = src.start; node.loopEnd = src.end; node.playbackRate.value = layer.pitch;
    node.connect(g); node.start(); h.sources.add(node); rec.node = node;
  } else {
    let buf;
    try { buf = await bufferOf(layer.take); } catch { say('Could not read ' + layer.take); return; }
    if (!h.alive || h.layers.get(layer.id) !== rec || !buf) return;
    const b = body(buf);
    const fire = () => {
      const t = ctx.currentTime, node = ctx.createBufferSource(), eg = ctx.createGain(), ep = makePanner(ctx);
      const r = () => h.rng() * 2 - 1;
      node.buffer = buf; node.playbackRate.value = layer.pitch * (1 + r() * layer.pitchRand / 100);
      eg.gain.value = dbToLin(r() * layer.levelRand) * (b.baked ? 1 : b.boost);
      ep.set(clamp(layer.pan + r() * layer.spread, -1, 1));
      node.connect(eg); eg.connect(ep.input); ep.output.connect(g);
      node.start(t, b.from, Math.max(0.05, b.to - b.from)); h.sources.add(node);
      node.onended = () => { h.sources.delete(node); try { ep.output.disconnect(); } catch {} };
    };
    const next = () => {
      if (!h.alive || h.layers.get(layer.id) !== rec) return;
      const lo = GAPS[layer.gMin], hi = Math.max(lo, GAPS[layer.gMax]), wait = lo + h.rng() * (hi - lo);
      const id = setTimeout(() => { h.timers.delete(id); if (!h.alive || h.layers.get(layer.id) !== rec) return; fire(); next(); }, wait * 1000);
      h.timers.add(id);
    };
    next();
  }
}
function stopLayer(h, id) {
  const rec = h.layers.get(id);
  if (!rec) return;
  h.layers.delete(id);
  const t = ctx.currentTime;
  rec.g.gain.cancelScheduledValues(t); rec.g.gain.setTargetAtTime(0, t, 0.08);
  setTimeout(() => { try { rec.node?.stop(); } catch {} try { rec.g.disconnect(); } catch {} }, 400);
}
function layerLive(layer) {   // push a dial change to the layer if its scene is playing
  const h = running.get(cur().id), rec = h?.layers.get(layer.id);
  if (!rec) return;
  const t = ctx.currentTime;
  rec.g.gain.setTargetAtTime(dbToLin(layer.level), t, 0.05);
  rec.pan.set(layer.pan, t, 0.05);
  rec.node?.playbackRate.setTargetAtTime(layer.pitch, t, 0.05);
}
function layerRestart(layer) {
  const h = running.get(cur().id);
  if (!h) return;
  stopLayer(h, layer.id);
  if (layer.on && layer.take) startLayer(h, layer);
}

// ---------- the bench ----------
function sceneButtons() {
  const b = $('sceneGo');
  if (!b) return;
  const on = running.has(cur().id);
  b.textContent = on ? 'Stop scene' : 'Start scene'; b.classList.toggle('on-air', on); b.setAttribute('aria-pressed', on);
}
function renderScene() {
  const w = $('sceneWrap');
  if (!w) return;
  const sc = cur(), card = (title, ...kids) => el('div', { className: 'card' }, ...(title ? [el('h2', { textContent: title })] : []), ...kids);
  const names = el('select', { id: 'sceneSel', ariaLabel: 'Scene' }, ...scenes.map((s, i) => el('option', { value: i, textContent: s.name })));
  names.value = sceneIdx;
  names.onchange = () => { sceneIdx = +names.value; persist(); renderScene(); };
  const nameBox = el('input', { type: 'text', value: sc.name, ariaLabel: 'Scene name', maxLength: 40 });
  nameBox.oninput = () => { sc.name = nameBox.value || 'Scene'; names.options[sceneIdx].textContent = sc.name; persist(); };
  const go = el('button', { className: 'btn go', id: 'sceneGo' });
  go.onclick = () => running.has(sc.id) ? stopHandle(running.get(sc.id)) : startScene(sc);
  const add = el('button', { className: 'btn', textContent: 'New scene', onclick: () => { scenes.push(newScene('Scene ' + (scenes.length + 1))); sceneIdx = scenes.length - 1; persist(); renderScene(); } });
  const del = el('button', { className: 'btn warn', textContent: 'Delete scene' });
  del.onclick = () => {
    if (scenes.length < 2) { say('Keep at least one scene.'); return; }
    if (del.dataset.sure !== '1') { del.dataset.sure = '1'; del.textContent = 'Tap again to delete'; setTimeout(() => { del.dataset.sure = ''; del.textContent = 'Delete scene'; }, 3000); return; }
    if (running.has(sc.id)) stopHandle(running.get(sc.id), 0.1);
    scenes.splice(sceneIdx, 1); sceneIdx = Math.max(0, sceneIdx - 1); persist(); renderScene();
  };
  const lvl = dialFor(SD_LEVEL, sc.level, v => { sc.level = v; const h = running.get(sc.id); if (h) h.out.gain.setTargetAtTime(dbToLin(v), ctx.currentTime, 0.1); persist(); }, 76);
  const fade = dialFor(SD_FADE, sc.fade, v => { sc.fade = v; persist(); }, 76);
  const layersCard = card('Layers');
  if (!sc.layers.length) layersCard.append(el('p', { className: 'note', textContent: takes.size ? 'No layers yet. Add one, pick a take, choose Loop for a bed or Random for one-shots such as distant calls.' : 'Add takes on the Takes bench, then build layers here.' }));
  for (const layer of sc.layers) layersCard.append(layerCard(sc, layer));
  const addLayer = el('button', { className: 'btn go', textContent: 'Add layer', style: 'margin-top:12px' });
  addLayer.onclick = () => { if (!takes.size) { say('Add some takes first.'); return; } const used = new Set(sc.layers.map(l => l.take)); sc.layers.push(newLayer([...takes.keys()].sort().find(n => !used.has(n)) || [...takes.keys()][0])); persist(); renderScene(); const h = running.get(sc.id); if (h) startLayer(h, sc.layers[sc.layers.length - 1]); };
  layersCard.append(addLayer);
  const len = dialFor(SD_LEN, sc.len, v => { sc.len = v; persist(); }, 76);
  const reroll = el('button', { className: 'btn', textContent: 'New variation', onclick: () => { sc.seed = (Math.random() * 2 ** 31) | 0; persist(); say('Random layers will fall differently in the next bounce.'); } });
  const bounce = el('button', { className: 'btn go', textContent: 'Bounce scene WAV', onclick: e => bounceScene(sc, e.currentTarget) });
  w.replaceChildren(
    card('Scene', el('div', { className: 'bar' }, names, add), el('div', { style: 'margin-top:8px' }, nameBox),
      el('div', { className: 'dials row2', style: 'margin-top:12px' }, lvl.root, fade.root),
      el('div', { className: 'bar', style: 'margin-top:12px' }, go, del),
      el('p', { className: 'note', textContent: 'Starting another scene crossfades from the one playing, over the Fade time. Scenes play through the Ambience strip on the Mix bench.' })),
    layersCard,
    card('Bounce', el('p', { className: 'note', style: 'margin:0 0 10px', textContent: 'Prints the scene through the Ambience strip and the master, so you hear what the Mix bench makes. The same variation gives the same file.' }),
      el('div', { className: 'dials row2' }, len.root), el('div', { className: 'bar', style: 'margin-top:12px' }, reroll, bounce)));
  sceneButtons();
}
function layerCard(sc, layer) {
  const names = [...takes.keys()].sort();
  const take = el('select', { ariaLabel: 'Take for layer' }, ...(takes.has(layer.take) ? [] : [el('option', { value: layer.take, textContent: takeLabel(layer.take) || 'Choose a take' })]), ...names.map(n => el('option', { value: n, textContent: takeLabel(n) })));
  take.value = layer.take;
  take.onchange = () => { layer.take = take.value; persist(); layerRestart(layer); };
  const on = el('button', { className: 'chip', textContent: 'On' }); on.setAttribute('aria-pressed', layer.on);
  on.onclick = () => { layer.on = !layer.on; on.setAttribute('aria-pressed', layer.on); persist(); layerRestart(layer); };
  const mode = el('div', { className: 'seg' }, ...['loop', 'random'].map(m => { const b = el('button', { textContent: m === 'loop' ? 'Loop' : 'Random', onclick: () => { layer.mode = m; persist(); layerRestart(layer); renderScene(); } }); b.setAttribute('aria-pressed', layer.mode === m); return b; }));
  const del = el('button', { className: 'btn warn', textContent: 'Remove' });
  del.onclick = () => {
    if (del.dataset.sure !== '1') { del.dataset.sure = '1'; del.textContent = 'Tap again'; setTimeout(() => { del.dataset.sure = ''; del.textContent = 'Remove'; }, 3000); return; }
    const h = running.get(sc.id); if (h) stopLayer(h, layer.id);
    sc.layers.splice(sc.layers.indexOf(layer), 1); persist(); renderScene();
  };
  const dial = (k, size = 68) => dialFor(LD[k], layer[k], v => { layer[k] = v; persist(); layerLive(layer); }, size).root;
  const keys = layer.mode === 'loop' ? ['level', 'pitch', 'pan'] : ['level', 'pitch', 'pan', 'gMin', 'gMax', 'pitchRand', 'levelRand', 'spread'];
  const grid = el('div', { className: 'dials' }, ...keys.map(k => dial(k)));
  const extra = [];
  if (layer.mode === 'loop') {
    const sm = el('button', { className: 'chip', textContent: 'Smooth seam' }); sm.setAttribute('aria-pressed', layer.smooth);
    sm.onclick = () => { layer.smooth = !layer.smooth; sm.setAttribute('aria-pressed', layer.smooth); persist(); layerRestart(layer); };
    extra.push(sm);
  }
  return el('div', { className: 'layer' }, el('div', { className: 'bar' }, take, on), mode, grid, el('div', { className: 'bar' }, ...extra, del));
}
renderScene();
