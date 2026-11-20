import * as THREE from 'three';
import {marketPedestrians} from './pedestrians.js';
import {marketPlanting} from './optics.js';
import {avenueMaterial,avenueParcel,parcelSeed,wallPerimeter} from './city-facades.js';

const styles={shopfront:0,apartments:1,workrooms:2,masonry:3,galleryhouse:4,officeglass16:5,roof16:6,awning16:7,citybark16:8,canopy16:9,fixture16:10};

function shell(o){
  if(o.kind==='mesh')return {vertices:o.vertices,faces:o.faces};
  const [a,b,c]=o.half, count=o.kind==='box'?4:32, vertices=[];
  for(const z of [-c,c])for(let j=0;j<count;j++){
    if(count===4){const corner=[[-a,-b],[a,-b],[a,b],[-a,b]][j];vertices.push([...corner,z]);}
    else{const t=2*Math.PI*j/count;vertices.push([a*Math.cos(t),a*Math.sin(t),z]);}
  }
  const faces=[];
  for(let i=0;i<count;i++){
    const j=(i+1)%count;faces.push([i,j,count+j],[i,count+j,count+i]);
    if(i>0&&i<count-1)faces.push([0,i+1,i],[count,count+i,count+i+1]);
  }
  return {vertices,faces};
}

function cityMaterial(uniforms,common){
  return new THREE.ShaderMaterial({uniforms,side:THREE.DoubleSide,
    vertexShader:`attribute vec4 building;attribute vec2 metres;varying vec4 use;varying vec2 wall;
      varying vec3 p,n;void main(){p=position;n=normal;use=building;wall=metres;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`,
    fragmentShader:'uniform float sceneryClock;uniform sampler2D streetFronts,alloyColor,slateColor;varying vec4 use;varying vec2 wall;'+common+`
      vec3 frontage(float slot,vec2 mapped,vec2 parallax){
        vec2 tile=vec2(mod(slot,2.),1.-floor(slot/2.))*.5;
        vec2 uv=tile+.003+fract(mapped+parallax)*.494;
        return textureGrad(streetFronts,uv,dFdx(mapped)*.494,dFdy(mapped)*.494).rgb;
      }
      float line(float v,float period,float width){
        float dist=abs(fract(v/period+.5)-.5)*period;
        return (1.-smoothstep(width,width+max(.015,fwidth(v)),dist))*(1.-smoothstep(period*.42,period,fwidth(v)));
      }
      void main(){
        vec3 N=normalize(n),V=normalize(cameraPosition-p);if(!gl_FrontFacing)N=-N;
        float kind=use.x,tenant=use.y,seed=use.z,base=use.w;
        float h=p.z-base,key=max(dot(N,sun),0.);
        vec3 c;vec3 sky=skySample(daySky,reflect(-V,N));float fres=pow(1.-abs(dot(V,N)),3.);
        if(N.z>.83||kind>5.5){
          vec2 tex=N.z>.7?p.xy/3.1:wall/3.1;
          vec3 grain=texture2D(slateColor,tex).rgb;
          if(kind>9.5)c=vec3(.026,.038,.04)+texture2D(alloyColor,tex).rgb*.29;
          else if(kind>8.5){vec3 fabric=mix(vec3(.035,.24,.28),vec3(.48,.16,.054),step(.5,seed));
            c=fabric*(.74+.41*key)+sky*.12+vec3(.11,.073,.032)*night;}
          else if(kind>7.5)c=vec3(.095,.063,.038)*(.81+.52*grain.r);
          else if(kind>6.5)c=mix(vec3(.17,.12,.076),vec3(.24,.28,.30),seed)*(.71+.37*key)+sky*.19;
          else{float seam=max(line(tex.x,1.6,.012),line(tex.y,1.6,.012));
            c=(vec3(.15,.18,.20)+grain*.42)*(.80+.33*key)*(1.-seam*.24);
            c=mix(c,c*.32+sky*.13,night);}
        }else{
          bool shops=kind<.5 || (h<7.7&&kind<4.6);
          float choice=shops?mod(floor(tenant),2.):(kind==1.||kind==3.||tenant>2.5?3.:2.);
          vec2 repeatSize=vec2(shops?16.7:17.85,shops?7.85:7.06);
          vec2 uv=vec2(wall.x,h)/repeatSize+vec2(floor(seed*5.)*.2,0.);
          vec3 front=frontage(choice,uv,vec2(0.));
          float refl=dot(front,vec3(.29,.56,.15));
          vec2 parallax=vec2(dot(V,vec3(-N.y,N.x,0.)),V.z)*.008;
          vec3 inside=frontage(choice,uv,parallax);
          float pane=smoothstep(.06,.23,refl);
          vec3 lit=mix(front,inside,pane*.42);
          vec3 tint=seed<.32?mix(vec3(.40,.55,.66),vec3(.61,.75,.78),seed*3.):seed<.63?vec3(.77,.69,.57):seed<.82?vec3(.78,.85,.91):vec3(.60,.47,.42);
          float floors=line(h,3.53,.075),upright=line(wall.x,3.57,.042);
          float rooms=hash(vec2(floor(wall.x/7.15)+tenant,floor(h/3.53)+seed));
          vec3 practical=mix(vec3(.65,.84,1.03),vec3(1.38,1.02,.64),rooms*.78+.16);
          vec3 baseDay=lit*(1.15+.64*key)*tint+sky*(.026+fres*.105);
          vec2 bay=fract(uv*vec2(5.,2.));
          float opening=smoothstep(.11,.18,bay.x)*(1.-smoothstep(.85,.92,bay.x))*
                        smoothstep(.11,.22,bay.y)*(1.-smoothstep(.83,.93,bay.y));
          float floorTenant=hash(vec2(floor(wall.x/17.85),floor(h/7.06))+floor(seed*941.));
          float occupancy=shops?.94:mix(.12,.91,smoothstep(.22,.76,floorTenant*.63+rooms*.37));
          vec3 baseNight=lit*tint*(shops?.33:.17)+vec3(.014,.024,.037);
          baseNight+=opening*(lit*(shops?1.78:1.48)*practical*occupancy+sky*(.14+.32*fres));
          baseNight+=vec3(.033,.059,.081)*fres*(1.-opening);
          c=mix(baseDay,baseNight,night);
          if(kind==5.){
            vec3 reflected=sky*(.41+.33*fres)+vec3(.033,.054,.079);
            c=mix(c,reflected,.30+.24*(1.-rooms));
            vec3 crownTint=mix(vec3(.20,.63,.74),vec3(.82,.46,.26),step(.58,seed));
            c+=crownTint*line(wall.x+seed*5.,23.,.084)*(.40+.41*night);
            c+=vec3(.12,.17,.22)*line(wall.x,7.15,.080);
            float liftHeight=10.+(1.-abs(fract(sceneryClock/(62.+22.*seed)+seed)*2.-1.))*(54.+seed*33.);
            float lift=exp(-abs(h-liftHeight)*.78)*(1.-smoothstep(.5,1.01,abs(wall.x-3.)));
            c+=vec3(.51,.65,.76)*lift*night;
          }
          c=mix(c,c*.63+vec3(.048,.064,.077)*mix(1.,.62,night),max(floors,upright)*.68);
          if(shops)c+=mix(vec3(.88,.46,.17),vec3(.24,.68,.73),step(.68,seed))*line(h-4.22,100.,.042)*(.75+.41*night);
        }
        gl_FragColor=vec4(haze(c),1.);
        #include <colorspace_fragment>
      }`});
}

export function buildMarket(group,w,ground,uniforms,common){
  const data=w.vaderland.quarter,retained=new Set(data.retained),batches=new Map();
  const material=cityMaterial(uniforms,common),v=new THREE.Vector3(),e=new THREE.Vector3(),n=new THREE.Vector3();
  const facades=w.vaderland.city_lights?avenueMaterial(uniforms,common):null;
  const parcels=new Map();
  if(facades)for(const o of w.obstacles){
    const id=avenueParcel(o);if(!id)continue;
    if(!parcels.has(id))parcels.set(id,{seed:parcelSeed(id),roof:-Infinity,datum:Infinity});
    const parcel=parcels.get(id);
    parcel.roof=Math.max(parcel.roof,o.center[2]+o.half[2]);
    parcel.datum=Math.min(parcel.datum,o.datum_m??(o.center[2]-o.half[2]));
  }
  for(const o of w.obstacles){
    const parcel=facades?parcels.get(avenueParcel(o)):undefined;
    if(!parcel&&!o.city&&!retained.has(o.id))continue;
    const [x,y,z]=o.center,cell=parcel&&!o.city&&!retained.has(o.id)?920:230;
    const tile=(parcel?'facade/':'market/')+Math.floor(x/cell)+'/'+Math.floor(y/cell);
    if(!batches.has(tile))batches.set(tile,{pos:[],norm:[],wall:[],info:[],heights:[],spans:[],material:parcel?facades:material});
    const batch=batches.get(tile),{vertices,faces}=shell(o);
    const kind=styles[o.skin]??(o.half[2]<12&&(!parcel||Math.abs(z-o.half[2]-parcel.datum)<1)?0:5);
    const seed=parcel?.seed??Math.abs(Math.sin(x*.741+y*.274)*937.333)%1,tenant=o.tenancy??Math.floor(seed*4);
    const base=parcel?.datum??o.datum_m??ground.heightAt(x,y),corners=vertices.map(p=>new THREE.Vector3(...p));
    const perimeter=parcel?wallPerimeter(vertices):null;
    for(const face of faces){
      const [a,b,c]=face.map(i=>corners[i]);n.crossVectors(v.subVectors(b,a),e.subVectors(c,a)).normalize();
      const normal=n.toArray(),horizontal=Math.hypot(n.x,n.y),round=o.kind==='mesh'||o.kind==='cylinder';
      // Unwrap the perimeter continuously across curved and chamfered bays. Fix the 2π seam locally.
      const period=perimeter?.length??Math.PI*2;
      const raw=perimeter?face.map(i=>perimeter.u[i]):face.map(i=>Math.atan2(corners[i].y/o.half[1],corners[i].x/o.half[0]));
      const seam=Math.max(...raw)-Math.min(...raw)>period/2;
      for(const [j,i] of face.entries()){
        const p=corners[i],angle=raw[j]+(seam&&raw[j]<0?Math.PI*2:0);
        const along=perimeter?raw[j]+(seam&&raw[j]<period/2?period:0):
          round?angle*(o.half[0]+o.half[1])*.5:Math.abs(n.x)>Math.abs(n.y)?p.y:p.x;
        if(parcel)batch.heights.push(parcel.roof-base);
        batch.pos.push(p.x+x,p.y+y,p.z+z);batch.norm.push(...normal);
        batch.wall.push(horizontal>.05?along:p.x,p.z+z-base);batch.info.push(kind,tenant,seed,base);
      }
    }
    batch.spans.push({end:batch.pos.length/9,id:o.id});
  }
  for(const b of batches.values()){
    const geom=new THREE.BufferGeometry();
    for(const [name,values,size] of [['position',b.pos,3],['normal',b.norm,3],['metres',b.wall,2],['building',b.info,4]])
      geom.setAttribute(name,new THREE.Float32BufferAttribute(values,size));
    if(b.heights.length)geom.setAttribute('roofHeight',new THREE.Float32BufferAttribute(b.heights,1));
    geom.computeBoundingSphere();const node=new THREE.Mesh(geom,b.material);node.name='Meridian occupied block';
    node.userData.surveySpans=b.spans;group.add(node);
  }
  const pavement=ground.drapeTriangles(data.paving.map(tri=>tri.map(([x,y])=>({x,y,a:[]}))),{offset:.033});
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(pavement.pos,3));
  geo.setAttribute('normal',new THREE.Float32BufferAttribute(pavement.nor,3));
  const paving=new THREE.ShaderMaterial({uniforms,side:THREE.DoubleSide,
    vertexShader:'varying vec3 p,n;void main(){p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}',
    fragmentShader:'uniform sampler2D slateColor;'+common+`void main(){
      vec2 uv=p.xy/2.4;float grain=texture2D(slateColor,uv).r;
      vec2 seam=abs(fract(p.xy/vec2(1.8,.88)+.5)-.5);
      float joints=1.-smoothstep(.008,.027,min(seam.x,seam.y));vec3 V=normalize(cameraPosition-p);
      vec3 c=(vec3(.155,.167,.174)+grain*vec3(.30,.27,.24))*(1.-.29*joints);
      c*=mix(vec3(1.),vec3(.41,.44,.48),night);
      c+=skySample(daySky,reflect(-V,normalize(n)))*pow(1.-abs(V.z),3.)*.23;
      gl_FragColor=vec4(haze(c),1.);
      #include <colorspace_fragment>
    }`});
  const pavementMesh=new THREE.Mesh(geo,paving);pavementMesh.name='Meridian footways';group.add(pavementMesh);
  shopSigns(group,data.signs);
  dressMarket(group,data.stalls,uniforms);
  const leaves=new THREE.ShaderMaterial({uniforms,side:THREE.DoubleSide,
    vertexShader:`varying vec2 st;varying vec3 p,n;varying float distanceToTree;
      void main(){st=uv;vec3 foot=instanceMatrix[3].xyz;float h=instanceMatrix[2].z;
        vec3 d=cameraPosition-foot;distanceToTree=length(d);vec3 right=normalize(vec3(-d.y,d.x,.00001));
        p=foot+right*(uv.x-.5)*h*.96+vec3(0,0,h*uv.y);n=vec3(0,0,1.);
        gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`,
    fragmentShader:'uniform sampler2D tree1;varying vec2 st;varying float distanceToTree;'+common+`
      void main(){if(distanceToTree<151.)discard;vec4 leaf=texture2D(tree1,st);if(leaf.a<.43)discard;
        gl_FragColor=vec4(haze(leaf.rgb*mix(vec3(.88,1.,.85),vec3(.43,.52,.45),night)),1.);
        #include <colorspace_fragment>
      }`});
  const planting=marketPlanting(w),trees=new THREE.InstancedMesh(new THREE.PlaneGeometry(1,1),leaves,planting.length),object=new THREE.Object3D();
  planting.forEach((t,i)=>{object.position.set(...t.xy,t.z);object.scale.set(t.h,t.h,t.h);object.updateMatrix();trees.setMatrixAt(i,object.matrix);});
  trees.computeBoundingSphere();group.add(trees);
  const pedestrians=marketPedestrians(group,data.people);
  const practicals=Array.from({length:3},()=>{const lamp=new THREE.PointLight(0xffd89a,240,28,2);group.add(lamp);return lamp;});
  let lastPosition;
  return {update(cam,t){
    pedestrians.update(cam,t);
    if(!lastPosition||cam.position.distanceToSquared(lastPosition)>36){
      lastPosition=cam.position.clone();
      const near=data.lots.map(l=>({l,d:(l.door[0]-cam.position.x)**2+(l.door[1]-cam.position.y)**2+(l.datum+3-cam.position.z)**2})).sort((a,b)=>a.d-b.d);
      practicals.forEach((lamp,i)=>{const {l,d}=near[i];lamp.visible=d<58*58;
        lamp.position.set(l.door[0]+l.front[0]*1.2,l.door[1]+l.front[1]*1.2,l.datum+3.71);});
    }
  }};
}

function dressMarket(group,stalls,uniforms){
  const bulbs=[],wire=[],goods=[],steam=[];
  for(const [j,s] of stalls.entries()){
    const at=(u,v,h)=>new THREE.Vector3(s.xy[0]+s.axis[0]*u+s.front[0]*v,s.xy[1]+s.axis[1]*u+s.front[1]*v,s.z+h);
    let last;
    for(let i=0;i<=20;i++){
      const f=i/20,p=at(-2.42+4.84*f,1.39,3.21+.17*f-.26*Math.sin(f*Math.PI));
      if(last)wire.push(...last.toArray(),...p.toArray());last=p;
      if(i%2===0)bulbs.push(p);
    }
    for(let i=0;i<31;i++){
      const u=-2.1+(i%11)*.388,v=.19+Math.floor(i/11)*.33;
      const p=at(u,v,1.21);
      const rows=[['#a66f36','#c68b4c','#87532d'],['#d57787','#8f86c0','#d0b75a'],['#c9924c','#c48245','#8e552e'],['#aa5d43','#848f64','#cfaa70']];
      goods.push([p,new THREE.Vector3(.15,.112,s.kind===1?.21:.096),rows[s.kind][i%3]]);
    }
    if(j%3===0)steam.push(at(1.41,.83,1.41));
  }
  const line=new THREE.BufferGeometry();line.setAttribute('position',new THREE.Float32BufferAttribute(wire,3));
  group.add(new THREE.LineSegments(line,new THREE.LineBasicMaterial({color:0x4e403a})));
  const object=new THREE.Object3D();
  const bulbsMesh=new THREE.InstancedMesh(new THREE.SphereGeometry(.053,8,6),new THREE.MeshBasicMaterial({color:new THREE.Color(2.12,1.12,.44)}),bulbs.length);
  bulbs.forEach((p,i)=>{object.position.copy(p);object.updateMatrix();bulbsMesh.setMatrixAt(i,object.matrix);});group.add(bulbsMesh);
  const stock=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),new THREE.MeshStandardMaterial({roughness:.68}),goods.length);
  goods.forEach(([p,scale,tint],i)=>{object.position.copy(p);object.scale.copy(scale);object.rotation.z=i*2.21;object.updateMatrix();stock.setMatrixAt(i,object.matrix);stock.setColorAt(i,new THREE.Color(tint));});
  group.add(stock);
  const positions=[],stages=[];
  for(const p of steam)for(let i=0;i<5;i++){positions.push(...p.toArray());stages.push(i/5);}
  const cloud=new THREE.BufferGeometry();cloud.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  cloud.setAttribute('phase',new THREE.Float32BufferAttribute(stages,1));
  group.add(new THREE.Points(cloud,new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,
    vertexShader:`uniform float sceneryClock;attribute float phase;varying float alpha;void main(){
      float f=fract(sceneryClock*.32+phase);vec3 p=position+vec3(.14*f+.077*sin(f*5.),.07*sin(f*3.),f*.91);
      vec4 eye=viewMatrix*vec4(p,1.);gl_Position=projectionMatrix*eye;gl_PointSize=clamp((45.+80.*f)/max(1.,-eye.z),1.,32.);
      alpha=.105*sin(f*3.14159);}`,fragmentShader:`varying float alpha;void main(){float r=length(gl_PointCoord-.5)*2.;
      if(r>1.)discard;gl_FragColor=vec4(.74,.71,.65,alpha*(1.-smoothstep(.0,1.,r)));}` })));
}

function shopSigns(group,signs){
  const names=[...new Set(signs.map(s=>s.name))],sheet=document.createElement('canvas');
  sheet.width=1024;sheet.height=128*names.length;const ctx=sheet.getContext('2d');
  names.forEach((name,i)=>{
    ctx.fillStyle=['#17302f','#282735','#473129','#243942','#252b32','#463c2c'][i%6];
    ctx.fillRect(0,128*i,1024,128);ctx.fillStyle='#ccb47d';ctx.fillRect(20,128*i+12,984,2);
    ctx.textAlign='center';ctx.fillStyle='#f8e5bd';ctx.font='600 65px system-ui';ctx.fillText(name,512,128*i+87,950);
  });
  const texture=new THREE.CanvasTexture(sheet);texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=8;
  const positions=[],uv=[];
  for(const s of signs){
    const [x,y]=s.xy,[nx,ny]=s.front,z=s.height_m,j=names.indexOf(s.name);
    for(const [u,v] of [[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]]){
      positions.push(x-ny*(u-.5)*s.width_m+nx*.055,y+nx*(u-.5)*s.width_m+ny*.055,z+(v-.5)*1.18);
      uv.push(u,(names.length-j-1+v)/names.length);
    }
  }
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  geo.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2));
  group.add(new THREE.Mesh(geo,new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide})));
}
