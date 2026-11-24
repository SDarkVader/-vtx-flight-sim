import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/BufferGeometryUtils.js';
import {distanceToTrail} from './alpine-layout.js';
import {hash2} from './city-density.js';
import {meridianStreets} from './meridian-streets.js';
import {leafyCluster} from './parallax-court.js';

const TREE_CAP = 52;
const ROAD_VERGE = 6;
const TREE_CLEARANCE = 3.5;
const FRONTAGE_REACH = 46;
const SITE_SPACING = 150;
const POCKET_SPACING = 100;
const CELL_SIZE = 128;
const FRONTAGE_ROADS = new Set(['boulevard','arterial','street','local','lane']);

function contains([left,bottom,right,top],x,y) {
  return x>=left && x<=right && y>=bottom && y<=top;
}

function routeFootprint(route) {
  const xs=route.points.map(point=>point[0]), ys=route.points.map(point=>point[1]);
  const halfWidth=route.width_m/2, radius=halfWidth+TREE_CLEARANCE;
  const corners=[];
  if(route.mitre) {
    const points=route.points;
    const [firstX,firstY]=points[0],[lastX,lastY]=points.at(-1);
    const closed=route.kind!=='marina-link' && firstX===lastX && firstY===lastY;
    for(let i=closed?0:1;i<points.length-1;i++) {
      const [x,y]=points[i],[ax,ay]=points[i>0?i-1:points.length-2],[bx,by]=points[i+1];
      const dx=x-ax,dy=y-ay,ex=bx-x,ey=by-y;
      const product=Math.hypot(dx,dy)*Math.hypot(ex,ey);
      if(!product) continue;
      const cosine=(dx*ex+dy*ey)/product;
      const reach=halfWidth/Math.sqrt(Math.max(Number.EPSILON,(1+cosine)/2));
      if(reach>halfWidth+.5) corners.push({x,y,radius:reach+TREE_CLEARANCE});
    }
  }
  const margin=Math.max(radius,...corners.map(corner=>corner.radius));
  const bounds=[Math.min(...xs)-margin,Math.min(...ys)-margin,Math.max(...xs)+margin,Math.max(...ys)+margin];
  return {bounds,radius,points:route.points,corners};
}

function frontageCells(obstacles,wards) {
  const cells=new Map();
  const [minX,minY,maxX,maxY]=wards.map(value=>Math.floor(value/CELL_SIZE));
  for(const obstacle of obstacles) {
    const {center:[x,y],half:[a,b],role,crown_radius_m:canopy}=obstacle;
    const reach=role==='architecture' ? FRONTAGE_REACH : TREE_CLEARANCE;
    const dx=Math.max(a+reach,(canopy??0)+TREE_CLEARANCE);
    const dy=Math.max(b+reach,(canopy??0)+TREE_CLEARANCE);
    const x0=Math.max(minX,Math.floor((x-dx)/CELL_SIZE)),x1=Math.min(maxX,Math.floor((x+dx)/CELL_SIZE));
    const y0=Math.max(minY,Math.floor((y-dy)/CELL_SIZE)),y1=Math.min(maxY,Math.floor((y+dy)/CELL_SIZE));
    for(let i=x0;i<=x1;i++) for(let j=y0;j<=y1;j++) {
      const key=`${i},${j}`;
      if(!cells.has(key)) cells.set(key,[]);
      cells.get(key).push(obstacle);
    }
  }
  return cells;
}

function clearFrontage(obstacles,{x,y,roadX,roadY}) {
  let hasBuilding=false;
  for(const {center,half,role,crown_radius_m:canopy} of obstacles) {
    const dx=Math.abs(center[0]-x),dy=Math.abs(center[1]-y);
    const halfWidth=Math.max(half[0],canopy??0),halfDepth=Math.max(half[1],canopy??0);
    if(dx<=halfWidth+TREE_CLEARANCE && dy<=halfDepth+TREE_CLEARANCE) return false;
    const sameSide=(center[0]-roadX)*(x-roadX)+(center[1]-roadY)*(y-roadY)>0;
    if(role==='architecture' && sameSide && dx<=half[0]+FRONTAGE_REACH && dy<=half[1]+FRONTAGE_REACH) {
      hasBuilding=true;
    }
  }
  return hasBuilding;
}

function measureStreet(points) {
  let length=0;
  const segments=[];
  for(let i=1;i<points.length;i++) {
    const [x,y]=points[i-1],[bx,by]=points[i];
    const dx=bx-x,dy=by-y,span=Math.hypot(dx,dy);
    if(!span) continue;
    segments.push({x,y,cos:dx/span,sin:dy/span,start:length,end:length+span});
    length+=span;
  }
  return {segments,length};
}

function vergePoint(segments,station,offset) {
  const segment=segments.find(({start,end})=>station>=start && station<=end);
  if(!segment) return null;
  const {x,y,cos,sin,start}=segment, along=station-start;
  const roadX=x+along*cos,roadY=y+along*sin;
  return {roadX,roadY,x:roadX-offset*sin,y:roadY+offset*cos};
}

// Dress built-up verges along the displayed street plan. Keep the surveyed routes clear too.
export function planAvenuePlanting(world,ground) {
  const city=world.vaderland, wardBounds=city?.neighbourhoods?.bounds, market=city?.quarter?.bounds_m;
  if(!wardBounds || !market || !ground) return [];
  const [left,right,bottom,top]=wardBounds;
  const wards=[left,bottom,right,top];
  const painted=meridianStreets(world);
  const occupied=[...new Set([...painted,...city.routes,...(city.streams??[])])]
    .filter(route=>route.points.length>1).map(routeFootprint);
  const avenues=painted.filter(route=>FRONTAGE_ROADS.has(route.kind));
  const frontage=frontageCells(world.obstacles,wards);
  const waterline=(world.harbour?.waterLevelM??0)+2;
  function plantable(point,route) {
    if(!point) return null;
    const {x,y}=point;
    if(!contains(wards,x,y) || contains(market,x,y)) return null;
    const z=ground.heightAt(x,y);
    if(!Number.isFinite(z) || z<waterline || ground.normalAt(x,y).z<.97) return null;
    const cell=frontage.get(`${Math.floor(x/CELL_SIZE)},${Math.floor(y/CELL_SIZE)}`);
    if(!cell || !clearFrontage(cell,point)) return null;
    const blocks=({bounds,radius,points,corners})=>contains(bounds,x,y) &&
      (distanceToTrail(x,y,points)<radius || corners.some(corner=>Math.hypot(corner.x-x,corner.y-y)<corner.radius));
    if(occupied.some(blocks)) return null;
    return {x,y,z,seed:hash2(x,y),route:route.name};
  }
  const pockets=[];
  for(const route of avenues) {
    const {segments,length}=measureStreet(route.points);
    const start=SITE_SPACING*hash2(...route.points[0]);
    for(let station=start;station<length;station+=SITE_SPACING*(.76+.48*hash2(station,length))) {
      const side=hash2(station,length)<.5 ? -1 : 1;
      const verge=route.width_m/2+ROAD_VERGE;
      let anchor,anchorStation,offset;
      for(const shift of [0,-24,24]) {
        anchorStation=station+shift;
        for(const direction of [side,-side]) {
          offset=direction*verge;
          anchor=plantable(vergePoint(segments,anchorStation,offset),route);
          if(anchor) break;
        }
        if(anchor) break;
      }
      if(!anchor) continue;
      const trees=[anchor];
      const size=hash2(anchor.y,anchor.x), spread=12+size*7;
      const extras=size<.38 ? [] : size<.8 ? [spread] : [-spread,spread];
      for(const shift of extras) {
        const extra=plantable(vergePoint(segments,anchorStation+shift,offset+Math.sign(offset)*1.5),route);
        if(extra && trees.every(tree=>Math.hypot(tree.x-extra.x,tree.y-extra.y)>8)) trees.push(extra);
      }
      pockets.push({anchor,trees});
    }
  }
  const anchors=[],sites=[];
  for(const {anchor,trees} of pockets.sort((a,b)=>a.anchor.seed-b.anchor.seed)) {
    if(anchors.some(site=>Math.hypot(site.x-anchor.x,site.y-anchor.y)<POCKET_SPACING)) continue;
    if(sites.length+trees.length>TREE_CAP) continue;
    anchors.push(anchor);
    sites.push(...trees);
    if(sites.length===TREE_CAP) break;
  }
  return sites;
}

function treeGeometry() {
  const stem=new THREE.CylinderGeometry(.018,.032,.62,6).toNonIndexed();
  stem.rotateX(Math.PI/2).translate(0,0,.31);
  stem.deleteAttribute('uv');
  const bark=new THREE.Color('#493e32');
  const stemColors=new Float32Array(stem.attributes.position.count*3);
  for(let i=0;i<stemColors.length;i+=3) bark.toArray(stemColors,i);
  stem.setAttribute('color',new THREE.BufferAttribute(stemColors,3));

  const crown=leafyCluster().scale(.35,.35,.42).translate(0,0,.65);
  const leaf=new THREE.Color('#526b43'),colors=crown.attributes.color;
  for(let i=0;i<colors.count;i++) {
    const tint=colors.getX(i);
    colors.setXYZ(i,leaf.r*tint,leaf.g*tint,leaf.b*tint);
  }
  const geometry=mergeGeometries([stem,crown]);
  stem.dispose();crown.dispose();
  return geometry;
}

export function buildAvenuePlanting(group,world,ground) {
  const sites=planAvenuePlanting(world,ground);
  if(!sites.length) return null;
  const material=new THREE.MeshStandardMaterial({vertexColors:true,roughness:1,side:THREE.DoubleSide});
  const trees=new THREE.InstancedMesh(treeGeometry(),material,sites.length);
  trees.name='Meridian outskirts trees';
  const pose=new THREE.Object3D(), tint=new THREE.Color();
  for(const [i,{x,y,z,seed}] of sites.entries()) {
    pose.position.set(x,y,z-.02);
    pose.rotation.z=seed*2*Math.PI;
    pose.scale.setScalar(3.8+1.8*hash2(y,x));
    pose.updateMatrix();
    trees.setMatrixAt(i,pose.matrix);
    const brightness=.86+.23*seed;
    tint.setRGB(brightness,brightness,.94*brightness);
    trees.setColorAt(i,tint);
  }
  trees.computeBoundingSphere();
  group.add(trees);
  return trees;
}
