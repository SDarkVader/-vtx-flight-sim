import * as THREE from 'three';
import {makeAirportModel} from '../airport-models.js?v=2';
import {besideTrail,distanceToTrail} from './alpine-layout.js';

const pieces = [
  {name:'Tumbled airport trainer', type:'fixed-wing', paint:0xc76739, scale:2.1, turn:.6, lean:.56},
  {name:'Tower rotor', type:'rotorcraft', part:'airport-rotor', paint:0xb99664, scale:2.5, turn:-.38, lean:1.24},
  {name:'Stranded service truck', type:'ground', paint:0xcd9465, scale:2, turn:.85, lean:.19},
  {name:'Salvaged airframe tube', type:'fixed-wing', part:'airport-fuselage', paint:0x6899a6, scale:2.1, turn:-.45, lean:.43},
];
const amber = new THREE.Color('#ffac62');

function extractPiece(spec) {
  const vehicle=makeAirportModel(THREE,spec.type,spec.paint);
  if(!spec.part)return vehicle;
  const part=vehicle.getObjectByName(spec.part);
  part.removeFromParent();
  const retained=new Set(), disposed=new Set();
  part.traverse(node=>{retained.add(node.geometry);retained.add(node.material);});
  vehicle.traverse(node=>{
    for(const resource of [node.geometry,node.material]){
      if(resource&&!retained.has(resource)&&!disposed.has(resource)){resource.dispose();disposed.add(resource);}
    }
  });
  return part;
}

export function placeAlpineSalvage(root, route, samples, ground, placeLight) {
  const entries=route.id==='storm-face'?[0,1,3]:route.id==='meadow'?[2]:[];
  const placed=[];
  for(const [i,key] of entries.entries()){
    const index=Math.round((samples.length-1)*(i+1)/(entries.length+1));
    const [x,y]=samples[index], [ax,ay]=samples[index-1], [bx,by]=samples[index+1];
    const dx=bx-ax,dy=by-ay;
    const position=besideTrail(route,[x,y],dx,dy,17,i%2===0?1:-1);
    if(!position)continue;
    const spec=pieces[key], fragment=extractPiece(spec);
    const marker=new THREE.Group();
    marker.name=spec.name;
    fragment.position.set(0,0,0);
    fragment.scale.multiplyScalar(spec.scale);
    marker.rotation.set(spec.lean,0,Math.atan2(dy,dx)+spec.turn);
    marker.add(fragment);
    if(spec.part==='airport-fuselage'){
      const rim=new THREE.Mesh(new THREE.TorusGeometry(1.3,.16,6,14),
        new THREE.MeshBasicMaterial({color:'#b67d54'}));
      rim.rotation.y=Math.PI/2;rim.position.x=6.6;
      marker.add(rim);
    }
    const bounds=new THREE.Box3().setFromObject(marker);
    const z=ground(...position);
    marker.position.set(...position,z-bounds.min.z-.18);
    marker.traverse(node=>{
      if(!node.isMesh)return;
      node.castShadow=false;node.receiveShadow=false;
      node.material.emissive?.copy(node.material.color).multiplyScalar(.25);
    });
    root.add(marker);
    placeLight(position,amber,route.id==='storm-face'?43:31,.42,5.5);
    const radialExtent=Math.hypot(Math.max(Math.abs(bounds.min.x),Math.abs(bounds.max.x)),
      Math.max(Math.abs(bounds.min.y),Math.abs(bounds.max.y)));
    const clearance=distanceToTrail(...position,route.points)-route.width*.5-radialExtent;
    placed.push({name:spec.name,point:position,clearance});
  }
  return placed;
}
