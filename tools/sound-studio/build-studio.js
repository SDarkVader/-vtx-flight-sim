// Rebuilds "VTX Sound Studio.html" from the three tool pages. Run: node build-studio.js
const fs = require('fs'), path = require('path');
const here = __dirname, phantom = path.join(here, 'Vehicle', 'Phantom A10-D');
const pages = {
  radio: ['Radio', path.join(here, 'Radio.html')],
  designer: ['Vehicle designer', path.join(phantom, 'Vehicle Designer.html')],
  audition: ['Audition', path.join(phantom, 'Sound Audition.html')],
};
const embedded = Object.fromEntries(Object.entries(pages).map(([key, [, file]]) => [key, fs.readFileSync(file, 'utf8')]));
const data = JSON.stringify(embedded).replace(/<\/(script)/gi, '<\\/$1').replace(/<!--/g, '<\\!--');
const tabs = Object.entries(pages).map(([key, [label]]) => `<button data-tab="${key}">${label}</button>`).join('\n    ');

const shell = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VTX Sound Studio</title>
<style>
  html,body{height:100%;margin:0}
  body{display:flex;flex-direction:column;font:14px/1.4 system-ui,sans-serif;background:#0d2129;color:#e5f5f2}
  header{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px;border-bottom:1px solid #5d8f99}
  button,label.pick{font:inherit;background:#142d36;color:inherit;border:1px solid #5d8f99;border-radius:5px;padding:6px 11px;cursor:pointer}
  button[aria-selected=true]{background:#1d5563;border-color:#8cdce6;color:#ffca72}
  label.pick input{display:none}
  #note{flex:1 1 100%;opacity:.8}
  main{flex:1;position:relative;background:#121212}
  iframe{position:absolute;inset:0;width:100%;height:100%;border:0;visibility:hidden;color-scheme:dark}
  iframe.on{visibility:visible}
</style>
</head>
<body>
<header>
    ${tabs}
  <span style="flex:1"></span>
  <button id="link" hidden>Remember my sounds folder</button>
  <button id="load" hidden>Load my sounds</button>
  <label class="pick">Open a folder once<input id="once" type="file" webkitdirectory></label>
  <div id="note" role="status">Choose your sounds folder once and it is remembered.</div>
</header>
<main></main>
<script>
'use strict';
const PAGES = ${data};
const $ = id => document.getElementById(id);
const frames = {}, ready = [];
for (const [key, source] of Object.entries(PAGES)) {
  const frame = document.createElement('iframe');
  frame.title = key;
  frame.allow = 'autoplay';
  ready.push(new Promise(done => frame.onload = done));
  frame.srcdoc = source;
  document.querySelector('main').append(frame);
  frames[key] = frame;
}
function show(key) {
  for (const [name, frame] of Object.entries(frames)) frame.classList.toggle('on', name === key);
  for (const tab of document.querySelectorAll('[data-tab]')) tab.setAttribute('aria-selected', tab.dataset.tab === key);
  try { localStorage.setItem('vtx-studio-tab', key); } catch {}
}
for (const tab of document.querySelectorAll('[data-tab]')) tab.onclick = () => show(tab.dataset.tab);

// One folder feeds all three: songs to the radio, vehicle clips to the designer and audition.
async function share(files) {
  await Promise.all(ready);
  const where = f => f.webkitRelativePath || f.name;
  const audio = files.filter(f => /\\.(mp3|mpeg|m4a|aac|ogg|wav|flac)$/i.test(f.name) && !/(^|\\/)exact copies\\//i.test(where(f)));
  const songs = audio.filter(f => /(^|\\/)radio\\//i.test(where(f))), clips = audio.filter(f => !songs.includes(f));
  frames.radio.contentWindow.add(songs);
  if (clips.length) {
    frames.designer.contentWindow.load(clips);
    await frames.audition.contentWindow.load(clips);
  }
  $('note').textContent = songs.length + ' songs and ' + clips.length + ' vehicle clips loaded.';
}
async function walk(directory, at, found) {
  for await (const entry of directory.values()) {
    if (entry.kind === 'directory') await walk(entry, at + entry.name + '/', found);
    else {
      const file = await entry.getFile();
      Object.defineProperty(file, 'webkitRelativePath', { value: at + entry.name });
      found.push(file);
    }
  }
  return found;
}
function store(mode, work) {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open('vtx-studio', 1);
    open.onupgradeneeded = () => open.result.createObjectStore('folder');
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const db = open.result, tx = db.transaction('folder', mode), request = work(tx.objectStore('folder'));
      tx.oncomplete = () => { db.close(); resolve(request.result); };
      tx.onerror = tx.onabort = () => { db.close(); reject(tx.error); };
    };
  });
}
async function open(handle, ask) {
  let permission = await handle.queryPermission({ mode: 'read' });
  if (permission !== 'granted' && ask) permission = await handle.requestPermission({ mode: 'read' });
  if (permission !== 'granted') {
    $('load').hidden = false;
    $('note').textContent = 'Press "Load my sounds" to open ' + handle.name + '.';
    return;
  }
  $('load').hidden = true;
  $('note').textContent = 'Loading ' + handle.name + '…';
  try { await share(await walk(handle, handle.name + '/', [])); }
  catch { $('note').textContent = 'Could not read ' + handle.name + '. Choose it again.'; }
}
if (window.showDirectoryPicker) {
  $('link').hidden = false;
  $('link').onclick = async () => {
    let handle;
    try { handle = await showDirectoryPicker({ id: 'vtx-sounds', startIn: 'music' }); } catch { return; }
    await store('readwrite', s => s.put(handle, 'sounds'));
    await open(handle, true);
  };
  const saved = () => store('readonly', s => s.get('sounds'));
  $('load').onclick = async () => open(await saved(), true);
  saved().then(handle => handle && open(handle, false)).catch(() => {});
}
$('once').onchange = e => { share([...e.target.files]); e.target.value = ''; };
let first = 'radio';
try { first = localStorage.getItem('vtx-studio-tab') || first; } catch {}
show(frames[first] ? first : 'radio');
</script>
</body>
</html>
`;
fs.writeFileSync(path.join(here, 'VTX Sound Studio.html'), shell);
console.log('built', Math.round(shell.length / 1024), 'KB');
