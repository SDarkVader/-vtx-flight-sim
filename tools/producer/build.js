// Joins the page source into one self-contained HTML file.
//   node tools/producer/build.js                 writes "VTX Producer.html" next to this script
//   node tools/producer/build.js --fragment F    also writes F: the page without html/head/body tags, for hosts that add their own
// Edit the files under src/, not the generated page, then rebuild.
const fs = require('fs'), path = require('path');
const here = __dirname, src = path.join(here, 'src');
const read = f => fs.readFileSync(path.join(src, f), 'utf8');
const order = fs.readdirSync(path.join(src, 'js')).filter(f => f.endsWith('.js')).sort().map(f => f.replace(/\.js$/, ''));   // numbered files load in order
let js = order.map(n => read('js/' + n + '.js')).join('\n');
const flight = read('data/flight.js').trim();
if (!/const FLIGHT = \{.*\};$/m.test(flight)) throw new Error('unexpected flight data shape');
js = js.replace('/*FLIGHT_DATA*/const FLIGHT = {};', () => flight);
js = js.replace('/*TUNING_DATA*/{}', () => JSON.stringify(JSON.parse(read('data/vehicle-tuning-2026-11-25.json'))));
js = js.replace(/<\/(script)/gi, '<\\/$1');
const css = read('style.css'), body = read('body.html');
const head = '<meta name="claude:viewport-fit-sides" content="cover">\n<meta name="theme-color" content="#0a1a20">\n<title>VTX Producer</title>';
const full = `<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n${head}\n<style>\n${css}</style>\n</head>\n<body>\n${body}\n<script>\n${js}\n</script>\n</body>\n</html>\n`;
fs.writeFileSync(path.join(here, 'VTX Producer.html'), full);
const at = process.argv.indexOf('--fragment');
if (at > 0) fs.writeFileSync(process.argv[at + 1], `${head}\n<style>\n${css}</style>\n${body}\n<script>\n${js}\n</script>\n`);
console.log('built VTX Producer.html,', Math.round(full.length / 1024), 'KB');
