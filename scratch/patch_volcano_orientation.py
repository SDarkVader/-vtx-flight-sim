with open('public/vtx-env/volcano-basement.js', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Enclosing cavern rock wall
target1 = '''  const cavernCeiling = new THREE.Mesh(cavernVaultGeom, cavernMat);
  cavernCeiling.receiveShadow = true;
  group.add(cavernCeiling);'''

repl1 = '''  const cavernCeiling = new THREE.Mesh(cavernVaultGeom, cavernMat);
  cavernCeiling.receiveShadow = true;
  group.add(cavernCeiling);

  // Enclosed vertical basalt rock walls
  const wallGeom = new THREE.CylinderGeometry(cavernW * 0.52, cavernW * 0.52, 36, 48, 1, true);
  wallGeom.rotateX(Math.PI / 2);
  wallGeom.translate(0, 6, 18);
  const wallMat = new THREE.MeshStandardMaterial({
    map: volcanoBasaltTexture(),
    roughness: 0.92,
    side: THREE.BackSide,
  });
  wallMat.map.repeat.set(6, 2);
  const cavernWall = new THREE.Mesh(wallGeom, wallMat);
  group.add(cavernWall);'''

# 2. Lava waterfall vertical orientation
target2 = '''  const fallW = 34, fallH = 46;
  const fallGeom = new THREE.PlaneGeometry(fallW, fallH, 20, 20);
  fallGeom.translate(0, 0, fallH / 2 + 1);
  const lavaFall = new THREE.Mesh(fallGeom, lavaMat);
  lavaFall.position.set(0, 42, 0);
  lavaFall.rotation.y = Math.PI; // Face South into the cavern
  group.add(lavaFall);'''

repl2 = '''  const fallW = 34, fallH = 46;
  const fallGeom = new THREE.PlaneGeometry(fallW, fallH, 20, 20);
  fallGeom.rotateX(-Math.PI / 2); // Stand vertically facing South (-Y)
  fallGeom.translate(0, 0, fallH / 2 + 1);
  const lavaFall = new THREE.Mesh(fallGeom, lavaMat);
  lavaFall.position.set(0, 42, 0);
  group.add(lavaFall);'''

# 3. Steampunk sign vertical orientation
target3 = '''  const signW = 28, signH = 14;
  const signMesh = new THREE.Mesh(new THREE.PlaneGeometry(signW, signH), signMat);
  signMesh.position.set(0, 24, 32);
  signMesh.rotation.y = Math.PI; // Face South toward the entrance tunnel
  signMesh.castShadow = true;
  group.add(signMesh);'''

repl3 = '''  const signW = 28, signH = 14;
  const signGeom = new THREE.PlaneGeometry(signW, signH);
  signGeom.rotateX(-Math.PI / 2); // Stand vertically facing South (-Y)
  const signMesh = new THREE.Mesh(signGeom, signMat);
  signMesh.position.set(0, 24, 32);
  signMesh.castShadow = true;
  group.add(signMesh);'''

# 4. Robot mask face vertical orientation
target4 = '''    const mMesh = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 3.2), maskMat);
    mMesh.rotation.x = Math.PI / 12;
    maskHolder.add(mMesh);'''

repl4 = '''    const mGeom = new THREE.PlaneGeometry(3.2, 3.2);
    mGeom.rotateX(-Math.PI / 2); // Stand vertically facing South (-Y)
    const mMesh = new THREE.Mesh(mGeom, maskMat);
    maskHolder.add(mMesh);'''

assert target1 in c, 'target1 not found'
assert target2 in c, 'target2 not found'
assert target3 in c, 'target3 not found'
assert target4 in c, 'target4 not found'

c = c.replace(target1, repl1).replace(target2, repl2).replace(target3, repl3).replace(target4, repl4)

with open('public/vtx-env/volcano-basement.js', 'w', encoding='utf-8') as f:
    f.write(c)
print('Patched volcano basement orientations successfully!')
