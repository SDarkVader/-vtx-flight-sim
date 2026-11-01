// Procedural canvas textures for the Vader's Taxis environment.
// Everything is generated at load time: zero external or paid image assets.
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

export function toTexture(canvas, { repeat, srgb = true, aniso = 8, wrap = false } = {}) {
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

function blotch(ctx, w, h, x, y, r, color, alpha) {
  for (const dx of [-w, 0, w]) for (const dy of [-h, 0, h]) {
    const g = ctx.createRadialGradient(x + dx, y + dy, 0, x + dx, y + dy, r);
    g.addColorStop(0, color.replace('A', alpha));
    g.addColorStop(1, color.replace('A', 0));
    ctx.fillStyle = g;
    ctx.fillRect(x + dx - r, y + dy - r, r * 2, r * 2);
  }
}

// ---- Highland terrain ground texture ----------------------------------------
export function grassTexture() {
  const S = 512, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(19);
  g.fillStyle = '#6b8245'; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 90; i++) blotch(g, S, S, r() * S, r() * S, 30 + r() * 90, r() < .5 ? 'rgba(64,88,38,A)' : 'rgba(148,136,70,A)', .38);
  for (let i = 0; i < 40; i++) blotch(g, S, S, r() * S, r() * S, 15 + r() * 45, 'rgba(102,68,48,A)', .28); // peat / heather undertones
  speckle(g, S, S, r, 12000, ['#4f6e32', '#7b9449', '#8f8048', '#584432', '#647c40', '#9aa85a'], 1, 3.2);
  return toTexture(c, { wrap: true, aniso: 8 });
}

// ---- Asphalt: tarmac with micro-aggregate, tyre rubber burnouts and oil slicks ---
export function asphaltTextures() {
  const S = 512, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(29);
  g.fillStyle = '#323438'; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 80; i++) blotch(g, S, S, r() * S, r() * S, 20 + r() * 80, r() < .5 ? 'rgba(22,23,25,A)' : 'rgba(68,70,74,A)', .32);
  speckle(g, S, S, r, 16000, ['#242628', '#424548', '#525559', '#1a1b1d', '#5d6064'], 1, 2.4);
  // Tar-sealed crack repair snakes
  g.strokeStyle = 'rgba(14,15,16,.65)'; g.lineWidth = 1.4;
  for (let i = 0; i < 12; i++) {
    g.beginPath(); let x = r() * S, y = r() * S; g.moveTo(x, y);
    for (let k = 0; k < 9; k++) { x += (r() - .5) * 55; y += (r() - .5) * 55; g.lineTo(x, y); }
    g.stroke();
  }
  // Iridescent oil slick sheen (Scottish rain puddles)
  for (let i = 0; i < 6; i++) {
    const ox = r() * S, oy = r() * S, orad = 20 + r() * 40;
    const og = g.createRadialGradient(ox, oy, 0, ox, oy, orad);
    og.addColorStop(0, 'rgba(40,50,60,.3)');
    og.addColorStop(.4, 'rgba(80,120,90,.18)');
    og.addColorStop(.7, 'rgba(120,70,110,.14)');
    og.addColorStop(1, 'rgba(30,35,40,0)');
    g.fillStyle = og; g.fillRect(ox - orad, oy - orad, orad * 2, orad * 2);
  }
  // Roughness: low in puddle depressions
  const rc = makeCanvas(S, S), rg = rc.getContext('2d');
  rg.fillStyle = 'rgb(0,180,0)'; rg.fillRect(0, 0, S, S);
  const pr = rng(7);
  for (let i = 0; i < 30; i++) blotch(rg, S, S, pr() * S, pr() * S, 25 + pr() * 70, 'rgba(0,40,0,A)', .95);
  for (let i = 0; i < 50; i++) blotch(rg, S, S, pr() * S, pr() * S, 10 + pr() * 45, 'rgba(0,90,0,A)', .65);
  return { map: toTexture(c, { wrap: true, aniso: 8 }), rough: toTexture(rc, { wrap: true, srgb: false, aniso: 8 }) };
}

// ---- Concrete apron slabs: joints, spalls, skydrol stains and tie-down rings -
export function concreteTextures() {
  const S = 512, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(43);
  g.fillStyle = '#8a8d8c'; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 70; i++) blotch(g, S, S, r() * S, r() * S, 30 + r() * 90, r() < .5 ? 'rgba(105,108,107,A)' : 'rgba(165,167,162,A)', .35);
  speckle(g, S, S, r, 9500, ['#727574', '#9a9d98', '#646765', '#b0b3ad'], 1, 2.5);
  // Bituminous expansion joint sealant
  g.fillStyle = 'rgba(28,30,32,.75)'; g.fillRect(0, 0, S, 4); g.fillRect(0, 0, 4, S);
  g.fillStyle = 'rgba(225,225,215,.25)'; g.fillRect(0, 4, S, 2); g.fillRect(4, 0, 2, S);
  // Chipped slab corners
  for (const [cx, cy] of [[0, 0], [S, 0], [0, S], [S, S]]) {
    g.fillStyle = 'rgba(50,52,50,.55)'; g.beginPath(); g.arc(cx, cy, 14 + r() * 10, 0, Math.PI * 2); g.fill();
  }
  // Hydraulic fluid / skydrol drip stains
  for (let i = 0; i < 8; i++) {
    const sx = r() * S, sy = r() * S, srad = 8 + r() * 26;
    const sg = g.createRadialGradient(sx, sy, 0, sx, sy, srad);
    sg.addColorStop(0, 'rgba(45,35,25,.55)');
    sg.addColorStop(.6, 'rgba(45,35,25,.2)');
    sg.addColorStop(1, 'rgba(45,35,25,0)');
    g.fillStyle = sg; g.fillRect(sx - srad, sy - srad, srad * 2, srad * 2);
  }
  const rc = makeCanvas(S, S), rg = rc.getContext('2d');
  rg.fillStyle = 'rgb(0,210,0)'; rg.fillRect(0, 0, S, S);
  const pr = rng(11);
  for (let i = 0; i < 28; i++) blotch(rg, S, S, pr() * S, pr() * S, 25 + pr() * 65, 'rgba(0,70,0,A)', .9);
  return { map: toTexture(c, { wrap: true, aniso: 8 }), rough: toTexture(rc, { wrap: true, srgb: false, aniso: 8 }) };
}

// ---- Carbon-Fibre 2x2 Twill Weave ------------------------------------------
export function carbonFiberTextures() {
  const S = 128, c = makeCanvas(S, S), g = c.getContext('2d');
  g.fillStyle = '#0a0d0f'; g.fillRect(0, 0, S, S);
  const step = 8;
  for (let y = 0; y < S; y += step) {
    for (let x = 0; x < S; x += step) {
      const isH = ((Math.floor(x / step) + Math.floor(y / step)) % 2 === 0);
      const gr = isH ? g.createLinearGradient(x, y, x + step, y) : g.createLinearGradient(x, y, x, y + step);
      gr.addColorStop(0, '#11161a');
      gr.addColorStop(0.5, '#2c333a');
      gr.addColorStop(1, '#0c0f12');
      g.fillStyle = gr;
      g.fillRect(x, y, step, step);
      // Micro strand lines
      g.strokeStyle = 'rgba(255,255,255,0.06)';
      g.lineWidth = 0.8;
      if (isH) {
        for (let l = 2; l < step; l += 2) { g.beginPath(); g.moveTo(x, y + l); g.lineTo(x + step, y + l); g.stroke(); }
      } else {
        for (let l = 2; l < step; l += 2) { g.beginPath(); g.moveTo(x + l, y); g.lineTo(x + l, y + step); g.stroke(); }
      }
    }
  }
  return toTexture(c, { repeat: [18, 18], wrap: true, aniso: 8 });
}

// ---- Brushed Titanium & Machined Aerospace Alloy ---------------------------
export function brushedMetalTexture() {
  const S = 256, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(88);
  g.fillStyle = '#9098a0'; g.fillRect(0, 0, S, S);
  for (let y = 0; y < S; y++) {
    const val = Math.floor(140 + r() * 45);
    g.strokeStyle = `rgb(${val},${val + 4},${val + 8})`;
    g.lineWidth = 1;
    g.beginPath(); g.moveTo(0, y); g.lineTo(S, y); g.stroke();
  }
  return toTexture(c, { repeat: [4, 4], wrap: true, aniso: 8 });
}

// ---- Corrugated industrial steel cladding -----------------------------------
export function corrugatedTexture(base = '#1e2226', rib = '#2b3036') {
  const S = 256, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(77);
  g.fillStyle = base; g.fillRect(0, 0, S, S);
  for (let x = 0; x < S; x += 16) {
    const grad = g.createLinearGradient(x, 0, x + 16, 0);
    grad.addColorStop(0, rib); grad.addColorStop(.5, 'rgba(255,255,255,.09)'); grad.addColorStop(1, 'rgba(0,0,0,.38)');
    g.fillStyle = grad; g.fillRect(x, 0, 16, S);
  }
  // Galvanized zinc spangles & rust lines
  for (let i = 0; i < 22; i++) {
    const x = r() * S, len = 35 + r() * 190;
    const gr = g.createLinearGradient(0, 0, 0, len);
    gr.addColorStop(0, 'rgba(100,65,40,.0)'); gr.addColorStop(.2, 'rgba(105,70,42,.22)'); gr.addColorStop(1, 'rgba(100,65,40,0)');
    g.fillStyle = gr; g.fillRect(x, r() * S * .3, 3 + r() * 6, len);
  }
  return toTexture(c, { wrap: true, aniso: 8 });
}

export function roofTexture() {
  const S = 256, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(8);
  g.fillStyle = '#373a3e'; g.fillRect(0, 0, S, S);
  speckle(g, S, S, r, 4000, ['#282a2d', '#44474b', '#525559'], 1, 2);
  g.strokeStyle = 'rgba(12,13,15,.55)'; g.lineWidth = 2.5;
  for (let x = 0; x < S; x += 64) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, S); g.stroke(); }
  return toTexture(c, { wrap: true });
}

export function stoneTexture() {
  const S = 256, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(51);
  g.fillStyle = '#67625b'; g.fillRect(0, 0, S, S);
  for (let y = 0; y < S; y += 32) {
    let x = (y / 32 % 2) * 24;
    while (x < S) {
      const w = 40 + r() * 36;
      g.fillStyle = `rgb(${92 + r() * 36 | 0},${86 + r() * 32 | 0},${78 + r() * 28 | 0})`;
      g.fillRect(x + 1.5, y + 1.5, w - 3, 29);
      x += w;
    }
  }
  speckle(g, S, S, r, 2800, ['rgba(0,0,0,.22)', 'rgba(255,255,255,.12)'], 1, 2);
  return toTexture(c, { wrap: true, aniso: 8 });
}

// ---- Transgression Record Blackboard (Authentic Raymond Winston lore) -------
export function transgressionTexture() {
  const W = 512, H = 384, c = makeCanvas(W, H), g = c.getContext('2d');
  // Slate blackboard background
  g.fillStyle = '#1c2022'; g.fillRect(0, 0, W, H);
  // Wood frame border
  g.strokeStyle = '#5a3d28'; g.lineWidth = 14; g.strokeRect(7, 7, W - 14, H - 14);
  g.strokeStyle = '#322014'; g.lineWidth = 2; g.strokeRect(14, 14, W - 28, H - 28);
  // Chalk smudges
  const r = rng(101);
  for (let i = 0; i < 35; i++) blotch(g, W, H, r() * W, r() * H, 20 + r() * 40, 'rgba(240,245,250,A)', .08);
  // Chalk text
  g.font = 'bold 24px "Courier New", monospace';
  g.fillStyle = '#f0f5fa';
  g.textAlign = 'center';
  g.fillText('TRANSGRESSION RECORD', W / 2, 45);
  g.lineWidth = 2; g.strokeStyle = '#f0f5fa';
  g.beginPath(); g.moveTo(40, 55); g.lineTo(W - 40, 55); g.stroke();

  g.textAlign = 'left';
  g.font = 'bold 16px "Courier New", monospace';
  g.fillStyle = '#f5b800'; g.fillText('Ref: VT-2887', 35, 85);
  g.fillStyle = '#f0f5fa'; g.fillText('Subject: Steve (The Boss)', 35, 115);

  g.fillStyle = '#d0d8e0';
  g.font = '15px "Courier New", monospace';
  g.fillText('Offence: "Raymond Winston from', 35, 150);
  g.fillText('the bottom of the sea with a', 35, 175);
  g.fillText('banana up his arse."', 35, 200);

  g.fillStyle = '#f0f5fa';
  g.font = 'bold 16px "Courier New", monospace';
  g.fillText('Status: Recorded  [✔]', 35, 240);
  g.fillText('Outcome: On record (owned by Boss)', 35, 270);

  // Big red stamp: RECORDED
  g.save();
  g.translate(330, 290);
  g.rotate(-0.16);
  g.strokeStyle = '#d63030';
  g.lineWidth = 4;
  g.strokeRect(-90, -25, 180, 50);
  g.font = 'bold 26px "Arial Black", sans-serif';
  g.fillStyle = 'rgba(214,48,48,0.85)';
  g.textAlign = 'center';
  g.fillText('RECORDED', 0, 9);
  g.restore();

  // Exhibit A footer
  g.font = '12px "Courier New", monospace';
  g.fillStyle = '#8fa0a8';
  g.fillText('Compliance: Arthur Finch  |  Middle Mngmt: R. Winston', 35, 335);

  return toTexture(c, { aniso: 4 });
}

// ---- Depot Checklist Whiteboard ---------------------------------------------
export function depotWhiteboardTexture() {
  const W = 512, H = 384, c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = '#f6f7f9'; g.fillRect(0, 0, W, H);
  // Aluminum frame
  g.strokeStyle = '#8d9298'; g.lineWidth = 10; g.strokeRect(5, 5, W - 10, H - 10);
  // Header
  g.font = 'bold 22px "Arial Black", sans-serif'; g.fillStyle = '#181b1e';
  g.fillText("VADER'S TAXIS — DEPOT BOARD", 25, 42);
  g.fillStyle = '#f5b800'; g.fillRect(25, 50, W - 50, 4);

  // Checklist
  g.font = 'bold 18px "Courier New", monospace'; g.fillStyle = '#222';
  g.fillText('Next tasks:', 30, 85);

  const items = [
    '[✔] Battery range test ^',
    '[✔] Cab heater fix',
    '[✔] Highland weather flight',
    '[✔] Dispatch AI v2',
    '[✔] More coffee',
    '[ ] Steve apology to Raymond'
  ];
  items.forEach((it, i) => {
    g.fillStyle = it.startsWith('[✔]') ? '#1d7335' : '#b22222';
    g.fillText(it, 40, 120 + i * 30);
  });

  // Footer slogan
  g.font = 'bold 15px "Arial", sans-serif'; g.fillStyle = '#0f1113';
  g.fillText('CLEANER · QUIETER · TOUGHER · FURTHER', 30, 325);
  g.fillStyle = '#f5b800';
  g.font = 'italic 13px Georgia, serif';
  g.fillText('"Odd parts, big ideas, further miles."', 30, 350);

  return toTexture(c, { aniso: 4 });
}

// ---- Caution & Compliance Signboards ---------------------------------------
export function cautionSignTexture(title, lines, warning = true) {
  const W = 512, H = 256, c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = warning ? '#f5b800' : '#0f1113'; g.fillRect(0, 0, W, H);
  g.strokeStyle = warning ? '#0f1113' : '#f5b800'; g.lineWidth = 8; g.strokeRect(6, 6, W - 12, H - 12);

  // Hazard border on top
  const hW = W - 12;
  g.save(); g.beginPath(); g.rect(6, 6, hW, 20); g.clip();
  g.fillStyle = '#0f1113';
  for (let x = -20; x < W + 20; x += 24) {
    g.beginPath(); g.moveTo(x, 26); g.lineTo(x + 12, 26); g.lineTo(x + 22, 6); g.lineTo(x + 10, 6); g.fill();
  }
  g.restore();

  g.font = 'bold 24px "Arial Black", Impact, sans-serif';
  g.fillStyle = warning ? '#0f1113' : '#f5b800';
  g.textAlign = 'center';
  g.fillText(title, W / 2, 65);

  g.font = 'bold 16px "Arial", sans-serif';
  g.fillStyle = warning ? '#181b1e' : '#f1efe6';
  lines.forEach((l, i) => {
    g.fillText(l, W / 2, 105 + i * 28);
  });

  return toTexture(c, { aniso: 4 });
}

// ---- Cockpit Avionics & Vintage Vader's Taxi Meter Texture ------------------
export function cockpitDisplaysTexture() {
  const W = 512, H = 256, c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = '#050c10'; g.fillRect(0, 0, W, H);

  // --- Left Side: Primary Flight Display (PFD)
  g.fillStyle = '#0a1a24'; g.fillRect(10, 10, 240, 236);
  g.strokeStyle = '#2fe3ff'; g.lineWidth = 1.5; g.strokeRect(10, 10, 240, 236);

  // Artificial Horizon
  const cx = 130, cy = 110;
  g.save(); g.beginPath(); g.rect(30, 30, 200, 150); g.clip();
  const skyGrad = g.createLinearGradient(0, 30, 0, cy);
  skyGrad.addColorStop(0, '#0a3a60'); skyGrad.addColorStop(1, '#1a6fa0');
  g.fillStyle = skyGrad; g.fillRect(30, 30, 200, cy - 30);
  const gndGrad = g.createLinearGradient(0, cy, 0, 180);
  gndGrad.addColorStop(0, '#5a452a'); gndGrad.addColorStop(1, '#2a1e12');
  gndGrad.fillStyle = gndGrad; g.fillRect(30, cy, 200, 180 - cy);
  // Horizon line
  g.strokeStyle = '#ffffff'; g.lineWidth = 2;
  g.beginPath(); g.moveTo(40, cy); g.lineTo(220, cy); g.stroke();
  // Pitch ladder
  for (const dy of [-30, -15, 15, 30]) {
    g.beginPath(); g.moveTo(cx - 20, cy + dy); g.lineTo(cx + 20, cy + dy); g.stroke();
  }
  // Aircraft reticle
  g.strokeStyle = '#f5b800'; g.lineWidth = 3;
  g.beginPath(); g.moveTo(cx - 25, cy); g.lineTo(cx - 8, cy); g.lineTo(cx, cy + 6); g.lineTo(cx + 8, cy); g.lineTo(cx + 25, cy); g.stroke();
  g.restore();

  // Speed and Alt tapes
  g.font = 'bold 12px "Courier New", monospace'; g.fillStyle = '#2fe3ff';
  g.fillText('IAS 45 KT', 35, 205);
  g.fillText('ALT 25 FT', 155, 205);
  g.fillText('F1:1200 F2:1200 F3:1200 F4:1200', 25, 228);

  // --- Right Side: Vintage Vader's Taxi Meter (The Absurd Element!)
  g.fillStyle = '#14171a'; g.fillRect(265, 10, 235, 236);
  g.strokeStyle = '#d4a34b'; g.lineWidth = 3; g.strokeRect(265, 10, 235, 236);

  // Meter Header
  g.fillStyle = '#000000'; g.fillRect(275, 20, 215, 38);
  g.font = 'bold 16px "Arial Black", sans-serif'; g.fillStyle = '#f5b800';
  g.textAlign = 'center';
  g.fillText("VADER'S AIR TAXI", 382, 45);

  // Fare Display (LED segmented look)
  g.fillStyle = '#0a0500'; g.fillRect(275, 68, 215, 65);
  g.font = 'bold 36px "Courier New", monospace'; g.fillStyle = '#ff3b2a';
  g.fillText('£42.50', 382, 115);

  // Tariff & Status
  g.font = 'bold 13px "Courier New", monospace'; g.fillStyle = '#f5b800';
  g.fillText('TARIFF 1: HOVER SURCHARGE', 382, 155);
  g.fillStyle = '#35e060';
  g.fillText('STATUS: HIRED / AIRBORNE', 382, 178);

  // Compliance note on dash
  g.fillStyle = '#fff4cc'; g.fillRect(275, 195, 215, 42);
  g.strokeStyle = '#d6b85c'; g.lineWidth = 1; g.strokeRect(275, 195, 215, 42);
  g.font = 'bold 10px "Arial", sans-serif'; g.fillStyle = '#9c281b';
  g.fillText('COMPLIANCE NOTICE (VT-2887):', 382, 210);
  g.fillStyle = '#181b1e';
  g.fillText('STRICTLY NO BANANAS IN COCKPIT', 382, 226);

  return toTexture(c, { aniso: 4 });
}

// ---- Aviation Windsock Fabric Texture ----------------------------------------
export function windsockTexture() {
  const W = 256, H = 128, c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = '#ff4d1a'; g.fillRect(0, 0, W, H);
  const stripeW = W / 5;
  g.fillStyle = '#f4f5f6';
  g.fillRect(stripeW, 0, stripeW, H);
  g.fillRect(stripeW * 3, 0, stripeW, H);
  // Fabric weave texture
  const r = rng(5);
  speckle(g, W, H, r, 2000, ['rgba(0,0,0,0.1)', 'rgba(255,255,255,0.1)'], 1, 2);
  return toTexture(c, { wrap: true, aniso: 4 });
}

export function cloudTexture(seed = 3) {
  const W = 512, H = 256, c = makeCanvas(W, H), g = c.getContext('2d'), r = rng(seed);
  for (let i = 0; i < 85; i++) {
    const x = W * (.15 + .70 * r()), y = H * (.45 + .22 * (r() - .5)), rad = 28 + r() * 75 * (1 - Math.abs(x / W - .5));
    const gr = g.createRadialGradient(x, y, 0, x, y, rad);
    gr.addColorStop(0, 'rgba(255,255,255,.32)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
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

// ---- Molten Magma / Lava Texture (Animated in Shader/UV) ---------------------
export function lavaTexture() {
  const S = 512, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(108);
  // Base fiery magma gradient
  const bg = g.createLinearGradient(0, 0, S, S);
  bg.addColorStop(0, '#ff3000');
  bg.addColorStop(0.3, '#ff7a00');
  bg.addColorStop(0.6, '#ffcc00');
  bg.addColorStop(0.85, '#ff4800');
  bg.addColorStop(1, '#cc1800');
  g.fillStyle = bg; g.fillRect(0, 0, S, S);

  // Flowing river channels of blazing yellow/white heat
  for (let i = 0; i < 20; i++) {
    g.strokeStyle = r() < 0.5 ? '#fff4b8' : '#ffe066';
    g.lineWidth = 12 + r() * 24;
    g.lineCap = 'round';
    g.beginPath();
    let x = r() * S, y = 0;
    g.moveTo(x, y);
    while (y < S) {
      x += (r() - 0.5) * 60;
      y += 20 + r() * 40;
      g.lineTo(x, y);
    }
    g.stroke();
  }

  // Cooling black basalt crust islands floating on magma
  for (let i = 0; i < 90; i++) {
    const cx = r() * S, cy = r() * S, rad = 15 + r() * 45;
    g.fillStyle = '#1c1514';
    g.beginPath();
    for (let a = 0; a < Math.PI * 2; a += Math.PI / 4) {
      const dist = rad * (0.65 + r() * 0.7);
      const px = cx + Math.cos(a) * dist, py = cy + Math.sin(a) * dist;
      if (a === 0) g.moveTo(px, py); else g.lineTo(px, py);
    }
    g.closePath();
    g.fill();
    // Glowing red perimeter fissure
    g.strokeStyle = '#ff3d00';
    g.lineWidth = 2.5;
    g.stroke();
  }

  // Fine basalt ash speckle
  speckle(g, S, S, r, 6000, ['#0d0a09', '#241a18', '#382520'], 1, 3);
  return toTexture(c, { wrap: true, aniso: 8 });
}

// ---- Volcanic Basalt Rock Texture -------------------------------------------
export function volcanoBasaltTexture() {
  const S = 512, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(731);
  g.fillStyle = '#1a1918'; g.fillRect(0, 0, S, S);
  // Hexagonal basalt column joints
  g.strokeStyle = '#0d0d0c'; g.lineWidth = 3;
  const colSize = 32;
  for (let y = 0; y < S + colSize; y += colSize * 0.866) {
    const offset = ((y / (colSize * 0.866) | 0) % 2) * colSize * 0.5;
    for (let x = -colSize; x < S + colSize; x += colSize) {
      g.beginPath();
      for (let a = 0; a < Math.PI * 2; a += Math.PI / 3) {
        const px = x + offset + Math.cos(a) * (colSize * 0.55);
        const py = y + Math.sin(a) * (colSize * 0.55);
        if (a === 0) g.moveTo(px, py); else g.lineTo(px, py);
      }
      g.closePath();
      g.fillStyle = `hsl(25, ${8 + r() * 8}%, ${11 + r() * 8}%)`;
      g.fill();
      g.stroke();
    }
  }
  // Subtle glowing red/amber fissures in cracks
  for (let i = 0; i < 18; i++) {
    g.strokeStyle = 'rgba(255, 75, 20, 0.65)';
    g.lineWidth = 1.8;
    g.beginPath();
    let x = r() * S, y = r() * S; g.moveTo(x, y);
    for (let k = 0; k < 6; k++) { x += (r() - 0.5) * 40; y += (r() - 0.5) * 40; g.lineTo(x, y); }
    g.stroke();
  }
  speckle(g, S, S, r, 9000, ['#111110', '#252321', '#33302b'], 1, 2.5);
  return toTexture(c, { wrap: true, aniso: 8 });
}

// ---- Steampunk "Vader's Taxi's Basement" Sign Texture ------------------------
export function basementSignTexture() {
  const W = 1024, H = 512, c = makeCanvas(W, H), g = c.getContext('2d'), r = rng(42);
  // Dark industrial steel plate with brass frame
  g.fillStyle = '#181b1e'; g.fillRect(0, 0, W, H);
  g.strokeStyle = '#b88628'; g.lineWidth = 12; g.strokeRect(10, 10, W - 20, H - 20);
  g.strokeStyle = '#5a4218'; g.lineWidth = 4; g.strokeRect(22, 22, W - 44, H - 44);

  // Corner brass rivets
  for (const [rx, ry] of [[35, 35], [W - 35, 35], [35, H - 35], [W - 35, H - 35], [W / 2, 35], [W / 2, H - 35]]) {
    g.fillStyle = '#d4af37'; g.beginPath(); g.arc(rx, ry, 10, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#594412'; g.beginPath(); g.arc(rx - 3, ry - 3, 3, 0, Math.PI * 2); g.fill();
  }

  // Steampunk cogs and gears on sides
  function drawGear(gx, gy, rad, teeth, col = '#b88628') {
    g.save(); g.translate(gx, gy);
    g.fillStyle = col; g.beginPath(); g.arc(0, 0, rad, 0, Math.PI * 2); g.fill();
    for (let t = 0; t < teeth; t++) {
      const a = (t / teeth) * Math.PI * 2;
      g.save(); g.rotate(a);
      g.fillRect(-rad * 0.12, -rad * 1.25, rad * 0.24, rad * 0.35);
      g.restore();
    }
    g.fillStyle = '#181b1e'; g.beginPath(); g.arc(0, 0, rad * 0.45, 0, Math.PI * 2); g.fill();
    g.fillStyle = col; g.beginPath(); g.arc(0, 0, rad * 0.2, 0, Math.PI * 2); g.fill();
    g.restore();
  }
  drawGear(100, 100, 55, 12, '#c9933b');
  drawGear(170, 60, 38, 10, '#8c6828');
  drawGear(W - 100, 100, 55, 12, '#c9933b');
  drawGear(W - 170, 60, 38, 10, '#8c6828');

  // Arched Header Banner: "Vader's"
  g.fillStyle = '#e8dec8';
  g.font = 'bold 76px "Georgia", serif';
  g.textAlign = 'center';
  g.shadowColor = '#ff5500';
  g.shadowBlur = 18;
  g.fillText("Vader's", W / 2, 130);
  g.shadowBlur = 0;

  // Middle Plate: "Taxi's"
  g.fillStyle = '#f5b800';
  g.font = 'bold 64px "Arial Black", Impact, sans-serif';
  g.fillText("Taxi's", W / 2, 230);

  // Lower Steampunk Ribbon Plaque: "Basement"
  const rw = 520, rh = 110, rx = (W - rw) / 2, ry = 280;
  g.fillStyle = '#3a2718'; g.fillRect(rx, ry, rw, rh);
  g.strokeStyle = '#d4af37'; g.lineWidth = 6; g.strokeRect(rx, ry, rw, rh);
  g.fillStyle = '#f4eedb';
  g.font = 'bold 78px "Georgia", "Times New Roman", serif';
  g.fillText("Basement", W / 2, ry + 82);

  // Subtitle warning
  g.font = 'bold 20px "Courier New", monospace';
  g.fillStyle = '#ff6a00';
  g.fillText("VOLCANIC HEADQUARTERS · COMPLIANCE OFF-LIMITS", W / 2, 450);

  return toTexture(c, { aniso: 8 });
}

// ---- Vintage Subway Platform Station Sign Texture ---------------------------
export function subwayStationSignTexture() {
  const W = 512, H = 256, c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = '#081c24'; g.fillRect(0, 0, W, H);
  g.strokeStyle = '#38e4ff'; g.lineWidth = 6; g.strokeRect(8, 8, W - 16, H - 16);

  // Japanese Kanji: 地下鉄 (Chikatetsu = Subway)
  g.font = 'bold 72px "Hiragino Kaku Gothic Pro", "Yu Gothic", "Meiryo", sans-serif';
  g.fillStyle = '#ffffff';
  g.textAlign = 'center';
  g.fillText('地下鉄', W / 2, 90);

  // English: SUBWAY STATION
  g.font = 'bold 26px "Arial Black", sans-serif';
  g.fillStyle = '#38e4ff';
  g.fillText('SUBWAY STATION', W / 2, 135);

  // Platform 3 banner
  g.fillStyle = '#f5b800'; g.fillRect(40, 160, W - 80, 55);
  g.fillStyle = '#000000';
  g.font = 'bold 32px Impact, Arial, sans-serif';
  g.fillText('PLATFORM 3  ·  VTX BASEMENT', W / 2, 200);

  return toTexture(c, { aniso: 8 });
}

// ---- Cherry Blossom Petals Texture ------------------------------------------
export function cherryBlossomTexture() {
  const S = 128, c = makeCanvas(S, S), g = c.getContext('2d'), r = rng(88);
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2;
    const px = 64 + Math.cos(a) * 24, py = 64 + Math.sin(a) * 24;
    const pg = g.createRadialGradient(px, py, 0, px, py, 28);
    pg.addColorStop(0, '#ffffff');
    pg.addColorStop(0.4, '#ffb8d2');
    pg.addColorStop(0.85, '#ff80aa');
    pg.addColorStop(1, 'rgba(255, 128, 170, 0)');
    g.fillStyle = pg;
    g.beginPath();
    g.ellipse(px, py, 22, 14, a, 0, Math.PI * 2);
    g.fill();
  }
  return toTexture(c);
}

// ---- Metallic Robot Mask with Fiery Glowing Eyes ----------------------------
export function robotMaskTexture() {
  const W = 256, H = 256, c = makeCanvas(W, H), g = c.getContext('2d');
  g.fillStyle = '#1c1f22'; g.fillRect(0, 0, W, H);
  // Metallic curved face shape
  const fg = g.createRadialGradient(128, 120, 20, 128, 120, 110);
  fg.addColorStop(0, '#8c949c');
  fg.addColorStop(0.6, '#464c54');
  fg.addColorStop(1, '#1e2124');
  g.fillStyle = fg;
  g.beginPath();
  g.ellipse(128, 128, 90, 110, 0, 0, Math.PI * 2);
  g.fill();

  // Mechanical seam lines
  g.strokeStyle = '#2b3036'; g.lineWidth = 2.5;
  g.beginPath(); g.moveTo(128, 30); g.lineTo(128, 220); g.stroke();
  g.beginPath(); g.moveTo(50, 128); g.lineTo(206, 128); g.stroke();

  // Fiery glowing orange-red eyes (as in reference photos)
  for (const ex of [92, 164]) {
    const ey = 110;
    // Outer flame glow
    const eg = g.createRadialGradient(ex, ey, 2, ex, ey, 28);
    eg.addColorStop(0, '#fff5cc');
    eg.addColorStop(0.3, '#ff6600');
    eg.addColorStop(0.7, '#cc1100');
    eg.addColorStop(1, 'rgba(180, 0, 0, 0)');
    g.fillStyle = eg;
    g.beginPath(); g.arc(ex, ey, 28, 0, Math.PI * 2); g.fill();
    // Inner core
    g.fillStyle = '#ffffff';
    g.beginPath(); g.ellipse(ex, ey, 10, 6, 0, 0, Math.PI * 2); g.fill();
  }

  // Subdued robotic mouth slit
  g.fillStyle = '#0f1113'; g.fillRect(104, 175, 48, 6);
  return toTexture(c, { aniso: 4 });
}

// ---- Steve Dark's Heroism Citation Certificate (31 Oct 2026) -----------------
export function citationTexture() {
  const W = 512, H = 724, c = makeCanvas(W, H), g = c.getContext('2d');
  // Aged parchment paper
  g.fillStyle = '#faf4e4'; g.fillRect(0, 0, W, H);
  g.strokeStyle = '#c9a24d'; g.lineWidth = 8; g.strokeRect(16, 16, W - 32, H - 32);
  g.strokeStyle = '#7d6028'; g.lineWidth = 2; g.strokeRect(26, 26, W - 52, H - 52);

  // Header
  g.font = 'bold 24px "Arial Black", sans-serif'; g.fillStyle = '#1c1b18'; g.textAlign = 'center';
  g.fillText("Vader's Taxis", W / 2, 70);
  g.font = 'italic 34px "Georgia", serif'; g.fillStyle = '#8a5e1d';
  g.fillText("Citation", W / 2, 120);

  g.font = '16px "Georgia", serif'; g.fillStyle = '#423d33';
  g.fillText("Awarded to", W / 2, 160);
  g.font = 'bold 36px "Georgia", serif'; g.fillStyle = '#1c1b18';
  g.fillText("Steve Dark", W / 2, 210);

  g.font = 'bold 18px "Georgia", serif'; g.fillStyle = '#8a5e1d';
  g.fillText("For Extraordinary Altruistic Heroism", W / 2, 255);

  // Text body
  g.font = '14px "Georgia", serif'; g.fillStyle = '#2d2820';
  const textLines = [
    "In the manual recovery of the Vader's Taxis",
    "experimental aircraft and AI agent (Colin),",
    "following a loss of control, under extreme",
    "conditions, severe time constraints and",
    "limited fuel, with no loss of life or asset."
  ];
  let ty = 310;
  for (const line of textLines) {
    g.fillText(line, W / 2, ty);
    ty += 28;
  }

  // Wreath icon
  g.font = '40px serif'; g.fillStyle = '#c9a24d';
  g.fillText("🪶 🚁 🪶", W / 2, 490);

  // Signature
  g.font = 'italic 20px "Brush Script MT", cursive, sans-serif'; g.fillStyle = '#181b1e';
  g.fillText("Arthur Finch", 160, 620);
  g.font = '12px sans-serif'; g.fillStyle = '#5a554a';
  g.fillText("Arthur Finch", 160, 642);
  g.fillText("Compliance & Operations", 160, 660);

  g.font = 'bold 13px sans-serif'; g.fillStyle = '#1c1b18';
  g.fillText("31 October 2026", 360, 642);

  return toTexture(c, { aniso: 8 });
}
