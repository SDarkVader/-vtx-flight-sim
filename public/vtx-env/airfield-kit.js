// Fixed airfield architecture dressed onto the physical obstacle boxes of world.py (visual only; no colliders change).
// First pieces: the Vader's Taxis HQ hangar (pitched roof, roof lights, door portal) and the control tower's glazed
// dome cab, plus apron floodlight masts. Interactive gameplay objects are deliberately not part of this module.
import * as THREE from 'three';

const GOLD = '#f5b800';
const ZUP = new THREE.Vector3(0, 0, 1), QX = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2);
function canvasTex(w, h, draw, repeat) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...repeat); }
  return t;
}
// standing-seam steel roof sheet: dark charcoal with fine seams and slight weathering
const seamTex = (rx, ry) => canvasTex(256, 256, (g, w, h) => {
  g.fillStyle = '#2b3036'; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(${i % 2 ? 255 : 0},${i % 2 ? 255 : 0},${i % 2 ? 255 : 0},0.025)`; g.fillRect((i * 97) % w, (i * 53) % h, 18, 2); }
  for (let x = 0; x < w; x += 32) { g.fillStyle = '#15181b'; g.fillRect(x, 0, 3, h); g.fillStyle = '#4a525a'; g.fillRect(x + 3, 0, 2, h); }
}, [rx, ry]);
const crestTex = () => canvasTex(1024, 256, (g, w, h) => {
  g.fillStyle = '#0e1012'; g.fillRect(0, 0, w, h);
  g.strokeStyle = GOLD; g.lineWidth = 10; for (let i = 0; i < 3; i++) { g.beginPath(); g.moveTo(250 + i * 34, 196); g.lineTo(300 + i * 34, 60); g.stroke(); }   // VTX speed stripes
  g.fillStyle = '#f4f1e6'; g.font = '900 150px system-ui, sans-serif'; g.textBaseline = 'middle'; g.fillText('VTX', 400, 134);
  g.fillStyle = GOLD; g.font = '700 30px system-ui, sans-serif'; g.fillText("VADER'S TAXIS  ·  AVIATION DIVISION", 404, 224);
});

function gableRoof({ x0, x1, y0, y1, z, rise, over = 0.9 }) {
  // ridge runs north-south so the gable end faces the apron; eaves overhang the side walls
  const xa = x0 - over, xb = x1 + over, ya = y0 - over, yb = y1 + over, xm = (x0 + x1) / 2, zr = z + rise;
  const slope = new THREE.BufferGeometry();
  slope.setAttribute('position', new THREE.Float32BufferAttribute([xa, ya, z, xa, yb, z, xm, yb, zr, xm, ya, zr, xb, ya, z, xb, yb, z, xm, yb, zr, xm, ya, zr], 3));
  slope.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1], 2));
  slope.setIndex([0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7]); slope.computeVertexNormals();
  const gable = new THREE.BufferGeometry();
  gable.setAttribute('position', new THREE.Float32BufferAttribute([x0, y0, z, x1, y0, z, xm, y0, zr, x1, y1, z, x0, y1, z, xm, y1, zr], 3));
  gable.setIndex([0, 1, 2, 3, 4, 5]); gable.computeVertexNormals();
  return { slope, gable, span: Math.hypot(xm - xa, rise), xm, zr, xa, xb, ya, yb };
}

export function buildAirfieldKit(scene, world, { quality = {} } = {}) {
  const group = new THREE.Group(); group.name = 'vtx-airfield-kit';
  const nightGlow = [], spots = [], updaters = [];
  const steel = (color, rough = 0.55, metal = 0.6) => new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal });
  const glow = (color, day, night) => { const m = new THREE.MeshStandardMaterial({ color: '#111', emissive: color, emissiveIntensity: day }); nightGlow.push([m, day, night]); return m; };
  const add = (geo, mat, x, y, z, cast = true) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = cast; m.receiveShadow = true; group.add(m); return m; };
  const box = (sx, sy, sz, mat, x, y, z) => add(new THREE.BoxGeometry(sx, sy, sz), mat, x, y, z);

  // ---------------- HQ hangar: pitched standing-seam roof, roof lights, ridge, eaves, door portal
  const h = world.obstacles.find((o) => o.id === 'hangar');
  if (h) {
    const [cx, cy, cz] = h.center, [hx, hy, hz] = h.half, x0 = cx - hx, x1 = cx + hx, y0 = cy - hy, y1 = cy + hy, top = cz + hz;
    const rise = 3.4, R = gableRoof({ x0, x1, y0, y1, z: top + 0.05, rise });
    const roofMat = new THREE.MeshStandardMaterial({ map: seamTex(34, 5), roughness: 0.42, metalness: 0.7, side: THREE.DoubleSide });
    const roof = new THREE.Mesh(R.slope, roofMat); roof.castShadow = roof.receiveShadow = true; group.add(roof);
    const gables = new THREE.Mesh(R.gable, new THREE.MeshStandardMaterial({ color: '#15181a', roughness: 0.7, metalness: 0.3, side: THREE.DoubleSide })); gables.castShadow = true; group.add(gables);
    // translucent roof-light strips down each slope (they glow from the lit interior at night)
    const lightMat = glow('#ffe2a8', 0.12, 2.2); lightMat.color.set('#cfd6d8'); lightMat.roughness = 0.25;
    const pitch = Math.atan2(rise, R.xm - R.xa);
    for (const sgn of [-1, 1]) for (let i = 0; i < 5; i++) {
      const strip = add(new THREE.BoxGeometry(R.span * 0.6, 2.0, 0.08), lightMat, R.xm + sgn * (R.xm - R.xa) * 0.52, y0 + 4 + i * (2 * hy - 8) / 4, top + rise * 0.48 + 0.12, false);
      strip.rotation.y = sgn * pitch;
    }
    box(0.7, R.yb - R.ya, 0.28, steel('#3b4046'), R.xm, cy, R.zr + 0.1);                                  // ridge cap
    for (const x of [R.xa, R.xb]) box(0.22, R.yb - R.ya, 0.34, steel(GOLD, 0.4, 0.5), x, cy, top + 0.02);   // gold eaves gutters
    // VTX crest in the gable facing the apron, with a gold verge trim along both rakes
    const crest = add(new THREE.PlaneGeometry(11, 2.75), new THREE.MeshStandardMaterial({ map: crestTex(), emissiveMap: crestTex(), emissive: '#ffffff', emissiveIntensity: 0.3, roughness: 0.5 }), cx, y0 - 0.06, top + 1.45, false);
    crest.rotation.x = Math.PI / 2; nightGlow.push([crest.material, 0.3, 1.5]);
    for (const sgn of [-1, 1]) { const v = box(R.span + 0.4, 0.3, 0.3, steel(GOLD, 0.4, 0.5), R.xm + sgn * (R.xm - R.xa) / 2, R.ya, top + rise / 2 + 0.1); v.rotation.y = sgn * pitch; }
    // door portal on the apron face: steel columns with hazard-banded feet and a door track set into the apron
    const yf = y0 - 0.35, colMat = steel('#1b1e21', 0.6, 0.5);
    for (const x of [x0 + 5.2, x1 - 5.2]) {
      box(1.0, 0.7, 12.4, colMat, x, yf, 6.2);
      for (let k = 0; k < 6; k++) box(1.04, 0.74, 0.5, steel(k % 2 ? '#111' : GOLD, 0.5, 0.3), x, yf, 0.3 + k * 0.5);
    }
    box(2 * hx - 9.3, 1.1, 0.06, steel('#3a3f44', 0.35, 0.8), cx, yf - 0.4, 0.03);
  }

  // ---------------- control tower: brass-ribbed glass dome cab with a warm interior
  const t = world.obstacles.find((o) => o.id === 'tower');
  if (t) {
    const [cx, cy, cz] = t.center, top = cz + t.half[2], r = 8.4, brass = steel('#b98a2e', 0.32, 0.9);
    add(new THREE.CylinderGeometry(r + 0.9, r + 0.5, 1.0, 40).rotateX(Math.PI / 2), steel('#2a2d30', 0.6, 0.6), cx, cy, top + 1.1);   // gallery deck
    add(new THREE.TorusGeometry(r + 0.95, 0.09, 8, 48), brass, cx, cy, top + 2.7, false);                                              // gallery rail
    for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2; add(new THREE.CylinderGeometry(0.05, 0.05, 1.1, 6).rotateX(Math.PI / 2), brass, cx + Math.cos(a) * (r + 0.95), cy + Math.sin(a) * (r + 0.95), top + 2.15, false); }
    const glass = new THREE.MeshPhysicalMaterial({ color: '#9fc4d6', roughness: 0.05, metalness: 0.2, transparent: true, opacity: 0.32, envMapIntensity: 2.2, side: THREE.DoubleSide, depthWrite: false });
    const dome = add(new THREE.SphereGeometry(r, 40, 20, 0, Math.PI * 2, 0, Math.PI / 2).rotateX(Math.PI / 2), glass, cx, cy, top + 1.6, false); dome.renderOrder = 5;
    for (let i = 0; i < 12; i++) {   // meridian ribs
      const rib = add(new THREE.TorusGeometry(r + 0.03, 0.11, 6, 24, Math.PI / 2), brass, cx, cy, top + 1.6, false);
      rib.quaternion.setFromAxisAngle(ZUP, i / 12 * Math.PI * 2).multiply(QX);   // stand the arc up, then swing it round the dome
    }
    for (const f of [0.35, 0.7]) { const rr = r * Math.cos(Math.asin(f)); add(new THREE.TorusGeometry(rr + 0.03, 0.08, 6, 48), brass, cx, cy, top + 1.6 + r * f, false); }   // parallels
    add(new THREE.CylinderGeometry(0.5, 0.9, 1.2, 12).rotateX(Math.PI / 2), brass, cx, cy, top + 1.6 + r + 0.4);                         // crown
    add(new THREE.CylinderGeometry(0.05, 0.08, 6, 6).rotateX(Math.PI / 2), steel('#c9cdd0'), cx, cy, top + 1.6 + r + 3.8, false);         // mast
    add(new THREE.CircleGeometry(r - 0.4, 40), glow('#ffb45a', 0.5, 3.2), cx, cy, top + 1.7, false);                                    // warm floor glow seen through the glass
    add(new THREE.CylinderGeometry(1.6, 1.9, 1.5, 20).rotateX(Math.PI / 2), steel('#3a2a1c', 0.5, 0.3), cx, cy, top + 2.4, false);        // central desk ring
    const hx = t.half[0] + 0.72, hy = t.half[1] + 0.72;
    for (let i = 0; i < 6; i++) for (const [mx, my] of [[-hx + i * 2 * hx / 5, -hy], [-hx + i * 2 * hx / 5, hy], [-hx, -hy + i * 2 * hy / 5], [hx, -hy + i * 2 * hy / 5]]) box(0.16, 0.16, 6.5, brass, cx + mx, cy + my, top - 3.25);
    const lamp = new THREE.PointLight('#ffb45a', 0, 60, 1.6); lamp.position.set(cx, cy, top + 5); group.add(lamp); spots.push([lamp, 900]);
  }

  // ---------------- floodlight masts at the hangar's front corners, clear of the apron and runway (lit at night on the app tier)
  if (h) {
    const [cx, cy] = h.center, y0 = cy - h.half[1], mastMat = steel('#8d9296', 0.5, 0.7), headMat = glow('#fff1d0', 0.2, 3.5);
    const n = Math.min(2, quality.floodlights ?? 0);
    [-1, 1].forEach((sgn, i) => {
      const x = cx + sgn * (h.half[0] + 3.5), y = y0 + 1.5;
      add(new THREE.CylinderGeometry(0.16, 0.26, 21, 10).rotateX(Math.PI / 2), mastMat, x, y, 10.5);
      box(3.2, 0.5, 0.5, mastMat, x, y, 21.1);
      for (const k of [-1.1, 0, 1.1]) { const hd = box(0.8, 0.5, 0.55, headMat, x + k, y - 0.35, 20.6); hd.rotation.x = 0.6; }
      if (i < n) {
        const s = new THREE.SpotLight('#ffe6b8', 0, 110, 0.8, 0.55, 1.5); s.position.set(x, y - 0.5, 20.5); s.target.position.set(x - sgn * 12, y0 - 9, 0);
        group.add(s, s.target); spots.push([s, 1500]);
      }
    });
    // rain-slick sheen on the apron strip between the doors and the runway edge (night only)
    const wet = add(new THREE.PlaneGeometry(2 * h.half[0] + 16, 12.5), new THREE.MeshStandardMaterial({ color: '#07090c', roughness: 0.32, metalness: 0.0, transparent: true, opacity: 0, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4 }), cx, y0 - 6.5, 0.06, false);
    wet.renderOrder = 3; wet.visible = false; updaters.push((night) => { wet.visible = night; wet.material.opacity = night ? 0.35 : 0; });
  }

  scene.add(group);
  return {
    group,
    setNight(on) {
      for (const [m, d, n] of nightGlow) m.emissiveIntensity = on ? n : d;
      for (const [l, power] of spots) l.intensity = on ? power : 0;
      for (const u of updaters) u(on);
    },
  };
}
