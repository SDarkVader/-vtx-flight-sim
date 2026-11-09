const { chromium } = require('playwright'); const fs = require('fs');
const S = process.argv[2];
const VIEWS = {
  deploy: [{offset:[-8.5,7.5,4.2],followYaw:true,fov:38}, {offset:[-8.5,7.5,4.2],followYaw:true,fov:38}, {offset:[-9,-7.5,4.5],followYaw:true,fov:38}],
  steer: [{offset:[6.0,-4.2,1.5],followYaw:true,fov:40,lookZ:0.45}, {offset:[5.5,4.5,2.2],followYaw:true,fov:40,lookZ:0.45}],
  vtol: [{offset:[8,-7,2.5],followYaw:true,fov:38,lookZ:0.6}, {offset:[9,-9,1.0],followYaw:true,fov:38,lookZ:0.4}],
  roll: [{offset:[-2,-12,2.6],followYaw:true,fov:36}],
  decel: [{offset:[-13,7,4.5],followYaw:true,fov:36}, {offset:[-13,7,4.5],followYaw:true,fov:36}, {offset:[-12,-9,5],followYaw:true,fov:38}, {offset:[-12,-9,5],followYaw:true,fov:38}, {offset:[8,-9,4],followYaw:true,fov:38}],
};
(async () => {
  const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  page.on('console', m => { if (m.type() === 'error') console.log('console:', m.text()); });
  await page.goto('http://127.0.0.1:8791/render.html'); await page.waitForFunction(() => window.ready === true);
  const nodes = await page.evaluate(() => window.loadModel('/assets/phantom-a10-visual.glb')); console.log('body nodes', nodes);
  let k = process.argv[4] ? Number(process.argv[4]) : 0;
  for (const sc of (process.argv[3] ? process.argv[3].split(',') : ['deploy', 'steer', 'vtol', 'roll', 'decel'])) {
    const frames = JSON.parse(fs.readFileSync(`${S}/shots/${sc}.json`, 'utf8'));
    for (let i = 0; i < frames.length; i++) {
      await page.evaluate(([f, v]) => { window.CONFIG = 'phantom-a10b'; return window.renderFrame(f, v); }, [frames[i], VIEWS[sc][i] || VIEWS[sc][0]]);
      await page.waitForTimeout(150);
      const out = `${S}/shots/${String(++k).padStart(2, '0')}_${sc}_${i + 1}.png`; await page.screenshot({ path: out }); console.log('wrote', out);
    }
  }
  await browser.close();
})();
