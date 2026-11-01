// Facade painters for Vader's Taxis buildings. All drawing is in METRES on a
// y-down canvas (0,0 = top-left of the wall, y = height - z). A second
// "emissive" canvas receives everything that should glow (lit windows, signs).
import * as THREE from 'three';
import { makeCanvas, toTexture, rng } from './textures.js';

export const YEL = '#f5b800', BLK = '#0f1113', WHITE = '#f1efe6';
const HEAVY = '"Arial Black","Segoe UI Black",Impact,"Helvetica Neue",Arial,sans-serif';
const COND = 'Impact,"Arial Narrow","Segoe UI",Arial,sans-serif';

// emit:false keeps the emissive pass tiny (walls with nothing that glows) to save GPU memory.
export function paintTexture(wM, hM, ppm, paint, { emit = true, maxDim = 2048 } = {}) {
  const k = Math.min(ppm, maxDim / Math.max(wM, hM));
  const W = Math.max(8, Math.round(wM * k)), H = Math.max(8, Math.round(hM * k));
  const c = makeCanvas(W, H), g = c.getContext('2d');
  const e = emit ? makeCanvas(W, H) : makeCanvas(8, 8), eg = e.getContext('2d');
  eg.fillStyle = '#000'; eg.fillRect(0, 0, e.width, e.height);
  g.scale(k, k); if (emit) eg.scale(k, k); else eg.scale(8 / wM, 8 / hM);
  paint(g, eg, wM, hM);
  return { map: toTexture(c, { aniso: 8 }), emissive: emit ? toTexture(e, { aniso: 4 }) : null };
}

export const material = ({ map, emissive }, emissiveIntensity = .9, extra = {}) =>
  new THREE.MeshStandardMaterial({ map, emissiveMap: emissive || null, emissive: emissive ? '#ffffff' : '#000000', emissiveIntensity, roughness: .78, metalness: .12, ...extra });

// ---------------------------------------------------------------- wall bases
export function corrugated(g, w, h, base = '#1f2327', rib = '#2c3238') {
  g.fillStyle = base; g.fillRect(0, 0, w, h);
  for (let x = 0; x < w; x += .24) { g.fillStyle = (x / .24 | 0) % 2 ? 'rgba(255,255,255,.055)' : 'rgba(0,0,0,.22)'; g.fillRect(x, 0, .12, h); }
  const r = rng(Math.round(w * 13 + h));
  for (let i = 0; i < w * .9; i++) { const x = r() * w, len = 1 + r() * h * .5, gr = g.createLinearGradient(0, 0, 0, len); gr.addColorStop(0, 'rgba(110,70,40,.0)'); gr.addColorStop(.15, 'rgba(110,70,40,.2)'); gr.addColorStop(1, 'rgba(110,70,40,0)'); g.fillStyle = gr; g.save(); g.translate(x, r() * h * .4); g.fillRect(0, 0, .09 + r() * .15, len); g.restore(); }
  g.fillStyle = 'rgba(0,0,0,.25)'; for (let y = 6; y < h; y += 6) g.fillRect(0, y, w, .06);  // panel joints
}
export function brick(g, w, h, base = '#6b3d33') {
  g.fillStyle = '#3a2824'; g.fillRect(0, 0, w, h); const r = rng(7);
  for (let y = 0; y < h; y += .12) for (let x = ((y / .12 | 0) % 2) * .12; x < w; x += .25) { g.fillStyle = `hsl(${10 + r() * 8},${35 + r() * 12}%,${24 + r() * 11}%)`; g.fillRect(x + .01, y + .01, .23, .1); }
}
export function concrete(g, w, h, base = '#8a8d8e') {
  g.fillStyle = base; g.fillRect(0, 0, w, h); const r = rng(Math.round(w + h * 3));
  for (let i = 0; i < w * h * .5; i++) { g.fillStyle = r() < .5 ? 'rgba(0,0,0,.05)' : 'rgba(255,255,255,.05)'; g.fillRect(r() * w, r() * h, .2 + r() * .5, .2 + r() * .5); }
  g.fillStyle = 'rgba(0,0,0,.28)'; for (let y = 3; y < h; y += 3) g.fillRect(0, y, w, .05); for (let x = 3; x < w; x += 3) g.fillRect(x, 0, .05, h);
  for (let i = 0; i < w * .4; i++) { const x = r() * w, len = 1 + r() * 7, gr = g.createLinearGradient(0, 0, 0, len); gr.addColorStop(0, 'rgba(30,35,30,.0)'); gr.addColorStop(.2, 'rgba(30,35,30,.16)'); gr.addColorStop(1, 'rgba(30,35,30,0)'); g.save(); g.translate(x, r() * h); g.fillStyle = gr; g.fillRect(0, 0, .15, len); g.restore(); }
}
export function containers(g, w, h, palette = [YEL, '#25272b', '#3d5a6d', '#7a3b2e', '#4a5a40', '#c9c6bd']) {
  const r = rng(Math.round(w * 7 + h)), cw = 6.06, ch = 2.6;
  for (let row = 0; row * ch < h + ch; row++) for (let x = -(row % 2) * 3; x < w; x += cw) {
    const col = palette[(r() * palette.length) | 0]; g.fillStyle = col; g.fillRect(x + .04, h - (row + 1) * ch, cw - .08, ch - .06);
    g.fillStyle = 'rgba(0,0,0,.28)'; for (let i = .2; i < cw - .2; i += .28) g.fillRect(x + i, h - (row + 1) * ch + .12, .09, ch - .3);
    g.fillStyle = 'rgba(255,255,255,.12)'; g.fillRect(x + .04, h - (row + 1) * ch, cw - .08, .1);
  }
}
export function plinth(g, w, h, ph = 1.1, stripe = true) {
  g.fillStyle = '#6e7173'; g.fillRect(0, h - ph, w, ph);
  g.fillStyle = 'rgba(0,0,0,.25)'; for (let x = 0; x < w; x += 3) g.fillRect(x, h - ph, .05, ph);
  if (stripe) hazard(g, 0, h - ph - .28, w, .28, .45);
}
export function hazard(g, x, y, w, h, step = .5) {
  g.save(); g.beginPath(); g.rect(x, y, w, h); g.clip(); g.fillStyle = YEL; g.fillRect(x, y, w, h); g.fillStyle = BLK;
  for (let i = -h; i < w + h; i += step * 2) { g.beginPath(); g.moveTo(x + i, y + h); g.lineTo(x + i + step, y + h); g.lineTo(x + i + step + h, y); g.lineTo(x + i + h, y); g.fill(); }
  g.restore();
}
export function checker(g, x, y, w, h, s = .25, a = YEL, b = BLK, e) {
  for (let j = 0; j * s < h; j++) for (let i = 0; i * s < w; i++) {
    const col = (i + j) % 2 ? a : b, ww = Math.min(s, w - i * s), hh = Math.min(s, h - j * s);
    g.fillStyle = col; g.fillRect(x + i * s, y + j * s, ww, hh); if (e && col === a) { e.fillStyle = col; e.fillRect(x + i * s, y + j * s, ww, hh); }
  }
}

// ---------------------------------------------------------------- text + logo
export function text(g, e, str, x, y, size, { color = WHITE, align = 'left', font = HEAVY, glow = true, max, spacing = 0 } = {}) {
  for (const ctx of glow && e ? [g, e] : [g]) {
    ctx.font = `${size}px ${font}`; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = 'alphabetic';
    if ('letterSpacing' in ctx) ctx.letterSpacing = `${spacing}px`;
    if (max) ctx.fillText(str, x, y, max); else ctx.fillText(str, x, y);
  }
}

// The VADER'S TAXIS wordmark: white VADER'S with a yellow chevron for the A, yellow TAXIS.
export function wordmark(g, e, x, y, w, h, { tagline = true, board = true } = {}) {
  if (board) {
    g.fillStyle = '#0c0d0f'; g.fillRect(x, y, w, h);
    g.strokeStyle = 'rgba(245,184,0,.55)'; g.lineWidth = Math.max(.04, h * .012); g.strokeRect(x + h * .03, y + h * .03, w - h * .06, h - h * .06);
  }
  const size = h * (tagline ? .56 : .66), base = y + h * (tagline ? .70 : .76);
  g.font = `${size}px ${HEAVY}`; if ('letterSpacing' in g) g.letterSpacing = `${size * .02}px`;
  const parts = [['V', WHITE], ['▲', YEL], ['DER’S', WHITE], [' ', WHITE], ['TAXIS', YEL]];
  const widths = parts.map(([s]) => s === '▲' ? size * .9 : g.measureText(s).width), total = widths.reduce((a, b) => a + b, 0);
  const k = Math.min(1, (w * .86) / total); let cx = x + (w - total * k) / 2;
  for (const ctx of e ? [g, e] : [g]) {
    ctx.save(); ctx.translate(cx, 0); ctx.scale(k, 1); let px = 0;
    parts.forEach(([s, col], i) => {
      if (s === '▲') { ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(px + size * .05, base); ctx.lineTo(px + size * .45, base - size * .74); ctx.lineTo(px + size * .85, base); ctx.lineTo(px + size * .64, base); ctx.lineTo(px + size * .45, base - size * .36); ctx.lineTo(px + size * .26, base); ctx.fill(); }
      else { ctx.font = `${size}px ${HEAVY}`; if ('letterSpacing' in ctx) ctx.letterSpacing = `${size * .02}px`; ctx.fillStyle = col; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.fillText(s, px, base); }
      px += widths[i];
    });
    ctx.restore();
  }
  if (tagline) {
    const ts = h * .13; text(g, e, 'PEOPLE  ·  PLACES  ·  PROBLEMS  SOLVED', x + w * .5, y + h * .93, ts, { align: 'center', color: '#d6d3c8', font: COND, spacing: ts * .18, max: w * .6 });
    checker(g, x + w - h * .55 - w * .03, y + h * .72, h * .45, h * .16, h * .04, YEL, '#0c0d0f', e);
  }
}

export function taxiIcon(g, e, x, y, s, color = YEL) {
  for (const c of [g, e]) {
    c.save(); c.translate(x, y); c.scale(s, s); c.strokeStyle = color; c.lineWidth = .06; c.lineJoin = 'round';
    c.beginPath(); c.moveTo(.05, .55); c.lineTo(.12, .55); c.lineTo(.2, .3); c.lineTo(.42, .22); c.lineTo(.66, .22); c.lineTo(.82, .38); c.lineTo(.95, .42); c.lineTo(.97, .55); c.lineTo(.9, .55); c.stroke();
    for (const wx of [.26, .76]) { c.beginPath(); c.arc(wx, .56, .08, 0, Math.PI * 2); c.stroke(); }
    c.strokeRect(.4, .1, .14, .08); c.restore();
  }
}

export function windowGrid(g, e, x, y, cols, rows, ww, wh, gx, gy, { lit = .65, seed = 1, frame = '#101316', warm = ['#ffd58a', '#ffc15c', '#ffe2a8'], cool = '#9fd8ff', coolP = .14 } = {}) {
  const r = rng(seed);
  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
    const px = x + i * (ww + gx), py = y + j * (wh + gy);
    g.fillStyle = frame; g.fillRect(px - .12, py - .12, ww + .24, wh + .24);
    const on = r() < lit, cl = r() < coolP;
    const col = on ? (cl ? cool : warm[(r() * warm.length) | 0]) : '#1b2730';
    const gr = g.createLinearGradient(0, py, 0, py + wh); gr.addColorStop(0, col); gr.addColorStop(1, on ? 'rgba(255,170,70,.85)' : '#0e161c');
    g.fillStyle = on ? gr : col; g.fillRect(px, py, ww, wh);
    if (on) { e.fillStyle = col; e.fillRect(px, py, ww, wh); }
    else { g.fillStyle = 'rgba(160,190,215,.18)'; g.beginPath(); g.moveTo(px, py + wh); g.lineTo(px + ww * .55, py); g.lineTo(px + ww * .8, py); g.lineTo(px + ww * .25, py + wh); g.fill(); }
    g.fillStyle = frame; g.fillRect(px + ww / 2 - .04, py, .08, wh); g.fillRect(px, py + wh * .52, ww, .07);
  }
}

// Workshop bay with lit interior, rack shelving, a parked taxi or an aircraft silhouette.
export function bay(g, e, x, y, w, h, { vehicle = 'taxi', seed = 3 } = {}) {
  const r = rng(seed);
  g.save(); g.beginPath(); g.rect(x, y, w, h); g.clip();
  const gr = g.createLinearGradient(0, y, 0, y + h); gr.addColorStop(0, '#171a1e'); gr.addColorStop(.6, '#22262b'); gr.addColorStop(1, '#4b3a2a');
  g.fillStyle = gr; g.fillRect(x, y, w, h);
  // back-wall shelving
  for (let s = 0; s < 4; s++) { const sy = y + h * (.2 + s * .15); g.fillStyle = '#34383d'; g.fillRect(x + w * .06, sy, w * .88, .08); for (let i = 0; i < 20; i++) { const bw = .35 + r() * .7, bx = x + w * .07 + r() * w * .84; g.fillStyle = ['#c43d2b', YEL, '#2b6a9a', '#9aa0a3', '#3a3f45', '#cf8a2c'][(r() * 6) | 0]; g.fillRect(bx, sy - .35 - r() * .4, bw, .5 + r() * .4); } }
  // ceiling strip lights
  for (let i = 0; i < 4; i++) { const lx = x + w * (.12 + i * .22); for (const c of [g, e]) { c.fillStyle = i % 2 ? '#bfe3ff' : '#fff1d0'; c.fillRect(lx, y + .5, w * .13, .12); } const lg = g.createLinearGradient(0, y + .6, 0, y + h * .75); lg.addColorStop(0, 'rgba(255,240,210,.35)'); lg.addColorStop(1, 'rgba(255,240,210,0)'); g.fillStyle = lg; g.fillRect(lx - w * .03, y + .6, w * .19, h * .65); }
  // blue steel column + cyan lab glow
  e.fillStyle = 'rgba(40,150,210,.55)'; e.fillRect(x + w * .55, y + h * .25, w * .38, h * .45);
  g.fillStyle = 'rgba(40,150,210,.25)'; g.fillRect(x + w * .55, y + h * .25, w * .38, h * .45);
  // parked vehicle
  const gy = y + h - .25, vx = x + w * .5, vw = w * .62, vh = h * .3;
  g.fillStyle = '#0b0c0e';
  if (vehicle === 'taxi') {
    g.beginPath(); g.moveTo(vx - vw / 2, gy); g.lineTo(vx - vw / 2, gy - vh * .45); g.lineTo(vx - vw * .32, gy - vh * .5); g.lineTo(vx - vw * .24, gy - vh); g.lineTo(vx + vw * .22, gy - vh); g.lineTo(vx + vw * .32, gy - vh * .5); g.lineTo(vx + vw / 2, gy - vh * .45); g.lineTo(vx + vw / 2, gy); g.fill();
    g.fillStyle = YEL; g.fillRect(vx - vw * .08, gy - vh * 1.12, vw * .16, vh * .12); e.fillStyle = YEL; e.fillRect(vx - vw * .08, gy - vh * 1.12, vw * .16, vh * .12);
    g.fillStyle = '#e8e6df'; for (const hx of [-.46, .46]) g.fillRect(vx + vw * hx - .15, gy - vh * .35, .3, .14);
    g.fillStyle = '#17191c'; for (const wx of [-.3, .3]) { g.beginPath(); g.arc(vx + vw * wx, gy - .1, vh * .22, 0, Math.PI * 2); g.fill(); }
  } else { // VTX silhouette, front view
    const cx = vx, cy = gy - vh * .55;
    for (const side of [-1, 1]) { g.fillStyle = '#d8dde0'; g.beginPath(); g.ellipse(cx + side * vw * .36, cy - vh * .12, vw * .24, vh * .13, 0, 0, Math.PI * 2); g.fill(); for (const c of [g, e]) { c.strokeStyle = '#38e4ff'; c.lineWidth = .08; c.beginPath(); c.ellipse(cx + side * vw * .36, cy - vh * .12, vw * .24, vh * .13, 0, 0, Math.PI * 2); c.stroke(); } }
    g.fillStyle = '#e9ecee'; g.beginPath(); g.ellipse(cx, cy, vh * .5, vh * .5, 0, 0, Math.PI * 2); g.fill(); g.fillStyle = 'rgba(30,60,80,.75)'; g.beginPath(); g.ellipse(cx, cy, vh * .4, vh * .4, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#16191c'; for (const lx of [-.3, -.15, .15, .3]) g.fillRect(cx + vw * lx - .08, cy + vh * .35, .16, vh * .5);
  }
  // floor sheen
  const fg = g.createLinearGradient(0, y + h * .9, 0, y + h); fg.addColorStop(0, 'rgba(255,190,110,0)'); fg.addColorStop(1, 'rgba(255,190,110,.45)'); g.fillStyle = fg; g.fillRect(x, y + h * .9, w, h * .1);
  // roller door slats rolled up at the top
  g.fillStyle = '#51565b'; g.fillRect(x, y, w, h * .09); g.fillStyle = 'rgba(0,0,0,.35)'; for (let i = 0; i < 8; i++) g.fillRect(x, y + i * h * .0115, w, .04);
  g.restore();
}

export function rollerDoor(g, x, y, w, h, color = '#4a5157') {
  g.fillStyle = color; g.fillRect(x, y, w, h); g.fillStyle = 'rgba(0,0,0,.35)'; for (let yy = y; yy < y + h; yy += .3) g.fillRect(x, yy, w, .05);
  g.fillStyle = 'rgba(255,255,255,.08)'; g.fillRect(x, y, w, h * .08);
  g.strokeStyle = YEL; g.lineWidth = .16; g.strokeRect(x - .08, y - .08, w + .16, h + .16);
}

export function serviceBoard(g, e, x, y, w, h, lines, { title } = {}) {
  g.fillStyle = '#0d0f12'; g.fillRect(x, y, w, h); g.strokeStyle = 'rgba(241,239,230,.35)'; g.lineWidth = .05; g.strokeRect(x + .1, y + .1, w - .2, h - .2);
  const n = lines.length + (title ? 1 : 0), step = (h - .8) / n, size = Math.min(step * .72, w * .12);
  let cy = y + .5 + step * .78;
  if (title) { text(g, e, title, x + .45, cy, size, { color: YEL, font: COND, max: w - .9 }); cy += step; }
  for (const l of lines) { text(g, e, l, x + .45, cy, size, { color: WHITE, font: COND, max: w - .9 }); cy += step; }
}
