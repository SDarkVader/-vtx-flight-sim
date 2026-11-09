import assert from 'node:assert/strict';
import * as THREE from '../public/vendor/three.module.js';
import {makeFarForest} from '../public/vtx-env/landscape.js';
for (const half of [500, 4000]) {
  const forest = makeFarForest(() => 0, 200, half);
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const scale = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  for (let i = 0; i < forest.count; i++) {
    forest.getMatrixAt(i, matrix);
    matrix.decompose(position, quaternion, scale);
    assert.ok(Math.max(Math.abs(position.x),Math.abs(position.y)) - 7 * Math.max(scale.x,scale.y) > half,
      'forest crown enters physical world at ' + position.toArray());
  }
}
console.log('far forest stays outside the physical terrain');
