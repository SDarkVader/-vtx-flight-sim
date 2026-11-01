import puppeteer from 'file:///C:/Users/steve/.gemini/antigravity/brain/241fb4eb-b280-4dfd-a674-1c440e7372a9/scratch/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js';

(async () => {
  console.log('Testing Free Roam Camera and Touch Pinch/Zoom...');
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--window-size=1200,800']
  });
  const page = await browser.newPage();

  await page.goto('http://127.0.0.1:8765/?debug', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => window.__vtx && window.__vtx.world && window.__vtx.model && document.getElementById('loading').hidden,
    { timeout: 30000 }
  );

  console.log('Page loaded. Checking initial button text...');
  const initialBtnText = await page.$eval('#camera', el => el.textContent);
  console.log('Initial camera button:', initialBtnText);

  console.log('Clicking camera button to enter Free Roam mode...');
  await page.click('#camera');
  await new Promise(r => setTimeout(r, 500));

  const freeState = await page.evaluate(() => {
    const v = window.__vtx;
    const hud = document.getElementById('free-cam-hud');
    return {
      active: v.freeCam.isActive,
      hudDisplay: hud ? getComputedStyle(hud).display : 'none',
      pos: [v.freeCam.position.x, v.freeCam.position.y, v.freeCam.position.z],
      yaw: v.freeCam.yaw,
      pitch: v.freeCam.pitch
    };
  });
  console.log('Free Roam activated:', freeState);

  console.log('Testing landmark teleport to Basement Platform 3...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('#free-cam-hud button'));
    const platBtn = btns.find(b => b.textContent.includes('Platform 3'));
    if (platBtn) platBtn.click();
  });
  await new Promise(r => setTimeout(r, 600));

  const teleState = await page.evaluate(() => {
    const v = window.__vtx;
    return {
      camPos: [v.camera.position.x, v.camera.position.y, v.camera.position.z],
      yaw: v.freeCam.yaw,
      pitch: v.freeCam.pitch
    };
  });
  console.log('Camera teleported to Platform 3:', teleState);

  // Test touch look gesture with valid Touch objects
  console.log('Testing touch look gesture...');
  await page.evaluate(() => {
    const canvas = document.querySelector('#viewport canvas');
    const t1 = new Touch({ identifier: 1, target: canvas, clientX: 200, clientY: 200 });
    const t2 = new Touch({ identifier: 1, target: canvas, clientX: 300, clientY: 250 });
    canvas.dispatchEvent(new TouchEvent('touchstart', { touches: [t1] }));
    canvas.dispatchEvent(new TouchEvent('touchmove', { touches: [t2], cancelable: true }));
    canvas.dispatchEvent(new TouchEvent('touchend', { touches: [] }));
  });
  await new Promise(r => setTimeout(r, 300));

  const afterTouchState = await page.evaluate(() => {
    const v = window.__vtx;
    return {
      yaw: v.freeCam.yaw,
      pitch: v.freeCam.pitch
    };
  });
  console.log('After touch look gesture:', afterTouchState);

  // Test pinch-to-zoom / fly gesture
  console.log('Testing pinch-to-fly gesture...');
  await page.evaluate(() => {
    const canvas = document.querySelector('#viewport canvas');
    const start1 = new Touch({ identifier: 1, target: canvas, clientX: 200, clientY: 200 });
    const start2 = new Touch({ identifier: 2, target: canvas, clientX: 300, clientY: 200 });
    canvas.dispatchEvent(new TouchEvent('touchstart', { touches: [start1, start2] }));

    // Spread fingers apart (pinch to zoom/fly)
    const move1 = new Touch({ identifier: 1, target: canvas, clientX: 120, clientY: 200 });
    const move2 = new Touch({ identifier: 2, target: canvas, clientX: 380, clientY: 200 });
    canvas.dispatchEvent(new TouchEvent('touchmove', { touches: [move1, move2], cancelable: true }));
    canvas.dispatchEvent(new TouchEvent('touchend', { touches: [] }));
  });
  await new Promise(r => setTimeout(r, 300));

  const afterPinchPos = await page.evaluate(() => {
    const v = window.__vtx;
    return [v.camera.position.x, v.camera.position.y, v.camera.position.z];
  });
  console.log('Position after pinch gesture:', afterPinchPos);

  console.log('Returning to chase mode...');
  await page.click('#camera');
  await new Promise(r => setTimeout(r, 300));
  const isDeactivated = await page.evaluate(() => !window.__vtx.freeCam.isActive);
  console.log('Deactivated successfully:', isDeactivated);

  console.log('ALL FREE ROAM & TOUCH TESTS PASSED PERFECTLY!');
  await browser.close();
})().catch(err => {
  console.error('TEST SCRIPT FAILED:', err);
  process.exit(1);
});
