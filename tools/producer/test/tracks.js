// Tracks bench. Uses the owner's own audio when USER_AUDIO points at a folder with Radio/ and Sounds/ (not in the repo),
// otherwise the synthetic test audio.
const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const path = require('path'), fs = require('fs'), cp = require('child_process');
const ok = (n, c, e = '') => console.log((c ? 'PASS ' : 'FAIL ') + n + (e ? '  ' + e : ''));
const root = process.env.USER_AUDIO || path.join(__dirname, 'assets');
const list = d => fs.readdirSync(path.join(root, d)).filter(f => /\.(wav|mp3|m4a)$/i.test(f)).map(f => path.join(root, d, f));
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true });
  const page = await context.newPage();
  const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(URL);
  ok('opens on the Tracks bench', await page.locator('#tab-tracks').isVisible());
  const sounds = list('Sounds'), songs = list('Radio'), N = Math.min(6, sounds.length);
  await page.setInputFiles('#tracksWrap input[type=file] >> nth=1', sounds.slice(0, N));   // stems: one track each
  await page.waitForFunction(n => arr.tracks.length >= n, N, { timeout: 60000 });
  ok('importing stems makes one track per file', (await page.evaluate(() => arr.tracks.length)) === N);
  await page.evaluate(() => { sel.track = arr.tracks[0].id; arr.pos = 8; });
  await page.setInputFiles('#tracksWrap input[type=file] >> nth=0', [songs[0]]);
  await page.waitForFunction(() => arr.tracks[0].clips.length === 2, null, { timeout: 60000 });
  const c = await page.evaluate(() => arr.tracks[0].clips[1]);
  ok('a song lands on the selected track at the playhead (bar 5 at 120 bpm)', Math.abs(c.start - 8) < 0.01 && c.dur > 20, JSON.stringify({ start: c.start, dur: Math.round(c.dur) }));
  ok('clips and lanes are drawn', (await page.locator('.tclip').count()) === N + 1);
  // play
  await page.click('#tPlay'); await page.waitForTimeout(3000);
  const s = await page.evaluate(() => ({ playing: eng.playing, pos: arrPos(), mom: LM.mom }));
  ok('the timeline plays through the master', s.playing && s.pos > 2 && s.mom > -60, JSON.stringify(s));
  await page.click('#tPlay');
  // select, move, split, undo, chop
  await page.evaluate(() => { TR.scroll.scrollLeft = 0; }); await page.waitForTimeout(100);
  const first = page.locator('.tl-lane >> nth=1').locator('.tclip').first();
  await first.click(); await page.waitForTimeout(150);
  ok('tapping a clip selects it', (await page.locator('.tclip.sel').count()) === 1);
  const bb = await page.locator('.tclip.sel').boundingBox();
  await page.mouse.move(bb.x + bb.width / 2, bb.y + 20); await page.mouse.down(); await page.mouse.move(bb.x + bb.width / 2 + 60, bb.y + 20, { steps: 6 }); await page.mouse.up();
  const moved = await page.evaluate(() => clipOf(sel.clip).clip.start);
  ok('dragging the selected clip moves it, snapped to the beat', moved > 0.4 && Math.abs(moved / 0.5 - Math.round(moved / 0.5)) < 1e-6, 'start ' + moved);
  await page.click('button:text-is("Undo")');
  ok('undo puts it back', (await page.evaluate(() => clipOf(sel.clip)?.clip.start ?? arr.tracks[1].clips[0].start)) === 0);
  await page.evaluate(() => { sel.clip = arr.tracks[1].clips[0].id; arr.pos = arr.tracks[1].clips[0].dur / 2; });
  await page.click('.menu-btn:has-text("Clip")'); await page.click('text=Split at the playhead');
  ok('split makes two clips', (await page.evaluate(() => arr.tracks[1].clips.length)) === 2);
  await page.click('.menu-btn:has-text("Clip")'); await page.click('text=Chop into 4');
  ok('chop into 4 replaces a clip with four', (await page.evaluate(() => arr.tracks[1].clips.length)) === 5);
  await page.click('button:text-is("Redo")').catch(() => {});
  // inspector
  await page.locator('.seg button[data-v=clip]').click();
  ok('clip inspector shows its dials', (await page.locator('#tracksWrap [aria-label=Gain]').count()) >= 1);
  await page.locator('.tl-name').first().click();
  ok('track inspector holds the full channel strip', (await page.locator('#tracksWrap .strip').count()) === 1);
  // bounce the song through the master
  const [d] = await Promise.all([page.waitForEvent('download', { timeout: 120000 }), (async () => { await page.click('.menu-btn:has-text("Bounce")'); await page.click('text=Song through the master (WAV)'); })()]);
  const f = path.join(__dirname, 'out', d.suggestedFilename()); await d.saveAs(f);
  const v = fs.readFileSync(f), secs = v.readUInt32LE(40) / (v.readUInt16LE(22) * v.readUInt16LE(34) / 8) / v.readUInt32LE(24);
  const end = await page.evaluate(() => songEnd());
  ok('song bounce is a WAV as long as the song plus a 2 s tail', Math.abs(secs - end - 2) < 0.1, `${d.suggestedFilename()} ${secs.toFixed(1)} s, song ${end.toFixed(1)} s`);
  // the project survives a reload, audio included
  await page.waitForTimeout(800); await page.reload(); await page.waitForTimeout(2500);
  const back = await page.evaluate(() => ({ tracks: arr.tracks.length, clips: arr.tracks.reduce((n, t) => n + t.clips.length, 0), takes: takes.size }));
  ok('after a reload every track, clip and sound is still there', back.tracks === N && back.clips >= N + 1 && back.takes >= N + 1, JSON.stringify(back));
  await page.click('#tPlay'); await page.waitForTimeout(2500);
  ok('and it plays straight away', (await page.evaluate(() => eng.playing && LM.mom > -70)));
  await page.click('#tPlay');
  ok('no page errors', errors.length === 0, JSON.stringify(errors.slice(0, 3)));
  await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: path.join(__dirname, 'out', 'tracks.png') });
  await browser.close();
})();
