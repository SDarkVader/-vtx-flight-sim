// Visual treatment of the real VTX simulator aircraft.
// Swaps materials for aerospace-grade PBR finishes and adds visual detail
// to the existing rendered body nodes (so they follow physical articulation).
// Non-negotiable: airframe geometry, body poses, collision, and mass model are untouched.
import * as THREE from 'three';
import { makeCanvas, toTexture, carbonFiberTextures, brushedMetalTexture, cockpitDisplaysTexture } from './textures.js';
import {avionicsReadings} from '../cockpit-avionics.js?v=2';

const PEARL = new THREE.Color('#f0f4f6'), CARBON = new THREE.Color('#0c1013'), CYAN = new THREE.Color('#2fe3ff'), YEL = new THREE.Color('#f5b800');

function checkerTexture() {
  const c = makeCanvas(128, 16), g = c.getContext('2d');
  for (let i = 0; i < 16; i++) for (let j = 0; j < 2; j++) {
    g.fillStyle = (i + j) % 2 ? '#f5b800' : '#0f1113';
    g.fillRect(i * 8, j * 8, 8, 8);
  }
  const t = toTexture(c, { repeat: [8, 1], wrap: true });
  t.magFilter = THREE.NearestFilter;
  return t;
}

// Procedural stencil texture for duct and fuselage markings
function stencilTexture(text, subtext = '') {
  const c = makeCanvas(256, 64), g = c.getContext('2d');
  g.fillStyle = '#0f1113'; g.fillRect(0, 0, 256, 64);
  g.font = 'bold 20px "Arial Black", sans-serif';
  g.fillStyle = '#f5b800'; g.textAlign = 'center';
  g.fillText(text, 128, 28);
  if (subtext) {
    g.font = 'bold 12px "Courier New", monospace';
    g.fillStyle = '#e0e5ea';
    g.fillText(subtext, 128, 48);
  }
  return toTexture(c, { aniso: 4 });
}

function paintDuct(geo) {
  if (geo.userData.ductPainted) return;
  geo.userData.ductPainted = true;
  const p = geo.attributes.position, n = geo.attributes.normal, cols = new Float32Array(p.count * 3), c = new THREE.Color();
  geo.computeBoundingBox();
  const cx = (geo.boundingBox.min.x + geo.boundingBox.max.x) * .5;
  const cy = (geo.boundingBox.min.y + geo.boundingBox.max.y) * .5;
  for (let i = 0; i < p.count; i++) {
    const out = n.getX(i) * (p.getX(i) - cx) + n.getY(i) * (p.getY(i) - cy);
    const t = THREE.MathUtils.smoothstep(out, -.06, .14);
    c.copy(CARBON).lerp(PEARL, t);
    cols.set([c.r, c.g, c.b], i * 3);
  }
  geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));
}

export function enhanceAircraft(root, envTexture) {
  const cache = new Map(), replaced = new Set(), fx = { rotorDiscs: [], strobes: [], landingLights: [] };
  const make = (key, fn) => { if (!cache.has(key)) cache.set(key, fn()); return cache.get(key); };
  const phys = (o) => new THREE.MeshPhysicalMaterial({ side: THREE.DoubleSide, envMap: envTexture, ...o });

  const carbonTex = carbonFiberTextures();
  const brushedTex = brushedMetalTexture();
  const avionicsTex = cockpitDisplaysTexture();

  root.traverse((n) => {
    if (!n.isMesh || Array.isArray(n.material)) return;
    const body = n.userData.physical_body || '', kind = body.replace(/\d+$/, ''), old = n.material, name = old.name;
    let mat = null;
    switch (name) {
      case 'Laminated glazing nominal':
        // Aerospace optical canopy glazing with subtle cyan-sky solar tint & realistic Fresnel reflection
        mat = make(name, () => phys({
          color: '#8ac4d8', metalness: 0.05, roughness: 0.02, transparent: true,
          opacity: 0.18, envMapIntensity: 2.8, clearcoat: 1.0, clearcoatRoughness: 0.02,
          depthWrite: false, ior: 1.52, transmission: 0.88
        }));
        break;
      case 'Instrument glass':
        mat = make(name, () => new THREE.MeshStandardMaterial({
          map: avionicsTex, emissiveMap: avionicsTex, emissive: '#ffffff',
          emissiveIntensity: 1.2, roughness: 0.1, metalness: 0.1
        }));
        break;
      case 'Seat and trim':
        mat = make(name, () => phys({
          color: '#282f34', roughness: 0.65, metalness: 0.05,
          sheen: 0.5, sheenColor: new THREE.Color('#8fa4b0')
        }));
        break;
      case 'Duct inlet highlight':
        mat = make(name, () => phys({
          color: '#06323a', emissive: CYAN, emissiveIntensity: 3.5,
          roughness: 0.18, metalness: 0.2
        }));
        break;
      case 'CFRP woven reinforced':
        if (kind === 'nacelle') {
          paintDuct(n.geometry);
          mat = make('duct', () => phys({
            vertexColors: true, color: '#ffffff', roughness: 0.22,
            metalness: 0.08, clearcoat: 1.0, clearcoatRoughness: 0.04
          }));
        }
        break;
      case 'Aerospace aluminum surfaces':
        mat = kind === 'rotor'
          ? make('blade', () => phys({ color: '#202428', roughness: 0.32, metalness: 0.55, clearcoat: 0.45 }))
          : kind === 'nacelle'
          ? make('strut', () => phys({ color: '#e8edf0', roughness: 0.26, metalness: 0.4, clearcoat: 0.8 }))
          : make('alloy', () => phys({ color: '#b0b8bc', map: brushedTex, roughness: 0.3, metalness: 0.88 }));
        break;
      case 'Titanium nodes':
      case 'VTX V2 - titanium attachments':
      case 'VTX V3 / titanium forged joint':
      case 'VTX V4 / titanium articulated load fitting':
      case 'VTX V4 / machined light alloy':
        mat = make(name, () => {
          const m = old.clone();
          m.roughness = 0.24; m.metalness = 0.95; m.map = brushedTex; m.envMap = envTexture;
          return m;
        });
        break;
      case 'CFRP structural composite':
      case 'VTX V2 - carbon laminate':
      case 'VTX V4 / laminated CFRP primary spaceframe':
      case 'VTX V4 / braided CFRP secondary bracing':
      case 'VTX V3 / carbon triangulated primary structure':
        mat = make('cfrp_twill', () => phys({
          color: '#121619', map: carbonTex, roughness: 0.28,
          metalness: 0.15, clearcoat: 0.85, clearcoatRoughness: 0.1
        }));
        break;
      case 'VTX V3 / control torque path':
      case 'VTX V3 / independent power bus':
      case 'VTX V4 / monitored landing dampers':
      case 'Variable pitch actuators':
        mat = make(name, () => {
          const m = old.clone(); m.roughness = 0.32; m.envMap = envTexture; return m;
        });
        break;
      default: break;
    }
    if (mat && mat !== old) { replaced.add(old); n.material = mat; }
  });
  replaced.forEach((m) => m.dispose());

  const sub = (b) => root.getObjectByName(b);
  const checker = checkerTexture();
  const checkerMaterial = new THREE.MeshStandardMaterial({ map: checker, roughness: .5, metalness: .1 });

  // ---- Nacelle detailing & Livery (attached to nacelles and rotors) -----------
  for (let i = 1; i <= 4; i++) {
    const nac = sub('nacelle' + i), rot = sub('rotor' + i);
    if (!nac) continue;

    // Glowing cyan aerodynamic lip ring
    if (!nac.getObjectByName(`Phase2_Duct_Lip_Glow_F${i}`)) {
      const accent = new THREE.Mesh(
        new THREE.TorusGeometry(1.215, .016, 8, 96),
        new THREE.MeshStandardMaterial({ color: '#04282f', emissive: CYAN, emissiveIntensity: 3.5 })
      );
      accent.position.z = .27; accent.name = 'vtx-accent-ring'; accent.userData.pitch_axis = 'decor';
      nac.add(accent);
    }

    // Yellow and black taxi checkerboard livery band
    const sourceBand = nac.getObjectByName(`Phase2_Duct_Livery_Band_F${i}`);
    if (sourceBand?.isMesh) {
      sourceBand.material = checkerMaterial;
      // The supplied band is at the upper lip; the reference images place it
      // along the lower outer rim. This is a render-only livery adjustment.
      if (!sourceBand.userData.referenceBandPositioned) {
        sourceBand.position.z -= .335;
        sourceBand.userData.referenceBandPositioned = true;
      }
    } else {
      const band = new THREE.Mesh(new THREE.TorusGeometry(1.2, .03, 6, 96), checkerMaterial);
      band.position.z = .15; band.name = 'vtx-livery-band'; band.userData.pitch_axis = 'decor';
      nac.add(band);
    }

    // Rivet / fastener ring along the outer duct flange
    const rivetRing = new THREE.Mesh(
      new THREE.TorusGeometry(1.22, .008, 6, 96),
      new THREE.MeshStandardMaterial({ color: '#889098', metalness: .9, roughness: .25 })
    );
    rivetRing.position.z = .05; rivetRing.name = 'vtx-rivet-ring'; rivetRing.userData.pitch_axis = 'decor';
    nac.add(rivetRing);

    // Dynamic rotor blur disc with blade sweep shadows
    if (rot) {
      const disc = new THREE.Mesh(
        new THREE.CircleGeometry(.88, 48),
        new THREE.MeshBasicMaterial({
          color: '#3a444c', transparent: true, opacity: 0,
          depthWrite: false, side: THREE.DoubleSide
        })
      );
      disc.position.z = .03; disc.name = 'vtx-rotor-blur'; disc.userData.pitch_axis = 'decor';
      rot.add(disc); fx.rotorDiscs[i - 1] = disc;
    }
  }

  // ---- Detailed Cockpit Interior (attached to cabin node) -------------------
  const cabin = sub('cabin');
  if (cabin) {
    const decorMat = (c, r = .5, m = .2) => new THREE.MeshStandardMaterial({ color: c, roughness: r, metalness: m });
    const darkMat = decorMat('#16181b', .6, .3);
    const alloyMat = decorMat('#8c949a', .3, .85);
    const cyanScreenMat = new THREE.MeshBasicMaterial({ map: avionicsTex });

    // 1. Center Avionics Console with PFD & Vintage Taxi Meter
    const consoleGeo = new THREE.BoxGeometry(.48, .28, .36);
    const consoleMesh = new THREE.Mesh(consoleGeo, darkMat);
    consoleMesh.position.set(-.02, -.48, .08);
    consoleMesh.rotation.x = Math.PI / 6;
    consoleMesh.userData.pitch_axis = 'decor';
    consoleMesh.userData.legacyCockpitPanel = true;
    cabin.add(consoleMesh);

    // Illuminated screen face
    const screenGeo = new THREE.PlaneGeometry(.44, .24);
    const screenMesh = new THREE.Mesh(screenGeo, cyanScreenMat);
    screenMesh.position.set(0, 0, .185);
    screenMesh.userData.pitch_axis = 'decor';
    consoleMesh.add(screenMesh);

    // Compact pilot display, attached to the real cabin pose and placed below
    // the forward view. Its canvas is populated only from live observations.
    const avCanvas=makeCanvas(1024,512), avContext=avCanvas.getContext('2d');
    const avTexture=toTexture(avCanvas);
    const avPanel=new THREE.Group();
    avPanel.name='vtx-live-cockpit-avionics';
    avPanel.position.set(-.30,-.72,.005);
    avPanel.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(
      new THREE.Vector3(-1,0,0),new THREE.Vector3(0,0,1),new THREE.Vector3(0,1,0)));
    avPanel.rotateX(-.28);
    const avFrame=new THREE.Mesh(new THREE.BoxGeometry(.255,.14,.025),new THREE.MeshStandardMaterial({color:'#202a30',roughness:.5,metalness:.65,depthTest:false,depthWrite:false}));
    const avScreen=new THREE.Mesh(new THREE.PlaneGeometry(.235,.118),new THREE.MeshBasicMaterial({map:avTexture,depthTest:false,depthWrite:false,side:THREE.DoubleSide}));
    avFrame.renderOrder=20;avScreen.renderOrder=21;avScreen.position.z=.013;
    const mount=new THREE.Mesh(new THREE.BoxGeometry(.032,.045,.018),new THREE.MeshStandardMaterial({color:'#46565a',roughness:.55,metalness:.7,depthTest:false,depthWrite:false}));
    mount.position.set(0,-.086,-.007);mount.renderOrder=19;
    avPanel.add(mount,avFrame,avScreen);
    const screwGeo=new THREE.CircleGeometry(.0022,12),screwMat=new THREE.MeshBasicMaterial({color:'#9aaeb0',depthTest:false,depthWrite:false});
    for(const x of [-.120,.120])for(const y of [-.063,.063]){
      const screw=new THREE.Mesh(screwGeo,screwMat);screw.position.set(x,y,.013);screw.renderOrder=22;avPanel.add(screw);
    }
    avPanel.visible=true;cabin.add(avPanel);
    fx.setCockpitMode = enabled => {
      avPanel.traverse(node=>{if(node.isMesh)node.material.depthTest=!enabled;});
    };
    fx.updateAvionics = (observation, stale=false) => {
      const read=avionicsReadings(observation);
      const c=avContext;c.fillStyle='#10191d';c.fillRect(0,0,1024,512);
      c.fillStyle='#27373c';c.fillRect(0,0,1024,48);
      c.fillStyle='#dbe7e8';c.font='bold 26px sans-serif';c.fillText('VTX   FLIGHT INSTRUMENTS',26,32);
      c.textAlign='right';c.fillStyle=stale?'#ffb35d':'#83e0c7';c.fillText(stale?'STALE':read?`${read.state}   ${read.time} s`:'WAITING',998,32);c.textAlign='left';
      if (read) {
        const gauge=(x,y,label,unit,raw,min,max,display)=>{
          const radius=98,start=.75*Math.PI,end=2.25*Math.PI;
          c.fillStyle='#050b0e';c.strokeStyle='#779095';c.lineWidth=8;c.beginPath();c.arc(x,y,radius,0,2*Math.PI);c.fill();c.stroke();
          c.strokeStyle='#d0dfdc';c.lineWidth=3;
          for(let i=0;i<=10;i++){const a=start+(end-start)*i/10,r=i%5===0?76:84;c.beginPath();c.moveTo(x+Math.cos(a)*r,y+Math.sin(a)*r);c.lineTo(x+Math.cos(a)*91,y+Math.sin(a)*91);c.stroke();}
          c.fillStyle='#93adb1';c.font='bold 19px sans-serif';c.textAlign='center';c.fillText(label,x,y-42);c.fillText(unit,x,y+61);
          if(Number.isFinite(raw)){const a=start+(end-start)*Math.max(0,Math.min(1,(raw-min)/(max-min)));c.strokeStyle='#ffb552';c.lineWidth=5;c.beginPath();c.moveTo(x,y);c.lineTo(x+Math.cos(a)*68,y+Math.sin(a)*68);c.stroke();}
          c.fillStyle='#e8f4f2';c.font='bold 25px sans-serif';c.fillText(display,x,y+28);c.textAlign='left';
        };
        gauge(135,177,'ROTOR AVG','RPM',read.meanRpm,0,1500,read.meanRpm===null?'—':read.meanRpm.toFixed(0));
        gauge(365,177,'VERTICAL','m/s',read.verticalValue,-10,10,read.vertical);
        c.fillStyle='#a5bcbf';c.font='bold 19px sans-serif';c.textAlign='center';
        c.fillText('0',65,263);c.fillText('1500',207,263);c.fillText('-10',289,263);c.fillText('+10',438,263);c.textAlign='left';
        c.fillStyle='#061016';c.fillRect(500,74,492,225);
        c.fillStyle='#87a6aa';c.font='bold 24px sans-serif';c.fillText('CLEARANCE',525,110);c.fillText('GROUND SPEED',750,110);c.fillText('FUEL',525,209);c.fillText('SHAFT POWER',750,209);
        c.fillStyle='#d8f7f0';c.font='bold 37px monospace';c.fillText(`${read.clearance} m`,525,161,200);c.fillText(`${read.speed} m/s`,750,161,220);c.fillText(`${read.fuel} kg`,525,259,200);c.fillText(`${read.power} kW`,750,259,220);
        c.fillStyle='#b1c8c8';c.font='bold 24px sans-serif';c.fillText(`RPM 1–4   ${read.rpms}`,30,365,620);
        c.fillStyle='#80dbc3';c.textAlign='right';c.fillText(`LEVEL ${read.level}`,990,365,350);c.textAlign='left';
        c.fillStyle=read.warnings.length?'#ffc46b':'#7ad9bc';c.font='bold 21px sans-serif';
        c.fillText(read.warnings.length?read.warnings.join(' · ').replaceAll('_',' '):'SYSTEM STATUS: NO ACTIVE WARNINGS',30,456,960);
      }
      avTexture.needsUpdate=true;
    };
    fx.updateAvionics(null);

    // Decorative yokes removed: their stems projected into the seats.

    // 3. Dual High-G Bucket Seats & 5-point Harnesses
    for (const seatX of [-.30, .26]) {
      const seatBack = new THREE.Mesh(new THREE.BoxGeometry(.34, .08, .55), decorMat('#252a2e', .7, .1));
      seatBack.position.set(seatX, .12, .18);
      seatBack.rotation.x = -Math.PI / 18;
      seatBack.userData.pitch_axis = 'decor';
      seatBack.userData.cockpitObstruction = seatX === -.30;
      cabin.add(seatBack);

      const seatPan = new THREE.Mesh(new THREE.BoxGeometry(.34, .36, .08), decorMat('#252a2e', .7, .1));
      seatPan.position.set(seatX, -.08, -.06);
      seatPan.userData.pitch_axis = 'decor';
      seatPan.userData.cockpitObstruction = seatX === -.30;
      cabin.add(seatPan);

      // Yellow/black shoulder harness straps
      for (const strapX of [-.09, .09]) {
        const strap = new THREE.Mesh(new THREE.PlaneGeometry(.045, .44), new THREE.MeshStandardMaterial({ color: '#d4a000', roughness: .8 }));
        strap.position.set(strapX, .045, .02);
        strap.userData.pitch_axis = 'decor';
        strap.userData.cockpitObstruction = true;
        seatBack.add(strap);
      }
      // Central rotary buckle
      const buckle = new THREE.Mesh(new THREE.CylinderGeometry(.026, .026, .012, 12), alloyMat);
      buckle.rotation.x = Math.PI / 2;
      buckle.position.set(0, -.14, .02);
      buckle.userData.pitch_axis = 'decor';
      seatBack.add(buckle);
    }

    // 4. Absurd Vader's Taxis Mug in Cup Holder
    const cupHolder = new THREE.Mesh(new THREE.CylinderGeometry(.05, .045, .05, 12), darkMat);
    cupHolder.position.set(-.02, -.24, -.06);
    cupHolder.userData.pitch_axis = 'decor';
    cabin.add(cupHolder);

    const mug = new THREE.Mesh(new THREE.CylinderGeometry(.038, .035, .07, 12), new THREE.MeshStandardMaterial({ color: '#f5b800', roughness: .3 }));
    mug.position.set(0, 0, .035);
    mug.userData.pitch_axis = 'decor';
    cupHolder.add(mug);
  }

  // ---- Navigation Strobes & Landing Light -----------------------------------
  const lamp = (parent, color, x, y, z, r = .07) => {
    const m = new THREE.Mesh(
      new THREE.SphereGeometry(r, 12, 8),
      new THREE.MeshStandardMaterial({ color: '#111', emissive: color, emissiveIntensity: 5 })
    );
    m.position.set(x, y, z); m.name = 'vtx-nav-light'; m.userData.pitch_axis = 'decor';
    parent.add(m); return m;
  };

  // Nav lights: Red Port (nacelle 1 / +X), Green Starboard (nacelle 3 / -X), White Stern (nacelle 2 / +Y)
  if (sub('nacelle1')) lamp(sub('nacelle1'), '#ff2211', 1.23, 0, .3);
  if (sub('nacelle3')) lamp(sub('nacelle3'), '#11ff44', -1.23, 0, .3);
  if (sub('nacelle2')) fx.strobes.push(lamp(sub('nacelle2'), '#ffffff', 0, 1.23, .3, .09));
  if (sub('airframe')) fx.strobes.push(lamp(sub('airframe'), '#ff2211', 0, 0, .08, .09)); // belly beacon

  // Cyan glowing inner duct aerodynamic rings (matching VTX specification diagram)
  const ductRingMat = new THREE.MeshStandardMaterial({
    color: '#081c22',
    emissive: '#2fe3ff',
    emissiveIntensity: 3.2,
    roughness: 0.2,
    metalness: 0.4
  });
  for (let i = 1; i <= 4; i++) {
    const nac = sub(`nacelle${i}`);
    if (nac) {
      const ringGeom = new THREE.TorusGeometry(1.06, 0.022, 8, 32);
      const ring = new THREE.Mesh(ringGeom, ductRingMat);
      ring.position.set(0, 0, 0.02);
      ring.userData.pitch_axis = 'decor';
      nac.add(ring);
    }
  }

  // Forward Landing Searchlight (under the nose frame)
  const airframe = sub('airframe');
  if (airframe) {
    const lightLens = new THREE.Mesh(
      new THREE.CylinderGeometry(.08, .09, .06, 16).rotateX(Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: '#222', emissive: '#fff6e0', emissiveIntensity: 6 })
    );
    lightLens.position.set(0, -1.8, .45); lightLens.rotation.x = -Math.PI / 9;
    lightLens.userData.pitch_axis = 'decor';
    airframe.add(lightLens);
    fx.landingLights.push(lightLens);
  }

  // Real aviation strobe timing: double-flash pattern
  fx.update = (rotorRpm, seconds) => {
    fx.rotorDiscs.forEach((d, i) => {
      if (d) d.material.opacity = THREE.MathUtils.clamp(Math.abs(rotorRpm?.[i] || 0) / 950, 0, 1) * .36;
    });
    // Aviation anti-collision double-flash: flash at 0.0s, flash at 0.2s, dark until 1.2s
    const cycle = seconds % 1.2;
    const isFlash = (cycle < 0.08) || (cycle > 0.18 && cycle < 0.26);
    fx.strobes.forEach((s) => {
      s.material.emissiveIntensity = isFlash ? 12 : 0.4;
    });
  };

  return fx;
}
