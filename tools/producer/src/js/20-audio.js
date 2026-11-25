// =====================================================================================
// AUDIO ENGINE: channel strips (four fixed ones, then one per track), sends and a master suite.
// Built on the first tap, as phone browsers require.
// =====================================================================================
const STRIP_IDS = ['music', 'veh', 'sfx', 'amb'];   // tracks add their own after these
const FIXED_STRIPS = 4;
const STRIP_NAMES = { music: 'Music', veh: 'Vehicle', sfx: 'SFX and takes', amb: 'Ambience' };
const RATIOS = [1, 1.5, 2, 3, 4, 6, 8, 12, 20];
const ATTACKS = [1, 3, 10, 30, 100], RELEASES = [50, 100, 200, 400, 800];
const GATT = [10, 30, 50, 100], GREL = [100, 200, 400, 800], GRATIOS = [1, 1.5, 2, 3, 4];
const HP_LIST = [10, 20, 30, 40, 60, 80, 120, 200];
const TIMES = [60, 90, 120, 160, 200, 250, 300, 375, 450, 500, 600, 750, 900, 1000];
const ROOMS = [[0.5, 9], [1.0, 6], [2.2, 3.2], [4.0, 1.9]];
const ROOM_NAMES = ['Booth', 'Room', 'Hall', 'Cathedral'];
const panText = v => v === 0 ? 'Centre' : (v < 0 ? 'L ' : 'R ') + Math.round(Math.abs(v) * 100);
const stripDefaults = () => ({ fader: 0, pan: 0, mute: false, solo: false, trim: 0, hp: 0, low: 0, mid: 0, high: 0,
  thr: 0, ratio: 0, att: 2, rel: 2, makeup: 0, sa: 0, sb: 0 });
const masterDefaults = () => ({ trim: 0, ceil: -2, limiter: true, eqL: 0, eqLM: 0, eqHM: 0, eqH: 0, gthr: 0, gratio: 0, gatt: 1, grel: 1, gmk: 0, width: 1 });
const mixState = {
  strips: Object.fromEntries(STRIP_IDS.map(id => [id, stripDefaults()])),
  master: masterDefaults(),
  sends: { room: 2, vret: 0.5, time: 5, fb: 0.35, eret: 0.5 },
  duck: { amount: -6, attack: 30, hold: 500, release: 800, music: true, veh: false, sfx: false, amb: true, onHits: true },
  target: -18,
};
merge(mixState, saved.mix);

// Dial definitions, shared by the strips, master suite, sends and ducking
const SD = {
  trim: { label: 'Trim', min: -24, max: 24, step: 1, fine: 0.1, fmt: fmtDb, def: 0 },
  hp: { label: 'Low cut', list: HP_LIST, text: ['Off', '20 Hz', '30 Hz', '40 Hz', '60 Hz', '80 Hz', '120 Hz', '200 Hz'], def: 0 },
  low: { label: 'Low', min: -12, max: 12, step: 1, fine: 0.1, fmt: fmtDb, def: 0 },
  mid: { label: 'Mid', min: -12, max: 12, step: 1, fine: 0.1, fmt: fmtDb, def: 0 },
  high: { label: 'High', min: -12, max: 12, step: 1, fine: 0.1, fmt: fmtDb, def: 0 },
  thr: { label: 'Threshold', min: -40, max: 0, step: 1, fine: 0.25, fmt: v => v === 0 ? 'Off' : v + ' dB', def: 0 },
  ratio: { label: 'Ratio', list: RATIOS, text: RATIOS.map(r => r + ':1'), def: 0 },
  att: { label: 'Attack', list: ATTACKS, text: ATTACKS.map(x => x + ' ms'), def: 2 },
  rel: { label: 'Release', list: RELEASES, text: RELEASES.map(x => x + ' ms'), def: 2 },
  makeup: { label: 'Makeup', min: 0, max: 18, step: 0.5, fine: 0.1, fmt: v => '+' + v.toFixed(1) + ' dB', def: 0 },
  sa: { label: 'Space', min: 0, max: 1, step: 0.05, fine: 0.01, fmt: pct, def: 0 },
  sb: { label: 'Echo', min: 0, max: 1, step: 0.05, fine: 0.01, fmt: pct, def: 0 },
  pan: { label: 'Pan', min: -1, max: 1, step: 0.1, fine: 0.02, fmt: panText, def: 0 },
};
const MD = {
  trim: { label: 'Master trim', min: -12, max: 12, step: 0.5, fine: 0.1, fmt: fmtDb, def: 0 },
  ceil: { label: 'Ceiling', min: -12, max: 0, step: 0.5, fine: 0.1, fmt: fmtDb, def: -2 },
  eqL: { label: 'Low 100 Hz', min: -12, max: 12, step: 0.5, fine: 0.1, fmt: fmtDb, def: 0 },
  eqLM: { label: 'Low-mid 400', min: -12, max: 12, step: 0.5, fine: 0.1, fmt: fmtDb, def: 0 },
  eqHM: { label: 'High-mid 2.5k', min: -12, max: 12, step: 0.5, fine: 0.1, fmt: fmtDb, def: 0 },
  eqH: { label: 'High 9k', min: -12, max: 12, step: 0.5, fine: 0.1, fmt: fmtDb, def: 0 },
  gthr: { label: 'Glue threshold', min: -30, max: 0, step: 1, fine: 0.25, fmt: v => v === 0 ? 'Off' : v + ' dB', def: 0 },
  gratio: { label: 'Glue ratio', list: GRATIOS, text: GRATIOS.map(r => r + ':1'), def: 0 },
  gatt: { label: 'Glue attack', list: GATT, text: GATT.map(x => x + ' ms'), def: 1 },
  grel: { label: 'Glue release', list: GREL, text: GREL.map(x => x + ' ms'), def: 1 },
  gmk: { label: 'Glue makeup', min: 0, max: 12, step: 0.5, fine: 0.1, fmt: v => '+' + v.toFixed(1) + ' dB', def: 0 },
  width: { label: 'Width', min: 0, max: 2, step: 0.1, fine: 0.02, center: 1, fmt: v => v === 0 ? 'Mono' : v === 1 ? 'Normal' : round(v, 2) + 'x', def: 1 },
};
const XD = {
  room: { label: 'Room', list: [0, 1, 2, 3], text: ROOM_NAMES, def: 2 },
  vret: { label: 'Space return', min: 0, max: 1, step: 0.05, fine: 0.01, fmt: pct, def: 0.5 },
  time: { label: 'Echo time', list: TIMES, text: TIMES.map(t => t < 1000 ? t + ' ms' : '1 s'), def: 5 },
  fb: { label: 'Repeats', min: 0, max: 0.85, step: 0.05, fine: 0.01, fmt: pct, def: 0.35 },
  eret: { label: 'Echo return', min: 0, max: 1, step: 0.05, fine: 0.01, fmt: pct, def: 0.5 },
};
const DD = {
  amount: { label: 'Duck by', min: -18, max: 0, step: 1, fine: 0.25, fmt: v => v === 0 ? 'Off' : fmtDb(v), def: -6 },
  attack: { label: 'Attack', min: 5, max: 200, step: 5, fine: 1, fmt: v => v + ' ms', def: 30 },
  hold: { label: 'Hold', min: 0, max: 2000, step: 50, fine: 10, fmt: v => v + ' ms', def: 500 },
  release: { label: 'Release', min: 50, max: 3000, step: 50, fine: 10, fmt: v => v + ' ms', def: 800 },
};

let ctx = null, A = null, noise = null, vMaster = null, vEcho = null, padBus = null, ambBus = null;

function makeNoise(c) {
  const buf = c.createBuffer(1, c.sampleRate * 3, c.sampleRate), n = buf.getChannelData(0);
  for (let i = 0, slow = 0; i < n.length; i++) { const w = Math.random() * 2 - 1; slow = 0.97 * slow + 0.03 * w; n[i] = 0.5 * w + 2 * slow; }
  return buf;
}
function room(c, i) {
  const [sec, decay] = ROOMS[i], n = Math.floor(c.sampleRate * sec), ir = c.createBuffer(2, n, c.sampleRate);
  for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch); for (let k = 0; k < n; k++) d[k] = (Math.random() * 2 - 1) * Math.exp(-decay * k / c.sampleRate) * 0.25; }
  return ir;
}
// ITU-R BS.1770 K-weighting as two biquads: a high shelf and a 38 Hz high-pass, for any sample rate.
function kCoefs(fs) {
  const G = 3.999843853973347, Q = 0.7071752369554196, fc = 1681.974450955533;
  const K = Math.tan(Math.PI * fc / fs), Vh = 10 ** (G / 20), Vb = Vh ** 0.4996667741545416, a0 = 1 + K / Q + K * K;
  const pre = { b: [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0], a: [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0] };
  const Q2 = 0.5003270373238773, fc2 = 38.13547087602444, K2 = Math.tan(Math.PI * fc2 / fs), a02 = 1 + K2 / Q2 + K2 * K2;
  const rlb = { b: [1, -2, 1], a: [1, 2 * (K2 * K2 - 1) / a02, (1 - K2 / Q2 + K2 * K2) / a02] };
  return [pre, rlb];
}
// The browser's compressor adds an automatic makeup gain of -0.6 x threshold x (1 - 1/ratio) dB. This cancels it.
const compCancelDb = (thr, ratio) => 0.6 * thr * (1 - 1 / ratio);

// Constant-power pan for a stereo or mono signal: centre is unity, a hard side is +3 dB, and the opposite side is silent.
// (The browser's own stereo panner lifts a centred source by 6 dB as it moves to a side, so it is not used.)
function makePanner(c) {
  const input = c.createGain(); input.channelCount = 2; input.channelCountMode = 'explicit'; input.channelInterpretation = 'speakers';
  const sp = c.createChannelSplitter(2), mg = c.createChannelMerger(2), gl = c.createGain(), gr = c.createGain();
  input.connect(sp); sp.connect(gl, 0); sp.connect(gr, 1); gl.connect(mg, 0, 0); gr.connect(mg, 0, 1);
  const set = (pan, t = null, k = 0.02) => {
    const th = (clamp(pan, -1, 1) + 1) * Math.PI / 4, l = Math.SQRT2 * Math.cos(th), r = Math.SQRT2 * Math.sin(th);
    if (t === null) { gl.gain.value = l; gr.gain.value = r; } else { gl.gain.setTargetAtTime(l, t, k); gr.gain.setTargetAtTime(r, t, k); }
  };
  set(0);
  return { input, output: mg, set };
}
// Stereo width as a mid/side matrix: 0 is mono, 1 leaves the signal alone, 2 doubles the sides.
function makeWidth(c) {
  const input = c.createGain(); input.channelCount = 2; input.channelCountMode = 'explicit'; input.channelInterpretation = 'speakers';
  const sp = c.createChannelSplitter(2), mg = c.createChannelMerger(2), ll = c.createGain(), lr = c.createGain(), rl = c.createGain(), rr = c.createGain();
  input.connect(sp); sp.connect(ll, 0); sp.connect(rl, 0); sp.connect(lr, 1); sp.connect(rr, 1);
  ll.connect(mg, 0, 0); lr.connect(mg, 0, 0); rl.connect(mg, 0, 1); rr.connect(mg, 0, 1);
  const set = (w, t = null) => {
    const a = (1 + w) / 2, b = (1 - w) / 2;
    for (const [n, v] of [[ll, a], [rr, a], [lr, b], [rl, b]]) t === null ? (n.gain.value = v) : n.gain.setTargetAtTime(v, t, 0.03);
  };
  set(1);
  return { input, output: mg, set };
}

// Builds the whole desk in context c: live (meters on) or offline (for bouncing). opts.noClip leaves out the last-resort hard stop.
function buildMixer(c, live, opts = {}) {
  const g = (v = 1) => { const n = c.createGain(); n.gain.value = v; return n; };
  const bq = (type, f, q = 0.7) => { const b = c.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; return b; };
  const M = { c, live, strips: {}, roomIdx: -1 };
  M.sum = g(); M.sum.channelCount = 2; M.sum.channelCountMode = 'explicit';
  M.trim = g();
  M.eqL = bq('lowshelf', 100); M.eqLM = bq('peaking', 400, 0.8); M.eqHM = bq('peaking', 2500, 0.8); M.eqH = bq('highshelf', 9000);
  M.glue = c.createDynamicsCompressor(); M.glue.knee.value = 0; M.glueMk = g();
  M.wid = makeWidth(c);
  M.limit = c.createDynamicsCompressor(); M.limit.knee.value = 0; M.limit.attack.value = 0.001; M.limit.release.value = 0.12;
  M.post = g();
  M.clip = c.createWaveShaper(); M.clip.curve = new Float32Array([-1, 1]);   // hard stop at full scale, a last resort
  M.sum.connect(M.trim); M.trim.connect(M.eqL); M.eqL.connect(M.eqLM); M.eqLM.connect(M.eqHM); M.eqHM.connect(M.eqH); M.eqH.connect(M.glue);
  M.glue.connect(M.glueMk); M.glueMk.connect(M.wid.input); M.wid.output.connect(M.limit); M.limit.connect(M.post);
  if (opts.noClip) M.post.connect(c.destination); else { M.post.connect(M.clip); M.clip.connect(c.destination); }
  // sends: a room and an echo, shared by every strip
  M.verb = { in: g(), conv: c.createConvolver(), ret: g(0.5) };
  M.verb.in.connect(M.verb.conv); M.verb.conv.connect(M.verb.ret); M.verb.ret.connect(M.sum);
  M.echo = { in: g(), delay: c.createDelay(1.5), fb: g(0.35), damp: bq('lowpass', 4200), ret: g(0.5) };
  M.echo.in.connect(M.echo.delay); M.echo.delay.connect(M.echo.damp); M.echo.damp.connect(M.echo.fb); M.echo.fb.connect(M.echo.delay);
  M.echo.damp.connect(M.echo.ret); M.echo.ret.connect(M.sum);
  M.addStrip = id => {
    const n = M.strips[id] = {};
    n.in = g(); n.cock = bq('lowpass', 20000); n.hp = bq('highpass', 10);
    n.low = bq('lowshelf', 120); n.mid = bq('peaking', 1000, 1); n.high = bq('highshelf', 6000);
    n.comp = c.createDynamicsCompressor(); n.comp.knee.value = 0; n.makeup = g(); n.duck = g(); n.fader = g();
    n.pan = makePanner(c);
    n.sa = g(0); n.sb = g(0);
    n.in.connect(n.cock); n.cock.connect(n.hp); n.hp.connect(n.low); n.low.connect(n.mid); n.mid.connect(n.high); n.high.connect(n.comp);
    n.comp.connect(n.makeup); n.makeup.connect(n.duck); n.duck.connect(n.fader); n.fader.connect(n.pan.input); n.pan.output.connect(M.sum);
    n.pan.output.connect(n.sa); n.sa.connect(M.verb.in); n.pan.output.connect(n.sb); n.sb.connect(M.echo.in);
    if (live) { n.an = c.createAnalyser(); n.an.fftSize = 1024; n.pan.output.connect(n.an); }
    return n;
  };
  M.removeStrip = id => {
    const n = M.strips[id];
    if (!n) return;
    try { n.in.disconnect(); n.pan.output.disconnect(); if (n.an) n.an.disconnect(); } catch {}
    delete M.strips[id];
  };
  for (const id of STRIP_IDS) M.addStrip(id);
  if (live) {   // metering taps, after the limiter
    M.spec = c.createAnalyser(); M.spec.fftSize = 4096; M.spec.smoothingTimeConstant = 0.6; M.clip.connect(M.spec);
    M.sp = c.createChannelSplitter(2); M.clip.connect(M.sp);
    M.pL = c.createAnalyser(); M.pR = c.createAnalyser(); M.pL.fftSize = M.pR.fftSize = 2048;
    M.sp.connect(M.pL, 0); M.sp.connect(M.pR, 1);
    try {
      const [pre, rlb] = kCoefs(c.sampleRate);
      M.k1 = c.createIIRFilter(pre.b, pre.a); M.k2 = c.createIIRFilter(rlb.b, rlb.a);
      M.clip.connect(M.k1); M.k1.connect(M.k2);
      M.ks = c.createChannelSplitter(2); M.k2.connect(M.ks);
      M.kL = c.createAnalyser(); M.kR = c.createAnalyser(); M.kL.fftSize = M.kR.fftSize = 2048;
      M.ks.connect(M.kL, 0); M.ks.connect(M.kR, 1);
    } catch { M.kL = M.kR = null; }
  }
  return M;
}
// mode: false = as heard, true = every strip audible (a print of one source), or a list of strip ids whose mute and solo count.
// bypassMaster: leave the master suite and limiter out (stems).
function applyMixer(M, immediate = false, mode = false, bypassMaster = false) {
  const c = M.c, t = c.currentTime, smooth = M.live && !immediate;
  const set = (p, v, k = 0.02) => smooth ? p.setTargetAtTime(v, t, k) : (p.value = v);
  const scope = Array.isArray(mode) ? mode : null;
  const anySolo = mode !== true && (scope || STRIP_IDS).some(id => mixState.strips[id]?.solo);
  for (const id of STRIP_IDS) {
    const s = mixState.strips[id];
    if (!s) continue;
    const n = M.strips[id] || M.addStrip(id);
    set(n.in.gain, dbToLin(s.trim));
    set(n.hp.frequency, HP_LIST[s.hp]);
    set(n.low.gain, s.low); set(n.mid.gain, s.mid); set(n.high.gain, s.high);
    const r = RATIOS[s.ratio], thr = r === 1 ? 0 : s.thr;
    n.comp.threshold.value = thr; n.comp.ratio.value = r;
    n.comp.attack.value = ATTACKS[s.att] / 1000; n.comp.release.value = RELEASES[s.rel] / 1000;
    set(n.makeup.gain, dbToLin(s.makeup + compCancelDb(thr, r)));
    const inScope = !scope || scope.includes(id);
    const audible = mode === true || !inScope || (!s.mute && (!anySolo || s.solo));
    set(n.fader.gain, audible ? dbToLin(s.fader) : 0, 0.015);
    n.pan.set(s.pan, smooth ? t : null);
    set(n.sa.gain, s.sa); set(n.sb.gain, s.sb);
    if (id === 'veh' || id === 'sfx' || id === 'amb') set(n.cock.frequency, prefs.cockpit ? 1400 : 20000);
  }
  const m = bypassMaster ? { ...masterDefaults(), limiter: false } : mixState.master;
  const thr = m.limiter ? m.ceil : 0, ratio = m.limiter ? 20 : 1;
  set(M.trim.gain, dbToLin(m.trim));
  set(M.eqL.gain, m.eqL); set(M.eqLM.gain, m.eqLM); set(M.eqHM.gain, m.eqHM); set(M.eqH.gain, m.eqH);
  const gr = GRATIOS[m.gratio], gthr = gr === 1 ? 0 : m.gthr;
  M.glue.threshold.value = gthr; M.glue.ratio.value = gr; M.glue.attack.value = GATT[m.gatt] / 1000; M.glue.release.value = GREL[m.grel] / 1000;
  set(M.glueMk.gain, dbToLin(m.gmk + compCancelDb(gthr, gr)));
  M.wid.set(m.width, smooth ? t : null);
  M.limit.threshold.value = thr; M.limit.ratio.value = ratio;
  set(M.post.gain, dbToLin(compCancelDb(thr, ratio)));
  const x = mixState.sends;
  if (M.roomIdx !== x.room) { M.verb.conv.buffer = room(c, x.room); M.roomIdx = x.room; }
  set(M.verb.ret.gain, x.vret);
  set(M.echo.delay.delayTime, TIMES[x.time] / 1000, 0.08);
  set(M.echo.fb.gain, x.fb); set(M.echo.ret.gain, x.eret);
}
const remix = () => { if (A) applyMixer(A); };
function ensureLiveStrip(id) { if (A && !A.strips[id]) { A.addStrip(id); applyMixer(A, true); } }

// Ducking: a short dip on chosen strips whenever a hit or marked take fires.
function duck() {
  const d = mixState.duck;
  if (!ctx || !A || d.amount >= 0) return;
  const t = ctx.currentTime, lin = dbToLin(d.amount);
  for (const id of STRIP_IDS) {
    if (!d[id] || !A.strips[id]) continue;
    const p = A.strips[id].duck.gain;
    if (p.cancelAndHoldAtTime) p.cancelAndHoldAtTime(t); else p.cancelScheduledValues(t);
    p.setTargetAtTime(lin, t, d.attack / 3000 + 0.001);
    p.setTargetAtTime(1, t + (d.attack + d.hold) / 1000, d.release / 3000);
  }
}

function audio() {
  if (!ctx) {
    try { ctx = new AC({ latencyHint: 'interactive' }); } catch { ctx = new AC(); }
    try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch {}
    noise = makeNoise(ctx);
    A = buildMixer(ctx, true);
    applyMixer(A, true);
    // sources outside the music chain meet their strips here
    vMaster = ctx.createGain(); vMaster.gain.value = vehMaster; vMaster.connect(A.strips.veh.in);
    vEcho = ctx.createConvolver(); vEcho.buffer = room(ctx, 1); vEcho.connect(vMaster);
    padBus = ctx.createGain(); padBus.connect(A.strips.sfx.in);
    ambBus = ctx.createGain(); ambBus.connect(A.strips.amb.in);
    buildRadio();
    for (const id of Object.keys(P)) applyParam(id);
    ctx.onstatechange = () => { if (ctx.state !== 'running' && (!player.paused || (typeof eng !== 'undefined' && eng.playing))) say('Tap Play to wake the audio.'); };
    startFrame();
  }
  if (ctx.state !== 'running') Promise.resolve(ctx.resume()).catch(() => {});
  return ctx;
}
