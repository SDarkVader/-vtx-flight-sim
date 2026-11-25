// =====================================================================================
// EXPORT: WAV bounce (16 or 24 bit), zip, saving, the project file
// =====================================================================================
function encodeWav(buf, bits = 24) {
  const ch = buf.numberOfChannels, n = buf.length, sr = buf.sampleRate, bytes = bits / 8, dataLen = n * ch * bytes;
  const out = new ArrayBuffer(44 + dataLen), v = new DataView(out);
  const tag = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  tag(0, 'RIFF'); v.setUint32(4, 36 + dataLen, true); tag(8, 'WAVE'); tag(12, 'fmt '); v.setUint32(16, 16, true);
  v.setUint16(20, bits === 32 ? 3 : 1, true); v.setUint16(22, ch, true); v.setUint32(24, sr, true);
  v.setUint32(28, sr * ch * bytes, true); v.setUint16(32, ch * bytes, true); v.setUint16(34, bits, true);
  tag(36, 'data'); v.setUint32(40, dataLen, true);
  const data = []; for (let c = 0; c < ch; c++) data.push(buf.getChannelData(c));
  let o = 44;
  for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) {
    const x = clamp(data[c][i], -1, 1);
    if (bits === 16) { v.setInt16(o, clamp(Math.round(x * 32767 + Math.random() - Math.random()), -32768, 32767), true); o += 2; }   // triangular dither
    else if (bits === 24) { const s = Math.round(x * 8388607); v.setUint8(o, s & 255); v.setUint8(o + 1, (s >> 8) & 255); v.setUint8(o + 2, (s >> 16) & 255); o += 3; }
    else { v.setFloat32(o, data[c][i], true); o += 4; }
  }
  return new Blob([out], { type: 'audio/wav' });
}
const crcTable = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(u8) { let c = 0xFFFFFFFF; for (let i = 0; i < u8.length; i++) c = crcTable[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
// A plain zip with the files stored as they are. Shipped pages may save only a few file types; a zip carries WAVs.
async function makeZip(files) {
  const enc = new TextEncoder(), parts = [], central = [], now = new Date();
  const dosTime = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
  const dosDate = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
  let offset = 0;
  for (const f of files) {
    const data = new Uint8Array(await f.blob.arrayBuffer()), name = enc.encode(f.name), crc = crc32(data);
    const l = new DataView(new ArrayBuffer(30));
    l.setUint32(0, 0x04034b50, true); l.setUint16(4, 20, true); l.setUint16(6, 0x0800, true); l.setUint16(10, dosTime, true); l.setUint16(12, dosDate, true);
    l.setUint32(14, crc, true); l.setUint32(18, data.length, true); l.setUint32(22, data.length, true); l.setUint16(26, name.length, true);
    parts.push(l.buffer, name, data);
    const c = new DataView(new ArrayBuffer(46));
    c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true); c.setUint16(12, dosTime, true); c.setUint16(14, dosDate, true);
    c.setUint32(16, crc, true); c.setUint32(20, data.length, true); c.setUint32(24, data.length, true); c.setUint16(28, name.length, true); c.setUint32(42, offset, true);
    central.push(c.buffer, name);
    offset += 30 + name.length + data.length;
  }
  const cdSize = central.reduce((a, p) => a + p.byteLength, 0), end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true); end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);
  return new Blob([...parts, ...central, end.buffer], { type: 'application/zip' });
}
function anchorDownload(name, blob) {
  const u = URL.createObjectURL(blob), a = el('a', { href: u, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(u), 5000);
}
const VIEWER_TYPES = new Set(['json', 'txt', 'md', 'csv', 'zip']);
// Saves one file as it is, or several (or a WAV, which a hosted page may not save directly) as a zip.
async function deliver(files, zipName) {
  const viewer = !!(window.claude && window.claude.use);
  let dl = null;
  if (viewer) { try { dl = await window.claude.use('downloads'); } catch {} }
  const ext = f => f.name.split('.').pop().toLowerCase();
  const direct = files.length === 1 && (!viewer || VIEWER_TYPES.has(ext(files[0])));
  const name = direct ? files[0].name : zipName, blob = direct ? files[0].blob : await makeZip(files);
  if (dl) {
    try { await dl.save({ filename: name, data: blob }); say(`Saved ${name}.`); }
    catch (e) { say(e?.code === 'declined' ? 'Save cancelled.' : `This viewer could not save the file (${e?.code || 'error'}).`); }
    return;
  }
  if (viewer) { say('This viewer cannot save files. Open the studio in a browser tab.'); return; }
  anchorDownload(name, blob); say(`Saved ${name}.`);
}
async function busy(btn, label, work) {
  const was = btn?.textContent;
  if (btn) { btn.disabled = true; btn.textContent = label; }
  try { await work(); } catch (e) { say('That did not work: ' + (e?.message || e)); console.error(e); }
  finally { if (btn) { btn.disabled = false; btn.textContent = was; } }
}
const safe = s => stem(s).replace(/[^\w\-]+/g, '_').replace(/^_+|_+$/g, '') || 'sound';
const wavBits = () => prefs.bits16 ? 16 : 24;

// ---------- bounces ----------
async function bounceOne(name, btn) {
  await busy(btn, 'Bouncing…', async () => {
    audio();
    const f = { name: safe(takeLabel(name)) + '.wav', blob: encodeWav(await bounceBuffer(name, ctx), wavBits()) };
    await deliver([f], safe(takeLabel(name)) + '.zip');
  });
}
async function bounceKept(btn) {
  const names = [...takes.keys()].filter(n => meta(n).keep);
  if (!names.length) { say('Mark takes as Keep in the editor first.'); return; }
  await busy(btn, 'Bouncing…', async () => {
    audio();
    const files = [];
    for (const n of names) files.push({ name: safe(takeLabel(n)) + '.wav', blob: encodeWav(await bounceBuffer(n, ctx), wavBits()) });
    await deliver(files, 'vtx-kept-takes.zip');
  });
}
async function bouncePart(part, btn) {
  await busy(btn, 'Bouncing…', async () => {
    audio();
    await deliver([{ name: 'Phantom_' + safe(part.name) + '.wav', blob: encodeWav(await renderPart(part), wavBits()) }], 'Phantom_' + safe(part.name) + '.zip');
  });
}
async function bounceAllParts(btn) {
  await busy(btn, 'Bouncing…', async () => {
    audio();
    const files = [];
    for (const part of PARTS) files.push({ name: 'Phantom_' + safe(part.name) + '.wav', blob: encodeWav(await renderPart(part), wavBits()) });
    await deliver(files, 'Phantom_A10D_parts.zip');
  });
}
async function renderSceneAudio(sc) {
  audio();
  const sr = 48000, secs = SCENE_LENS[sc.len], off = new OAC(2, sr * secs, sr);
  const M = buildMixer(off, false); applyMixer(M, true, true);
  const out = off.createGain(), lvl = dbToLin(sc.level);
  out.gain.setValueAtTime(0, 0); out.gain.linearRampToValueAtTime(lvl, 0.4); out.gain.setValueAtTime(lvl, secs - 0.4); out.gain.linearRampToValueAtTime(0, secs);
  out.connect(M.strips.amb.in);
  const rng = mulberry32(sc.seed), r = () => rng() * 2 - 1;
  for (const layer of sc.layers) {
    if (!layer.on || !takes.has(layer.take)) continue;
    const g = off.createGain(), pan = makePanner(off);
    pan.set(layer.pan);
    g.gain.value = dbToLin(layer.level); g.connect(pan.input); pan.output.connect(out);
    if (layer.mode === 'loop') {
      const src = await loopSource(layer.take, layer.smooth);
      const node = off.createBufferSource(); node.buffer = src.buffer; node.loop = true; node.loopStart = src.start; node.loopEnd = src.end;
      node.playbackRate.value = layer.pitch; node.connect(g); node.start(0);
    } else {
      const buf = await bufferOf(layer.take), b = body(buf), lo = GAPS[layer.gMin], hi = Math.max(lo, GAPS[layer.gMax]);
      for (let t = lo * rng(); t < secs; t += lo + rng() * (hi - lo)) {
        const node = off.createBufferSource(), eg = off.createGain(), ep = makePanner(off);
        node.buffer = buf; node.playbackRate.value = layer.pitch * (1 + r() * layer.pitchRand / 100);
        eg.gain.value = dbToLin(r() * layer.levelRand) * (b.baked ? 1 : b.boost);
        ep.set(clamp(layer.pan + r() * layer.spread, -1, 1));
        node.connect(eg); eg.connect(ep.input); ep.output.connect(g); node.start(t, b.from, Math.max(0.05, b.to - b.from));
      }
    }
  }
  return off.startRendering();
}
async function bounceScene(sc, btn) {
  if (!sc.layers.some(l => l.on && takes.has(l.take))) { say('Add a layer with a take first.'); return; }
  await busy(btn, 'Rendering…', async () => {
    await deliver([{ name: 'Scene_' + safe(sc.name) + '.wav', blob: encodeWav(await renderSceneAudio(sc), wavBits()) }], 'Scene_' + safe(sc.name) + '.zip');
  });
}

// ---------- copy, project file ----------
async function copyText(text, area) {
  area.value = text; area.hidden = false;
  try { await navigator.clipboard.writeText(text); say('Copied.'); }
  catch { area.focus(); area.select(); say('Select the text shown and copy it.'); }
}
function collect() {
  return { v: 2, prefs, rack, mix: mixState, veh: plainVeh(), macro, takeMeta, edits, scenes, sceneIdx, notebook };
}
const projectJson = () => JSON.stringify({ app: 'VTX Sound Studio', schema: 1, saved: new Date().toISOString(), ...collect() }, null, 1);
const saveProject = btn => busy(btn, 'Saving…', () => deliver([{ name: 'vtx-sound-studio-project.json', blob: new Blob([projectJson()], { type: 'application/json' }) }], 'vtx-sound-studio-project.zip'));
function applyProject(text) {
  const note = $('projectNote');
  let obj;
  try { obj = JSON.parse(text); } catch { note.textContent = 'That is not valid JSON.'; return; }
  if (!obj || obj.app !== 'VTX Sound Studio') { note.textContent = 'That is not a VTX Sound Studio project.'; return; }
  try { const { app, schema, saved: when, ...state } = obj; localStorage.setItem(KEY, JSON.stringify(state)); }
  catch { note.textContent = 'This browser will not let the studio keep settings, so the project cannot be applied here.'; return; }
  note.textContent = 'Applied. Reloading…'; setTimeout(() => location.reload(), 300);
}
function resetStudio() {
  try { localStorage.removeItem(KEY); } catch {}
  location.reload();
}
