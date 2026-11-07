// Place the supplied Y-up A10 model in the Z-up physical body's frame.
export function preparePhysicalVisual(THREE, scene, asset, latestA10Asset) {
  if (asset !== latestA10Asset) return scene;
  if (scene.getObjectByName('airframe')) throw Error('Unexpected A10 root: physical frame already present');
  const root = new THREE.Group();
  root.name = 'airframe';
  root.userData.physical_body = 'airframe';
  scene.rotation.x = Math.PI / 2;
  root.add(scene);
  return root;
}
