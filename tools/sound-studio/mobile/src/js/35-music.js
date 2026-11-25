// =====================================================================================
// MUSIC BENCH: the radio deck and the character rack. The rack shapes songs; the Mix bench shapes the channel.
// =====================================================================================
const player = new Audio();
player.preload = 'auto';
let songs = [], current = -1, url = null, history = [], fx = null;
const title = s => s.file.name.replace(AUDIO, '').replaceAll('_', ' ');
const shown = () => {
  const words = $('search').value.toLowerCase().split(/\s+/).filter(Boolean);
  return songs.map((s, i) => i).filter(i => words.every(w => (songs[i].path + ' ' + title(songs[i])).toLowerCase().includes(w)));
};
function addSongs(files, { keep = true } = {}) {
  const have = new Set(songs.map(s => s.file.name + '|' + s.file.size)), playing = songs[current];
  let added = 0;
  for (const file of files) {
    const key = file.name + '|' + file.size;
    if (!AUDIO.test(file.name) || have.has(key)) continue;
    have.add(key); added++;
    songs.push({ file, path: where(file) });
    if (keep && prefs.keepSongs) lib.put('song', file).catch(() => {});
  }
  songs.sort((a, b) => title(a).localeCompare(title(b), undefined, { numeric: true }));
  current = playing ? songs.indexOf(playing) : -1;
  history = [];
  drawList(); showNow();
  $('libNote').textContent = `${songs.length} songs${added ? `, ${added} added` : ''}. Everything stays on this device.`;
  if (!playing && songs.length) say(`${songs.length} songs. Pick one.`);
}
const LIMIT = 300;
function drawList() {
  const list = shown(), rows = list.slice(0, LIMIT).map(i => {
    const li = el('li'), b = el('button', { textContent: title(songs[i]) });
    const dir = songs[i].path.split('/').slice(0, -1).join(' / ');
    if (dir) b.append(el('small', { textContent: dir }));
    b.dataset.i = i; b.onclick = () => select(i, true, true);
    if (i === current) b.setAttribute('aria-current', 'true');
    li.append(b); return li;
  });
  if (list.length > LIMIT) rows.push(el('li', {}, el('p', { className: 'note', textContent: `Showing ${LIMIT} of ${list.length}. Search to narrow the list.` })));
  $('list').replaceChildren(...rows);
}
function showNow() {
  const s = songs[current];
  $('nowTitle').textContent = s ? title(s) : 'VTX Sound Studio';
  $('lcdTitle').textContent = s ? title(s) : (songs.length ? 'Turn the tuning dial or tap a song.' : 'Add songs or a music folder.');
  const at = shown().indexOf(current);
  $('lcdNo').textContent = s ? `SONG ${String(at + 1).padStart(2, '0')} / ${String(shown().length).padStart(2, '0')}` : 'NO SONG';
  for (const b of $('list').querySelectorAll('button')) b.toggleAttribute('aria-current', +b.dataset.i === current);
  setSession();
}
function select(i, remember = true, manual = false) {
  if (!songs[i]) return;
  audio();
  if (remember && current >= 0 && current !== i) history.push(current);
  current = i;
  if (url) URL.revokeObjectURL(url);
  url = URL.createObjectURL(songs[i].file);
  player.src = url;
  applySpeed();
  start();
  if (manual && prefs.tuneStatic) burst();
  showNow();
}
function start() {
  audio();
  Promise.resolve(player.play()).catch(e => { if (e.name !== 'AbortError') say('That file would not play: ' + (songs[current] ? title(songs[current]) : '')); });
}
function step(delta, manual = false) {
  const list = shown();
  if (!list.length) return;
  if (prefs.shuffle) {
    if (delta < 0 && history.length) return select(history.pop(), false, manual);
    const others = list.filter(i => i !== current);
    return select(others.length ? others[Math.floor(Math.random() * others.length)] : list[0], true, manual);
  }
  const at = list.indexOf(current);
  select(list[at < 0 ? 0 : ((at + delta) % list.length + list.length) % list.length], true, manual);
}
function toggle() { current < 0 ? step(1) : player.paused ? start() : player.pause(); }
player.onplay = () => { $('play').innerHTML = icon('pause'); $('play').setAttribute('aria-label', 'Pause'); };
player.onpause = () => { $('play').innerHTML = icon('play'); $('play').setAttribute('aria-label', 'Play'); };
player.onended = () => {
  if (prefs.repeat === 'one') { player.currentTime = 0; start(); return; }
  const list = shown();
  if (prefs.repeat === 'off' && !prefs.shuffle && list.indexOf(current) === list.length - 1) return;
  step(1);
};
player.onerror = () => { if (songs[current]) say('That file would not play: ' + title(songs[current])); };
player.ontimeupdate = () => {
  const t = `${mmss(player.currentTime)} / ${mmss(player.duration)}`;
  $('lcdTime').textContent = t;
  if (Date.now() > say.until) $('nowSub').textContent = songs[current] ? t : 'Add songs on the Music bench';
  if (player.duration && document.activeElement !== $('seek')) $('seek').value = player.currentTime / player.duration * 1000;
};
$('seek').onchange = e => { if (player.duration) player.currentTime = e.target.value / 1000 * player.duration; e.target.blur(); };
function setSession() {
  if (!('mediaSession' in navigator) || !songs[current]) return;
  try { navigator.mediaSession.metadata = new MediaMetadata({ title: title(songs[current]), artist: 'VTX Sound Studio' }); } catch {}
}
if ('mediaSession' in navigator) {
  const on = (a, f) => { try { navigator.mediaSession.setActionHandler(a, f); } catch {} };
  on('play', start); on('pause', () => player.pause());
  on('previoustrack', () => step(-1, true)); on('nexttrack', () => step(1, true));
  on('seekto', d => { if (d.seekTime != null) player.currentTime = d.seekTime; });
}

// ---------- remembered folders (only where the browser can) ----------
async function walk(directory, path, found) {
  for await (const entry of directory.values()) {
    if (entry.kind === 'directory') await walk(entry, path + entry.name + '/', found);
    else if (AUDIO.test(entry.name)) { const file = await entry.getFile(); paths.set(file, path + entry.name); found.push(file); }
  }
  return found;
}
const route = (role, files) => role === 'music' ? addSongs(files) : studioFolder(files);
async function loadFolders(ask) {
  let waiting = 0;
  for (const rec of await tx('folders', 'readonly', s => s.getAll())) {
    const handle = rec.handle;
    let permission = await handle.queryPermission({ mode: 'read' });
    if (permission !== 'granted' && ask) permission = await handle.requestPermission({ mode: 'read' });
    if (permission !== 'granted') { waiting++; continue; }
    try { route(rec.role || 'music', await walk(handle, handle.name + '/', [])); }
    catch { say(`Could not read the folder "${handle.name}". Has it moved?`); }
  }
  $('reloadMusic').hidden = !waiting;
  if (waiting && !songs.length) say('Press "Load my music" to open your remembered folders.');
}
async function rememberFolder(role) {
  let handle;
  try { handle = await showDirectoryPicker({ id: 'vtx-' + role, startIn: 'music' }); } catch { return; }
  let known = false;
  for (const rec of await tx('folders', 'readonly', s => s.getAll())) known ||= await rec.handle.isSameEntry(handle);
  if (!known) await tx('folders', 'readwrite', s => s.add({ handle, role }));
  route(role, await walk(handle, handle.name + '/', []));
  $('forgetMusic').hidden = false;
}
if (window.showDirectoryPicker) {
  $('linkMusic').hidden = false;
  $('linkMusic').onclick = () => rememberFolder('music');
  $('reloadMusic').onclick = () => loadFolders(true);
  $('forgetMusic').onclick = async () => {
    await tx('folders', 'readwrite', s => s.clear()); $('reloadMusic').hidden = true; $('forgetMusic').hidden = true;
    say('Forgot the folders. Your files were not touched.');
  };
  tx('folders', 'readonly', s => s.getAll()).then(r => { $('forgetMusic').hidden = !r.length; return loadFolders(false); }).catch(() => {});
}
$('songFiles').onchange = e => { addSongs([...e.target.files]); e.target.value = ''; };
$('songFolder').onchange = e => { addSongs([...e.target.files]); e.target.value = ''; };
$('search').oninput = () => { drawList(); showNow(); };
$('keepSongs').setAttribute('aria-pressed', prefs.keepSongs);
$('keepSongs').onclick = async e => {
  prefs.keepSongs = !prefs.keepSongs; e.currentTarget.setAttribute('aria-pressed', prefs.keepSongs); persist();
  if (prefs.keepSongs) { keepPersistent(); for (const s of songs) lib.put('song', s.file).catch(() => {}); say('Songs are kept in this browser.'); }
  else { try { await lib.clear('song'); } catch {} say('Stored songs removed. Your files were not touched.'); }
};
if (prefs.keepSongs) lib.all('song').then(files => files.length && addSongs(files, { keep: false })).catch(() => {});

// ---------- the Rack: character dials for the song ----------
const pctD = (label, def = 0, extra = {}) => ({ label, min: 0, max: 1, step: 0.05, fine: 0.01, fmt: pct, def, ...extra });
const P = {
  low:    { label: 'Low cut', list: [10, 40, 60, 80, 120, 180, 250, 350, 500, 800, 1200, 2000], text: ['Off', '40 Hz', '60 Hz', '80 Hz', '120 Hz', '180 Hz', '250 Hz', '350 Hz', '500 Hz', '800 Hz', '1.2 kHz', '2 kHz'], def: 0 },
  high:   { label: 'High cut', list: [20000, 12000, 9000, 7000, 5500, 4000, 3400, 2500, 1800, 1200, 800, 500], text: ['Off', '12 kHz', '9 kHz', '7 kHz', '5.5 kHz', '4 kHz', '3.4 kHz', '2.5 kHz', '1.8 kHz', '1.2 kHz', '800 Hz', '500 Hz'], def: 0 },
  bass:   { label: 'Bass', min: -12, max: 12, step: 1, fine: 0.25, fmt: fmtDb, def: 0 },
  mid:    { label: 'Mid', min: -12, max: 12, step: 1, fine: 0.25, fmt: fmtDb, def: 0 },
  treble: { label: 'Treble', min: -12, max: 12, step: 1, fine: 0.25, fmt: fmtDb, def: 0 },
  echo:   pctD('Echo'),
  time:   { label: 'Echo time', list: TIMES, text: TIMES.map(t => t < 1000 ? t + ' ms' : '1 s'), def: 5 },
  fb:     { label: 'Repeats', min: 0, max: 0.85, step: 0.05, fine: 0.01, fmt: pct, def: 0.35 },
  reverb: pctD('Reverb'),
  room:   { label: 'Room', list: [0, 1, 2, 3], text: ROOM_NAMES, def: 2 },
  drive:  pctD('Drive'),
  wobble: pctD('Wobble'),
  rate:   { label: 'Wobble rate', list: [0.5, 1, 2, 3, 5, 7, 10], text: ['0.5 Hz', '1 Hz', '2 Hz', '3 Hz', '5 Hz', '7 Hz', '10 Hz'], def: 3 },
  static: pctD('Static'),
  width:  { label: 'Width', min: 0, max: 2, step: 0.1, fine: 0.02, center: 1, fmt: v => v === 0 ? 'Mono' : v === 1 ? 'Normal' : round(v, 2) + 'x', def: 1 },
  pan:    { label: 'Balance', min: -1, max: 1, step: 0.1, fine: 0.02, fmt: panText, def: 0 },
  speed:  { label: 'Speed', min: 0.5, max: 2, step: 0.05, fine: 0.01, center: 1, fmt: v => round(v, 2) + 'x', def: 1 },
  volume: { label: 'Volume', min: 0, max: 2, step: 0.05, fine: 0.01, fmt: pct, def: 0.8 },
};
const rack = Object.fromEntries(Object.entries(P).map(([k, p]) => [k, p.def]));
for (const k of Object.keys(rack)) if (typeof saved.rack?.[k] === 'number') rack[k] = saved.rack[k];
const rackDials = {};
function rackDial(id, size = 72) {
  return rackDials[id] = dialFor(P[id], rack[id], v => { rack[id] = v; applyParam(id); persist(); }, size);
}
function buildRadio() {
  const c = ctx, f = fx = {};
  const bq = (type, freq, q = 0.7) => { const b = c.createBiquadFilter(); b.type = type; b.frequency.value = freq; b.Q.value = q; return b; };
  const g = (v = 1) => { const n = c.createGain(); n.gain.value = v; return n; };
  f.src = c.createMediaElementSource(player);
  f.up = g(); f.up.channelCount = 2; f.up.channelCountMode = 'explicit'; f.up.channelInterpretation = 'speakers';
  f.hp = bq('highpass', 10); f.lp = bq('lowpass', 20000);
  f.bass = bq('lowshelf', 110); f.mid = bq('peaking', 1000, 0.9); f.treble = bq('highshelf', 4500);
  f.dry = g(); f.wet = g(0); f.shaper = c.createWaveShaper(); f.shaper.oversample = '2x'; f.sum = g();
  f.src.connect(f.up); f.up.connect(f.hp); f.hp.connect(f.lp); f.lp.connect(f.bass); f.bass.connect(f.mid); f.mid.connect(f.treble);
  f.treble.connect(f.dry); f.treble.connect(f.shaper); f.shaper.connect(f.wet); f.dry.connect(f.sum); f.wet.connect(f.sum);
  // wobble: a short delay whose time is wavered by a slow oscillator
  f.wob = c.createDelay(0.05); f.wob.delayTime.value = 0.008;
  f.lfo = c.createOscillator(); f.lfo.frequency.value = 3; f.lfoDepth = g(0);
  f.lfo.connect(f.lfoDepth); f.lfoDepth.connect(f.wob.delayTime); f.lfo.start();
  f.sum.connect(f.wob);
  // stereo width as a mid/side matrix, then balance
  f.split = c.createChannelSplitter(2); f.merge = c.createChannelMerger(2);
  f.ll = g(); f.lr = g(0); f.rl = g(0); f.rr = g();
  f.wob.connect(f.split);
  f.split.connect(f.ll, 0); f.split.connect(f.rl, 0); f.split.connect(f.lr, 1); f.split.connect(f.rr, 1);
  f.ll.connect(f.merge, 0, 0); f.lr.connect(f.merge, 0, 0); f.rl.connect(f.merge, 0, 1); f.rr.connect(f.merge, 0, 1);
  f.pan = makePanner(c);
  f.merge.connect(f.pan.input);
  f.proc = g(); f.bus = g(); f.pan.output.connect(f.proc); f.proc.connect(f.bus);   // proc is the A/B switch for everything above
  // echo and reverb of the rack itself
  f.echoSend = g(0); f.delay = c.createDelay(1.5); f.delay.delayTime.value = 0.25; f.fb = g(0.35); f.damp = bq('lowpass', 4200);
  f.proc.connect(f.echoSend); f.echoSend.connect(f.delay); f.delay.connect(f.damp); f.damp.connect(f.fb); f.fb.connect(f.delay); f.damp.connect(f.bus);
  f.verbSend = g(0); f.verb = c.createConvolver(); f.verb.buffer = room(c, rack.room);
  f.proc.connect(f.verbSend); f.verbSend.connect(f.verb); f.verb.connect(f.bus);
  // radio hiss under everything
  f.hissSrc = c.createBufferSource(); f.hissSrc.buffer = noise; f.hissSrc.loop = true;
  f.hissHp = bq('highpass', 1800); f.hiss = g(0); f.hissOn = g();
  f.hissSrc.connect(f.hissHp); f.hissHp.connect(f.hiss); f.hiss.connect(f.hissOn); f.hissOn.connect(f.bus); f.hissSrc.start();
  f.direct = g(0); f.up.connect(f.direct); f.direct.connect(f.bus);
  f.vol = g(0.8); f.bus.connect(f.vol); f.vol.connect(A.strips.music.in);
  applyBypass();
}
function applyBypass() {
  if (!fx) return;
  const t = ctx.currentTime;
  fx.proc.gain.setTargetAtTime(prefs.bypass ? 0 : 1, t, 0.02); fx.direct.gain.setTargetAtTime(prefs.bypass ? 1 : 0, t, 0.02);
  fx.hissOn.gain.setTargetAtTime(prefs.bypass ? 0 : 1, t, 0.02);
}
function burst() {
  if (!ctx || !fx) return;
  const t = ctx.currentTime, src = ctx.createBufferSource(), gn = ctx.createGain(), bp = ctx.createBiquadFilter();
  src.buffer = noise; bp.type = 'bandpass'; bp.frequency.value = 2400; bp.Q.value = 0.6;
  gn.gain.setValueAtTime(0, t); gn.gain.linearRampToValueAtTime(0.5, t + 0.03); gn.gain.exponentialRampToValueAtTime(0.001, t + 0.38);
  src.connect(bp).connect(gn).connect(fx.bus); src.start(t, Math.random() * 2); src.stop(t + 0.4);
}
function setDrive(v) {
  const n = 1024, curve = new Float32Array(n), k = 1 + v * 30;
  for (let i = 0; i < n; i++) { const x = i / (n - 1) * 2 - 1; curve[i] = Math.tanh(k * x) / Math.tanh(k); }
  fx.shaper.curve = curve;
  const t = ctx.currentTime;   // the saturated path is pulled down by k^0.6 so typical program stays near its level as drive rises
  fx.wet.gain.setTargetAtTime(v / k ** 0.6, t, 0.03); fx.dry.gain.setTargetAtTime(1 - v * 0.7, t, 0.03);
}
function setWidth(w) {
  const t = ctx.currentTime, a = (1 + w) / 2, b = (1 - w) / 2;
  for (const [node, val] of [[fx.ll, a], [fx.rr, a], [fx.lr, b], [fx.rl, b]]) node.gain.setTargetAtTime(val, t, 0.03);
}
function setLock() { for (const k of ['preservesPitch', 'webkitPreservesPitch', 'mozPreservesPitch']) if (k in player) player[k] = prefs.lock; }
function applySpeed() { player.defaultPlaybackRate = rack.speed; player.playbackRate = rack.speed; setLock(); }
function applyParam(id) {
  if (id === 'speed') return applySpeed();
  if (!fx) return;
  const t = ctx.currentTime, v = rack[id], to = (param, x, k = 0.03) => param.setTargetAtTime(x, t, k);
  switch (id) {
    case 'low': to(fx.hp.frequency, P.low.list[v]); break;
    case 'high': to(fx.lp.frequency, P.high.list[v]); break;
    case 'bass': to(fx.bass.gain, v); break;
    case 'mid': to(fx.mid.gain, v); break;
    case 'treble': to(fx.treble.gain, v); break;
    case 'echo': to(fx.echoSend.gain, v); break;
    case 'time': to(fx.delay.delayTime, TIMES[v] / 1000, 0.08); break;
    case 'fb': to(fx.fb.gain, v); break;
    case 'reverb': to(fx.verbSend.gain, v * 1.2); break;
    case 'room': fx.verb.buffer = room(ctx, v); break;
    case 'drive': setDrive(v); break;
    case 'wobble': to(fx.lfoDepth.gain, v * 0.001); break;
    case 'rate': to(fx.lfo.frequency, P.rate.list[v], 0.1); break;
    case 'static': to(fx.hiss.gain, v * 0.07); break;
    case 'width': setWidth(v); break;
    case 'pan': fx.pan.set(v, t, 0.03); break;
    case 'volume': to(fx.vol.gain, v); break;
  }
}
const PRESETS = {
  Flat: {},
  Cabin: { low: 5, high: 4, drive: 0.1, bass: -1 },
  Telephone: { low: 7, high: 6, drive: 0.35, treble: 2, width: 0 },
  Underwater: { high: 10, wobble: 0.45, rate: 2, reverb: 0.35, room: 2, bass: 3 },
  Tape: { high: 3, bass: 2, wobble: 0.25, rate: 3, static: 0.25, drive: 0.2 },
  Hall: { reverb: 0.45, room: 2, echo: 0.15, time: 7, fb: 0.3, treble: 1 },
  Bunker: { low: 3, high: 5, reverb: 0.5, room: 3, echo: 0.25, time: 9, fb: 0.5, drive: 0.15 },
  'Slowed and wet': { speed: 0.8, reverb: 0.4, room: 3, bass: 3, lock: false },
  Chipmunk: { speed: 1.5, treble: 3, lock: false },
};
function usePreset(name) {
  const set = PRESETS[name];
  for (const id of Object.keys(P)) if (id !== 'volume') rackDials[id].set(set[id] ?? P[id].def);
  prefs.lock = set.lock ?? true; $('lockChip').setAttribute('aria-pressed', prefs.lock); setLock();
  for (const b of $('presets').children) b.setAttribute('aria-pressed', b.dataset.p === name);
  say('Preset: ' + name); persist();
}

// ---------- deck dials and rack layout ----------
{
  const tune = makeDial({ endless: true, notches: 12, label: 'Tuning', size: 132, note: 'Song', onStep: n => step(n, true) });
  const jog = makeDial({ endless: true, notches: 24, label: 'Jog', size: 88, note: '5 s a click', onStep: n => { if (player.duration) player.currentTime = clamp(player.currentTime + n * 5, 0, player.duration); } });
  $('radioDials').append(jog.root, tune.root, rackDial('volume', 88).root);
  const groups = [
    ['Tone', ['low', 'high', 'bass', 'mid', 'treble']],
    ['Space', ['echo', 'time', 'fb', 'reverb', 'room']],
    ['Character', ['drive', 'wobble', 'rate', 'static', 'width', 'pan']],
    ['Time', ['speed']],
  ];
  for (const [name, ids] of groups) {
    const card = el('div', { className: 'card' }, el('h2', { textContent: name })), grid = el('div', { className: 'dials' });
    for (const id of ids) grid.append(rackDial(id).root);
    if (name === 'Time') {
      const chip = el('button', { className: 'chip', id: 'lockChip', textContent: 'Keep pitch' });
      chip.setAttribute('aria-pressed', prefs.lock);
      chip.onclick = () => { prefs.lock = !prefs.lock; chip.setAttribute('aria-pressed', prefs.lock); setLock(); persist(); };
      grid.append(el('div', { style: 'display:grid;align-content:center;justify-items:center;gap:6px' }, chip,
        el('small', { className: 'note', textContent: 'Off: slower is lower, faster is higher, like tape.' })));
    }
    card.append(grid); $('rackGroups').append(card);
  }
  for (const name of Object.keys(PRESETS)) {
    const b = el('button', { className: 'chip', textContent: name });
    b.dataset.p = name; b.setAttribute('aria-pressed', 'false'); b.onclick = () => usePreset(name);
    $('presets').append(b);
  }
  $('bypass').setAttribute('aria-pressed', prefs.bypass);
  $('bypass').onclick = e => { prefs.bypass = !prefs.bypass; e.currentTarget.setAttribute('aria-pressed', prefs.bypass); applyBypass(); persist(); };
  for (const id of ['fine', 'haptics', 'clicks']) {
    $(id).setAttribute('aria-pressed', prefs[id]);
    $(id).onclick = e => { prefs[id] = !prefs[id]; e.currentTarget.setAttribute('aria-pressed', prefs[id]); if (id === 'clicks') audio(); persist(); };
  }
  $('rackNote').textContent = navigator.vibrate ? 'Fine increments make each click smaller. Dial buzz uses your phone vibration.' : 'Fine increments make each click smaller. This browser cannot vibrate, so the dial buzz does nothing here.';
  let lock = null;
  async function wake(on) {
    try { if (on) lock = await navigator.wakeLock.request('screen'); else { await lock?.release(); lock = null; } }
    catch { prefs.wake = false; $('wake').setAttribute('aria-pressed', 'false'); say('This browser would not keep the screen on.'); }
  }
  $('wake').setAttribute('aria-pressed', prefs.wake);
  $('wake').onclick = e => {
    if (!navigator.wakeLock) { say('This browser cannot keep the screen on.'); return; }
    prefs.wake = !prefs.wake; e.currentTarget.setAttribute('aria-pressed', prefs.wake); wake(prefs.wake); persist();
  };
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    if (prefs.wake && !lock) wake(true);
    if (ctx && ctx.state !== 'running' && !player.paused) Promise.resolve(ctx.resume()).catch(() => {});
  });
  $('shuffle').onclick = e => { prefs.shuffle = !prefs.shuffle; e.currentTarget.setAttribute('aria-pressed', prefs.shuffle); persist(); };
  const REPEATS = { all: 'Repeat all', one: 'Repeat one', off: 'No repeat' };
  $('repeat').onclick = () => { prefs.repeat = { all: 'one', one: 'off', off: 'all' }[prefs.repeat]; $('repeat').textContent = REPEATS[prefs.repeat]; persist(); };
  $('tuneStatic').onclick = e => { prefs.tuneStatic = !prefs.tuneStatic; e.currentTarget.setAttribute('aria-pressed', prefs.tuneStatic); persist(); };
  $('repeat').textContent = REPEATS[prefs.repeat];
  $('shuffle').setAttribute('aria-pressed', prefs.shuffle);
  $('tuneStatic').setAttribute('aria-pressed', prefs.tuneStatic);
  $('prev').onclick = () => step(-1, true);
  $('next').onclick = () => step(1, true);
  $('play').onclick = toggle;
  for (const b of $('musicSeg').children) b.onclick = () => showMusic(b.dataset.v);
}
function showMusic(v) {
  prefs.musicView = v;
  $('music-deck').hidden = v !== 'deck'; $('music-rack').hidden = v !== 'rack';
  for (const b of $('musicSeg').children) b.setAttribute('aria-pressed', b.dataset.v === v);
  persist();
}
