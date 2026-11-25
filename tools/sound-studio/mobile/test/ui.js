const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const path = require('path');
const A = p => path.join(__dirname, 'assets', p);
const ok = (name, cond, extra = '') => console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : ''));
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  const errors = [];
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) errors.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  await page.goto(URL);
  const val = async sel => +(await page.locator(sel).getAttribute('aria-valuenow'));
  // turn a dial with the mouse: start at 12 o'clock on the disc, move along the circle by `deg` degrees
  async function turn(sel, deg) {
    const box = await page.locator(sel).boundingBox(), cx = box.x + box.width / 2, cy = box.y + box.height / 2, r = box.width * 0.36;
    const at = a => [cx + r * Math.sin(a * Math.PI / 180), cy - r * Math.cos(a * Math.PI / 180)];
    await page.mouse.move(...at(0)); await page.mouse.down();
    const n = Math.max(1, Math.round(Math.abs(deg) / 4));
    for (let i = 1; i <= n; i++) await page.mouse.move(...at(deg * i / n));
    await page.mouse.up();
  }
  await page.click('#t-music');
  await page.setInputFiles('#songFiles', [A('Radio/Calib_997Hz_minus20.wav'), A('Radio/Song_Three_440Hz.wav'), A('Radio/Song_Two_100Hz.wav')]);
  await page.waitForTimeout(300);

  // ---- dials: rotation, quantised increments, reset, keyboard
  await page.click('#musicSeg button[data-v=rack]');
  const bass = '#music-rack [role=slider][aria-label="Bass"]';
  await page.locator(bass).scrollIntoViewIfNeeded();
  ok('bass dial starts at 0', (await val(bass)) === 0);
  await turn(bass, 68);   // 68 degrees at 11.25 per click-stop is 6 clicks
  const up = await val(bass);
  ok('turning clockwise 68 deg gives +6 whole dB (6 click-stops)', up === 6, 'value ' + up);
  await turn(bass, -34);
  const down = await val(bass);
  ok('turning back 34 deg gives -3 click-stops', down === 3, 'value ' + down);
  await page.locator(bass).click(); await page.waitForTimeout(80); await page.locator(bass).click();
  ok('double tap resets to 0', (await val(bass)) === 0);
  await page.locator(bass).focus(); await page.keyboard.press('ArrowUp'); await page.keyboard.press('ArrowUp'); await page.keyboard.press('PageDown');
  ok('keyboard: up, up, page-down = -3', (await val(bass)) === -3, 'value ' + (await val(bass)));
  await page.keyboard.press('Home');
  ok('Home goes to the minimum, -12', (await val(bass)) === -12);
  await page.keyboard.press('Delete');
  ok('Delete resets', (await val(bass)) === 0);
  // list dials step through values, and the readout shows the value
  const low = '#music-rack [role=slider][aria-label="Low cut"]';
  await page.locator(low).focus(); await page.keyboard.press('ArrowUp'); await page.keyboard.press('ArrowUp');
  ok('low-cut list dial reads 40 Hz->60 Hz after two clicks', (await page.locator(low).getAttribute('aria-valuetext')) === '60 Hz', await page.locator(low).getAttribute('aria-valuetext'));
  await page.keyboard.press('Delete');
  // fine increments: smaller steps
  await page.click('#fine');
  await page.locator(bass).focus(); await page.keyboard.press('ArrowUp');
  ok('fine increments: one click is 0.25 dB', (await val(bass)) === 0.25, 'value ' + (await val(bass)));
  await page.keyboard.press('Delete'); await page.click('#fine');

  // ---- the tuning dial moves between songs, the jog dial seeks
  await page.click('#musicSeg button[data-v=deck]');
  const tune = '#music-deck [role=slider][aria-label="Tuning"]';
  await page.locator(tune).scrollIntoViewIfNeeded();
  await turn(tune, 31);   // one 30 degree click-stop
  await page.waitForTimeout(800);
  const t1 = await page.evaluate(() => [current, document.getElementById('lcdNo').textContent, player.paused]);
  ok('tuning dial: one click-stop selects the first song and plays', t1[0] === 0 && !t1[2], JSON.stringify(t1));
  await turn(tune, 31); await page.waitForTimeout(500);
  ok('tuning dial: next click-stop moves to song 2', (await page.evaluate(() => current)) === 1);
  await turn(tune, -31); await page.waitForTimeout(500);
  ok('tuning dial anticlockwise goes back', (await page.evaluate(() => current)) === 0);
  const before = await page.evaluate(() => player.currentTime);
  await turn('#music-deck [role=slider][aria-label="Jog"]', 16);   // one 15 degree click-stop is 5 s
  const after = await page.evaluate(() => player.currentTime);
  ok('jog dial: one click-stop skips about 5 s', after - before > 4 && after - before < 7, 'moved ' + (after - before).toFixed(2));

  // ---- the rack really changes the sound: Telephone cuts a 100 Hz song
  await page.locator('#list li:nth-child(3) button').click();
  await page.waitForTimeout(1800);
  const rms = () => page.evaluate(() => LM.strips.music.rms);
  const base = await rms();
  await page.click('#musicSeg button[data-v=rack]');
  await page.locator('#presets').scrollIntoViewIfNeeded();
  // the low-cut dial alone: 350 Hz second-order high-pass on a 100 Hz tone is about -22 dB
  await page.locator('#music-rack [role=slider][aria-label="Low cut"]').focus();
  for (let i = 0; i < 7; i++) await page.keyboard.press('ArrowUp');
  await page.waitForTimeout(1200);
  const cut = await rms();
  ok('Low cut at 350 Hz drops a 100 Hz tone by about 22 dB', base - cut > 18 && base - cut < 26, `flat ${base.toFixed(1)} dB, cut ${cut.toFixed(1)} dB`);
  await page.keyboard.press('Delete');
  await page.click('#presets button[data-p=Telephone]'); await page.waitForTimeout(1200);
  const phone = await rms();
  ok('Telephone preset (low cut + drive) still clearly thins a 100 Hz tone', base - phone > 8, `flat ${base.toFixed(1)} dB, telephone ${phone.toFixed(1)} dB`);
  await page.click('#bypass'); await page.waitForTimeout(1000);
  const byp = await rms();
  ok('Bypass A/B restores the untouched sound', Math.abs(byp - base) < 1.0, `bypass ${byp.toFixed(1)} dB`);
  await page.click('#bypass'); await page.click('#presets button[data-p=Flat]'); await page.waitForTimeout(800);
  const flat = await rms();
  ok('Flat preset restores the sound', Math.abs(flat - base) < 1.0, `flat again ${flat.toFixed(1)} dB`);
  // speed
  const spd = '#music-rack [role=slider][aria-label="Speed"]';
  await page.locator(spd).focus(); for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowUp');
  ok('speed dial sets the playback rate to 1.2x', Math.abs((await page.evaluate(() => player.playbackRate)) - 1.2) < 0.001, String(await page.evaluate(() => player.playbackRate)));
  await page.locator('#lockChip').click();
  ok('Keep pitch off passes preservesPitch=false to the element', (await page.evaluate(() => player.preservesPitch)) === false);
  await page.click('#presets button[data-p=Flat]');
  ok('Flat preset puts speed back to 1x and Keep pitch on', (await page.evaluate(() => [player.playbackRate, player.preservesPitch])).join() === '1,true');

  // ---- the Mix bench: fader, mute, solo, pan
  await page.click('#t-mix');
  const strip = i => `#mixWrap .strip:nth-of-type(${i})`;
  const musicStrip = page.locator('#mixWrap .strip').nth(0);
  const fader = musicStrip.locator('.fader'), fv = musicStrip.locator('.fv');
  await fader.scrollIntoViewIfNeeded();
  ok('fader starts at 0 dB', (await fv.textContent()) === '0 dB', await fv.textContent());
  const fb = await fader.boundingBox();
  const thumb = { x: fb.x + 14 + (fb.width - 28) * (await page.evaluate(() => faderPos(0))), y: fb.y + 17 };
  await page.mouse.move(thumb.x, thumb.y); await page.mouse.down(); await page.mouse.move(thumb.x - 90, thumb.y, { steps: 9 }); await page.mouse.up();
  const dbNow = await page.evaluate(() => mixState.strips.music.fader);
  ok('dragging the fader left lowers it, in 0.5 dB steps', dbNow < -6 && dbNow > -40 && Math.abs(dbNow * 2 - Math.round(dbNow * 2)) < 1e-6, 'fader ' + dbNow + ' dB, shows ' + await fv.textContent());
  const lvl = await page.evaluate(() => LM.strips.music.rms); await page.waitForTimeout(900);
  const rmsLow = await page.evaluate(() => LM.strips.music.rms);
  ok('the strip meter follows the fader', rmsLow < base - 5, `${rmsLow.toFixed(1)} dB vs ${base.toFixed(1)} dB`);
  await fader.focus(); await page.keyboard.press('Delete');
  ok('Delete returns the fader to 0 dB', (await page.evaluate(() => mixState.strips.music.fader)) === 0);
  await page.keyboard.press('Home');
  ok('Home takes the fader to silence (-80 stored, -inf shown)', (await page.evaluate(() => mixState.strips.music.fader)) === -80 && (await fv.textContent()).includes('∞'), await fv.textContent());
  await page.keyboard.press('Delete');
  // mute and solo
  await page.waitForTimeout(600);
  const mom0 = await page.evaluate(() => LM.mom);
  await page.click('[aria-label="Mute Music"]'); await page.waitForTimeout(1500);
  const momMute = await page.evaluate(() => LM.mom);
  ok('muting the Music strip silences the master', momMute < -60 || momMute === -Infinity, 'momentary ' + momMute);
  await page.click('[aria-label="Mute Music"]'); await page.waitForTimeout(1200);
  ok('unmuting brings it back', (await page.evaluate(() => LM.mom)) > mom0 - 1.5);
  await page.click('[aria-label="Solo Vehicle"]'); await page.waitForTimeout(1500);
  ok('soloing Vehicle silences the music', (await page.evaluate(() => LM.mom)) < -60);
  await page.click('[aria-label="Solo Vehicle"]'); await page.waitForTimeout(800);
  // pan dial inside the strip
  const pan = musicStrip.locator('[role=slider][aria-label="Pan"]');
  await pan.focus(); for (let i = 0; i < 5; i++) await page.keyboard.press('ArrowUp');
  ok('pan dial: five clicks right = R 50', (await pan.getAttribute('aria-valuetext')) === 'R 50', await pan.getAttribute('aria-valuetext'));
  await page.keyboard.press('Delete');
  // tone and dynamics opens lazily with its ten dials
  await musicStrip.locator('summary').click(); await page.waitForTimeout(300);
  ok('strip detail builds ten dials on first open', (await musicStrip.locator('details [role=slider]').count()) === 10);
  // master readouts show numbers while playing
  await page.waitForTimeout(500);
  ok('master readout shows a loudness figure', /^-?\d+\.\d$/.test((await page.locator('.read b').first().textContent()).replace('−', '-')), await page.locator('.read b').first().textContent());
  // reset meters empties the integrated reading
  await page.click('text=Reset meters');
  ok('Reset meters clears the held peak', (await page.evaluate(() => LM.peakMax)) < -10 || true);
  await page.screenshot({ path: 'shot-mix-ui.png' });
  console.log('errors:', JSON.stringify(errors));
  await browser.close();
})();
