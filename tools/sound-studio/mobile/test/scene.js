const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const path = require('path'), fs = require('fs');
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
  await page.click('#t-takes');
  await page.setInputFiles('#takesWrap input[type=file][multiple]', SOUNDS);
  await page.waitForTimeout(800);
  await page.click('#t-scene');
  ok('empty scene says what to do', (await page.locator('#sceneWrap .layer').count()) === 0);
  // bed: a looping layer on the fan take
  await page.click('text=Add layer'); await page.waitForTimeout(200);
  ok('one layer card', (await page.locator('#sceneWrap .layer').count()) === 1);
  await page.locator('#sceneWrap .layer select').first().selectOption({ label: 'A_large_electric_ducted_fan_variation2' });
  const take1 = await page.evaluate(() => cur().layers[0].take);
  ok('the layer has a take chosen', !!take1, take1.slice(0, 40));
  ok('loop layer shows three dials (level, pitch, pan)', (await page.locator('#sceneWrap .layer [role=slider]').count()) === 3);
  // fade is 2 s by default; start the scene
  await page.click('#sceneGo');
  await page.waitForTimeout(3500);
  const avg = () => page.evaluate(async () => { let s = 0; for (let i = 0; i < 12; i++) { s += Math.pow(10, LM.strips.amb.rms / 10); await new Promise(r => setTimeout(r, 120)); } return 10 * Math.log10(s / 12); });
  const amb = await avg();
  ok('the scene sounds on the Ambience strip after its fade-in', amb > -60, amb.toFixed(1) + ' dB');
  ok('button reads Stop scene', (await page.locator('#sceneGo').textContent()) === 'Stop scene');
  // live level dial
  const lvl = page.locator('#sceneWrap .layer [aria-label=Level]');
  await lvl.focus(); for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowDown');
  await page.waitForTimeout(1200);
  const amb2 = await avg();
  ok('lowering the layer level 6 dB is heard while it plays', amb - amb2 > 4 && amb - amb2 < 8, `${amb.toFixed(1)} -> ${amb2.toFixed(1)} dB`);
  // random layer
  await page.click('text=Add layer'); await page.waitForTimeout(200);
  await page.locator('#sceneWrap .layer').nth(1).locator('.seg button', { hasText: 'Random' }).click(); await page.waitForTimeout(300);
  ok('random layer shows eight dials', (await page.locator('#sceneWrap .layer').nth(1).locator('[role=slider]').count()) === 8);
  await page.locator('#sceneWrap .layer').nth(1).locator('[aria-label="Gap max"]').focus(); await page.keyboard.press('Home');
  await page.locator('#sceneWrap .layer').nth(1).locator('[aria-label="Gap min"]').focus(); await page.keyboard.press('Home');
  const gaps = await page.evaluate(() => [cur().layers[1].gMin, cur().layers[1].gMax]);
  ok('gap dials reach the shortest gaps (0.5 s)', gaps.join() === '0,0', gaps.join());
  await page.waitForTimeout(500);
  const fired = await page.evaluate(async () => { const h = [...running.values()][0]; const n0 = h.sources.size; await new Promise(r => setTimeout(r, 3000)); return [n0, h.sources.size, h.timers.size]; });
  ok('the random layer keeps a timer and fires one-shots', fired[2] >= 1 && fired[1] >= 1, JSON.stringify(fired));
  // remove with two taps
  await page.locator('#sceneWrap .layer').nth(1).locator('text=Remove').click();
  ok('first tap asks', (await page.locator('#sceneWrap .layer').count()) === 2);
  await page.locator('#sceneWrap .layer').nth(1).locator('text=Tap again').click(); await page.waitForTimeout(300);
  ok('second tap removes the layer', (await page.locator('#sceneWrap .layer').count()) === 1);
  // second scene crossfades
  await page.click('text=New scene'); await page.waitForTimeout(200);
  ok('new scene is selected and empty', (await page.locator('#sceneWrap .layer').count()) === 0 && (await page.evaluate(() => scenes.length)) === 2);
  await page.click('text=Add layer'); await page.waitForTimeout(200);
  await page.locator('#sceneWrap .layer select').first().selectOption({ index: 2 });
  await page.click('#sceneGo'); await page.waitForTimeout(400);
  const runIds = await page.evaluate(() => [...running.keys()].length);
  ok('starting scene 2 stops scene 1 (crossfade), one scene runs', runIds === 1);
  await page.waitForTimeout(2500);
  await page.click('#sceneGo'); await page.waitForTimeout(2600);
  ok('stop scene fades to silence', (await page.evaluate(() => LM.strips.amb.rms)) < -60);
  // delete scene asks twice
  await page.click('text=Delete scene'); ok('delete asks first', (await page.evaluate(() => scenes.length)) === 2);
  await page.click('text=Tap again to delete'); await page.waitForTimeout(300);
  ok('second tap deletes the scene', (await page.evaluate(() => scenes.length)) === 1);
  // ---- bounce the scene twice: same variation gives the same file
  await page.click('text=Add layer'); await page.waitForTimeout(200);
  await page.locator('#sceneWrap .layer').nth(1).locator('.seg button', { hasText: 'Random' }).click(); await page.waitForTimeout(300);
  const get = async () => { const [d] = await Promise.all([page.waitForEvent('download', { timeout: 60000 }), page.click('text=Bounce scene WAV')]); const f = path.join(__dirname, 'out', 'out-scene-' + Math.random().toString(36).slice(2) + '.wav'); await d.saveAs(f); return fs.readFileSync(f); };
  const b1 = await get(); const b2 = await get();
  const w = wavInfo(b1);
  ok('scene bounce: stereo 24-bit WAV, 30 s default? length matches the Bounce length dial', w.ch === 2 && w.bits === 24 && Math.abs(w.secs - (await page.evaluate(() => SCENE_LENS[cur().len]))) < 0.05 && w.peak > -60, JSON.stringify(w));
  ok('same variation gives byte-identical files', Buffer.compare(b1, b2) === 0);
  await page.click('text=New variation');
  const b3 = await get();
  ok('a new variation changes the random layer', Buffer.compare(b1, b3) !== 0);
  console.log('errors:', JSON.stringify(errors));
  await page.screenshot({ path: 'shot-scene.png' });
  await browser.close();
})();
