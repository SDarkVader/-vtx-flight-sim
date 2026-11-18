import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

function element(value = '') {
  const handlers = {};
  return {value, disabled: false, textContent: '', firstChild: {textContent: ''}, handlers,
    children: [], append(...nodes) {this.children.push(...nodes);}, replaceChildren(...nodes) {this.children=nodes;},
    addEventListener(name, fn) { handlers[name] = fn; }, focus() {}, scrollIntoView() {}};
}
const airframe = element('r6');
airframe.options = [{value:'r6', textContent:'R6 · Argon'}, {value:'phantom-a10d', textContent:'Phantom A10-D · test aircraft'},
  {value:'phantom-a10b', textContent:'Phantom A10-B · pinned reference'}].map(item=>({...item,cloneNode(){return {...item};}}));
Object.defineProperty(airframe, 'selectedOptions', {get() { return airframe.options.filter(item => item.value === airframe.value); }});
const items = {airframe, 'phantom-start': element('road'), validation: element(), start: element(),
  models: element(), 'historical-vehicles':element(), 'main-aircraft': element(), dep: element('0,0'), 'aircraft-evidence': element(),
  'r6-pilot-record': element()};
items['main-aircraft'].options = ['phantom-a10c','r6','boat:ricochet-airport','boat:ricochet-marina'].map(value=>({value,cloneNode(){return {value};}}));
const listeners = {};
const dialogItems = Object.fromEntries(['data-vehicle-close', 'data-vehicle-choice', 'data-vehicle-status', 'data-vehicle-select'].map(key => [key, element()]));
const dialog = {querySelector(selector) {return dialogItems[selector.slice(1,-1)];},
  showModal() {}, close() {}};
globalThis.document = {documentElement: {dataset:{}}, getElementById: id => items[id],
  body: {append() {}},
  createElement(tag) {return tag === 'dialog' ? dialog : element();},
  addEventListener(name, fn) { listeners[name] = fn; },
  dispatchEvent(event) {listeners[event.type]?.(event); return true;}};
globalThis.Option = function(text, value){return {textContent:text,value};};
let appliedView;
document.addEventListener('vtx-aircraft-departure-request', event => {
  event.detail.original = [...event.detail.departure];
  event.detail.departure = [-3885, 0];
});
document.addEventListener('vtx-aircraft-selected', event => {appliedView = event.detail;});
let actual = 'r6', active = false;
let releasePreview;
const calls = [];
globalThis.fetch = async (url, options) => {
  calls.push({url, options});
  if (url === '/api/view') return {ok:true, json:async()=>({active, observation:{configuration:{airframe_variant:actual}}})};
  if (url === '/api/model-preview') {
    await new Promise(resolve => {releasePreview=resolve;});
    actual = JSON.parse(options.body).airframe_variant;
    return {ok:true, json:async()=>({observation:{configuration:{airframe_variant:actual}}})};
  }
  throw Error('Unexpected endpoint ' + url);
};
const selectionUrl = new URL('../public/aircraft-selection.js', import.meta.url).href;
const sceneryUrl = new URL('../public/scenery-view.js', import.meta.url).href;
const source=(await readFile(new URL('../public/model-selector.js',import.meta.url),'utf8'))
  .replace("from './aircraft-selection.js?v=1'", `from '${selectionUrl}'`)
  .replace(/from '\.\/scenery-view\.js\?v=[^']*'/, `from '${sceneryUrl}'`);
await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(airframe.value, 'r6');
assert.equal(items['main-aircraft'].value,'r6');
assert.equal(calls.filter(call => call.url === '/api/model-preview').length, 0, 'startup must not switch aircraft');
airframe.value = 'phantom-a10b';
airframe.handlers.change();
assert.equal(document.documentElement.dataset.vtxPreviewPending,'1');
assert.equal(airframe.disabled,true);
assert.equal(items.start.disabled,true);
assert.equal(JSON.parse(calls.at(-1).options.body).airframe_variant,'phantom-a10b');
assert.deepEqual(JSON.parse(calls.at(-1).options.body).departure,[-3885,0]);
releasePreview();
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(document.documentElement.dataset.vtxPreviewPending,'0');
assert.equal(airframe.value,'phantom-a10b');
assert.equal(airframe.disabled,false);
assert.match(items.validation.textContent,/no flight started/);
assert.equal(appliedView.observation.configuration.airframe_variant,'phantom-a10b');
items.models.handlers.click();
const groups=dialogItems['data-vehicle-choice'].children;
assert.equal(groups[1].label,'Main vehicles');
assert.deepEqual(groups[1].children.map(option=>option.value),['phantom-a10c','r6','boat:ricochet-airport','boat:ricochet-marina']);
assert.equal(groups[3].label,'Ride as passenger');
assert.equal(groups[3].children.length,10);
assert.equal(groups[2].label,'Historical and experimental aircraft');
assert.deepEqual(groups[2].children.map(option=>option.value),['phantom-a10d','phantom-a10b']);
for(const option of groups[3].children){
 let boarded;
 document.addEventListener('vtx-ride-scenery',event=>{event.preventDefault();boarded=event.detail.vehicleId;event.detail.resolve();});
 dialogItems['data-vehicle-choice'].value=option.value;
 await dialogItems['data-vehicle-select'].handlers.click();
 assert.equal(boarded,option.value.slice('scenery:'.length));
}
assert.equal(calls.filter(call => call.url === '/api/model-preview').length,1,'boarding must not switch the physical aircraft');
console.log('Model selector keeps the server aircraft at startup and applies explicit preview safely');

// The prominent main menu must load the actual R6, without silently starting it.
items['main-aircraft'].value='r6'; items['main-aircraft'].handlers.change();
assert.equal(JSON.parse(calls.at(-1).options.body).airframe_variant,'r6');
releasePreview(); await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(actual,'r6'); assert.equal(items['main-aircraft'].value,'r6');
// An active flight permits an explicit switch bound to the run the operator saw.
active=true; listeners['vtx-aircraft-state']({detail:{active:true,run_id:'old',observation:{configuration:{airframe_variant:'r6'}}}});
assert.equal(items['main-aircraft'].disabled,false);
airframe.value='phantom-a10b'; airframe.handlers.change();
assert.equal(JSON.parse(calls.at(-1).options.body).save_run_id,'old');
releasePreview(); await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(airframe.value,'phantom-a10b');
