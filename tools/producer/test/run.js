// Runs every suite in a headless Chromium against the built page. Needs Node 18+ and Playwright (npm i playwright).
//   node tools/producer/test/run.js
// Suites make synthetic audio (including a calibrated 997 Hz tone), play it through the page and check what comes out.
const http = require('http'), fs = require('fs'), path = require('path'), { spawn, spawnSync } = require('child_process');
const root = path.resolve(__dirname, '..'), out = path.join(__dirname, 'out');
fs.mkdirSync(out, { recursive: true });
const server = http.createServer((req, res) => {
  const f = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': f.endsWith('.html') ? 'text/html' : 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
});
const run = (file, env) => new Promise(resolve => {
  const child = spawn('node', [file], { cwd: out, env });   // asynchronous, so this process can keep serving the page
  let stdout = '', stderr = '';
  child.stdout.on('data', d => stdout += d); child.stderr.on('data', d => stderr += d);
  const timer = setTimeout(() => child.kill(), 300000);
  child.on('close', code => { clearTimeout(timer); resolve({ code, stdout, stderr }); });
});
server.listen(0, '127.0.0.1', async () => {
  const url = `http://127.0.0.1:${server.address().port}/VTX%20Producer.html`;
  if (!fs.existsSync(path.join(__dirname, 'assets'))) spawnSync('node', [path.join(__dirname, 'gen.js')], { stdio: 'inherit' });
  let pass = 0, fail = 0;
  for (const suite of ['dsp', 'smoke', 'audio', 'ui', 'takes', 'vehicle', 'scene', 'persist', 'overflow', 'touch', 'tracks']) {
    const r = await run(path.join(__dirname, suite + '.js'), { ...process.env, STUDIO_URL: url });
    const lines = r.stdout.split('\n');
    const p = lines.filter(l => l.startsWith('PASS ')).length, f = lines.filter(l => l.startsWith('FAIL ')).length + (r.code ? 1 : 0);
    pass += p; fail += f;
    console.log(`${f ? 'FAIL' : 'ok  '} ${suite.padEnd(9)} ${p} passed${f ? ', ' + f + ' failed' : ''}`);
    for (const l of lines) if (l.startsWith('FAIL ')) console.log('       ' + l);
    if (r.code && r.stderr) console.log('       ' + r.stderr.split('\n').slice(0, 6).join('\n       '));
  }
  console.log(`\n${pass} checks passed, ${fail} failed`);
  server.close(); process.exit(fail ? 1 : 0);
});
