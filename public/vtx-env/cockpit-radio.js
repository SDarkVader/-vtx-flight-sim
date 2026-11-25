// Cockpit radio. Plays the player's own audio files, kept in this browser; nothing is uploaded or bundled.
// It reads no flight data and sends no commands.

export const stepTrack = (index, delta, count) => count ? ((index + delta) % count + count) % count : -1;
export const titleOf = name => name.replace(/\.[a-z0-9]+$/i, '').replaceAll('_', ' ').trim();
export const isAudio = file => /\.(mp3|mpeg|m4a|aac|ogg|wav|flac)$/i.test(file.name);
// Knob turn: one station for each 30 degrees of drag.
export const detents = degrees => Math.trunc(degrees / 30);
export const turnBetween = (from, to) => ((to - from + 540) % 360) - 180;

const DB = 'vtx-cockpit-radio', STORE = 'tracks', PREFS = 'vtx-cockpit-radio';
const OUTSIDE_LEVEL = 0.2;

function database() {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open(DB, 1);
    open.onupgradeneeded = () => open.result.createObjectStore(STORE, {keyPath: 'name'});
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(open.error);
  });
}
async function transact(mode, work) {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode), request = work(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(request?.result);
      tx.onerror = tx.onabort = () => reject(tx.error);
    });
  } finally { db.close(); }
}

const STYLE = `
#cockpit-radio{position:absolute;left:12px;bottom:12px;z-index:4;width:250px;padding:10px;border:1px solid #5d8f99;border-radius:8px;
  background:#0d2129ee;color:#e5f5f2;font:12px/1.35 system-ui,sans-serif;display:grid;gap:7px}
#cockpit-radio[hidden]{display:none}
#cockpit-radio .station{background:#06131a;border-radius:4px;padding:6px 8px;color:#ffca72;min-height:34px;overflow:hidden}
#cockpit-radio .row{display:flex;gap:8px;align-items:center;justify-content:space-between}
#cockpit-radio button,#cockpit-radio label.load{font:inherit;color:inherit;background:#142d36;border:1px solid #5d8f99;border-radius:4px;padding:6px 9px;cursor:pointer}
#cockpit-radio button[aria-pressed=true]{background:#164555;border-color:#8cdce6}
#cockpit-radio .knob{width:56px;height:56px;border-radius:50%;border:2px solid #8cdce6;background:#1b3a45;position:relative;cursor:grab;touch-action:none;flex:none}
#cockpit-radio .knob::after{content:'';position:absolute;left:25px;top:4px;width:3px;height:17px;background:#ffca72;border-radius:2px}
#cockpit-radio input[type=range]{width:100%}
#cockpit-radio input[type=file]{display:none}`;

export function createCockpitRadio({host, toggle, reportError = console.warn}) {
  let prefs = {};
  try { prefs = JSON.parse(localStorage.getItem(PREFS) || '{}'); } catch {}
  const savePrefs = () => { try { localStorage.setItem(PREFS, JSON.stringify(prefs)); } catch {} };
  let tracks = [], index = -1, on = false, inCockpit = false, url = null, ctx = null, level = null;
  const player = new Audio();
  player.preload = 'auto';

  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.append(style);
  const panel = document.createElement('section');
  panel.id = 'cockpit-radio';
  panel.hidden = true;
  panel.setAttribute('aria-label', 'Cockpit radio');
  panel.innerHTML = `
    <div class="station" role="status"></div>
    <div class="row">
      <button type="button" data-power aria-pressed="false">Radio off</button>
      <button type="button" data-prev aria-label="Previous song">◀</button>
      <div class="knob" role="slider" tabindex="0" aria-label="Song knob" aria-valuemin="1"></div>
      <button type="button" data-next aria-label="Next song">▶</button>
    </div>
    <label>Volume <input type="range" data-volume min="0" max="3" step="0.05"></label>
    <div class="row"><label class="load">Add my music<input type="file" multiple accept="audio/*,.mpeg"></label><button type="button" data-clear>Clear</button></div>`;
  host.append(panel);
  const q = selector => panel.querySelector(selector);
  const station = q('.station'), power = q('[data-power]'), knob = q('.knob'), volume = q('[data-volume]');
  volume.value = prefs.volume ?? 1;

  // Radio keys and clicks must not reach the flight or camera controls.
  for (const type of ['keydown', 'keyup', 'pointerdown', 'wheel', 'dblclick'])
    panel.addEventListener(type, event => event.stopPropagation());
  // Hand the keyboard back to the aircraft after a mouse click.
  panel.addEventListener('click', event => { if (event.detail) event.target.closest('button')?.blur(); });

  function show(message) {
    const name = tracks[index]?.name;
    station.textContent = message ?? (name ? `${index + 1}/${tracks.length}  ${titleOf(name)}` : 'No music yet. Add your tracks.');
    knob.setAttribute('aria-valuemax', String(Math.max(1, tracks.length)));
    knob.setAttribute('aria-valuenow', String(Math.max(1, index + 1)));
    knob.setAttribute('aria-valuetext', name ? titleOf(name) : 'No music');
    knob.style.transform = `rotate(${Math.max(0, index) * 30}deg)`;
  }
  // Cabin speaker: band-limited, and faint when the camera is outside.
  function assemble() {
    if (ctx) return;
    ctx = new AudioContext();
    const source = ctx.createMediaElementSource(player);
    const low = ctx.createBiquadFilter(), high = ctx.createBiquadFilter(), limit = ctx.createDynamicsCompressor();
    low.type = 'highpass'; low.frequency.value = 140;
    high.type = 'lowpass'; high.frequency.value = 7000;
    limit.threshold.value = -3; limit.ratio.value = 20;
    level = ctx.createGain();
    source.connect(low).connect(high).connect(level).connect(limit).connect(ctx.destination);
    applyLevel();
  }
  function applyLevel() {
    level?.gain.setTargetAtTime(Number(volume.value) * (inCockpit ? 1 : OUTSIDE_LEVEL), ctx.currentTime, 0.12);
  }
  function cue(next) {
    index = next;
    if (url) URL.revokeObjectURL(url);
    url = null;
    if (tracks[index]) {
      url = URL.createObjectURL(tracks[index].file);
      player.src = url;
      prefs.last = tracks[index].name;
      savePrefs();
    } else player.removeAttribute('src');
    show();
  }
  async function setPower(next) {
    on = next && tracks.length > 0;
    power.setAttribute('aria-pressed', String(on));
    power.textContent = on ? 'Radio on' : 'Radio off';
    if (!on) { player.pause(); return; }
    try {
      assemble();
      await ctx.resume();
      await player.play();
    } catch (error) {
      if (error.name === 'AbortError') return;
      on = false;
      power.setAttribute('aria-pressed', 'false');
      power.textContent = 'Radio off';
      reportError(error);
    }
  }
  function change(delta) {
    if (!tracks.length) return;
    cue(stepTrack(index, delta, tracks.length));
    if (on) void setPower(true);
  }
  function use(list) {
    tracks = list.sort((a, b) => a.name.localeCompare(b.name));
    cue(tracks.length ? Math.max(0, tracks.findIndex(t => t.name === prefs.last)) : -1);
  }

  power.onclick = () => void setPower(!on);
  q('[data-prev]').onclick = () => change(-1);
  q('[data-next]').onclick = () => change(1);
  volume.oninput = () => { prefs.volume = Number(volume.value); savePrefs(); if (ctx) applyLevel(); };
  player.onended = () => change(1);
  player.onerror = () => show('That file would not play.');
  knob.onkeydown = event => {
    const delta = {ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1}[event.key];
    if (delta) { event.preventDefault(); change(delta); }
  };
  knob.onwheel = event => { event.preventDefault(); change(Math.sign(event.deltaY)); };
  // Drag the knob round to tune.
  const angle = event => {
    const box = knob.parentElement.getBoundingClientRect(), own = knob.getBoundingClientRect();
    return Math.atan2(event.clientY - (own.top + own.height / 2), event.clientX - (own.left + own.width / 2 || box.left)) * 180 / Math.PI;
  };
  let drag = null;
  knob.addEventListener('pointerdown', event => { knob.setPointerCapture(event.pointerId); drag = {angle: angle(event), turned: 0}; });
  knob.addEventListener('pointermove', event => {
    if (!drag) return;
    const now = angle(event);
    drag.turned += turnBetween(drag.angle, now);
    drag.angle = now;
    const steps = detents(drag.turned);
    if (steps) { drag.turned -= steps * 30; change(steps); }
  });
  knob.onpointerup = knob.onpointercancel = () => { drag = null; };

  q('input[type=file]').onchange = async event => {
    const files = [...event.target.files].filter(isAudio);
    event.target.value = '';
    if (!files.length) return;
    const added = files.map(file => ({name: file.name, file}));
    try {
      await transact('readwrite', store => { for (const track of added) store.put(track); });
      use(await transact('readonly', store => store.getAll()));
    } catch (error) {
      // Still playable for this visit if the browser refuses to keep them.
      use([...tracks.filter(t => !added.some(a => a.name === t.name)), ...added]);
      reportError(error);
    }
  };
  q('[data-clear]').onclick = async () => {
    if (!confirm('Remove the radio\'s copies of your music from this browser? Your files stay where they are.')) return;
    await setPower(false);
    try { await transact('readwrite', store => store.clear()); } catch (error) { reportError(error); }
    use([]);
  };

  // The panel belongs to the cockpit view; the toggle button hides or shows it.
  const refresh = () => {
    panel.hidden = !inCockpit || prefs.hidden === true;
    toggle?.setAttribute('aria-pressed', String(prefs.hidden !== true));
  };
  if (toggle) toggle.onclick = () => { prefs.hidden = prefs.hidden !== true; savePrefs(); refresh(); };
  show();
  refresh();
  transact('readonly', store => store.getAll()).then(use).catch(reportError);

  return {
    update({cockpit}) {
      if (cockpit === inCockpit) return;
      inCockpit = cockpit;
      refresh();
      if (ctx) applyLevel();
    },
  };
}
