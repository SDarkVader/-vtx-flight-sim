with open('public/vtx-env/airfield.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Import windsockTexture
old_imp = "import { asphaltTextures, concreteTextures, makeCanvas, toTexture, rng } from './textures.js';"
new_imp = "import { asphaltTextures, concreteTextures, makeCanvas, toTexture, rng, windsockTexture } from './textures.js';"
assert old_imp in text
text = text.replace(old_imp, new_imp)

# Update underground portal text
old_portal = """      F.text(g, null, 'VTX DEEP BAY', w / 2, 8.2, 1.6, { color: F.YEL, align: 'center', font: 'Impact,Arial', glow: false, spacing: .2 });
      F.text(g, null, 'ACCESS RESERVED', w / 2, 10.4, 1.15, { color: '#e8e6d8', align: 'center', font: 'Impact,Arial', glow: false, spacing: .2 });
      F.text(g, null, 'PHASE 2', w / 2, 12.2, .9, { color: '#9aa0a3', align: 'center', font: 'Impact,Arial', glow: false, spacing: .2 });"""

new_portal = """      F.text(g, null, 'VTX BASEMENT & VOLCANO ASCENT', w / 2, 8.2, 1.3, { color: F.YEL, align: 'center', font: 'Impact,Arial', glow: false, spacing: .1 });
      F.text(g, null, 'KEEP OUT STEVE · COMPLIANCE DIRECTIVE', w / 2, 10.4, 1.0, { color: '#e8e6d8', align: 'center', font: 'Impact,Arial', glow: false, spacing: .1 });
      F.text(g, null, 'RAYMOND WINSTON & ARTHUR FINCH ONLY', w / 2, 12.2, .85, { color: '#f5b800', align: 'center', font: 'Impact,Arial', glow: false, spacing: .1 });"""

assert old_portal in text
text = text.replace(old_portal, new_portal)

# Add 3D windsock and GSE to airfield
old_end = """  scene.add(group);
  return { group, lightCount: lights.length };
}"""

new_end = """  // ---- 3D Illuminated Windsock (near runway threshold)
  const sockGroup = new THREE.Group();
  sockGroup.position.set(-112, -38, 0);
  const poleMat = new THREE.MeshStandardMaterial({ color: '#55595d', metalness: 0.8, roughness: 0.4 });
  const sockPole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 6.5, 8), poleMat);
  sockPole.position.set(0, 0, 3.25); sockGroup.add(sockPole);

  const sockMat = new THREE.MeshStandardMaterial({
    map: windsockTexture(),
    roughness: 0.7,
    side: THREE.DoubleSide
  });
  const sockCone = new THREE.Mesh(new THREE.ConeGeometry(0.55, 3.4, 12, 1, true), sockMat);
  sockCone.rotateZ(Math.PI / 2);
  sockCone.position.set(1.7, 0, 6.2);
  sockGroup.add(sockCone);

  const sockLamp = new THREE.PointLight('#fff2d4', 1.8, 12);
  sockLamp.position.set(0, 0, 6.6); sockGroup.add(sockLamp);
  group.add(sockGroup);

  // ---- Ground Support Equipment (GSE) parked safely on apron edge
  const gseMat = new THREE.MeshStandardMaterial({ color: '#f5b800', roughness: 0.5, metalness: 0.2 });
  const darkMat = new THREE.MeshStandardMaterial({ color: '#16191c', roughness: 0.7 });

  // GPU Trailer (Ground Power Unit)
  const gpuGroup = new THREE.Group();
  gpuGroup.position.set(16, 12, 0);
  const gpuBody = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.2, 0.9), gseMat);
  gpuBody.position.set(0, 0, 0.65); gpuBody.castShadow = true; gpuGroup.add(gpuBody);
  // Wheels
  for (const [wx, wy] of [[-0.7, 0.65], [-0.7, -0.65], [0.7, 0.65], [0.7, -0.65]]) {
    const wMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.16, 12), darkMat);
    wMesh.rotateX(Math.PI / 2); wMesh.position.set(wx, wy, 0.24); gpuGroup.add(wMesh);
  }
  group.add(gpuGroup);

  // Airframe Service Stepladder Stand
  const ladderGroup = new THREE.Group();
  ladderGroup.position.set(22, 16, 0);
  const plat = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.4, 0.1), gseMat);
  plat.position.set(0, 0, 2.2); ladderGroup.add(plat);
  for (const [lx, ly] of [[-0.5, -0.6], [0.5, -0.6], [-0.5, 0.6], [0.5, 0.6]]) {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 2.2, 6), darkMat);
    leg.position.set(lx, ly, 1.1); ladderGroup.add(leg);
  }
  ladderGroup.castShadow = true;
  group.add(ladderGroup);

  scene.add(group);
  return { group, lightCount: lights.length };
}"""

assert old_end in text
text = text.replace(old_end, new_end)

with open('public/vtx-env/airfield.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("airfield.js patched successfully!")
