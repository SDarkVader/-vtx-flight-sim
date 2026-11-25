// =====================================================================================
// VEHICLE BENCH: the engine of the desktop Vehicle Designer, routed through the Vehicle strip
// =====================================================================================
const live = new Map();    // part id -> stop function
const ui = {};             // part id -> { button }
let timers = [], openPart = null;

function channel(s) {
  const input = ctx.createGain(), low = ctx.createBiquadFilter(), high = ctx.createBiquadFilter();
  const out = ctx.createGain(), send = ctx.createGain(), sources = [];
  low.type = 'lowshelf'; low.frequency.value = 220; low.gain.value = s.weight;
  high.type = 'highshelf'; high.frequency.value = 2600; high.gain.value = s.edge;
  out.gain.value = s.volume; send.gain.value = s.echo;
  input.connect(low).connect(high).connect(out).connect(vMaster);
  out.connect(send).connect(vEcho);
  return { input, sources, kill() {
    out.gain.setTargetAtTime(0, ctx.currentTime, 0.03); send.gain.setTargetAtTime(0, ctx.currentTime, 0.03);
    for (const node of sources) { try { node.stop(ctx.currentTime + 0.15); } catch {} }
  } };
}
function envelope(ch, at, length, level, fade) {
  const g = ctx.createGain(), f = Math.min(fade, length / 2);
  g.gain.setValueAtTime(0, at); g.gain.linearRampToValueAtTime(level, at + f);
  g.gain.setValueAtTime(level, at + length - f); g.gain.linearRampToValueAtTime(0, at + length);
  g.connect(ch.input); return g;
}
function playerNode(ch, buffer, to, at, offset, length, rate, loop) {
  const src = ctx.createBufferSource();
  src.buffer = buffer; src.playbackRate.value = rate; src.loop = !!loop;
  if (loop) { src.loopStart = loop[0]; src.loopEnd = loop[1]; }
  src.connect(to); src.start(at, offset); if (Number.isFinite(length)) src.stop(at + length);
  ch.sources.push(src); return src;
}
function standIn(ch, to, part, s, at, length) {
  const [hum, air] = part.tone;
  if (hum) {
    const osc = ctx.createOscillator(), g = ctx.createGain();
    osc.type = s.rough ? 'sawtooth' : 'triangle'; osc.frequency.value = hum * s.pitch;
    g.gain.value = part.kind === 'loop' ? 0.12 : 0.16; osc.connect(g).connect(to);
    osc.start(at); if (Number.isFinite(length)) osc.stop(at + length); ch.sources.push(osc);
    if (s.layer) {
      const two = ctx.createOscillator(), g2 = ctx.createGain();
      two.type = 'sine'; two.frequency.value = hum * s.pitch * 3.02; g2.gain.value = 0.07 * s.layer;
      two.connect(g2).connect(to); two.start(at); if (Number.isFinite(length)) two.stop(at + length); ch.sources.push(two);
    }
  }
  const band = ctx.createBiquadFilter(); band.type = 'bandpass'; band.frequency.value = air * s.pitch; band.Q.value = s.rough ? 2.5 : 0.8;
  band.connect(to);
  playerNode(ch, noise, band, at, Math.random(), length, 1, [0, noise.duration]);
}
function clunk(ch, at, amount, part) {
  if (!amount) return;
  const osc = ctx.createOscillator(), g = ctx.createGain(), click = ctx.createBiquadFilter(), g2 = ctx.createGain();
  const base = Math.max(45, Math.min(120, part.tone[0] || 70));
  osc.frequency.setValueAtTime(base * 2, at); osc.frequency.exponentialRampToValueAtTime(base * 0.6, at + 0.18);
  g.gain.setValueAtTime(0.5 * amount, at); g.gain.exponentialRampToValueAtTime(0.001, at + 0.32);
  osc.connect(g).connect(ch.input); osc.start(at); osc.stop(at + 0.34); ch.sources.push(osc);
  click.type = 'bandpass'; click.frequency.value = part.tone[1] * 1.6; click.Q.value = 1.4;
  g2.gain.setValueAtTime(0.7 * amount, at); g2.gain.exponentialRampToValueAtTime(0.001, at + 0.09);
  click.connect(g2).connect(ch.input);
  playerNode(ch, noise, click, at, Math.random(), 0.1, 1);
}
function layerName(s) {
  const names = [...takes.keys()].filter(n => n !== s.source);
  return names.find(n => /geared|motor/i.test(n)) ?? names[0] ?? null;
}
// Schedule one part on a channel, starting at `at`.
function build(ch, part, s, buffer, extra, at) {
  const level = buffer ? body(buffer).boost : 1;
  if (part.kind === 'loop') {
    if (!buffer) return standIn(ch, envelope(ch, at, 3600, 0.8, 0.5), part, s, at, 3600);
    const b = body(buffer), pad = Math.min(0.4, (b.to - b.from) * 0.15), lp = b.loop || [b.from + pad, b.to - pad];
    const g = envelope(ch, at, 3600, level, 0.5);
    playerNode(ch, buffer, g, at, lp[0], Infinity, s.pitch, lp);
    if (extra && s.layer) playerNode(ch, extra, envelope(ch, at, 3600, body(extra).boost * s.layer * 0.4, 0.5), at, 0, Infinity, s.pitch * 0.5, [0, extra.duration]);
    return;
  }
  if (part.kind === 'hit') {
    if (buffer) playerNode(ch, buffer, envelope(ch, at, 0.9, level, 0.02), at, body(buffer).from, 0.9, s.pitch);
    else standIn(ch, envelope(ch, at, 0.45, 1, 0.01), part, s, at, 0.45);
    clunk(ch, at, Math.max(0.35, s.clunk), part);
    if (s.layer > 0.4) clunk(ch, at + 0.09, s.layer * 0.5, part);
    return;
  }
  const len = s.length, head = Math.min(0.5, len * 0.3), tail = Math.min(0.6, len * 0.35);
  clunk(ch, at, s.clunk * 0.6, part);
  if (buffer) {
    const b = body(buffer), size = b.to - b.from, mid = b.from + size * 0.3, end = b.from + size * 0.7;
    playerNode(ch, buffer, envelope(ch, at, head + 0.15, level, 0.04), at, b.from, head + 0.15, s.pitch);
    const run = playerNode(ch, buffer, envelope(ch, at + head, Math.max(0.2, len - head - tail) + 0.2, level, 0.12),
      at + head, mid, Math.max(0.2, len - head - tail) + 0.2, s.pitch, [mid, Math.max(mid + 0.1, end)]);
    run.playbackRate.setValueAtTime(s.pitch * 0.9, at + head);
    run.playbackRate.linearRampToValueAtTime(s.pitch, at + head + 0.3);
    playerNode(ch, buffer, envelope(ch, at + len - tail, tail, level, 0.05), at + len - tail, Math.max(b.from, b.to - tail * s.pitch), tail, s.pitch);
  } else standIn(ch, envelope(ch, at, len, 1, 0.15), part, s, at, len);
  if (extra && s.layer) playerNode(ch, extra, envelope(ch, at, len, body(extra).boost * s.layer * 0.5, 0.1), at, body(extra).from, len, s.pitch * 0.6, [0, extra.duration]);
  clunk(ch, at + len, s.clunk, part);
}
function markPart(id, on) {
  const b = ui[id]?.button;
  if (b) { b.setAttribute('aria-pressed', on); b.textContent = on ? 'Stop' : 'Play'; b.classList.toggle('on-air', on); }
}
function stopPart(id) { live.get(id)?.(); live.delete(id); markPart(id, false); }
async function playPart(part, seconds) {
  const s = veh[part.id];
  stopPart(part.id);
  const token = {}; s.token = token;
  audio();
  let buffer = null, extra = null;
  try {
    buffer = await bufferOf(s.source);
    if (s.layer && part.kind !== 'hit') extra = await bufferOf(layerName(s));
  } catch { say('Could not read ' + s.source); return; }
  if (s.token !== token) return;
  const ch = channel(s);
  live.set(part.id, () => ch.kill());   // registered first, so anything that starts can always be silenced
  markPart(part.id, true);
  try { build(ch, part, s, buffer, extra, ctx.currentTime + 0.05); }
  catch { stopPart(part.id); say(`${part.name} could not play with these settings.`); return; }
  if (part.kind === 'hit' && mixState.duck.onHits) duck();
  persist();
  const lasts = seconds ?? (part.kind === 'loop' ? 0 : part.kind === 'hit' ? 1.5 : s.length + 1.2);
  const timer = lasts ? setTimeout(() => stopPart(part.id), lasts * 1000) : 0;
  live.set(part.id, () => { clearTimeout(timer); ch.kill(); });
}
function stopAllVehicle() {
  stopFlight();
  for (const part of PARTS) { veh[part.id].token = null; stopPart(part.id); }
}

// ---------- flight replay ----------
/*FLIGHT_DATA*/const FLIGHT = {};
const PROCEDURES = {
  'VTOL takeoff and landing': [['wings', 'Wing deployment on the ground'], ['fansUp', 'Fans start, pods down'],
    ['vLift', 'Vertical lift-off'], ['vLand', 'Descent and touchdown'], ['vDown', 'Settled after landing']],
  'Horizontal takeoff, then transition to hover': [['wings', 'Wing deployment on the ground'], ['jetStart', 'Boosters light'],
    ['roll', 'Takeoff roll'], ['hLift', 'Lift-off and climb'], ['transition', 'Transition to hover'], ['hover', 'Hover']],
};
let flight = 0, flightKill = null;
function stopFlight() {
  flight++;
  timers.forEach(clearTimeout); timers = [];
  flightKill?.(); flightKill = null;
}
// A continuously running version of a part whose level and pitch follow the record.
async function voice(part) {
  const s = veh[part.id], ch = channel(s), g = ctx.createGain();
  g.gain.value = 0; g.connect(ch.input);
  const buffer = await bufferOf(s.source), at = ctx.currentTime + 0.02;
  if (buffer) {
    const b = body(buffer), size = b.to - b.from, loop = b.loop || [b.from + size * 0.25, b.from + size * 0.75];
    const level = ctx.createGain(); level.gain.value = b.boost; level.connect(g);
    playerNode(ch, buffer, level, at, loop[0], Infinity, s.pitch, loop);
  } else standIn(ch, g, part, s, at, 3600);
  const running = ch.sources.slice(), bases = running.map(node => node.playbackRate?.value);   // clunks added later are left alone
  return { ch, s, part, on: false,
    set(level, rate = 1) {
      const now = ctx.currentTime;
      g.gain.setTargetAtTime(level, now, 0.08);
      running.forEach((node, i) => {
        if (node.playbackRate) node.playbackRate.setTargetAtTime(bases[i] * rate, now, 0.1);
        else node.detune?.setTargetAtTime(1200 * Math.log2(rate), now, 0.1);
      });
    } };
}
async function runStep(key, label, mine) {
  const rows = FLIGHT[key], voices = {};
  if (!rows) return;
  for (const part of PARTS) if (part.kind !== 'hit' && part.id !== 'airbrake') voices[part.id] = await voice(part);
  const kill = () => Object.values(voices).forEach(v => v.ch.kill());
  if (mine !== flight) { kill(); return; }
  const hits = [];
  flightKill = () => { kill(); hits.forEach(h => h.kill()); };
  const hit = async id => {
    const part = PARTS.find(p => p.id === id), s = veh[id], buffer = await bufferOf(s.source);
    if (mine !== flight) return;
    const ch = channel(s); hits.push(ch);
    build(ch, part, s, buffer, null, ctx.currentTime + 0.02);
    if (mixState.duck.onHits) duck();
  };
  const move = (id, moving, speed) => {
    const v = voices[id];
    if (moving !== v.on) { v.on = moving; clunk(v.ch, ctx.currentTime + 0.01, v.s.clunk, v.part); }
    v.set(moving ? 1 : 0, 0.85 + 0.3 * clamp(speed));
  };
  let airborne = rows[0][8] === 0, latched = false, i = 0;
  const began = ctx.currentTime;
  await new Promise(done => {
    const tick = () => {
      if (mine !== flight) return done();
      i = Math.min(rows.length - 1, Math.floor((ctx.currentTime - began) * 10));
      const row = rows[i], before = rows[Math.max(0, i - 3)];
      const [t, speed, height, rpm, tilt, thrust, flap, leg, support, wing] = row;
      const rate = n => Math.abs(row[n] - before[n]) / Math.max(0.1, t - before[0]);
      const fan = clamp(rpm / 4500), jet = clamp(thrust / 6000), grounded = support > 0;
      voices.hum.set(0.25);
      voices.fans.set(fan ** 1.7, 0.45 + 0.75 * fan);
      voices.boosters.set(jet ** 0.8, 0.75 + 0.35 * jet);
      voices.wind.set(clamp(speed / 80) ** 1.4, 0.8 + 0.4 * clamp(speed / 90));
      voices.tyres.set(grounded && speed > 0.5 ? clamp(speed / 50) : 0, 0.7 + 0.6 * clamp(speed / 80));
      move('wings', !['stowed', 'locked'].includes(wing), 0.6);
      move('pods', rate(4) > 1.5, rate(4) / 30);
      move('flaps', rate(6) > 1.5, rate(6) / 20);
      move('legs', rate(7) > 0.04, rate(7));
      if (wing !== before[9] && wing === 'locked' && !latched) { latched = true; hit('latch'); }
      if (!grounded) airborne = true;
      else if (airborne) { airborne = false; hit('touchdown'); }
      $('now').textContent = `${label}: ${Math.round(speed * 3.6)} km/h, ${Math.max(0, height).toFixed(0)} m, fans ${rpm} rpm, boosters ${thrust} N, record ${t.toFixed(0)} s`;
      if (i >= rows.length - 1) return done();
      timers.push(setTimeout(tick, 100));
    };
    tick();
  });
  if (mine === flight) { flightKill(); flightKill = null; }
}
async function fly(steps) {
  stopAllVehicle(); stopAllPads();
  const mine = flight;
  audio();
  for (const [key, label] of steps) {
    if (mine !== flight) return;
    $('now').textContent = label + '…';
    await runStep(key, label, mine);
  }
  if (mine === flight) $('now').textContent = 'Finished.';
}
function drawSteps() {
  $('steps').replaceChildren(...PROCEDURES[$('procedure').value].map(([key, label], n) =>
    el('button', { className: 'chip', textContent: `${n + 1}. ${label}`, onclick: () => fly([[key, label]]) })));
}

// ---------- balance by measurement ----------
// Target loudness of each part at full drive, in dB. Engines lead, mechanisms sit under them, the hum is barely there.
const TARGET = { boosters: -13, fans: -15, touchdown: -13, wings: -17, latch: -17, pods: -20, airbrake: -20,
  flaps: -22, legs: -22, wind: -21, tyres: -23, hum: -33 };
// Runs a part through a silent offline context, reporting its loudest 0.4 s. Swaps the shared globals while it schedules.
async function scheduleOffline(part, s, seconds, sampleRate, post) {
  const buffer = await bufferOf(s.source);
  const extra = s.layer && part.kind !== 'hit' ? await bufferOf(layerName(s)) : null;
  const off = new OAC(2, Math.ceil(sampleRate * seconds), sampleRate), real = [ctx, vMaster, vEcho];
  const sink = post ? post(off) : off.destination;
  const m = off.createGain(); m.connect(sink);
  ctx = off; vMaster = m; vEcho = off.createConvolver();   // build() works on the shared context, so point it at the silent one while scheduling
  try { vEcho.buffer = room(off, 1); vEcho.connect(vMaster); build(channel(s), part, s, buffer, extra, 0.05); }
  finally { [ctx, vMaster, vEcho] = real; }
  return off.startRendering();
}
async function loudness(part) {
  const s = { ...veh[part.id], volume: 1, echo: 0 };
  const rendered = await scheduleOffline(part, s, 4, 48000, off => {
    const weigh = off.createBiquadFilter(), lift = off.createBiquadFilter();
    weigh.type = 'highpass'; weigh.frequency.value = 100; lift.type = 'highshelf'; lift.frequency.value = 2000; lift.gain.value = 4;
    weigh.connect(lift).connect(off.destination); return weigh;
  });
  const data = rendered.getChannelData(0), size = 19200;
  let loudest = 0;
  for (let from = 0; from + size <= data.length; from += size / 4) {
    let sum = 0; for (let i = from; i < from + size; i++) sum += data[i] * data[i];
    loudest = Math.max(loudest, Math.sqrt(sum / size));
  }
  return 20 * Math.log10(Math.max(loudest, 1e-5));
}
async function balance() {
  stopAllVehicle(); audio();
  say('Balancing…', 30000);
  for (const part of PARTS) {
    const measured = await loudness(part);
    veh[part.id].volume = Math.round(Math.max(0.05, Math.min(4, 10 ** ((TARGET[part.id] - measured) / 20))) * 20) / 20;
  }
  if (openPart) renderPartBody(openPart);
  persist(); say('Volumes balanced by measurement. Fine-tune by ear.');
}
// A finished sound of one part, as the game would use it: no strip, no master.
async function renderPart(part) {
  const s = veh[part.id], length = part.kind === 'loop' ? 8 : part.kind === 'hit' ? 1.6 : s.length + 1.8;
  const out = await scheduleOffline(part, s, length, 48000);
  return part.kind === 'loop' ? seamless(out, 0.15) : out;
}
function seamless(buf, sec) {   // the last `sec` seconds fade into the first, so the file repeats without a join
  const fade = Math.min(Math.floor(buf.sampleRate * sec), Math.floor(buf.length / 3)), n = buf.length - fade;
  const out = ctx.createBuffer(buf.numberOfChannels, n, buf.sampleRate);
  for (let c = 0; c < buf.numberOfChannels; c++) {
    const from = buf.getChannelData(c), to = out.getChannelData(c);
    to.set(from.subarray(0, n));
    for (let i = 0; i < fade; i++) { const x = i / fade * Math.PI / 2; to[i] = from[i] * Math.sin(x) + from[n + i] * Math.cos(x); }
  }
  return out;
}

// ---------- part cards ----------
const summary = part => { const s = veh[part.id]; return `${part.kind} · ${s.name} · ${s.source ? takeLabel(s.source) : 'stand-in'}`; };
function partCard(part) {
  const button = el('button', { className: 'chip', textContent: 'Play', onclick: () => live.has(part.id) ? stopPart(part.id) : playPart(part) });
  button.setAttribute('aria-pressed', 'false');
  ui[part.id] = { button };
  const head = el('button', { className: 'part-open', id: 'open-' + part.id }, el('b', { textContent: part.name }), el('small', { id: 'sum-' + part.id }));
  head.setAttribute('aria-expanded', 'false');
  head.onclick = () => { openPart = openPart === part.id ? null : part.id; renderParts(); };
  return el('div', { className: 'part', id: 'part-' + part.id }, el('div', { className: 'part-row' }, head, button), el('div', { className: 'part-body', id: 'body-' + part.id, hidden: true }));
}
function renderPartBody(id) {
  const part = PARTS.find(p => p.id === id), s = veh[id], host = $('body-' + id);
  const replay = debounce(() => { if (live.has(id)) playPart(part); }, 250);
  const names = [...takes.keys()].sort();
  const design = el('select', { ariaLabel: part.name + ' design' }, ...DESIGNS.map((d, i) => el('option', { value: i, textContent: d.name })));
  design.value = Math.max(0, DESIGNS.findIndex(d => d.name === s.name));
  const source = el('select', { ariaLabel: part.name + ' take' }, el('option', { value: '', textContent: 'Stand-in (no take)' }),
    ...names.map(n => el('option', { value: n, textContent: takeLabel(n) })));
  source.value = s.source;
  const grid = el('div', { className: 'dials' }), dials = {};
  const keys = part.kind === 'move' ? ['length', 'pitch', 'weight', 'edge', 'clunk', 'echo', 'layer', 'volume'] : ['pitch', 'weight', 'edge', 'clunk', 'echo', 'layer', 'volume'];
  for (const key of keys) {
    const d = dialFor(VD[key], s[key], v => { s[key] = v; persist(); replay(); }, 68);
    dials[key] = d; grid.append(d.root);
  }
  const drawDials = () => { for (const [key, d] of Object.entries(dials)) d.set(s[key]); };
  design.onchange = () => { Object.assign(s, { rough: false }, DESIGNS[design.value]); drawDials(); $('sum-' + id).textContent = summary(part); persist(); playPart(part); };
  source.onchange = () => { s.source = source.value; $('sum-' + id).textContent = summary(part); persist(); replay(); if (!live.has(id)) playPart(part); renderPrompts(); };
  const surprise = el('button', { className: 'btn', textContent: 'Surprise me', onclick: () => {
    const r = (a, b) => Math.round((a + Math.random() * (b - a)) * 20) / 20;
    Object.assign(s, { pitch: r(0.6, 1.6), weight: r(-4, 12), edge: r(-6, 9), clunk: r(0, 1.2), echo: r(0, 0.7), layer: r(0, 1), rough: Math.random() < 0.3 });
    drawDials(); persist(); playPart(part);
  } });
  const bounce = el('button', { className: 'btn go', textContent: 'Bounce WAV', onclick: e => bouncePart(part, e.currentTarget) });
  host.replaceChildren(el('div', { className: 'bar' }, design, source), el('div', { className: 'bar' }, surprise, bounce), grid);
}
function renderParts() {
  if (!$('parts').children.length) return;
  for (const part of PARTS) {
    const open = openPart === part.id, bodyEl = $('body-' + part.id);
    $('sum-' + part.id).textContent = summary(part);
    $('open-' + part.id).setAttribute('aria-expanded', open);
    bodyEl.hidden = !open;
    if (open) renderPartBody(part.id); else bodyEl.replaceChildren();
  }
}
{
  $('parts').replaceChildren(...PARTS.map(partCard));
  $('procedure').append(...Object.keys(PROCEDURES).map(name => el('option', { textContent: name, value: name })));
  $('procedure').onchange = () => { stopAllVehicle(); drawSteps(); };
  $('story').onclick = () => fly(PROCEDURES[$('procedure').value]);
  $('vStop').onclick = () => { stopAllVehicle(); stopAllPads(); $('now').textContent = 'Stopped.'; };
  $('balance').onclick = balance;
  const master = makeDial({ label: 'Vehicle master', min: 0, max: 3, step: 0.1, fine: 0.01, def: 1, value: macro.master, size: 76,
    fmt: v => round(v, 2) + 'x', onInput: v => { vehMaster = macro.master = v; if (vMaster) vMaster.gain.value = v; persist(); } });
  $('vehDials').append(master.root);
  $('cockpit').setAttribute('aria-pressed', prefs.cockpit);
  $('cockpit').onclick = () => { prefs.cockpit = !prefs.cockpit; $('cockpit').setAttribute('aria-pressed', prefs.cockpit); remix(); persist(); };
  loaderBar($('vehLoad'), 'vehNote');
  drawSteps(); renderParts();
  $('copyTuning').onclick = () => copyText(JSON.stringify(plainVeh(), null, 1), $('tuningOut'));
  $('bounceParts').onclick = e => bounceAllParts(e.currentTarget);
}
