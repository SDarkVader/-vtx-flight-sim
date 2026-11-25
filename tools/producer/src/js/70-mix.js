// =====================================================================================
// MIX BENCH: master meters, spectrum, four channel strips, limiter, sends, ducking, project file
// =====================================================================================
const me = {};   // elements the frame loop updates
const COL = {};
const levelPct = db => clamp((db + 60) / 60) * 100;
const lufsText = v => Number.isFinite(v) ? v.toFixed(1) : '−∞';
const TARGETS = [['Console −24', -24], ['Mobile −18', -18], ['Loud mobile −16', -16]];

function readout(id, label) {
  const b = el('b', { textContent: '−∞' });
  me[id] = b;
  return el('div', { className: 'read' }, b, el('small', { textContent: label }));
}
function masterCard() {
  const card = el('div', { className: 'card' }, el('h2', { textContent: 'Master' }));
  card.append(el('div', { className: 'reads' }, readout('mom', 'LUFS momentary'), readout('short', 'LUFS short'), readout('int', 'LUFS integrated'),
    readout('peak', 'Peak dBFS'), readout('tp', 'True peak≈ dBTP'), readout('corr', 'Correlation')));
  const corr = el('div', { className: 'corr', style: 'margin-top:10px' }, el('i', { style: 'left:100%' })); me.corrBar = corr.firstChild;
  const gr = el('div', { className: 'meter gr', style: 'margin-top:10px', title: 'Limiter gain reduction' }, el('div', { className: 'lv' })); me.limGr = gr.firstChild;
  card.append(corr, el('small', { className: 'note', textContent: 'Phase correlation: +1 is mono-safe, below 0 means the sides cancel.' }), gr, el('small', { className: 'note', textContent: 'Limiter gain reduction' }));
  const bar = el('div', { className: 'bar', style: 'margin-top:12px' });
  me.targetChips = TARGETS.map(([label, v]) => {
    const c = el('button', { className: 'chip', textContent: label });
    c.setAttribute('aria-pressed', mixState.target === v);
    c.onclick = () => { mixState.target = v; me.targetChips.forEach((x, i) => x.setAttribute('aria-pressed', TARGETS[i][1] === v)); persist(); };
    return c;
  });
  bar.append(...me.targetChips);
  me.delta = el('p', { className: 'note', textContent: 'Play something to measure it.' });
  const reset = el('button', { className: 'btn', textContent: 'Reset meters', onclick: () => { resetMeters(); paintMaster(); } });
  const stop = el('button', { className: 'btn warn', textContent: 'Stop everything', onclick: panic });
  card.append(bar, me.delta, el('div', { className: 'bar' }, reset, stop),
    el('p', { className: 'note', textContent: 'Loudness is measured in this page from the output, K-weighted and gated as in ITU-R BS.1770. Guidance in Wwise material is about −24 LUFS for console and −18 for mobile, true peak no higher than −1 dBTP. Check a final master in a certified meter.' }));
  return card;
}
function panic() { player.pause(); stopAllVehicle(); stopAllPads(); stopScenes(); say('Everything stopped.'); }
function paintMaster() {
  if (!me.mom) return;
  me.mom.textContent = lufsText(LM.mom); me.short.textContent = lufsText(LM.short); me.int.textContent = lufsText(LM.int);
  me.peak.textContent = lufsText(LM.peakMax); me.tp.textContent = lufsText(LM.tpMax); me.corr.textContent = (LM.corr >= 0 ? '+' : '−') + Math.abs(LM.corr).toFixed(2);
  me.peak.parentNode.classList.toggle('bad', LM.peakMax > -0.1); me.tp.parentNode.classList.toggle('bad', LM.tpMax > -1);
  me.corrBar.style.left = ((clamp(LM.corr, -1, 1) + 1) / 2 * 100) + '%';
  me.limGr.style.clipPath = `inset(0 ${100 - clamp(-LM.gr / 12) * 100}% 0 0)`;
  if (Number.isFinite(LM.int)) {
    const d = LM.int - mixState.target;
    me.delta.textContent = `Integrated is ${d > 0 ? '+' : d < 0 ? '−' : ''}${Math.abs(d).toFixed(1)} LU from the target of ${mixState.target} LUFS. Within 2 LU either side is on target.`;
    me.int.parentNode.classList.toggle('bad', Math.abs(d) > 2);
  }
}

// ---------- spectrum ----------
const spec = { peaks: null };
function specCard() {
  const cv = el('canvas', { className: 'spec', id: 'spec', ariaLabel: 'Spectrum of the master output' });
  return el('div', { className: 'card' }, el('h2', { textContent: 'Spectrum' }), cv, el('p', { className: 'note', textContent: '20 Hz to 20 kHz on the bottom, −90 to 0 dBFS up the side. The line holds the peaks.' }));
}
function drawSpectrum() {
  const cv = $('spec');
  if (!cv || !cv.isConnected || !A?.spec) return;
  const dpr = Math.min(2, window.devicePixelRatio || 1), W = cv.clientWidth, H = 150;
  if (!W) return;
  if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); spec.peaks = new Float32Array(W).fill(-120); }
  if (!COL.cyan) { const cs = getComputedStyle(document.documentElement); for (const k of ['cyan', 'amber', 'line', 'ink-2', 'hot']) COL[k] = cs.getPropertyValue('--' + k).trim(); }
  const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  const sr = ctx.sampleRate, binHz = sr / A.spec.fftSize, data = scratch.spec, nb = data.length, fmin = 20, fmax = Math.min(20000, sr / 2);
  const xOf = f => Math.log(f / fmin) / Math.log(fmax / fmin) * W, yOf = db => H - 14 - clamp((db + 90) / 90) * (H - 22);
  g.font = '10px ui-monospace,Menlo,monospace'; g.fillStyle = COL['ink-2']; g.strokeStyle = COL.line; g.lineWidth = 1;
  for (const f of [50, 100, 200, 500, 1000, 2000, 5000, 10000]) { const x = Math.round(xOf(f)) + 0.5; g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H - 14); g.stroke(); g.fillText(f >= 1000 ? f / 1000 + 'k' : f, x + 2, H - 3); }
  for (const d of [-20, -40, -60]) { const y = Math.round(yOf(d)) + 0.5; g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); g.fillText(d, 2, y - 2); }
  const path = new Path2D(), top = new Path2D(); path.moveTo(0, H - 14);
  for (let x = 0; x < W; x++) {
    const b0 = fmin * Math.pow(fmax / fmin, x / W) / binHz, b1 = fmin * Math.pow(fmax / fmin, (x + 1) / W) / binHz;
    let v;
    if (b1 - b0 < 1) { const bi = (b0 + b1) / 2, i0 = Math.floor(bi), fr = bi - i0; v = data[i0] * (1 - fr) + data[Math.min(nb - 1, i0 + 1)] * fr; }
    else { v = -Infinity; for (let k = Math.floor(b0); k <= Math.min(nb - 1, Math.ceil(b1)); k++) if (data[k] > v) v = data[k]; }
    if (!Number.isFinite(v)) v = -120;
    spec.peaks[x] = Math.max(v, spec.peaks[x] - 0.5);
    path.lineTo(x, yOf(v)); x ? top.lineTo(x, yOf(spec.peaks[x])) : top.moveTo(0, yOf(spec.peaks[x]));
  }
  path.lineTo(W, H - 14); path.closePath();
  const grad = g.createLinearGradient(0, 0, 0, H); grad.addColorStop(0, 'rgba(255,202,114,.85)'); grad.addColorStop(1, 'rgba(140,220,230,.25)');
  g.fillStyle = grad; g.fill(path);
  g.strokeStyle = COL.amber; g.lineWidth = 1; g.stroke(top);
}

// ---------- channel strips ----------
function stripCard(id) {
  const s = mixState.strips[id];
  const mute = el('button', { className: 'ms m', textContent: 'M', ariaLabel: 'Mute ' + STRIP_NAMES[id] }), solo = el('button', { className: 'ms s', textContent: 'S', ariaLabel: 'Solo ' + STRIP_NAMES[id] });
  mute.setAttribute('aria-pressed', s.mute); solo.setAttribute('aria-pressed', s.solo);
  mute.onclick = () => { s.mute = !s.mute; mute.setAttribute('aria-pressed', s.mute); remix(); persist(); };
  solo.onclick = () => {
    s.solo = !s.solo; solo.setAttribute('aria-pressed', s.solo);
    remix(); persist();
  };
  me['ms-' + id] = { mute, solo };
  const fv = el('div', { className: 'fv', textContent: fmtDb(s.fader) });
  const fader = makeFader({ label: STRIP_NAMES[id] + ' level', value: s.fader, onInput: v => { s.fader = v; fv.textContent = fmtDb(v); remix(); persist(); } });
  const lv = el('div', { className: 'lv' }), pk = el('div', { className: 'pk' }), meter = el('div', { className: 'meter', title: 'Level, RMS with peak hold' }, lv, pk);
  const gl = el('div', { className: 'lv' }), gr = el('div', { className: 'meter gr', title: 'Compressor gain reduction' }, gl);
  me['lv-' + id] = { lv, pk, gl };
  const dial = (key, size = 60) => dialFor(SD[key], s[key], v => { s[key] = v; remix(); persist(); }, size).root;
  const detail = el('details', { className: 'strip-detail' }, el('summary', { textContent: 'Tone and dynamics', style: 'min-height:40px;display:flex;align-items:center;color:var(--cyan);cursor:pointer' }));
  let built = false;
  detail.ontoggle = () => {
    if (!detail.open || built) return;
    built = true;
    detail.append(el('div', { className: 'dials', style: 'margin-top:8px' }, ...['trim', 'hp', 'low', 'mid', 'high', 'thr', 'ratio', 'att', 'rel', 'makeup'].map(k => dial(k, 64))),
      el('p', { className: 'note', textContent: 'The compressor is off until the ratio is above 1:1. Its automatic makeup gain is cancelled, so Makeup is yours alone.' }));
  };
  return el('div', { className: 'card strip' },
    el('div', { className: 'head' }, el('b', { textContent: STRIP_NAMES[id] }), mute, solo),
    el('div', { className: 'fadrow' }, fader.root, fv), meter, gr,
    el('div', { className: 'dials row3' }, dial('pan'), dial('sa'), dial('sb')), detail);
}
function paintStrips() {
  for (const id of STRIP_IDS) {
    const m = LM.strips[id], e = me['lv-' + id];
    if (!e) continue;
    e.lv.style.clipPath = `inset(0 ${100 - levelPct(m.rms)}% 0 0)`;
    e.pk.style.left = `calc(${levelPct(m.hold)}% - 2px)`;
    e.gl.style.clipPath = `inset(0 ${100 - clamp(-m.gr / 20) * 100}% 0 0)`;
  }
}

// ---------- master out, sends, ducking, project ----------
function outCard() {
  const m = mixState.master, card = el('div', { className: 'card' }, el('h2', { textContent: 'Master out' }));
  const lim = el('button', { className: 'chip', textContent: 'Limiter' }); lim.setAttribute('aria-pressed', m.limiter);
  lim.onclick = () => { m.limiter = !m.limiter; lim.setAttribute('aria-pressed', m.limiter); remix(); persist(); };
  card.append(el('div', { className: 'dials row3' },
    dialFor(MD.trim, m.trim, v => { m.trim = v; remix(); persist(); }, 76).root,
    dialFor(MD.ceil, m.ceil, v => { m.ceil = v; remix(); persist(); }, 76).root, el('div', { style: 'display:grid;justify-items:center;align-content:center' }, lim)),
    el('p', { className: 'note', textContent: 'The limiter holds peaks at the ceiling, with a hard stop at full scale behind it. Master trim pushes into it. A ceiling of −2 dB leaves room for true peaks.' }));
  return card;
}
function sendsCard() {
  const x = mixState.sends, d = el('details', { className: 'card' }, el('summary', { textContent: 'Sends' }));
  d.append(el('div', { className: 'dials' }, ...['room', 'vret', 'time', 'fb', 'eret'].map(k => dialFor(XD[k], x[k], v => { x[k] = v; remix(); persist(); }, 68).root)),
    el('p', { className: 'note', textContent: 'Space is a room all strips can feed with their Space dial. Echo is a darkening repeat with the Echo dial. Both come back into the master.' }));
  return d;
}
function duckCard() {
  const dk = mixState.duck, d = el('details', { className: 'card' }, el('summary', { textContent: 'Ducking' }));
  const chips = el('div', { className: 'bar', style: 'margin-top:12px' });
  for (const id of STRIP_IDS) {
    const c = el('button', { className: 'chip', textContent: STRIP_NAMES[id] }); c.setAttribute('aria-pressed', dk[id]);
    c.onclick = () => { dk[id] = !dk[id]; c.setAttribute('aria-pressed', dk[id]); persist(); };
    chips.append(c);
  }
  const hits = el('button', { className: 'chip', textContent: 'On vehicle hits' }); hits.setAttribute('aria-pressed', dk.onHits);
  hits.onclick = () => { dk.onHits = !dk.onHits; hits.setAttribute('aria-pressed', dk.onHits); persist(); };
  d.append(el('div', { className: 'dials' }, ...['amount', 'attack', 'hold', 'release'].map(k => dialFor(DD[k], dk[k], v => { dk[k] = v; persist(); }, 68).root)),
    el('p', { className: 'note', textContent: 'Dips the chosen strips when a Latch or Touchdown hit fires, and when a take marked Duck on play starts.' }), chips,
    el('div', { className: 'bar', style: 'margin-top:8px' }, hits, el('button', { className: 'btn', textContent: 'Test duck', onclick: () => { audio(); duck(); } })));
  return d;
}
function projectCard() {
  const d = el('details', { className: 'card' }, el('summary', { textContent: 'Project' }));
  const out = el('textarea', { id: 'projectOut', readonly: true, hidden: true, ariaLabel: 'Project JSON', style: 'margin-top:8px' });
  const paste = el('textarea', { id: 'projectIn', placeholder: 'Paste a project here, then tap Apply', ariaLabel: 'Project to apply', style: 'margin-top:8px' });
  const reset = el('button', { className: 'btn warn', textContent: 'Reset studio' });
  reset.onclick = () => {
    if (reset.dataset.sure !== '1') { reset.dataset.sure = '1'; reset.textContent = 'Tap again: this clears every setting'; setTimeout(() => { reset.dataset.sure = ''; reset.textContent = 'Reset studio'; }, 4000); return; }
    resetStudio();
  };
  const b16 = el('button', { className: 'chip', textContent: 'Bounce as 16-bit' }); b16.setAttribute('aria-pressed', prefs.bits16);
  b16.onclick = () => { prefs.bits16 = !prefs.bits16; b16.setAttribute('aria-pressed', prefs.bits16); persist(); };
  d.append(el('p', { className: 'note', style: 'margin:0 0 10px', textContent: 'The project holds every dial, fader, edit, scene, prompt and tuning. It does not hold your audio files.' }),
    el('div', { className: 'bar' }, el('button', { className: 'btn go', textContent: 'Copy project', onclick: () => copyText(projectJson(), out) }),
      el('button', { className: 'btn', textContent: 'Save project file', onclick: e => saveProject(e.currentTarget) })),
    el('div', { className: 'bar', style: 'margin-top:8px' }, b16, el('small', { textContent: 'Bounces are 24-bit unless this is on, then dithered 16-bit.' })),
    out, paste, el('div', { className: 'bar', style: 'margin-top:8px' }, el('button', { className: 'btn go', textContent: 'Apply pasted project', onclick: () => applyProject(paste.value) }), reset),
    el('p', { className: 'note', id: 'projectNote' }));
  return d;
}
function buildMix() {
  $('mixWrap').replaceChildren(masterCard(), specCard(), ...STRIP_IDS.map(stripCard), outCard(), sendsCard(), duckCard(), projectCard());
}

// ---------- the frame loop: header spectrum, meters, loudness ----------
let frameOn = false, activeTab = 'mix';
const meterCv = $('meter'), mc = meterCv.getContext('2d');
function drawHeader() {
  const W = meterCv.width, H = meterCv.height, N = 14, bw = W / N, sr = ctx.sampleRate, binHz = sr / A.spec.fftSize;
  mc.clearRect(0, 0, W, H);
  for (let i = 0; i < N; i++) {
    const a = Math.max(1, Math.round(40 * Math.pow(400, i / N) / binHz)), b = Math.max(a + 1, Math.round(40 * Math.pow(400, (i + 1) / N) / binHz));
    let m = -Infinity; for (let k = a; k < b && k < scratch.spec.length; k++) if (scratch.spec[k] > m) m = scratch.spec[k];
    const h = Math.max(2, clamp((m + 90) / 80) * (H - 4));
    mc.fillStyle = m > -6 ? '#ff6b5e' : '#ffca72';
    mc.fillRect(i * bw + 3, H - 2 - h, bw - 6, h);
  }
}
function startFrame() { if (!frameOn) { frameOn = true; requestAnimationFrame(frame); } }
function frame() {
  requestAnimationFrame(frame);
  if (!A || document.hidden) return;
  if (!readMeters()) return;
  A.spec.getFloatFrequencyData(scratch.spec);
  drawHeader();
  $('clipLed').classList.toggle('on', performance.now() < LM.clipUntil);
  if (activeTab === 'mix') { paintMaster(); paintStrips(); drawSpectrum(); }
  else if (activeTab === 'takes' && editor.name && pads.has(editor.name)) drawWave();
}
buildMix();
