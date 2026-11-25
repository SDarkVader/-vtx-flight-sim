const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const path = require('path'), fs = require('fs');
const A = p => path.join(__dirname, 'assets', p);
const SOUNDS = fs.readdirSync(A('Sounds')).map(f => A('Sounds/' + f));
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  for (const width of [320, 360, 390, 430]) {
    const page = await (await browser.newContext({ viewport: { width, height: 800 }, deviceScaleFactor: 1 })).newPage();
    await page.goto(URL);
    await page.click('#t-music'); await page.setInputFiles('#songFiles', [A('Radio/Calib_997Hz_minus20.wav')]);
    await page.click('#t-takes'); await page.setInputFiles('#takesWrap input[type=file][multiple]', SOUNDS); await page.waitForTimeout(700);
    await page.click('#t-vehicle'); await page.click('#open-wings');
    await page.click('#t-scene'); await page.click('text=Add layer'); await page.click('text=Add layer');
    await page.locator('#sceneWrap .layer').nth(1).locator('.seg button', { hasText: 'Random' }).click();
    await page.click('#t-takes'); await page.locator('#takeList .take', { hasText: 'wing_deployment' }).locator('.pick-take').click(); await page.waitForTimeout(600);
    await page.click('#editorBody >> text=Loop points');
    const bad = [];
    for (const tab of ['tracks', 'mix', 'music', 'vehicle', 'scene', 'takes']) {
      await page.click('#t-' + tab); await page.waitForTimeout(200);
      if (tab === 'music') { for (const v of ['deck', 'rack']) { await page.click(`#musicSeg button[data-v=${v}]`); await page.waitForTimeout(100); const w = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]); if (w[0] > w[1]) bad.push(`music/${v} ${w}`); } }
      const w = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth, [...document.querySelectorAll('.tab:not([hidden]) *')].filter(e => !e.closest('.tl-scroll') && e.getBoundingClientRect().right > innerWidth + 1).slice(0, 3).map(e => e.tagName + '.' + e.className)]);
      if (w[0] > w[1] || w[2].length) bad.push(`${tab} scrollWidth ${w[0]} vs ${w[1]} ${w[2]}`);
    }
    console.log((bad.length ? 'FAIL ' : 'PASS ') + `no sideways scroll on any bench at ${width}px wide` + (bad.length ? '  ' + bad.join(' | ') : ''));
    await page.close();
  }
  await browser.close();
})();
