import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {VISUAL_ASSET_PINS, loadPinnedGltf, verifiedVisualAssets} from '../public/visual-identity.js';
import {VEHICLE_MODELS} from '../public/vtx-env/vehicle-registry.js';

for (const [uri, pin] of Object.entries(VISUAL_ASSET_PINS)) {
  const bytes = await readFile(new URL('../public' + uri, import.meta.url));
  assert.equal(createHash('sha256').update(bytes).digest('hex'), pin, 'pinned visual bytes: ' + uri);
}
assert.equal(VEHICLE_MODELS.r6.sha256, VISUAL_ASSET_PINS[VEHICLE_MODELS.r6.asset.split('?')[0]]);
const bytes = new TextEncoder().encode('test visual').buffer, hash = createHash('sha256').update(new Uint8Array(bytes)).digest('hex');
const calls = [], loader = {parse(data, base, resolve) {calls.push(data); resolve({scene: 'verified'});}};
const fetch = async () => ({ok: true, arrayBuffer: async () => bytes});
assert.deepEqual(await loadPinnedGltf(loader, '/assets/test.glb', hash, fetch), {scene: 'verified'});
assert.equal(verifiedVisualAssets.has('/assets/test.glb'), true);
await assert.rejects(loadPinnedGltf(loader, '/assets/test.glb', '0'.repeat(64), fetch), /pinned revision/);
assert.equal(calls.length, 1, 'a mismatched visual must never be parsed or rendered');
assert.equal(verifiedVisualAssets.has('/assets/test.glb'), false);
