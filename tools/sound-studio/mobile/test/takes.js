const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const path = require('path'), fs = require('fs'), cp = require('child_process');
const A = p => path.join(__dirname, 'assets', p);
const ok = (name, cond, extra = '') => console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : ''));
const SOUNDS = fs.readdirSync(A('Sounds')).map(f => A('Sounds/' + f));
function wavInfo(buf) {   // parse a PCM wav: returns channels, rate, bits, frames, peak in dBFS
  const v = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const tag = o => String.fromCharCode(v.getUint8(o), v.getUint8(o + 1), v.getUint8(o + 2), v.getUint8(o + 3));
  if (tag(0) !== 'RIFF' || tag(8) !== 'WAVE') return null;
  const ch = v.getUint16(22, true), rate = v.getUint32(24, true), bits = v.getUint16(34, true), len = v.getUint32(40, true), n = len / (ch * bits / 8);
  let peak = 0, o = 44;
  for (let i = 0; i < n * ch; i++) {
    let x; if (bits === 16) { x = v.getInt16(o, true) / 32768; o += 2; } else { x = (v.getUint8(o) | v.getUint8(o + 1) << 8 | v.getInt8(o + 2) << 16) / 8388608; o += 3; }
    if (Math.abs(x) > peak) peak = Math.abs(x);
  }
  return { ch, rate, bits, frames: n, secs: n / rate, peak: 20 * Math.log10(peak) };
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
  ok('five takes listed', (await page.locator('#takeList .take').count()) === 5);
  ok('Vehicle parts auto-picked takes by name', await page.evaluate(() => veh.wings.source.includes('wing_deployment') && veh.legs.source.includes('geared_electric_motor') && veh.fans.source.includes('ducted_fan')), await page.evaluate(() => JSON.stringify([veh.wings.source.slice(0, 30), veh.legs.source.slice(0, 30), veh.fans.source.slice(0, 30)])));

  // ---- editor on the wing take: 0.4 s of silence in front, 3 s of sound, 0.5 s behind
  const wingName = await page.evaluate(() => [...takes.keys()].find(n => /wing_deployment/.test(n)));
  await page.locator('#takeList .take', { hasText: 'wing_deployment' }).locator('.pick-take').click();
  await page.waitForTimeout(700);
  ok('editor opens with a waveform canvas', await page.locator('#editorBody canvas.wave').count() === 1);
  const filled = await page.evaluate(() => { const c = document.querySelector('#editorBody canvas.wave'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n / (d.length / 4); });
  ok('waveform has been drawn', filled > 0.05, (filled * 100).toFixed(1) + '% of pixels');
  const stats = await page.evaluate(n => takes.get(n).stats, wingName);
  ok('take statistics: peak -9 dBFS, mono, 3.9 s', Math.abs(stats.peak + 9) < 0.3 && stats.ch === 1, JSON.stringify(stats));
  await page.click('#editorBody >> text=Auto trim');
  const e1 = await page.evaluate(n => edits[n], wingName);
  ok('Auto trim finds the silence either side (in ~0.4 s, out ~3.4 s)', e1 && Math.abs(e1.in - 0.4) < 0.08 && Math.abs(e1.out - 3.4) < 0.12, JSON.stringify(e1));
  // drag the IN handle on the waveform
  await page.locator('#editorBody canvas.wave').scrollIntoViewIfNeeded(); await page.waitForTimeout(700);
  const cv = await page.locator('#editorBody canvas.wave').boundingBox();
  const inX = cv.x + cv.width * (e1.in / 3.9);
  await page.mouse.move(inX, cv.y + 10); await page.mouse.down(); await page.mouse.move(inX + cv.width * 0.1, cv.y + 10, { steps: 6 }); await page.mouse.up();
  const e2 = await page.evaluate(n => edits[n], wingName);
  ok('dragging the IN handle moves the trim by about 0.39 s', e2.in > e1.in + 0.3 && e2.in < e1.in + 0.5, 'in ' + e2.in);
  ok('the In dial follows the handle', Math.abs((await page.locator('#editorBody [aria-label=In]').getAttribute('aria-valuenow')) - e2.in) < 0.011);
  // dial edits: fade, gain, normalise
  await page.locator('#editorBody [aria-label=Gain]').focus(); for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowUp');
  ok('Gain dial +2 dB', (await page.evaluate(n => edits[n].gain, wingName)) === 2);
  await page.locator('#editorBody [aria-label="Fade in"]').focus(); for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowUp');
  ok('Fade in 30 ms in 10 ms increments', (await page.evaluate(n => edits[n].fadeIn, wingName)) === 30);
  // loop points
  await page.click('#editorBody >> text=Loop points');
  const e3 = await page.evaluate(n => edits[n], wingName);
  ok('loop points appear inside the trim', e3.loopIn > e3.in && e3.loopOut <= e3.out + 1e-9 && e3.loopIn < e3.loopOut, JSON.stringify(e3));
  ok('loop dials exist', await page.locator('#editorBody [aria-label="Loop in"]').count() === 1);
  // baked buffer
  const baked = await page.evaluate(async n => { const b = await bufferOf(n); return { secs: b.duration, loop: b.body.loop, peakDb: (() => { const d = b.getChannelData(0); let p = 0; for (const v of d) p = Math.max(p, Math.abs(v)); return 20 * Math.log10(p); })() }; }, wingName);
  ok('baked take: length = out - in, peak -1 dBFS (-3 normalise + 2 gain), even with a loop crossfade', Math.abs(baked.secs - (e3.out - e3.in)) < 0.02 && Math.abs(baked.peakDb - (-3 + 2)) < 0.25, JSON.stringify(baked));
  await page.waitForTimeout(400);
  ok('editor shows the result peak', /peak -1 dB/.test((await page.locator('#resultInfo').textContent()).replace('\u2212','-')), await page.locator('#resultInfo').textContent());
  ok('baked take carries a loop region', Array.isArray(baked.loop) && baked.loop[1] > baked.loop[0]);
  // audition plays through the SFX strip
  await page.click('#editorBody >> text=Play');
  await page.waitForTimeout(900);
  const sfx = await page.evaluate(() => LM.strips.sfx.rms);
  ok('Play in the editor sounds on the SFX strip', sfx > -60, 'sfx strip ' + sfx.toFixed(1) + ' dB');
  ok('playhead readout is running', /\d:\d\d \/ \d:\d\d/.test(await page.locator('#padClock').textContent()), await page.locator('#padClock').textContent());
  await page.click('#editorBody >> text=Stop');

  // ---- bounce a take to WAV (24-bit)
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#editorBody >> text=Bounce WAV')]);
  const out = path.join(__dirname, 'out', 'out-' + dl.suggestedFilename());
  await dl.saveAs(out);
  const info = wavInfo(fs.readFileSync(out));
  ok('bounced file is a 24-bit WAV', info && info.bits === 24 && info.ch === 1, JSON.stringify(info));
  ok('bounce length matches the trim (' + (e3.out - e3.in).toFixed(2) + ' s)', info && Math.abs(info.secs - (e3.out - e3.in)) < 0.02, 'secs ' + (info && info.secs.toFixed(3)));
  ok('bounce peak is -1 dBFS (-3 normalise + 2 gain)', info && Math.abs(info.peak + 1) < 0.35, 'peak ' + (info && info.peak.toFixed(2)));
  console.log('   saved as', dl.suggestedFilename());

  // ---- keep + bounce kept takes as a zip
  await page.locator('#editorBody .chip', { hasText: 'Keep' }).click();
  await page.locator('#takeList .take', { hasText: 'Touchdown' }).locator('.pick-take').click(); await page.waitForTimeout(500);
  await page.locator('#editorBody .chip', { hasText: 'Keep' }).click();
  const [dz] = await Promise.all([page.waitForEvent('download'), page.click('text=Bounce kept takes')]);
  const zout = path.join(__dirname, 'out', 'out-kept.zip'); await dz.saveAs(zout);
  const zl = cp.execSync(`python3 - <<'PY'\nimport zipfile\nz=zipfile.ZipFile(${JSON.stringify(zout)})\nprint(z.testzip(), [ (i.filename, i.file_size) for i in z.infolist()])\nPY`).toString().trim();
  ok('zip of kept takes is valid and holds two WAVs', /^None/.test(zl) && (zl.match(/\.wav/g) || []).length === 2, zl);
  // picks JSON
  await page.click('text=Copy picks JSON');
  const picks = await page.locator('#picksOut').inputValue();
  ok('picks JSON lists the kept takes and the edit', picks.includes('"keep": true') && picks.includes('"gain": 2'), picks.slice(0, 120).replace(/\n/g, ' '));
  // reset edit
  await page.locator('#takeList .take', { hasText: 'wing_deployment' }).locator('.pick-take').click(); await page.waitForTimeout(500);
  await page.click('#editorBody >> text=Reset edit');
  ok('Reset edit clears the edit', (await page.evaluate(n => edits[n], wingName)) === undefined);
  // remove from studio needs two taps
  await page.click('#editorBody >> text=Remove from studio'); ok('first tap only asks', (await page.locator('#takeList .take').count()) === 5);
  await page.click('#editorBody >> text=Tap again to remove'); await page.waitForTimeout(300);
  ok('second tap removes the take', (await page.locator('#takeList .take').count()) === 4);

  console.log('errors:', JSON.stringify(errors));
  await page.screenshot({ path: 'shot-takes-editor.png', fullPage: false });
  await browser.close();
})();
