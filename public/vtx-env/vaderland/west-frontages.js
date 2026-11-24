import * as THREE from 'three';
import {meridianStreets} from './meridian-streets.js';

const STREETS = new Set(['West Exchange Crescent', 'Orchard Rise']);
const WARD = [-3060, 2290, -2220, 3470];
const MAX_LINKS = 7;
const MAX_LENGTH = 29;
const ROAD_GAP = 1.15;
const WALL_GAP = 1.05;
const CLEARANCE = .4;
const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));

function bounds(points) {
  const x = points.map(point => point[0]), y = points.map(point => point[1]);
  return [Math.min(...x), Math.min(...y), Math.max(...x), Math.max(...y)];
}

function overlaps(a, b, margin = 0) {
  return a[0] < b[2]+margin && a[2] > b[0]-margin && a[1] < b[3]+margin && a[3] > b[1]-margin;
}

function unit(a, b) {
  const dx = b[0]-a[0], dy = b[1]-a[1], length = Math.hypot(dx, dy);
  return length ? [dx/length, dy/length] : [0, 0];
}

function strip(a, b, width) {
  const [x,y] = unit(a,b), dx = -y*width/2, dy = x*width/2;
  return [[a[0]-dx,a[1]-dy],[b[0]-dx,b[1]-dy],[b[0]+dx,b[1]+dy],[a[0]+dx,a[1]+dy]];
}

function roadSections({name, kind, width_m:width, points, mitre}) {
  // Follow the rendered strip, including the pavement miter at each bend.
  const joined = mitre || kind === 'experimental' || kind === 'marina-link' ||
    kind === 'speedway' || name === 'Exchange Boulevard';
  if(!joined) return points.slice(1).map((b,i) => strip(points[i],b,width));
  const normals = points.slice(1).map((point,i) => {
    const [x,y] = unit(points[i],point);
    return [-y,x];
  });
  const last = normals.length-1;
  const closed = kind !== 'marina-link' && points[0].every((n,i) => n === points.at(-1)[i]);
  const edges = points.map(([x,y],i) => {
    const a = normals[i>0?i-1:closed?last:0], b = normals[i<=last?i:closed?0:last];
    const scale = width/2 / Math.max(.05,1+a[0]*b[0]+a[1]*b[1]);
    const dx = (a[0]+b[0])*scale, dy = (a[1]+b[1])*scale;
    return [[x-dx,y-dy],[x+dx,y+dy]];
  });
  return edges.slice(1).map((b,i) => [edges[i][0],b[0],b[1],edges[i][1]]);
}

function footprint({kind, center:[x,y], half:[a,b]}) {
  if(kind !== 'cylinder') return [[x-a,y-b],[x+a,y-b],[x+a,y+b],[x-a,y+b]];
  const radius = Math.max(a,b)/Math.cos(Math.PI/24);
  return Array.from({length:24},(_,i) => {
    const angle = i*Math.PI/12;
    return [x+radius*Math.cos(angle), y+radius*Math.sin(angle)];
  });
}

function obstacleBounds({kind,center:[x,y],half:[a,b]}) {
  const radius = kind === 'cylinder' ? Math.max(a,b)/Math.cos(Math.PI/24) : 0;
  return [x-(radius||a),y-(radius||b),x+(radius||a),y+(radius||b)];
}

function clears(poly, occupied) {
  const area = bounds(poly);
  return occupied.every(other => {
    if(!overlaps(area,other.area,CLEARANCE)) return true;
    // The separating-axis test also reserves a margin along at least one edge normal.
    return [poly,other.poly].some(points => points.some((a,i) => {
      const [dx,dy] = unit(a,points[(i+1)%points.length]);
      const project = ([x,y]) => -dy*x+dx*y;
      const p = poly.map(project), q = other.poly.map(project);
      return Math.max(Math.min(...p)-Math.max(...q),Math.min(...q)-Math.max(...p)) >= CLEARANCE;
    }));
  });
}

function project([x,y],a,b) {
  const [dx,dy] = unit(a,b);
  const t = clamp((x-a[0])*dx+(y-a[1])*dy,0,Math.hypot(b[0]-a[0],b[1]-a[1]));
  return [a[0]+dx*t,a[1]+dy*t];
}

function frontage({kind,center:[x,y],half:[a,b]},point) {
  if(kind === 'cylinder'){
    const [dx,dy] = unit([x,y],point);
    return [x+a*dx,y+a*dy];
  }
  const [u,v] = point;
  // Keep the end pad on a wall face, clear of the corners.
  return Math.abs(u-x)-a >= Math.abs(v-y)-b
    ? [x+Math.sign(u-x)*a,clamp(v,y-b+3,y+b-3)]
    : [clamp(u,x-a+3,x+a-3),y+Math.sign(v-y)*b];
}

export function planWestFrontages(world, ground) {
  if(world.id !== 'vaderland-33' || !world.vaderland?.quarter) return [];
  const roads = meridianStreets(world).filter(road => road.points.length>1 && road.width_m>0 &&
    overlaps(bounds(road.points),WARD,road.width_m+MAX_LENGTH));
  const streets = roads.filter(road => STREETS.has(road.name));
  const obstacles = world.obstacles.filter(o => overlaps(obstacleBounds(o),WARD,MAX_LENGTH));
  const occupied = [...roads.flatMap(roadSections), ...obstacles.map(footprint)]
    .filter(poly => overlaps(bounds(poly),WARD,MAX_LENGTH)).map(poly => ({poly,area:bounds(poly)}));
  const entries = [];
  const waterline = (world.harbour?.waterLevelM ?? 0)+2;
  for(const building of obstacles){
    const {id,kind,role,center:[x,y,z],half:[a,b,h]} = building;
    if(role !== 'architecture' || !/^(ward-\d+-\d+-\d+|courtyard-\d+)$/.test(id) ||
       !['box','cylinder'].includes(kind) || Math.min(a,b)<4) continue;
    for(const road of streets) for(let i=1;i<road.points.length;i++){
      const from = road.points[i-1], to = road.points[i];
      const wall = frontage(building,project([x,y],from,to));
      const lane = project(wall,from,to);
      const distance = Math.hypot(wall[0]-lane[0],wall[1]-lane[1]);
      const verge = road.width_m/2+ROAD_GAP;
      const length = distance-verge-WALL_GAP;
      if(length<4 || length>MAX_LENGTH) continue;
      const [dx,dy] = unit(lane,wall);
      const ahead = m => [lane[0]+dx*m,lane[1]+dy*m];
      const start = ahead(verge), end = ahead(distance-WALL_GAP);
      const landing = ahead(distance-WALL_GAP-2.4);
      const pieces = [strip(start,landing,1.8),strip(landing,end,3.5)];
      const elevation = ground.heightAt(...end);
      if(elevation<z-h-.6 || elevation>z+h-1) continue;
      if(!pieces.every(poly => clears(poly,occupied))) continue;
      if(![start,ahead(verge+length*.5),end].every(point =>
        ground.heightAt(...point)>waterline && ground.normalAt(...point).z>.987)) continue;
      entries.push({building:id,street:road.name,start,end,length,pieces});
    }
  }
  const links = [];
  for(const entry of entries.sort((a,b) => a.length-b.length)){
    if(links.some(link => link.building===entry.building)) continue;
    const previous = links.flatMap(link => link.pieces.map(poly => ({poly,area:bounds(poly)})));
    if(!entry.pieces.every(poly => clears(poly,previous))) continue;
    links.push(entry);
    if(links.length === MAX_LINKS) break;
  }
  return links;
}

export function buildWestFrontages(group, world, ground, uniforms, common) {
  const links = planWestFrontages(world,ground);
  if(!links.length) return null;
  const triangles = links.flatMap(link => link.pieces.flatMap((quad,style) => {
    const [a,b,c,d] = quad.map(([x,y]) => ({x,y,a:[style]}));
    return [[a,b,c],[a,c,d]];
  }));
  const {pos,nor,att} = ground.drapeTriangles(triangles,{offset:.018});
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
  geometry.setAttribute('normal',new THREE.Float32BufferAttribute(nor,3));
  geometry.setAttribute('setback',new THREE.Float32BufferAttribute(att,1));
  geometry.computeBoundingSphere();
  const material = new THREE.ShaderMaterial({uniforms,
    vertexShader:`
      attribute float setback;
      varying float pavedLanding;
      varying vec3 p,n;
      void main(){p=position;n=normal;pavedLanding=setback;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}
    `,
    fragmentShader:common+`
      varying float pavedLanding;
      void main(){
        vec2 tile=p.xy/vec2(1.25,.8);
        vec2 gap=abs(fract(tile+.5)-.5);
        float seam=1.-smoothstep(.012,.024,min(gap.x,gap.y));
        seam*=1.-smoothstep(.045,.32,max(fwidth(tile.x),fwidth(tile.y)));
        float tone=hash(floor(tile+.5));
        vec3 stone=mix(vec3(.103,.099,.090),vec3(.141,.130,.111),pavedLanding);
        stone*=mix(.87,1.13,tone)*(1.-.18*seam);
        stone*=mix(.82+.18*max(dot(normalize(n),sun),0.),.5,night);
        gl_FragColor=vec4(haze(stone),1.);
        #include <colorspace_fragment>
      }
    `});
  const mesh = new THREE.Mesh(geometry,material);
  mesh.name = 'West Exchange footpaths and setbacks';
  mesh.userData.frontages = links;
  group.add(mesh);
  return mesh;
}
