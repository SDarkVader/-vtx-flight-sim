import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {test} from 'node:test';

const source=await readFile(new URL('../public/world-sync.js',import.meta.url));
const {createWorldSynchronizer,worldMatches}=await import('data:text/javascript;base64,'+source.toString('base64'));
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const airport={key:'airport',id:'airport-v4',version:'4',seed:41031,displayed_world_sha256:'a'.repeat(64)};
const valley={key:'r6-valley-20261103',id:'stage1-valley',version:'2',seed:41031,displayed_world_sha256:'b'.repeat(64)};
const world=e=>({environment:e.key,id:e.id,version:e.version,seed:e.seed,displayed_world_sha256:e.displayed_world_sha256});

test('an unsuccessful world request is retried while mismatched terrain remains unavailable',async()=>{
  let expected=valley,rendered=world(airport),available=true,clock=0,requests=0;
  const sync=createWorldSynchronizer({getExpected:()=>expected,getRendered:()=>rendered,
    fetchWorld:async()=>{requests++;if(requests===1)throw Error('offline');return world(expected);},
    applyWorld:w=>{rendered=w;},setUnavailable:x=>{available=!x;},now:()=>clock,retryMs:1000});
  sync.reconcile();await flush();assert.equal(available,false);assert.equal(requests,1);
  clock=999;sync.reconcile();await flush();assert.equal(requests,1);
  clock=1000;sync.reconcile();await flush();assert.equal(requests,2);
  assert.equal(worldMatches(rendered,valley),true);assert.equal(available,true);
});

test('a delayed response for a previous environment cannot replace the latest world',async()=>{
  let expected=airport,rendered=world(valley),resolveFirst,available=true,requests=0;
  const sync=createWorldSynchronizer({getExpected:()=>expected,getRendered:()=>rendered,
    fetchWorld:()=>{requests++;return requests===1?new Promise(resolve=>{resolveFirst=resolve;}):Promise.resolve(world(expected));},
    applyWorld:w=>{rendered=w;},setUnavailable:x=>{available=!x;}});
  sync.reconcile();await flush();expected=valley;
  resolveFirst(world(airport));await flush();
  assert.equal(worldMatches(rendered,valley),true); // stale airport was not applied
  sync.reconcile();assert.equal(available,true);
  expected=airport;sync.reconcile();await flush();
  assert.equal(worldMatches(rendered,airport),true);assert.equal(available,true);
});

test('same id and version with a different environment key is not a match',()=>{
  assert.equal(worldMatches({environment:'sandbox',id:'stage1-valley',version:'2'},valley),false);
});


test('same labels with different terrain or seed cannot be treated as the current world',()=>{
  assert.equal(worldMatches({...world(valley),displayed_world_sha256:'c'.repeat(64)},valley),false);
  assert.equal(worldMatches({...world(valley),seed:valley.seed+1},valley),false);
  assert.equal(worldMatches({...world(valley),displayed_world_sha256:undefined},valley),false);
  assert.equal(worldMatches(world(valley),{...valley,displayed_world_sha256:'bad'}),false);
});

test('a delayed response with matching labels but old terrain stays unavailable until the right world arrives',async()=>{
  const revised={...valley,displayed_world_sha256:'c'.repeat(64)};
  let expected=valley,rendered=world(airport),resolveFirst,available=true,requests=0;
  const sync=createWorldSynchronizer({getExpected:()=>expected,getRendered:()=>rendered,
    fetchWorld:()=>{requests++;return requests===1?new Promise(resolve=>{resolveFirst=resolve;}):Promise.resolve(world(revised));},
    applyWorld:w=>{rendered=w;},setUnavailable:x=>{available=!x;}});
  sync.reconcile();await flush();expected=revised;resolveFirst(world(valley));await flush();
  assert.equal(available,false);assert.equal(worldMatches(rendered,revised),false);
  sync.reconcile();await flush();assert.equal(available,true);assert.equal(worldMatches(rendered,revised),true);
});
