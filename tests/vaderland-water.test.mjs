import assert from 'node:assert/strict';
import test from 'node:test';
import * as THREE from 'three';
import {followTide} from '../public/vtx-env/vaderland/tidal-surface.js';

test('solver water keeps chart holes, shared patch edges and snapshot time',()=>{
  const ring=points=>points.map(p=>new THREE.Vector2(...p));
  const shape=new THREE.Shape(ring([[0,0],[20,0],[20,20],[0,20]]));
  shape.holes.push(new THREE.Path(ring([[8,8],[8,12],[12,12],[12,8]])));
  const original=new THREE.ShapeGeometry(shape);
  const water=new THREE.Mesh(original,new THREE.MeshBasicMaterial({side:THREE.DoubleSide}));
  const tide=followTide(water,{samples:7,spacing_m:2});
  function state(time,z,generation='A'){
    const bytes=Buffer.from(new Float32Array(49).fill(z).buffer).toString('base64');
    return {available:true,generation,t_s:time,water_surface:{samples:7,spacing_m:2,
      patches:[[0,2],[6,2]].map(origin=>({origin,offset_f32le:bytes}))}};
  }
  function level(x,y){
    const hits=new THREE.Raycaster(new THREE.Vector3(x,y,50),new THREE.Vector3(0,0,-1)).intersectObject(water);
    return hits[0]?.point.z;
  }
  function area(g){
    const pos=g.attributes.position,idx=g.index;
    let sum=0;
    for(let i=0;i<idx.count;i+=3){
      const [a,b,c]=[0,1,2].map(j=>idx.getX(i+j));
      sum+=Math.abs((pos.getX(b)-pos.getX(a))*(pos.getY(c)-pos.getY(a))-
        (pos.getY(b)-pos.getY(a))*(pos.getX(c)-pos.getX(a)))/2;
    }
    return sum;
  }
  tide.update(state(5,.5));
  assert.ok(Math.abs(area(water.geometry)-384)<1e-4);
  for(const x of [4,8,12,15])assert.ok(Math.abs(level(x,6)-.5)<1e-5);
  assert.equal(level(10,10),undefined);assert.equal(level(19,19),0);
  tide.update(state(4,-1));assert.equal(tide.time,5);assert.equal(level(4,6),.5);
  tide.update(state(0,-.25,'restored'));assert.equal(level(4,6),-.25);
  tide.update({available:false});assert.equal(water.geometry,original);assert.equal(level(4,6),0);
});
