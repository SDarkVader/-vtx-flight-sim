// =====================================================================================
// TRACKS BENCH: transport, drop-down menus, timeline, clip and track inspector, bounces, save points
// =====================================================================================
const TR = {};
const zoomPx = () => ZOOMS[arr.zoom];
const LANE = 64;
const hexA = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };

// ---------- a small drop-down menu ----------
let openMenu = null;
function closeMenus() { if (openMenu) { openMenu.panel.hidden = true; openMenu.btn.setAttribute('aria-expanded', 'false'); openMenu = null; } }
document.addEventListener('pointerdown', e => { if (openMenu && !openMenu.wrap.contains(e.target)) closeMenus(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenus(); });
function menu(label, items) {
  const wrap = el('div', { className: 'menu' }), btn = el('button', { className: 'chip menu-btn', textContent: label });
  const panel = el('div', { className: 'menu-panel', hidden: true }); panel.setAttribute('role', 'menu');
  btn.setAttribute('aria-haspopup', 'menu'); btn.setAttribute('aria-expanded', 'false');
  btn.onclick = () => {
    const was = openMenu?.wrap === wrap; closeMenus(); if (was) return;
    panel.replaceChildren(...items().map(it => {
      if (it === '-') return el('div', { className: 'menu-sep' });
      const b = el('button', { className: 'menu-item', textContent: it.label, disabled: !!it.off }); b.setAttribute('role', 'menuitem');
      b.onclick = () => { closeMenus(); it.run(); }; return b;
    }));
    const r = btn.getBoundingClientRect(); panel.style.left = r.left > innerWidth / 2 ? 'auto' : '0'; panel.style.right = r.left > innerWidth / 2 ? '0' : 'auto';
    panel.hidden = false; btn.setAttribute('aria-expanded', 'true'); openMenu = { wrap, panel, btn };
  };
  wrap.append(btn, panel); return wrap;
}

// ---------- build ----------
function buildTracks() {
  const w = $('tracksWrap'), card = (...k) => el('div', { className: 'card' }, ...k);
  const fileIn = (stems) => { const i = el('input', { type: 'file', multiple: true, accept: 'audio/*,.mp3,.m4a,.wav,.ogg,.flac,.aac', hidden: true }); i.onchange = () => { importFiles([...i.files], { stems }); i.value = ''; }; return i; };
  TR.imp = fileIn(false); TR.stems = fileIn(true);
  // transport
  TR.lcd = el('div', { className: 'lcd tlcd' }, el('div', { className: 'no', id: 'tPos' }), el('div', { className: 'big', id: 'tClock' }));
  const ib = (id, label, glyph, fn) => { const b = el('button', { className: 'ib', id, ariaLabel: label }); b.innerHTML = icon(glyph); b.onclick = fn; return b; };
  TR.play = ib('tPlay', 'Play', 'play', arrToggle);
  const stop = el('button', { className: 'ib', id: 'tStop', ariaLabel: 'Stop and return' }); stop.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M6 6h12v12H6z"/></svg>'; stop.onclick = () => arrStop(true);
  const chip = (label, get, set) => { const c = el('button', { className: 'chip', textContent: label }); c.setAttribute('aria-pressed', get()); c.onclick = () => { set(!get()); c.setAttribute('aria-pressed', get()); persist(); syncTransport(); }; return c; };
  TR.loopChip = chip('Loop', () => arr.loop.on, v => { arr.loop.on = v; if (eng.playing) { arrPause(); arrPlay(); } });
  const dials = el('div', { className: 'dials row3' },
    dialFor({ label: 'Tempo', min: 40, max: 240, step: 1, fine: 0.1, fmt: v => round(v, 1) + ' bpm', def: 120 }, arr.bpm, v => { checkpoint('bpm'); arr.bpm = v; persist(); renderTimeline(); }, 64).root,
    dialFor({ label: 'Snap', list: SNAPS.map(s => s[1]), text: SNAPS.map(s => s[0]), def: 2 }, arr.snap, v => { arr.snap = v; persist(); }, 64).root,
    dialFor({ label: 'Zoom', list: ZOOMS, text: ZOOMS.map(z => z + ' px/s'), def: 3 }, arr.zoom, v => { const mid = (TR.scroll.scrollLeft + TR.scroll.clientWidth / 2) / zoomPx(); arr.zoom = v; persist(); renderTimeline(); TR.scroll.scrollLeft = mid * zoomPx() - TR.scroll.clientWidth / 2; }, 64).root);
  TR.undoB = el('button', { className: 'chip', textContent: 'Undo', onclick: undo }); TR.redoB = el('button', { className: 'chip', textContent: 'Redo', onclick: redo });
  const hasClip = () => !!clipOf(sel.clip), hasTrack = () => !!trackOf(sel.track);
  const menus = el('div', { className: 'bar' },
    menu('Add', () => [{ label: 'Import clips onto the selected track', run: () => TR.imp.click() }, { label: 'Import stems, one track each', run: () => TR.stems.click() }, '-', { label: 'New track', run: () => newTrack() }]),
    menu('Clip', () => [
      { label: 'Split at the playhead', off: !hasClip(), run: () => { if (!splitClip(sel.clip, arrPos())) say('Put the playhead inside the clip first.'); } },
      { label: 'Duplicate', off: !hasClip(), run: () => duplicateClip(sel.clip) }, { label: 'Repeat four times', off: !hasClip(), run: () => duplicateClip(sel.clip, 4) },
      { label: 'Chop into 4', off: !hasClip(), run: () => chopClip(sel.clip, 4) }, { label: 'Chop into 8', off: !hasClip(), run: () => chopClip(sel.clip, 8) },
      { label: 'Reverse', off: !hasClip(), run: () => { const c = clipOf(sel.clip).clip; editClip(c.id, { rev: !c.rev }); changed(); } },
      { label: 'Loop around this clip', off: !hasClip(), run: () => { const c = clipOf(sel.clip).clip; arr.loop = { on: true, start: c.start, end: c.start + c.dur }; changed(); syncTransport(); } },
      '-', { label: 'Delete clip', off: !hasClip(), run: () => deleteClip(sel.clip) }]),
    menu('Track', () => [{ label: 'New track', run: () => newTrack() }, { label: 'Duplicate track', off: !hasTrack(), run: () => duplicateTrack(sel.track) },
      { label: 'Move up', off: !hasTrack(), run: () => moveTrack(sel.track, -1) }, { label: 'Move down', off: !hasTrack(), run: () => moveTrack(sel.track, 1) },
      '-', { label: 'Delete track', off: !hasTrack(), run: () => deleteTrack(sel.track) }]),
    menu('Bounce', () => [{ label: 'Song through the master (WAV)', off: !songEnd(), run: () => bounceSong() }, { label: 'Stems, one per track (zip)', off: !songEnd(), run: () => bounceStems() },
      { label: 'Seamless loop of the loop range', off: !(arr.loop.end > arr.loop.start), run: () => bounceLoop() }]),
    menu('Save', () => [{ label: 'Save a save point now', run: () => savePoint('Save point') }, ...savePoints().slice(0, 8).map(p => ({ label: 'Restore: ' + p.name + ' · ' + new Date(p.t).toLocaleTimeString(), run: () => restorePoint(p) }))]),
    TR.undoB, TR.redoB);
  w.append(card(TR.lcd, el('div', { className: 'bar', style: 'margin-top:10px' }, ib('tHome', 'Back to the start', 'prev', () => arrSeek(arr.loop.on ? arr.loop.start : 0)), TR.play, stop, TR.loopChip,
    chip('Click', () => arr.metro, v => arr.metro = v), chip('Follow', () => arr.follow, v => arr.follow = v)), el('div', { style: 'margin-top:12px' }, dials), el('div', { style: 'margin-top:12px' }, menus), TR.imp, TR.stems));
  // timeline
  TR.heads = el('div', { className: 'tl-heads' });
  TR.ruler = el('canvas', { className: 'tl-ruler' });
  TR.lanes = el('div', { className: 'tl-lanes' });
  TR.playhead = el('div', { className: 'tl-playhead' });
  TR.loopBox = el('div', { className: 'tl-loop' });
  TR.inner = el('div', { className: 'tl-inner' }, TR.ruler, TR.lanes, TR.loopBox, TR.playhead);
  TR.scroll = el('div', { className: 'tl-scroll' }, TR.inner);
  TR.scroll.addEventListener('scroll', drawRuler, { passive: true });
  TR.empty = el('p', { className: 'note', textContent: 'No tracks yet. Use Add to import clips; each file lands on the selected track at the playhead. Tap a clip to select it, then drag it to move, or drag its edges to trim.' });
  const lib = el('select', { ariaLabel: 'Take from the library' }); TR.libSel = lib;
  const addLib = el('button', { className: 'btn', textContent: 'Add to track', onclick: async () => { if (!lib.value) return; audio(); await rawBuffer(lib.value); const t = trackOf(sel.track) || newTrackQuiet(); checkpoint(); addClip(t.id, lib.value, snapT(arrPos())); changed(); } });
  w.append(card(el('div', { className: 'tl' }, TR.heads, TR.scroll), TR.empty, el('div', { className: 'bar', style: 'margin-top:10px' }, lib, addLib),
    el('p', { className: 'note', id: 'tMaster' })));
  // inspector
  TR.seg = el('div', { className: 'seg' }, ...['clip', 'track'].map(v => { const b = el('button', { textContent: v === 'clip' ? 'Clip' : 'Track', onclick: () => { TR.view = v; renderInspector(); } }); b.dataset.v = v; return b; }));
  TR.insp = el('div', { style: 'margin-top:12px' });
  w.append(card(TR.seg, TR.insp));
  attachTimeline();
  renderTracks();
}

// ---------- render ----------
function renderTracks() {
  if (!TR.lanes) return;
  renderHeads(); renderTimeline(); renderInspector(); syncTransport(); syncUndo();
  TR.empty.hidden = arr.tracks.length > 0;
  const names = [...takes.keys()].sort();
  TR.libSel.replaceChildren(el('option', { value: '', textContent: names.length ? 'Choose a take from the library' : 'The library is empty' }), ...names.map(n => el('option', { value: n, textContent: takeLabel(n) })));
}
function renderHeads() {
  TR.heads.replaceChildren(el('div', { className: 'tl-spacer' }), ...arr.tracks.map(t => {
    const s = mixState.strips[t.id], h = el('div', { className: 'tl-head' + (sel.track === t.id ? ' sel' : '') });
    h.style.setProperty('--c', t.color);
    const name = el('button', { className: 'tl-name', textContent: t.name, onclick: () => { sel.track = t.id; sel.clip = null; TR.view = 'track'; renderTracks(); } });
    const m = el('button', { className: 'ms m', textContent: 'M', ariaLabel: 'Mute ' + t.name }), so = el('button', { className: 'ms s', textContent: 'S', ariaLabel: 'Solo ' + t.name });
    m.onclick = () => { s.mute = !s.mute; syncMS(); remix(); persist(); }; so.onclick = () => { s.solo = !s.solo; syncMS(); remix(); persist(); };
    msList.push({ id: t.id, mute: m, solo: so });
    const lv = el('div', { className: 'lv' }), meter = el('div', { className: 'meter mini' }, lv, el('div', { className: 'pk' }));
    lvList.push({ id: t.id, lv, pk: meter.lastChild, gl: el('div') });
    h.append(name, el('div', { className: 'bar', style: 'gap:4px' }, m, so), meter); return h;
  }));
  syncMS();
}
function renderTimeline() {
  if (!TR.lanes) return;
  const W = Math.max(TR.scroll.clientWidth || 300, Math.ceil((Math.max(songEnd(), arr.loop.on ? arr.loop.end : 0) + 20) * zoomPx()));
  TR.inner.style.width = W + 'px';
  const beatPx = spb() * zoomPx();
  TR.lanes.style.setProperty('--beat', beatPx + 'px'); TR.lanes.style.setProperty('--bar', beatPx * arr.beats + 'px');
  TR.lanes.style.height = arr.tracks.length * LANE + 'px';
  TR.lanes.replaceChildren(...arr.tracks.map(t => {
    const lane = el('div', { className: 'tl-lane' + (sel.track === t.id ? ' sel' : '') }); lane.dataset.id = t.id;
    for (const c of t.clips) lane.append(clipEl(c, t)); return lane;
  }));
  TR.loopBox.hidden = !arr.loop.on;
  TR.loopBox.style.left = arr.loop.start * zoomPx() + 'px'; TR.loopBox.style.width = (arr.loop.end - arr.loop.start) * zoomPx() + 'px';
  drawRuler(); arrFrame(true);
}
function clipEl(c, t) {
  const d = el('div', { className: 'tclip' + (sel.clip === c.id ? ' sel' : '') + (c.mute ? ' muted' : '') });
  d.dataset.id = c.id; d.style.setProperty('--c', t.color); d.style.background = hexA(t.color, 0.18);
  placeClip(d, c);
  const cv = el('canvas');
  d.append(cv, el('div', { className: 'nm', textContent: (c.rev ? '⇄ ' : '') + takeLabel(c.take) }), el('div', { className: 'hd l' }), el('div', { className: 'hd r' }));
  requestAnimationFrame(() => drawClipWave(cv, c, t.color));
  return d;
}
function placeClip(d, c) { d.style.left = c.start * zoomPx() + 'px'; d.style.width = Math.max(6, c.dur * zoomPx()) + 'px'; }
function drawClipWave(cv, c, color) {
  const t = takes.get(c.take), W = Math.min(1600, cv.clientWidth), H = cv.clientHeight;
  if (!t?.peaks || !W || !H) return;
  cv.width = W; cv.height = H;
  const g = cv.getContext('2d'), bins = t.peaks.length / 2, D = t.raw.duration, r = rateOf(c), mid = H / 2 + 6;
  g.fillStyle = hexA(color, 0.75);
  for (let x = 0; x < W; x++) {
    let s = c.offset + (x / W) * c.dur * r; if (c.rev) s = c.offset + c.dur * r - (x / W) * c.dur * r;
    if (s < 0 || s >= D) continue;
    const k = Math.min(bins - 1, Math.floor(s / D * bins)), lo = t.peaks[k * 2], hi = t.peaks[k * 2 + 1], amp = (H - 16) / 2 * dbToLin(Math.min(6, c.gain));
    g.fillRect(x, mid - hi * amp, 1, Math.max(1, (hi - lo) * amp));
  }
}
function drawRuler() {
  const cv = TR.ruler, W = TR.scroll.clientWidth, H = 28, dpr = Math.min(2, devicePixelRatio || 1);
  if (!W) return;
  cv.style.width = W + 'px'; if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const g = cv.getContext('2d'), x0 = TR.scroll.scrollLeft, px = zoomPx(), bl = barLen();
  g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  if (arr.loop.on) { g.fillStyle = 'rgba(255,202,114,.25)'; g.fillRect(arr.loop.start * px - x0, 0, (arr.loop.end - arr.loop.start) * px, H); }
  g.font = '10px ui-monospace,Menlo,monospace'; g.fillStyle = '#93b6bc'; g.strokeStyle = '#2b5560';
  const every = bl * px < 40 ? Math.ceil(40 / (bl * px)) : 1;
  for (let b = Math.floor(x0 / px / bl); b * bl * px < x0 + W; b++) {
    const x = Math.round(b * bl * px - x0) + 0.5;
    g.beginPath(); g.moveTo(x, b % every ? 18 : 10); g.lineTo(x, H); g.stroke();
    if (b % every === 0) g.fillText(String(b + 1), x + 3, 12);
    if (spb() * px > 12) for (let k = 1; k < arr.beats; k++) { const bx = Math.round((b * bl + k * spb()) * px - x0) + 0.5; g.beginPath(); g.moveTo(bx, 22); g.lineTo(bx, H); g.stroke(); }
  }
}
function arrFrame(force) {
  if (!TR.lanes || (!eng.playing && !force)) return;
  const pos = arrPos(), x = pos * zoomPx();
  TR.playhead.style.transform = `translateX(${x}px)`;
  $('tPos').textContent = `BAR ${posText(pos)}  ·  ${round(arr.bpm, 1)} BPM  ·  ${arr.beats}/4`;
  $('tClock').textContent = clockText(pos);
  if (eng.playing && arr.follow) { const s = TR.scroll; if (x > s.scrollLeft + s.clientWidth * 0.85 || x < s.scrollLeft) s.scrollLeft = x - s.clientWidth * 0.15; }
  if (activeTab === 'tracks' && Date.now() > say.until) { $('nowTitle').textContent = arr.name; $('nowSub').textContent = `${posText(pos)}  ${clockText(pos)}`; }
}
function paintTrackMeters() { const n = $('tMaster'); if (n) n.textContent = `Master: ${lufsText(LM.mom)} LUFS momentary, ${lufsText(LM.int)} integrated (target ${mixState.target}), peak ${lufsText(LM.peakMax)} dBFS.`; }
function syncTransport() {
  if (!TR.play) return;
  TR.play.innerHTML = icon(eng.playing ? 'pause' : 'play'); TR.play.setAttribute('aria-label', eng.playing ? 'Pause' : 'Play');
  TR.loopChip.setAttribute('aria-pressed', arr.loop.on);
  if (activeTab === 'tracks') { $('play').innerHTML = icon(eng.playing ? 'pause' : 'play'); }
  arrFrame(true);
}
function syncUndo() { if (TR.undoB) { TR.undoB.disabled = !hist.undo.length; TR.redoB.disabled = !hist.redo.length; } }

// ---------- inspector ----------
function renderInspector() {
  const f = clipOf(sel.clip), t = trackOf(sel.track);
  if (TR.view !== 'clip' && TR.view !== 'track') TR.view = f ? 'clip' : 'track';
  for (const b of TR.seg.children) b.setAttribute('aria-pressed', b.dataset.v === TR.view);
  if (TR.view === 'clip') {
    if (!f) { TR.insp.replaceChildren(el('p', { className: 'note', textContent: 'Tap a clip on the timeline to edit it here.' })); return; }
    const c = f.clip, set = (k, key) => v => { editClip(c.id, { [k]: v }, key || k); renderTimeline(); };
    const D = takes.get(c.take)?.raw?.duration ?? 60;
    const dials = el('div', { className: 'dials' },
      dialFor({ label: 'Gain', min: -24, max: 12, step: 0.5, fine: 0.1, fmt: fmtDb, def: 0 }, c.gain, set('gain'), 64).root,
      dialFor({ label: 'Pitch', min: -24, max: 24, step: 1, fine: 0.1, fmt: v => (v > 0 ? '+' : '') + round(v, 1) + ' st', def: 0 }, c.semi, set('semi'), 64).root,
      dialFor({ label: 'Fade in', min: 0, max: 4000, step: 50, fine: 5, fmt: v => v + ' ms', def: 0 }, c.fadeIn, set('fadeIn'), 64).root,
      dialFor({ label: 'Fade out', min: 0, max: 4000, step: 50, fine: 5, fmt: v => v + ' ms', def: 0 }, c.fadeOut, set('fadeOut'), 64).root,
      dialFor({ label: 'Start', min: 0, max: Math.max(600, c.start + 60), step: 0.05, fine: 0.005, fmt: v => v.toFixed(2) + ' s', def: 0 }, c.start, set('start'), 64).root,
      dialFor({ label: 'Length', min: 0.05, max: Math.max(0.1, D / rateOf(c)), step: 0.05, fine: 0.005, fmt: v => v.toFixed(2) + ' s', def: c.dur }, c.dur, set('dur'), 64).root,
      dialFor({ label: 'Clip in', min: 0, max: Math.max(0.01, D - 0.01), step: 0.05, fine: 0.005, fmt: v => v.toFixed(2) + ' s', def: 0 }, c.offset, set('offset'), 64).root);
    const mute = el('button', { className: 'chip', textContent: 'Mute clip' }); mute.setAttribute('aria-pressed', c.mute);
    mute.onclick = () => { editClip(c.id, { mute: !c.mute }); changed(); };
    const move = el('select', { ariaLabel: 'Track' }, ...arr.tracks.map(x => el('option', { value: x.id, textContent: 'On ' + x.name })));
    move.value = f.track.id; move.onchange = () => moveClipToTrack(c.id, move.value);
    TR.insp.replaceChildren(el('h3', { textContent: takeLabel(c.take) }), el('p', { className: 'note', style: 'margin:0 0 8px', textContent: `Starts at bar ${posText(c.start)}, ${c.dur.toFixed(2)} s long. Pitch changes speed too, like tape.` }), dials,
      el('div', { className: 'bar', style: 'margin-top:12px' }, mute, move));
    return;
  }
  if (!t) { TR.insp.replaceChildren(el('p', { className: 'note', textContent: 'Make a track with Add, then select it to set its level, pan and tone.' })); return; }
  const name = el('input', { type: 'text', value: t.name, ariaLabel: 'Track name', maxLength: 30 });
  name.oninput = () => { renameTrack(t.id, name.value.trim()); renderHeads(); };
  const colours = el('div', { className: 'bar' }, ...TRACK_COLORS.map(col => { const b = el('button', { className: 'swatch', ariaLabel: 'Colour' }); b.style.background = col; b.setAttribute('aria-pressed', t.color === col); b.onclick = () => { t.color = col; changed(); }; return b; }));
  TR.insp.replaceChildren(el('div', { style: 'display:grid;gap:8px' }, name, colours), el('div', { style: 'margin-top:12px' }, stripCard(t.id)));
}

// ---------- timeline gestures: tap selects, drag moves the selected clip, its edges trim ----------
function attachTimeline() {
  let g = null;
  const timeAt = e => (e.clientX - TR.inner.getBoundingClientRect().left) / zoomPx();
  TR.ruler.addEventListener('pointerdown', e => { arrSeek(snapT(timeAt(e))); });
  TR.lanes.addEventListener('pointerdown', e => {
    const d = e.target.closest('.tclip'), lane = e.target.closest('.tl-lane');
    if (!lane) return;
    g = { x: e.clientX, y: e.clientY, d, lane, moved: false, pointer: e.pointerId };
    if (d && d.classList.contains('sel')) {
      const c = clipOf(d.dataset.id).clip;
      g.mode = e.target.classList.contains('l') ? 'l' : e.target.classList.contains('r') ? 'r' : 'move';
      g.c = c; g.start = c.start; g.dur = c.dur; g.off = c.offset; g.track = clipOf(c.id).track.id;
      try { d.setPointerCapture(e.pointerId); } catch {}
    }
  });
  TR.lanes.addEventListener('pointermove', e => {
    if (!g || !g.mode) return;
    const dx = e.clientX - g.x;
    if (!g.moved && Math.abs(dx) < 4 && Math.abs(e.clientY - g.y) < 8) return;
    if (!g.moved) { checkpoint(); g.moved = true; }
    const c = g.c, r = rateOf(c), D = takes.get(c.take)?.raw?.duration ?? Infinity, dt = dx / zoomPx();
    if (g.mode === 'move') {
      c.start = snapT(g.start + dt);
      const i = clamp(Math.floor((e.clientY - TR.lanes.getBoundingClientRect().top) / LANE), 0, arr.tracks.length - 1), to = arr.tracks[i];
      const from = clipOf(c.id).track;
      if (to && to !== from) { from.clips.splice(from.clips.indexOf(c), 1); to.clips.push(c); sel.track = to.id; to.id && g.lane !== null && TR.lanes.children[i].append(g.d); }
    } else if (g.mode === 'l') {
      let ns = snapT(g.start + dt); ns = Math.min(ns, g.start + g.dur - 0.05);
      const delta = ns - g.start;
      if (!c.rev) { if (g.off + delta * r < 0) { ns = g.start - g.off / r; } c.offset = g.off + (ns - g.start) * r; }
      c.start = ns; c.dur = g.dur - (ns - g.start);
    } else {
      let end = snapT(g.start + g.dur + dt); end = Math.max(end, g.start + 0.05);
      const maxEnd = g.start + (D - g.off) / r; if (!c.rev) end = Math.min(end, maxEnd);
      c.dur = end - g.start; if (c.rev) c.offset = Math.max(0, g.off + (g.dur - c.dur) * r);
    }
    placeClip(g.d, c);
    const sc = TR.scroll, rr = sc.getBoundingClientRect();
    if (e.clientX > rr.right - 24) sc.scrollLeft += 12; else if (e.clientX < rr.left + 24) sc.scrollLeft -= 12;
  });
  const end = e => {
    if (!g) return;
    const tap = !g.moved && Math.abs(e.clientX - g.x) < 6 && Math.abs(e.clientY - g.y) < 8;
    if (g.mode && g.moved) { persist(); renderTimeline(); renderInspector(); }
    else if (tap) {
      if (g.d) { sel.clip = g.d.dataset.id; sel.track = clipOf(sel.clip).track.id; TR.view = 'clip'; }
      else { sel.track = g.lane.dataset.id; sel.clip = null; arrSeek(snapT(timeAt(e))); }
      renderTracks();
    }
    g = null;
  };
  TR.lanes.addEventListener('pointerup', end); TR.lanes.addEventListener('pointercancel', () => { if (g?.mode && g.moved) { persist(); renderTimeline(); } g = null; });
}

// ---------- save points: snapshots of the whole project in this browser ----------
const PKEY = 'vtx-producer-points';
const savePoints = () => { try { return JSON.parse(localStorage.getItem(PKEY) || '[]'); } catch { return []; } };
function savePoint(name, auto = false) {
  try {
    const list = savePoints(); list.unshift({ name, auto, t: Date.now(), json: projectJson() });
    const keep = list.filter(p => !p.auto).slice(0, 20).concat(list.filter(p => p.auto).slice(0, 8)).sort((a, b) => b.t - a.t);
    localStorage.setItem(PKEY, JSON.stringify(keep)); if (!auto) say('Save point stored: ' + name);
  } catch { say('This browser is full; the save point was not stored. Save the project file instead (Mix, Project).'); }
}
function restorePoint(p) { savePoint('Before restoring ' + p.name, true); applyProject(p.json); }

// ---------- bounces ----------
async function renderArr({ from = 0, to = songEnd(), tail = 0, only = null, master = true } = {}) {
  audio(); await decodeUsed();
  const sr = 48000, off = new OAC(2, Math.max(1, Math.ceil(sr * (to - from + tail))), sr);
  const M = buildMixer(off, false, { noClip: !master }); applyMixer(M, true, only ? [only] : arr.tracks.map(t => t.id), !master);
  for (const t of arr.tracks) {
    if (only && t.id !== only) continue;
    for (const c of t.clips) {
      if (c.mute || c.start >= to || c.start + c.dur <= from) continue;
      const skip = Math.max(0, from - c.start);
      playClip(off, M.strips[t.id].in, c, Math.max(0, c.start - from), skip);
    }
  }
  return off.startRendering();
}
const fileBase = () => safe(arr.name) + '_' + Math.round(arr.bpm) + 'bpm';
const bounceSong = () => busy(null, '', async () => { say('Bouncing…', 60000); await deliver([{ name: fileBase() + '.wav', blob: encodeWav(await renderArr({ tail: 2 }), wavBits()) }], fileBase() + '.zip'); });
const bounceStems = () => busy(null, '', async () => {
  say('Bouncing stems…', 120000); const files = [];
  for (const [i, t] of arr.tracks.entries()) {
    if (mixState.strips[t.id]?.mute || !t.clips.length) continue;
    const b = await renderArr({ tail: 2, only: t.id, master: false });
    let peak = 0; for (let c = 0; c < 2; c++) for (const v of b.getChannelData(c)) if (Math.abs(v) > peak) peak = Math.abs(v);
    files.push({ name: `${fileBase()}_${String(i + 1).padStart(2, '0')}_${safe(t.name)}.wav`, blob: encodeWav(b, peak > 1 ? 32 : wavBits()) });
  }
  await deliver(files, fileBase() + '_stems.zip');
});
const bounceLoop = () => busy(null, '', async () => {
  say('Bouncing the loop…', 60000);
  const len = arr.loop.end - arr.loop.start, tail = Math.min(6, barLen() * 2), b = await renderArr({ from: arr.loop.start, to: arr.loop.end, tail });
  const n = Math.round(len * b.sampleRate), out = ctx.createBuffer(2, n, b.sampleRate);
  for (let c = 0; c < 2; c++) { const s = b.getChannelData(c), d = out.getChannelData(c); d.set(s.subarray(0, n)); for (let i = n; i < s.length && i - n < n; i++) d[i - n] += s[i]; }   // the tail folds onto the start
  await deliver([{ name: `${fileBase()}_loop_${round(len / barLen(), 2)}bars.wav`, blob: encodeWav(out, wavBits()) }], fileBase() + '_loop.zip');
});
