with open('public/vtx-env/buildings.js', 'r', encoding='utf-8') as f:
    text = f.read()

target = "place(trMesh, fr, 4.0, 3.2, 0.35); trMesh.castShadow = true; group.add(trMesh);"
addition = """place(trMesh, fr, 4.0, 3.2, 0.35); trMesh.castShadow = true; group.add(trMesh);

      // Steve Dark's Citation Certificate for Extraordinary Altruistic Heroism (31 Oct 2026)
      const citTex = citationTexture();
      const citMat = new THREE.MeshStandardMaterial({ map: citTex, roughness: 0.4 });
      const citMesh = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.6, 0.06), citMat);
      place(citMesh, fr, 1.6, 3.2, 0.35); citMesh.castShadow = true; group.add(citMesh);

      // The Gold Medal for Altruistic Heroism in navy velvet case
      const medalCase = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.65, 0.12), metal('#0f1b2b', { roughness: 0.85 }));
      const goldMedal = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.04, 24).rotateX(Math.PI / 2), metal('#d4af37', { roughness: 0.25, metalness: 0.9 }));
      goldMedal.position.set(0, 0, 0.07);
      medalCase.add(goldMedal);
      place(medalCase, fr, 1.6, 1.8, 0.35); medalCase.castShadow = true; group.add(medalCase);"""

assert target in text
text = text.replace(target, addition)

with open('public/vtx-env/buildings.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("buildings.js patched with Citation & Medal!")
