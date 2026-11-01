// Procedural canvas textures for the Vader's Taxis environment.
// Everything is generated at load time: no external or paid image assets.
import * as THREE from 'three';

export function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

export function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

export function toTexture(canvas, { repeat, srgb = true, aniso = 4, wrap = false } = {}) {
  const t = new THREE.CanvasTexture(canvas);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = aniso;
  if (wrap || repeat) {
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    if (repeat) t.repeat.set(...repeat);
  }
  return t;
}

function speckle(ctx, w, h, rand, count, colors, minR, maxR) {
  for (let i = 0; i < count; i++) {
    ctx.fillStyle = colors[(rand() * colors.length) | 0];
    const r = minR + rand() * (maxR - minR);
    ctx.fillRect(rand() * w, rand() * h, r, r);
  }
}

// Wrap-around blotches so tiles repeat without visible seams.
function blotch(ctx, w, h, x, y, r, color, alpha) {
  for (const dx of [-w, 0, w]) for (const dy of [-h, 0, h]) {
    const g = ctx.createRadialGradient(x + dx, y + dy, 0, x + dx, y + dy, r);
    g.addColorStop(0, color.replace('A', alpha));
    g.addColorStop(1, color.replace('A', 0));
    ctx.fillStyle = g;
    ctx.fillRect(x + dx - r, y + dy - r, r * 2, r * 2);
  }
}

export function grassTexture() {
  const S = 512, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(11);
  g.fillStyle = '#7c9650'; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 90; i++) blotch(g, S, S, r() * S, r() * S, 30 + r() * 80, r() < .5 ? 'rgba(74,104,52,A)' : 'rgba(128,142,78,A)', .35);
  speckle(g, S, S, r, 9000, ['#587a3e', '#7b9a55', '#4e6f38', '#8aa35f', '#6f8c46'], 1, 3);
  return toTexture(c, { wrap: true, aniso: 8 });
}

export function asphaltTextures() {
  const S = 512, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(23);
  g.fillStyle = '#3a3d40'; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 70; i++) blotch(g, S, S, r() * S, r() * S, 20 + r() * 70, r() < .5 ? 'rgba(30,32,35,A)' : 'rgba(78,80,82,A)', .3);
  speckle(g, S, S, r, 14000, ['#2c2e30', '#4b4e51', '#585b5d', '#222426'], 1, 2.2);
  // tyre rubber / oil darkening and hairline cracks
  g.strokeStyle = 'rgba(18,19,20,.55)'; g.lineWidth = 1;
  for (let i = 0; i < 9; i++) { g.beginPath(); let x = r() * S, y = r() * S; g.moveTo(x, y); for (let k = 0; k < 8; k++) { x += (r() - .5) * 60; y += (r() - .5) * 60; g.lineTo(x, y); } g.stroke(); }
  // Roughness: low = shiny. Puddle blotches from recent rain.
  const rc = makeCanvas(S, S), rg = rc.getContext('2d'); rg.fillStyle = 'rgb(0,176,0)'; rg.fillRect(0, 0, S, S);
  const pr = rng(5);
  for (let i = 0; i < 26; i++) blotch(rg, S, S, pr() * S, pr() * S, 25 + pr() * 60, 'rgba(0,60,0,A)', .95);
  for (let i = 0; i < 40; i++) blotch(rg, S, S, pr() * S, pr() * S, 10 + pr() * 40, 'rgba(0,110,0,A)', .6);
  return { map: toTexture(c, { wrap: true, aniso: 8 }), rough: toTexture(rc, { wrap: true, srgb: false, aniso: 8 }) };
}

// Concrete apron slab texture: one tile = one 12 m slab with joints.
export function concreteTextures() {
  const S = 512, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(31);
  g.fillStyle = '#8d8f8c'; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 60; i++) blotch(g, S, S, r() * S, r() * S, 30 + r() * 80, r() < .5 ? 'rgba(112,114,111,A)' : 'rgba(160,160,154,A)', .3);
  speckle(g, S, S, r, 8000, ['#7c7e7b', '#9d9d97', '#6f716e'], 1, 2.2);
  g.fillStyle = 'rgba(40,42,44,.55)'; g.fillRect(0, 0, S, 3); g.fillRect(0, 0, 3, S);
  g.fillStyle = 'rgba(215,215,205,.18)'; g.fillRect(0, 3, S, 2); g.fillRect(3, 0, 2, S);
  const rc = makeCanvas(S, S), rg = rc.getContext('2d'); rg.fillStyle = 'rgb(0,200,0)'; rg.fillRect(0, 0, S, S);
  const pr = rng(9);
  for (let i = 0; i < 22; i++) blotch(rg, S, S, pr() * S, pr() * S, 25 + pr() * 55, 'rgba(0,95,0,A)', .9);
  return { map: toTexture(c, { wrap: true, aniso: 8 }), rough: toTexture(rc, { wrap: true, srgb: false, aniso: 8 }) };
}

export function corrugatedTexture(base = '#1e2226', rib = '#2b3036') {
  const S = 256, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(77);
  g.fillStyle = base; g.fillRect(0, 0, S, S);
  for (let x = 0; x < S; x += 16) {
    const grad = g.createLinearGradient(x, 0, x + 16, 0);
    grad.addColorStop(0, rib); grad.addColorStop(.5, 'rgba(255,255,255,.07)'); grad.addColorStop(1, 'rgba(0,0,0,.35)');
    g.fillStyle = grad; g.fillRect(x, 0, 16, S);
  }
  for (let i = 0; i < 18; i++) {
    const x = r() * S, len = 40 + r() * 190;
    const gr = g.createLinearGradient(0, 0, 0, len);
    gr.addColorStop(0, 'rgba(92,60,38,.0)'); gr.addColorStop(.2, 'rgba(92,60,38,.18)'); gr.addColorStop(1, 'rgba(92,60,38,0)');
    g.fillStyle = gr; g.fillRect(x, r() * S * .3, 3 + r() * 5, len);
  }
  return toTexture(c, { wrap: true, aniso: 8 });
}

export function roofTexture() {
  const S = 256, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(8);
  g.fillStyle = '#3b3f43'; g.fillRect(0, 0, S, S);
  speckle(g, S, S, r, 3500, ['#2f3236', '#474b50', '#55595d'], 1, 2);
  g.strokeStyle = 'rgba(15,16,18,.45)'; g.lineWidth = 2;
  for (let x = 0; x < S; x += 64) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, S); g.stroke(); }
  return toTexture(c, { wrap: true });
}

export function stoneTexture() {
  const S = 256, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(51);
  g.fillStyle = '#6f6a62'; g.fillRect(0, 0, S, S);
  for (let y = 0; y < S; y += 32) {
    let x = (y / 32 % 2) * 24;
    while (x < S) { const w = 40 + r() * 36; g.fillStyle = `rgb(${96 + r() * 36 | 0},${90 + r() * 32 | 0},${82 + r() * 28 | 0})`; g.fillRect(x + 1.5, y + 1.5, w - 3, 29); x += w; }
  }
  speckle(g, S, S, r, 2500, ['rgba(0,0,0,.18)', 'rgba(255,255,255,.1)'], 1, 2);
  return toTexture(c, { wrap: true, aniso: 8 });
}

export function cloudTexture(seed = 3) {
  const W = 512, H = 256, c = makeCanvas(W, H), g = c.getContext('2d'), r = rng(seed);
  for (let i = 0; i < 70; i++) {
    const x = W * (.18 + .64 * r()), y = H * (.45 + .2 * (r() - .5)), rad = 28 + r() * 70 * (1 - Math.abs(x / W - .5));
    const gr = g.createRadialGradient(x, y, 0, x, y, rad);
    gr.addColorStop(0, 'rgba(255,255,255,.28)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr; g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
  }
  return toTexture(c);
}

export function glowTexture() {
  const S = 128, c = makeCanvas(S, S), g = c.getContext('2d');
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(.15, 'rgba(255,255,255,.7)'); gr.addColorStop(.5, 'rgba(255,255,255,.16)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, S, S);
  return toTexture(c);
}
