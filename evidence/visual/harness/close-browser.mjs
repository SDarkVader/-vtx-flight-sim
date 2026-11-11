// Closes a headless browser left on a CDP port by an interrupted capture: node close-browser.mjs <port>
const port = process.argv[2] || 9341;
try {
  const v = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
  const ws = new WebSocket(v.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r, { once: true }));
  ws.send(JSON.stringify({ id: 1, method: 'Browser.close' }));
  await new Promise((r) => setTimeout(r, 800));
  console.log('closed', port);
} catch (e) { console.log('nothing on', port); }
process.exit(0);
