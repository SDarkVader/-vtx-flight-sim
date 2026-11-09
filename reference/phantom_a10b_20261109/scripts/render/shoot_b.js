const { chromium } = require('playwright'); const fs = require('fs'); const S = process.argv[2];
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.goto('http://127.0.0.1:8791/render.html'); await page.waitForFunction(() => window.ready === true);
  await page.evaluate(() => window.loadModel('/assets/phantom-a10b-visual.glb'));
  const f = JSON.parse(fs.readFileSync(`${S}/shots/deploy.json`, 'utf8'))[2];
  f.label = 'A10-B visual model: wings locked, 7 deg incidence'; f.note = 'updated model public/assets/phantom-a10b-visual.glb';
  await page.evaluate(([f, v]) => { window.CONFIG = 'phantom-a10b'; return window.renderFrame(f, v); }, [f, {offset:[-0.5,-9.5,1.2],followYaw:true,fov:34,lookZ:0.8}]);
  await page.waitForTimeout(150); await page.screenshot({ path: `${S}/shots/14_a10b_model_side.png` });
  await page.evaluate(([f, v]) => window.renderFrame(f, v), [f, {offset:[-8.5,7.5,4.2],followYaw:true,fov:38}]);
  await page.waitForTimeout(150); await page.screenshot({ path: `${S}/shots/15_a10b_model_rear.png` });
  await browser.close(); console.log('ok');
})();
