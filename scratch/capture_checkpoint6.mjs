import puppeteer from 'file:///C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9/scratch/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js';
import fs from 'fs';
import path from 'path';

const outDir = 'C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9';

(async () => {
  console.log('Launching browser to capture Checkpoint 6 Volcano Basement screenshots...');
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

  // 1. Exterior Volcanic Mountain Approach
  console.log('Capturing checkpoint6_01_volcano_mountain_exterior.png...');
  await setCam([-30, 40, 40], [-30, 220, 25]);
  const shot1 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_01_volcano_mountain_exterior.png'), shot1);

  // 2. Tunnel Entrance Portal Mouth
  console.log('Capturing checkpoint6_02_volcano_tunnel_portal_approach.png...');
  await setCam([-30, 125, 10], [-30, 158, 9]);
  const shot2 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_02_volcano_tunnel_portal_approach.png'), shot2);

  // 3. Subterranean Station Overview: Platform 3, Cherry Blossom, Figure in yellow coat
  console.log('Capturing checkpoint6_03_subterranean_station_overview.png...');
  await setCam([-10, 206, 3.8], [-24, 222, 2.8]);
  const shot3 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_03_subterranean_station_overview.png'), shot3);

  // 4. Steampunk Sign, Rotating Gears, Lava Falls & Floating Robot Masks
  console.log('Capturing checkpoint6_04_steampunk_sign_and_lava_falls.png...');
  await setCam([-30, 195, 12], [-30, 244, 26]);
  const shot4 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_04_steampunk_sign_and_lava_falls.png'), shot4);

  // 5. Swimming Sky-Whale "Nordeus" gliding overhead
  console.log('Capturing checkpoint6_05_swimming_sky_whale_nordeus.png...');
  await setCam([-48, 208, 5], [-30, 226, 26]);
  const shot5 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_05_swimming_sky_whale_nordeus.png'), shot5);

  // 6. Subterranean Landing Pad Touchdown
  console.log('Capturing checkpoint6_06_subterranean_landing_pad_touchdown.png...');
  await setCam([-2, 208, 4.2], [-14, 222, 0.8]);
  const shot6 = await (await page.$('#viewport canvas')).screenshot();
  fs.writeFileSync(path.join(outDir, 'checkpoint6_06_subterranean_landing_pad_touchdown.png'), shot6);

  await browser.close();
  console.log('Checkpoint 6 capture complete!');
})();
