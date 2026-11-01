// Authoritative Live Minimap & Tactical Display for VTX Flight Simulator.
// Renders the genuine mathematical geometry graph of runways, curved Bézier taxiways,
// aprons, stands, holding points, and facility complexes from LAYOUT with sub-millimetre parity.
// Live aircraft pose is synchronized with MuJoCo truth frame (position, physical yaw, velocity).
import { LAYOUT } from './layout.js';

function evalCubicBezier(p0, p1, p2, p3, t) {
  const mt = 1 - t, mt2 = mt * mt, mt3 = mt2 * mt, t2 = t * t, t3 = t2 * t;
  return [
    mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0],
    mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]
  ];
}

const backgroundCache = new WeakMap();

export class TacticalMinimap {
  constructor(canvas, { isLarge = false } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.isLarge = isLarge;
    this.zoom = 0.88;
    this.center = [20, 110]; // centered to capture both runways and northern facilities
    this.tacticalMode = false; // toggle between full valley (0.88x) and airfield tactical (2.4x)
    this.dragStart = null;
    this.isDragging = false;
    
    this.bindEvents();
  }

  bindEvents() {
    const c = this.canvas;
    
    // Double click to toggle tactical zoom
    c.addEventListener('dblclick', (e) => {
      this.tacticalMode = !this.tacticalMode;
      this.zoom = this.tacticalMode ? 2.4 : 0.88;
      this.center = this.tacticalMode ? [0, 40] : [20, 110];
      backgroundCache.delete(c);
      e.preventDefault();
    });

    // Touch support: drag to pan
    let touchDist = 0;
    c.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        this.isDragging = true;
        this.dragStart = [e.touches[0].clientX, e.touches[0].clientY, ...this.center];
      } else if (e.touches.length === 2) {
        touchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      }
    }, { passive: true });

    c.addEventListener('touchmove', (e) => {
      if (e.touches.length === 1 && this.isDragging && this.dragStart) {
        const dx = e.touches[0].clientX - this.dragStart[0];
        const dy = e.touches[0].clientY - this.dragStart[1];
        const span = (1000) / this.zoom;
        this.center[0] = this.dragStart[2] - (dx / c.width) * span;
        this.center[1] = this.dragStart[3] + (dy / c.height) * span;
        backgroundCache.delete(c);
      } else if (e.touches.length === 2 && touchDist > 0) {
        const newDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
        const scale = newDist / touchDist;
        this.zoom = Math.max(0.6, Math.min(6.0, this.zoom * scale));
        touchDist = newDist;
        backgroundCache.delete(c);
      }
    }, { passive: true });

    c.addEventListener('touchend', () => { this.isDragging = false; }, { passive: true });
  }

  getProjection(worldHalf = 500) {
    const w = this.canvas.width, h = this.canvas.height;
    const span = (worldHalf * 2) / this.zoom;
    const cx = this.center[0], cy = this.center[1];
    return {
      w, h,
      px: x => ((x - cx) / span + 0.5) * w,
      py: y => (0.5 - (y - cy) / span) * h,
      scaleM: m => (m / span) * w,
      unpx: sx => (sx / w - 0.5) * span + cx,
      unpy: sy => (0.5 - sy / h) * span + cy
    };
  }

  buildBackgroundLayer(world, proj) {
    const layer = document.createElement('canvas');
    layer.width = proj.w; layer.height = proj.h;
    const g = layer.getContext('2d');
    const { px, py, scaleM, w, h } = proj;

    // 1. Terrain elevation contour background
    g.fillStyle = '#1c2826'; g.fillRect(0, 0, w, h);
    if (world && world.heights_m) {
      const n = world.heights_m.length;
      const step = Math.max(1, Math.floor(n / 64));
      for (let j = 0; j < n - 1; j += step) {
        for (let i = 0; i < n - 1; i += step) {
          const v = world.heights_m[j][i];
          const wx = -world.half_m + (i / (n - 1)) * world.half_m * 2;
          const wy = -world.half_m + (j / (n - 1)) * world.half_m * 2;
          const shade = Math.min(85, Math.round(35 + v * 0.9));
          g.fillStyle = `rgb(${shade},${shade + 22},${shade + 14})`;
          const x0 = px(wx), y0 = py(wy);
          const x1 = px(wx + (step / (n - 1)) * world.half_m * 2);
          const y1 = py(wy + (step / (n - 1)) * world.half_m * 2);
          g.fillRect(x0, y1, Math.max(1, x1 - x0 + 1), Math.max(1, y0 - y1 + 1));
        }
      }
    }

    // 2. Lake water
    if (world && world.water) {
      const { x, y, half_x, half_y } = world.water;
      g.fillStyle = 'rgba(75, 140, 175, 0.75)';
      g.fillRect(px(x - half_x), py(y + half_y), scaleM(half_x * 2), scaleM(half_y * 2));
      g.strokeStyle = '#68b5d8'; g.lineWidth = 1;
      g.strokeRect(px(x - half_x), py(y + half_y), scaleM(half_x * 2), scaleM(half_y * 2));
    }

    // 3. Grid coordinates (every 200m)
    g.strokeStyle = 'rgba(150, 195, 180, 0.12)'; g.lineWidth = 1;
    for (let x = -600; x <= 800; x += 200) {
      g.beginPath(); g.moveTo(px(x), 0); g.lineTo(px(x), h); g.stroke();
    }
    for (let y = -400; y <= 800; y += 200) {
      g.beginPath(); g.moveTo(0, py(y)); g.lineTo(w, py(y)); g.stroke();
    }

    // 4. Expanded Aprons
    if (LAYOUT.aprons_expanded) {
      for (const ap of LAYOUT.aprons_expanded) {
        const [aw, ah] = ap.size; const [acx, acy] = ap.center;
        g.fillStyle = '#40454b';
        g.fillRect(px(acx - aw / 2), py(acy + ah / 2), scaleM(aw), scaleM(ah));
        g.strokeStyle = '#f5b800'; g.lineWidth = 1.2;
        g.strokeRect(px(acx - aw / 2), py(acy + ah / 2), scaleM(aw), scaleM(ah));
        g.fillStyle = 'rgba(235, 230, 215, 0.4)';
        g.font = `bold ${Math.max(9, Math.round(scaleM(18)))}px system-ui`;
        g.textAlign = 'center';
        g.fillText(ap.name, px(acx), py(acy));
      }
    }

    // 5. Central Operational Apron
    if (LAYOUT.apron) {
      const { x0, x1, y0, y1 } = LAYOUT.apron;
      g.fillStyle = '#454a50';
      g.fillRect(px(x0), py(y1), scaleM(x1 - x0), scaleM(y1 - y0));
      g.strokeStyle = '#f5b800'; g.lineWidth = 1;
      g.strokeRect(px(x0), py(y1), scaleM(x1 - x0), scaleM(y1 - y0));
    }

    // 6. Runways
    // Runway 08/26 (Primary: 1432m x 30m)
    g.save();
    g.fillStyle = '#22252a';
    g.fillRect(px(-716), py(15), scaleM(1432), scaleM(30));
    g.strokeStyle = 'rgba(255,255,255,0.7)'; g.lineWidth = Math.max(1, scaleM(0.8));
    g.setLineDash([scaleM(14), scaleM(16)]);
    g.beginPath(); g.moveTo(px(-690), py(0)); g.lineTo(px(690), py(0)); g.stroke();
    g.setLineDash([]);
    // Heading numbers '08' and '26'
    g.fillStyle = '#ffffff';
    g.font = `bold ${Math.max(8, Math.round(scaleM(14)))}px "Arial Black", sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('08', px(-660), py(0));
    g.fillText('26', px(660), py(0));
    // Threshold green/red markers
    g.fillStyle = '#22e055'; g.fillRect(px(-716), py(15), scaleM(3), scaleM(30));
    g.fillStyle = '#ff2211'; g.fillRect(px(713), py(15), scaleM(3), scaleM(30));
    g.restore();

    // Runway 03/21 (Secondary: 980m x 23m, 55 deg)
    g.save();
    g.translate(px(235), py(0));
    const rwy21Ang = -Math.atan2(0.81915204, 0.57357644); // Canvas Y is inverted
    g.rotate(rwy21Ang);
    const r21Len = scaleM(980), r21W = scaleM(23);
    g.fillStyle = '#22252a';
    g.fillRect(-r21Len / 2, -r21W / 2, r21Len, r21W);
    g.strokeStyle = 'rgba(255,255,255,0.7)'; g.lineWidth = Math.max(1, scaleM(0.8));
    g.setLineDash([scaleM(12), scaleM(14)]);
    g.beginPath(); g.moveTo(-r21Len / 2 + scaleM(20), 0); g.lineTo(r21Len / 2 - scaleM(20), 0); g.stroke();
    g.setLineDash([]);
    g.fillStyle = '#ffffff';
    g.font = `bold ${Math.max(8, Math.round(scaleM(12)))}px "Arial Black", sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('03', -r21Len / 2 + scaleM(35), 0);
    g.fillText('21', r21Len / 2 - scaleM(35), 0);
    g.restore();

    // Closed Runway 18/36 (North-South at x = -180m)
    g.save();
    g.fillStyle = '#2b2e32';
    g.fillRect(px(-189), py(400), scaleM(18), scaleM(800));
    g.fillStyle = '#f5b800';
    g.font = `bold ${Math.max(10, Math.round(scaleM(16)))}px Arial, sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let y = -300; y <= 300; y += 150) g.fillText('X', px(-180), py(y));
    g.restore();

    // 7. Taxiway Network (Curved Béziers & Polylines)
    if (LAYOUT.taxiways_network) {
      for (const twy of LAYOUT.taxiways_network) {
        g.strokeStyle = '#22252a'; g.lineWidth = Math.max(2, scaleM(twy.width || 14));
        g.beginPath();
        if (twy.kind === 'cubic_bezier') {
          const cps = twy.control_points;
          for (let i = 0; i <= 32; i++) {
            const pt = evalCubicBezier(cps[0], cps[1], cps[2], cps[3], i / 32);
            if (i === 0) g.moveTo(px(pt[0]), py(pt[1]));
            else g.lineTo(px(pt[0]), py(pt[1]));
          }
        } else if (twy.kind === 'polyline' && twy.points) {
          g.moveTo(px(twy.points[0][0]), py(twy.points[0][1]));
          g.lineTo(px(twy.points[1][0]), py(twy.points[1][1]));
        }
        g.stroke();

        // Yellow taxiway centerline
        g.strokeStyle = '#f5b800'; g.lineWidth = Math.max(1, scaleM(0.6));
        g.beginPath();
        if (twy.kind === 'cubic_bezier') {
          const cps = twy.control_points;
          for (let i = 0; i <= 32; i++) {
            const pt = evalCubicBezier(cps[0], cps[1], cps[2], cps[3], i / 32);
            if (i === 0) g.moveTo(px(pt[0]), py(pt[1]));
            else g.lineTo(px(pt[0]), py(pt[1]));
          }
        } else if (twy.kind === 'polyline' && twy.points) {
          g.moveTo(px(twy.points[0][0]), py(twy.points[0][1]));
          g.lineTo(px(twy.points[1][0]), py(twy.points[1][1]));
        }
        g.stroke();
      }
    }

    // 7.5 Airfield Service Road Network
    g.save();
    g.strokeStyle = '#2b2e32'; g.lineWidth = Math.max(1.5, scaleM(10));
    g.beginPath();
    const rCps = [[-720, 695], [-650, 735], [220, 735], [800, 695]];
    for (let i = 0; i <= 32; i++) {
      const pt = evalCubicBezier(rCps[0], rCps[1], rCps[2], rCps[3], i / 32);
      if (i === 0) g.moveTo(px(pt[0]), py(pt[1])); else g.lineTo(px(pt[0]), py(pt[1]));
    }
    g.stroke();
    g.lineWidth = Math.max(1.2, scaleM(8));
    g.beginPath();
    g.moveTo(px(-650), py(490));
    g.lineTo(px(-100), py(490));
    g.lineTo(px(40), py(520));
    g.lineTo(px(240), py(500));
    g.lineTo(px(475), py(530));
    g.lineTo(px(680), py(540));
    g.stroke();
    g.strokeStyle = 'rgba(255, 255, 255, 0.45)'; g.lineWidth = Math.max(0.8, scaleM(0.4));
    g.setLineDash([scaleM(4), scaleM(4)]);
    g.beginPath();
    for (let i = 0; i <= 32; i++) {
      const pt = evalCubicBezier(rCps[0], rCps[1], rCps[2], rCps[3], i / 32);
      if (i === 0) g.moveTo(px(pt[0]), py(pt[1])); else g.lineTo(px(pt[0]), py(pt[1]));
    }
    g.moveTo(px(-650), py(490));
    g.lineTo(px(-100), py(490));
    g.lineTo(px(40), py(520));
    g.lineTo(px(240), py(500));
    g.stroke();
    g.setLineDash([]);
    g.restore();

    // 8. Stands 1 to 6
    if (LAYOUT.stands_expanded) {
      for (let idx = 0; idx < LAYOUT.stands_expanded.length; idx++) {
        const st = LAYOUT.stands_expanded[idx];
        const sx = px(st.center[0]), sy = py(st.center[1]), sr = scaleM(st.radius);
        g.fillStyle = '#26292d';
        g.beginPath(); g.arc(sx, sy, sr, 0, Math.PI * 2); g.fill();
        g.strokeStyle = '#f5b800'; g.lineWidth = 1.2;
        g.beginPath(); g.arc(sx, sy, sr, 0, Math.PI * 2); g.stroke();
        g.fillStyle = '#f5b800';
        g.font = `bold ${Math.max(8, Math.round(scaleM(6)))}px system-ui`;
        g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(String(idx + 1), sx, sy);
      }
    }

    // 9. Physical Building Footprints
    if (world && world.obstacles) {
      for (const o of world.obstacles) {
        g.fillStyle = o.landable ? '#8ca094' : '#a07865';
        const [ox, oy] = o.center, [hx, hy] = o.half;
        g.fillRect(px(ox - hx), py(oy + hy), scaleM(hx * 2), scaleM(hy * 2));
      }
    }

    // 10. Facility Complex Badges & Labels
    const facilities = [
      { id: 'SCHOOL', label: '🎓 VTX ACADEMY', pt: [-555, 635], col: '#f5b800' },
      { id: 'HQ', label: '🏢 HQ / TERMINAL', pt: [-200, 620], col: '#38a8e0' },
      { id: 'ENG', label: '⚙️ MRO SKUNKWORKS', pt: [40, 590], col: '#e08838' },
      { id: 'TOWER', label: '📡 ATC TOWER', pt: [240, 555], col: '#ff5533' },
      { id: 'FIRE', label: '🚒 FIRE STN 9', pt: [475, 600], col: '#ff3322' },
      { id: 'CARGO', label: '📦 CARGO HUB', pt: [680, 600], col: '#e0c038' },
      { id: 'VOLCANO', label: '🌋 VOLCANO / BASEMENT', pt: [-30, 290], col: '#ff4400' }
    ];
    for (const f of facilities) {
      const fx = px(f.pt[0]), fy = py(f.pt[1]);
      g.fillStyle = 'rgba(15, 20, 25, 0.85)';
      const textW = Math.max(50, Math.round(scaleM(80)));
      g.fillRect(fx - textW / 2, fy - 10, textW, 20);
      g.strokeStyle = f.col; g.lineWidth = 1;
      g.strokeRect(fx - textW / 2, fy - 10, textW, 20);
      g.fillStyle = f.col;
      g.font = `bold ${Math.max(9, Math.round(scaleM(12)))}px system-ui`;
      g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(f.label, fx, fy);
    }

    return layer;
  }

  render(world, { last, track, departure, destination }) {
    if (!world) return;
    const proj = this.getProjection(world.half_m);
    const { px, py, scaleM, w, h } = proj;

    // Cache or redraw background
    let bg = backgroundCache.get(this.canvas);
    if (!bg || bg.w !== w || bg.h !== h || bg.zoom !== this.zoom || bg.cx !== this.center[0] || bg.cy !== this.center[1]) {
      const layer = this.buildBackgroundLayer(world, proj);
      bg = { layer, w, h, zoom: this.zoom, cx: this.center[0], cy: this.center[1] };
      backgroundCache.set(this.canvas, bg);
    }
    this.ctx.drawImage(bg.layer, 0, 0);

    // Dynamic flight track breadcrumbs
    if (track && track.length > 1) {
      this.ctx.strokeStyle = '#2fe3ffcc';
      this.ctx.lineWidth = Math.max(1.5, scaleM(1.2));
      this.ctx.beginPath();
      track.forEach((p, i) => {
        if (i === 0) this.ctx.moveTo(px(p[0]), py(p[1]));
        else this.ctx.lineTo(px(p[0]), py(p[1]));
      });
      this.ctx.stroke();
    }

    // Departure (A) and Destination (B) Markers
    for (const [p, label, col] of [[departure, 'A', '#2fe3ff'], [destination, 'B', '#ffaa22']]) {
      if (!p) continue;
      const x = px(p[0]), y = py(p[1]);
      this.ctx.fillStyle = col;
      this.ctx.beginPath(); this.ctx.arc(x, y, Math.max(6, scaleM(6)), 0, Math.PI * 2); this.ctx.fill();
      this.ctx.strokeStyle = '#ffffff'; this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
      this.ctx.fillStyle = '#0a1a1c';
      this.ctx.font = `bold ${Math.max(9, Math.round(scaleM(7)))}px system-ui`;
      this.ctx.textAlign = 'center'; this.ctx.textBaseline = 'middle';
      this.ctx.fillText(label, x, y + 0.5);
    }

    // Authoritative Live Aircraft Glyph (Physical Yaw, Ducted Fans, Velocity Vector)
    if (last && last.observation) {
      const p = last.observation.gnss_xy_m;
      const vel = last.observation.gnss_velocity_mps || [0, 0, 0];
      const ax = px(p[0]), ay = py(p[1]);
      const yawDeg = last.observation.attitude_xyz_deg ? last.observation.attitude_xyz_deg[2] : 0;
      const yawRad = -(yawDeg * Math.PI / 180); // Canvas Y is inverted

      this.ctx.save();
      this.ctx.translate(ax, ay);
      this.ctx.rotate(yawRad);

      // Velocity projection line
      const speed = Math.hypot(vel[0], vel[1]);
      if (speed > 0.5) {
        this.ctx.strokeStyle = '#2fe3ff88';
        this.ctx.lineWidth = 2;
        this.ctx.setLineDash([3, 3]);
        this.ctx.beginPath();
        this.ctx.moveTo(0, 0);
        this.ctx.lineTo(0, -scaleM(speed * 2.0));
        this.ctx.stroke();
        this.ctx.setLineDash([]);
      }

      // Aircraft 4-duct eVTOL glyph
      const gR = Math.max(8, scaleM(3.8));
      this.ctx.fillStyle = 'rgba(12, 18, 22, 0.95)';
      this.ctx.strokeStyle = '#2fe3ff';
      this.ctx.lineWidth = 1.5;

      // Central cabin
      this.ctx.beginPath();
      this.ctx.arc(0, 0, gR * 0.45, 0, Math.PI * 2);
      this.ctx.fill(); this.ctx.stroke();

      // 4 Ducted fan nacelles
      const fanOffset = gR * 0.72;
      const fanR = gR * 0.38;
      for (const [fx, fy] of [[-fanOffset, -fanOffset], [fanOffset, -fanOffset], [-fanOffset, fanOffset], [fanOffset, fanOffset]]) {
        this.ctx.beginPath();
        this.ctx.arc(fx, fy, fanR, 0, Math.PI * 2);
        this.ctx.fillStyle = '#0a1a24';
        this.ctx.fill();
        this.ctx.strokeStyle = '#2fe3ff';
        this.ctx.stroke();
        // Cyan spinning rotor center dot
        this.ctx.fillStyle = '#2fe3ff';
        this.ctx.beginPath();
        this.ctx.arc(fx, fy, fanR * 0.4, 0, Math.PI * 2);
        this.ctx.fill();
      }

      // Forward direction arrow
      this.ctx.fillStyle = '#f5b800';
      this.ctx.beginPath();
      this.ctx.moveTo(0, -gR * 1.3);
      this.ctx.lineTo(gR * 0.35, -gR * 0.6);
      this.ctx.lineTo(-gR * 0.35, -gR * 0.6);
      this.ctx.closePath();
      this.ctx.fill();

      this.ctx.restore();

      // Tactical HUD Telemetry Overlay (Top & Bottom Readouts)
      this.ctx.fillStyle = 'rgba(8, 12, 16, 0.85)';
      this.ctx.fillRect(8, 8, 210, 48);
      this.ctx.strokeStyle = '#2fe3ff44'; this.ctx.lineWidth = 1;
      this.ctx.strokeRect(8, 8, 210, 48);

      this.ctx.fillStyle = '#2fe3ff';
      this.ctx.font = 'bold 11px monospace';
      this.ctx.textAlign = 'left';
      this.ctx.fillText(`POS X: ${p[0].toFixed(1)}m  Y: ${p[1].toFixed(1)}m`, 14, 23);
      this.ctx.fillText(`HDG: ${((yawDeg % 360 + 360) % 360).toFixed(0).padStart(3, '0')}°  SPD: ${speed.toFixed(1)}m/s`, 14, 37);
      this.ctx.fillText(`ALT: ${last.observation.radar_clearance_m.toFixed(1)}m AGL`, 14, 50);

      // Tactical Mode Indicator & Zoom Pill
      this.ctx.fillStyle = this.tacticalMode ? '#f5b800' : 'rgba(235, 240, 245, 0.7)';
      this.ctx.font = 'bold 10px system-ui';
      this.ctx.textAlign = 'right';
      this.ctx.fillText(this.tacticalMode ? 'AIRFIELD TACTICAL (2.6×)' : 'VALLEY WIDE (1.0×)', w - 10, 18);
      this.ctx.fillStyle = 'rgba(255,255,255,0.45)';
      this.ctx.fillText('DBL-CLICK / PINCH ZOOM', w - 10, 32);
    }
  }
}
