import * as THREE from 'three';

export function controlDesk(group,runway){
  const c=document.createElement('canvas');c.width=720;c.height=320;const g=c.getContext('2d');
  const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;
  const screen=new THREE.Mesh(new THREE.PlaneGeometry(1.51,.52),new THREE.MeshBasicMaterial({map:t}));
  screen.position.set(116,-231.63,91.147);group.add(screen);
  let prior='';
  return xy=>{
    const key=xy?xy.map(n=>Math.round(n/5)).join('/'):'idle';
    if(key===prior)return;prior=key;
    g.fillStyle='#081b23';g.fillRect(0,0,720,320);g.strokeStyle='#214b54';g.lineWidth=2;
    for(const r of [32,71,111,151]){g.beginPath();g.ellipse(267,169,r,r,0,0,Math.PI*2);g.stroke();}
    for(let i=0;i<720;i+=40){g.fillStyle='#244851';g.fillRect(i,0,1,320);}
    g.fillStyle='#88caca';g.fillRect(85,166,365,6);g.font='19px monospace';g.fillText('08',55,172);g.fillText('26',461,172);
    g.fillStyle='#b6ddda';g.font='bold 23px monospace';g.fillText('MERIDIAN TOWER',18,32);
    g.fillStyle='#edae57';g.font='bold 18px monospace';g.fillText('APPROACH',510,36);g.fillText('R. WINSTON',510,69);
    g.fillStyle='#9eb8b6';g.font='16px monospace';g.fillText('RWY 08 / 26',510,136);g.fillText((runway.length/1000).toFixed(1)+' KM',510,164);
    if(xy){const x=267+xy[0]*.045,y=169-xy[1]*.045;g.fillStyle='#91ffd3';g.fillRect(x-4,y-4,8,8);}
    t.needsUpdate=true;
  };
}

export function architecturalLights(group,w){
  const positions=[],colors=[],size=[];
  function glow(x,y,z,tint,r){positions.push(x,y,z);new THREE.Color(tint).toArray(colors,colors.length);size.push(r);}
  for(const door of w.vaderland.operations.annex.doors){
    const [cx,y,z]=door.center,sign=door.id==='west'?-1:1,x=cx+sign*.655;
    for(let i=0;i<100;i++){const a=i*Math.PI/50;
      glow(x,y+13.45*Math.cos(a),z+13.45*Math.sin(a),i%25===0?'#80e4dd':'#ffb455',i%25===0?.58:.24);}
  }
  for(let x=971;x<1032;x+=5)for(const s of [-1,1]){
    glow(x,-325+s*14.26,18+4.35,'#f7a24b',.48);glow(x,-325+s*13.97,18-5.30,'#70b7cf',.32);
  }
  for(let x=970;x<=1030;x+=3.75){glow(x,-350.37,10.28,'#eeb36a',.38);glow(x,-287.72,10.34,'#e6af6e',.33);}
  for(let x=74;x<=150;x+=9){const a=(x-74)*Math.PI/38;glow(116+10.97*Math.cos(a),-235+10.97*Math.sin(a),95.45,'#85e5e0',.50);}
  if(w.vaderland.civic_district){
    const [x,y,z]=w.vaderland.civic_district.plaza;
    for(let i=0;i<96;i++){const a=i*Math.PI/48;glow(x+18.5*Math.cos(a),y+18.5*Math.sin(a),z+.76,'#ffb960',.27);}
    for(const i of [-1,1])for(let j=-4;j<=4;j++){glow(x+j*10.,y+i*46.,z+.075,'#e8a55d',.39);}
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.setAttribute('shade',new THREE.Float32BufferAttribute(colors,3));g.setAttribute('lampRadius',new THREE.Float32BufferAttribute(size,1));
  const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    vertexShader:`attribute vec3 shade;attribute float lampRadius;varying vec3 rgb;
      void main(){rgb=shade;vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;
        gl_PointSize=clamp(1.7+lampRadius*1000./max(1.,-p.z),1.,33.);}`,
    fragmentShader:`varying vec3 rgb;void main(){float d=length(gl_PointCoord-.5)*2.;if(d>1.)discard;
      float glow=exp(-d*d*5.5);gl_FragColor=vec4(rgb*1.67,glow*.63);}`});
  group.add(new THREE.Points(g,m));
}
