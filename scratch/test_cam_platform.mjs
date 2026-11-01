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

  await page.goto('http://127.0.0.1:8765/?debug', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => window.__vtx && window.__vtx.world && window.__vtx.model && document.getElementById('loading').hidden,
    { timeout: 30000 }
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

  // 1. Platform 3, Cherry Blossom, Yellow Coat figure, Flooded Rails & Cyan Orbs
  console.log('Capturing platform view...');
  await setCam([-42, 206, 4.2], [-54, 222, 3.2]);
  const shot1 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_03_subterranean_station_overview.png'), shot1);

  // 2. Arthur Finch Desk with Citation & Police Scotland Mug
  console.log('Capturing citation and mug view...');
  await setCam([-53, 230, 3.2], [-56.5, 232, 2.3]);
  const shot2 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_07_arthur_finch_citation_and_mug.png'), shot2);

  // 3. Swimming Sky-Whale Nordeus through the cracked glass vault
  console.log('Capturing sky whale...');
  await setCam([-50, 208, 6.0], [-26, 228, 25.0]);
  const shot3 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_05_swimming_sky_whale_nordeus.png'), shot3);

  // 4. Steampunk Sign, Rotating Gears, Lava Falls, Churning Steam Puffs & Floating Robot Masks
  console.log('Capturing steampunk sign and lava falls...');
  await setCam([-26, 202, 14], [-30, 252, 26]);
  const shot4 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_04_steampunk_sign_and_lava_falls.png'), shot4);

  console.log('Done!');
  await browser.close();
})().catch(err => {
  console.error(err);
  process.exit(1);
});
