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

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.message));

  console.log('Navigating to http://127.0.0.1:8768/?debug ...');
  await page.goto('http://127.0.0.1:8768/?debug', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => window.__vtx && window.__vtx.world && window.__vtx.model && document.getElementById('loading').hidden,
    { timeout: 120000 }
  );
  await new Promise(r => setTimeout(r, 2000));

  // Capture Full Valley minimap view (sidebar minimap)
  const mapElement = await page.$('#map');
  if (mapElement) {
    const valleyShot = await mapElement.screenshot();
    fs.writeFileSync(path.join(outDir, 'checkpoint4_01_minimap_full_valley.png'), valleyShot);
    console.log('Saved checkpoint4_01_minimap_full_valley.png');
  }

  // Click #map-mode to toggle to Tactical zoom
  console.log('Clicking #map-mode button...');
  await page.click('#map-mode');
  await new Promise(r => setTimeout(r, 1000));

  // Capture Airfield Tactical minimap view
  if (mapElement) {
    const tacticalShot = await mapElement.screenshot();
    fs.writeFileSync(path.join(outDir, 'checkpoint4_02_minimap_airfield_tactical.png'), tacticalShot);
    console.log('Saved checkpoint4_02_minimap_airfield_tactical.png');
  }

  // Also open Expand Map dialog to check large minimap
  console.log('Clicking #map-zoom to open large map dialog...');
  await page.click('#map-zoom');
  await new Promise(r => setTimeout(r, 1000));
  const largeMapElement = await page.$('#large-map');
  if (largeMapElement) {
    const largeShot = await largeMapElement.screenshot();
    fs.writeFileSync(path.join(outDir, 'checkpoint4_03_minimap_large_dialog.png'), largeShot);
    console.log('Saved checkpoint4_03_minimap_large_dialog.png');
  }

  // Click on the large map to pick a point and check coordinate
  const rect = await page.evaluate(() => {
    const el = document.getElementById('large-map');
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, width: r.width, height: r.height };
  });
  console.log('Large map rect:', rect);
  // Click near runway 08 threshold (left side of center)
  await page.mouse.click(rect.left + rect.width * 0.25, rect.top + rect.height * 0.45);
  await new Promise(r => setTimeout(r, 500));
  const valText = await page.evaluate(() => document.getElementById('large-validation').textContent);
  console.log('Picked point validation:', valText);

  if (errors.length > 0) {
    console.error('Browser errors encountered:', errors);
  } else {
    console.log('ZERO browser errors encountered!');
  }

  await browser.close();
  console.log('Minimap verification finished successfully.');
})();
