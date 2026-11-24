import assert from 'node:assert/strict';
import test from 'node:test';
import {Group} from 'three';
import {buildAvenuePlanting,planAvenuePlanting} from '../public/vtx-env/vaderland/avenue-planting.js';

const street={name:'District Avenue',kind:'street',width_m:24,points:[[0,680],[0,2100]]};
const buildings=[-44,44].map(x=>({role:'architecture',center:[x,1400,34],half:[8,720,8]}));
const city={routes:[street],neighbourhoods:{bounds:[-150,150,680,2100]},quarter:{bounds_m:[-80,1180,80,1420]}};
const world={vaderland:city,obstacles:buildings,harbour:{waterLevelM:7}};
const dryGround={heightAt:()=>26,normalAt:()=>({z:1})};

test('surveyed outskirts trees stay outside roads, structures, and the detailed market',()=>{
  const baseline=planAvenuePlanting(world,dryGround);
  assert.ok(baseline.length>3);
  assert.deepEqual(planAvenuePlanting(world,dryGround),baseline);
  assert.ok(baseline.every(({x,y,z})=>[18,19.5].includes(Math.abs(x)) && (y<1180||y>1420) && z===26));

  const [roadSite,obstacleSite]=baseline;
  const crossing={name:'Existing local crossing',kind:'local',width_m:14,points:[[-75,roadSite.y],[75,roadSite.y]]};
  const changed={...world,vaderland:{...city,routes:[street,crossing]},
    obstacles:[...buildings,{center:[obstacleSite.x,obstacleSite.y,26],half:[1,1,1]}]};
  const kept=planAvenuePlanting(changed,dryGround);
  assert.ok(kept.length>0 && kept.length<baseline.length);
  assert.ok(kept.every(site=>Math.abs(site.y-roadSite.y)>7 && Math.hypot(site.x-obstacleSite.x,site.y-obstacleSite.y)>=3.5));
});

test('Vaderland 33 plants along the rendered West Exchange frontage and clears a replaced survey route',()=>{
  const frontage=[
    {center:[-2776.28,2525.17,34.6673],half:[41.94,24.35,4.8792]},
    {center:[-2491.39,2478.11,32.1503],half:[39.96,35.03,4.0349]},
    {center:[-2492.20,2805.64,36.1394],half:[31.08,22.04,4.1034]},
    {center:[-2695.70,2596.90,39.6750],half:[15.60,14.10,9.0465]},
  ].map(parcel=>({...parcel,role:'architecture'}));
  const surveyed={...world,id:'vaderland-33',obstacles:frontage,
    vaderland:{...city,routes:[],neighbourhoods:{bounds:[-3000,-2200,2350,2900]}}};
  const placed=planAvenuePlanting(surveyed,dryGround);
  const west=placed.find(site=>site.route==='West Exchange Crescent');
  assert.ok(west);
  const replaced={name:'Terrace 2',kind:'street',width_m:24,points:[[-3000,west.y],[-2200,west.y]]};
  const next=planAvenuePlanting({...surveyed,vaderland:{...surveyed.vaderland,routes:[replaced]}},dryGround);
  assert.ok(next.some(site=>site.route==='West Exchange Crescent'));
  assert.ok(next.every(site=>site.route!==replaced.name && Math.abs(site.y-west.y)>12));
});

test('open land, wet ground, and unsupported scenery do not get trees',()=>{
  assert.deepEqual(planAvenuePlanting({...world,obstacles:[]},dryGround),[]);
  assert.deepEqual(planAvenuePlanting(world,{...dryGround,heightAt:()=>7}),[]);
  assert.deepEqual(planAvenuePlanting(world,{...dryGround,normalAt:()=>({z:.8})}),[]);
  assert.equal(buildAvenuePlanting(new Group(),{},dryGround),null);
});

test('the planting makes one capped, frustum-culled draw without shadows',()=>{
  const lines=[-600,-300,0,300,600];
  const roads=lines.map((x,i)=>({...street,name:`North street ${i+1}`,points:[[x,680],[x,5000]]}));
  const parcels=lines.flatMap(x=>buildings.map(building=>({...building,
    center:[x+building.center[0],2840,34],half:[8,2160,8]})));
  const broadWorld={...world,obstacles:parcels,vaderland:{...city,routes:roads,
    neighbourhoods:{bounds:[-750,750,680,5000]}}};
  const group=new Group();
  const trees=buildAvenuePlanting(group,broadWorld,dryGround);
  assert.equal(group.children.length,1);
  assert.equal(trees.isInstancedMesh,true);
  assert.equal(trees.count,52);
  assert.ok(trees.geometry.attributes.position.count/3<=80);
  assert.equal(trees.frustumCulled,true);
  assert.equal(trees.castShadow,false);
  trees.geometry.dispose();trees.material.dispose();
});
