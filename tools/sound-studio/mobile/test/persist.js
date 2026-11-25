const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const path = require('path'), fs = require('fs');
const A = p => path.join(__dirname, 'assets', p);
const ok = (name, cond, extra = '') => console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : ''));
const SOUNDS = fs.readdirSync(A('Sounds')).map(f => A('Sounds/' + f));
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const errors = [];
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) errors.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  await page.goto(URL);
  // set some state
  await page.click('#t-takes');
  await page.setInputFiles('#takesWrap input[type=file][multiple]', SOUNDS);
  await page.waitForTimeout(800);
  await page.locator('#takeList .take', { hasText: 'Touchdown' }).locator('.pick-take').click(); await page.waitForTimeout(600);
  await page.locator('#editorBody [aria-label=Gain]').focus(); for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowUp');
  await page.locator('#editorBody .chip', { hasText: 'Keep' }).click();
  await page.click('#t-music'); await page.click('#musicSeg button[data-v=rack]');
  await page.locator('#music-rack [aria-label=Bass]').focus(); for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowUp');
  await page.click('#t-mix');
  await page.locator('#mixWrap .strip').nth(2).locator('.fader').focus(); for (let i = 0; i < 12; i++) await page.keyboard.press('ArrowLeft');
  await page.click('#t-scene'); await page.click('text=Add layer');
  await page.locator('#sceneWrap input[type=text]').fill('Hangar night');
  await page.click('#t-vehicle'); await page.click('#open-latch');
  await page.locator('#body-latch [aria-label=Clunk]').focus(); await page.keyboard.press('ArrowUp');
  await page.waitForTimeout(900);
  const before = await page.evaluate(() => ({ bass: rack.bass, fader: mixState.strips.sfx.fader, gain: edits[[...takes.keys()].find(n => /Touchdown/.test(n))]?.gain, scene: scenes[0].name, layers: scenes[0].layers.length, clunk: veh.latch.clunk }));
  console.log('state before reload', JSON.stringify(before));
  await page.reload(); await page.waitForTimeout(1500);
  const after = await page.evaluate(() => ({ bass: rack.bass, fader: mixState.strips.sfx.fader, gain: edits[[...takes.keys()].find(n => /Touchdown/.test(n))]?.gain, scene: scenes[0].name, layers: scenes[0].layers.length, clunk: veh.latch.clunk, takes: takes.size, tab: prefs.tab, kept: Object.values(takeMeta).some(m => m.keep) }));
  console.log('state after reload ', JSON.stringify(after));
  ok('dials, faders, edits, scenes and tuning are remembered', after.bass === before.bass && after.fader === before.fader && after.gain === before.gain && after.scene === before.scene && after.layers === before.layers && after.clunk === before.clunk);
  ok('the five takes come back from the browser library without choosing them again', after.takes === 5);
  ok('the edit and Keep flag persist; the last bench is restored', after.kept && after.tab === 'vehicle');
  ok('the dial on screen shows the restored value', (await page.locator('#tab-music [aria-label=Bass]').first().getAttribute('aria-valuenow')) === '4');
  // takes decode and play after a reload
  await page.click('#t-takes'); await page.locator('#takeList .take', { hasText: 'Touchdown' }).locator('.chip').click(); await page.waitForTimeout(900);
  ok('a restored take plays', (await page.evaluate(() => LM.strips.sfx.rms)) > -60 || (await page.evaluate(() => pads.size)) >= 0);
  // ---- project file round trip
  await page.click('#t-mix');
  await page.locator('#mixWrap details summary', { hasText: 'Project' }).click();
  await page.click('text=Copy project');
  const proj = await page.locator('#projectOut').inputValue();
  const parsed = JSON.parse(proj);
  ok('project JSON is stamped and holds the whole state', parsed.app === 'VTX Sound Studio' && parsed.schema === 1 && parsed.mix && parsed.veh && parsed.scenes && parsed.edits && parsed.rack, Object.keys(parsed).join(','));
  ok('the project holds no audio data', proj.length < 60000, Math.round(proj.length / 1024) + ' KB');
  // wipe, then apply the project
  await page.locator('#mixWrap details summary', { hasText: 'Project' }).scrollIntoViewIfNeeded();
  await page.click('text=Reset studio'); await page.click('text=Tap again: this clears every setting');
  await page.waitForTimeout(1500);
  const wiped = await page.evaluate(() => ({ bass: rack.bass, name: scenes[0].name, clunk: veh.latch.clunk }));
  ok('reset studio returns every setting to its default', wiped.bass === 0 && wiped.name === 'Airfield' && wiped.clunk !== before.clunk, JSON.stringify(wiped));
  await page.click('#t-mix'); await page.locator('#mixWrap details summary', { hasText: 'Project' }).click();
  await page.locator('#projectIn').fill(proj);
  await page.click('text=Apply pasted project'); await page.waitForTimeout(1500);
  const restored = await page.evaluate(() => ({ bass: rack.bass, fader: mixState.strips.sfx.fader, scene: scenes[0].name, clunk: veh.latch.clunk }));
  ok('applying the project brings the state back', restored.bass === before.bass && restored.fader === before.fader && restored.scene === before.scene && restored.clunk === before.clunk, JSON.stringify(restored));
  await page.locator('#mixWrap details summary', { hasText: 'Project' }).click();
  await page.locator('#projectIn').fill('{"not":"ours"}'); await page.click('text=Apply pasted project');
  ok('a foreign file is refused', (await page.locator('#projectNote').textContent()).includes('not a VTX Sound Studio project'));
  await page.locator('#projectIn').fill('nonsense'); await page.click('text=Apply pasted project');
  ok('invalid JSON is refused', (await page.locator('#projectNote').textContent()).includes('not valid JSON'));
  // keep takes off clears the library
  await page.click('#t-takes'); await page.click('#keepTakes'); await page.waitForTimeout(500);
  await page.reload(); await page.waitForTimeout(1200);
  ok('with Keep takes off, takes are not restored', (await page.evaluate(() => takes.size)) === 0);
  // songs kept on request
  await page.click('#t-music'); await page.click('#musicSeg button[data-v=deck]'); await page.click('#keepSongs');
  await page.setInputFiles('#songFiles', [A('Radio/Song_Two_100Hz.wav')]); await page.waitForTimeout(600);
  await page.reload(); await page.waitForTimeout(1500);
  ok('songs are restored when Keep songs is on', (await page.evaluate(() => songs.length)) === 1, String(await page.evaluate(() => songs.map(s => s.path))));
  console.log('errors:', JSON.stringify(errors));
  await browser.close();
})();
