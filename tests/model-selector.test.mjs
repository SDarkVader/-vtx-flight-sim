import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

function element(value = '') {
  const handlers = {};
  return {value, disabled: false, textContent: '', firstChild: {textContent: ''}, handlers,
    addEventListener(name, fn) { handlers[name] = fn; }, focus() {}, scrollIntoView() {}};
}
const airframe = element('r6');
airframe.options = [{value:'r6', textContent:'R6 · Argon'}, {value:'phantom-a10b', textContent:'Phantom A10-B · current'}];
Object.defineProperty(airframe, 'selectedOptions', {get() { return airframe.options.filter(item => item.value === airframe.value); }});
const items = {airframe, 'phantom-start': element('road'), validation: element(), start: element(),
  models: element(), dep: element('0,0')};
const listeners = {};
globalThis.document = {documentElement: {dataset:{}}, getElementById: id => items[id],
  addEventListener(name, fn) { listeners[name] = fn; }};
let actual = 'r6';
let releasePreview;
const calls = [];
globalThis.fetch = async (url, options) => {
  calls.push({url, options});
  if (url === '/api/view') return {ok:true, json:async()=>({active:false, observation:{configuration:{airframe_variant:actual}}})};
  if (url === '/api/model-preview') {
    await new Promise(resolve => {releasePreview=resolve;});
    actual = JSON.parse(options.body).airframe_variant;
    return {ok:true, json:async()=>({observation:{configuration:{airframe_variant:actual}}})};
  }
  throw Error('Unexpected endpoint ' + url);
};
const source=await readFile(new URL('../public/model-selector.js',import.meta.url),'utf8');
await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(airframe.value, 'r6');
assert.equal(calls.filter(call => call.url === '/api/model-preview').length, 0, 'startup must not switch aircraft');
airframe.value = 'phantom-a10b';
airframe.handlers.change();
assert.equal(document.documentElement.dataset.vtxPreviewPending,'1');
assert.equal(airframe.disabled,true);
assert.equal(items.start.disabled,true);
assert.equal(JSON.parse(calls.at(-1).options.body).airframe_variant,'phantom-a10b');
releasePreview();
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(document.documentElement.dataset.vtxPreviewPending,'0');
assert.equal(airframe.value,'phantom-a10b');
assert.equal(airframe.disabled,false);
assert.match(items.validation.textContent,/no flight started/);
console.log('Model selector keeps the server aircraft at startup and applies explicit preview safely');
