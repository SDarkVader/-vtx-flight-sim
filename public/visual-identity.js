// Fix the current render revisions without changing aircraft configurations or dynamics.
export const VISUAL_ASSET_PINS = Object.freeze({
  '/assets/airframe-r6.glb': 'd001ae20ba7665cbdbb8e910e4006df07bc855cbcf85c58211ff81e04ac82034',
  '/assets/airframe-r6-blendstra-rig.glb': '7325d0b303398c4ec0e9ece398cdcf63176db2555205b06c4d32a74a095c1489',
  '/assets/airframe-r6-connected-r2.glb': '0e91bb0667bcc5d756ad0478a0d7bf86525263ecd2e8289d7e64fe3773186a04',
  '/assets/phantom-a10b-visual.glb': '45364301f2950ca57e5b34ac73d29b0abe11471dd82f0fe0e5068da70418a93e',
  '/assets/phantom-a10-blendstra-81c823e2.glb': '315fd09c2dc33d27c4954c3440a9eac4db9917c593eb289b637118e81844cfed',
});
export const verifiedVisualAssets = new Set();

export async function loadPinnedGltf(loader, uri, expected = VISUAL_ASSET_PINS[uri.split('?')[0]], fetchAsset = globalThis.fetch) {
  if (!expected) return new Promise((resolve, reject) => loader.load(uri, resolve, undefined, reject));
  verifiedVisualAssets.delete(uri.split('?')[0]);
  const response = await fetchAsset(uri, {cache: 'no-cache'});
  if (!response.ok) throw Error('Aircraft visual asset unavailable');
  const bytes = await response.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
  if (digest !== expected) throw Error('Aircraft visual differs from its pinned revision');
  const gltf = await new Promise((resolve, reject) => loader.parse(bytes, '/assets/', resolve, reject));
  verifiedVisualAssets.add(uri.split('?')[0]);
  return gltf;
}
