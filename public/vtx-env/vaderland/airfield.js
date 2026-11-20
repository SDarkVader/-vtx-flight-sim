import * as THREE from 'three';
import {primaryRunwayCues} from '../runway-layout.js';

const vert=`
  attribute float surface; varying float kind; varying vec3 p; varying vec3 n;
  void main(){kind=surface;p=position;n=vec3(0.,0.,1.);gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}
`;

function sign(group,canvas,width,height,position,rot=0,vertical=false){
  const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;
  const m=new THREE.MeshBasicMaterial({map:t,transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-3});
  const face=new THREE.Mesh(new THREE.PlaneGeometry(width,height),m);
  face.rotation.order='ZYX';if(vertical)face.rotation.x=Math.PI/2;
  face.rotation.z=rot;face.position.set(...position);group.add(face);
}

function lettering(label,fg,bg){
  const c=document.createElement('canvas');c.width=1024;c.height=256;const x=c.getContext('2d');
  if(bg){x.fillStyle=bg;x.fillRect(0,0,1024,256);}
  x.textAlign='center';x.textBaseline='middle';x.font='bold 192px "Arial Narrow", sans-serif';
  x.fillStyle=fg;x.fillText(label,512,136,970);return c;
}

function terminalMark(group,o,diameter=116.5){
  const c=document.createElement('canvas');c.width=c.height=1024;const x=c.getContext('2d');
  x.fillStyle='#141c24';x.beginPath();x.arc(512,512,501,0,Math.PI*2);x.fill();
  for(const [r,stroke,color] of [[494,9,'#e4ab53'],[471,2,'#f7d593'],[428,2,'#646058']]){
    x.beginPath();x.arc(512,512,r,0,Math.PI*2);x.lineWidth=stroke;x.strokeStyle=color;x.stroke();
  }
  for(const s of [-1,1]){
    x.save();x.translate(512,311);x.scale(s,1);
    x.beginPath();x.moveTo(0,82);x.lineTo(167,-21);x.lineTo(95,-17);x.lineTo(0,44);x.fillStyle='#e5af5c';x.fill();
    x.beginPath();x.moveTo(10,27);x.lineTo(92,-28);x.lineTo(62,-25);x.lineTo(18,5);x.fill();x.restore();
  }
  x.textAlign='center';x.fillStyle='#f1d397';x.font='600 83px "Arial Narrow",sans-serif';x.fillText('VADERLAND',512,535,800);
  x.font='bold 145px "Arial Narrow",sans-serif';x.fillText('VTX',512,700);
  sign(group,c,diameter,diameter,[...o.center.slice(0,2),o.center[2]+o.half[2]+.045]);
}

function makePaving(group,w,uniforms,common){
  const positions=[],types=[],mark=[],col=[],lamps=[];
  const cues=primaryRunwayCues(w),r=cues.runway;
  function polygon(points,z,type,tint){
    const verts=THREE.ShapeUtils.triangulateShape(points.map(p=>new THREE.Vector2(...p)),[]);
    const rgb=tint?new THREE.Color(tint):null;
    for(const tri of verts)for(const i of tri){
      (rgb?mark:positions).push(...points[i],z);
      if(rgb)col.push(rgb.r,rgb.g,rgb.b);else types.push(type);
    }
  }
  function rect(x,y,a,b,z,type,tint){
    polygon([[x-a,y-b],[x+a,y-b],[x+a,y+b],[x-a,y+b]],z,type,tint);
  }
  function strip(points,width,offset,z,type,tint){
    const sides=[];
    for(let i=0;i<points.length;i++){
      const p=points[i],a=points[Math.max(0,i-1)],b=points[Math.min(points.length-1,i+1)];
      const dx=b[0]-a[0],dy=b[1]-a[1],l=Math.hypot(dx,dy)||1;
      sides.push([-1,1].map(sign=>[p[0]-dy/l*(offset+sign*width/2),p[1]+dx/l*(offset+sign*width/2)]));
    }
    for(let i=1;i<sides.length;i++)polygon([sides[i-1][0],sides[i][0],sides[i][1],sides[i-1][1]],z,type,tint);
  }
  rect(0,0,r.length/2,19,.014,0);rect(0,0,r.length/2,15,.027,2);
  rect(0,-45,r.length/2-42,6,.018,0);
  rect(7,-78,260,32,.019,1);
  if(w.vaderland.arrivals){
    const ring=(r,turn=0)=>Array.from({length:145},(_,i)=>{
      const a=turn+i*Math.PI/72;return [r*Math.cos(a),-437+r*Math.sin(a)];
    });
    strip(ring(16.3),4.6,0,.018,1);
    rect(0,-395,42,8,.019,1);
    const inner=Array.from({length:61},(_,i)=>{const a=(-72+i*2.4)*Math.PI/180;return [80*Math.sin(a),-300-80*Math.cos(a)];});
    polygon([...inner,[91,-350],[84,-377],[63,-391],[37,-404],[-37,-404],[-63,-391],[-84,-377],[-91,-350]],.017,3);
    for(const road of w.vaderland.routes.filter(r=>r.kind==='arrivals')){
      strip(road.points,road.width_m+1.1,0,.026,0);strip(road.points,road.width_m,0,.032,0);
      for(const side of [-1,1]){
        strip(road.points,.15,side*(road.width_m/2-.25),.046,0,'#ad9c77');
        strip(road.points,.22,side*(road.width_m/2+.30),.043,0,'#77766a');
      }
    }
    for(let i=0;i<36;i++){
      const a=i*Math.PI/18, x=15.5*Math.cos(a),y=-437+15.5*Math.sin(a);
      lamps.push([x,y,.081,'#e5a14f',.53]);
    }
    for(const side of [-1,1]){
      for(let i=0;i<8;i++)rect(side*(27+i*.84),-395,.20,3.85,.054,0,'#d2cabc');
      for(let i=0;i<9;i++)lamps.push([side*(3+i*3.35),-400.65,9.02+2.1*(1-((3+i*3.35)/38)**2)-.57,'#ffe0a0',.38]);
    }
  }
  for(const h of w.vaderland.airfield.aprons){
    const [x,y]=h.xy,[a,b]=h.half,q=19;
    polygon([[x-a+q,y-b],[x+a-q,y-b],[x+a,y-b+q],[x+a,y+b-q],
      [x+a-q,y+b],[x-a+q,y+b],[x-a,y+b-q],[x-a,y-b+q]],.021,1);
  }
  // Curved exits join the marked runway and parallel taxiway. Their line
  // widths, markings and insets use world metres throughout.
  for(let x=-3550;x<=3550;x+=710){
    const exit=[];
    for(let j=0;j<=24;j++){const t=j/24;exit.push([x+88*t,-45*t*t*(3-2*t)]);}
    strip(exit,16,0,.022,0);
    strip(exit.slice(8),.25,0,.052,0,'#f5c35e');
    for(let j=7;j<23;j+=4)lamps.push([exit[j][0],exit[j][1],.072,'#81e7ad',.32]);
  }
  for(const road of w.vaderland.routes.filter(o=>o.kind==='taxi')){
    strip(road.points,road.width_m,0,.029,0);
    strip(road.points,.26,0,.059,0,'#efbd55');
    for(const side of [-1,1])strip(road.points,.19,side*(road.width_m/2-.43),.057,0,'#c9ab73');
    let next=0,station=0;
    for(let i=1;i<road.points.length;i++){
      const a=road.points[i-1],b=road.points[i],dx=b[0]-a[0],dy=b[1]-a[1],l=Math.hypot(dx,dy);
      while(next<=station+l){
        const t=(next-station)/l;
        for(const side of [-1,1])lamps.push([a[0]+t*dx-side*dy/l*(road.width_m/2+.55),
          a[1]+t*dy+side*dx/l*(road.width_m/2+.55),.14,'#568aff',.55]);
        next+=22;
      }
      station+=l;
    }
  }
  for(let x=-r.length/2+103;x<r.length/2-90;x+=58)rect(x,0,13.5,.28,.053,0,'#dfe0d7');
  for(const side of [-1,1]){
    rect(0,side*14.45,r.length/2-.1,.19,.055,0,'#edebdf');
    for(const direction of [-1,1]){
      const end=(r.length/2)*direction;
      for(const distance of [160,310,465,620]){
        if(distance===310)rect(end-direction*distance,side*8.2,18,2.20,.056,0,'#e8e5d9');
        else for(let i=0;i<(distance===160?3:distance===465?2:1);i++)
          rect(end-direction*distance,side*(8.5+i*1.15),10.8,.35,.056,0,'#dbdfd6');
      }
      for(let i=0;i<5;i++)rect(end-direction*17,side*(3+i*2.1),12.6,.57,.057,0,'#eeece2');
    }
  }
  for(const n of cues.numbers)sign(group,lettering(n.label,'#e5e5d9'),15.5,15.5,[n.x+(n.label==='08'?24:-24),0,.061],n.rotation);
  for(const lamp of [...cues.edgeLights,...cues.thresholdLights])lamps.push([lamp[0],lamp[1],.16,lamp[2],.56]);
  for(const p of w.vaderland.airfield.pads){
    const arc=(r,lo,hi)=>Array.from({length:65},(_,i)=>{const a=lo+(hi-lo)*i/64;return [p.x+r*Math.cos(a),p.y+r*Math.sin(a)];});
    strip(arc(16.6,.22,2*Math.PI-.22),.36,0,.062,0,'#ece5ca');strip(arc(14.9,.23,2*Math.PI-.23),.22,0,.062,0,'#daa54b');
    strip([[p.x,p.y+35],[p.x,p.y+6]],.30,0,.065,0,'#f3b44f');
    for(const s of [-1,1])rect(p.x+s*5.15,p.y,1.25,2.55,.063,0,'#dddeda');
    sign(group,lettering(p.code,'#e7dfca'),10.4,3.8,[p.x,p.y-4.6,.069]);
    for(let i=0;i<12;i++){const t=i*Math.PI/6;lamps.push([p.x+17.45*Math.cos(t),p.y+17.45*Math.sin(t),.105,'#eac06d',.5]);}
  }
  function geom(pos){
    const b=new THREE.BufferGeometry();b.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));return b;
  }
  const pavement=geom(positions);pavement.setAttribute('surface',new THREE.Float32BufferAttribute(types,1));
  const material=new THREE.ShaderMaterial({uniforms,side:THREE.DoubleSide,vertexShader:vert,
    fragmentShader:'varying float kind;uniform sampler2D reliefLight;'+common+`
    void main(){
      float grain=fbm(p.xy*6.7), mottling=fbm(p.xy*.039);
      vec2 uv=p.xy/7.5,grid=abs(fract(uv+.5)-.5)*7.5;
      float line=min(grid.x,grid.y),joint=1.-smoothstep(.018,.073+min(.09,fwidth(line)),line);
      vec3 slab=mix(vec3(.125,.124,.118),vec3(.245,.241,.224),mottling+.11*hash(floor(uv+.5)));
      slab*=.79+.29*grain;slab*=1.-.57*joint;
      vec3 asphalt=mix(vec3(.043,.049,.054),vec3(.092,.099,.105),mottling)*(.74+.38*grain);
      vec3 color=kind>.5 && kind<1.5?slab:asphalt;
      if(kind>2.5){
        vec2 tile=vec2(p.x/2.2,p.y/1.1),g=abs(fract(tile+.5)-.5);
        float seam=(1.-smoothstep(.005,.024,min(g.x,g.y)))*(1.-smoothstep(.16,.52,max(fwidth(tile.x),fwidth(tile.y))));
        color=mix(vec3(.155,.145,.125),vec3(.27,.26,.23),.56*grain+.26*mottling)*mix(1.,.61,seam);
      }else if(kind>1.5){
        float fromEnd=3900.-abs(p.x);
        float zone=smoothstep(45.,250.,fromEnd)*(1.-smoothstep(420.,1150.,fromEnd));
        float grooves=fbm(vec2(p.x*.019,p.y*3.2));
        color*=1.-.58*zone*(1.-smoothstep(1.,8.,abs(abs(p.y)-2.7)))*grooves;
      }
      float shade=texture2D(reliefLight,p.xy/16000.+.5).r;
      color*=mix(vec3(.46,.58,.83),vec3(1.30,1.10,.91),shade);
      vec2 contact=forecourtShadow(p.xy);
      color*=mix(vec3(.45,.55,.71),vec3(1.),contact.x)*mix(.67,1.,contact.y);
      gl_FragColor=vec4(haze(color*mix(1.,.38,night)),1.);
      #include <colorspace_fragment>
    }`,polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-2});
  const base=new THREE.Mesh(pavement,material);base.name='Meridian surveyed hardstanding';group.add(base);
  const paint=geom(mark);paint.setAttribute('color',new THREE.Float32BufferAttribute(col,3));
  group.add(new THREE.Mesh(paint,new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:-4,polygonOffsetUnits:-4})));
  for(const [x,y,z] of w.vaderland.airfield.lamps)lamps.push([x,y,z-.15,'#ffe0a1',1.05]);
  const light=geom(lamps.flatMap(l=>l.slice(0,3)));light.setAttribute('tint',new THREE.Float32BufferAttribute(lamps.flatMap(l=>new THREE.Color(l[3]).toArray()),3));
  light.setAttribute('diameter',new THREE.Float32BufferAttribute(lamps.map(l=>l[4]),1));
  group.add(new THREE.Points(light,new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    vertexShader:`attribute vec3 tint;attribute float diameter;varying vec3 v;void main(){v=tint;vec4 q=modelViewMatrix*vec4(position,1.);
    gl_Position=projectionMatrix*q;gl_PointSize=clamp(1.6+diameter*530./max(1.,-q.z),1.6,19.);}`,
    fragmentShader:`varying vec3 v;void main(){float r=length(gl_PointCoord-.5)*2.;if(r>1.)discard;
    gl_FragColor=vec4(v*(1.15+exp(-r*r*24.)),exp(-r*r*4.1));}`})));
}

function terminalMaterial(uniforms,common,finish,round){
  const glazed=['gate','rotunda','cab'].includes(finish);
  return new THREE.ShaderMaterial({uniforms,vertexShader:`
    varying vec3 p;varying vec3 n;varying vec3 local;varying vec3 dim;
    void main(){vec4 pos=instanceMatrix*vec4(position,1.);p=pos.xyz;local=position;
      dim=vec3(length(instanceMatrix[0].xyz),length(instanceMatrix[1].xyz),length(instanceMatrix[2].xyz));
      n=normalize(normal);gl_Position=projectionMatrix*viewMatrix*pos;}`,
    fragmentShader:'uniform sampler2D clouds;uniform float clock;varying vec3 local;varying vec3 dim;'+common+`
    void main(){
      vec3 N=normalize(n),view=normalize(cameraPosition-p);
      float ht=(local.z+.5)*dim.z,fromTop=(.5-local.z)*dim.z;
      float s=${round?'atan(local.y,local.x)*dim.x*.5':'(abs(N.x)>.5?p.y:p.x)'};
      float fine=fbm(p.xy*.13+p.z*.05);
      vec3 reflected=skySample(clouds,reflect(-view,N));
      float direct=max(dot(N,sun),0.);
      vec3 metal=mix(vec3(.018,.031,.049),vec3(.073,.099,.14),fine)*(.70+.72*direct);
      vec3 bronze=mix(vec3(.075,.040,.021),vec3(.50,.25,.085),direct+.10*fine);
      vec3 c=metal;
      if(${glazed?'true':'false'} && abs(N.z)<.72){
        float pitch=${finish==='cab'?'3.85':finish==='rotunda'?'3.5':'3.15'};
        vec2 pane=vec2(s/pitch,(p.z-.8)/4.35),f=fract(pane);
        vec2 frame=min(f,1.-f)*vec2(pitch,4.35);
        float window=smoothstep(.10,.18,min(frame.x,frame.y));
        vec2 bay=floor(pane);
        float occupancy=hash(vec2(floor(bay.x/3.),bay.y)+floor(dim.xy+.5));
        vec3 glass=vec3(.009,.021,.038)+reflected*vec3(.30,.42,.65)*(.48+.24*(1.-abs(dot(N,view))));
        float occupied=smoothstep(.30,.65,occupancy);
        float ceiling=smoothstep(.85,.90,f.y)*(1.-smoothstep(.965,.99,f.y));
        float pool=1.-smoothstep(.06,.80,length(vec2((f.x-.51)*.83,f.y-.42)));
        vec3 hall=vec3(.080,.044,.023)+vec3(.84,.39,.095)*pool*(.35+.65*occupied);
        hall+=vec3(1.3,.73,.27)*ceiling*(.30+.70*occupied);
        hall*=mix(.49,1.,smoothstep(.1,.27,f.y));
        glass=mix(glass,hall,.15+.59*occupied);
        c=mix(vec3(.028,.042,.052),glass,window);
        float spandrel=1.-smoothstep(.08,.15,min(f.y,1.-f.y));
        c=mix(c,metal*.54,spandrel*.82);
        float fascia=1.-smoothstep(.16,.36,fromTop);
        c=mix(c,bronze,fascia);
        c+=vec3(1.55,.81,.20)*(1.-smoothstep(.055,.22,abs(fromTop-.48)));
        c=mix(c,metal*.62,1.-smoothstep(.4,1.2,ht));
      }else if(${finish==='vault'?'true':'false'}){
        float seam=(1.-smoothstep(.015,.065,min(fract(p.y/1.18),1.-fract(p.y/1.18))*1.18))*(1.-smoothstep(.09,.45,fwidth(p.y)));
        c=mix(metal*.78+reflected*.06,metal*.43,seam);
        float verge=(1.-smoothstep(.19,.50,(.5-abs(local.y))*dim.y))*(1.-smoothstep(.32,.52,fromTop));
        c=mix(c,vec3(.68,.35,.088),verge);
        if(abs(N.y)>.7)c=mix(metal*.7,vec3(.61,.30,.069),1.-smoothstep(.13,.40,fromTop));
      }else if(${finish==='service'?'true':'false'} && abs(N.z)<.7){
        float bay=fract(s/6.),level=fract((p.z+.2)/4.8);
        float glazing=smoothstep(.08,.13,bay)*(1.-smoothstep(.88,.94,bay))*
          smoothstep(.44,.50,level)*(1.-smoothstep(.87,.91,level));
        vec3 steel=metal*(.83+.15*cos(s*9.));
        float lit=step(.62,hash(vec2(floor(s/12.),floor((p.z+.2)/4.8))));
        c=mix(steel,vec3(.021,.044,.066)+reflected*.13+vec3(.40,.19,.053)*lit,glazing);
        c+=vec3(.78,.43,.14)*(1.-smoothstep(.045,.14,abs(fromTop-.39)));
      }else if(${finish==='hangar-wall'||finish==='hangar-roof'?'true':'false'}){
        float rib=1.-smoothstep(.028,.079,min(fract(s/.92),1.-fract(s/.92))*.92);
        c=metal*(.75+.25*rib);
        if(N.z<-.7){float light=1.-smoothstep(.035,.12,abs(mod(p.y-45.+3.4,6.8)-3.4));
           c=metal*.66+vec3(.91,.79,.55)*light;}
        if(abs(N.z)<.7){
          float band=smoothstep(.57,.63,p.z)*(1.-smoothstep(1.28,1.36,p.z));
          c=mix(c,mix(vec3(.065,.068,.063),vec3(.59,.39,.12),step(.5,fract(s*.36+p.z*.42))),band);
        }
      }else if(${finish==='quay-canopy'?'true':'false'}){
        float seam=abs(fract(p.x*.95)-.5);
        c=mix(metal,metal*.49,smoothstep(.43,.49,seam))+reflected*.065;
        if(N.z<-.5){
          float strip=1.-smoothstep(.025,.072,abs(abs(p.y+536.8)-2.95));
          c=vec3(.13,.088,.049)*(.76+.24*fine)+vec3(.90,.55,.22)*strip;
        }else if(abs(N.z)<.5)c+=vec3(.89,.44,.10)*(1.-smoothstep(.03,.095,abs(fromTop-.13)));
      }else if(${finish==='quay-column'||finish==='pile'?'true':'false'}){
        float gloss=pow(max(0.,dot(reflect(-view,N),normalize(vec3(.78,-.56,.29)))),14.);
        c=metal*.88+reflected*.17+vec3(.45,.32,.18)*gloss;
        if(${finish==='pile'?'true':'false'} && p.z<7.18)c=mix(c,vec3(.033,.059,.049),.63);
        if(${finish==='quay-column'?'true':'false'}){
          c=mix(c,bronze*.79,1.-smoothstep(.66,.71,ht));
          c+=vec3(.32,.17,.068)*(1.-smoothstep(.016,.038,abs(ht-.71)));
          float flange=1.-smoothstep(.20,.25,fromTop);c=mix(c,bronze,flange);
        }
      }else if(${finish==='shaft'?'true':'false'}){
        float flute=cos(atan(local.y,local.x)*24.);
        c=mix(vec3(.15,.17,.17),vec3(.42,.37,.29),.5+.5*flute)*(.69+.54*direct);
      }else if(${finish==='lamp'?'true':'false'}){
        c=fromTop<.35?vec3(1.7,1.05,.45):vec3(.064,.077,.082);
      }else if(${finish==='bronze'?'true':'false'}){
        c=bronze+reflected*.13;
      }else if(${finish==='pad'?'true':'false'}){
        c=mix(vec3(.075,.09,.099),vec3(.12,.13,.13),fine);
      }else if(N.z>.7){
        c=metal*.65+reflected*.10;
      }
      gl_FragColor=vec4(haze(c*mix(1.,${glazed?'.83':'.53'},night)),1.);
      #include <colorspace_fragment>
    }`});
}

function firTexture(seed){
  let state=seed;
  const random=()=>((state=(Math.imul(1664525,state)+1013904223)>>>0)/4294967296);
  const c=document.createElement('canvas');c.width=192;c.height=384;
  const ctx=c.getContext('2d');
  const trunk=y=>96+1.8*Math.sin(y*.018+seed);
  ctx.lineCap='round';
  ctx.fillStyle='#5c5141';ctx.beginPath();ctx.moveTo(trunk(9),8);ctx.lineTo(trunk(380)-3,380);ctx.lineTo(trunk(380)+3.6,380);ctx.fill();
  const boughs=[];
  for(let tier=0;tier<33;tier++){
    const f=(tier+1)/34,base=10+f*319;
    const length=(6+80*Math.pow(f,.77))*(.91+.09*Math.sin(tier*7));
    for(let j=0;j<9;j++){
      const a=(j+random()*.64)*Math.PI*2/9;
      boughs.push({y:base+random()*5,dx:Math.cos(a)*length*(.78+.22*random()),depth:Math.sin(a),f});
    }
  }
  for(const b of boughs.sort((a,b)=>a.depth-b.depth)){
    const start=trunk(b.y),slope=8+b.f*(12+7*b.depth),shade=.68+.23*(b.depth+1)/2+.16*(b.dx>0?1:0);
    for(let j=0;j<24;j++){
      const t=(j+random()*.6)/24,x=start+b.dx*t,y=b.y+slope*Math.sin(t*2)-t*1.8;
      const length=(1-t)*(.37+b.f)*15+3,glow=(.73+.42*random())*shade;
      ctx.strokeStyle='rgb('+[68,88,66].map((v,k)=>Math.round(v*glow+(k===0?6:0))).join(',')+')';
      ctx.lineWidth=Math.min(3.2,.85+2.2*b.f*(1-t));ctx.beginPath();
      ctx.moveTo(x,y);ctx.lineTo(x+b.dx*.06+(random()-.5)*5,y+length);ctx.stroke();
      if(j%2===0){ctx.strokeStyle='rgba(139,150,105,.45)';ctx.lineWidth=.85;ctx.beginPath();
        ctx.moveTo(x,y);ctx.lineTo(x+b.dx*.042,y+length*.52);ctx.stroke();}
    }
  }
  const tex=new THREE.CanvasTexture(c);tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=8;return tex;
}

export function airportTree(o){
  return o.kind==='cylinder' && (!o.role||o.role==='conifer') &&
    Math.abs(o.center[0])<940 && Math.abs(o.center[1]+220)<780;
}

export function buildAirport(group,w,uniforms,common,instanced){
  makePaving(group,w,uniforms,common);
  const sets=new Map(),stands=[[],[],[]],trunks=[];
  for(const o of w.obstacles){
    if(w.vaderland.quarter && o.id.startsWith('plaza-linden-'))continue;
    if(o.finish==='jetty')continue;
    if(o.finish==='shell')continue;
    if(airportTree(o)){
      const [x,y,z]=o.center,[r,,h]=o.half;
      const radius=o.crown_radius_m??r;
      const variation=o.species??Math.abs(Math.round(x*.7+y*3.4))%3;
      const angle=(x*.77+y*1.3)%6.28;
      for(let k=0;k<(w.vaderland.arrivals?1:3);k++)stands[variation].push([x,y,z,radius*2.15,1,2*h,0,angle+k*Math.PI/3]);
      const trunk=o.crown_radius_m?r:Math.max(.12,r*.095);
      if(!w.vaderland.arrivals)trunks.push([x,y,z-h*.37,trunk*2,trunk*2,1.26*h,'#514638']);
      continue;
    }
    if(!o.finish)continue;
    const key=o.finish+'/'+o.kind;
    if(!sets.has(key))sets.set(key,[]);
    sets.get(key).push(o);
    if(o.id==='airport-rotunda-crown')terminalMark(group,o);
  }
  for(const objects of sets.values()){
    const {finish,kind}=objects[0],round=kind==='cylinder';
    const shape=round?new THREE.CylinderGeometry(.5,.5,1,finish==='rotunda'?100:48).rotateX(Math.PI/2):new THREE.BoxGeometry();
    const mat=terminalMaterial(uniforms,common,finish,round);
    const mesh=instanced(group,shape,mat,objects.map(o=>[...o.center,...o.half.map(h=>2*h)]));
    mesh.name='Airfield '+finish;mesh.userData.sceneryIds=objects.map(o=>o.id);
  }
  instanced(group,new THREE.CylinderGeometry(.50,.50,1,8).rotateX(Math.PI/2),
    new THREE.MeshStandardMaterial({roughness:1}),trunks);
  for(let i=0;i<stands.length;i++){
    const tex=w.vaderland.arrivals?uniforms['tree'+i].value:firTexture(i+37),card=new THREE.PlaneGeometry(1,1).rotateX(Math.PI/2);
    const m=w.vaderland.arrivals?new THREE.ShaderMaterial({uniforms:{...uniforms,foliage:{value:tex}},
      side:THREE.DoubleSide,vertexShader:`
      varying vec2 st;varying vec3 p;varying vec3 n;varying vec2 foot;
      void main(){
        st=uv;vec3 center=instanceMatrix[3].xyz;foot=center.xy;
        float w=length(instanceMatrix[0].xyz),h=length(instanceMatrix[2].xyz);
        vec3 ground=center-vec3(0.,0.,h*.5),v=normalize(cameraPosition-ground);
        vec3 right=normalize(vec3(-v.y,v.x,.000001));
        vec3 up=normalize(mix(vec3(0.,0.,1.),cross(v,right),.34*abs(v.z)));
        p=ground+right*(uv.x-${[.5282,.5425,.4297][i]})*w+up*uv.y*h;n=vec3(0.,0.,1.);
        gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`,
      fragmentShader:'uniform sampler2D foliage;varying vec2 st;varying vec2 foot;'+common+`
        void main(){vec4 leaf=texture2D(foliage,st);if(leaf.a<.45)discard;
          vec2 contact=forecourtShadow(foot);float lit=mix(.60,1.,st.y);
          vec3 c=leaf.rgb*mix(vec3(.38,.48,.58),vec3(.84,.79,.64),st.y*.55+.45*contact.x)*lit;
          float l=dot(c,vec3(.22,.67,.11));c=mix(c,vec3(l*.93,l,l*1.08),.24);
          gl_FragColor=vec4(haze(c*mix(1.,.38,night)),1.);
          #include <colorspace_fragment>
        }`}):new THREE.MeshBasicMaterial({map:tex,alphaTest:.34,side:THREE.DoubleSide,color:'#c7c9b6',toneMapped:true});
    instanced(group,card,m,stands[i]);
  }
  for(const [x,angle] of [[61.985,-Math.PI/2],[108.015,Math.PI/2]]){
    sign(group,lettering('HANGAR   A','#f6d595','#182630'),13,1.25,[x,45,16.90],angle,true);
  }
}
