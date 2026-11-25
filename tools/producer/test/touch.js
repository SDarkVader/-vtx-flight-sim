const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const path = require('path'), fs = require('fs');
const A = p => path.join(__dirname, 'assets', p);
const ok = (name, cond, extra = '') => console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : ''));
const SOUNDS = fs.readdirSync(A('Sounds')).map(f => A('Sounds/' + f));
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto(URL);
  const touch = async (type, x, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y, id: 1 }] });
  async function swipe(points) { await touch('touchStart', ...points[0]); for (const p of points.slice(1)) { await touch('touchMove', ...p); await page.waitForTimeout(12); } await touch('touchEnd'); }
  const arc = (box, from, to, n = 20) => { const cx = box.x + box.width / 2, cy = box.y + box.height / 2, r = box.width * 0.36; return Array.from({ length: n + 1 }, (_, i) => { const a = (from + (to - from) * i / n) * Math.PI / 180; return [cx + r * Math.sin(a), cy - r * Math.cos(a)]; }); };
  await page.tap('#t-music'); await page.tap('#musicSeg button[data-v=rack]'); await page.waitForTimeout(200);
  const bass = page.locator('#music-rack [aria-label=Bass]');
  await bass.scrollIntoViewIfNeeded(); await page.waitForTimeout(200);
  const y0 = await page.evaluate(() => scrollY);
  const box = await bass.boundingBox();
  await swipe(arc(box, 0, 68));
  ok('touch: turning a dial 68 deg gives +6 click-stops', (await bass.getAttribute('aria-valuenow')) === '6', await bass.getAttribute('aria-valuenow'));
  ok('touch: a finger on a dial does not scroll the page', (await page.evaluate(() => scrollY)) === y0, `${y0} -> ${await page.evaluate(() => scrollY)}`);
  // double tap resets
  await bass.tap(); await page.waitForTimeout(100); await bass.tap();
  ok('touch: double tap resets the dial', (await bass.getAttribute('aria-valuenow')) === '0', await bass.getAttribute('aria-valuenow'));
  // vertical swipe starting on empty card text scrolls
  const noteBox = await page.locator('#music-rack .note').first().boundingBox();
  const s0 = await page.evaluate(() => scrollY);
  await swipe([[noteBox.x + 30, noteBox.y + 10], [noteBox.x + 30, noteBox.y - 60], [noteBox.x + 30, noteBox.y - 160]]);
  await page.waitForTimeout(400);
  ok('touch: a swipe on plain card area scrolls the page', Math.abs((await page.evaluate(() => scrollY)) - s0) > 40, `${s0} -> ${await page.evaluate(() => scrollY)}`);
  // fader by touch
  await page.tap('#t-mix'); await page.waitForTimeout(200);
  const strip = page.locator('#mixWrap .strip').nth(1);
  await strip.scrollIntoViewIfNeeded(); await page.waitForTimeout(200);
  const fb = await strip.locator('.fader').boundingBox();
  const thumbX = fb.x + 14 + (fb.width - 28) * (await page.evaluate(() => faderPos(0))), ty = fb.y + 17;
  const sy = await page.evaluate(() => scrollY);
  await swipe(Array.from({ length: 12 }, (_, i) => [thumbX - i * 8, ty + (i % 2)]));
  const f = await page.evaluate(() => mixState.strips.veh.fader);
  ok('touch: dragging a fader lowers it without scrolling the page', f < -5 && f > -40 && (await page.evaluate(() => scrollY)) === sy, `fader ${f} dB`);
  // mute by touch (a pause first: the browser swallows a click that follows a swipe within a few milliseconds)
  await page.waitForTimeout(700);
  await page.tap('[aria-label="Mute Vehicle"]');
  await page.waitForTimeout(250);
  ok('touch: M button toggles', await page.evaluate(() => mixState.strips.veh.mute) === true);
  await page.tap('[aria-label="Mute Vehicle"]');
  // tap targets: all buttons and chips at least 40px high, dial faces at least 56 px
  const small = await page.evaluate(() => { const bad = []; for (const e of document.querySelectorAll('button, .chip, select, label.pick, [role=slider]')) { const r = e.getBoundingClientRect(); if (!r.width || !r.height) continue; const min = e.classList.contains('face') ? 56 : 38; if (r.height < min && !e.closest('[hidden]')) bad.push((e.getAttribute('aria-label') || e.textContent || e.className).trim().slice(0, 24) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); } return bad; });
  ok('every visible control on the Mix bench is at least 38 px tall (dials 56+)', small.length === 0, small.slice(0, 6).join('; '));
  console.log('errors', errors);
  await browser.close();
})();
