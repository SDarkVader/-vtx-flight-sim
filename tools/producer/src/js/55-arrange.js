// =====================================================================================
// TRACKS ENGINE: tracks, clips, tempo grid, transport, undo. Each track is a channel strip on the same desk
// as everything else, so the Mix bench, the master suite and the meters all see it.
// =====================================================================================
const SNAPS = [['Off', 0], ['Bar', -1], ['Beat', 1], ['1/2 beat', 0.5], ['1/4 beat', 0.25]];
const ZOOMS = [10, 20, 40, 60, 90, 140, 220, 340];
const TRACK_COLORS = ['#8cdce6', '#ffca72', '#ff9f6b', '#4fd18b', '#c9a3ff', '#ff8fb1'];
const num = (v, d = 0) => Number.isFinite(+v) ? +v : d;
function sanitizeArr(a) {
  const o = { name: 'Song', bpm: 120, beats: 4, snap: 2, zoom: 3, pos: 0, metro: false, follow: true, loop: { on: false, start: 0, end: 8 }, tracks: [] };
  if (!a || typeof a !== 'object') return o;
  if (typeof a.name === 'string' && a.name.trim()) o.name = a.name.slice(0, 40);
  o.bpm = clamp(num(a.bpm, 120), 40, 240); o.beats = clamp(Math.round(num(a.beats, 4)), 1, 12);
  o.snap = clamp(Math.round(num(a.snap, 2)), 0, SNAPS.length - 1); o.zoom = clamp(Math.round(num(a.zoom, 3)), 0, ZOOMS.length - 1); o.pos = Math.max(0, num(a.pos));
  o.metro = !!a.metro; o.follow = a.follow !== false;
  if (a.loop) { o.loop.on = !!a.loop.on; o.loop.start = Math.max(0, num(a.loop.start)); o.loop.end = Math.max(o.loop.start + 0.1, num(a.loop.end, 8)); }
  o.tracks = (Array.isArray(a.tracks) ? a.tracks : []).map((t, i) => ({
    id: String(t.id || 'tr' + uid()), name: String(t.name || 'Track ' + (i + 1)).slice(0, 30), color: String(t.color || TRACK_COLORS[i % TRACK_COLORS.length]),
    clips: (Array.isArray(t.clips) ? t.clips : []).map(c => ({
      id: String(c.id || uid()), take: String(c.take || ''), start: Math.max(0, num(c.start)), offset: Math.max(0, num(c.offset)), dur: Math.max(0.02, num(c.dur, 1)),
      gain: clamp(num(c.gain), -48, 24), fadeIn: Math.max(0, num(c.fadeIn)), fadeOut: Math.max(0, num(c.fadeOut)), semi: clamp(num(c.semi), -24, 24), rev: !!c.rev, mute: !!c.mute })),
  }));
  return o;
}
const arr = sanitizeArr(saved.arr);
const sel = { track: arr.tracks[0]?.id ?? null, clip: null };
let mixDirty = false;

function registerStrip(t, state) {
  if (!STRIP_IDS.includes(t.id)) STRIP_IDS.push(t.id);
  STRIP_NAMES[t.id] = t.name;
  mixState.strips[t.id] = merge(stripDefaults(), state || saved.mix?.strips?.[t.id] || {});
}
function dropStrip(id) {
  const i = STRIP_IDS.indexOf(id);
  if (i >= FIXED_STRIPS) STRIP_IDS.splice(i, 1);
  delete mixState.strips[id]; delete STRIP_NAMES[id]; delete LM.strips[id];
  if (A?.strips[id]) A.removeStrip(id);
}
for (const t of arr.tracks) registerStrip(t);

const trackOf = id => arr.tracks.find(t => t.id === id);
const clipOf = id => { for (const t of arr.tracks) { const c = t.clips.find(c => c.id === id); if (c) return { clip: c, track: t }; } return null; };
const spb = () => 60 / arr.bpm, barLen = () => spb() * arr.beats;
const rateOf = c => 2 ** (c.semi / 12);
const songEnd = () => arr.tracks.reduce((m, t) => t.clips.reduce((mm, c) => c.mute ? mm : Math.max(mm, c.start + c.dur), m), 0);
function snapT(t, off = false) {
  const s = SNAPS[arr.snap][1];
  if (off || !s) return Math.max(0, t);
  const unit = (s < 0 ? arr.beats : s) * spb();
  return Math.max(0, Math.round(t / unit) * unit);
}
const posText = t => {
  const bl = barLen(), bar = Math.floor(t / bl) + 1, beat = Math.floor((t % bl) / spb()) + 1;
  return `${String(bar).padStart(3, '0')}.${beat}`;
};
const clockText = t => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`;

// ---------- history: every edit can be undone, and nothing is lost ----------
const hist = { undo: [], redo: [], key: '', at: 0 };
const snapshot = () => JSON.stringify({ arr, strips: Object.fromEntries(arr.tracks.map(t => [t.id, mixState.strips[t.id]])) });
function checkpoint(key = '') {   // call before an edit; edits with the same key within 1.5 s share one step
  const now = Date.now();
  if (key && key === hist.key && now - hist.at < 1500) { hist.at = now; return; }
  hist.undo.push(snapshot()); if (hist.undo.length > 80) hist.undo.shift();
  hist.redo.length = 0; hist.key = key; hist.at = now; syncUndo();
}
function restore(json) {
  const s = JSON.parse(json), next = sanitizeArr(s.arr);
  arrStop(false);
  for (const t of arr.tracks) if (!next.tracks.some(n => n.id === t.id)) dropStrip(t.id);
  for (const k of Object.keys(next)) arr[k] = next[k];
  for (const t of arr.tracks) { registerStrip(t, s.strips?.[t.id]); ensureLiveStrip(t.id); }
  if (!trackOf(sel.track)) sel.track = arr.tracks[0]?.id ?? null;
  if (!clipOf(sel.clip)) sel.clip = null;
  remix(); changed();
}
function undo() { if (!hist.undo.length) return; hist.redo.push(snapshot()); restore(hist.undo.pop()); syncUndo(); }
function redo() { if (!hist.redo.length) return; hist.undo.push(snapshot()); restore(hist.redo.pop()); syncUndo(); }
function changed() { mixDirty = true; persist(); if (typeof renderTracks === 'function') renderTracks(); syncUndo(); }

// ---------- tracks ----------
function newTrack(name) {
  checkpoint();
  const i = arr.tracks.length, t = { id: 'tr' + uid(), name: name || 'Track ' + (i + 1), color: TRACK_COLORS[i % TRACK_COLORS.length], clips: [] };
  arr.tracks.push(t); registerStrip(t, {}); ensureLiveStrip(t.id);
  sel.track = t.id; sel.clip = null; changed(); return t;
}
function deleteTrack(id) {
  const t = trackOf(id); if (!t) return;
  savePoint('Before deleting ' + t.name, true);
  checkpoint(); arr.tracks.splice(arr.tracks.indexOf(t), 1); dropStrip(id);
  if (sel.track === id) sel.track = arr.tracks[0]?.id ?? null;
  sel.clip = null; changed();
}
function moveTrack(id, dir) {
  const i = arr.tracks.findIndex(t => t.id === id), j = i + dir;
  if (i < 0 || j < 0 || j >= arr.tracks.length) return;
  checkpoint(); [arr.tracks[i], arr.tracks[j]] = [arr.tracks[j], arr.tracks[i]]; changed();
}
function duplicateTrack(id) {
  const t = trackOf(id); if (!t) return;
  checkpoint();
  const n = { id: 'tr' + uid(), name: t.name + ' copy', color: t.color, clips: t.clips.map(c => ({ ...c, id: uid() })) };
  arr.tracks.splice(arr.tracks.indexOf(t) + 1, 0, n); registerStrip(n, { ...mixState.strips[t.id], solo: false }); ensureLiveStrip(n.id);
  sel.track = n.id; sel.clip = null; changed();
}
function renameTrack(id, name) { const t = trackOf(id); if (!t) return; t.name = name || 'Track'; STRIP_NAMES[id] = t.name; mixDirty = true; persist(); }

// ---------- clips ----------
function clipFromTake(name, start) {
  const t = takes.get(name), raw = t.raw;
  let offset = 0, dur = raw.duration, gain = 0, fadeIn = 0, fadeOut = 0;
  if (isEdited(name)) {   // start from the take's edit: its trim, fades and level
    const e = fullEdit(name); offset = e.in ?? 0; dur = (e.out ?? raw.duration) - offset; fadeIn = e.fadeIn; fadeOut = e.fadeOut;
    let peak = 0; for (let ch = 0; ch < raw.numberOfChannels; ch++) { const d = raw.getChannelData(ch); for (let i = Math.floor(offset * raw.sampleRate), n = Math.min(d.length, Math.floor((offset + dur) * raw.sampleRate)); i < n; i++) { const v = Math.abs(d[i]); if (v > peak) peak = v; } }
    const target = NORM[e.norm]; gain = linToDb((target == null ? 1 : Math.min(6, dbToLin(target) / Math.max(peak, 1e-4))) * dbToLin(e.gain));
  } else if (raw.duration < 20) { const b = body(raw); offset = b.from; dur = Math.max(0.05, b.to - b.from); }   // short one-shots: trim the silence
  return { id: uid(), take: name, start, offset, dur: Math.max(0.05, dur), gain: round(gain, 1), fadeIn, fadeOut, semi: 0, rev: false, mute: false };
}
function addClip(trackId, name, start) {
  const t = trackOf(trackId); if (!t || !takes.get(name)?.raw) return null;
  const c = clipFromTake(name, start); t.clips.push(c); sel.clip = c.id; sel.track = t.id; return c;
}
async function importFiles(files, { stems = false } = {}) {
  audio();
  const list = [...files].filter(f => AUDIO.test(f.name));
  if (!list.length) { say('No audio files in that selection.'); return; }
  addTakes(list, { force: true });
  checkpoint();
  let at = snapT(arrPos()), last = null, added = 0;
  say(`Reading ${list.length} file${list.length > 1 ? 's' : ''}…`, 30000);
  for (const f of list) {
    try { await rawBuffer(f.name); } catch { say(`Could not read ${f.name}. It may be too large to decode on this device.`); continue; }
    let target;
    if (stems) { target = newTrackQuiet(stem(f.name).replace(/_/g, ' ')); at = 0; }
    else { target = trackOf(sel.track) || newTrackQuiet('Track ' + (arr.tracks.length + 1)); if (last && last.track === target.id) at = last.end; }
    const c = addClip(target.id, f.name, at); if (!c) continue;
    last = { track: target.id, end: c.start + c.dur }; added++;
  }
  changed(); say(added ? `${added} clip${added > 1 ? 's' : ''} added.` : 'Nothing was added.');
}
function newTrackQuiet(name) {   // inside one history step
  const i = arr.tracks.length, t = { id: 'tr' + uid(), name: name || 'Track ' + (i + 1), color: TRACK_COLORS[i % TRACK_COLORS.length], clips: [] };
  arr.tracks.push(t); registerStrip(t, {}); ensureLiveStrip(t.id); sel.track = t.id; return t;
}
function editClip(id, patch, key) { const f = clipOf(id); if (!f) return; checkpoint(key); Object.assign(f.clip, patch); persist(); }
function splitClip(id, at) {
  const f = clipOf(id); if (!f) return false;
  const c = f.clip, r = rateOf(c), cut = at - c.start;
  if (cut < 0.03 || cut > c.dur - 0.03) return false;
  checkpoint();
  const b = { ...c, id: uid(), start: at, dur: c.dur - cut, fadeIn: 0 }, a = c;
  if (c.rev) { b.offset = c.offset; a.offset = c.offset + (c.dur - cut) * r; }
  else b.offset = c.offset + cut * r;
  a.dur = cut; a.fadeOut = 0;
  f.track.clips.push(b); sel.clip = b.id; changed(); return true;
}
function duplicateClip(id, times = 1) {
  const f = clipOf(id); if (!f) return;
  checkpoint(); let at = f.clip.start + f.clip.dur, last = null;
  for (let i = 0; i < times; i++) { last = { ...f.clip, id: uid(), start: at }; f.track.clips.push(last); at += f.clip.dur; }
  if (last) sel.clip = last.id; changed();
}
function chopClip(id, n) {
  const f = clipOf(id); if (!f || n < 2) return;
  checkpoint(); const c = f.clip, r = rateOf(c), part = c.dur / n, out = [];
  for (let i = 0; i < n; i++) {
    const p = { ...c, id: i ? uid() : c.id, start: c.start + i * part, dur: part, fadeIn: i ? 0 : c.fadeIn, fadeOut: i < n - 1 ? 0 : c.fadeOut };
    p.offset = c.rev ? c.offset + (n - 1 - i) * part * r : c.offset + i * part * r; out.push(p);
  }
  f.track.clips.splice(f.track.clips.indexOf(c), 1, ...out); sel.clip = out[0].id; changed();
}
function deleteClip(id) { const f = clipOf(id); if (!f) return; checkpoint(); f.track.clips.splice(f.track.clips.indexOf(f.clip), 1); if (sel.clip === id) sel.clip = null; changed(); }
function moveClipToTrack(id, trackId) { const f = clipOf(id), t = trackOf(trackId); if (!f || !t || f.track === t) return; checkpoint(); f.track.clips.splice(f.track.clips.indexOf(f.clip), 1); t.clips.push(f.clip); sel.track = t.id; changed(); }

// ---------- playing a clip, live or offline ----------
const reversedOf = t => {
  if (!t.rev) {
    const b = t.raw, r = ctx.createBuffer(b.numberOfChannels, b.length, b.sampleRate);
    for (let c = 0; c < b.numberOfChannels; c++) { const s = b.getChannelData(c), d = r.getChannelData(c); for (let i = 0, n = s.length; i < n; i++) d[i] = s[n - 1 - i]; }
    t.rev = r;
  }
  return t.rev;
};
// Plays `clip` from its own time `skip` seconds in, starting at context time `when`, never past `cap` seconds of clip time.
function playClip(c, dest, clip, when, skip = 0, cap = Infinity) {
  const t = takes.get(clip.take), raw = t?.raw;
  if (!raw) return null;
  const rate = rateOf(clip), D = raw.duration, dur = Math.min(clip.dur, cap) - skip;
  if (dur <= 0.002) return null;
  let buf = raw, off = clip.offset + skip * rate;
  if (clip.rev) { buf = reversedOf(t); off = D - (clip.offset + clip.dur * rate) + skip * rate; }
  if (off >= D || off < 0) return null;
  const src = c.createBufferSource(), g = c.createGain(), gain = dbToLin(clip.gain), fi = clip.fadeIn / 1000, fo = Math.min(clip.fadeOut / 1000, clip.dur);
  src.buffer = buf; src.playbackRate.value = rate;
  const inFade = fi > 0 && skip < fi;
  g.gain.setValueAtTime(inFade ? gain * skip / fi : gain, when);
  if (inFade) g.gain.linearRampToValueAtTime(gain, when + (fi - skip));
  const end = when + dur;
  if (fo > 0 && Math.min(clip.dur, cap) >= clip.dur - 1e-6) { g.gain.setValueAtTime(gain, Math.max(when + (inFade ? fi - skip : 0), end - fo)); g.gain.linearRampToValueAtTime(0, end); }
  src.connect(g); g.connect(dest); src.start(when, off, dur * rate);
  return { src, g };
}

// ---------- transport: a scheduler that stays a little ahead of the audio clock ----------
const eng = { playing: false, passes: [], sched: null, timer: 0, nodes: new Set() };
const LOOKAHEAD = 0.4;
async function decodeUsed() { for (const n of new Set(arr.tracks.flatMap(t => t.clips.map(c => c.take)))) if (takes.has(n)) await rawBuffer(n); }
function arrPos() {
  if (!eng.playing || !eng.passes.length) return arr.pos;
  const now = ctx.currentTime; let p = eng.passes[0];
  for (const q of eng.passes) if (q.t0 <= now) p = q;
  return Math.max(p.from, Math.min(p.to, p.from + now - p.t0));
}
async function arrPlay() {
  if (eng.playing) return;
  audio(); eng.playing = true; eng.passes = [];   // claimed first so a second tap cannot start a second player
  try { await decodeUsed(); } catch { eng.playing = false; say('Could not read one of the clips.'); return; }
  for (const t of arr.tracks) ensureLiveStrip(t.id);
  const loop = arr.loop.on && arr.loop.end > arr.loop.start + 0.05;
  let from = arr.pos; if (loop && (from < arr.loop.start || from >= arr.loop.end)) from = arr.loop.start;
  const p = { from, to: loop ? arr.loop.end : Infinity, t0: ctx.currentTime + 0.08 };
  eng.passes = [p]; eng.sched = { pass: p, cursor: from, first: true };
  eng.timer = setInterval(arrTick, 50); arrTick(); syncTransport();
}
function stopNodes() {
  const now = ctx.currentTime;
  for (const n of eng.nodes) { try { n.g.gain.cancelScheduledValues(now); n.g.gain.setTargetAtTime(0, now, 0.008); n.src.stop(now + 0.05); } catch {} }
  eng.nodes.clear();
}
function arrPause() {
  if (!eng.playing) return;
  arr.pos = arrPos(); clearInterval(eng.timer); eng.playing = false; stopNodes(); persist(); syncTransport();
}
function arrStop(rewind = true) {
  if (eng.playing) { clearInterval(eng.timer); eng.playing = false; stopNodes(); }
  if (rewind) arr.pos = arr.loop.on ? arr.loop.start : 0;
  persist(); syncTransport();
}
function arrSeek(t) {
  t = Math.max(0, t);
  if (eng.playing) { clearInterval(eng.timer); eng.playing = false; stopNodes(); arr.pos = t; arrPlay(); }
  else { arr.pos = t; persist(); syncTransport(); }
}
const arrToggle = () => eng.playing ? arrPause() : arrPlay();
function arrTick() {
  if (!eng.playing || !ctx) return;
  const now = ctx.currentTime, ahead = now + LOOKAHEAD, s = eng.sched;
  for (let guard = 0; guard < 8; guard++) {
    const p = s.pass, endCtx = p.to === Infinity ? Infinity : p.t0 + (p.to - p.from);
    const untilTl = p.from + (Math.min(ahead, endCtx) - p.t0);
    if (untilTl > s.cursor || s.first) { scheduleWindow(p, s.cursor, untilTl, s.first); s.first = false; s.cursor = Math.max(s.cursor, untilTl); }
    if (p.to !== Infinity && ahead >= endCtx) {   // loop: the next pass starts exactly where this one ends
      const np = { from: arr.loop.start, to: arr.loop.end, t0: endCtx };
      eng.passes.push(np); s.pass = np; s.cursor = np.from; s.first = true; continue;
    }
    break;
  }
  while (eng.passes.length > 1 && eng.passes[1].t0 <= now - 0.5) eng.passes.shift();
  if (s.pass.to === Infinity && arrPos() > songEnd() + 1.5) { arrStop(true); say('End of the song.'); }
}
function scheduleWindow(p, a, b, first) {
  const strips = A.strips;
  for (const t of arr.tracks) {
    const dest = strips[t.id]?.in; if (!dest) continue;
    for (const c of t.clips) {
      if (c.mute) continue;
      const cs = c.start, ce = cs + c.dur;
      let when, skip = 0;
      if (cs >= a && cs < b && cs < p.to) when = p.t0 + (cs - p.from);
      else if (first && cs < a && ce > a) { skip = a - cs; when = p.t0 + (a - p.from); }
      else continue;
      const n = playClip(ctx, dest, c, Math.max(when, ctx.currentTime), skip + Math.max(0, ctx.currentTime - when), p.to - cs);
      if (n) { eng.nodes.add(n); n.src.onended = () => { eng.nodes.delete(n); try { n.g.disconnect(); } catch {} }; }
    }
  }
  if (arr.metro) {
    const sp = spb();
    for (let k = Math.ceil(a / sp - 1e-9); k * sp < b; k++) { const when = p.t0 + (k * sp - p.from); if (when >= ctx.currentTime - 0.005) click(when, k % arr.beats === 0); }
  }
}
function click(when, accent) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.frequency.value = accent ? 1500 : 1000;
  g.gain.setValueAtTime(0.0001, when); g.gain.exponentialRampToValueAtTime(accent ? 0.3 : 0.18, when + 0.002); g.gain.exponentialRampToValueAtTime(0.0001, when + 0.05);
  o.connect(g).connect(ctx.destination); o.start(when); o.stop(when + 0.06);   // straight to the output, so it never reaches the meters or a bounce
}
