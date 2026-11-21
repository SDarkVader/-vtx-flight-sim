// Vaderland 33: ward neighbourhoods, mini tracks, rooftop landing zones and mission hoops.
// Houses, trees and ramps draw exactly the native solids (same boxes, cylinders and hulls);
// gardens are ground colour only; zone markings and hoops carry no collision.
import * as THREE from 'three';

const PALETTE=['#c8553d','#2f8f83','#e0a43a','#8e6cc4','#e8e1d2','#4f7cac','#d97a9a','#6f9e4f','#b9794f','#3d4b6b'].map(c=>new THREE.Color(c));
const STYLE={terrace:0,cube:1,'cube-upper':1,tower:2,silo:3};
const isOurs=id=>/^nb[trs]?-/.test(id);
export const neighbourhoodSolid=isOurs;

export function buildNeighbourhoods(group,w,uniforms,common,ground){
  const plan=w.vaderland.neighbourhoods;if(!plan)return null;
  const root=new THREE.Group();root.name='Meridian Rooftop Quarter';group.add(root);
  const solids=w.obstacles.filter(o=>isOurs(o.id));
  root.add(...houses(solids,uniforms,common));
  root.add(...trees(solids));
  const r=ramps(solids,uniforms,common);if(r)root.add(r);
  if(ground)root.add(gardens(plan.gardens,ground,uniforms,common));
  const zones=landingZones(plan.pads,uniforms);root.add(zones.group);
  const missions=missionMarkers(w.vaderland.missions||[],plan.pads,uniforms);root.add(missions.group);
  return {update(seconds,timing){zones.time.value=seconds;missions.update(seconds,timing);}};
}

// ---- houses -----------------------------------------------------------------------------
function houses(solids,uniforms,common){
  const out=[];
  for(const round of [false,true]){
    const list=solids.filter(o=>o.role==='house'&&(o.kind==='cylinder')===round);
    if(!list.length)continue;
    const geometry=round?new THREE.CylinderGeometry(.5,.5,1,28).rotateX(Math.PI/2):new THREE.BoxGeometry();
    const g=new THREE.InstancedBufferGeometry().copy(geometry);g.instanceCount=list.length;
    const at=(n,size,f)=>g.setAttribute(n,new THREE.InstancedBufferAttribute(new Float32Array(list.flatMap(f)),size));
    at('centre',3,o=>o.center);at('dims',3,o=>o.half.map(v=>v*2));
    at('look',4,o=>{const s=(o.palette??0)/1048576;return [STYLE[o.style]??0,s,o.units??1,(o.front?.[0]??0)*2+(o.front?.[1]??0)];});
    const m=new THREE.ShaderMaterial({uniforms,vertexShader:`
      attribute vec3 centre,dims;attribute vec4 look;varying vec4 kind;varying vec3 local,size;varying vec3 p;varying vec3 n;
      void main(){
        local=position;size=dims;kind=look;
        p=centre+position*dims;n=normal;
        gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);
      }`,fragmentShader:common+`
      uniform float clock;varying vec4 kind;varying vec3 local,size;
      vec3 pal(float i){
        i=mod(floor(i),10.);
        return i<1.?vec3(.60,.22,.14):i<2.?vec3(.11,.42,.38):i<3.?vec3(.72,.50,.15):i<4.?vec3(.40,.28,.60):i<5.?vec3(.78,.75,.68)
          :i<6.?vec3(.22,.36,.55):i<7.?vec3(.72,.38,.48):i<8.?vec3(.32,.48,.24):i<9.?vec3(.56,.35,.22):vec3(.17,.21,.32);
      }
      void main(){
        vec3 N=normalize(n);float style=kind.x,seed=kind.y,units=max(1.,kind.z);
        bool roof=N.z>.7;
        float horiz=abs(N.x)>abs(N.y)?(local.y+.5)*size.y:(local.x+.5)*size.x;
        float span=abs(N.x)>abs(N.y)?size.y:size.x;
        if(style>2.5){float a=atan(local.y,local.x);horiz=(a/6.2831853+.5)*3.14159*size.x;span=3.14159*size.x;}
        float h=(local.z+.5)*size.z;
        float unit=floor(horiz/span*units*step(style,.5)+0.);
        float hue=floor(seed*97.)+unit*3.+(style>.5?style*2.:0.);
        vec3 wall=pal(hue)*(.82+.30*hash(vec2(unit,seed*31.)));
        float light=max(dot(N,sun),0.);
        vec3 c;
        if(roof){
          float r=hash(vec2(seed*71.,unit));
          vec2 q=(local.xy+.5)*size.xy;
          vec3 deck=r<.30?vec3(.10,.20,.07)*(.8+.4*fbm(q*.6)):r<.55?vec3(.42,.16,.09):r<.80?vec3(.05,.07,.11)+vec3(.05,.07,.10)*step(.85,fract(q.x*.8)):vec3(.40,.38,.34);
          c=deck*(vec3(.30,.36,.50)+vec3(1.15,.95,.75)*light);
        }else{
          float floorH=style>1.5&&style<2.5?3.1:2.9;
          vec2 cell=vec2(horiz/2.6,(h-.4)/floorH);
          vec2 f=fract(cell);vec2 id=floor(cell);
          float win=step(.22,f.x)*step(f.x,.78)*step(.28,f.y)*step(f.y,.78)*step(.5,id.y)*step(h,size.z-.6);
          float sep=step(style,.5)*(1.-smoothstep(.0,.25,abs(fract(horiz/span*units)-.0)*span/units));
          float lit=step(.45,hash(id+seed*13.+unit));
          vec3 glass=mix(vec3(.05,.07,.10),vec3(1.,.66,.32)*1.6,lit*night)+vec3(.10,.12,.16)*(1.-night);
          c=wall*(vec3(.32,.36,.48)+vec3(1.1,.92,.72)*light);
          c=mix(c,glass,win*.92);
          c=mix(c,vec3(.03,.03,.04),sep*.85);
          float door=step(abs(fract(horiz/span*units)-.5)*span/units,.6)*step(h,2.2)*step(.5,abs(N.x)+abs(N.y));
          c=mix(c,pal(hue+5.)*.35,door*.9*step(style,.5));
        }
        gl_FragColor=vec4(haze(c),1.);
        #include <colorspace_fragment>
      }`});
    const mesh=new THREE.Mesh(g,m);mesh.frustumCulled=false;mesh.name=round?'Round houses':'Ward houses';
    mesh.userData.sceneryIds=list.map(o=>o.id);out.push(mesh);
  }
  return out;
}

// ---- trees: trunk plus a lumpy rounded crown, many greens and a few blossom trees ----------
function trees(solids){
  const list=solids.filter(o=>o.role==='broadleaf');
  if(!list.length)return [];
  const trunkG=new THREE.CylinderGeometry(.22,.34,1,6).rotateX(Math.PI/2);
  const crownG=new THREE.IcosahedronGeometry(1,1);
  const pos=crownG.attributes.position;
  for(let i=0;i<pos.count;i++){const v=new THREE.Vector3().fromBufferAttribute(pos,i);v.multiplyScalar(1+.16*Math.sin(v.x*5.1+v.y*3.7)*Math.cos(v.z*4.3));pos.setXYZ(i,v.x,v.y,v.z);}
  crownG.computeVertexNormals();
  const trunks=new THREE.InstancedMesh(trunkG,new THREE.MeshStandardMaterial({color:0x4a3a2c,roughness:1}),list.length);
  const crowns=new THREE.InstancedMesh(crownG,new THREE.MeshStandardMaterial({roughness:.95,flatShading:true}),list.length);
  const m=new THREE.Matrix4(),q=new THREE.Quaternion(),s=new THREE.Vector3(),v=new THREE.Vector3(),c=new THREE.Color();
  list.forEach((o,i)=>{
    const [x,y,z]=o.center,[r,,hz]=o.half,bottom=z-hz,top=z+hz,R=o.crown_radius_m??r*2;
    v.set(x,y,bottom+(top-bottom)*.3);s.set(1,1,(top-bottom)*.6);m.compose(v,q,s);trunks.setMatrixAt(i,m);
    v.set(x,y,top-R*.75);s.set(R,R,R*.95);m.compose(v,q.setFromAxisAngle(new THREE.Vector3(0,0,1),i*1.7),s);crowns.setMatrixAt(i,m);
    q.identity();crowns.setColorAt(i,c.set(o.color));
  });
  trunks.name='Ward tree trunks';crowns.name='Ward tree crowns';
  return [trunks,crowns];
}

// ---- ramps: the native convex hulls, striped for reading speed and take-off point ---------
function ramps(solids,uniforms,common){
  const list=solids.filter(o=>o.role==='ramp');if(!list.length)return null;
  const P=[],H=[];
  for(const o of list){
    const heading=o.ramp.heading;
    for(const f of o.faces)for(const k of f){const v=o.vertices[k];P.push(v[0]+o.center[0],v[1]+o.center[1],v[2]+o.center[2]);H.push(heading);}
  }
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(P,3));
  g.setAttribute('heading',new THREE.Float32BufferAttribute(H,1));g.computeVertexNormals();
  const m=new THREE.ShaderMaterial({uniforms,vertexShader:`attribute float heading;varying float hd;varying vec3 p;varying vec3 n;
    void main(){hd=heading;p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`,
    fragmentShader:common+`varying float hd;
    void main(){
      vec3 N=normalize(n);vec2 d=vec2(cos(hd),sin(hd));float u=dot(p.xy,d),v=dot(p.xy,vec2(-d.y,d.x));
      float chevron=step(.5,fract((u+abs(v)*.8)*.35));
      vec3 deck=mix(vec3(.05,.05,.06),vec3(1.,.55,.10),chevron);
      vec3 side=vec3(.09,.09,.11);
      vec3 c=(N.z>.15?deck:side)*(vec3(.35,.40,.52)+vec3(1.1,.9,.7)*max(dot(N,sun),0.));
      c+=vec3(1.,.5,.1)*chevron*step(.15,N.z)*night*.6;
      gl_FragColor=vec4(haze(c),1.);
      #include <colorspace_fragment>
    }`});
  const mesh=new THREE.Mesh(g,m);mesh.name='Ward track ramps';mesh.userData.sceneryIds=list.map(o=>o.id);return mesh;
}

// ---- gardens: lawns, flower beds, gravel paths, ponds, plazas and crop rows on the ground ---
const GARDEN={lawn:0,bed:1,path:2,pond:3,plaza:4,crops:5,pitch:6,bays:7};
function gardens(list,ground,uniforms,common){
  const tris=[];
  for(const [kind,x0,y0,x1,y1,tone] of list){
    const a=[GARDEN[kind]??0,tone];
    const pt=(x,y)=>({x,y,a});
    tris.push([pt(x0,y0),pt(x1,y0),pt(x1,y1)],[pt(x0,y0),pt(x1,y1),pt(x0,y1)]);
  }
  const r=ground.drapeTriangles(tris,{offset:.05});
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(r.pos,3));
  g.setAttribute('normal',new THREE.Float32BufferAttribute(r.nor,3));
  g.setAttribute('garden',new THREE.Float32BufferAttribute(r.att,2));
  const m=new THREE.ShaderMaterial({uniforms,polygonOffset:true,polygonOffsetFactor:-3,polygonOffsetUnits:-6,
    vertexShader:`attribute vec2 garden;varying vec2 kind;varying vec3 p;varying vec3 n;void main(){kind=garden;p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`,
    fragmentShader:common+`varying vec2 kind;
    void main(){
      float k=floor(kind.x+.5),tone=kind.y;vec3 c;
      float grain=fbm(p.xy*.9),speck=hash(floor(p.xy*1.6));
      if(k<.5)c=mix(vec3(.05,.12,.04),vec3(.12,.20,.06),tone/3.)*(.75+.5*grain);
      else if(k<1.5){vec3 bloom=tone<1.?vec3(.75,.08,.12):tone<2.?vec3(.85,.62,.06):tone<3.?vec3(.45,.12,.62):tone<4.?vec3(.85,.85,.82):tone<5.?vec3(.95,.36,.10):vec3(.85,.30,.55);
        c=mix(vec3(.04,.09,.03),bloom,step(.55,speck));}
      else if(k<2.5)c=vec3(.33,.29,.24)*(.8+.4*grain);
      else if(k<3.5){vec3 V=normalize(cameraPosition-p);c=mix(vec3(.02,.06,.08),vec3(.20,.28,.40)*(1.-.6*night),pow(1.-V.z,3.));}
      else if(k<4.5)c=vec3(.27,.22,.17)*(.75+.45*grain);
      else if(k<5.5){float row=step(.5,fract(dot(p.xy,vec2(.43,.9))));c=mix(vec3(.08,.14,.04),tone<2.?vec3(.40,.34,.10):vec3(.10,.22,.06),row)*(.8+.3*grain);}
      else if(k<6.5){float stripe=step(.5,fract(p.x*.1));c=mix(vec3(.06,.16,.05),vec3(.09,.21,.07),stripe);
        vec2 g=abs(fract(p.xy/vec2(60.,40.))-.5);c=mix(c,vec3(.75),step(.485,max(g.x,g.y))*.8);}
      else if(k<7.5){c=vec3(.05,.05,.06);c=mix(c,vec3(.80,.78,.70),step(.92,fract(p.x*.38))*.9);}
      else{float row=step(.5,fract(dot(p.xy,vec2(.43,.9))));c=mix(vec3(.08,.14,.04),tone<2.?vec3(.40,.34,.10):vec3(.10,.22,.06),row)*(.8+.3*grain);}
      c*=vec3(.36,.40,.52)+vec3(1.05,.88,.68)*max(dot(normalize(n),sun),0.);
      c*=mix(1.,.45,night);
      gl_FragColor=vec4(haze(c),1.);
      #include <colorspace_fragment>
    }`});
  const mesh=new THREE.Mesh(g,m);mesh.name='Ward gardens';return mesh;
}

// ---- landing zones: lit rings, edge lights, a V mark and a wayfinding beam per zone ---------
function landingZones(pads,uniforms){
  const group=new THREE.Group();group.name='Rooftop landing zones';
  const time={value:0};
  const deck=new THREE.ShaderMaterial({uniforms:{night:uniforms.night,time},transparent:true,depthWrite:false,
    polygonOffset:true,polygonOffsetFactor:-6,polygonOffsetUnits:-10,toneMapped:false,
    vertexShader:`varying vec2 q;void main(){q=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`uniform float night,time;uniform vec3 tint;varying vec2 q;
    void main(){
      float r=length(q);if(r>1.08)discard;
      float ring=smoothstep(.86,.90,r)*(1.-smoothstep(.96,1.,r));
      float inner=smoothstep(.60,.62,r)*(1.-smoothstep(.65,.67,r))*step(.5,fract(atan(q.y,q.x)*3.8197));
      vec2 a=abs(q);float vee=step(abs(q.y*.9-a.x*1.6+.18),.07)*step(q.y,.42)*step(-.38,q.y);
      float dots=step(.93,fract(atan(q.y,q.x)*2.546+time*.5))*smoothstep(1.,1.02,r)*(1.-smoothstep(1.04,1.08,r));
      float lit=.55+.95*night;
      vec3 c=tint*(ring*1.6+inner*.8+vee*1.2)*lit+vec3(1.)*dots*(1.+2.*night);
      float alpha=clamp(ring+inner+vee+dots+.32*(1.-step(.86,r)),0.,1.);
      gl_FragColor=vec4(c+vec3(.025,.03,.04)*(1.-step(.86,r)),alpha);
    }`});
  const beam=new THREE.ShaderMaterial({uniforms:{night:uniforms.night,time},transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    side:THREE.DoubleSide,toneMapped:false,
    vertexShader:`varying float h;void main(){h=position.z;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`uniform float night;uniform vec3 tint;varying float h;
    void main(){gl_FragColor=vec4(tint*(1.-h)*(.10+.22*night),1.);}`});
  const beamG=new THREE.CylinderGeometry(.35,1.,1,24,1,true).rotateX(Math.PI/2).translate(0,0,.5);
  for(const p of pads){
    const tint={value:new THREE.Color(p.colour)};
    const d=deck.clone();d.uniforms={...deck.uniforms,tint};
    const disc=new THREE.Mesh(new THREE.PlaneGeometry(2.2,2.2),d);
    disc.scale.setScalar(p.radius_m);disc.position.set(p.center[0],p.center[1],p.center[2]+.06);disc.name=p.id;
    const b=beam.clone();b.uniforms={...beam.uniforms,tint};
    const column=new THREE.Mesh(beamG,b);column.scale.set(p.radius_m*.6,p.radius_m*.6,70);column.position.set(...p.center);
    group.add(disc,column);
  }
  return {group,time};
}

// ---- mission hoops, runway touchdown boxes and the exit hoop ------------------------------
function missionMarkers(missions,pads,uniforms){
  const group=new THREE.Group();group.name='Mission hoops';
  const rows=[];
  for(const m of missions){
    const colour=new THREE.Color(pads.find(p=>p.id===m.pad)?.colour??'#ffb340');
    const idle=new THREE.MeshBasicMaterial({color:colour.clone().multiplyScalar(.9),toneMapped:false});
    const hot=new THREE.MeshBasicMaterial({color:colour.clone().multiplyScalar(3.),toneMapped:false});
    const markers=m.steps.map((s,i)=>{
      const node=new THREE.Group();node.name=m.name+' step '+(i+1);
      if(s.type==='hoop'){
        const ring=new THREE.Mesh(new THREE.TorusGeometry(s.radius_m,Math.max(.45,s.radius_m*.045),10,64),idle);
        ring.position.set(...s.center);
        ring.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),new THREE.Vector3(...s.normal));
        node.add(ring);
      }else if(s.shape==='box'){
        const [hx,hy]=s.half,z=s.center[2]+.08;
        const pts=[[-hx,-hy],[hx,-hy],[hx,hy],[-hx,hy],[-hx,-hy]].map(([x,y])=>new THREE.Vector3(s.center[0]+x,s.center[1]+y,z));
        for(let k=1;k<pts.length;k++){
          const a=pts[k-1],b=pts[k],len=a.distanceTo(b);
          const bar=new THREE.Mesh(new THREE.BoxGeometry(len,.9,.08),idle);
          bar.position.copy(a).lerp(b,.5);bar.rotation.z=Math.atan2(b.y-a.y,b.x-a.x);node.add(bar);
        }
      }
      group.add(node);return node;
    });
    rows.push({m,markers,idle,hot,next:-1});
  }
  return {group,update(seconds,timing){
    for(const row of rows){
      const next=timing?.[row.m.name]?.next??0;
      const pulse=.5+.5*Math.sin(seconds*4);
      row.hot.color.setScalar(0).add(row.idle.color).multiplyScalar(2.2+1.4*pulse);
      if(row.next===next)continue;row.next=next;
      row.markers.forEach((node,i)=>node.traverse(o=>{if(o.isMesh)o.material=i===next?row.hot:row.idle;}));
    }
  }};
}
