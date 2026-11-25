const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const path = require('path'), fs = require('fs'), cp = require('child_process');
const A = p => path.join(__dirname, 'assets', p);
const ok = (name, cond, extra = '') => console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : ''));
const SOUNDS = fs.readdirSync(A('Sounds')).map(f => A('Sounds/' + f));
function wavInfo(buf) {
  const v = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const ch = v.getUint16(22, true), rate = v.getUint32(24, true), bits = v.getUint16(34, true), len = v.getUint32(40, true), n = len / (ch * bits / 8);
  let peak = 0, o = 44;
  for (let i = 0; i < n * ch; i++) { const x = (v.getUint8(o) | v.getUint8(o + 1) << 8 | v.getInt8(o + 2) << 16) / 8388608; o += 3; if (Math.abs(x) > peak) peak = Math.abs(x); }
  return { ch, rate, bits, secs: n / rate, peak: peak ? 20 * Math.log10(peak) : -Infinity };
}
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
  const page = await context.newPage();
  const errors = [];
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) errors.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  await page.goto(URL);
  await page.click('#t-vehicle');
  await page.setInputFiles('#vehLoad input[type=file][multiple]', SOUNDS);
  await page.waitForTimeout(800);
  ok('12 part cards', (await page.locator('#parts .part').count()) === 12);
  ok('part summary names the take chosen by name', (await page.locator('#sum-wings').textContent()).includes('D. Big set-piece') && (await page.locator('#sum-wings').textContent()).includes('wing_deployment'), await page.locator('#sum-wings').textContent());
  // open Wing transformation, play with the loaded take
  await page.click('#open-wings');
  ok('move parts show 8 dials (Seconds + the seven)', (await page.locator('#body-wings [role=slider]').count()) === 8);
  await page.click('#part-wings .part-row .chip');
  await page.waitForTimeout(1500);
  const vrms = await page.evaluate(() => LM.strips.veh.rms);
  ok('wings play on the Vehicle strip', vrms > -60, 'veh strip ' + vrms.toFixed(1) + ' dB');
  await page.waitForTimeout(5500);
  ok('the move stops by itself', (await page.evaluate(() => live.has('wings'))) === false);
  // design menu rewrites the dials
  await page.locator('#body-wings select').first().selectOption({ label: 'C. Fast and sharp' });
  await page.waitForTimeout(300);
  ok('picking design C sets pitch 1.35 and edge +8 dB', await page.evaluate(() => veh.wings.pitch === 1.35 && veh.wings.edge === 8));
  ok('the pitch dial shows the new value', (await page.locator('#body-wings [aria-label=Pitch]').getAttribute('aria-valuetext')) === '1.35x');
  await page.click('#part-wings .part-row .chip'); await page.waitForTimeout(300);
  // a dial turned while playing replays with the change
  await page.locator('#body-wings [aria-label=Volume]').focus(); await page.keyboard.press('ArrowUp');
  ok('volume dial writes the part state (0.55 -> 0.6 with 0.1 steps off the 0.55 start)', await page.evaluate(() => veh.wings.volume > 0.55), await page.evaluate(() => veh.wings.volume));
  await page.click('#vStop');
  // ---- flight replay
  await page.click('#steps .chip:nth-child(2)');
  await page.waitForTimeout(3500);
  const now = await page.locator('#now').textContent();
  ok('flight replay reports speed, fans and boosters', /km\/h.*fans.*rpm.*boosters/.test(now), now);
  const fl = await page.evaluate(() => LM.strips.veh.rms);
  ok('the replay is audible on the Vehicle strip', fl > -60, fl.toFixed(1) + ' dB');
  await page.click('#vStop'); await page.waitForTimeout(400);
  // ---- ducking on a hit
  await page.evaluate(() => { audio(); duck(); });
  await page.waitForTimeout(150);
  const dg = await page.evaluate(() => [A.strips.music.duck.gain.value, A.strips.amb.duck.gain.value, A.strips.veh.duck.gain.value]);
  ok('duck dips Music and Ambience (to about -6 dB) but not Vehicle', dg[0] < 0.75 && dg[1] < 0.75 && dg[2] > 0.99, JSON.stringify(dg.map(x => Math.round(x * 100) / 100)));
  await page.waitForTimeout(3500);
  ok('and releases afterwards', (await page.evaluate(() => A.strips.music.duck.gain.value)) > 0.97);
  // ---- auto balance
  const volsBefore = await page.evaluate(() => JSON.stringify(Object.fromEntries(Object.entries(veh).map(([k, v]) => [k, v.volume]))));
  await page.click('#balance');
  await page.waitForFunction(() => document.getElementById('nowSub').textContent.startsWith('Volumes balanced'), null, { timeout: 60000 });
  const volsAfter = await page.evaluate(() => Object.fromEntries(Object.entries(veh).map(([k, v]) => [k, v.volume])));
  ok('auto balance sets sane volumes for all twelve parts', Object.values(volsAfter).every(v => v >= 0.05 && v <= 4) && JSON.stringify(volsAfter) !== volsBefore, JSON.stringify(volsAfter));
  // ---- bounce a part
  const [d1] = await Promise.all([page.waitForEvent('download'), page.click('#body-wings >> text=Bounce WAV')]);
  const p1 = path.join(__dirname, 'out', 'out-part-' + d1.suggestedFilename()); await d1.saveAs(p1);
  const w1 = wavInfo(fs.readFileSync(p1));
  const expLen = await page.evaluate(() => veh.wings.length + 1.8);
  ok('bounced wing part is a stereo 24-bit WAV of length+1.8 s with sound in it', w1.ch === 2 && w1.bits === 24 && Math.abs(w1.secs - expLen) < 0.05 && w1.peak > -30, JSON.stringify(w1) + ' expected ' + expLen);
  console.log('   saved as', d1.suggestedFilename());
  // ---- bounce all parts
  const [d2] = await Promise.all([page.waitForEvent('download', { timeout: 90000 }), page.click('#bounceParts')]);
  const p2 = path.join(__dirname, 'out', 'out-all-parts.zip'); await d2.saveAs(p2);
  const z = cp.execSync(`python3 - <<'PY'\nimport zipfile\nz=zipfile.ZipFile(${JSON.stringify(p2)})\nprint(z.testzip(), len(z.namelist()), sum(i.file_size for i in z.infolist()))\nPY`).toString().trim();
  ok('zip of all parts is valid with 12 WAVs', /^None 12 /.test(z), z);
  // a looping part renders 8 s minus the 0.15 s seamless fold
  const fansOut = path.join(__dirname, 'out', 'fans.wav');
  const fans = cp.execSync(`python3 - <<'PY'\nimport zipfile\nz=zipfile.ZipFile(${JSON.stringify(p2)})\nn=[x for x in z.namelist() if 'Wheel_fans' in x][0]\nopen(${JSON.stringify(fansOut)},'wb').write(z.read(n))\nPY`);
  const wf = wavInfo(fs.readFileSync(path.join(__dirname, 'out', 'fans.wav')));
  ok('wheel-fan loop is 7.85 s (8 s with a 0.15 s fold for a seamless repeat)', Math.abs(wf.secs - 7.85) < 0.03 && wf.peak > -40, JSON.stringify(wf));
  // ---- tuning JSON
  await page.click('#copyTuning');
  const tj = JSON.parse(await page.locator('#tuningOut').inputValue());
  ok('tuning JSON holds all twelve parts and no runtime handles', Object.keys(tj).length === 12 && !('token' in tj.wings) && tj.wings.pitch === 1.35, Object.keys(tj).join(','));
  console.log('errors:', JSON.stringify(errors));
  await page.click('#t-vehicle');
  await page.screenshot({ path: 'shot-vehicle-open.png' });
  await browser.close();
})();
