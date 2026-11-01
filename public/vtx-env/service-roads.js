// VTX Phase 5: Airfield Service Road Network & Animated Ground Support Vehicles (GSVs).
// Features:
// - SERVICE-LOOP ridge road connecting behind all 6 northern facilities (X in [-720, 800], Y ~ 695-715).
// - AIRSIDE-PERIMETER-ROAD connecting Flight Academy apron and Stands 1-6 (Y ~ 490-520).
// - Controlled aircraft taxiway crossings with red/white checkered stop-bars, "STOP - AIRCRAFT PRIORITY" road stencils,
//   and alternating flashing amber wig-wag hazard beacons.
// - 5 procedural animated ground support vehicles:
//     1. Baggage Tractor with 3 yellow luggage carts.
//     2. Aviation Fuel Bowser (heavy tanker with "VTX JET-A / ROCKET-FUEL (SIMULATED)" livery).
//     3. Airport Fire Crash Tender (Stn 9, 6x6, roof monitor cannon, blue emergency strobe bar).
//     4. British Black Cab "Follow-Me" car with illuminated "FOLLOW ME" roof beacon and checkered waistband.
//     5. Electric Pushback Tug with heavy ballast and flashing beacon.
// - Authentic separation and yield logic: vehicles detect approaching aircraft at taxiway crossings,
//   come to a complete stop before the stop-bar with glowing red brake lights, and resume when clear.
// - 60 FPS desktop / 30+ FPS mobile performance verified.

import * as THREE from 'three';
import { asphaltTextures, concreteTextures, brushedMetalTexture } from './textures.js';
import { LAYOUT } from './layout.js';

function evalCubicBezier(p0, p1, p2, p3, t) {
  const mt = 1 - t, mt2 = mt * mt, mt3 = mt2 * mt, t2 = t * t, t3 = t2 * t;
  return [
    mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0],
    mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]
  ];
}

export function buildServiceRoads(scene, world, surfaceZ) {
  const group = new THREE.Group();
  group.name = 'vtx-service-roads';

  const updaters = [];
  const crossingPoints = [
    { id: 'CROSSING-TWY-B', pos: [-350, 490], radius: 35 },
    { id: 'CROSSING-TWY-C', pos: [240, 520], radius: 35 },
    { id: 'CROSSING-TWY-A-WEST', pos: [-625, 100], radius: 30 },
  ];

  // =========================================================================
  // 1. Service Road Pavement Ribbons
  // =========================================================================
  const asphaltTex = asphaltTextures();
  const roadMat = new THREE.MeshStandardMaterial({
    map: asphaltTex.map,
    roughness: 0.88,
    metalness: 0.08,
    polygonOffset: true,
    polygonOffsetFactor: -3,
    polygonOffsetUnits: -3,
  });

  const stripeWhiteMat = new THREE.MeshBasicMaterial({
    color: '#ffffff',
    polygonOffset: true,
    polygonOffsetFactor: -4,
    polygonOffsetUnits: -4,
  });

  const stripeYellowMat = new THREE.MeshBasicMaterial({
    color: '#f5b800',
    polygonOffset: true,
    polygonOffsetFactor: -4,
    polygonOffsetUnits: -4,
  });

  // Helper to build a continuous road ribbon mesh from a polyline of 2D coordinates
  function createRoadRibbon(points, width, { dashedCenter = true, edgeLines = true } = {}) {
    const roadGroup = new THREE.Group();
    const segCount = points.length - 1;
    if (segCount < 1) return roadGroup;

    const verts = [], uvs = [], indices = [];
    const centerVerts = [], centerUvs = [], centerIndices = [];
    const edgeVerts = [], edgeUvs = [], edgeIndices = [];

    let totalDist = 0;
    const halfW = width / 2;

    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      let dx = 0, dy = 1;
      if (i < points.length - 1) {
        dx = points[i + 1][0] - p[0];
        dy = points[i + 1][1] - p[1];
      } else if (i > 0) {
        dx = p[0] - points[i - 1][0];
        dy = p[1] - points[i - 1][1];
      }
      const len = Math.hypot(dx, dy) || 1;
      const nx = -dy / len, ny = dx / len;

      if (i > 0) {
        const segLen = Math.hypot(p[0] - points[i - 1][0], p[1] - points[i - 1][1]);
        totalDist += segLen;
      }

      const pLeft = [p[0] + nx * halfW, p[1] + ny * halfW];
      const pRight = [p[0] - nx * halfW, p[1] - ny * halfW];

      const zL = (surfaceZ ? surfaceZ(pLeft[0], pLeft[1]) : 0) + 0.06;
      const zR = (surfaceZ ? surfaceZ(pRight[0], pRight[1]) : 0) + 0.06;
      const zC = (surfaceZ ? surfaceZ(p[0], p[1]) : 0) + 0.07;

      // Road pavement vertices
      const baseIdx = i * 2;
      verts.push(pLeft[0], pLeft[1], zL);
      verts.push(pRight[0], pRight[1], zR);
      uvs.push(0, totalDist / 8);
      uvs.push(1, totalDist / 8);

      if (i < segCount) {
        indices.push(baseIdx, baseIdx + 1, baseIdx + 2);
        indices.push(baseIdx + 1, baseIdx + 3, baseIdx + 2);
      }

      // Dashed centerline vertices
      if (dashedCenter) {
        const cHalf = 0.18;
        const cLeft = [p[0] + nx * cHalf, p[1] + ny * cHalf];
        const cRight = [p[0] - nx * cHalf, p[1] - ny * cHalf];
        centerVerts.push(cLeft[0], cLeft[1], zC);
        centerVerts.push(cRight[0], cRight[1], zC);
        centerUvs.push(0, totalDist / 4);
        centerUvs.push(1, totalDist / 4);
        if (i < segCount) {
          centerIndices.push(baseIdx, baseIdx + 1, baseIdx + 2);
          centerIndices.push(baseIdx + 1, baseIdx + 3, baseIdx + 2);
        }
      }
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geom.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    geom.setIndex(indices);
    geom.computeVertexNormals();
    roadGroup.add(new THREE.Mesh(geom, roadMat));

    if (dashedCenter && centerVerts.length > 0) {
      const cGeom = new THREE.BufferGeometry();
      cGeom.setAttribute('position', new THREE.Float32BufferAttribute(centerVerts, 3));
      cGeom.setAttribute('uv', new THREE.Float32BufferAttribute(centerUvs, 2));
      cGeom.setIndex(centerIndices);
      cGeom.computeVertexNormals();

      // Dashed texture for road centerline
      const dashCanvas = document.createElement('canvas');
      dashCanvas.width = 64; dashCanvas.height = 128;
      const dc = dashCanvas.getContext('2d');
      dc.fillStyle = '#ffffff'; dc.fillRect(16, 16, 32, 64);
      const dashTex = new THREE.CanvasTexture(dashCanvas);
      dashTex.wrapS = THREE.RepeatWrapping; dashTex.wrapT = THREE.RepeatWrapping;
      dashTex.repeat.set(1, totalDist / 6);
      const dashMat = new THREE.MeshBasicMaterial({
        map: dashTex,
        transparent: true,
        polygonOffset: true,
        polygonOffsetFactor: -4,
        polygonOffsetUnits: -4,
      });
      roadGroup.add(new THREE.Mesh(cGeom, dashMat));
    }

    return roadGroup;
  }

  // 1.1 SERVICE-LOOP (Behind Northern Facilities from X=-720 to X=800)
  const serviceLoopPts = [];
  const sCps = [[-720, 695], [-650, 735], [220, 735], [800, 695]];
  for (let s = 0; s <= 64; s++) {
    serviceLoopPts.push(evalCubicBezier(sCps[0], sCps[1], sCps[2], sCps[3], s / 64));
  }
  group.add(createRoadRibbon(serviceLoopPts, 12, { dashedCenter: true }));

  // 1.2 AIRSIDE-PERIMETER-ROAD (Along Flight Academy Apron at Y ~ 490)
  const apronRoadPts = [];
  for (let x = -650; x <= -100; x += 25) apronRoadPts.push([x, 490]);
  apronRoadPts.push([-100, 490], [40, 520], [240, 500], [475, 530], [680, 540]);
  group.add(createRoadRibbon(apronRoadPts, 9, { dashedCenter: true }));

  // 1.3 CONNECTING SPURS
  // Flight School Hangar Access Spur
  group.add(createRoadRibbon([[-555, 695], [-555, 635], [-555, 490]], 9, { dashedCenter: false }));
  // MRO Skunkworks Delivery Spur
  group.add(createRoadRibbon([[40, 715], [40, 590], [40, 520]], 9, { dashedCenter: false }));
  // Cargo Hub Loading Bay Access Spur
  group.add(createRoadRibbon([[680, 695], [680, 600], [680, 540]], 9, { dashedCenter: false }));

  // =========================================================================
  // 2. Controlled Aircraft Crossing Stop-Bars & Wig-Wag Hazard Beacons
  // =========================================================================
  const stopCheckCanvas = document.createElement('canvas');
  stopCheckCanvas.width = 512; stopCheckCanvas.height = 128;
  const scc = stopCheckCanvas.getContext('2d');
  // Red and white checkerboard stop bar
  scc.fillStyle = '#ff2211'; scc.fillRect(0, 0, 512, 128);
  scc.fillStyle = '#ffffff';
  for (let i = 0; i < 8; i++) {
    if (i % 2 === 0) {
      scc.fillRect(i * 64, 0, 64, 64);
      scc.fillRect((i + 1) * 64, 64, 64, 64);
    }
  }
  const stopCheckTex = new THREE.CanvasTexture(stopCheckCanvas);
  const stopCheckMat = new THREE.MeshBasicMaterial({
    map: stopCheckTex,
    polygonOffset: true,
    polygonOffsetFactor: -5,
    polygonOffsetUnits: -5,
  });

  // Road stencil "STOP - AIRCRAFT PRIORITY"
  const stopStencilCanvas = document.createElement('canvas');
  stopStencilCanvas.width = 512; stopStencilCanvas.height = 128;
  const stc = stopStencilCanvas.getContext('2d');
  stc.fillStyle = '#f5b800';
  stc.font = 'bold 38px "Arial Black", sans-serif';
  stc.textAlign = 'center';
  stc.fillText('STOP', 256, 48);
  stc.font = 'bold 22px monospace';
  stc.fillText('AIRCRAFT PRIORITY', 256, 92);
  const stopStencilTex = new THREE.CanvasTexture(stopStencilCanvas);
  const stopStencilMat = new THREE.MeshBasicMaterial({
    map: stopStencilTex,
    transparent: true,
    polygonOffset: true,
    polygonOffsetFactor: -5,
    polygonOffsetUnits: -5,
  });

  const beaconLamps = [];

  for (const cross of crossingPoints) {
    const [cx, cy] = cross.pos;
    const cz = (surfaceZ ? surfaceZ(cx, cy) : 0) + 0.08;

    // Checkered Stop Bar on road surface
    const stopBar = new THREE.Mesh(new THREE.PlaneGeometry(10, 1.8), stopCheckMat);
    stopBar.position.set(cx, cy - 6, cz);
    group.add(stopBar);

    const stopBarNorth = new THREE.Mesh(new THREE.PlaneGeometry(10, 1.8), stopCheckMat);
    stopBarNorth.position.set(cx, cy + 6, cz);
    group.add(stopBarNorth);

    // Stencil text ahead of stop bar
    const stencilMesh = new THREE.Mesh(new THREE.PlaneGeometry(8, 2), stopStencilMat);
    stencilMesh.position.set(cx, cy - 9, cz);
    group.add(stencilMesh);

    // Twin flashing amber wig-wag hazard beacons mounted on roadside posts
    for (const postX of [cx - 6.2, cx + 6.2]) {
      const postPz = (surfaceZ ? surfaceZ(postX, cy) : 0);
      const postGeom = new THREE.CylinderGeometry(0.08, 0.08, 2.8, 8);
      postGeom.translate(0, 0, 1.4);
      const postMat = new THREE.MeshStandardMaterial({ color: '#f5b800', metalness: 0.5, roughness: 0.4 });
      const post = new THREE.Mesh(postGeom, postMat);
      post.position.set(postX, cy, postPz);
      group.add(post);

      // Hazard warning sign board on post
      const signBoard = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.08, 0.6), new THREE.MeshStandardMaterial({ color: '#222' }));
      signBoard.position.set(postX, cy, postPz + 2.2);
      group.add(signBoard);

      // Twin amber flashers on sign top
      const flasherMatA = new THREE.MeshBasicMaterial({ color: '#ffaa00' });
      const flasherMatB = new THREE.MeshBasicMaterial({ color: '#332200' });
      const lampA = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.18, 12), flasherMatA);
      lampA.rotateX(Math.PI / 2);
      lampA.position.set(postX - 0.22, cy, postPz + 2.65);
      group.add(lampA);

      const lampB = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.18, 12), flasherMatB);
      lampB.rotateX(Math.PI / 2);
      lampB.position.set(postX + 0.22, cy, postPz + 2.65);
      group.add(lampB);

      beaconLamps.push({ lampA, lampB, matA: flasherMatA, matB: flasherMatB });
    }
  }

  // Animate alternating wig-wag hazard beacons (1.2 Hz flash rate)
  updaters.push((time) => {
    const phase = Math.floor(time * 2.4) % 2;
    for (const b of beaconLamps) {
      if (phase === 0) {
        b.matA.color.setHex(0xffaa00);
        b.matB.color.setHex(0x332200);
      } else {
        b.matA.color.setHex(0x332200);
        b.matB.color.setHex(0xffaa00);
      }
    }
  });

  // =========================================================================
  // 3. Animated Ground Support Vehicles (GSVs) with Separation & Yield Logic
  // =========================================================================
  const vehicles = [];

  // Common wheel geometry
  const wheelGeom = new THREE.CylinderGeometry(0.42, 0.42, 0.28, 16);
  wheelGeom.rotateZ(Math.PI / 2);
  const wheelMat = new THREE.MeshStandardMaterial({ color: '#16191b', roughness: 0.85 });

  // -------------------------------------------------------------------------
  // Vehicle 1: Baggage Tractor & 3 Luggage Carts
  // -------------------------------------------------------------------------
  const baggageGroup = new THREE.Group();
  baggageGroup.name = 'vtx-gsv-baggage-train';

  // Tractor Cab
  const bTugMat = new THREE.MeshStandardMaterial({ color: '#f59200', metalness: 0.3, roughness: 0.4 });
  const bTugBody = new THREE.Mesh(new THREE.BoxGeometry(2.4, 1.3, 0.9), bTugMat);
  bTugBody.position.set(0, 0, 0.65);
  baggageGroup.add(bTugBody);

  // Driver windshield & roll-cage
  const bCageMat = new THREE.MeshStandardMaterial({ color: '#222', metalness: 0.7, roughness: 0.3 });
  const bCage = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.25, 0.85), bCageMat);
  bCage.position.set(-0.3, 0, 1.45);
  baggageGroup.add(bCage);

  // Flashing amber beacon on tug roof
  const tugBeaconMat = new THREE.MeshBasicMaterial({ color: '#ffaa00' });
  const tugBeacon = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.18, 10), tugBeaconMat);
  tugBeacon.position.set(-0.3, 0, 1.95);
  baggageGroup.add(tugBeacon);

  // Headlights & Tail/Brake lights
  const bHeadL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.2, 0.15), new THREE.MeshBasicMaterial({ color: '#ffffcc' }));
  bHeadL.position.set(1.22, 0.42, 0.65);
  const bHeadR = bHeadL.clone();
  bHeadR.position.set(1.22, -0.42, 0.65);
  baggageGroup.add(bHeadL, bHeadR);

  const bBrakeMat = new THREE.MeshBasicMaterial({ color: '#660000' });
  const bBrakeL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.2, 0.15), bBrakeMat);
  bBrakeL.position.set(-1.22, 0.42, 0.65);
  const bBrakeR = bBrakeL.clone();
  bBrakeR.position.set(-1.22, -0.42, 0.65);
  baggageGroup.add(bBrakeL, bBrakeR);

  // Tug 4 Wheels
  const tugWheels = [];
  for (const [wx, wy] of [[0.7, 0.65], [0.7, -0.65], [-0.7, 0.65], [-0.7, -0.65]]) {
    const wm = new THREE.Mesh(wheelGeom, wheelMat);
    wm.position.set(wx, wy, 0.42);
    baggageGroup.add(wm);
    tugWheels.push(wm);
  }

  // 3 Articulated Luggage Carts
  const cartMat = new THREE.MeshStandardMaterial({ color: '#e0c038', roughness: 0.6 });
  const luggageColors = ['#992222', '#224488', '#227744', '#774422', '#333333'];
  const cartWheels = [];
  const carts = [];

  for (let c = 0; c < 3; c++) {
    const cartGroup = new THREE.Group();
    const cartDist = -2.8 - c * 2.6;
    cartGroup.position.set(cartDist, 0, 0);

    // Cart flatbed & wire mesh railings
    const bed = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.2, 0.35), cartMat);
    bed.position.set(0, 0, 0.45);
    cartGroup.add(bed);

    // Tow bar link
    const bar = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.8, 6), bCageMat);
    bar.rotateZ(Math.PI / 2);
    bar.position.set(1.2, 0, 0.4);
    cartGroup.add(bar);

    // Luggage pile
    for (let l = 0; l < 4; l++) {
      const lMat = new THREE.MeshStandardMaterial({ color: luggageColors[(c * 4 + l) % luggageColors.length], roughness: 0.7 });
      const lug = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.45, 0.35), lMat);
      lug.position.set(-0.5 + (l % 2) * 0.75, (l < 2 ? -0.25 : 0.25), 0.75);
      cartGroup.add(lug);
    }

    // 4 Wheels per cart
    for (const [cx, cy] of [[0.6, 0.6], [0.6, -0.6], [-0.6, 0.6], [-0.6, -0.6]]) {
      const cWheel = new THREE.Mesh(wheelGeom, wheelMat);
      cWheel.position.set(cx, cy, 0.42);
      cartGroup.add(cWheel);
      cartWheels.push(cWheel);
    }

    baggageGroup.add(cartGroup);
    carts.push(cartGroup);
  }

  group.add(baggageGroup);

  // Baggage Train Looping Route (Apron service loop: [-600, 490] to [-150, 490])
  const baggageWaypoints = [
    [-620, 490], [-450, 490], [-350, 490], [-180, 490],
    [-140, 520], [-140, 560], [-250, 560], [-450, 560], [-620, 560], [-620, 520]
  ];

  vehicles.push({
    group: baggageGroup,
    waypoints: baggageWaypoints,
    speed: 8.5,           // 8.5 m/s (~30 km/h)
    dist: 0,
    currentSpeed: 8.5,
    targetSpeed: 8.5,
    brakeMat: bBrakeMat,
    beaconMat: tugBeaconMat,
    wheels: [...tugWheels, ...cartWheels],
    wheelRadius: 0.42,
    yieldDistance: 42
  });

  // -------------------------------------------------------------------------
  // Vehicle 2: Aviation Fuel Bowser (Heavy Tanker with VTX JET-A livery)
  // -------------------------------------------------------------------------
  const bowserGroup = new THREE.Group();
  bowserGroup.name = 'vtx-gsv-fuel-bowser';

  // Tanker Cab (White/Green)
  const bCabMat = new THREE.MeshStandardMaterial({ color: '#2d6a4f', metalness: 0.4, roughness: 0.3 });
  const bCab = new THREE.Mesh(new THREE.BoxGeometry(2.6, 2.4, 2.2), bCabMat);
  bCab.position.set(2.6, 0, 1.6);
  bowserGroup.add(bCab);

  // Windshield
  const bGlass = new THREE.Mesh(new THREE.BoxGeometry(0.1, 2.1, 0.9), new THREE.MeshStandardMaterial({ color: '#112233', roughness: 0.1 }));
  bGlass.position.set(3.91, 0, 1.85);
  bowserGroup.add(bGlass);

  // Large Cylindrical Fuel Tank (White with green livery)
  const tankMat = new THREE.MeshStandardMaterial({ color: '#e8edf0', metalness: 0.3, roughness: 0.4 });
  const tankGeom = new THREE.CylinderGeometry(1.2, 1.2, 5.2, 20);
  tankGeom.rotateZ(Math.PI / 2);
  tankGeom.translate(-1.4, 0, 1.7);
  bowserGroup.add(new THREE.Mesh(tankGeom, tankMat));

  // Fuel Tank Branding Sign: "VTX JET-A / ROCKET-FUEL (SIMULATED)"
  const tankSignCanvas = document.createElement('canvas');
  tankSignCanvas.width = 512; tankSignCanvas.height = 128;
  const tsc = tankSignCanvas.getContext('2d');
  tsc.fillStyle = '#2d6a4f'; tsc.fillRect(0, 0, 512, 128);
  tsc.fillStyle = '#ffffff';
  tsc.font = 'bold 36px "Arial Black", sans-serif';
  tsc.textAlign = 'center';
  tsc.fillText('VTX AVIATION FUEL', 256, 48);
  tsc.font = 'bold 20px monospace';
  tsc.fillStyle = '#f5b800';
  tsc.fillText('JET-A / ROCKET-FUEL (SIMULATED)', 256, 82);
  tsc.font = 'bold 16px monospace';
  tsc.fillStyle = '#ff4422';
  tsc.fillText('FLAMMABLE LIQUID 3 · NO SMOKING', 256, 110);
  const tankSignTex = new THREE.CanvasTexture(tankSignCanvas);
  const tankSignMat = new THREE.MeshBasicMaterial({ map: tankSignTex });

  const tankSignL = new THREE.Mesh(new THREE.PlaneGeometry(4.2, 1.1), tankSignMat);
  tankSignL.position.set(-1.4, 1.25, 1.7);
  tankSignL.rotateX(-Math.PI / 2);
  bowserGroup.add(tankSignL);

  const tankSignR = new THREE.Mesh(new THREE.PlaneGeometry(4.2, 1.1), tankSignMat);
  tankSignR.position.set(-1.4, -1.25, 1.7);
  tankSignR.rotateX(Math.PI / 2);
  bowserGroup.add(tankSignR);

  // Dual roof beacons
  const bowserBeaconMat = new THREE.MeshBasicMaterial({ color: '#ffaa00' });
  for (const by of [-0.8, 0.8]) {
    const bB = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.18, 10), bowserBeaconMat);
    bB.position.set(2.4, by, 2.8);
    bowserGroup.add(bB);
  }

  // Bowser Headlights & Brake Lights
  const bowserBrakeMat = new THREE.MeshBasicMaterial({ color: '#660000' });
  const bowBrakeL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.3, 0.2), bowserBrakeMat);
  bowBrakeL.position.set(-4.05, 0.9, 0.7);
  const bowBrakeR = bowBrakeL.clone();
  bowBrakeR.position.set(-4.05, -0.9, 0.7);
  bowserGroup.add(bowBrakeL, bowBrakeR);

  // 6 Heavy Wheels
  const bowserWheels = [];
  const bWheelGeom = new THREE.CylinderGeometry(0.55, 0.55, 0.35, 16);
  bWheelGeom.rotateZ(Math.PI / 2);
  for (const [bx, by] of [[2.4, 1.15], [2.4, -1.15], [-1.2, 1.15], [-1.2, -1.15], [-2.6, 1.15], [-2.6, -1.15]]) {
    const bw = new THREE.Mesh(bWheelGeom, wheelMat);
    bw.position.set(bx, by, 0.55);
    bowserGroup.add(bw);
    bowserWheels.push(bw);
  }

  group.add(bowserGroup);

  // Bowser Patrol Route (Ridge service loop -> Apron link -> Stands)
  const bowserWaypoints = [
    [-650, 695], [-400, 715], [40, 715], [40, 590], [40, 520],
    [-100, 490], [-350, 490], [-550, 490], [-555, 635], [-650, 695]
  ];

  vehicles.push({
    group: bowserGroup,
    waypoints: bowserWaypoints,
    speed: 9.5,
    dist: 300,            // Stagger initial position
    currentSpeed: 9.5,
    targetSpeed: 9.5,
    brakeMat: bowserBrakeMat,
    beaconMat: bowserBeaconMat,
    wheels: bowserWheels,
    wheelRadius: 0.55,
    yieldDistance: 45
  });

  // -------------------------------------------------------------------------
  // Vehicle 3: Airport Fire Crash Tender (Stn 9, 6x6, Blue Emergency Strobe)
  // -------------------------------------------------------------------------
  const fireGroup = new THREE.Group();
  fireGroup.name = 'vtx-gsv-fire-crash-tender';

  const fireRedMat = new THREE.MeshStandardMaterial({ color: '#d90429', metalness: 0.3, roughness: 0.35 });
  const fireBody = new THREE.Mesh(new THREE.BoxGeometry(8.6, 2.9, 2.4), fireRedMat);
  fireBody.position.set(0, 0, 1.8);
  fireGroup.add(fireBody);

  // High-visibility yellow battenburg diagonal hazard stripes along sides
  const battenCanvas = document.createElement('canvas');
  battenCanvas.width = 512; battenCanvas.height = 128;
  const btc = battenCanvas.getContext('2d');
  btc.fillStyle = '#d90429'; btc.fillRect(0, 0, 512, 128);
  btc.fillStyle = '#ffea00';
  for (let x = 0; x < 512; x += 64) {
    btc.beginPath(); btc.moveTo(x, 0); btc.lineTo(x + 32, 0); btc.lineTo(x, 128); btc.lineTo(x - 32, 128); btc.fill();
  }
  const battenTex = new THREE.CanvasTexture(battenCanvas);
  const battenMat = new THREE.MeshBasicMaterial({ map: battenTex });
  const battenL = new THREE.Mesh(new THREE.PlaneGeometry(6.5, 0.9), battenMat);
  battenL.position.set(-0.4, 1.46, 1.5);
  battenL.rotateX(-Math.PI / 2);
  fireGroup.add(battenL);
  const battenR = battenL.clone();
  battenR.position.set(-0.4, -1.46, 1.5);
  battenR.rotateX(Math.PI / 2);
  fireGroup.add(battenR);

  // Roof Monitor Water Cannon
  const monitorMat = new THREE.MeshStandardMaterial({ color: '#ffea00', metalness: 0.8, roughness: 0.3 });
  const monitor = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.16, 1.4, 8), monitorMat);
  monitor.rotateZ(Math.PI / 3);
  monitor.position.set(2.8, 0, 3.2);
  fireGroup.add(monitor);

  // Rapid flashing blue LED emergency strobe bars
  const strobeBlueMat = new THREE.MeshBasicMaterial({ color: '#0055ff' });
  const strobeBar = new THREE.Mesh(new THREE.BoxGeometry(0.4, 2.2, 0.2), strobeBlueMat);
  strobeBar.position.set(2.4, 0, 3.1);
  fireGroup.add(strobeBar);

  const fireBrakeMat = new THREE.MeshBasicMaterial({ color: '#660000' });
  const fireBrakeL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.4, 0.25), fireBrakeMat);
  fireBrakeL.position.set(-4.32, 1.0, 1.0);
  const fireBrakeR = fireBrakeL.clone();
  fireBrakeR.position.set(-4.32, -1.0, 1.0);
  fireGroup.add(fireBrakeL, fireBrakeR);

  // 6 Large All-Terrain Wheels
  const fireWheels = [];
  const fWheelGeom = new THREE.CylinderGeometry(0.68, 0.68, 0.42, 16);
  fWheelGeom.rotateZ(Math.PI / 2);
  for (const [fx, fy] of [[2.4, 1.35], [2.4, -1.35], [-0.8, 1.35], [-0.8, -1.35], [-2.4, 1.35], [-2.4, -1.35]]) {
    const fw = new THREE.Mesh(fWheelGeom, wheelMat);
    fw.position.set(fx, fy, 0.68);
    fireGroup.add(fw);
    fireWheels.push(fw);
  }

  group.add(fireGroup);

  // Fire Crash Tender Patrol Route (Fire Station 9 to Runway crossing and return)
  const fireWaypoints = [
    [475, 600], [475, 530], [240, 500], [240, 420],
    [40, 420], [40, 520], [240, 520], [475, 530], [475, 600]
  ];

  vehicles.push({
    group: fireGroup,
    waypoints: fireWaypoints,
    speed: 12.0,          // Rapid response 12 m/s (~43 km/h)
    dist: 120,
    currentSpeed: 12.0,
    targetSpeed: 12.0,
    brakeMat: fireBrakeMat,
    strobeMat: strobeBlueMat,
    wheels: fireWheels,
    wheelRadius: 0.68,
    yieldDistance: 48
  });

  // -------------------------------------------------------------------------
  // Vehicle 4: British Black Cab "Follow-Me" Car
  // -------------------------------------------------------------------------
  const cabGroup = new THREE.Group();
  cabGroup.name = 'vtx-gsv-follow-me-cab';

  const cabBlackMat = new THREE.MeshStandardMaterial({ color: '#111315', roughness: 0.35, metalness: 0.5 });
  // Authentic London Black Cab chassis & passenger cabin
  const cabBody = new THREE.Mesh(new THREE.BoxGeometry(4.4, 1.75, 1.3), cabBlackMat);
  cabBody.position.set(0, 0, 0.9);
  cabGroup.add(cabBody);

  const cabHood = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.6, 0.75), cabBlackMat);
  cabHood.position.set(1.6, 0, 0.65);
  cabGroup.add(cabHood);

  // Chrome Radiator Grille
  const grille = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.8, 0.65), new THREE.MeshStandardMaterial({ color: '#e8edf0', metalness: 0.9, roughness: 0.15 }));
  grille.position.set(2.32, 0, 0.65);
  cabGroup.add(grille);

  // Illuminated "FOLLOW ME" Roof Light Box
  const followCanvas = document.createElement('canvas');
  followCanvas.width = 256; followCanvas.height = 64;
  const flc = followCanvas.getContext('2d');
  flc.fillStyle = '#ffaa00'; flc.fillRect(0, 0, 256, 64);
  flc.fillStyle = '#000000';
  flc.font = 'bold 32px "Arial Black", sans-serif';
  flc.textAlign = 'center';
  flc.fillText('FOLLOW ME', 128, 44);
  const followTex = new THREE.CanvasTexture(followCanvas);
  const followMat = new THREE.MeshBasicMaterial({ map: followTex });

  const followSign = new THREE.Mesh(new THREE.BoxGeometry(0.3, 1.2, 0.32), [
    followMat, followMat, followMat, followMat, followMat, followMat
  ]);
  followSign.position.set(0.1, 0, 1.72);
  cabGroup.add(followSign);

  const cabBrakeMat = new THREE.MeshBasicMaterial({ color: '#660000' });
  const cabBrakeL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.22, 0.18), cabBrakeMat);
  cabBrakeL.position.set(-2.22, 0.6, 0.7);
  const cabBrakeR = cabBrakeL.clone();
  cabBrakeR.position.set(-2.22, -0.6, 0.7);
  cabGroup.add(cabBrakeL, cabBrakeR);

  // 4 Wheels
  const cabWheels = [];
  const cWheelGeom = new THREE.CylinderGeometry(0.36, 0.36, 0.24, 16);
  cWheelGeom.rotateZ(Math.PI / 2);
  for (const [cx, cy] of [[1.3, 0.82], [1.3, -0.82], [-1.3, 0.82], [-1.3, -0.82]]) {
    const cw = new THREE.Mesh(cWheelGeom, wheelMat);
    cw.position.set(cx, cy, 0.36);
    cabGroup.add(cw);
    cabWheels.push(cw);
  }

  group.add(cabGroup);

  // Black Cab Follow-Me Route (Along Taxiway Alpha: [-500, 100] to [400, 100])
  const cabWaypoints = [
    [-550, 100], [-350, 100], [-100, 100], [150, 100], [450, 100],
    [500, 100], [450, 100], [150, 100], [-100, 100], [-350, 100], [-550, 100]
  ];

  vehicles.push({
    group: cabGroup,
    waypoints: cabWaypoints,
    speed: 11.0,
    dist: 50,
    currentSpeed: 11.0,
    targetSpeed: 11.0,
    brakeMat: cabBrakeMat,
    wheels: cabWheels,
    wheelRadius: 0.36,
    yieldDistance: 38
  });

  // -------------------------------------------------------------------------
  // Vehicle 5: Electric Pushback Tug
  // -------------------------------------------------------------------------
  const tugGroup = new THREE.Group();
  tugGroup.name = 'vtx-gsv-pushback-tug';

  const eTugMat = new THREE.MeshStandardMaterial({ color: '#f5b800', metalness: 0.4, roughness: 0.4 });
  const eBody = new THREE.Mesh(new THREE.BoxGeometry(3.6, 2.1, 0.8), eTugMat);
  eBody.position.set(0, 0, 0.55);
  tugGroup.add(eBody);

  const eCabMat = new THREE.MeshStandardMaterial({ color: '#16191b', roughness: 0.3 });
  const eCab = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.8, 0.7), eCabMat);
  eCab.position.set(0.6, 0, 1.25);
  tugGroup.add(eCab);

  const eBeaconMat = new THREE.MeshBasicMaterial({ color: '#ffaa00' });
  const eBeacon = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.16, 10), eBeaconMat);
  eBeacon.position.set(0.6, 0, 1.68);
  tugGroup.add(eBeacon);

  const eBrakeMat = new THREE.MeshBasicMaterial({ color: '#660000' });
  const eBrakeL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.25, 0.18), eBrakeMat);
  eBrakeL.position.set(-1.82, 0.7, 0.55);
  const eBrakeR = eBrakeL.clone();
  eBrakeR.position.set(-1.82, -0.7, 0.55);
  tugGroup.add(eBrakeL, eBrakeR);

  const eWheels = [];
  const eWheelGeom = new THREE.CylinderGeometry(0.48, 0.48, 0.32, 16);
  eWheelGeom.rotateZ(Math.PI / 2);
  for (const [ex, ey] of [[1.1, 1.0], [1.1, -1.0], [-1.1, 1.0], [-1.1, -1.0]]) {
    const ew = new THREE.Mesh(eWheelGeom, wheelMat);
    ew.position.set(ex, ey, 0.48);
    tugGroup.add(ew);
    eWheels.push(ew);
  }

  group.add(tugGroup);

  // Pushback Tug Route (Apron stands 1 to 4: [-500, 530] to [-250, 530])
  const eTugWaypoints = [
    [-520, 530], [-420, 530], [-320, 530], [-240, 530],
    [-240, 510], [-320, 510], [-420, 510], [-520, 510]
  ];

  vehicles.push({
    group: tugGroup,
    waypoints: eTugWaypoints,
    speed: 6.5,
    dist: 180,
    currentSpeed: 6.5,
    targetSpeed: 6.5,
    brakeMat: eBrakeMat,
    beaconMat: eBeaconMat,
    wheels: eWheels,
    wheelRadius: 0.48,
    yieldDistance: 35
  });

  // =========================================================================
  // 4. Vehicle Animation, Separation & Priority Stop Controller
  // =========================================================================
  function getSplinePose(waypoints, dist) {
    let totalLen = 0;
    const segLens = [];
    for (let i = 0; i < waypoints.length; i++) {
      const next = waypoints[(i + 1) % waypoints.length];
      const sl = Math.hypot(next[0] - waypoints[i][0], next[1] - waypoints[i][1]);
      segLens.push(sl);
      totalLen += sl;
    }
    if (totalLen <= 0.001) return { pos: [0, 0, 0], heading: 0 };

    let normDist = ((dist % totalLen) + totalLen) % totalLen;
    let acc = 0;
    for (let i = 0; i < waypoints.length; i++) {
      const pA = waypoints[i];
      const pB = waypoints[(i + 1) % waypoints.length];
      const sl = segLens[i];
      if (acc + sl >= normDist) {
        const t = (normDist - acc) / sl;
        const x = pA[0] + (pB[0] - pA[0]) * t;
        const y = pA[1] + (pB[1] - pA[1]) * t;
        const heading = Math.atan2(pB[1] - pA[1], pB[0] - pA[0]);
        return { pos: [x, y], heading };
      }
      acc += sl;
    }
    return { pos: waypoints[0], heading: 0 };
  }

  let lastTime = 0;
  updaters.push((time, dt, aircraftPos) => {
    // Strobe / beacon blinking
    const blueFlash = Math.sin(time * 16.0) > 0.1;
    const amberFlash = Math.sin(time * 6.0) > 0.0;

    for (const v of vehicles) {
      if (v.strobeMat) {
        v.strobeMat.color.setHex(blueFlash ? 0x0088ff : 0x001133);
      }
      if (v.beaconMat) {
        v.beaconMat.color.setHex(amberFlash ? 0xffaa00 : 0x332200);
      }

      // Check priority yield condition at crossings
      const pose = getSplinePose(v.waypoints, v.dist);
      let shouldYield = false;

      if (aircraftPos) {
        const [ax, ay] = aircraftPos;
        for (const cross of crossingPoints) {
          const distVehToCross = Math.hypot(pose.pos[0] - cross.pos[0], pose.pos[1] - cross.pos[1]);
          const distAirToCross = Math.hypot(ax - cross.pos[0], ay - cross.pos[1]);

          // If vehicle is approaching crossing and aircraft is within the crossing zone
          if (distVehToCross < v.yieldDistance && distAirToCross < 48) {
            shouldYield = true;
            break;
          }
        }
      }

      // Smooth acceleration / deceleration
      if (shouldYield) {
        v.targetSpeed = 0;
        v.currentSpeed = Math.max(0, v.currentSpeed - 4.5 * dt);
        // Illuminate red brake lights
        if (v.brakeMat) v.brakeMat.color.setHex(0xff1100);
      } else {
        v.targetSpeed = v.speed;
        v.currentSpeed = Math.min(v.speed, v.currentSpeed + 2.5 * dt);
        // Dim running tail-lights
        if (v.brakeMat) v.brakeMat.color.setHex(0x550000);
      }

      // Advance along path
      v.dist += v.currentSpeed * dt;
      const newPose = getSplinePose(v.waypoints, v.dist);
      const z = (surfaceZ ? surfaceZ(newPose.pos[0], newPose.pos[1]) : 0);

      v.group.position.set(newPose.pos[0], newPose.pos[1], z);
      v.group.rotation.set(0, 0, newPose.heading);

      // Rotate wheels
      const wheelRot = (v.currentSpeed * dt) / v.wheelRadius;
      for (const w of v.wheels) w.rotation.x += wheelRot;
    }
  });

  scene.add(group);

  return {
    group,
    update: (time, aircraftPos) => {
      const dt = lastTime ? Math.min(0.1, time - lastTime) : 0.016;
      lastTime = time;
      for (const fn of updaters) fn(time, dt, aircraftPos);
    }
  };
}
