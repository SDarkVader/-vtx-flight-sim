import assert from 'node:assert/strict';
import test from 'node:test';
import {Group} from 'three';
import {createGround} from '../public/vtx-env/ground.js';
import {buildWestFrontages,planWestFrontages} from '../public/vtx-env/vaderland/west-frontages.js';

const building = {id:'courtyard-567',kind:'box',role:'architecture',
  center:[-2387.6,2803.7058,38],half:[11.5,16,4]};
const world = {id:'vaderland-33',half_m:8000,heights_m:[[34,34,34],[34,34,34],[34,34,34]],
  obstacles:[building],vaderland:{quarter:{},routes:[]}};
const ground = createGround(world,null);

test('west frontage uses the painted Crescent and ends outside a real facade footprint', () => {
  const baseline = structuredClone(world);
  const [link,...other] = planWestFrontages(world,ground);
  assert.deepEqual(other,[]);
  assert.equal(link.building,building.id);
  assert.equal(link.street,'West Exchange Crescent');
  assert.ok(link.length>=4 && link.length<=29);
  const vertices = link.pieces.flat();
  const wall = building.center[0]-building.half[0];
  assert.ok(vertices.every(([x]) => x<=wall-.4));
  assert.ok(Math.abs(link.end[0]-wall)<=1.2);
  assert.deepEqual(world,baseline);
  assert.deepEqual(planWestFrontages({...world,id:'vaderland-32'},ground),[]);
});

test('links route clear of conflicting streets and skip blocked frontages', () => {
  const crossing = {name:'Existing service connection',kind:'local',width_m:6,
    points:[[-2403,2740],[-2403,2865]]};
  const [alternative] = planWestFrontages({...world,vaderland:{...world.vaderland,routes:[crossing]}},ground);
  assert.ok(alternative.pieces.flat().every(([x]) => x>=-2399.6));
  const obstruction = {id:'occupied-forecourt',kind:'box',center:[-2399,2804,35],half:[8,25,1]};
  assert.deepEqual(planWestFrontages({...world,obstacles:[building,obstruction]},ground),[]);
});

test('the frontage draws in one culled batch at terrain height plus a small display offset', () => {
  const group = new Group();
  const mesh = buildWestFrontages(group,world,ground,{night:{value:0}},'');
  assert.deepEqual(group.children,[mesh]);
  assert.equal(mesh.frustumCulled,true);
  assert.equal(mesh.castShadow,false);
  const p = mesh.geometry.attributes.position;
  assert.ok(p.count>=12);
  for(let i=0;i<p.count;i++){
    assert.ok(Math.abs(p.getZ(i)-ground.heightAt(p.getX(i),p.getY(i))-.018)<1e-4);
  }
  mesh.geometry.dispose();
  mesh.material.dispose();
});
