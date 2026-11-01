import puppeteer from 'file:///C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9/scratch/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js';

const out = 'C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9';

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

await page.addStyleTag({
  content: '#retry-bar,#toast,#scene-caption,#keyboard-open,#view-tools{display:none!important}'
});
await new Promise(r => setTimeout(r, 2000));

let el = await page.$('#viewport');

// VTX-TOWER: 45m Tower at [240, 555]
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(240, 430, 62);
  v.orbit.target.set(240, 555, 46);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_04_vtx_control_tower.png` });

// VTX-FIRE: Fire Station at [475, 600]
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(475, 540, 38);
  v.orbit.target.set(475, 600, 30);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_05_vtx_fire_station.png` });

// VTX-CARGO: Cargo Hub at [680, 600]
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(680, 535, 36);
  v.orbit.target.set(680, 600, 28);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_06_vtx_cargo_depot.png` });

await browser.close();
console.log('Saved tower, fire, cargo screenshots');
