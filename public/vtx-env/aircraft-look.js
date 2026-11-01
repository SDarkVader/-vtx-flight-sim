// Visual treatment of the real VTX simulator aircraft. This only swaps MATERIALS and adds
// small child meshes to the existing rendered body nodes (so they follow the physical
// articulation). The airframe geometry, body poses, collision and mass model are untouched.
import * as THREE from 'three';
import { makeCanvas, toTexture } from './textures.js';

const PEARL = new THREE.Color('#eef2f3'), CARBON = new THREE.Color('#0e1215'), CYAN = new THREE.Color('#2fe3ff');

function checkerTexture() {
  const c = makeCanvas(128, 16), g = c.getContext('2d');
  for (let i = 0; i < 16; i++) for (let j = 0; j < 2; j++) { g.fillStyle = (i + j) % 2 ? '#f5b800' : '#0f1113'; g.fillRect(i * 8, j * 8, 8, 8); }
  const t = toTexture(c, { repeat: [6, 1], wrap: true }); t.magFilter = THREE.NearestFilter; return t;
}

// Outward-facing surfaces of the duct shell become pearl-white composite, the inner wall stays carbon.
function paintDuct(geo) {
  if (geo.userData.ductPainted) return; geo.userData.ductPainted = true;
  const p = geo.attributes.position, n = geo.attributes.normal, cols = new Float32Array(p.count * 3), c = new THREE.Color();
  for (let i = 0; i < p.count; i++) {
    const out = n.getX(i) * p.getX(i) + n.getY(i) * p.getY(i), t = THREE.MathUtils.smoothstep(out, -.05, .15);
    c.copy(CARBON).lerp(PEARL, t); cols.set([c.r, c.g, c.b], i * 3);
  }
  geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));
}

export function enhanceAircraft(root, envTexture) {
  const cache = new Map(), replaced = new Set(), fx = { rotorDiscs: [], strobes: [] };
  const make = (key, fn) => { if (!cache.has(key)) cache.set(key, fn()); return cache.get(key); };
  const phys = (o) => new THREE.MeshPhysicalMaterial({ side: THREE.DoubleSide, envMap: envTexture, ...o });

  root.traverse((n) => {
    if (!n.isMesh || Array.isArray(n.material)) return;
    const body = n.userData.physical_body || '', kind = body.replace(/\d+$/, ''), old = n.material, name = old.name;
    let mat = null;
    switch (name) {
      case 'Laminated glazing nominal':
        mat = make(name, () => phys({ color: '#a8d4e2', metalness: 0, roughness: .03, transparent: true, opacity: .16, envMapIntensity: 2.6, clearcoat: 1, clearcoatRoughness: .02, depthWrite: false })); break;
      case 'Instrument glass':
        mat = make(name, () => phys({ color: '#03161c', emissive: CYAN, emissiveIntensity: 1.5, roughness: .08, metalness: .2 })); break;
      case 'Seat and trim':
        mat = make(name, () => phys({ color: '#d9d3c5', roughness: .62, metalness: 0, sheen: .6, sheenColor: new THREE.Color('#ffffff') })); break;
      case 'Duct inlet highlight':
        mat = make(name, () => phys({ color: '#06323a', emissive: CYAN, emissiveIntensity: 3, roughness: .2, metalness: .1 })); break;
      case 'CFRP woven reinforced':
        if (kind === 'nacelle') { paintDuct(n.geometry); mat = make('duct', () => phys({ vertexColors: true, color: '#ffffff', roughness: .24, metalness: .08, clearcoat: 1, clearcoatRoughness: .05 })); }
        break;
      case 'Aerospace aluminum surfaces':
        mat = kind === 'rotor' ? make('blade', () => phys({ color: '#252a2f', roughness: .34, metalness: .5, clearcoat: .4 }))
          : kind === 'nacelle' ? make('strut', () => phys({ color: '#e6eaec', roughness: .28, metalness: .35, clearcoat: .8 }))
          : make('alloy', () => phys({ color: '#b8c0c4', roughness: .32, metalness: .85 }));
        break;
      case 'VTX V3 / signal bus route': case 'VTX V2 - stator control linkage':
        mat = make(name, () => { const m = old.clone(); m.emissive = CYAN.clone(); m.emissiveIntensity = .55; m.envMap = envTexture; return m; }); break;
      case 'Titanium nodes': case 'VTX V2 - titanium attachments': case 'VTX V3 / titanium forged joint': case 'VTX V4 / titanium articulated load fitting': case 'VTX V4 / machined light alloy':
        mat = make(name, () => { const m = old.clone(); m.roughness = Math.min(m.roughness, .28); m.metalness = .95; m.envMap = envTexture; return m; }); break;
      case 'CFRP structural composite': case 'VTX V2 - carbon laminate': case 'VTX V4 / laminated CFRP primary spaceframe': case 'VTX V4 / braided CFRP secondary bracing': case 'VTX V3 / carbon triangulated primary structure':
        mat = make(name, () => phys({ color: '#161b1f', roughness: .3, metalness: .15, clearcoat: .7, clearcoatRoughness: .12 })); break;
      case 'VTX V3 / control torque path': case 'VTX V3 / independent power bus': case 'VTX V4 / monitored landing dampers': case 'Variable pitch actuators':
        mat = make(name, () => { const m = old.clone(); m.roughness = .38; m.envMap = envTexture; return m; }); break;
      default: break;
    }
    if (mat && mat !== old) { replaced.add(old); n.material = mat; }
  });
  replaced.forEach((m) => m.dispose());

  const sub = (b) => root.getObjectByName(b);
  const checker = checkerTexture();
  for (let i = 1; i <= 4; i++) {
    const nac = sub('nacelle' + i), rot = sub('rotor' + i); if (!nac) continue;
    const accent = new THREE.Mesh(new THREE.TorusGeometry(1.215, .016, 8, 96), new THREE.MeshStandardMaterial({ color: '#04282f', emissive: CYAN, emissiveIntensity: 3.2 }));
    accent.position.z = .27; accent.name = 'vtx-accent-ring'; accent.userData.pitch_axis = 'decor'; nac.add(accent);
    const band = new THREE.Mesh(new THREE.TorusGeometry(1.2, .03, 6, 96), new THREE.MeshStandardMaterial({ map: checker, roughness: .5, metalness: .1 }));
    band.position.z = .15; band.name = 'vtx-livery-band'; band.userData.pitch_axis = 'decor'; nac.add(band);
    if (rot) {
      const disc = new THREE.Mesh(new THREE.CircleGeometry(.88, 40), new THREE.MeshBasicMaterial({ color: '#59636b', transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide }));
      disc.position.z = .03; disc.name = 'vtx-rotor-blur'; disc.userData.pitch_axis = 'decor'; rot.add(disc); fx.rotorDiscs[i - 1] = disc;
    }
  }
  // Navigation lights (aircraft forward is -Y): red port (+X), green starboard (-X), white tail, red belly beacon.
  const lamp = (parent, color, x, y, z, r = .07) => { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 8), new THREE.MeshStandardMaterial({ color: '#111', emissive: color, emissiveIntensity: 5 })); m.position.set(x, y, z); m.name = 'vtx-nav-light'; m.userData.pitch_axis = 'decor'; parent.add(m); return m; };
  if (sub('nacelle1')) lamp(sub('nacelle1'), '#ff2a1a', 1.23, 0, .3);
  if (sub('nacelle3')) lamp(sub('nacelle3'), '#26ff5a', -1.23, 0, .3);
  if (sub('nacelle2')) fx.strobes.push(lamp(sub('nacelle2'), '#ffffff', 0, 1.23, .3, .09));
  if (sub('airframe')) fx.strobes.push(lamp(sub('airframe'), '#ff3b2a', 0, 0, .1, .09));

  fx.update = (rotorRpm, seconds) => {
    fx.rotorDiscs.forEach((d, i) => { if (d) d.material.opacity = THREE.MathUtils.clamp(Math.abs(rotorRpm?.[i] || 0) / 900, 0, 1) * .32; });
    const on = (seconds % 1.4) < .12 || ((seconds + .25) % 1.4) < .1;
    fx.strobes.forEach((s) => { s.material.emissiveIntensity = on ? 10 : .3; });
  };
  return fx;
}
