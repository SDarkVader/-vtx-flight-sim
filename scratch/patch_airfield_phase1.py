with open('public/vtx-env/airfield.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the single runway with the full dual crossing runway system + closed cross runway
old_runway_block = """  // ---- runway: asphalt, shoulders, threshold bars, centreline, numbers, touchdown zones
  const rw = runway.x1 - runway.x0, rh = runway.width + 8;
  decal(group, rw, rh, (runway.x0 + runway.x1) / 2, runway.yc, surface(rw, rh, ppm * .9, (g, w, h) => {
    patternFill(g, asph.map, w, h, 8);
    g.fillStyle = 'rgba(80,82,80,.35)'; g.fillRect(0, 0, w, 4); g.fillRect(0, h - 4, w, 4);               // shoulders
    const cy = h / 2; g.fillStyle = '#e9e7da';
    g.fillRect(0, 4.2, w, .35); g.fillRect(0, h - 4.55, w, .35);                                        // edge lines
    for (let x = 14; x < w - 14; x += 30) g.fillRect(x, cy - .2, 14, .4);                                   // centreline
    for (const dir of [1, -1]) {                                                                         // thresholds + touchdown bars
      const x0 = dir > 0 ? 2.5 : w - 2.5;
      for (let i = 0; i < 8; i++) g.fillRect(dir > 0 ? x0 : x0 - 14, cy - 11.5 + i * 3, 14, 1.5);
      for (const sgn of [-1, 1]) { g.fillRect(dir > 0 ? x0 + 38 : x0 - 38 - 7, cy + sgn * 5 - (sgn > 0 ? 0 : 1.2), 7, 1.2); g.fillRect(dir > 0 ? x0 + 56 : x0 - 56 - 5, cy + sgn * 5 - (sgn > 0 ? 0 : 1.2), 5, 1.2); }
    }
    // heading numbers read from the approach end: the top of the glyphs points down the runway
    for (const [label, px, rot] of [['09', 28, Math.PI / 2], ['27', w - 28, -Math.PI / 2]]) { g.save(); g.translate(px, cy); g.rotate(rot); F.text(g, null, label, 0, 4, 11, { color: '#e9e7da', align: 'center', glow: false }); g.restore(); }
    // rubber at touchdown
    const r = rng(5); for (const x0 of [34, w - 34]) for (let i = 0; i < 14; i++) { g.fillStyle = 'rgba(18,18,18,.25)'; g.fillRect(x0 + (r() - .5) * 18, cy + (r() - .5) * 16, 4 + r() * 8, .5 + r() * 1.2); }
    F.text(g, null, 'VTX', w / 2, cy + 3.2, 8, { color: 'rgba(245,184,0,.82)', align: 'center', glow: false });
  }, { roughness: .4, env: 1.4 }));"""

new_runway_block = """  // =========================================================================
  // DUAL CROSSING RUNWAYS (Gloucestershire EGBJ Operational Topology)
  // =========================================================================

  // ---- 1. Primary Runway 08/26: 1,432m length x 30m width (heading 090°, X-aligned)
  const rwy0826_len = 1432, rwy0826_w = 30 + 8; // 30m runway + 4m shoulders on each side
  decal(group, rwy0826_len, rwy0826_w, 0, 0, surface(rwy0826_len, rwy0826_w, 2.5, (g, w, h) => {
    patternFill(g, asph.map, w, h, 8);
    // Shoulders
    g.fillStyle = 'rgba(60,62,65,.4)'; g.fillRect(0, 0, w, 4); g.fillRect(0, h - 4, w, 4);
    const cy = h / 2; g.fillStyle = '#f0eee2';
    // Solid runway edge lines
    g.fillRect(0, 4.2, w, .45); g.fillRect(0, h - 4.65, w, .45);
    // Centreline dashes (14m dash, 16m gap)
    for (let x = 20; x < w - 20; x += 30) g.fillRect(x, cy - .25, 14, .5);
    // Threshold piano keys (8 stripes per end, 14m x 1.5m)
    for (const dir of [1, -1]) {
      const x0 = dir > 0 ? 3 : w - 3;
      for (let i = 0; i < 8; i++) g.fillRect(dir > 0 ? x0 : x0 - 14, cy - 11.5 + i * 3, 14, 1.5);
      // Touchdown aiming point markings (300m from thresholds)
      const aimX = dir > 0 ? 300 : w - 300 - 45;
      for (const sgn of [-1, 1]) g.fillRect(aimX, cy + sgn * 6 - (sgn > 0 ? 0 : 3.0), 45, 3.0);
    }
    // Heading designators: '08' at west threshold, '26' at east threshold
    for (const [label, px, rot] of [['08', 36, Math.PI / 2], ['26', w - 36, -Math.PI / 2]]) {
      g.save(); g.translate(px, cy); g.rotate(rot);
      F.text(g, null, label, 0, 4.5, 12, { color: '#f0eee2', align: 'center', glow: false });
      g.restore();
    }
    // Touchdown tyre rubber burnouts
    const r = rng(108);
    for (const aimX of [300, w - 300]) {
      for (let i = 0; i < 28; i++) {
        g.fillStyle = 'rgba(15,15,16,.28)';
        g.fillRect(aimX + (r() - .5) * 55, cy + (r() - .5) * 14, 8 + r() * 16, .6 + r() * 1.4);
      }
    }
    // VTX Aviation watermark at intersection
    F.text(g, null, 'VTX AVIATION', w / 2, cy + 3.8, 9, { color: 'rgba(245,184,0,.75)', align: 'center', glow: false });
  }, { roughness: .4, env: 1.4 }), { z: Z + .001 });

  // ---- 2. Secondary Crossing Runway 03/21: 980m length x 23m width (heading 055°, crossing at [235, 0])
  const rwy0321_len = 980, rwy0321_w = 23 + 7; // 23m runway + 3.5m shoulders
  const rwy0321_rot = Math.atan2(0.81915204, 0.57357644); // ~0.95993 rad = 55.0 deg
  decal(group, rwy0321_len, rwy0321_w, 235, 0, surface(rwy0321_len, rwy0321_w, 3.2, (g, w, h) => {
    patternFill(g, asph.map, w, h, 8);
    // Shoulders
    g.fillStyle = 'rgba(60,62,65,.4)'; g.fillRect(0, 0, w, 3.5); g.fillRect(0, h - 3.5, w, 3.5);
    const cy = h / 2; g.fillStyle = '#f0eee2';
    // Edge lines
    g.fillRect(0, 3.7, w, .4); g.fillRect(0, h - 4.1, w, .4);
    // Centreline
    for (let x = 18; x < w - 18; x += 30) g.fillRect(x, cy - .22, 14, .45);
    // Threshold piano keys
    for (const dir of [1, -1]) {
      const x0 = dir > 0 ? 3 : w - 3;
      for (let i = 0; i < 6; i++) g.fillRect(dir > 0 ? x0 : x0 - 12, cy - 8.5 + i * 3, 12, 1.4);
      const aimX = dir > 0 ? 220 : w - 220 - 35;
      for (const sgn of [-1, 1]) g.fillRect(aimX, cy + sgn * 5 - (sgn > 0 ? 0 : 2.4), 35, 2.4);
    }
    // Heading numbers: '03' at SW threshold, '21' at NE threshold
    for (const [label, px, rot] of [['03', 32, Math.PI / 2], ['21', w - 32, -Math.PI / 2]]) {
      g.save(); g.translate(px, cy); g.rotate(rot);
      F.text(g, null, label, 0, 4.2, 10.5, { color: '#f0eee2', align: 'center', glow: false });
      g.restore();
    }
    // Touchdown tyre rubber
    const r = rng(321);
    for (const aimX of [220, w - 220]) {
      for (let i = 0; i < 22; i++) {
        g.fillStyle = 'rgba(15,15,16,.25)';
        g.fillRect(aimX + (r() - .5) * 45, cy + (r() - .5) * 12, 6 + r() * 14, .5 + r() * 1.2);
      }
    }
  }, { roughness: .42, env: 1.4 }), { rot: rwy0321_rot, z: Z + .002 });

  // ---- 3. Decommissioned Former Cross Runway 18/36: 800m length x 18m width (CLOSED, yellow X crosses)
  const rwy1836_len = 800, rwy1836_w = 18 + 4;
  decal(group, rwy1836_len, rwy1836_w, -180, 0, surface(rwy1836_len, rwy1836_w, 3.5, (g, w, h) => {
    // Weathered, aged cracked asphalt
    patternFill(g, asph.map, w, h, 8);
    g.fillStyle = 'rgba(70,60,50,.35)'; g.fillRect(0, 0, w, h); // weathered oxidation
    const cy = h / 2;
    // Faded centreline remnants
    g.fillStyle = 'rgba(200,195,180,.25)';
    for (let x = 20; x < w - 20; x += 35) g.fillRect(x, cy - .2, 12, .4);
    // Prominent yellow 'X' closed runway crosses every 140m per ICAO Annex 14
    for (let x = 80; x < w - 60; x += 140) {
      g.save(); g.translate(x, cy);
      g.strokeStyle = '#d49800'; g.lineWidth = 1.6;
      g.beginPath(); g.moveTo(-10, -8); g.lineTo(10, 8); g.moveTo(10, -8); g.lineTo(-10, 8); g.stroke();
      g.restore();
    }
  }, { roughness: .55, env: 1.1 }), { rot: Math.PI / 2, z: Z });"""

assert old_runway_block in text
text = text.replace(old_runway_block, new_runway_block)

# Update flush light fittings for both active runways
old_lights_block = """  // ---- flush light fittings (flat emissive discs; they do not project above the surface)
  const disc = new THREE.CircleGeometry(.22, 10);
  const add = (x, y, col) => lights.push([x, y, col]);
  for (let x = runway.x0 + 2; x <= runway.x1 - 2; x += 15) { add(x, runway.yc - runway.width / 2 - .2, '#fff3d0'); add(x, runway.yc + runway.width / 2 + .2, '#fff3d0'); }
  for (let y = -15; y <= 15; y += 3) { add(runway.x0 + .6, runway.yc + y, '#35e060'); add(runway.x1 - .6, runway.yc + y, '#ff3a2a'); }
  for (const t of taxiways) for (let y = t.y0 + 1; y <= t.y1 - 1; y += 7) { add(t.x - t.width / 2 + .3, y, '#3d6cff'); add(t.x + t.width / 2 - .3, y, '#3d6cff'); }
  for (let x = apron.x0 + 4; x <= apron.x1 - 4; x += 10) add(x, apron.y0 + .8, '#3d6cff');"""

new_lights_block = """  // ---- flush light fittings (flat emissive discs; they do not project above the surface)
  const disc = new THREE.CircleGeometry(.22, 10);
  const add = (x, y, col) => lights.push([x, y, col]);

  // Runway 08/26 Edge Lights: white along runway, amber on last 300m of each end
  for (let x = -710; x <= 710; x += 25) {
    const isAmber = Math.abs(x) > 410;
    const col = isAmber ? '#ffb822' : '#fff3d0';
    add(x, -15.4, col); add(x, 15.4, col);
  }
  // Runway 08/26 Threshold Lights (Green entrance / Red end)
  for (let y = -14; y <= 14; y += 3.5) {
    add(-715, y, '#35e060'); // 08 threshold green
    add(715, y, '#ff3a2a');  // 26 end red
    add(-716, y, '#ff3a2a'); // 08 end red (from reverse)
    add(714, y, '#35e060');  // 26 threshold green (from reverse)
  }

  // Runway 03/21 Edge Lights along rotated axis
  const cos21 = Math.cos(rwy0321_rot), sin21 = Math.sin(rwy0321_rot);
  for (let s = -480; s <= 480; s += 25) {
    const isAmber = Math.abs(s) > 280;
    const col = isAmber ? '#ffb822' : '#fff3d0';
    for (const offset of [-11.8, 11.8]) {
      const lx = 235 + s * cos21 - offset * sin21;
      const ly = s * sin21 + offset * cos21;
      add(lx, ly, col);
    }
  }
  // Runway 03/21 Threshold Green / Red
  for (const sgn of [-1, 1]) {
    const s = sgn * 485;
    for (let offset = -10; offset <= 10; offset += 3.2) {
      const lx = 235 + s * cos21 - offset * sin21;
      const ly = s * sin21 + offset * cos21;
      add(lx, ly, sgn < 0 ? '#35e060' : '#ff3a2a');
    }
  }

  // Taxiway edge lights (blue) & apron edge lights
  for (const t of taxiways) for (let y = t.y0 + 1; y <= t.y1 - 1; y += 7) { add(t.x - t.width / 2 + .3, y, '#3d6cff'); add(t.x + t.width / 2 - .3, y, '#3d6cff'); }
  for (let x = apron.x0 + 4; x <= apron.x1 - 4; x += 10) add(x, apron.y0 + .8, '#3d6cff');

  // PAPI (Precision Approach Path Indicator) 4-box arrays (white/red units)
  const papiBox = (px, py, ang) => {
    const bg = new THREE.Group(); bg.position.set(px, py, Z + 0.1);
    bg.rotation.z = ang;
    for (let b = 0; b < 4; b++) {
      const bx = (b - 1.5) * 2.2;
      const housing = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.6, 0.45), new THREE.MeshStandardMaterial({ color: '#f5b800', roughness: 0.5 }));
      housing.position.set(bx, 0, 0.22); bg.add(housing);
      const lamp = new THREE.Mesh(new THREE.CircleGeometry(0.18, 8), new THREE.MeshBasicMaterial({ color: b < 2 ? '#ffffff' : '#ff2211' }));
      lamp.position.set(bx, -0.31, 0.22); lamp.rotateX(Math.PI / 2); bg.add(lamp);
    }
    group.add(bg);
  };
  papiBox(-416, -24, 0); // RWY 08 PAPI
  papiBox(416, 24, Math.PI); // RWY 26 PAPI"""

assert old_lights_block in text
text = text.replace(old_lights_block, new_lights_block)

with open('public/vtx-env/airfield.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("airfield.js successfully upgraded to Phase 1 dual crossing runways!")
