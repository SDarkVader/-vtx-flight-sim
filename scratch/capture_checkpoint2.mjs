import puppeteer from 'file:///C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9/scratch/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js';

const out = 'C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9';
console.log('Launching browser to capture Checkpoint 2 screenshots...');

const browser = await puppeteer.launch({
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: 'new',
  args: [
    '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader',
    '--ignore-gpu-blocklist',
    '--no-sandbox',
    '--window-size=1600,900'
  ]
});

const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900 });
await page.setCacheEnabled(false);

page.on('console', m => {
  const t = m.text();
  if (/error|warn|VTX|exception/i.test(t)) {
    console.log('[browser]', t.slice(0, 300));
  }
});
page.on('pageerror', e => console.error('[pageerror]', e.message));

await page.goto('http://127.0.0.1:8768/?debug', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(
  () => window.__vtx && window.__vtx.world && window.__vtx.model && document.getElementById('loading').hidden,
  { timeout: 120000 }
);

await page.addStyleTag({
  content: '#retry-bar,#toast,#scene-caption,#keyboard-open,#view-tools{display:none!important}'
});
await new Promise(r => setTimeout(r, 2000));

let el = await page.$('#viewport');

// 1. High-Angle Overview of the Curved Bézier Taxiway Network & Aprons
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-100, -180, 480);
  v.orbit.target.set(-50, 180, 0);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint2_01_taxiway_network_overview.png` });
console.log('Saved checkpoint2_01_taxiway_network_overview.png');

// 2. West Entry Curved Bézier Fillet (TWY-A-WEST-ENTRY with R_min=28m)
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-610, -50, 65);
  v.orbit.target.set(-640, 50, 0);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint2_02_west_entry_bezier_fillet.png` });
console.log('Saved checkpoint2_02_west_entry_bezier_fillet.png');

// 3. Low-Angle CAT I Runway Holding Point Markings & Illuminated Signs (08-26 / B)
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(27, 4, 2.4);
  v.orbit.target.set(22.5, 16, 0.95);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint2_03_cat1_holding_point_signs.png` });
console.log('Saved checkpoint2_03_cat1_holding_point_signs.png');

// 4. VTX Flight Academy Apron and Stands 1-4
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-420, 140, 120);
  v.orbit.target.set(-420, 305, 0);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint2_04_flight_academy_apron_and_stands.png` });
console.log('Saved checkpoint2_04_flight_academy_apron_and_stands.png');

await browser.close();
console.log('Checkpoint 2 screenshots captured successfully!');
