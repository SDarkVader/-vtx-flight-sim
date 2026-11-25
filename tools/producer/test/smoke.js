const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 })).newPage();
  const errors = [];
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) errors.push(m.type() + ': ' + m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  await page.goto(URL);
  await page.waitForTimeout(500);
  const ok = (n, c, e = '') => console.log((c ? 'PASS ' : 'FAIL ') + n + (e ? '  ' + e : ''));
  ok('page title', (await page.title()) === 'VTX Producer');
  for (const tab of ['mix', 'music', 'vehicle', 'scene', 'takes']) {
    await page.click(`#t-${tab}`);
    await page.waitForTimeout(250);
    const sw = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
    ok(tab + ' bench fits the screen width', sw[0] <= sw[1], sw.join('/'));
    await page.screenshot({ path: `shot-${tab}.png`, fullPage: false });
  }
  ok('four channel strips', (await page.evaluate(() => document.querySelectorAll('.strip').length)) === 4);
  ok('dials are built', (await page.evaluate(() => document.querySelectorAll('.dial').length)) > 40);
  ok('no console errors or warnings', errors.length === 0, JSON.stringify(errors));
  await browser.close();
})();
