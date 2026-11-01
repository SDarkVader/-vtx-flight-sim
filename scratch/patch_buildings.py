with open('public/vtx-env/buildings.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Add imports
old_imp = "import { stoneTexture } from './textures.js';"
new_imp = "import { stoneTexture, transgressionTexture, depotWhiteboardTexture } from './textures.js';"
assert old_imp in text
text = text.replace(old_imp, new_imp)

# Hangar additions: Transgression Record, Whiteboard, Exhibit A Banana Plinth
hangar_anchor = "place(sign, fr, W / 2, 14.6, .25); sign.castShadow = true; group.add(sign);"
hangar_addition = """place(sign, fr, W / 2, 14.6, .25); sign.castShadow = true; group.add(sign);

      // Transgression Record blackboard (VT-2887 regarding the banana incident)
      const trTex = transgressionTexture();
      const trMat = new THREE.MeshStandardMaterial({ map: trTex, roughness: 0.6 });
      const trMesh = new THREE.Mesh(new THREE.BoxGeometry(2.4, 1.4, 0.08), trMat);
      place(trMesh, fr, 4.0, 3.2, 0.35); trMesh.castShadow = true; group.add(trMesh);

      // Depot To-Do Whiteboard with checklist & odd parts big ideas
      const wbTex = depotWhiteboardTexture();
      const wbMat = new THREE.MeshStandardMaterial({ map: wbTex, roughness: 0.35 });
      const wbMesh = new THREE.Mesh(new THREE.BoxGeometry(2.6, 1.4, 0.08), wbMat);
      place(wbMesh, fr, 43.8, 3.2, 0.35); wbMesh.castShadow = true; group.add(wbMesh);

      // EXHIBIT A: The Banana on a Plinth outside Compliance
      const plinthGroup = new THREE.Group();
      const ped = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.95), metal('#45484c', { roughness: 0.8 }));
      ped.position.set(0, 0, 0.475); ped.castShadow = true; plinthGroup.add(ped);
      const plaque = new THREE.Mesh(new THREE.PlaneGeometry(0.35, 0.15), metal('#d4af37', { roughness: 0.3 }));
      plaque.position.set(0, -0.26, 0.5); plinthGroup.add(plaque);
      const bananaCurve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(-0.16, 0, 0.98),
        new THREE.Vector3(-0.06, 0.05, 0.96),
        new THREE.Vector3(0.06, 0.05, 0.96),
        new THREE.Vector3(0.16, 0, 0.99),
      ]);
      const banana = new THREE.Mesh(new THREE.TubeGeometry(bananaCurve, 12, 0.045, 8, false), new THREE.MeshStandardMaterial({ color: '#ffdd00', roughness: 0.4 }));
      banana.castShadow = true; plinthGroup.add(banana);
      const bSpot = new THREE.SpotLight('#fff0d0', 2.5, 4, Math.PI / 4, 0.5);
      bSpot.position.set(0, -0.6, 1.5); bSpot.target = banana;
      plinthGroup.add(bSpot, bSpot.target);
      place(plinthGroup, fr, 2.2, 0, 0.35); group.add(plinthGroup);"""

assert hangar_anchor in text
text = text.replace(hangar_anchor, hangar_addition)

# Office weather vane addition
office_anchor = "if (kind === 'office') boxAt(fr, W / 2, 4.5, 11, .35, .8, dark);"
office_addition = """if (kind === 'office') {
        boxAt(fr, W / 2, 4.5, 11, .35, .8, dark);
        // Rooftop black cab weather vane
        const vaneGroup = new THREE.Group();
        const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 2.2, 8), metal('#1a1a1a'));
        rod.position.set(0, 0, 1.1); vaneGroup.add(rod);
        const cabShape = new THREE.Shape();
        cabShape.moveTo(-0.8, 0); cabShape.lineTo(0.8, 0); cabShape.lineTo(0.8, 0.3); cabShape.lineTo(0.45, 0.35); cabShape.lineTo(0.25, 0.65); cabShape.lineTo(-0.35, 0.65); cabShape.lineTo(-0.55, 0.35); cabShape.lineTo(-0.8, 0.3); cabShape.closePath();
        const cabMesh = new THREE.Mesh(new THREE.ExtrudeGeometry(cabShape, { depth: 0.04, bevelEnabled: false }), metal('#f5b800'));
        cabMesh.position.set(0, 0, 2.0); vaneGroup.add(cabMesh);
        vaneGroup.position.set(o.center[0], o.center[1], o.center[2] + o.half[2]);
        group.add(vaneGroup);
        updaters.push((t) => { cabMesh.rotation.z = Math.sin(t * 0.6) * 0.5; });
      }"""
assert office_anchor in text
text = text.replace(office_anchor, office_addition)

# Radar addition to addTowerTop
radar_anchor = "const beacon = new THREE.Mesh(new THREE.SphereGeometry(.45, 12, 8), glowMat('#ff2a1a', 4)); beacon.position.set(cx, cy, top + .8); group.add(beacon);"
radar_addition = """const beacon = new THREE.Mesh(new THREE.SphereGeometry(.45, 12, 8), glowMat('#ff2a1a', 4)); beacon.position.set(cx, cy, top + .8); group.add(beacon);
  // Rotating radar scanner on mast
  const radar = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.35, 0.4), metal('#d8dde0'));
  radar.position.set(cx + 3, cy - 2, top + 5.5); group.add(radar);
  updaters.push((t) => { radar.rotation.z = t * 2.4; });"""
assert radar_anchor in text
text = text.replace(radar_anchor, radar_addition)

with open('public/vtx-env/buildings.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("buildings.js patched successfully!")
