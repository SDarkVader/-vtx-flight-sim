const { chromium } = require('playwright');
const URL = process.env.STUDIO_URL || 'http://127.0.0.1:8123/studio.html';
const ok = (name, cond, extra = '') => console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : ''));
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await (await browser.newContext()).newPage();
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto(URL);
  const res = await page.evaluate(async () => {
    // renders a stereo sine through strip `id` of a fresh offline desk; returns RMS and peak in dB of the last second (left channel)
    async function run(strip, cfg, db, { master = {}, mono = false, f = 1000, bounce = true } = {}) {
      const keep = JSON.stringify(mixState);
      Object.assign(mixState.strips[strip], cfg); Object.assign(mixState.master, master); if (arguments[3]?.solo) mixState.strips[arguments[3].solo].solo = true;
      const sr = 48000, off = new OAC(2, sr * 3, sr), M = buildMixer(off, false); applyMixer(M, true, bounce);
      mixState.strips = JSON.parse(keep).strips; Object.assign(mixState.master, JSON.parse(keep).master);
      const o = off.createOscillator(); o.frequency.value = f; const g = off.createGain(); g.gain.value = dbToLin(db); o.connect(g);
      if (mono) g.connect(M.strips[strip].in); else { const m = off.createChannelMerger(2); g.connect(m, 0, 0); g.connect(m, 0, 1); m.connect(M.strips[strip].in); }
      o.start();
      const out = (await off.startRendering()).getChannelData(0).subarray(sr * 2);
      let sq = 0, pk = 0; for (const v of out) { sq += v * v; if (Math.abs(v) > pk) pk = Math.abs(v); }
      return { rms: 20 * Math.log10(Math.sqrt(sq / out.length)), peak: 20 * Math.log10(pk) };
    }
    const r = {};
    r.flat = await run('sfx', {}, -20);
    r.monoPan = await run('sfx', {}, -20, { mono: true });
    r.below = await run('sfx', { thr: -20, ratio: 4 }, -40);
    r.above = await run('sfx', { thr: -20, ratio: 4 }, -10);
    r.aboveMakeup = await run('sfx', { thr: -20, ratio: 4, makeup: 6 }, -10);
    r.limBelow = await run('sfx', {}, -30, { master: { ceil: -6, limiter: true } });
    r.limAbove = await run('sfx', {}, 0, { master: { ceil: -6, limiter: true } });
    r.limAbove2 = await run('sfx', {}, 6, { master: { ceil: -3, limiter: true } });
    r.noLimit = await run('sfx', {}, -20, { master: { limiter: false } });
    r.fader = await run('sfx', { fader: -6 }, -20);
    r.mute = await run('sfx', { mute: true }, -20, { bounce: false });
    r.soloOther = await run('sfx', {}, -20, { bounce: false, solo: 'veh' });
    r.panL = await run('sfx', { pan: -1 }, -20);
    r.panR = await run('sfx', { pan: 1 }, -20);
    r.hp = await run('sfx', { hp: 7 }, -20, { f: 100 });     // 200 Hz high-pass on a 100 Hz tone
    r.lowShelf = await run('sfx', { low: 12 }, -30, { f: 40 });
    return r;
  });
  const d = (a, b) => (a - b).toFixed(2);
  console.log(JSON.stringify(res, (k, v) => typeof v === 'number' ? Math.round(v * 100) / 100 : v));
  ok('flat stereo strip is unity (RMS -23.01 for a -20 dB peak sine)', Math.abs(res.flat.rms - -23.01) < 0.1, d(res.flat.rms, -23.01));
  ok('mono source is also unity at centre', Math.abs(res.monoPan.rms - res.flat.rms) < 0.15, d(res.monoPan.rms, res.flat.rms));
  ok('compressor below threshold is unity (makeup cancelled)', Math.abs(res.below.rms - (-43.01)) < 0.3, d(res.below.rms, -43.01));
  const exp = -20 + (-10 + 20) / 4;
  ok('compressor above threshold: peak near thr + (in-thr)/ratio = ' + exp, Math.abs(res.above.peak - exp) < 1.2, 'peak ' + res.above.peak.toFixed(2));
  ok('makeup +6 dB adds 6 dB', Math.abs(res.aboveMakeup.rms - res.above.rms - 6) < 0.2, d(res.aboveMakeup.rms - res.above.rms, 6));
  ok('limiter below ceiling is unity', Math.abs(res.limBelow.rms - (-33.01)) < 0.3, d(res.limBelow.rms, -33.01));
  ok('limiter holds 0 dBFS to near the -6 dB ceiling', res.limAbove.peak < -4.5 && res.limAbove.peak > -7.5, 'peak ' + res.limAbove.peak.toFixed(2));
  ok('limiter holds +6 dBFS to near the -3 dB ceiling', res.limAbove2.peak < -1.5 && res.limAbove2.peak > -4.5, 'peak ' + res.limAbove2.peak.toFixed(2));
  ok('limiter off passes the signal', Math.abs(res.noLimit.rms - (-23.01)) < 0.1);
  ok('fader -6 dB', Math.abs(res.fader.rms - res.flat.rms + 6) < 0.15, d(res.fader.rms - res.flat.rms, -6));
  ok('mute silences', res.mute.peak < -100);
  ok('soloing another strip silences this one', res.soloOther.peak < -100);
  ok('bounce mode ignores mute and solo (a print always includes the strip)', res.flat.peak > -30);
  ok('constant-power pan: hard left is +3 dB on the left, silent on the right', Math.abs(res.panL.rms - res.flat.rms - 3.01) < 0.2 && res.panR.peak < -100, d(res.panL.rms, res.flat.rms));
  ok('200 Hz low cut removes a 100 Hz tone', res.hp.rms < res.flat.rms - 8, 'rms ' + res.hp.rms.toFixed(1));
  ok('low shelf +12 dB lifts 40 Hz', res.lowShelf.rms > -33.01 + 8, 'rms ' + res.lowShelf.rms.toFixed(1));
  console.log('errors', errors);
  await browser.close();
})();
