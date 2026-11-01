// Parity test: verify bidirectional projection between MuJoCo world coordinates and minimap canvas
function createProjection(w, h, half_m, cx = 0, cy = 0, zoom = 1.0) {
  const span = (half_m * 2) / zoom;
  const px = x => ((x - cx) / span + 0.5) * w;
  const py = y => (0.5 - (y - cy) / span) * h;
  const unpx = screenX => (screenX / w - 0.5) * span + cx;
  const unpy = screenY => (0.5 - screenY / h) * span + cy;
  return { px, py, unpx, unpy };
}

const w = 400, h = 400, half_m = 500;
const proj = createProjection(w, h, half_m);

const testPoints = [
  [0, 0],
  [-555, 635],
  [235, 0],
  [-180, 0],
  [40, 590],
  [680, 600],
  [-30, 290]
];

let maxError = 0;
for (const [x, y] of testPoints) {
  const sx = proj.px(x);
  const sy = proj.py(y);
  const rx = proj.unpx(sx);
  const ry = proj.unpy(sy);
  const err = Math.hypot(rx - x, ry - y);
  if (err > maxError) maxError = err;
}

console.log(`Max roundtrip projection error: ${maxError.toExponential(4)} m`);
if (maxError < 1e-10) {
  console.log('PARITY TEST PASSED: Mathematical bijection between canvas and world coordinates is exact.');
} else {
  console.error('PARITY TEST FAILED');
  process.exit(1);
}
