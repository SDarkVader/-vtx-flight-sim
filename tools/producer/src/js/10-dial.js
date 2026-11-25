// =====================================================================================
// DIALS: rotating discs with click-stop increments, and faders with a dB taper
// =====================================================================================
function haptic(ms = 5) { if (prefs.haptics) { try { navigator.vibrate?.(ms); } catch {} } }
function clickSound() {
  if (!prefs.clicks || !ctx || !A) return;
  const t = ctx.currentTime, o = ctx.createOscillator(), g = ctx.createGain();
  o.frequency.value = 1900; g.gain.setValueAtTime(0.05, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.012);
  o.connect(g).connect(A.sum); o.start(t); o.stop(t + 0.02);
}
// o: { label, min, max, step, fine, def, value, center, fmt, onInput, size }
//    endless: { endless:true, notches, onStep(n), label, note, size }
function makeDial(o) {
  const endless = !!o.endless, sweep = endless ? 360 : 270, start = -sweep / 2;
  const notches = endless ? o.notches : Math.round((o.max - o.min) / o.step) + 1;
  const center = endless ? null : (o.center ?? (o.min < 0 && o.max > 0 ? 0 : null));
  const stepNow = () => (prefs.fine && o.fine) ? o.fine : o.step;
  let value = endless ? 0 : clamp(o.value ?? o.def ?? o.min, o.min, o.max), angle = 0;

  const root = el('div', { className: 'dial' });
  root.style.setProperty('--d', (o.size || 76) + 'px');
  const face = el('div', { className: 'face', tabIndex: 0 });
  face.setAttribute('role', 'slider');
  face.setAttribute('aria-label', o.label);
  face.setAttribute('aria-valuemin', endless ? 0 : o.min);
  face.setAttribute('aria-valuemax', endless ? notches : o.max);
  const svg = svgEl('svg', { viewBox: '0 0 100 100', 'aria-hidden': 'true' });

  const ticksN = endless ? o.notches : Math.min(notches, 29), ticks = [];
  for (let i = 0; i < ticksN; i++) {
    const f = endless ? i / ticksN : i / (ticksN - 1), th = (start + sweep * f) * Math.PI / 180;
    const major = endless ? i % Math.max(1, Math.round(ticksN / 4)) === 0
      : (i === 0 || i === ticksN - 1 || (ticksN > 8 && i % 4 === 0));
    const r1 = 40, r2 = major ? 47 : 44.5;
    const line = svgEl('line', { class: 'tk' + (major ? ' maj' : ''),
      x1: 50 + r1 * Math.sin(th), y1: 50 - r1 * Math.cos(th), x2: 50 + r2 * Math.sin(th), y2: 50 - r2 * Math.cos(th) });
    svg.append(line); ticks.push({ el: line, f });
  }
  const rot = svgEl('g');
  rot.append(svgEl('circle', { class: 'disc', cx: 50, cy: 50, r: 33 }), svgEl('circle', { class: 'grip', cx: 50, cy: 50, r: 29.5 }),
    svgEl('line', { class: 'ptr', x1: 50, y1: 21, x2: 50, y2: 31 }), svgEl('circle', { class: 'cap', cx: 50, cy: 50, r: 11 }));
  svg.append(rot); face.append(svg);
  const readout = el('div', { className: 'val' });
  root.append(face, el('div', { className: 'lab', textContent: o.label }), readout);

  function paint() {
    if (endless) {
      rot.setAttribute('transform', `rotate(${angle} 50 50)`);
      readout.textContent = o.note || '';
      face.setAttribute('aria-valuenow', 0);
      face.setAttribute('aria-valuetext', (o.note || '') + ' ' + o.label);
      return;
    }
    const frac = (value - o.min) / (o.max - o.min);
    rot.setAttribute('transform', `rotate(${start + sweep * frac} 50 50)`);
    const c = center == null ? 0 : (center - o.min) / (o.max - o.min), lo = Math.min(c, frac), hi = Math.max(c, frac);
    for (const t of ticks) t.el.classList.toggle('on', center == null ? (frac > 0 && t.f <= frac + 1e-9) : (t.f >= lo - 1e-9 && t.f <= hi + 1e-9 && frac !== c));
    readout.textContent = o.fmt ? o.fmt(value) : String(value);
    face.setAttribute('aria-valuenow', value);
    face.setAttribute('aria-valuetext', readout.textContent);
  }
  function set(v, feel = false) {
    v = clamp(v, o.min, o.max);
    if (v === value) return;
    value = v; paint();
    if (feel) { haptic(); clickSound(); }
    o.onInput?.(value);
  }
  function nudge(n) {
    if (endless) { angle += n * 360 / o.notches; paint(); haptic(); clickSound(); o.onStep?.(n); return; }
    const s = stepNow(), g = (value - o.min) / s, onGrid = Math.abs(g - Math.round(g)) < 1e-6;
    const target = onGrid ? Math.round(g) + n : (n > 0 ? Math.ceil(g) + n - 1 : Math.floor(g) + n + 1);
    set(round(o.min + target * s, Math.max(decimals(s), decimals(o.min))), true);
  }
  const reset = () => { if (!endless) set(o.def ?? o.min, true); };

  // Turning: the finger circles the disc; every `per` degrees is one click-stop.
  const per = () => endless ? 360 / o.notches : (prefs.fine && o.fine) ? 5 : Math.max(6, sweep / (notches - 1));
  let drag = null, lastTap = 0;
  const angleOf = e => {
    const b = face.getBoundingClientRect();
    return Math.atan2(e.clientY - b.top - b.height / 2, e.clientX - b.left - b.width / 2) * 180 / Math.PI;
  };
  face.addEventListener('pointerdown', e => {
    if (e.button > 0) return;
    try { face.setPointerCapture(e.pointerId); } catch {}
    drag = { last: angleOf(e), acc: 0, moved: 0 };
    face.classList.add('active');
  });
  face.addEventListener('pointermove', e => {
    if (!drag) return;
    const a = angleOf(e); let d = a - drag.last; d = ((d + 540) % 360) - 180; drag.last = a;
    drag.acc += d; drag.moved += Math.abs(d);
    const steps = Math.trunc(drag.acc / per());
    if (steps) { drag.acc -= steps * per(); nudge(steps); }
  });
  const end = () => {
    if (drag && drag.moved < 4) { const now = Date.now(); if (now - lastTap < 350) { reset(); lastTap = 0; } else lastTap = now; }
    drag = null; face.classList.remove('active');
  };
  face.addEventListener('pointerup', end);
  face.addEventListener('pointercancel', end);
  face.addEventListener('keydown', e => {
    const d = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 5, PageDown: -5 }[e.key];
    if (d) { e.preventDefault(); nudge(d); }
    else if (!endless && e.key === 'Home') { e.preventDefault(); set(o.min, true); }
    else if (!endless && e.key === 'End') { e.preventDefault(); set(o.max, true); }
    else if (!endless && (e.key === 'Backspace' || e.key === 'Delete')) { e.preventDefault(); reset(); }
  });
  face.addEventListener('wheel', e => { if (document.activeElement === face) { e.preventDefault(); nudge(e.deltaY < 0 ? 1 : -1); } }, { passive: false });
  paint();
  return { root, face, set: v => set(v, false), get: () => value, repaint: paint, setNote(t) { o.note = t; paint(); } };
}
// A dial from a definition: { label, min, max, step, fine, def, fmt, center } or { label, list, text, unit, def }
function dialFor(d, value, onInput, size = 68) {
  const list = !!d.list;
  return makeDial({ label: d.label, min: list ? 0 : d.min, max: list ? d.list.length - 1 : d.max, step: list ? 1 : d.step,
    fine: list ? 0 : d.fine, def: d.def ?? d.min, value, center: d.center, size,
    fmt: v => list ? (d.text ? d.text[v] : d.list[v] + (d.unit || '')) : d.fmt(v), onInput });
}

// Fader law: 0 dB sits at 80 % of the travel; the bottom of the travel is silence.
const F_MIN = -60, F_MAX = 6, F_POW = 0.4237;
const faderPos = dB => dB <= F_MIN ? 0 : clamp(((dB - F_MIN) / (F_MAX - F_MIN)) ** (1 / F_POW));
const faderDb = pos => pos <= 0.001 ? -Infinity : F_MIN + (F_MAX - F_MIN) * clamp(pos) ** F_POW;
function makeFader({ label, value, onInput }) {
  let dB = value <= F_MIN ? F_MIN : value;
  const root = el('div', { className: 'fader', tabIndex: 0 });
  root.setAttribute('role', 'slider');
  root.setAttribute('aria-label', label);
  root.setAttribute('aria-valuemin', F_MIN); root.setAttribute('aria-valuemax', F_MAX);
  const rail = el('div', { className: 'rail' }), fill = el('div', { className: 'fill' }), thumb = el('div', { className: 'thumb' });
  rail.append(fill); root.append(rail, thumb);
  const scale = el('div', { className: 'scale' });
  for (const m of [-40, -20, -10, -5, 0, 5]) scale.append(el('span', { textContent: m === 0 ? '0' : (m > 0 ? '+' : '−') + Math.abs(m), className: m === 0 ? 'z' : '', style: `left:${faderPos(m) * 100}%` }));
  root.append(scale);
  const width = () => rail.getBoundingClientRect().width || 1;
  function paint() {
    const p = faderPos(dB);
    thumb.style.left = `calc(14px + (100% - 28px) * ${p})`;
    fill.style.width = (p * 100) + '%';
    root.setAttribute('aria-valuenow', dB <= F_MIN ? F_MIN : dB);
    root.setAttribute('aria-valuetext', dB <= F_MIN ? 'minus infinity' : fmtDb(dB));
  }
  function set(v, feel = false) {
    if (v <= F_MIN + 0.01) v = F_MIN; else v = clamp(v, F_MIN, F_MAX);
    if (v === dB) return;
    const crossed = (dB < 0 && v >= 0) || (dB > 0 && v <= 0);
    dB = v; paint();
    if (feel && crossed) haptic(12);
    onInput?.(dB <= F_MIN ? -80 : dB);
  }
  const snap = v => v <= F_MIN + 0.25 ? F_MIN : round(Math.round(v / (prefs.fine ? 0.1 : 0.5)) * (prefs.fine ? 0.1 : 0.5), 1);
  let drag = null, lastTap = 0;
  root.addEventListener('pointerdown', e => {
    try { root.setPointerCapture(e.pointerId); } catch {}
    drag = { x: e.clientX, pos: faderPos(dB), moved: 0 };
  });
  root.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x; drag.moved += Math.abs(e.movementX || 0) || Math.abs(dx);
    set(snap(faderDb(drag.pos + dx / width() * (prefs.fine ? 0.25 : 1))), true);
  });
  const end = () => {
    if (drag && drag.moved < 4) { const now = Date.now(); if (now - lastTap < 350) { set(0, true); lastTap = 0; } else lastTap = now; }
    drag = null;
  };
  root.addEventListener('pointerup', end); root.addEventListener('pointercancel', end);
  root.addEventListener('keydown', e => {
    const s = prefs.fine ? 0.1 : 0.5, d = { ArrowRight: s, ArrowUp: s, ArrowLeft: -s, ArrowDown: -s, PageUp: 3, PageDown: -3 }[e.key];
    if (d) { e.preventDefault(); set(snap(Math.max(F_MIN, dB + d)), true); }
    else if (e.key === 'Home') { e.preventDefault(); set(F_MIN, true); }
    else if (e.key === 'End') { e.preventDefault(); set(F_MAX, true); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); set(0, true); }
  });
  paint();
  return { root, set: v => set(v, false), get: () => dB <= F_MIN ? -80 : dB };
}
