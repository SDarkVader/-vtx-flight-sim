// =====================================================================================
// TAKES BENCH: library, waveform editor (non-destructive), audition, Firefly prompt notebook
// =====================================================================================
const takes = new Map();   // file name -> { file, raw, baked, seconds, peaks, stats, row }
const edits = saved.edits && typeof saved.edits === 'object' ? saved.edits : {};
const takeMeta = saved.takeMeta && typeof saved.takeMeta === 'object' ? saved.takeMeta : {};
const meta = n => (takeMeta[n] ||= {});
const JOBS = ['Not decided', 'Wheel fans', 'Boosters', 'Flaps', 'Air brake', 'Legs and pods', 'Wings', 'Touchdown', 'Latch', 'Tyres', 'Wind', 'Cockpit', 'Environment', 'Not using'];
const NORM = [null, -6, -3, -1];
const NORM_TEXT = ['Off', '−6 dBFS', '−3 dBFS', '−1 dBFS'];
const EDIT0 = { in: null, out: null, fadeIn: 0, fadeOut: 0, gain: 0, norm: 2, loopIn: null, loopOut: null, xfade: 100 };
const fullEdit = n => ({ ...EDIT0, ...(edits[n] || {}) });
const isEdited = n => { const e = fullEdit(n); return Object.keys(EDIT0).some(k => e[k] !== EDIT0[k]); };
const takeLabel = n => n ? n.replace(/^Firefly.audio.|^Firefly-/, '').replace(/\.wav$/i, '') : 'Stand-in (no take)';
const secText = v => v == null ? 'Off' : round(v, 3).toFixed(3) + ' s';
const durText = s => !Number.isFinite(s) ? '' : s < 60 ? s.toFixed(2) + ' s' : mmss(s);

// ---------- decoding and baking ----------
async function rawBuffer(name) {
  const t = takes.get(name);
  if (!t) return null;
  if (!t.raw) {
    t.raw = await audio().decodeAudioData(await t.file.arrayBuffer());
    t.raw.takeName = name;
    analyseTake(t);
  }
  return t.raw;
}
function analyseTake(t) {
  const b = t.raw, bins = 1000, step = Math.max(1, Math.floor(b.length / bins)), peaks = new Float32Array(bins * 2);
  let peak = 0, sq = 0, n = 0;
  for (let k = 0; k < bins; k++) {
    let lo = 0, hi = 0;
    for (let c = 0; c < b.numberOfChannels; c++) {
      const d = b.getChannelData(c);
      for (let i = k * step, e = Math.min(b.length, i + step); i < e; i++) { const v = d[i]; if (v < lo) lo = v; if (v > hi) hi = v; }
    }
    peaks[k * 2] = lo; peaks[k * 2 + 1] = hi;
  }
  const d0 = b.getChannelData(0);
  for (let i = 0; i < d0.length; i++) { const v = d0[i]; if (Math.abs(v) > peak) peak = Math.abs(v); sq += v * v; n++; }
  for (let c = 1; c < b.numberOfChannels; c++) { const d = b.getChannelData(c); for (let i = 0; i < d.length; i++) if (Math.abs(d[i]) > peak) peak = Math.abs(d[i]); }
  t.peaks = peaks;
  t.stats = { peak: toDb(peak), rms: toDb(Math.sqrt(sq / Math.max(1, n))), rate: b.sampleRate, ch: b.numberOfChannels };
  t.seconds = b.duration;
}
// Where a take's sound begins and ends, ignoring silence at either side.
function body(buffer) {
  if (buffer.body) return buffer.body;
  const d = buffer.getChannelData(0), step = Math.floor(buffer.sampleRate * 0.02), levels = [];
  for (let i = 0; i + step <= d.length; i += step) {
    let sum = 0; for (let j = i; j < i + step; j++) sum += d[j] * d[j];
    levels.push(Math.sqrt(sum / step));
  }
  const top = Math.max(...levels, 1e-6), first = levels.findIndex(v => v > top * 0.08);
  let last = levels.length - 1; while (last > first && levels[last] <= top * 0.08) last--;
  let peak = 0; for (const v of d) peak = Math.max(peak, Math.abs(v));
  return buffer.body = { from: Math.max(0, first) * 0.02, to: (last + 1) * 0.02, boost: Math.min(6, 0.7 / Math.max(peak, 0.05)), loop: null };
}
// Applies an edit (trim, fades, seamless loop, then normalise and gain) to a decoded take. The result is what you hear and what you bounce.
// Level is set last, from the finished result, so a loop crossfade can never push the file past its normalised peak.
function bake(raw, e, c = ctx) {
  const sr = raw.sampleRate, n0 = clamp(Math.floor((e.in ?? 0) * sr), 0, raw.length - 1), n1 = clamp(Math.floor((e.out ?? raw.duration) * sr), n0 + 1, raw.length);
  const len = n1 - n0;
  if (len < 16) return raw;
  const chs = raw.numberOfChannels, out = c.createBuffer(chs, len, sr);
  const fi = Math.min(len >> 1, Math.floor(e.fadeIn * sr / 1000)), fo = Math.min(len >> 1, Math.floor(e.fadeOut * sr / 1000));
  for (let ch = 0; ch < chs; ch++) {
    const from = raw.getChannelData(ch), to = out.getChannelData(ch);
    for (let i = 0; i < len; i++) {
      let v = from[n0 + i];
      if (i < fi) v *= Math.sin(i / fi * Math.PI / 2);
      if (i >= len - fo) v *= Math.sin((len - 1 - i) / fo * Math.PI / 2);
      to[i] = v;
    }
  }
  let loop = null;
  if (e.loopIn != null && e.loopOut != null) {
    const li = clamp(Math.round((e.loopIn - (e.in ?? 0)) * sr), 0, len - 17), lo = clamp(Math.round((e.loopOut - (e.in ?? 0)) * sr), li + 16, len);
    const xf = Math.min(Math.round(e.xfade / 1000 * sr), li, lo - li - 1);
    if (xf > 8) for (let ch = 0; ch < chs; ch++) {
      const d = out.getChannelData(ch);
      for (let i = 0; i < xf; i++) { const t = i / xf; d[lo - xf + i] = d[lo - xf + i] * Math.cos(t * Math.PI / 2) + d[li - xf + i] * Math.sin(t * Math.PI / 2); }
    }
    loop = [li / sr, lo / sr];
  }
  let peak = 0;
  for (let ch = 0; ch < chs; ch++) { const d = out.getChannelData(ch); for (let i = 0; i < len; i++) { const v = Math.abs(d[i]); if (v > peak) peak = v; } }
  const target = NORM[e.norm];
  let k = (target == null ? 1 : Math.min(6, dbToLin(target) / Math.max(peak, 1e-4))) * dbToLin(e.gain);
  if (peak * k > 0.989) k = 0.989 / peak;   // never clip: hold the finished peak at -0.1 dBFS
  for (let ch = 0; ch < chs; ch++) { const d = out.getChannelData(ch); for (let i = 0; i < len; i++) d[i] *= k; }
  out.body = { from: 0, to: out.duration, boost: 1, loop, baked: true, peak: toDb(peak * k) };
  return out;
}
async function bufferOf(name) {
  const t = takes.get(name);
  if (!t) return null;
  const raw = await rawBuffer(name);
  if (!isEdited(name)) return raw;
  return t.baked ||= bake(raw, fullEdit(name));
}
// What a bounce writes: the edit, or for an untouched take a trim of its silence and a normalise to -3 dBFS.
async function bounceBuffer(name, c) {
  const raw = await rawBuffer(name);
  if (isEdited(name)) return bake(raw, fullEdit(name), c);
  const b = body(raw);
  return bake(raw, { ...EDIT0, in: b.from, out: b.to }, c);
}
const resultInfo = debounce(async name => {
  const n = $('resultInfo');
  if (!n || editor.name !== name) return;
  try { const b = await bufferOf(name); n.textContent = `After the edit: ${b.duration.toFixed(2)} s, peak ${fmtDb(b.body?.peak ?? takes.get(name).stats.peak)}${b.body?.loop ? ', loops seamlessly' : ''}.`; } catch {}
}, 150);
function takeChanged(name) {
  const t = takes.get(name);
  if (t) t.baked = null;
  persist(); resultInfo(name);
  if (editor.name === name) { drawWave(); renderTakeRow(name); }
  if (pads.has(name)) restartPad(name);
}

// ---------- loading ----------
function addTakes(files, { splitRadio = false, keep = true, force = false } = {}) {
  stopAllVehicle(); stopAllPads();
  const songsFound = [];
  let added = 0;
  for (const file of files) {
    if (!AUDIO.test(file.name)) continue;
    const p = where(file);
    if (/(^|\/)exact copies\//i.test(p)) continue;
    if (splitRadio && /(^|\/)radio\//i.test(p)) { songsFound.push(file); continue; }
    if (takes.has(file.name)) continue;
    takes.set(file.name, { file }); added++;
    if (keep && (prefs.keepTakes || force)) lib.put('take', file).catch(() => say('Storage is full: ' + file.name + ' is not kept.'));
  }
  autoPick();
  if (songsFound.length) addSongs(songsFound);
  renderTakes(); renderParts(); renderScene();
  const msg = `${takes.size} takes${songsFound.length ? ` and ${songsFound.length} songs` : ''} loaded. Parts without a matching take use a stand-in; pick any take for any part.`;
  for (const id of ['vehNote', 'takeNote']) if ($(id)) $(id).textContent = msg;
  say(added ? `${added} takes added.` : 'Nothing new to add.');
  libUsage();
  (async () => { for (const t of takes.values()) if (t.seconds === undefined) { t.seconds = await lengthOf(t.file); renderTakeRow(t.file.name); } })();
}
const studioFolder = files => addTakes(files, { splitRadio: true });
function lengthOf(file) {
  return new Promise(resolve => {
    const probe = new Audio(), u = URL.createObjectURL(file);
    const done = s => { URL.revokeObjectURL(u); resolve(s); };
    probe.preload = 'metadata'; probe.onloadedmetadata = () => done(probe.duration); probe.onerror = () => done(NaN);
    probe.src = u;
  });
}
function loaderBar(host, noteId) {
  const files = el('input', { type: 'file', multiple: true, accept: 'audio/*,.wav,.mp3,.m4a,.ogg,.flac' });
  const folder = el('input', { type: 'file' }); folder.setAttribute('webkitdirectory', '');
  files.onchange = () => { addTakes([...files.files]); files.value = ''; };
  folder.onchange = () => { studioFolder([...folder.files]); folder.value = ''; };
  host.append(el('label', { className: 'pick' }, 'Add takes', files), el('label', { className: 'pick' }, 'Add Sounds folder', folder));
  if (window.showDirectoryPicker) host.append(el('button', { className: 'btn', textContent: 'Remember Sounds folder', onclick: () => rememberFolder('sounds') }));
  $(noteId).textContent = 'Songs in a folder named Radio go to the Music bench; every other sound is a take. Nothing is uploaded.';
}
async function libUsage() {
  const n = $('libUsage');
  if (!n) return;
  const used = await lib.usage();
  n.textContent = prefs.keepTakes ? `Takes are kept in this browser${used != null ? `, ${(used / 1048576).toFixed(1)} MB used by the studio` : ''}.` : 'Takes are forgotten when this page closes.';
}

// ---------- audition pads ----------
const pads = new Map();    // take name -> { source, gain, mark, startedAt }
function tunePad(name) {
  const v = pads.get(name);
  if (!v?.source) return;
  const m = meta(name);
  let rate = m.pitch ?? 1, level = m.volume ?? 1;
  if (m.job === 'Wheel fans') { const r = macro.rpm / 0.7; rate *= r; level *= r ** 1.73; }
  else if (m.job === 'Boosters') { const t = macro.thrust; rate *= 0.8 + t * (0.2 / 0.7); level *= (t / 0.7) ** 0.8; }
  v.source.playbackRate.setTargetAtTime(rate, ctx.currentTime, 0.1);
  v.gain.gain.setTargetAtTime(level, ctx.currentTime, 0.1);
}
function stopPad(name) {
  const v = pads.get(name);
  pads.delete(name);
  if (v?.source) { v.source.onended = null; try { v.source.stop(); } catch {} v.gain.disconnect(); }
  v?.mark(false);
}
function stopAllPads() { [...pads.keys()].forEach(stopPad); }
function smoothLoop(input) {
  const fade = Math.min(Math.floor(input.sampleRate * 0.12), Math.floor(input.length / 4)), length = input.length - fade;
  const out = ctx.createBuffer(input.numberOfChannels, length, input.sampleRate);
  for (let c = 0; c < input.numberOfChannels; c++) {
    const from = input.getChannelData(c), to = out.getChannelData(c);
    to.set(from.subarray(0, length));
    for (let i = 0; i < fade; i++) { const x = i / fade * Math.PI / 2; to[i] = from[i] * Math.sin(x) + from[length + i] * Math.cos(x); }
  }
  return out;
}
// A buffer and loop points ready for a looping source: the editor's loop if there is one, else the take with a smoothed seam.
async function loopSource(name, smooth = true) {
  const buf = await bufferOf(name);
  if (!buf) return null;
  const b = body(buf);
  if (b.loop) return { buffer: buf, start: b.loop[0], end: b.loop[1] };
  if (smooth && buf.length > 4800) { const s = buf.smoothed ||= smoothLoop(buf); return { buffer: s, start: 0, end: s.duration }; }
  return { buffer: buf, start: 0, end: buf.duration };
}
async function startPad(name, mark) {
  const ticket = { mark };
  pads.set(name, ticket); mark(true);
  audio();
  const m = meta(name);
  let src;
  try { src = m.loop ? await loopSource(name, !!m.smooth) : { buffer: await bufferOf(name) }; } catch { stopPad(name); say('Could not play ' + name); return; }
  if (pads.get(name) !== ticket) return;
  if (!src?.buffer) { stopPad(name); return; }
  const node = ctx.createBufferSource(), gain = ctx.createGain();
  node.buffer = src.buffer; node.loop = !!m.loop;
  if (m.loop && src.end) { node.loopStart = src.start; node.loopEnd = src.end; }
  gain.gain.value = 0; node.connect(gain).connect(padBus);
  node.onended = () => stopPad(name);
  Object.assign(ticket, { source: node, gain, startedAt: ctx.currentTime });
  tunePad(name);
  if (m.duck) duck();
  node.start();
}
const restartPad = debounce(name => { const v = pads.get(name); if (v) { const mark = v.mark; stopPad(name); startPad(name, mark); } }, 200);

// ---------- list ----------
function takeRow(name) {
  const t = takes.get(name), m = meta(name);
  const play = el('button', { className: 'chip', textContent: 'Play' });
  const mark = on => { play.textContent = on ? 'Stop' : 'Play'; play.classList.toggle('on-air', on); };
  play.onclick = () => pads.has(name) ? stopPad(name) : startPad(name, mark);
  const pick = el('button', { className: 'pick-take' });
  pick.onclick = () => openEditor(name);
  const row = el('div', { className: 'take' }, play, pick);
  t.row = { row, pick, play, mark };
  fillTakeRow(name);
  return row;
}
function fillTakeRow(name) {
  const t = takes.get(name), m = meta(name), r = t.row;
  if (!r) return;
  r.pick.replaceChildren(el('div', { textContent: takeLabel(name) }),
    el('small', { textContent: [durText(t.seconds), t.stats ? 'peak ' + fmtDb(t.stats.peak) : '', m.job && m.job !== JOBS[0] ? m.job : '', isEdited(name) ? 'edited' : '', m.keep ? 'kept' : ''].filter(Boolean).join(' · ') }));
  r.pick.toggleAttribute('aria-current', editor.name === name);
}
function renderTakeRow(name) { fillTakeRow(name); }
function renderTakes() {
  const names = [...takes.keys()].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const host = $('takeList');
  host.replaceChildren(...(names.length ? names.map(takeRow) : [el('p', { className: 'note', textContent: 'No takes yet. Add the Sounds folder or pick WAV files. Vehicle parts use computer-made stand-ins until then.' })]));
}
function autoPick() {   // a part whose chosen take is not loaded gets the first take whose name matches
  for (const part of PARTS) {
    const s = veh[part.id];
    if (takes.size && !takes.has(s.source)) s.source = [...takes.keys()].sort().find(n => part.match.test(n)) ?? '';
  }
}

// ---------- editor ----------
const editor = { name: null, dials: {}, drag: null, canvas: null };
function openEditor(name) {
  editor.name = name;
  const t = takes.get(name), card = $('editorCard');
  card.hidden = false;
  rawBuffer(name).then(() => {
    if (editor.name !== name) return;
    buildEditor(name);
    for (const n of takes.keys()) fillTakeRow(n);
    card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }).catch(() => say('Could not read ' + name));
}
function closeEditor() { editor.name = null; $('editorCard').hidden = true; for (const n of takes.keys()) fillTakeRow(n); }
function buildEditor(name) {
  const t = takes.get(name), m = meta(name), dur = t.raw.duration, host = $('editorBody');
  const e = () => (edits[name] ||= {});
  const setEdit = (k, v) => { e()[k] = v; if (Object.keys(EDIT0).every(key => e()[key] === undefined || e()[key] === EDIT0[key])) delete edits[name]; takeChanged(name); };
  const cur = k => fullEdit(name)[k];
  const D = editor.dials = {};
  const secDef = (label) => ({ label, min: 0, max: round(dur, 3), step: 0.01, fine: 0.001, fmt: v => round(v, 3).toFixed(3) + ' s', def: 0 });
  const mk = (key, def, size = 64) => {
    const d = dialFor(def, cur(key) ?? def.def, v => {
      if (key === 'in') { v = Math.min(v, (cur('out') ?? dur) - 0.02); }
      if (key === 'out') { v = Math.max(v, (cur('in') ?? 0) + 0.02); }
      setEdit(key, v); syncConstraints(key);
    }, size);
    D[key] = d; return d.root;
  };
  function syncConstraints(changed) {
    const i = cur('in') ?? 0, o = cur('out') ?? dur;
    if (changed === 'in' || changed === 'out') {
      for (const k of ['loopIn', 'loopOut']) if (cur(k) != null) { const v = clamp(cur(k), i, o); if (v !== cur(k)) { setEdit(k, v); D[k]?.set(v); } }
    }
    if (cur('loopIn') != null && cur('loopOut') != null && cur('loopIn') > cur('loopOut') - 0.02) {
      if (changed === 'loopIn') { setEdit('loopOut', Math.min(o, cur('loopIn') + 0.02)); D.loopOut?.set(cur('loopOut')); }
      else { setEdit('loopIn', Math.max(i, cur('loopOut') - 0.02)); D.loopIn?.set(cur('loopIn')); }
    }
    drawWave();
  }
  const trimGrid = el('div', { className: 'dials' },
    mk('in', { ...secDef('In'), def: 0 }), mk('out', { ...secDef('Out'), def: round(dur, 3) }),
    mk('fadeIn', { label: 'Fade in', min: 0, max: 1000, step: 10, fine: 1, fmt: v => v + ' ms', def: 0 }),
    mk('fadeOut', { label: 'Fade out', min: 0, max: 1000, step: 10, fine: 1, fmt: v => v + ' ms', def: 0 }),
    mk('gain', { label: 'Gain', min: -24, max: 12, step: 0.5, fine: 0.1, fmt: fmtDb, def: 0 }),
    mk('norm', { label: 'Normalise', list: NORM, text: NORM_TEXT, def: 2 }));
  // loop points: off until asked for
  const loopGrid = el('div', { className: 'dials' });
  const loopOn = el('button', { className: 'chip', textContent: 'Loop points' });
  const drawLoop = () => {
    const on = cur('loopIn') != null;
    loopOn.setAttribute('aria-pressed', on);
    loopGrid.replaceChildren(...(on ? [mk('loopIn', { ...secDef('Loop in'), def: cur('in') ?? 0 }), mk('loopOut', { ...secDef('Loop out'), def: cur('out') ?? dur }),
      mk('xfade', { label: 'Crossfade', min: 0, max: 1000, step: 10, fine: 1, fmt: v => v + ' ms', def: 100 })] : []));
    drawWave();
  };
  loopOn.onclick = () => {
    if (cur('loopIn') != null) { setEdit('loopIn', null); setEdit('loopOut', null); }
    else { const i = cur('in') ?? 0, o = cur('out') ?? dur, span = o - i; setEdit('loopIn', round(i + span * 0.2, 2)); setEdit('loopOut', round(o, 2)); }
    drawLoop();
  };
  // audition settings (not part of the edit)
  const chip = (field, label, after) => {
    const c = el('button', { className: 'chip', textContent: label }); c.setAttribute('aria-pressed', !!m[field]);
    c.onclick = () => { m[field] = !m[field]; c.setAttribute('aria-pressed', !!m[field]); persist(); fillTakeRow(name); after?.(); };
    return c;
  };
  const job = el('select', { ariaLabel: 'Job for ' + name }, ...JOBS.map(j => el('option', { textContent: j, value: j })));
  job.value = m.job ?? JOBS[0];
  job.onchange = () => { m.job = job.value; persist(); tunePad(name); fillTakeRow(name); renderPrompts(); };
  const pitch = dialFor({ label: 'Pitch', min: 0.5, max: 2, step: 0.05, fine: 0.01, fmt: v => round(v, 2) + 'x', def: 1 }, m.pitch ?? 1, v => { m.pitch = v; persist(); tunePad(name); }, 64);
  const level = dialFor({ label: 'Level', min: 0, max: 4, step: 0.1, fine: 0.01, fmt: v => round(v, 2), def: 1 }, m.volume ?? 1, v => { m.volume = v; persist(); tunePad(name); }, 64);
  const play = el('button', { className: 'btn go', textContent: 'Play' });
  const mark = on => { play.textContent = on ? 'Stop' : 'Play'; play.classList.toggle('on-air', on); };
  play.onclick = () => pads.has(name) ? stopPad(name) : startPad(name, mark);
  const result = el('p', { className: 'note', id: 'resultInfo', textContent: '' });
  const info = el('p', { className: 'note' });
  info.textContent = t.stats ? `${(t.stats.rate / 1000).toFixed(1)} kHz, ${t.stats.ch === 1 ? 'mono' : 'stereo'}, ${durText(dur)}, peak ${fmtDb(t.stats.peak)}, RMS ${fmtDb(t.stats.rms)} (before edits).` : '';
  const auto = el('button', { className: 'btn', textContent: 'Auto trim', onclick: () => {
    const b = body(t.raw);
    setEdit('in', round(b.from, 2)); setEdit('out', round(Math.min(dur, b.to), 2));
    D.in.set(cur('in')); D.out.set(cur('out')); syncConstraints('in'); say('Trimmed the silence either side.');
  } });
  const reset = el('button', { className: 'btn', textContent: 'Reset edit', onclick: () => { delete edits[name]; takeChanged(name); buildEditor(name); } });
  const bounce = el('button', { className: 'btn go', textContent: 'Bounce WAV', onclick: () => bounceOne(name, bounce) });
  const remove = el('button', { className: 'btn warn', textContent: 'Remove from studio' });
  remove.onclick = () => {
    if (remove.dataset.sure !== '1') { remove.dataset.sure = '1'; remove.textContent = 'Tap again to remove'; setTimeout(() => { remove.dataset.sure = ''; remove.textContent = 'Remove from studio'; }, 3000); return; }
    stopPad(name); lib.remove('take', t.file).catch(() => {}); takes.delete(name); delete edits[name]; delete takeMeta[name];
    closeEditor(); autoPick(); renderTakes(); renderParts(); renderScene(); persist();
  };
  const cv = el('canvas', { className: 'wave', ariaLabel: 'Waveform of ' + takeLabel(name) });
  editor.canvas = cv;
  attachWaveDrag(cv);
  $('editorTitle').textContent = takeLabel(name);
  host.replaceChildren(cv,
    el('div', { className: 'bar', style: 'margin-top:8px' }, play, el('span', { className: 'note', id: 'padClock', style: 'margin:0' })),
    el('h3', { textContent: 'Trim and level', style: 'margin-top:14px' }), trimGrid,
    el('div', { className: 'bar', style: 'margin-top:12px' }, loopOn), loopGrid,
    el('h3', { textContent: 'Audition', style: 'margin-top:14px' }),
    el('div', { className: 'bar' }, chip('loop', 'Loop', () => pads.has(name) && restartPad(name)), chip('smooth', 'Smooth seam', () => pads.has(name) && restartPad(name)), chip('keep', 'Keep'), chip('duck', 'Duck on play'), job),
    el('div', { className: 'dials row2', style: 'margin-top:10px' }, pitch.root, level.root),
    el('div', { className: 'bar', style: 'margin-top:12px' }, auto, reset, bounce, remove), result, info);
  drawLoop();
  resultInfo(name);
  requestAnimationFrame(drawWave);
}
function drawWave() {
  const cv = editor.canvas, name = editor.name, t = name && takes.get(name);
  if (!cv || !t?.peaks || !cv.isConnected) return;
  const dpr = Math.min(2, window.devicePixelRatio || 1), W = cv.clientWidth, H = 150;
  if (!W) return;
  if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  const dur = t.raw.duration, e = fullEdit(name), x = s => s / dur * W, mid = H / 2, bins = t.peaks.length / 2;
  const cs = getComputedStyle(document.documentElement), col = n => cs.getPropertyValue(n).trim();
  g.fillStyle = col('--line'); g.fillRect(0, mid, W, 1);
  // loop region
  if (e.loopIn != null && e.loopOut != null) { g.fillStyle = 'rgba(255,202,114,.16)'; g.fillRect(x(e.loopIn), 0, x(e.loopOut) - x(e.loopIn), H); }
  g.fillStyle = col('--cyan');
  for (let px = 0; px < W; px++) {
    const k = Math.min(bins - 1, Math.floor(px / W * bins)), lo = t.peaks[k * 2], hi = t.peaks[k * 2 + 1];
    g.fillRect(px, mid - hi * (mid - 6), 1, Math.max(1, (hi - lo) * (mid - 6)));
  }
  // outside the trim
  g.fillStyle = 'rgba(6,19,26,.72)';
  g.fillRect(0, 0, x(e.in ?? 0), H); g.fillRect(x(e.out ?? dur), 0, W - x(e.out ?? dur), H);
  const handle = (s, colr, top, label) => {
    g.strokeStyle = colr; g.fillStyle = colr; g.lineWidth = 2;
    g.beginPath(); g.moveTo(x(s), 0); g.lineTo(x(s), H); g.stroke();
    g.beginPath(); const px = x(s), y = top ? 0 : H;
    g.moveTo(px - 8, y); g.lineTo(px + 8, y); g.lineTo(px, y + (top ? 12 : -12)); g.closePath(); g.fill();
  };
  handle(e.in ?? 0, col('--cyan'), true); handle(e.out ?? dur, col('--cyan'), true);
  if (e.loopIn != null && e.loopOut != null) { handle(e.loopIn, col('--amber'), false); handle(e.loopOut, col('--amber'), false); }
  // playhead
  const v = pads.get(name);
  if (v?.source) {
    const play = ctx.currentTime - v.startedAt, region = (e.out ?? dur) - (e.in ?? 0);
    const lp = fullEdit(name).loopIn != null && meta(name).loop;
    let pos = play * (v.source.playbackRate.value || 1);
    if (meta(name).loop && region > 0) pos = pos % region;
    g.fillStyle = col('--ink'); g.fillRect(x((e.in ?? 0) + Math.min(pos, region)), 0, 2, H);
    const clock = $('padClock'); if (clock) clock.textContent = `${mmss(Math.min(pos, region))} / ${mmss(region)}`;
  }
}
function attachWaveDrag(cv) {
  const which = (px, W, dur, e) => {
    const cand = [['in', e.in ?? 0], ['out', e.out ?? dur]];
    if (e.loopIn != null && e.loopOut != null) cand.push(['loopIn', e.loopIn], ['loopOut', e.loopOut]);
    let best = null;
    for (const [k, s] of cand) { const d = Math.abs(px - s / dur * W); if (d < 24 && (!best || d < best.d)) best = { k, d }; }
    return best?.k;
  };
  cv.addEventListener('pointerdown', ev => {
    const t = takes.get(editor.name), r = cv.getBoundingClientRect(), dur = t.raw.duration;
    const k = which(ev.clientX - r.left, r.width, dur, fullEdit(editor.name));
    if (!k) return;
    editor.drag = k; try { cv.setPointerCapture(ev.pointerId); } catch {}
    ev.preventDefault();
  });
  cv.addEventListener('pointermove', ev => {
    if (!editor.drag) return;
    const t = takes.get(editor.name), r = cv.getBoundingClientRect(), dur = t.raw.duration;
    const s = round(clamp((ev.clientX - r.left) / r.width) * dur, 2);
    editor.dials[editor.drag]?.set(s);
  });
  const end = () => { editor.drag = null; };
  cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
}

// ---------- Firefly prompt notebook ----------
const PROMPTS = [
  { part: 'fans', title: 'Wheel fans', text: 'Large electric ducted fan running at one steady speed, close up, constant tone and rush of air, no start or stop, dry, no music, no voices' },
  { part: 'boosters', title: 'Boosters', text: 'Small turbojet engine at steady high thrust, sharp whine over a deep exhaust roar, constant, no start or stop, dry, no music, no voices' },
  { part: 'tyres', title: 'Tyres', text: 'Rubber tyres rolling at a steady speed on smooth tarmac, low continuous rumble, no engine, dry, no music' },
  { part: 'wind', title: 'Wind in the cockpit', text: 'Fast air rushing past an aircraft canopy heard from inside the cockpit, steady, no engine, no gusts, no music' },
  { part: 'airbrake', title: 'Air brake', text: 'Aircraft air brake panel opening quickly, actuator push, firm stop, short burst of rushing air, one action only, close, dry' },
  { part: 'latch', title: 'Wing latch', text: 'Heavy metal locking pin engaging in an aircraft wing mechanism, one solid clunk, close, dry' },
  { part: 'touchdown', title: 'Touchdown', text: 'Heavy aircraft touching down on tarmac, one deep thump with a short tyre chirp and suspension compressing, no engine' },
];
const notebook = Array.isArray(saved.notebook) ? saved.notebook : PROMPTS.map(p => ({ ...p }));
function hasTakeFor(item) {
  const part = PARTS.find(p => p.id === item.part);
  if (part) return !!(veh[part.id].source && takes.has(veh[part.id].source));
  const key = item.title.toLowerCase();
  return [...takes.keys()].some(n => n.toLowerCase().includes(key));
}
function renderPrompts() {
  const host = $('promptList');
  if (!host) return;
  host.replaceChildren(...notebook.map((item, i) => {
    const ta = el('textarea', { value: item.text, ariaLabel: 'Prompt for ' + item.title, rows: 3 });
    ta.oninput = () => { item.text = ta.value; persist(); };
    const copy = el('button', { className: 'btn go', textContent: 'Copy prompt' });
    copy.onclick = async () => { try { await navigator.clipboard.writeText(item.text); say('Prompt copied.'); } catch { ta.focus(); ta.select(); say('Select the text and copy it.'); } };
    const del = el('button', { className: 'btn', textContent: 'Delete' });
    del.onclick = () => { if (del.dataset.sure !== '1') { del.dataset.sure = '1'; del.textContent = 'Tap again'; setTimeout(() => { del.dataset.sure = ''; del.textContent = 'Delete'; }, 3000); return; } notebook.splice(i, 1); persist(); renderPrompts(); };
    const ok = hasTakeFor(item);
    return el('div', { className: 'prompt' },
      el('div', { className: 'bar' }, el('b', {}, el('span', { className: 'dot' + (ok ? ' ok' : '') }), item.title), el('small', { textContent: ok ? 'take loaded' : 'no take yet' })),
      ta, el('div', { className: 'bar' }, copy, del));
  }));
}

// ---------- build the bench ----------
{
  const w = $('takesWrap'), card = (title, ...kids) => el('div', { className: 'card' }, ...(title ? [el('h2', { textContent: title })] : []), ...kids);
  const load = el('div', { className: 'bar' }), note = el('p', { className: 'note', id: 'takeNote' });
  const keep = el('button', { className: 'chip', id: 'keepTakes', textContent: 'Keep takes on this phone' });
  keep.setAttribute('aria-pressed', prefs.keepTakes);
  keep.onclick = async () => {
    prefs.keepTakes = !prefs.keepTakes; keep.setAttribute('aria-pressed', prefs.keepTakes); persist();
    if (prefs.keepTakes) { keepPersistent(); for (const t of takes.values()) lib.put('take', t.file).catch(() => {}); }
    else { try { await lib.clear('take'); const used = new Set(arr.tracks.flatMap(t => t.clips.map(c => c.take))); for (const t of takes.values()) if (used.has(t.file.name)) await lib.put('take', t.file); } catch {} }
    libUsage();
  };
  w.append(card('Sound sources', load, el('div', { className: 'bar', style: 'margin-top:8px' }, keep), note, el('p', { className: 'note', id: 'libUsage' })));
  loaderBar(load, 'takeNote');
  const rpm = dialFor({ label: 'Fan RPM', min: 0.2, max: 1, step: 0.05, fine: 0.01, fmt: v => round(v, 2), def: 0.7 }, macro.rpm, v => { macro.rpm = v; persist(); pads.forEach((_, n) => tunePad(n)); }, 76);
  const thrust = dialFor({ label: 'Thrust', min: 0, max: 1, step: 0.05, fine: 0.01, fmt: v => round(v, 2), def: 0.7 }, macro.thrust, v => { macro.thrust = v; persist(); pads.forEach((_, n) => tunePad(n)); }, 76);
  w.append(card('Bend the take', el('p', { className: 'note', style: 'margin:0 0 10px', textContent: 'Give a take the job Wheel fans or Boosters and these dials bend it, roughly as flight data would.' }),
    el('div', { className: 'dials row2' }, rpm.root, thrust.root),
    el('div', { className: 'bar', style: 'margin-top:12px' }, el('button', { className: 'btn', textContent: 'Stop all', onclick: stopAllPads }))));
  const ed = card('', el('div', { className: 'bar', style: 'justify-content:space-between;margin-bottom:10px' }, el('h2', { id: 'editorTitle', style: 'margin:0;overflow-wrap:anywhere', textContent: 'Edit take' }),
    el('button', { className: 'btn', textContent: 'Close', onclick: closeEditor })), el('div', { id: 'editorBody' }));
  ed.id = 'editorCard'; ed.hidden = true; w.append(ed);
  w.append(card('Takes', el('div', { id: 'takeList' })));
  w.append(card('Firefly prompt notebook',
    el('p', { className: 'note', style: 'margin:0 0 10px', textContent: 'Prompts for the sounds your takes do not seem to cover, going by their names. Edit them, copy one into Firefly, then add the take it makes.' }),
    el('div', { id: 'promptList' })));
  const nt = el('input', { type: 'text', placeholder: 'Title, for example Hangar door', ariaLabel: 'New prompt title' }), nx = el('textarea', { placeholder: 'Prompt text', ariaLabel: 'New prompt text', rows: 3 });
  const add = el('button', { className: 'btn go', textContent: 'Add prompt', onclick: () => { if (!nt.value.trim() || !nx.value.trim()) { say('Give the prompt a title and some text.'); return; } notebook.push({ title: nt.value.trim(), text: nx.value.trim() }); nt.value = nx.value = ''; persist(); renderPrompts(); } });
  w.lastChild.append(el('div', { style: 'display:grid;gap:8px;margin-top:12px' }, nt, nx, el('div', { className: 'bar' }, add)));
  w.append(card('Export', el('div', { className: 'bar' },
    el('button', { className: 'btn go', textContent: 'Bounce kept takes', onclick: e => bounceKept(e.currentTarget) }),
    el('button', { className: 'btn', textContent: 'Copy picks JSON', onclick: () => copyText(picksJson(), $('picksOut')) })),
    el('textarea', { id: 'picksOut', readonly: true, hidden: true, ariaLabel: 'Picks JSON', style: 'margin-top:8px' }),
    el('p', { className: 'note', id: 'takeExportNote' })));
  renderTakes(); renderPrompts(); libUsage();
  lib.all('take').then(files => { if (files.length) { addTakes(files, { keep: false }); if (typeof renderTracks === 'function') renderTracks(); } }).catch(() => {});
}
function picksJson() {
  return JSON.stringify([...takes.keys()].map(n => ({ file: n, seconds: Number.isFinite(takes.get(n).seconds) ? round(takes.get(n).seconds, 1) : undefined, edit: edits[n], ...meta(n) }))
    .filter(p => p.keep || (p.job && p.job !== JOBS[0]) || p.edit), null, 1);
}
