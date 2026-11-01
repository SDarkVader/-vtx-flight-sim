import puppeteer from 'file:///C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9/scratch/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js';
import fs from 'fs';
import path from 'path';

const outDir = 'C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9';

(async () => {
  console.log('Launching browser to capture enhanced Basement screenshots...');
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

  // 1. Subterranean Station Overview: Glass vault, Flooded rails with cyan orbs, Cherry Blossom, Figure with Nordeus umbrella
  console.log('Capturing checkpoint6_03_subterranean_station_overview.png...');
  await setCam([-12, 204, 5.0], [-24, 222, 3.5]);
  const shot3 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_03_subterranean_station_overview.png'), shot3);

  // 2. Steampunk Sign, Rotating Gears, Lava Falls, Churning Steam Puffs & Floating Robot Masks
  console.log('Capturing checkpoint6_04_steampunk_sign_and_lava_falls.png...');
  await setCam([-30, 200, 12], [-30, 244, 25]);
  const shot4 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_04_steampunk_sign_and_lava_falls.png'), shot4);

  // 3. Swimming Sky-Whale Nordeus in the Glass Cathedral Vault
  console.log('Capturing checkpoint6_05_swimming_sky_whale_nordeus.png...');
  await setCam([-22, 215, 18], [-8, 225, 26]);
  const shot5 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_05_swimming_sky_whale_nordeus.png'), shot5);

  // 4. Arthur Finch Kiosk / Heroism Citation & Police Scotland Mug
  console.log('Capturing checkpoint6_07_arthur_finch_citation_and_mug.png...');
  await setCam([-24, 228, 3.2], [-26.5, 232, 2.5]);
  const shot7 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_07_arthur_finch_citation_and_mug.png'), shot7);

  console.log('Screenshots captured successfully!');
  await browser.close();
})().catch(err => {
  console.error('ERROR:', err);
  process.exit(1);
});
