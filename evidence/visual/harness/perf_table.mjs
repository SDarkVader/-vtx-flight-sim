// Prints a markdown before/after table from capture perf JSON files.
// node perf_table.mjs <before.json> <after.json> [label]
import {readFileSync} from 'node:fs';
const [a, b, label = ''] = process.argv.slice(2);
const A = Object.values(JSON.parse(readFileSync(a)).configs)[0], B = Object.values(JSON.parse(readFileSync(b)).configs)[0];
console.log(`\n${label} (before tier ${A.quality}, AA ${A.antialias}, DPR ${A.pixelRatio}, shadows ${A.shadows} -> after tier ${B.quality}, AA ${B.antialias}, DPR ${B.pixelRatio}, shadows ${B.shadows}; GPU ${B.gpu})\n`);
console.log('| view | calls before | calls after | triangles before | triangles after | median ms before | median ms after |');
console.log('|---|---|---|---|---|---|---|');
let s = [0, 0, 0, 0, 0, 0];
for (const v of Object.keys(B.views)) {
  const x = A.views[v], y = B.views[v]; if (!x) continue;
  const r = [x.info.calls, y.info.calls, x.info.triangles, y.info.triangles, x.median_ms, y.median_ms];
  r.forEach((t, i) => (s[i] += t));
  console.log(`| ${v} | ${r.join(' | ')} |`);
}
console.log(`| **sum** | ${s.map((t) => +t.toFixed(1)).join(' | ')} |`);
