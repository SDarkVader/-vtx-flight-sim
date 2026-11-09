import assert from 'node:assert/strict';
import {TacticalMinimap} from '../public/vtx-env/tactical-minimap.js';
const canvas={width:540,height:430,getContext:()=>({}),addEventListener(){},getBoundingClientRect(){return {width:270,height:215}}};
const m=new TacticalMinimap(canvas);
for (const half of [500,4000]) {
  const p=m.getProjection(half);
  assert.equal(p.unpx(p.px(-690)),-690);
  assert.equal(p.unpy(p.py(110)),110);
  assert.ok(Math.abs((p.px(100)-p.px(0))-(p.py(0)-p.py(100)))<1e-10);
  assert.ok(p.scaleM(1432)>canvas.width*.65,'airport should fill most of the width');
}
m.worldHalf=4000;
m.tacticalMode=true; m.center=[0,0];
m.zoom=1000/(2*m.worldHalf*Math.max(1,canvas.width/canvas.height));
const world=m.getProjection(4000);
assert.ok(world.unpx(0)<=-4000);
assert.ok(world.unpx(canvas.width)>=4000);
assert.equal(world.unpy(0),4000);
assert.equal(world.unpy(canvas.height),-4000);
console.log('map projection and airport/world scales verified');