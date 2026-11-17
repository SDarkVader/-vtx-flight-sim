import assert from 'node:assert/strict';
import {TacticalMinimap,mapScaleBar,mapZoomLimits} from '../public/vtx-env/tactical-minimap.js';
const events={},canvas={width:900,height:600,getContext:()=>({}),addEventListener:(key,fn)=>events[key]=fn,getBoundingClientRect:()=>({width:450,height:300})};
const map=new TacticalMinimap(canvas);map.worldHalf=4000;
for(const zoom of [.06,.12,.5,2,10]){
 map.zoom=zoom;const p=map.getProjection(),bar=mapScaleBar(p,450,900);
 assert.ok(Math.abs((p.px(bar.metres)-p.px(0))/2-bar.pixels)<1e-9,'scale length is the projected real world distance after CSS resize');
 assert.ok(bar.pixels<=162&&bar.pixels>0);
}
map.zoom=.5;const p=map.getProjection(),anchor=[630,180],point=[p.unpx(anchor[0]),p.unpy(anchor[1])];map.zoomBy(1.4,anchor);
assert.ok(Math.abs(map.getProjection().unpx(anchor[0])-point[0])<1e-9);assert.ok(Math.abs(map.getProjection().unpy(anchor[1])-point[1])<1e-9);
map.zoomBy(1e9);assert.equal(map.zoom,mapZoomLimits(4000,1.5).max);map.zoomBy(1e-9);assert.equal(map.zoom,mapZoomLimits(4000,1.5).min);
assert.equal(typeof events.wheel,'function');
