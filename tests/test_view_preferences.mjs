import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';

const source=await readFile(new URL('../public/view-preferences.js',import.meta.url));
const {createViewPreferenceStore}=await import('data:text/javascript;base64,'+source.toString('base64'));
const storage=()=>{const data=new Map();return {getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),data};};
const cockpit={mode:'cockpit',cockpitYaw:.2,cockpitPitch:-.1,chaseOffset:[9,-11,8]};

test('aircraft and environments keep separate presentation preferences across reload',()=>{
  const store=storage(),first=createViewPreferenceStore(store);
  assert.equal(first.save('r6','airport',cockpit),true);
  assert.equal(first.save('phantom-a10c','sandbox',{...cockpit,mode:'chase',cockpitYaw:-.4}),true);
  const reloaded=createViewPreferenceStore(store);
  assert.deepEqual(reloaded.load('r6','airport'),cockpit);
  assert.equal(reloaded.load('r6','sandbox'),null);
  assert.equal(reloaded.load('phantom-a10c','sandbox').cockpitYaw,-.4);
});

test('invalid, stale or unavailable storage never creates a guessed preference',()=>{
  const store=storage(),prefs=createViewPreferenceStore(store);
  assert.equal(prefs.save('', 'airport', cockpit),false);
  assert.equal(prefs.save('r6','airport',{...cockpit,cockpitYaw:NaN}),false);
  assert.equal(prefs.save('r6','airport',{...cockpit,mode:'free'}),false);
  store.setItem('vtx.view.v1:r6:airport','{broken');
  assert.equal(prefs.load('r6','airport'),null);
  const denied=createViewPreferenceStore({getItem(){throw Error('denied');},setItem(){throw Error('denied');}});
  assert.equal(denied.save('r6','airport',cockpit),true);
  assert.deepEqual(denied.load('r6','airport'),cockpit);
});

test('free view preserves position and aim without corrupting its saved values',()=>{
  const prefs=createViewPreferenceStore(storage());
  const free={mode:'free',cockpitYaw:0,cockpitPitch:0,freePosition:[10,20,30],freeAim:[11,20,30]};
  assert.equal(prefs.save('r6','airport',free),true);
  free.freePosition[0]=999;
  assert.deepEqual(prefs.load('r6','airport').freePosition,[10,20,30]);
});

test('switching views restores the matching aircraft without sending simulator actions',async()=>{
  const app=await readFile(new URL('../public/app.js',import.meta.url),'utf8');
  const start=app.indexOf('function saveCameraPreference(){');
  const end=app.indexOf('// Ride cameras have independent transforms.',start);
  assert.ok(start>=0&&end>start);
  const saved=storage(),prefs=createViewPreferenceStore(saved);
  class Vec {
    constructor(x=0,y=0,z=0){this.x=x;this.y=y;this.z=z;}
    clone(){return new Vec(this.x,this.y,this.z);}
    sub(v){this.x-=v.x;this.y-=v.y;this.z-=v.z;return this;}
    add(v){this.x+=v.x;this.y+=v.y;this.z+=v.z;return this;}
    copy(v){this.x=v.x;this.y=v.y;this.z=v.z;return this;}
    set(x,y,z){this.x=x;this.y=y;this.z=z;return this;}
    toArray(){return [this.x,this.y,this.z];}
  }
  const ctx={cameraPreferences:prefs,THREE:{Vector3:Vec},cameraPreferenceIdentity:null,
    restoringCameraPreference:false,cameraPreferencesSuspended:false,rideEnabled:false,replayFrames:null,cameraMode:'chase',
    cockpitYaw:0,cockpitPitch:0,savedChaseOffset:null,Math,
    camera:{position:new Vec(9,-11,8),up:new Vec()},orbit:{target:new Vec(),update(){}},
    freeCam:{position:new Vec(2,3,4),yaw:0,pitch:0,teleport(){}},
    physicalCameraTarget:()=>[0,0,0],setCameraMode(mode){ctx.cameraMode=mode;},
    fetch(){throw Error('camera settings must not call the simulator');}};
  runInNewContext(app.slice(start,end),ctx);
  const view=(variant,environment)=>({inspection_selection_known:true,
    observation:{configuration:{airframe_variant:variant}},environment:{key:environment},rendering_truth:{}});
  ctx.syncCameraPreference(view('r6','airport'));
  ctx.cameraMode='cockpit';ctx.cockpitYaw=.4;ctx.cockpitPitch=-.2;ctx.savedChaseOffset=new Vec(9,-11,8);
  ctx.saveCameraPreference();
  ctx.syncCameraPreference(view('phantom-a10c','sandbox'));
  ctx.cameraMode='chase';ctx.cockpitYaw=-.1;ctx.cockpitPitch=.3;ctx.camera.position.set(4,5,6);
  ctx.saveCameraPreference();
  ctx.syncCameraPreference(view('r6','airport'));
  assert.equal(ctx.cameraMode,'cockpit');assert.equal(ctx.cockpitYaw,.4);assert.equal(ctx.cockpitPitch,-.2);
  ctx.rideEnabled=true;ctx.cameraMode='free';ctx.syncCameraPreference(view('phantom-a10c','sandbox'));
  assert.equal(ctx.cameraPreferenceIdentity.variant,'r6');
  ctx.rideEnabled=false;ctx.syncCameraPreference(view('r6','airport'));
  assert.equal(ctx.cameraMode,'cockpit');assert.equal(ctx.cockpitYaw,.4);
  ctx.replayFrames=[{}];ctx.saveCameraPreference();
  assert.equal(prefs.load('r6','airport').mode,'cockpit');
  ctx.replayFrames=null;ctx.syncCameraPreference({inspection_selection_known:false});
  assert.equal(ctx.cameraPreferenceIdentity,null);
});
