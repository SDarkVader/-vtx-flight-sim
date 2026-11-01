// The Volcanic Above-Ground Mountain housing the Subterranean "Vader's Taxi's Basement"
// The volcano is a towering mountain on the terrain, but inside is a fully enclosed
// underground cavernous headquarters: an enclosed subterranean subway flight chamber
// with steampunk signage, roaring molten lava falls, Victorian cast-iron and glass vault arches,
// swimming sky-whale, blooming cherry blossom tree, subway station platform (地下鉄 Platform 3),
// and hanging robot masks with fiery glowing eyes.

import * as THREE from 'three';
import {
  lavaTexture,
  volcanoBasaltTexture,
  basementSignTexture,
  subwayStationSignTexture,
  cherryBlossomTexture,
  robotMaskTexture,
  rng
} from './textures.js';

export function buildVolcanoBasement(scene, world) {
  const group = new THREE.Group();
  group.name = 'vtx-volcano-basement';

  // Position: North of the airfield on the ascending ridge (in full view from Stand 1 and runway)
  const CX = -30, CY = 350, BASE_Z = 12;
  group.position.set(CX, CY, BASE_Z);

  const updaters = [];

  // =========================================================================
  // 1. Exterior Volcanic Mountain (Enclosed peak, rugged basalt crags & glowing fissures)
  // =========================================================================
  const basaltMat = new THREE.MeshStandardMaterial({
    map: volcanoBasaltTexture(),
    roughness: 0.9,
    metalness: 0.15,
  });
  basaltMat.map.repeat.set(4, 3);

  // Outer mountain geometry: a massive volcanic mountain cone rising to a craggy closed dome peak
  const mountainBaseR = 88, mountainPeakR = 14, mountainH = 64;
  const mountainGeom = new THREE.CylinderGeometry(mountainPeakR, mountainBaseR, mountainH, 48, 16, false);
  mountainGeom.rotateX(Math.PI / 2);
  mountainGeom.translate(0, 0, mountainH / 2);

  // Deform mountain surface into crags and carve out the South entrance tunnel portal
  const mPos = mountainGeom.attributes.position;
  const rGen = rng(337);
  for (let i = 0; i < mPos.count; i++) {
    let x = mPos.getX(i), y = mPos.getY(i), z = mPos.getZ(i);
    const angle = Math.atan2(y, x);
    const dist2D = Math.hypot(x, y);

    // Carve out tunnel mouth portal on South slope (angle ~ -Math.PI / 2, y < -40)
    const isSouthTunnel = Math.abs(angle - (-Math.PI / 2)) < 0.28 && z < 22;
    if (isSouthTunnel) {
      const arch = Math.cos((angle - (-Math.PI / 2)) / 0.28 * Math.PI / 2);
      if (z < 18 * arch) {
        // Open the tunnel entrance portal
        mPos.setZ(i, Math.max(z, 18 * arch));
      }
    }

    // Basalt ridge crags and jagged mountain facets
    const crag = (rGen() - 0.5) * 5.2;
    mPos.setXYZ(i, x + Math.cos(angle) * crag, y + Math.sin(angle) * crag, mPos.getZ(i));
  }
  mountainGeom.computeVertexNormals();

  const outerMountain = new THREE.Mesh(mountainGeom, basaltMat);
  outerMountain.castShadow = true;
  outerMountain.receiveShadow = true;
  group.add(outerMountain);

  // Mountain peak craggy dome cap (completely closing the volcano on top)
  const peakCapGeom = new THREE.ConeGeometry(mountainPeakR + 2, 8, 24);
  peakCapGeom.rotateX(Math.PI / 2);
  peakCapGeom.translate(0, 0, mountainH + 4);
  const peakCap = new THREE.Mesh(peakCapGeom, basaltMat);
  peakCap.castShadow = true;
  group.add(peakCap);

  // Glowing lava fissure running down the exterior mountain ridge
  const fissureMat = new THREE.MeshStandardMaterial({
    color: '#ff3300',
    emissive: '#ff5500',
    emissiveIntensity: 3.5,
    roughness: 0.2,
  });
  const extFissureGeom = new THREE.BoxGeometry(1.6, 52, 0.4);
  extFissureGeom.rotateZ(Math.PI / 6);
  extFissureGeom.translate(32, 28, 30);
  group.add(new THREE.Mesh(extFissureGeom, fissureMat));

  // =========================================================================
  // 2. Industrial Tunnel Entrance Portal (Leading into the Underground Cavern)
  // =========================================================================
  const portalGroup = new THREE.Group();
  portalGroup.position.set(0, -62, 0);

  const ironMat = new THREE.MeshStandardMaterial({
    color: '#24282c',
    metalness: 0.8,
    roughness: 0.4,
  });

  // Reinforced tunnel portal frame
  const portalW = 24, portalH = 18, portalD = 4;
  const frameLeft = new THREE.Mesh(new THREE.BoxGeometry(2.4, portalD, portalH), ironMat);
  frameLeft.position.set(-portalW / 2 + 1.2, 0, portalH / 2);
  portalGroup.add(frameLeft);

  const frameRight = new THREE.Mesh(new THREE.BoxGeometry(2.4, portalD, portalH), ironMat);
  frameRight.position.set(portalW / 2 - 1.2, 0, portalH / 2);
  portalGroup.add(frameRight);

  const frameArch = new THREE.Mesh(new THREE.BoxGeometry(portalW, portalD, 2.5), ironMat);
  frameArch.position.set(0, 0, portalH - 1.25);
  portalGroup.add(frameArch);

  // Entrance Hazard Striping Header & Sign
  const portalCanvas = document.createElement('canvas');
  portalCanvas.width = 1024; portalCanvas.height = 256;
  const pc = portalCanvas.getContext('2d');
  pc.fillStyle = '#111315'; pc.fillRect(0, 0, 1024, 256);
  // Yellow/black diagonal hazard stripes
  pc.fillStyle = '#f5b800'; pc.fillRect(0, 0, 1024, 40); pc.fillRect(0, 216, 1024, 40);
  pc.fillStyle = '#000000';
  for (let x = -40; x < 1060; x += 60) {
    pc.beginPath(); pc.moveTo(x, 0); pc.lineTo(x + 30, 0); pc.lineTo(x + 10, 40); pc.lineTo(x - 20, 40); pc.fill();
    pc.beginPath(); pc.moveTo(x, 216); pc.lineTo(x + 30, 216); pc.lineTo(x + 10, 256); pc.lineTo(x - 20, 256); pc.fill();
  }
  // Title
  pc.font = 'bold 58px "Arial Black", Impact, sans-serif';
  pc.fillStyle = '#f5b800'; pc.textAlign = 'center';
  pc.fillText("VADER'S TAXIS · VOLCANO BASEMENT", 512, 115);
  pc.font = 'bold 28px monospace';
  pc.fillStyle = '#ffffff';
  pc.fillText("SUBTERRANEAN FLIGHT FACILITY · CLEARANCE 16M", 512, 168);
  pc.font = 'bold 20px monospace';
  pc.fillStyle = '#ff4422';
  pc.fillText("CAUTION: ACTIVE GEOTHERMAL DRAFT & LEVIATHAN CROSSING", 512, 202);

  const portalSignTex = new THREE.CanvasTexture(portalCanvas);
  const portalSignMat = new THREE.MeshStandardMaterial({
    map: portalSignTex,
    emissiveMap: portalSignTex,
    emissive: new THREE.Color('#ffffff'),
    emissiveIntensity: 0.9,
    roughness: 0.3,
  });
  const portalSignMesh = new THREE.Mesh(new THREE.PlaneGeometry(portalW - 2, 4.5), portalSignMat);
  portalSignMesh.position.set(0, -portalD / 2 - 0.05, portalH - 2.25);
  portalGroup.add(portalSignMesh);

  // Portal Entrance Sodium Floodlights
  for (const lx of [-portalW / 2 + 2, portalW / 2 - 2]) {
    const pLamp = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.4, 0.4), new THREE.MeshStandardMaterial({ color: '#111', emissive: '#ffd28a', emissiveIntensity: 4 }));
    pLamp.position.set(lx, -portalD / 2 - 0.2, portalH - 0.5);
    portalGroup.add(pLamp);
  }
  const portalLight = new THREE.PointLight('#ffd28a', 4.5, 45, 1.2);
  portalLight.position.set(0, -portalD - 2, portalH / 2);
  portalGroup.add(portalLight);

  // Rock-cut Entrance Tunnel Throat connecting outer portal to inner cavern
  const tunnelL = 36, tunnelW = 22, tunnelH = 17;
  const tunnelGeom = new THREE.BoxGeometry(tunnelW, tunnelL, tunnelH);
  // Invert normals for interior tunnel walls
  const tunnelMat = new THREE.MeshStandardMaterial({
    map: volcanoBasaltTexture(),
    roughness: 0.9,
    side: THREE.BackSide,
  });
  const tunnel = new THREE.Mesh(tunnelGeom, tunnelMat);
  tunnel.position.set(0, -42, tunnelH / 2);
  portalGroup.add(tunnel);

  // Tunnel Floor with yellow centerline guidance marking
  const tFloorCanvas = document.createElement('canvas');
  tFloorCanvas.width = 256; tFloorCanvas.height = 512;
  const tfc = tFloorCanvas.getContext('2d');
  tfc.fillStyle = '#222528'; tfc.fillRect(0, 0, 256, 512);
  tfc.fillStyle = '#f5b800';
  for (let y = 20; y < 512; y += 60) tfc.fillRect(124, y, 8, 35);
  const tunnelFloor = new THREE.Mesh(
    new THREE.PlaneGeometry(tunnelW, tunnelL),
    new THREE.MeshStandardMaterial({ map: new THREE.CanvasTexture(tFloorCanvas), roughness: 0.6 })
  );
  tunnelFloor.position.set(0, -42, 0.2);
  portalGroup.add(tunnelFloor);

  group.add(portalGroup);

  // =========================================================================
  // 3. The Enclosed Underground Cavern (Vaulted Rock Ceiling, No Sky Overhead!)
  // =========================================================================
  // Cavern Dimensions: 92m wide, 96m long, vaulting up to 50m height
  const cavernW = 90, cavernL = 94, cavernVaultH = 50;

  // Inverted rocky cavern ceiling dome (completely encloses the underground chamber)
  const cavernVaultGeom = new THREE.SphereGeometry(cavernW * 0.55, 32, 24, 0, Math.PI * 2, 0, Math.PI * 0.48);
  cavernVaultGeom.scale(1.0, 1.05, 0.95);
  cavernVaultGeom.rotateX(Math.PI);
  cavernVaultGeom.translate(0, 6, cavernVaultH);

  const cavernMat = new THREE.MeshStandardMaterial({
    map: volcanoBasaltTexture(),
    roughness: 0.92,
    metalness: 0.1,
    side: THREE.FrontSide, // Since geometry was scaled/inverted to face inward
  });
  cavernMat.map.repeat.set(6, 4);

  const cavernCeiling = new THREE.Mesh(cavernVaultGeom, cavernMat);
  cavernCeiling.receiveShadow = true;
  group.add(cavernCeiling);

  // Cavern basalt floor
  const cavernFloor = new THREE.Mesh(
    new THREE.CircleGeometry(cavernW * 0.52, 40),
    new THREE.MeshStandardMaterial({ map: volcanoBasaltTexture(), roughness: 0.85 })
  );
  cavernFloor.position.set(0, 6, 0.4);
  cavernFloor.receiveShadow = true;
  group.add(cavernFloor);

  // =========================================================================
  // 4. Molten Lava Waterfall & Boiling Magma Pool (Inside the Underground Cavern)
  // =========================================================================
  const lavaTex = lavaTexture();
  const lavaEmissiveTex = lavaTexture();
  const lavaMat = new THREE.MeshStandardMaterial({
    map: lavaTex,
    emissiveMap: lavaEmissiveTex,
    emissive: new THREE.Color('#ff4800'),
    emissiveIntensity: 3.2,
    roughness: 0.35,
    metalness: 0.2,
  });
  lavaTex.repeat.set(2, 4);
  lavaEmissiveTex.repeat.set(2, 4);

  // Vertical molten lava cascade pouring down the underground basalt back wall from an upper fissure
  const fallW = 34, fallH = 46;
  const fallGeom = new THREE.PlaneGeometry(fallW, fallH, 20, 20);
  fallGeom.translate(0, 0, fallH / 2 + 1);
  const lavaFall = new THREE.Mesh(fallGeom, lavaMat);
  lavaFall.position.set(0, 42, 0);
  lavaFall.rotation.y = Math.PI; // Face South into the cavern
  group.add(lavaFall);

  // Boiling Magma Pool at the foot of the underground waterfall
  const poolGeom = new THREE.PlaneGeometry(42, 24, 16, 16);
  const pool = new THREE.Mesh(poolGeom, lavaMat);
  pool.position.set(0, 34, 0.8);
  pool.receiveShadow = true;
  group.add(pool);

  // Powerful volcanic geothermal point light casting fiery orange light through the underground hall
  const lavaLight = new THREE.PointLight('#ff5511', 9.5, 110, 1.1);
  lavaLight.position.set(0, 28, 16);
  group.add(lavaLight);

  // Ambient cavern fill light (deep embers)
  const cavernAmber = new THREE.PointLight('#ff8822', 4.8, 80, 1.3);
  cavernAmber.position.set(0, -10, 28);
  group.add(cavernAmber);

  // Animate lava flow downwards in UV coordinates
  updaters.push((t, dt) => {
    lavaTex.offset.y -= dt * 0.25;
    lavaEmissiveTex.offset.y -= dt * 0.25;
    lavaLight.intensity = 8.8 + Math.sin(t * 4.8) * 1.5 + Math.cos(t * 7.5) * 0.9;
  });

  // =========================================================================
  // 5. Victorian Arched Cast-Iron Vault Ribs (Spanning the Underground Ceiling)
  // =========================================================================
  const vaultIronMat = new THREE.MeshStandardMaterial({
    color: '#1a1e22',
    metalness: 0.85,
    roughness: 0.4,
  });

  // 6 Massive cast-iron structural rib arches spanning the underground cavern
  const ribCount = 6;
  for (let r = 0; r < ribCount; r++) {
    const ry = -28 + r * 14;
    const archRadius = 38;
    const ribGeom = new THREE.TorusGeometry(archRadius, 0.5, 8, 36, Math.PI);
    ribGeom.rotateY(Math.PI / 2);
    ribGeom.translate(0, ry, 0);

    const rib = new THREE.Mesh(ribGeom, vaultIronMat);
    rib.castShadow = true;
    group.add(rib);

    // Cross-struts and lattice girders
    if (r < ribCount - 1) {
      for (let a = 0.25; a < Math.PI; a += 0.4) {
        const strutGeom = new THREE.CylinderGeometry(0.18, 0.18, 14, 6);
        const strut = new THREE.Mesh(strutGeom, vaultIronMat);
        const sx = Math.cos(a) * archRadius;
        const sz = Math.sin(a) * archRadius;
        strut.position.set(sx, ry + 7, sz);
        strut.rotateX(Math.PI / 2);
        group.add(strut);
      }
    }
  }

  // =========================================================================
  // 6. Steampunk "Vader's Taxi's Basement" Sign with Rotating Brass Gears
  // =========================================================================
  const signTex = basementSignTexture();
  const signMat = new THREE.MeshStandardMaterial({
    map: signTex,
    roughness: 0.45,
    metalness: 0.4,
    emissiveMap: signTex,
    emissive: new THREE.Color('#ffffff'),
    emissiveIntensity: 0.75,
  });

  const signW = 28, signH = 14;
  const signMesh = new THREE.Mesh(new THREE.PlaneGeometry(signW, signH), signMat);
  signMesh.position.set(0, 24, 32);
  signMesh.rotation.y = Math.PI; // Face South toward the entrance tunnel
  signMesh.castShadow = true;
  group.add(signMesh);

  // Rotating brass gears mounted on the sign corners
  const gearMat = new THREE.MeshStandardMaterial({
    color: '#d4af37',
    metalness: 0.85,
    roughness: 0.28,
  });

  const gears = [];
  const gearCoords = [
    { x: -12.5, z: 37, r: 2.2, speed: 0.8, teeth: 12 },
    { x: -10.2, z: 39.5, r: 1.4, speed: -1.25, teeth: 8 },
    { x: 12.5, z: 37, r: 2.2, speed: -0.8, teeth: 12 },
    { x: 10.2, z: 39.5, r: 1.4, speed: 1.25, teeth: 8 },
  ];

  for (const gc of gearCoords) {
    const gearGroup = new THREE.Group();
    gearGroup.position.set(gc.x, 23.9, gc.z);
    gearGroup.rotation.y = Math.PI;

    const disc = new THREE.Mesh(new THREE.CylinderGeometry(gc.r, gc.r, 0.25, 16), gearMat);
    disc.rotateX(Math.PI / 2);
    gearGroup.add(disc);

    for (let t = 0; t < gc.teeth; t++) {
      const ta = (t / gc.teeth) * Math.PI * 2;
      const tooth = new THREE.Mesh(new THREE.BoxGeometry(gc.r * 0.28, gc.r * 0.45, 0.22), gearMat);
      tooth.position.set(Math.cos(ta) * gc.r * 1.1, Math.sin(ta) * gc.r * 1.1, 0);
      tooth.rotation.z = ta;
      gearGroup.add(tooth);
    }

    group.add(gearGroup);
    gears.push({ mesh: gearGroup, speed: gc.speed });
  }

  updaters.push((t, dt) => {
    for (const g of gears) g.mesh.rotation.z += g.speed * dt;
  });

  // Heavy suspension chains anchored to the underground cavern vault
  const chainMat = new THREE.MeshStandardMaterial({ color: '#16191c', metalness: 0.9, roughness: 0.4 });
  for (const cx of [-11, 11]) {
    const chain = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 14, 6), chainMat);
    chain.position.set(cx, 24, 41);
    group.add(chain);
  }

  // =========================================================================
  // 7. The Majestic Swimming SKY-WHALE ("Nordeus" / VTX Leviathan)
  // =========================================================================
  const whaleGroup = new THREE.Group();
  whaleGroup.name = 'vtx-sky-whale';

  const whaleSkinMat = new THREE.MeshStandardMaterial({
    color: '#263440',
    roughness: 0.38,
    metalness: 0.18,
  });
  const bellyMat = new THREE.MeshStandardMaterial({
    color: '#d4dde2',
    roughness: 0.48,
  });

  const bodyLen = 22, bodyRad = 4.2;
  const whaleBodyGeom = new THREE.SphereGeometry(bodyRad, 24, 16);
  whaleBodyGeom.scale(1.0, 2.6, 0.9);
  whaleBodyGeom.rotateX(Math.PI / 2);
  const whaleBody = new THREE.Mesh(whaleBodyGeom, whaleSkinMat);
  whaleBody.castShadow = true;
  whaleGroup.add(whaleBody);

  // Underbelly grooves
  const bellyGeom = new THREE.SphereGeometry(bodyRad * 0.98, 20, 12, 0, Math.PI);
  bellyGeom.scale(0.95, 2.2, 0.85);
  bellyGeom.rotateX(Math.PI / 2);
  bellyGeom.translate(0, 0, -0.4);
  whaleGroup.add(new THREE.Mesh(bellyGeom, bellyMat));

  // Dorsal fin
  const dorsalGeom = new THREE.ConeGeometry(1.2, 3.2, 6);
  dorsalGeom.rotateX(Math.PI / 3);
  dorsalGeom.translate(0, -2, bodyRad + 0.6);
  whaleGroup.add(new THREE.Mesh(dorsalGeom, whaleSkinMat));

  // Pectoral flippers (wings that stroke)
  const leftFlipperGroup = new THREE.Group();
  leftFlipperGroup.position.set(bodyRad * 0.8, 3.5, -1.0);
  const flipperGeom = new THREE.BoxGeometry(6.5, 1.8, 0.35);
  flipperGeom.translate(3.25, -0.2, 0);
  leftFlipperGroup.add(new THREE.Mesh(flipperGeom, whaleSkinMat));
  whaleGroup.add(leftFlipperGroup);

  const rightFlipperGroup = new THREE.Group();
  rightFlipperGroup.position.set(-bodyRad * 0.8, 3.5, -1.0);
  const rightFlipperGeom = flipperGeom.clone();
  rightFlipperGeom.scale(-1, 1, 1);
  rightFlipperGroup.add(new THREE.Mesh(rightFlipperGeom, whaleSkinMat));
  whaleGroup.add(rightFlipperGroup);

  // Tail peduncle & undulating flukes
  const tailGroup = new THREE.Group();
  tailGroup.position.set(0, -bodyLen * 0.48, 0);

  const tailStemGeom = new THREE.CylinderGeometry(0.8, 2.0, 7.5, 12);
  tailStemGeom.rotateX(Math.PI / 2);
  tailStemGeom.translate(0, -3.75, 0);
  tailGroup.add(new THREE.Mesh(tailStemGeom, whaleSkinMat));

  const flukesGeom = new THREE.BoxGeometry(9.0, 2.4, 0.4);
  flukesGeom.translate(0, -7.5, 0);
  tailGroup.add(new THREE.Mesh(flukesGeom, whaleSkinMat));
  whaleGroup.add(tailGroup);

  // Nordeus flank lettering
  const flankCanvas = document.createElement('canvas');
  flankCanvas.width = 512; flankCanvas.height = 128;
  const fg = flankCanvas.getContext('2d');
  fg.fillStyle = 'rgba(0,0,0,0)'; fg.fillRect(0, 0, 512, 128);
  fg.font = 'bold 52px "Arial Black", sans-serif';
  fg.fillStyle = 'rgba(255, 255, 255, 0.85)';
  fg.textAlign = 'center';
  fg.fillText('Nordeus', 256, 75);
  fg.font = 'bold 22px monospace';
  fg.fillStyle = '#f5b800';
  fg.fillText('VTX SKY-LEVIATHAN', 256, 110);
  const flankTex = new THREE.CanvasTexture(flankCanvas);
  const flankMat = new THREE.MeshBasicMaterial({ map: flankTex, transparent: true, opacity: 0.88, side: THREE.DoubleSide });

  const flankSignLeft = new THREE.Mesh(new THREE.PlaneGeometry(8, 2), flankMat);
  flankSignLeft.position.set(bodyRad + 0.1, 1, 0.8);
  flankSignLeft.rotateY(Math.PI / 2);
  flankSignLeft.rotateZ(Math.PI / 12);
  whaleGroup.add(flankSignLeft);

  const flankSignRight = new THREE.Mesh(new THREE.PlaneGeometry(8, 2), flankMat);
  flankSignRight.position.set(-bodyRad - 0.1, 1, 0.8);
  flankSignRight.rotateY(-Math.PI / 2);
  flankSignRight.rotateZ(-Math.PI / 12);
  whaleGroup.add(flankSignRight);

  group.add(whaleGroup);

  // Whale swimming motion in a lazy subterranean orbit inside the cavern
  updaters.push((t, dt) => {
    const swimSpeed = 0.26;
    const a = t * swimSpeed;
    const orbitR_x = 22;
    const orbitR_y = 18;

    whaleGroup.position.set(
      Math.cos(a) * orbitR_x,
      6 + Math.sin(a) * orbitR_y,
      27 + Math.sin(a * 2.0) * 3.8
    );

    const heading = a + Math.PI / 2;
    whaleGroup.rotation.set(
      Math.sin(a * 2.0) * 0.14,
      Math.cos(a) * 0.18,
      heading
    );

    const stroke = Math.sin(t * 2.5);
    tailGroup.rotation.x = stroke * 0.35;
    leftFlipperGroup.rotation.y = stroke * 0.22;
    rightFlipperGroup.rotation.y = -stroke * 0.22;
  });

  // =========================================================================
  // 8. Subterranean Subway Platform ("地下鉄" / Platform 3) with Flooded Tracks
  // =========================================================================
  const platformW = 12, platformL = 42, platformH = 1.4;
  const platformMat = new THREE.MeshStandardMaterial({
    color: '#303438',
    roughness: 0.78,
  });

  const platform = new THREE.Mesh(new THREE.BoxGeometry(platformW, platformL, platformH), platformMat);
  platform.position.set(-24, 4, platformH / 2);
  platform.receiveShadow = true;
  group.add(platform);

  // Platform tactile yellow hazard line
  const edgePaving = new THREE.Mesh(new THREE.BoxGeometry(0.8, platformL, 0.05), new THREE.MeshStandardMaterial({ color: '#f5b800' }));
  edgePaving.position.set(-24 + platformW / 2 - 0.5, 4, platformH + 0.03);
  group.add(edgePaving);

  // Flooded submerged subway rails alongside platform
  const railMat = new THREE.MeshStandardMaterial({ color: '#16191c', metalness: 0.9, roughness: 0.2 });
  for (const rx of [-16.5, -14.5]) {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(0.18, platformL + 14, 0.25), railMat);
    rail.position.set(rx, 4, 0.3);
    group.add(rail);
  }

  // Wooden sleepers under flooded tracks
  const sleeperMat = new THREE.MeshStandardMaterial({ color: '#32251c', roughness: 0.95 });
  for (let sy = -platformL / 2 - 4; sy <= platformL / 2 + 4; sy += 1.8) {
    const sleeper = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.45, 0.2), sleeperMat);
    sleeper.position.set(-15.5, sy + 4, 0.15);
    group.add(sleeper);
  }

  // Station Enamel Sign: 地下鉄 / PLATFORM 3
  const stationSignTex = subwayStationSignTexture();
  const stationSignMat = new THREE.MeshStandardMaterial({
    map: stationSignTex,
    emissiveMap: stationSignTex,
    emissive: new THREE.Color('#38e4ff'),
    emissiveIntensity: 0.85,
    roughness: 0.3,
  });
  const stationSign = new THREE.Mesh(new THREE.BoxGeometry(0.15, 6.5, 3.2), [
    stationSignMat, stationSignMat, ironMat, ironMat, ironMat, ironMat
  ]);
  stationSign.position.set(-24 + platformW / 2 - 1.2, 2, platformH + 3.2);
  group.add(stationSign);

  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 3.2, 8), ironMat);
  post.position.set(-24 + platformW / 2 - 1.2, 2, platformH + 1.6);
  group.add(post);

  // Warm Victorian Station Lantern
  const lanternLight = new THREE.PointLight('#ffc57a', 3.0, 20, 1.4);
  lanternLight.position.set(-24 + platformW / 2 - 1.2, 2, platformH + 3.8);
  group.add(lanternLight);

  // =========================================================================
  // 9. Blooming Japanese Cherry Blossom Tree (Sakura)
  // =========================================================================
  const treeGroup = new THREE.Group();
  treeGroup.position.set(-24, -4, platformH);

  const trunkMat = new THREE.MeshStandardMaterial({ color: '#2c221e', roughness: 0.95 });
  const trunk1 = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.75, 4.2, 8), trunkMat);
  trunk1.position.set(0, 0, 2.1);
  trunk1.rotation.x = 0.15;
  treeGroup.add(trunk1);

  const trunk2 = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.45, 3.5, 8), trunkMat);
  trunk2.position.set(0.6, 0.4, 4.8);
  trunk2.rotation.z = -0.35;
  trunk2.rotation.x = 0.25;
  treeGroup.add(trunk2);

  const petalTex = cherryBlossomTexture();
  const blossomMat = new THREE.MeshStandardMaterial({
    map: petalTex,
    color: '#ffc4dc',
    emissive: new THREE.Color('#ff80aa'),
    emissiveIntensity: 0.75,
    roughness: 0.6,
  });

  const bloomOffsets = [
    [0.8, 0.6, 6.2, 2.8],
    [-0.7, -0.4, 5.5, 2.4],
    [1.8, 0.2, 5.8, 2.2],
    [-0.2, 1.4, 6.0, 2.6],
    [0.2, -1.2, 5.2, 2.3],
    [1.2, 1.6, 6.8, 2.5],
  ];

  for (const [bx, by, bz, brad] of bloomOffsets) {
    const cluster = new THREE.Mesh(new THREE.DodecahedronGeometry(brad, 1), blossomMat);
    cluster.position.set(bx, by, bz);
    cluster.castShadow = true;
    treeGroup.add(cluster);
  }

  group.add(treeGroup);

  // =========================================================================
  // 10. Figure in Yellow Taxi Mackintosh Coat with Umbrella
  // =========================================================================
  const figureGroup = new THREE.Group();
  figureGroup.position.set(-24, 6, platformH);

  const coatMat = new THREE.MeshStandardMaterial({ color: '#f5b800', roughness: 0.45 });
  const pantsMat = new THREE.MeshStandardMaterial({ color: '#141618', roughness: 0.8 });

  const legs = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.22, 1.0, 8), pantsMat);
  legs.position.set(0, 0, 0.5);
  figureGroup.add(legs);

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.38, 1.1, 8), coatMat);
  torso.position.set(0, 0, 1.45);
  figureGroup.add(torso);

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.2, 12, 10), new THREE.MeshStandardMaterial({ color: '#e5c29f' }));
  head.position.set(0, 0, 2.15);
  figureGroup.add(head);

  const umbrellaPole = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 1.6, 6), ironMat);
  umbrellaPole.position.set(0.25, 0.15, 1.8);
  figureGroup.add(umbrellaPole);

  const umbrellaCanopy = new THREE.Mesh(
    new THREE.ConeGeometry(1.2, 0.45, 12, 1, true),
    new THREE.MeshStandardMaterial({ color: '#16191c', roughness: 0.5, side: THREE.DoubleSide })
  );
  umbrellaCanopy.position.set(0.25, 0.15, 2.6);
  umbrellaCanopy.rotateX(Math.PI);
  figureGroup.add(umbrellaCanopy);

  const badge = new THREE.Mesh(new THREE.PlaneGeometry(0.35, 0.18), new THREE.MeshBasicMaterial({ color: '#d4281b' }));
  badge.position.set(0.25, 0.15 - 0.85, 2.45);
  badge.rotation.x = -Math.PI / 4;
  figureGroup.add(badge);

  group.add(figureGroup);

  // =========================================================================
  // 11. Hanging Robot Mask Faces with Fiery Glowing Red Eyes
  // =========================================================================
  const maskTex = robotMaskTexture();
  const maskMat = new THREE.MeshStandardMaterial({
    map: maskTex,
    roughness: 0.4,
    metalness: 0.6,
    emissiveMap: maskTex,
    emissive: new THREE.Color('#ffffff'),
    emissiveIntensity: 1.5,
  });

  const maskOffsets = [
    [-15, 14, 34],
    [14, 12, 33],
    [-8, -12, 31],
    [12, -14, 32],
    [0, -20, 29],
  ];

  const maskMeshes = [];
  for (const [mx, my, mz] of maskOffsets) {
    const maskHolder = new THREE.Group();
    maskHolder.position.set(mx, my, mz);

    const wire = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 14, 4), chainMat);
    wire.position.set(0, 0, 7);
    maskHolder.add(wire);

    const mMesh = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 3.2), maskMat);
    mMesh.rotation.x = Math.PI / 12;
    maskHolder.add(mMesh);

    group.add(maskHolder);
    maskMeshes.push(maskHolder);
  }

  updaters.push((t) => {
    maskMeshes.forEach((mh, i) => {
      mh.rotation.z = Math.sin(t * 1.5 + i * 1.2) * 0.08;
      mh.rotation.x = Math.cos(t * 1.2 + i * 0.9) * 0.06;
    });
  });

  // =========================================================================
  // 12. Subterranean Helipad / Landing Pad (Inside the Underground Cavern)
  // =========================================================================
  const padGroup = new THREE.Group();
  padGroup.position.set(16, 2, 0.6);

  const padGeom = new THREE.CylinderGeometry(11, 11.5, 0.8, 8);
  padGeom.rotateX(Math.PI / 2);
  const padMesh = new THREE.Mesh(padGeom, basaltMat);
  padMesh.receiveShadow = true;
  padGroup.add(padMesh);

  const padCanvas = document.createElement('canvas');
  padCanvas.width = 512; padCanvas.height = 512;
  const pc2 = padCanvas.getContext('2d');
  pc2.fillStyle = '#1c2024'; pc2.fillRect(0, 0, 512, 512);

  pc2.strokeStyle = '#f5b800'; pc2.lineWidth = 14;
  pc2.strokeRect(20, 20, 472, 472);

  pc2.beginPath(); pc2.arc(256, 256, 180, 0, Math.PI * 2);
  pc2.strokeStyle = '#ffffff'; pc2.lineWidth = 6; pc2.stroke();

  pc2.font = 'bold 50px Impact, Arial, sans-serif';
  pc2.fillStyle = '#f5b800'; pc2.textAlign = 'center';
  pc2.fillText('VTX BASEMENT', 256, 240);
  pc2.font = 'bold 24px monospace'; pc2.fillStyle = '#e8e6d8';
  pc2.fillText('SUBTERRANEAN LZ · VOLCANO', 256, 285);

  const padDecal = new THREE.Mesh(
    new THREE.PlaneGeometry(16, 16),
    new THREE.MeshStandardMaterial({ map: new THREE.CanvasTexture(padCanvas), roughness: 0.6 })
  );
  padDecal.position.set(0, 0, 0.42);
  padGroup.add(padDecal);

  group.add(padGroup);

  scene.add(group);

  return {
    group,
    update: (now) => {
      const dt = 0.05;
      updaters.forEach((fn) => fn(now, dt));
    },
  };
}
