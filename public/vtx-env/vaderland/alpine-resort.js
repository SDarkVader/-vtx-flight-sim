import * as THREE from 'three';
import {heightfieldZ} from '../landscape.js';
import {ALPINE_ACCESS, ALPINE_LIFTS, ALPINE_ROUTES, ALPINE_ZONES} from './alpine-layout.js';

const RESORT_BOUNDS = [3720, 730, 1070, 1270];
const WARM = new THREE.Color('#ffc17f');
const COOL = new THREE.Color('#a8d6ff');

function resample(points, step) {
  const vertices = [];
  for (let i = 1; i < points.length; i++) {
    const [ax, ay] = points[i-1], [bx, by] = points[i];
    const count = Math.max(1, Math.ceil(Math.hypot(bx-ax, by-ay)/step));
    for (let j = 0; j < count; j++) vertices.push([ax+(bx-ax)*j/count, ay+(by-ay)*j/count]);
  }
  vertices.push(points.at(-1));
  return vertices;
}

function spanHeights(route,ground) {
  return route.points.map((point,i)=>ground(...point)+(route.heights?.[i]??(route.kind==='zipline'?42:20)));
}

// Measure the authored map line against the same triangles used for rendered terrain.
export function measureAlpineRoutes(ground, waterLevel=0) {
  return [...ALPINE_LIFTS, ...ALPINE_ROUTES].map(route => {
    const points = resample(route.points, 10);
    let distance = 0, steepest = 0;
    for (let i = 1; i < points.length; i++) {
      const a = points[i-1], b = points[i];
      const length = Math.hypot(b[0]-a[0], b[1]-a[1]);
      distance += length;
      steepest = Math.max(steepest, (ground(...a)-ground(...b))/length);
    }
    const start = ground(...points[0]), end = ground(...points.at(-1));
    const waypointHeights=route.kind==='zipline'||!route.kind?spanHeights(route,ground):
      route.points.map((point,i)=>ground(...point)+(route.heights?.[i]??0));
    let clearance;
    if(route.kind==='zipline'){
      const [z0,z1]=waypointHeights;
      clearance=Math.min(...points.map((point,i)=>z0+(z1-z0)*i/(points.length-1)
        -Math.max(waterLevel,ground(...point))));
    }
    return {...route, distance, start, end, steepest, clearance, highPoint:Math.max(...waypointHeights)};
  });
}

function groundLightMap(lamps) {
  const size = 256, values = new Float32Array(size*size*3);
  const [left, bottom, width, length] = RESORT_BOUNDS;
  for (const {point:[x,y], color, radius, strength} of lamps) {
    const minI = Math.max(0, Math.floor((x-radius-left)/width*size));
    const maxI = Math.min(size-1, Math.ceil((x+radius-left)/width*size));
    const minJ = Math.max(0, Math.floor((y-radius-bottom)/length*size));
    const maxJ = Math.min(size-1, Math.ceil((y+radius-bottom)/length*size));
    for (let j=minJ; j<=maxJ; j++) for (let i=minI; i<=maxI; i++) {
      const dx=(left+(i+.5)*width/size-x)/radius, dy=(bottom+(j+.5)*length/size-y)/radius;
      const light = Math.max(0, 1-dx*dx-dy*dy)**2 * strength, k=(j*size+i)*3;
      values[k]+=light*color.r; values[k+1]+=light*color.g; values[k+2]+=light*color.b;
    }
  }
  const pixels = new Uint8Array(size*size*4);
  for (let i=0; i<size*size; i++) {
    for (let j=0; j<3; j++) pixels[i*4+j]=Math.round(Math.min(1,values[i*3+j])*255);
    pixels[i*4+3]=255;
  }
  const texture = new THREE.DataTexture(pixels,size,size);
  texture.minFilter=texture.magFilter=THREE.LinearFilter;
  texture.needsUpdate=true;
  return texture;
}

function bulbs(lamps, ground, night) {
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(lamps.flatMap(({point:[x,y],height})=>[x,y,ground(x,y)+height]),3));
  g.setAttribute('lampColor',new THREE.Float32BufferAttribute(lamps.flatMap(({color})=>color.toArray()),3));
  const m=new THREE.ShaderMaterial({uniforms:{night},transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    vertexShader:`attribute vec3 lampColor; varying vec3 colour;
    void main(){vec4 eye=modelViewMatrix*vec4(position,1.); colour=lampColor;
      gl_Position=projectionMatrix*eye;gl_PointSize=clamp(15000./max(1.,-eye.z),2.6,10.);}`,
    fragmentShader:`uniform float night;varying vec3 colour;
    void main(){float r=length(gl_PointCoord-.5);float core=1.-smoothstep(.08,.22,r);
      float glow=(1.-smoothstep(.12,.50,r))*.34;
      gl_FragColor=vec4(colour,(core+glow)*min(1.,night*1.7));
      #include <colorspace_fragment>
    }`});
  const points=new THREE.Points(g,m);
  points.name='East Ridge piste and lodge lights';
  return points;
}

function lampPosts(lamps,ground) {
  const supports=lamps.flatMap(({point:[x,y],height})=>{
    const z=ground(x,y);
    return [new THREE.Vector3(x,y,z),new THREE.Vector3(x,y,z+height)];
  });
  return new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(supports),
    new THREE.LineBasicMaterial({color:'#737b80'}));
}

function station(root, point, ground, size, night) {
  const [x,y]=point, z=ground(x,y), [width,depth,height]=size;
  const lodge=new THREE.Mesh(new THREE.BoxGeometry(width,depth,height),
    new THREE.MeshBasicMaterial({color:'#785a47'}));
  lodge.position.set(x,y,z+height*.26);
  const roof=new THREE.Mesh(new THREE.CylinderGeometry(0,1,1,4,1),new THREE.MeshBasicMaterial({color:'#343937'}));
  roof.rotation.set(Math.PI/2,Math.PI/4,0); roof.scale.set(width*.76, height*.55, depth*.76);
  roof.position.set(x,y,z+height*.96);
  const windows=new THREE.Mesh(new THREE.PlaneGeometry(width*.77,height*.26),new THREE.MeshBasicMaterial({color:'#aa7751',side:THREE.DoubleSide}));
  windows.rotation.x=Math.PI/2;windows.position.set(x,y-depth/2-.04,z+height*.40);
  root.add(lodge,roof,windows);
  return () => windows.material.color.set(night.value>.01 ? '#ffd193' : '#779393');
}

function span(root,route,ground) {
  const [a,b]=route.points, length=Math.hypot(b[0]-a[0],b[1]-a[1]);
  const [z0,z1]=spanHeights(route,ground);
  const samples=Math.max(10,Math.ceil(length/22));
  const line=[], legs=[];
  for (let i=0;i<=samples;i++) {
    const f=i/samples, x=a[0]+(b[0]-a[0])*f, y=a[1]+(b[1]-a[1])*f;
    const groundZ=ground(x,y), lineZ=z0+(z1-z0)*f;
    const z=route.kind==='zipline'?lineZ:Math.max(lineZ,groundZ+7);
    line.push(new THREE.Vector3(x,y,z));
    if (i===0 || i===samples || (route.kind!=='zipline' && i%6===0))
      legs.push(new THREE.Vector3(x,y,groundZ),new THREE.Vector3(x,y,z));
  }
  const wire=new THREE.Line(new THREE.BufferGeometry().setFromPoints(line),
    new THREE.LineBasicMaterial({color:route.color ?? '#768a95',transparent:true,opacity:.56}));
  wire.name=route.name+' survey line';
  const pylons=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(legs),
    new THREE.LineBasicMaterial({color:'#8c8e89'}));
  root.add(wire,pylons);
}

export function buildAlpineResort(group, world, night) {
  const ground=(x,y)=>heightfieldZ(world,x,y);
  const root=new THREE.Group();root.name='East Ridge Ski Resort';group.add(root);
  const lamps=[];
  const place=(point,color,radius,strength,height=6)=>lamps.push({point,color,radius,strength,height});
  for (const point of resample(ALPINE_ACCESS,32)) place(point,WARM,34,.22,4);
  for (const route of ALPINE_ROUTES.filter(route=>route.width)) {
    const path=resample(route.points,43);
    path.forEach(([x,y],i)=>{
      const [px,py]=path[Math.min(i+1,path.length-1)];
      const dx=px-x,dy=py-y,side=(i%2===0 ? -1 : 1)*route.width*.50;
      const length=Math.hypot(dx,dy)||1;
      place([x-dy/length*side,y+dx/length*side],COOL,47,.28,7);
    });
  }
  const windows=[];
  ALPINE_ZONES.slice(0,3).forEach(({point:[x,y]},i)=>{
    windows.push(station(root,[x,y],ground,i===0?[28,16,8]:[19,12,7],night));
    for (const [dx,dy] of [[-20,-12],[24,-11],[-19,15],[21,16]]) place([x+dx,y+dy],WARM,41,.45);
    if (i===0) for (const [dx,dy] of [[-43,13],[42,17],[-11,-36]]) {
      windows.push(station(root,[x+dx,y+dy],ground,[16,12,6],night));
      place([x+dx,y+dy-8],WARM,33,.43,4);
    }
  });
  for (const route of [...ALPINE_LIFTS,...ALPINE_ROUTES.filter(route=>route.kind==='zipline')]) span(root,route,ground);
  const lights=bulbs(lamps,ground,night);root.add(lights,lampPosts(lamps,ground));
  for(const {id,point:[x,y]} of ALPINE_ZONES.slice(3,6)){
    const marker=new THREE.Mesh(new THREE.ConeGeometry(3.4,9,4),
      new THREE.MeshBasicMaterial({color:id==='east-launch'?'#acb6dc':'#dfa668'}));
    marker.rotation.x=Math.PI/2;marker.position.set(x,y,ground(x,y)+4.5);
    marker.name=id+' survey marker';root.add(marker);
  }
  const texture=groundLightMap(lamps);
  const zones=ALPINE_ZONES.map(zone=>({...zone,elevation:ground(...zone.point)}));
  let lit;
  return {zones,routes:measureAlpineRoutes(ground,world.harbour?.waterLevelM),texture,bounds:RESORT_BOUNDS,
    view(point,distance=110){
      const [x,y]=point, height=ground(x,y);
      return {eye:[x-distance*.6,y-distance,Math.max(height,ground(x-distance*.6,y-distance))+distance*.72],
        target:[x,y,height+5]};
    },
    update(){
      const active=night.value>.01;
      if(active===lit)return;
      lit=active;lights.visible=active;windows.forEach(show=>show());
    },
    dispose(){texture.dispose();}};
}
