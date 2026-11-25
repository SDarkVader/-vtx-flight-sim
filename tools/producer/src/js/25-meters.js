// =====================================================================================
// METERS: loudness (K-weighted, gated), peaks, correlation, strip levels. Read from analysers once per frame.
// These are measured inside this page from the live output. Treat them as a very good guide, and check a final
// master in a certified meter before it ships.
// =====================================================================================
const ABS_GATE = 10 ** ((-70 + 0.691) / 10);
const lufs = ms => ms > 0 ? -0.691 + 10 * Math.log10(ms) : -Infinity;
const LM = {};
function resetMeters() {
  Object.assign(LM, { frames: [], blocks: [], windows: [], curIdx: -1, curSum: 0, curN: 0, mom: -Infinity, short: -Infinity, int: -Infinity,
    intAt: 0, peak: -Infinity, peakHold: -Infinity, peakMax: -Infinity, tp: -Infinity, tpMax: -Infinity, corr: 1, lastT: -1, clipUntil: 0,
    gr: 0, strips: {} });
}
resetMeters();
const scratch = { a: new Float32Array(2048), b: new Float32Array(2048), s: new Float32Array(1024), spec: new Float32Array(2048) };
const toDb = x => x > 1e-9 ? 20 * Math.log10(x) : -Infinity;

// Largest value between samples, found by 4x Catmull-Rom interpolation: a close estimate of the true peak.
function truePeak(d) {
  let m = 0;
  for (let i = 0; i < d.length; i++) { const v = Math.abs(d[i]); if (v > m) m = v; }
  for (let i = 1; i < d.length - 2; i++) {
    const p0 = d[i - 1], p1 = d[i], p2 = d[i + 1], p3 = d[i + 2];
    for (const t of [0.25, 0.5, 0.75]) {
      const v = Math.abs(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t));
      if (v > m) m = v;
    }
  }
  return m;
}
function integrated() {
  const W = LM.windows;
  if (!W.length) return -Infinity;
  let sum = 0; for (const w of W) sum += w;
  const gate = 10 ** ((lufs(sum / W.length) - 10 + 0.691) / 10);
  let s2 = 0, n2 = 0; for (const w of W) if (w > gate) { s2 += w; n2++; }
  return n2 ? lufs(s2 / n2) : -Infinity;
}
// Called every animation frame. Returns false when nothing could be read (audio not running).
function readMeters() {
  if (!A || !A.live || ctx.state !== 'running') return false;
  const t = ctx.currentTime;
  if (t === LM.lastT) return false;
  const dt = LM.lastT < 0 ? 0 : t - LM.lastT; LM.lastT = t;
  // loudness: energy of the K-weighted signal, both channels
  if (A.kL) {
    A.kL.getFloatTimeDomainData(scratch.a); A.kR.getFloatTimeDomainData(scratch.b);
    let s = 0; for (let i = 0; i < 2048; i++) s += scratch.a[i] * scratch.a[i] + scratch.b[i] * scratch.b[i];
    const ms = s / 2048;
    LM.frames.push({ t, ms });
    while (LM.frames.length && LM.frames[0].t < t - 3.05) LM.frames.shift();
    const mean = span => { let a = 0, n = 0; for (const f of LM.frames) if (f.t > t - span) { a += f.ms; n++; } return n ? a / n : 0; };
    LM.mom = lufs(mean(0.4)); LM.short = lufs(mean(3));
    const idx = Math.floor(t * 10);
    if (idx !== LM.curIdx) {
      if (LM.curN > 0) {
        LM.blocks.push(LM.curSum / LM.curN); if (LM.blocks.length > 8) LM.blocks.shift();
        if (LM.blocks.length >= 4) {
          const b = LM.blocks, w = (b[b.length - 1] + b[b.length - 2] + b[b.length - 3] + b[b.length - 4]) / 4;
          if (w > ABS_GATE) LM.windows.push(w);
        }
      }
      LM.curIdx = idx; LM.curSum = 0; LM.curN = 0;
    }
    LM.curSum += ms; LM.curN++;
    if (t - LM.intAt > 0.5) { LM.int = integrated(); LM.intAt = t; }
  }
  // peaks and stereo correlation
  A.pL.getFloatTimeDomainData(scratch.a); A.pR.getFloatTimeDomainData(scratch.b);
  let pl = 0, pr = 0, ll = 0, rr = 0, lr = 0;
  for (let i = 0; i < 2048; i++) {
    const l = scratch.a[i], r = scratch.b[i];
    if (Math.abs(l) > pl) pl = Math.abs(l); if (Math.abs(r) > pr) pr = Math.abs(r);
    ll += l * l; rr += r * r; lr += l * r;
  }
  const pk = Math.max(pl, pr);
  LM.peak = toDb(pk);
  LM.peakHold = Math.max(LM.peak, LM.peakHold - 12 * dt);
  LM.peakMax = Math.max(LM.peakMax, LM.peak);
  if (pk > 0.002) LM.tp = toDb(Math.max(truePeak(scratch.a), truePeak(scratch.b))); else LM.tp = -Infinity;
  LM.tpMax = Math.max(LM.tpMax, LM.tp);
  if (pk >= 0.999) LM.clipUntil = performance.now() + 1500;
  if (ll > 1e-8 && rr > 1e-8) LM.corr = LM.corr * 0.85 + 0.15 * (lr / Math.sqrt(ll * rr));
  LM.gr = A.limit.reduction;
  // each strip: RMS and peak with a slow fall and a hold
  for (const id of STRIP_IDS) {
    const n = A.strips[id];
    if (!n?.an) continue;
    const m = LM.strips[id] ||= { rms: -Infinity, peak: -Infinity, hold: -Infinity, holdT: 0, gr: 0 };
    n.an.getFloatTimeDomainData(scratch.s);
    let sq = 0, p = 0; for (let i = 0; i < 1024; i++) { const v = scratch.s[i]; sq += v * v; if (Math.abs(v) > p) p = Math.abs(v); }
    const rms = toDb(Math.sqrt(sq / 1024)), peak = toDb(p);
    m.rms = Math.max(rms, m.rms - 24 * dt); m.peak = Math.max(peak, m.peak - 30 * dt);
    if (peak >= m.hold || t - m.holdT > 1.2) { m.hold = peak; m.holdT = t; } else m.hold -= 14 * dt;
    m.gr = n.comp.reduction;
  }
  return true;
}
