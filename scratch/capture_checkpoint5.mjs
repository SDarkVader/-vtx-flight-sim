import puppeteer from 'file:///C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9/scratch/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js';
import fs from 'fs';
import path from 'path';

const outDir = 'C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox', '--window-size=1600,900']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 900 });
  await page.setCacheEnabled(false);

  await page.goto('http://127.0.0.1:8768/?debug', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => window.__vtx && window.__vtx.world && window.__vtx.model && document.getElementById('loading').hidden,
    { timeout: 120000 }
  );

  await new Promise(r => setTimeout(r, 2000));

  async function setCam(camPos, targetPos) {
    await page.evaluate(({ c, t }) => {
      const v = window.__vtx;
      v.setCameraMode('orbit');
      v.camera.position.set(c[0], c[1], c[2]);
      v.camera.up.set(0, 0, 1);
      v.orbit.target.set(t[0], t[1], t[2]);
      v.camera.lookAt(t[0], t[1], t[2]);
      v.orbit.update();
      v.renderer.render(v.scene, v.camera);
    }, { c: camPos, t: targetPos });
    await new Promise(r => setTimeout(r, 600));
  }

  // 4. Fire Crash Tender Stn 9 (Elevated view from side)
  const firePos = await page.evaluate(() => {
    const v = window.__vtx;
    const g = v.scene.getObjectByName('vtx-gsv-fire-crash-tender');
    return g ? [g.position.x, g.position.y, g.position.z] : [240, 500, 25];
  });
  console.log('Fire tender pos:', firePos);
  await setCam([firePos[0] + 18, firePos[1] - 18, firePos[2] + 9.0], [firePos[0], firePos[1], firePos[2] + 2.0]);
  const shot4 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint5_04_fire_crash_tender_stn9.png'), shot4);

  // 5. Follow-Me Black Cab (Elevated 3/4 view)
  const cabPos = await page.evaluate(() => {
    const v = window.__vtx;
    const g = v.scene.getObjectByName('vtx-gsv-follow-me-cab');
    return g ? [g.position.x, g.position.y, g.position.z] : [0, 100, 0];
  });
  console.log('Black cab pos:', cabPos);
  await setCam([cabPos[0] + 10, cabPos[1] - 14, cabPos[2] + 7.5], [cabPos[0], cabPos[1], cabPos[2] + 1.2]);
  const shot5 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint5_05_follow_me_black_cab.png'), shot5);

  // 6. Crossing Priority Yield Stop Bar (Elevated clear view of checkered line & beacons)
  console.log('Capturing checkpoint5_06_crossing_priority_yield.png...');
  await setCam([-350, 440, 48], [-350, 490, 22]);
  const shot6 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint5_06_crossing_priority_yield.png'), shot6);

  await browser.close();
  console.log('Re-captured 4, 5, 6 successfully!');
})();
