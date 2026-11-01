import puppeteer from 'file:///C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9/scratch/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js';

const out = 'C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9';
console.log('Launching browser to capture Checkpoint 3 screenshots...');

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

// 1. VTX-SCHOOL: Flight Academy & Simulation Centre
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-555, 560, 38);
  v.orbit.target.set(-555, 635, 29);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_01_vtx_flight_academy.png` });
console.log('Saved checkpoint3_01_vtx_flight_academy.png');

// 2. VTX-HQ: Passenger Terminal & Dispatch Concourse
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-200, 530, 48);
  v.orbit.target.set(-200, 620, 38);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_02_vtx_hq_passenger_terminal.png` });
console.log('Saved checkpoint3_02_vtx_hq_passenger_terminal.png');

// 3. VTX-ENGINEERING: Heavy MRO & Prototype Skunkworks
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(40, 520, 48);
  v.orbit.target.set(40, 590, 42);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_03_vtx_engineering_mro.png` });
console.log('Saved checkpoint3_03_vtx_engineering_mro.png');

// 4. VTX-TOWER & VTX-FIRE: ATC Tower (45m) & Airport Fire Station
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(350, 440, 70);
  v.orbit.target.set(350, 580, 45);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_04_vtx_control_tower_and_fire.png` });
console.log('Saved checkpoint3_04_vtx_control_tower_and_fire.png');

// 5. VTX-CARGO: Air Freight Depot & Sea Containers
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(680, 510, 42);
  v.orbit.target.set(680, 600, 30);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_05_vtx_cargo_depot.png` });
console.log('Saved checkpoint3_05_vtx_cargo_depot.png');

// 6. Northern Ridgeline Facilities Skyline Panorama (viewed from Runway 08/26 looking north)
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(50, -50, 45);
  v.orbit.target.set(50, 550, 40);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/checkpoint3_06_facilities_ridgeline_panorama.png` });
console.log('Saved checkpoint3_06_facilities_ridgeline_panorama.png');

await browser.close();
console.log('Checkpoint 3 screenshots captured successfully!');
