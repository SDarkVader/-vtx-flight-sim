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

// Elevated low-angle view of West Entry Holding Point and illuminated signs at [-625, 28]
// Looking from south-east at z = 48m looking at z = 38m
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-615, 6, 49);
  v.orbit.target.set(-625, 28, 41);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/test_elevated_hold.png` });

// Also let's test holding point on TWY-C at [-245, 108] where ground elevation is ~0.9m
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-245, 80, 5.5);
  v.orbit.target.set(-245, 110, 1.2);
  v.orbit.update();
});
await new Promise(r => setTimeout(r, 1500));
await el.screenshot({ path: `${out}/test_twyc_hold.png` });

await browser.close();
console.log('Saved test screenshots');
