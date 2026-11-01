import os

facility_code = '''
// =========================================================================
// PHASE 3: VTX FLIGHT ACADEMY & AIRPORT FACILITIES COMPLEX
// Authoritative coordinates derived from VTX_fictional_airport_layout_proposal.json
// Sitting on the northern scenic ridge overlooking the entire airport basin.
// =========================================================================

function makeFacilitySign(text, subtext, bgColor = '#181b1e', textColor = '#f5b800') {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 128;
  const g = c.getContext('2d');
  g.fillStyle = bgColor; g.fillRect(0, 0, 512, 128);
  g.strokeStyle = textColor; g.lineWidth = 6; g.strokeRect(3, 3, 506, 122);
  g.fillStyle = textColor;
  g.font = 'bold 36px "Arial Black", Impact, sans-serif';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText(text, 256, subtext ? 46 : 64);
  if (subtext) {
    g.fillStyle = '#e8e6d8';
    g.font = 'bold 20px Arial, sans-serif';
    g.fillText(subtext, 256, 88);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 8;
  return new THREE.MeshBasicMaterial({ map: tex });
}

function buildFacilityComplexes(group, updaters) {
  const facilitiesGroup = new THREE.Group();
  facilitiesGroup.name = 'vtx-facilities-complex';

  const concMat = new THREE.MeshStandardMaterial({ color: '#555b62', roughness: 0.65 });
  const darkWall = new THREE.MeshStandardMaterial({ color: '#252a2f', roughness: 0.5 });
  const glassMat = new THREE.MeshStandardMaterial({ color: '#0b1e2e', roughness: 0.1, metalness: 0.8, emissive: '#1a557a', emissiveIntensity: 0.4 });
  const yellowTrim = new THREE.MeshStandardMaterial({ color: '#f5b800', roughness: 0.4, metalness: 0.2 });
  const redMat = new THREE.MeshStandardMaterial({ color: '#c72418', roughness: 0.5 });

  // -----------------------------------------------------------------------
  // 1. VTX-SCHOOL: Flight Academy & Simulation Training Centre [-555, 635, 22.2]
  // -----------------------------------------------------------------------
  {
    const cx = -555, cy = 635, cz = 22.2;
    const b = new THREE.Group(); b.position.set(cx, cy, cz);
    
    // Main Training Hangar (54m x 28m x 14m)
    const main = new THREE.Mesh(new THREE.BoxGeometry(54, 28, 14), darkWall);
    main.position.set(0, 0, 7); main.castShadow = true; b.add(main);
    
    // Front Glass Briefing Atrium (26m x 8m x 7m)
    const atrium = new THREE.Mesh(new THREE.BoxGeometry(26, 8, 7), glassMat);
    atrium.position.set(0, -16, 3.5); atrium.castShadow = true; b.add(atrium);
    
    // Roof Sign: VTX FLIGHT ACADEMY
    const signMat = makeFacilitySign('VTX FLIGHT ACADEMY', 'SIMULATION TRAINING CENTRE · GLOUCESTER WING', '#111417', '#f5b800');
    const sign = new THREE.Mesh(new THREE.BoxGeometry(28, 0.4, 4.2), [darkWall, darkWall, darkWall, darkWall, signMat, darkWall]);
    sign.position.set(0, -14.2, 16.5); b.add(sign);
    
    // Arthur Finch Compliance Banner
    const finchSign = makeFacilitySign('ARTHUR FINCH DIRECTIVE', 'LESSON 1: STRICTLY NO BANANAS IN COCKPIT', '#3b120c', '#ffdd55');
    const fsign = new THREE.Mesh(new THREE.BoxGeometry(20, 0.4, 3.0), [darkWall, darkWall, darkWall, darkWall, finchSign, darkWall]);
    fsign.position.set(0, -14.2, 9.5); b.add(fsign);
    
    // 2 x Flight Simulator Motion Pods out front
    for (const sx of [-18, 18]) {
      const pylon = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.7, 3, 8), darkWall);
      pylon.rotateX(Math.PI / 2); pylon.position.set(sx, -22, 1.5); b.add(pylon);
      const pod = new THREE.Mesh(new THREE.BoxGeometry(5.5, 5.5, 3.8), yellowTrim);
      pod.position.set(sx, -22, 4.2); pod.castShadow = true; b.add(pod);
      const podGlass = new THREE.Mesh(new THREE.BoxGeometry(5.6, 2.2, 1.8), glassMat);
      podGlass.position.set(sx, -24, 4.2); b.add(podGlass);
      updaters.push((t) => { pod.rotation.z = Math.sin(t * 1.5 + sx) * 0.12; pod.rotation.x = Math.cos(t * 1.2 + sx) * 0.08; });
    }
    facilitiesGroup.add(b);
  }

  // -----------------------------------------------------------------------
  // 2. VTX-HQ: Dispatch & Passenger Terminal [-200, 620, 30.6]
  // -----------------------------------------------------------------------
  {
    const cx = -200, cy = 620, cz = 30.6;
    const b = new THREE.Group(); b.position.set(cx, cy, cz);
    
    // Concourse Terminal Building (68m x 32m x 16m)
    const main = new THREE.Mesh(new THREE.BoxGeometry(68, 32, 16), concMat);
    main.position.set(0, 0, 8); main.castShadow = true; b.add(main);
    
    // Large Curved Glass Front (56m x 6m x 11m)
    const glass = new THREE.Mesh(new THREE.BoxGeometry(56, 6, 11), glassMat);
    glass.position.set(0, -17, 7.5); b.add(glass);
    
    // Cantilevered Entrance Canopy (36m x 14m x 1.2m)
    const canopy = new THREE.Mesh(new THREE.BoxGeometry(36, 14, 1.2), yellowTrim);
    canopy.position.set(0, -22, 6.8); canopy.castShadow = true; b.add(canopy);
    for (const px of [-16, 0, 16]) {
      const post = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 6.8, 8), darkWall);
      post.rotateX(Math.PI / 2); post.position.set(px, -28, 3.4); b.add(post);
    }
    
    // Roof Clock Tower (7m x 7m x 24m)
    const tower = new THREE.Mesh(new THREE.BoxGeometry(7, 7, 24), darkWall);
    tower.position.set(24, 0, 16); tower.castShadow = true; b.add(tower);
    const clockFace = new THREE.Mesh(new THREE.CircleGeometry(2.2, 16), new THREE.MeshBasicMaterial({ color: '#fff9e6' }));
    clockFace.position.set(24, -3.6, 24); clockFace.rotateX(Math.PI / 2); b.add(clockFace);
    
    // Terminal Sign: VADER'S TAXIS WORLD HEADQUARTERS
    const signMat = makeFacilitySign('VADER’S TAXIS AVIATION HQ', 'MAIN PASSENGER TERMINAL & DISPATCH CONCOURSE', '#0f171e', '#f5b800');
    const sign = new THREE.Mesh(new THREE.BoxGeometry(38, 0.4, 4.6), [darkWall, darkWall, darkWall, darkWall, signMat, darkWall]);
    sign.position.set(0, -16.2, 18.5); b.add(sign);
    facilitiesGroup.add(b);
  }

  // -----------------------------------------------------------------------
  // 3. VTX-ENGINEERING: MRO & Engineering Facility [40, 590, 32.8]
  // -----------------------------------------------------------------------
  {
    const cx = 40, cy = 590, cz = 32.8;
    const b = new THREE.Group(); b.position.set(cx, cy, cz);
    
    // Heavy Maintenance Bay (62m x 38m x 18m)
    const main = new THREE.Mesh(new THREE.BoxGeometry(62, 38, 18), darkWall);
    main.position.set(0, 0, 9); main.castShadow = true; b.add(main);
    
    // External Overhead Gantry Crane Frame (44m span x 16m out x 16m high)
    const gantryMat = new THREE.MeshStandardMaterial({ color: '#f5b800', metalness: 0.6, roughness: 0.3 });
    const beam = new THREE.Mesh(new THREE.BoxGeometry(44, 1.2, 1.4), gantryMat);
    beam.position.set(0, -26, 15); b.add(beam);
    for (const gx of [-21, 21]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.2, 15), gantryMat);
      leg.position.set(gx, -26, 7.5); b.add(leg);
    }
    
    // 3 x Industrial Ventilation Stacks on roof
    for (let i = 0; i < 3; i++) {
      const stack = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.2, 9, 8), darkWall);
      stack.rotateX(Math.PI / 2); stack.position.set(-18 + i * 18, 8, 22.5); b.add(stack);
    }
    
    // Facility Sign: VTX ENGINEERING
    const signMat = makeFacilitySign('VTX ENGINEERING & MRO', 'PROTOTYPE SKUNKWORKS · CERTIFIED DUCT REPAIRS', '#14171a', '#f5b800');
    const sign = new THREE.Mesh(new THREE.BoxGeometry(34, 0.4, 4.4), [darkWall, darkWall, darkWall, darkWall, signMat, darkWall]);
    sign.position.set(0, -19.2, 19.5); b.add(sign);
    facilitiesGroup.add(b);
  }

  // -----------------------------------------------------------------------
  // 4. VTX-TOWER: Air Traffic Control Tower [240, 555, 28.4]
  // -----------------------------------------------------------------------
  {
    const cx = 240, cy = 555, cz = 28.4;
    const b = new THREE.Group(); b.position.set(cx, cy, cz);
    
    // Tower Hexagonal Concrete Shaft (10m diam, 42m high)
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(4.5, 5.5, 42, 6), concMat);
    shaft.rotateX(Math.PI / 2); shaft.position.set(0, 0, 21); shaft.castShadow = true; b.add(shaft);
    
    // 360-degree Observation Cab (16m diam, 6.5m high)
    const cab = new THREE.Mesh(new THREE.CylinderGeometry(7.5, 6.0, 6.5, 12), glassMat);
    cab.rotateX(Math.PI / 2); cab.position.set(0, 0, 44); cab.castShadow = true; b.add(cab);
    
    // Roof Radome & Radar Mast
    const radome = new THREE.Mesh(new THREE.SphereGeometry(2.4, 12, 10), new THREE.MeshStandardMaterial({ color: '#e8eaec', roughness: 0.3 }));
    radome.position.set(0, 0, 49.5); b.add(radome);
    
    const radar = new THREE.Mesh(new THREE.BoxGeometry(4.2, 0.5, 0.6), yellowTrim);
    radar.position.set(0, 0, 53); b.add(radar);
    updaters.push((t) => { radar.rotation.z = t * 2.8; });
    
    // Flashing red obstruction beacon
    const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.5, 8, 8), new THREE.MeshBasicMaterial({ color: '#ff2211' }));
    beacon.position.set(0, 0, 54.2); b.add(beacon);
    updaters.push((t) => { beacon.material.color.setHex((Math.sin(t * 3.5) > 0.5) ? 0xff2211 : 0x220000); });
    
    // Tower Sign
    const signMat = makeFacilitySign('VTX CONTROL TOWER', 'AIR TRAFFIC SERVICES · 121.850 MHz', '#101418', '#f5b800');
    const sign = new THREE.Mesh(new THREE.BoxGeometry(16, 0.4, 3.2), [darkWall, darkWall, darkWall, darkWall, signMat, darkWall]);
    sign.position.set(0, -6.0, 39.5); b.add(sign);
    facilitiesGroup.add(b);
  }

  // -----------------------------------------------------------------------
  // 5. VTX-FIRE: Airport Rescue & Fire Fighting Station [475, 600, 24.1]
  // -----------------------------------------------------------------------
  {
    const cx = 475, cy = 600, cz = 24.1;
    const b = new THREE.Group(); b.position.set(cx, cy, cz);
    
    // Fire Station Main Building (44m x 24m x 12m)
    const main = new THREE.Mesh(new THREE.BoxGeometry(44, 24, 12), darkWall);
    main.position.set(0, 0, 6); main.castShadow = true; b.add(main);
    
    // 4 x Red Roll-Up Appliance Bays
    for (let i = 0; i < 4; i++) {
      const door = new THREE.Mesh(new THREE.BoxGeometry(7.5, 0.4, 6.5), redMat);
      door.position.set(-15 + i * 10, -12.1, 3.5); b.add(door);
    }
    
    // Hose Drying & Training Tower (5m x 5m x 18m)
    const hoseTower = new THREE.Mesh(new THREE.BoxGeometry(5, 5, 18), darkWall);
    hoseTower.position.set(20, 4, 9); hoseTower.castShadow = true; b.add(hoseTower);
    
    // Parked Rapid Intervention Fire Tender (out front)
    const tender = new THREE.Mesh(new THREE.BoxGeometry(8, 3.2, 3.4), redMat);
    tender.position.set(-5, -18, 1.7); tender.castShadow = true; b.add(tender);
    const cabWindow = new THREE.Mesh(new THREE.BoxGeometry(3, 3.3, 1.4), glassMat);
    cabWindow.position.set(-7, -18, 2.4); b.add(cabWindow);
    const blueLight = new THREE.Mesh(new THREE.SphereGeometry(0.3, 8, 8), new THREE.MeshBasicMaterial({ color: '#2070ff' }));
    blueLight.position.set(-6, -18, 3.7); b.add(blueLight);
    updaters.push((t) => { blueLight.material.color.setHex((Math.sin(t * 8) > 0) ? 0x2088ff : 0x001144); });
    
    // Station Sign
    const signMat = makeFacilitySign('VTX RESCUE & FIRE SERVICE', 'AIRPORT EMERGENCY RESPONSE · STATION 9', '#240808', '#ff4433');
    const sign = new THREE.Mesh(new THREE.BoxGeometry(30, 0.4, 4.0), [darkWall, darkWall, darkWall, darkWall, signMat, darkWall]);
    sign.position.set(0, -12.2, 13.5); b.add(sign);
    facilitiesGroup.add(b);
  }

  // -----------------------------------------------------------------------
  // 6. VTX-CARGO: Air Freight & Logistics Depot [680, 600, 22.2]
  // -----------------------------------------------------------------------
  {
    const cx = 680, cy = 600, cz = 22.2;
    const b = new THREE.Group(); b.position.set(cx, cy, cz);
    
    // Long Cargo Distribution Hub (66m x 28m x 13m)
    const main = new THREE.Mesh(new THREE.BoxGeometry(66, 28, 13), darkWall);
    main.position.set(0, 0, 6.5); main.castShadow = true; b.add(main);
    
    // 5 x Loading Dock Roller Shutters
    for (let i = 0; i < 5; i++) {
      const shutter = new THREE.Mesh(new THREE.BoxGeometry(8.5, 0.4, 5.5), concMat);
      shutter.position.set(-22 + i * 11, -14.1, 3.2); b.add(shutter);
    }
    
    // Stacked Sea Containers (Yellow, Blue, Green, Red)
    const colors = ['#f5b800', '#2570b0', '#2e7d32', '#c62828'];
    for (let i = 0; i < 6; i++) {
      const cMat = new THREE.MeshStandardMaterial({ color: colors[i % colors.length], roughness: 0.6 });
      const cont = new THREE.Mesh(new THREE.BoxGeometry(6.0, 2.4, 2.6), cMat);
      const row = Math.floor(i / 3), col = i % 3;
      cont.position.set(-18 + col * 7.5, -22, 1.3 + row * 2.6);
      cont.castShadow = true; b.add(cont);
    }
    
    // Cargo Depot Sign
    const signMat = makeFacilitySign('VADER’S TAXIS CARGO', 'WE MOVE ANYTHING (EXCEPT UNMARKED BANANAS)', '#16191c', '#f5b800');
    const sign = new THREE.Mesh(new THREE.BoxGeometry(36, 0.4, 4.4), [darkWall, darkWall, darkWall, darkWall, signMat, darkWall]);
    sign.position.set(0, -14.2, 14.8); b.add(sign);
    facilitiesGroup.add(b);
  }

  group.add(facilitiesGroup);
}
'''

with open('public/vtx-env/buildings.js', 'r', encoding='utf-8') as f:
    orig = f.read()

# Add buildFacilityComplexes before buildBuildings
if 'buildFacilityComplexes' not in orig:
    # Insert before export function buildBuildings
    idx = orig.find('export function buildBuildings(')
    assert idx > 0
    updated = orig[:idx] + facility_code + '\n' + orig[idx:]
    
    # Inside buildBuildings, call buildFacilityComplexes(group, updaters);
    target = 'scene.add(group);\n  return { group, update: (t) => updaters.forEach((u) => u(t)) };'
    assert target in updated
    replacement = 'buildFacilityComplexes(group, updaters);\n  scene.add(group);\n  return { group, update: (t) => updaters.forEach((u) => u(t)) };'
    updated = updated.replace(target, replacement)
    
    with open('public/vtx-env/buildings.js', 'w', encoding='utf-8') as f:
        f.write(updated)
    print("Added Phase 3 facility complexes to buildings.js successfully.")
else:
    print("buildFacilityComplexes already in buildings.js.")
