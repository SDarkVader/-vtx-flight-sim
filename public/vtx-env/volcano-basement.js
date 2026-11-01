// The Volcanic Above-Ground "Vader's Taxi's Basement"
// A surreal volcanic caldera soaring above the landscape, housing the eccentric
// underground headquarters with its steampunk signage, flowing molten lava falls,
// Victorian iron/glass vault arches, swimming sky-whale, blooming cherry blossom tree,
// subway station platform, and hanging robot masks with fiery glowing eyes.

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

  // Position: North of the airfield on the ascending ridge, directly in view from Stand 1 and runway
  const CX = -30, CY = 350, BASE_Z = 12;
  group.position.set(CX, CY, BASE_Z);

  const updaters = [];

  // =========================================================================
  // 1. Outer Volcanic Caldera & Stepped Basalt Cone
  // =========================================================================
  const basaltMat = new THREE.MeshStandardMaterial({
    map: volcanoBasaltTexture(),
    roughness: 0.88,
    metalness: 0.15,
  });
  basaltMat.map.repeat.set(4, 2);

  // Outer cone geometry with an open top and a massive South-facing cavern mouth portal
  const outerR = 82, innerR = 46, rimZ = 58;
  const coneGeom = new THREE.CylinderGeometry(innerR, outerR, rimZ, 48, 12, true);
  coneGeom.rotateX(Math.PI / 2);
  coneGeom.translate(0, 0, rimZ / 2);

  // Carve out jagged basalt crags and a giant southern arch entrance
  const pos = coneGeom.attributes.position;
  const rGen = rng(991);
  for (let i = 0; i < pos.count; i++) {
    let x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const angle = Math.atan2(y, x);
    const rad = Math.hypot(x, y);

    // Southern arch entrance portal facing airfield (angle ~ -Math.PI / 2)
    const isSouthPortal = Math.abs(angle - (-Math.PI / 2)) < 0.42 && z < 38;
    if (isSouthPortal) {
      const archFactor = Math.cos((angle - (-Math.PI / 2)) / 0.42 * Math.PI / 2);
      if (z < 34 * archFactor) {
        // Push vertices outward/upward to open the giant portal arch
        pos.setZ(i, Math.max(z, 32 * archFactor));
      }
    }

    // Basalt column faceted noise
    const noise = (rGen() - 0.5) * 4.5;
    pos.setXYZ(i, x + Math.cos(angle) * noise, y + Math.sin(angle) * noise, pos.getZ(i));
  }
  coneGeom.computeVertexNormals();

  const outerCone = new THREE.Mesh(coneGeom, basaltMat);
  outerCone.castShadow = true;
  outerCone.receiveShadow = true;
  group.add(outerCone);

  // Rim basalt crags and jagged crest
  const rimRingGeom = new THREE.TorusGeometry(innerR + 1, 3.8, 10, 48);
  rimRingGeom.translate(0, 0, rimZ);
  const rimRing = new THREE.Mesh(rimRingGeom, basaltMat);
  rimRing.castShadow = true;
  group.add(rimRing);

  // Caldera interior floor: basalt slab with cracks
  const floorGeom = new THREE.CircleGeometry(innerR + 4, 36);
  floorGeom.translate(0, 0, 0.4);
  const floor = new THREE.Mesh(floorGeom, basaltMat);
  floor.receiveShadow = true;
  group.add(floor);

  // =========================================================================
  // 2. Molten Lava Waterfall & Boiling Magma Pool
  // =========================================================================
  const lavaTex = lavaTexture();
  const lavaEmissiveTex = lavaTexture();
  const lavaMat = new THREE.MeshStandardMaterial({
    map: lavaTex,
    emissiveMap: lavaEmissiveTex,
    emissive: new THREE.Color('#ff4800'),
    emissiveIntensity: 2.8,
    roughness: 0.35,
    metalness: 0.2,
  });
  lavaTex.repeat.set(2, 4);
  lavaEmissiveTex.repeat.set(2, 4);

  // Massive vertical curved lava cascade pouring down the northern interior wall
  const fallW = 32, fallH = 54, fallR = innerR - 2;
  const fallGeom = new THREE.CylinderGeometry(fallR, fallR, fallH, 24, 16, true, Math.PI * 0.25, Math.PI * 0.5);
  fallGeom.rotateX(Math.PI / 2);
  fallGeom.translate(0, 0, fallH / 2 + 1);
  const lavaFall = new THREE.Mesh(fallGeom, lavaMat);
  lavaFall.castShadow = false;
  group.add(lavaFall);

  // Boiling Magma Plunge Pool at base
  const poolGeom = new THREE.PlaneGeometry(36, 22, 16, 16);
  const pool = new THREE.Mesh(poolGeom, lavaMat);
  pool.position.set(0, 20, 0.8);
  pool.receiveShadow = true;
  group.add(pool);

  // Point light for dramatic volcanic illumination inside the chamber
  const lavaLight = new THREE.PointLight('#ff5511', 8.0, 95, 1.2);
  lavaLight.position.set(0, 15, 14);
  group.add(lavaLight);

  // Secondary amber ambient glow
  const rimLight = new THREE.PointLight('#ff8822', 4.5, 75, 1.4);
  rimLight.position.set(0, -10, 32);
  group.add(rimLight);

  // Animate lava flow downwards in UV coordinates
  updaters.push((t, dt) => {
    lavaTex.offset.y -= dt * 0.22;
    lavaEmissiveTex.offset.y -= dt * 0.22;
    // Molten light pulse
    lavaLight.intensity = 7.5 + Math.sin(t * 5.0) * 1.2 + Math.cos(t * 8.3) * 0.8;
  });

  // =========================================================================
  // 3. Victorian Arched Iron & Glass Vault Structure
  // =========================================================================
  const ironMat = new THREE.MeshStandardMaterial({
    color: '#22272c',
    metalness: 0.75,
    roughness: 0.45,
  });
  const glassMat = new THREE.MeshPhysicalMaterial({
    color: '#659ea8',
    transmission: 0.72,
    opacity: 0.85,
    transparent: true,
    roughness: 0.22,
    metalness: 0.1,
    ior: 1.5,
  });

  // 5 Curved cast-iron structural rib arches spanning the caldera
  const ribCount = 5;
  for (let r = 0; r < ribCount; r++) {
    const ry = -24 + r * 12;
    const archRadius = 38;
    const ribGeom = new THREE.TorusGeometry(archRadius, 0.45, 8, 32, Math.PI);
    ribGeom.rotateY(Math.PI / 2);
    ribGeom.translate(0, ry, 0);

    const rib = new THREE.Mesh(ribGeom, ironMat);
    rib.position.set(0, 0, 0);
    rib.castShadow = true;
    group.add(rib);

    // Cross struts and lattice trusses connecting the arches
    if (r < ribCount - 1) {
      for (let a = 0.2; a < Math.PI; a += 0.45) {
        const strutGeom = new THREE.CylinderGeometry(0.18, 0.18, 12, 6);
        const strut = new THREE.Mesh(strutGeom, ironMat);
        const sx = Math.cos(a) * archRadius;
        const sz = Math.sin(a) * archRadius;
        strut.position.set(sx, ry + 6, sz);
        strut.rotateX(Math.PI / 2);
        group.add(strut);
      }
    }
  }

  // =========================================================================
  // 4. Steampunk "Vader's Taxi's Basement" Sign with Rotating Brass Gears
  // =========================================================================
  const signTex = basementSignTexture();
  const signMat = new THREE.MeshStandardMaterial({
    map: signTex,
    roughness: 0.5,
    metalness: 0.35,
    emissiveMap: signTex,
    emissive: new THREE.Color('#ffffff'),
    emissiveIntensity: 0.65,
  });

  const signW = 28, signH = 14;
  const signMesh = new THREE.Mesh(new THREE.PlaneGeometry(signW, signH), signMat);
  signMesh.position.set(0, 16, 36);
  signMesh.rotation.y = Math.PI; // Face South toward the entrance portal!
  signMesh.castShadow = true;
  group.add(signMesh);

  // Steampunk Brass Gears mounted on the corners that actually rotate
  const gearMat = new THREE.MeshStandardMaterial({
    color: '#d4af37',
    metalness: 0.8,
    roughness: 0.3,
  });

  const gears = [];
  const gearCoords = [
    { x: -12.5, z: 41, r: 2.2, speed: 0.8, teeth: 12 },
    { x: -10.2, z: 43.5, r: 1.4, speed: -1.25, teeth: 8 },
    { x: 12.5, z: 41, r: 2.2, speed: -0.8, teeth: 12 },
    { x: 10.2, z: 43.5, r: 1.4, speed: 1.25, teeth: 8 },
  ];

  for (const gc of gearCoords) {
    const gearGroup = new THREE.Group();
    gearGroup.position.set(gc.x, 15.9, gc.z);
    gearGroup.rotation.y = Math.PI;

    // Center disc
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(gc.r, gc.r, 0.25, 16), gearMat);
    disc.rotateX(Math.PI / 2);
    gearGroup.add(disc);

    // Teeth
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
    for (const g of gears) {
      g.mesh.rotation.z += g.speed * dt;
    }
  });

  // Hanging heavy iron chains holding the sign
  const chainMat = new THREE.MeshStandardMaterial({ color: '#16191c', metalness: 0.9, roughness: 0.4 });
  for (const cx of [-11, 11]) {
    const chain = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 16, 6), chainMat);
    chain.position.set(cx, 16, 46);
    group.add(chain);
  }

  // =========================================================================
  // 5. The Majestic Swimming SKY-WHALE ("Nordeus" / VTX Leviathan)
  // =========================================================================
  const whaleGroup = new THREE.Group();
  whaleGroup.name = 'vtx-sky-whale';

  const whaleSkinMat = new THREE.MeshStandardMaterial({
    color: '#283642',
    roughness: 0.4,
    metalness: 0.15,
  });
  const bellyMat = new THREE.MeshStandardMaterial({
    color: '#d0d8dc',
    roughness: 0.5,
  });

  // Torpedo whale body
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
  const belly = new THREE.Mesh(bellyGeom, bellyMat);
  whaleGroup.add(belly);

  // Dorsal fin
  const dorsalGeom = new THREE.ConeGeometry(1.2, 3.2, 6);
  dorsalGeom.rotateX(Math.PI / 3);
  dorsalGeom.translate(0, -2, bodyRad + 0.6);
  whaleGroup.add(new THREE.Mesh(dorsalGeom, whaleSkinMat));

  // Pectoral flippers (wings that gently stroke)
  const leftFlipperGroup = new THREE.Group();
  leftFlipperGroup.position.set(bodyRad * 0.8, 3.5, -1.0);
  const flipperGeom = new THREE.BoxGeometry(6.5, 1.8, 0.35);
  flipperGeom.translate(3.25, -0.2, 0);
  const leftFlipper = new THREE.Mesh(flipperGeom, whaleSkinMat);
  leftFlipperGroup.add(leftFlipper);
  whaleGroup.add(leftFlipperGroup);

  const rightFlipperGroup = new THREE.Group();
  rightFlipperGroup.position.set(-bodyRad * 0.8, 3.5, -1.0);
  const rightFlipperGeom = flipperGeom.clone();
  rightFlipperGeom.scale(-1, 1, 1);
  const rightFlipper = new THREE.Mesh(rightFlipperGeom, whaleSkinMat);
  rightFlipperGroup.add(rightFlipper);
  whaleGroup.add(rightFlipperGroup);

  // Tail peduncle & flukes that undulate
  const tailGroup = new THREE.Group();
  tailGroup.position.set(0, -bodyLen * 0.48, 0);

  const tailStemGeom = new THREE.CylinderGeometry(0.8, 2.0, 7.5, 12);
  tailStemGeom.rotateX(Math.PI / 2);
  tailStemGeom.translate(0, -3.75, 0);
  tailGroup.add(new THREE.Mesh(tailStemGeom, whaleSkinMat));

  const flukesGeom = new THREE.BoxGeometry(9.0, 2.4, 0.4);
  flukesGeom.translate(0, -7.5, 0);
  const flukes = new THREE.Mesh(flukesGeom, whaleSkinMat);
  tailGroup.add(flukes);
  whaleGroup.add(tailGroup);

  // Nordeus / VTX flank lettering
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

  // Whale swimming motion in a lazy ellipse inside the caldera
  updaters.push((t, dt) => {
    const swimSpeed = 0.28;
    const a = t * swimSpeed;
    const orbitR_x = 24;
    const orbitR_y = 20;

    whaleGroup.position.set(
      Math.cos(a) * orbitR_x,
      Math.sin(a) * orbitR_y,
      30 + Math.sin(a * 2.0) * 4.5
    );

    // Tangent orientation
    const heading = a + Math.PI / 2;
    whaleGroup.rotation.set(
      Math.sin(a * 2.0) * 0.15,
      Math.cos(a) * 0.2,
      heading
    );

    // Swimming strokes
    const stroke = Math.sin(t * 2.5);
    tailGroup.rotation.x = stroke * 0.35;
    leftFlipperGroup.rotation.y = stroke * 0.25;
    rightFlipperGroup.rotation.y = -stroke * 0.25;
  });

  // =========================================================================
  // 6. Subway Platform ("地下鉄" / Platform 3) with Flooded Tracks
  // =========================================================================
  const platformW = 12, platformL = 38, platformH = 1.4;
  const platformMat = new THREE.MeshStandardMaterial({
    color: '#34383c',
    roughness: 0.75,
  });

  const platform = new THREE.Mesh(new THREE.BoxGeometry(platformW, platformL, platformH), platformMat);
  platform.position.set(-22, -4, platformH / 2);
  platform.receiveShadow = true;
  group.add(platform);

  // Platform tactile edge paving & yellow hazard line
  const edgePaving = new THREE.Mesh(new THREE.BoxGeometry(0.8, platformL, 0.05), new THREE.MeshStandardMaterial({ color: '#f5b800' }));
  edgePaving.position.set(-22 + platformW / 2 - 0.5, -4, platformH + 0.03);
  group.add(edgePaving);

  // Flooded submerged subway rails running alongside platform
  const railMat = new THREE.MeshStandardMaterial({ color: '#1a1d20', metalness: 0.9, roughness: 0.2 });
  for (const rx of [-14.5, -12.5]) {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(0.18, platformL + 12, 0.25), railMat);
    rail.position.set(rx, -4, 0.3);
    group.add(rail);
  }

  // Wooden sleepers under tracks
  const sleeperMat = new THREE.MeshStandardMaterial({ color: '#382b20', roughness: 0.9 });
  for (let sy = -platformL / 2 - 4; sy <= platformL / 2 + 4; sy += 1.8) {
    const sleeper = new THREE.Mesh(new THREE.BoxGeometry(3.6, 0.45, 0.2), sleeperMat);
    sleeper.position.set(-13.5, sy, 0.15);
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
  stationSign.position.set(-22 + platformW / 2 - 1.2, -6, platformH + 3.2);
  group.add(stationSign);

  // Platform steel post for sign
  const postGeom = new THREE.CylinderGeometry(0.12, 0.12, 3.2, 8);
  const post = new THREE.Mesh(postGeom, ironMat);
  post.position.set(-22 + platformW / 2 - 1.2, -6, platformH + 1.6);
  group.add(post);

  // Vintage Station Lantern casting warm pool of light
  const lanternLight = new THREE.PointLight('#ffc57a', 2.8, 18, 1.4);
  lanternLight.position.set(-22 + platformW / 2 - 1.2, -6, platformH + 3.8);
  group.add(lanternLight);

  // =========================================================================
  // 7. Glowing Blooming Japanese Cherry Blossom Tree (Sakura)
  // =========================================================================
  const treeGroup = new THREE.Group();
  treeGroup.position.set(-22, -12, platformH);

  // Sculptured twisted dark trunk
  const trunkMat = new THREE.MeshStandardMaterial({ color: '#322521', roughness: 0.95 });
  const trunk1 = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.75, 4.2, 8), trunkMat);
  trunk1.position.set(0, 0, 2.1);
  trunk1.rotation.x = 0.15;
  treeGroup.add(trunk1);

  const trunk2 = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.45, 3.5, 8), trunkMat);
  trunk2.position.set(0.6, 0.4, 4.8);
  trunk2.rotation.z = -0.35;
  trunk2.rotation.x = 0.25;
  treeGroup.add(trunk2);

  // Cherry Blossom Bloom clusters
  const petalTex = cherryBlossomTexture();
  const blossomMat = new THREE.MeshStandardMaterial({
    map: petalTex,
    color: '#ffc4dc',
    emissive: new THREE.Color('#ff80aa'),
    emissiveIntensity: 0.65,
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
  // 8. Lone Figure in Yellow Taxi Mackintosh Coat with Umbrella
  // =========================================================================
  const figureGroup = new THREE.Group();
  figureGroup.position.set(-22, -2, platformH);

  // Yellow coat body
  const coatMat = new THREE.MeshStandardMaterial({ color: '#f5b800', roughness: 0.45 });
  const pantsMat = new THREE.MeshStandardMaterial({ color: '#16191c', roughness: 0.8 });

  const legs = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.22, 1.0, 8), pantsMat);
  legs.position.set(0, 0, 0.5);
  figureGroup.add(legs);

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.38, 1.1, 8), coatMat);
  torso.position.set(0, 0, 1.45);
  figureGroup.add(torso);

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.2, 12, 10), new THREE.MeshStandardMaterial({ color: '#e5c29f' }));
  head.position.set(0, 0, 2.15);
  figureGroup.add(head);

  // Umbrella (Black with red Nordeus / Taxi badge)
  const umbrellaPole = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 1.6, 6), ironMat);
  umbrellaPole.position.set(0.25, 0.15, 1.8);
  figureGroup.add(umbrellaPole);

  const umbrellaCanopy = new THREE.Mesh(
    new THREE.ConeGeometry(1.2, 0.45, 12, 1, true),
    new THREE.MeshStandardMaterial({ color: '#181b1e', roughness: 0.5, side: THREE.DoubleSide })
  );
  umbrellaCanopy.position.set(0.25, 0.15, 2.6);
  umbrellaCanopy.rotateX(Math.PI);
  figureGroup.add(umbrellaCanopy);

  // Red badge on umbrella
  const badge = new THREE.Mesh(new THREE.PlaneGeometry(0.35, 0.18), new THREE.MeshBasicMaterial({ color: '#d4281b' }));
  badge.position.set(0.25, 0.15 - 0.85, 2.45);
  badge.rotation.x = -Math.PI / 4;
  figureGroup.add(badge);

  group.add(figureGroup);

  // =========================================================================
  // 9. Hanging Robot Mask Faces with Fiery Glowing Red Eyes
  // =========================================================================
  const maskTex = robotMaskTexture();
  const maskMat = new THREE.MeshStandardMaterial({
    map: maskTex,
    roughness: 0.4,
    metalness: 0.6,
    emissiveMap: maskTex,
    emissive: new THREE.Color('#ffffff'),
    emissiveIntensity: 1.4,
  });

  const maskOffsets = [
    [-15, 8, 38],
    [14, 6, 36],
    [-8, -16, 34],
    [12, -18, 35],
    [0, -26, 32],
  ];

  const maskMeshes = [];
  for (const [mx, my, mz] of maskOffsets) {
    const maskHolder = new THREE.Group();
    maskHolder.position.set(mx, my, mz);

    // Hanging wire
    const wire = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 14, 4), chainMat);
    wire.position.set(0, 0, 7);
    maskHolder.add(wire);

    // Mask plane
    const mMesh = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 3.2), maskMat);
    mMesh.rotation.x = Math.PI / 12; // tilt slightly downward to peer at aircraft
    maskHolder.add(mMesh);

    group.add(maskHolder);
    maskMeshes.push(maskHolder);
  }

  // Gentle swaying in geothermal updrafts
  updaters.push((t) => {
    maskMeshes.forEach((mh, i) => {
      mh.rotation.z = Math.sin(t * 1.5 + i * 1.2) * 0.08;
      mh.rotation.x = Math.cos(t * 1.2 + i * 0.9) * 0.06;
    });
  });

  // =========================================================================
  // 10. Volcanic Basement Landing Platform
  // =========================================================================
  const padGroup = new THREE.Group();
  padGroup.position.set(16, -6, 0.6);

  // Basalt octagonal helipad
  const padGeom = new THREE.CylinderGeometry(11, 11.5, 0.8, 8);
  padGeom.rotateX(Math.PI / 2);
  const padMesh = new THREE.Mesh(padGeom, basaltMat);
  padMesh.receiveShadow = true;
  padGroup.add(padMesh);

  // Painted hazard ring & logo
  const padCanvas = document.createElement('canvas');
  padCanvas.width = 512; padCanvas.height = 512;
  const pc = padCanvas.getContext('2d');
  pc.fillStyle = '#222528'; pc.fillRect(0, 0, 512, 512);

  // Hazard perimeter
  pc.strokeStyle = '#f5b800'; pc.lineWidth = 14;
  pc.strokeRect(20, 20, 472, 472);

  // Inner ring
  pc.beginPath(); pc.arc(256, 256, 180, 0, Math.PI * 2);
  pc.strokeStyle = '#ffffff'; pc.lineWidth = 6; pc.stroke();

  // VTX Basement Text
  pc.font = 'bold 54px Impact, Arial, sans-serif';
  pc.fillStyle = '#f5b800'; pc.textAlign = 'center';
  pc.fillText('VTX BASEMENT', 256, 240);
  pc.font = 'bold 24px monospace'; pc.fillStyle = '#e8e6d8';
  pc.fillText('VOLCANO LZ · CAUTION LAVA', 256, 285);

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
      const dt = 0.05; // standard delta
      updaters.forEach((fn) => fn(now, dt));
    },
  };
}
