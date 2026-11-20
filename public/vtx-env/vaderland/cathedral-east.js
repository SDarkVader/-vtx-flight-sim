import * as THREE from 'three';

const finishes={
  eastStone:'c=stone*(.31+.68*key)+sky*.11;',
  eastSteel:'c=(vec3(.027,.035,.050)+grain*.18)*(.47+.68*key)+sky*.28;',
  eastBasalt:'c=stone*vec3(.57,.47,.45)*(.27+key*.67)+sky*.10;',
  eastApron:'c=texture2D(asphaltColor,uv*.18).rgb*(.56+.46*key)+sky*.13;',
  eastGold:'c=vec3(3.20,1.03,.23);',
  eastCream:'c=vec3(2.35,1.48,.68);',
  eastViolet:'c=vec3(.70,.32,2.72);',
  eastAmberGlass:[
    'float mullion=smoothstep(.075,.11,fract(uv.x*.42));',
    'float rail=smoothstep(.07,.13,fract(p.z*.40));',
    'float room=fract(sin(floor(uv.x*.42)*39.458+floor(p.z*.40)*25.118)*4374.56);',
    'c=sky*.38 + mullion*rail*vec3(1.42,.52,.16)*(.10+.90*night)*(.36+room*.82);',
  ].join('\n'),
};

function architecture(group,world,uniforms,common){
  const batches = new Map();
  for(const obstacle of world.obstacles){
    if(!obstacle.id.startsWith('east-'))continue;
    if(!batches.has(obstacle.skin))batches.set(obstacle.skin,{positions:[],spans:[]});
    const b=batches.get(obstacle.skin);
    for(const face of obstacle.faces)for(const index of face){
      b.positions.push(...obstacle.vertices[index].map((p,i)=>p+obstacle.center[i]));
    }
    b.spans.push({end:b.positions.length/9,id:obstacle.id});
  }
  for(const [finish,b] of batches){
    const geo=new THREE.BufferGeometry();
    geo.setAttribute('position',new THREE.Float32BufferAttribute(b.positions,3));
    geo.computeVertexNormals();
    const mat=new THREE.ShaderMaterial({
      uniforms,
      vertexShader:'varying vec3 p,n;void main(){p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}',
      fragmentShader:common+'\n'+[
        'uniform sampler2D alloyColor,granite,asphaltColor;',
        'void main(){',
        'vec3 N=normalize(n),R=reflect(normalize(p-cameraPosition),N);',
        'float key=max(dot(N,sun),0.);',
        'vec2 uv=vec2(.83*p.x+.51*p.y,p.z+.18*p.x-.42*p.y);',
        'vec3 stone=texture2D(granite,uv*.29).rgb,grain=texture2D(alloyColor,uv*.43).rgb;',
        'vec3 sky=skySample(daySky,R),c;',
        finishes[finish],
        'gl_FragColor=vec4(haze(c),1.);',
        '#include <colorspace_fragment>',
        '}',
      ].join('\n'),
    });
    const mesh=new THREE.Mesh(geo,mat);
    mesh.name='Lantern Paddock '+finish;
    mesh.userData.surveySpans=b.spans;
    group.add(mesh);
  }
}

function board(group,info){
  const face=document.createElement('canvas');
  face.width=1024;
  face.height=160;
  const pen=face.getContext('2d');
  const texture=new THREE.CanvasTexture(face);
  texture.colorSpace=THREE.SRGBColorSpace;
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(info.width,info.height),
    new THREE.MeshBasicMaterial({map:texture,toneMapped:false}));
  mesh.rotation.x=info.normal==='north'?-Math.PI/2:Math.PI/2;
  if(info.normal==='west')mesh.rotateOnWorldAxis(new THREE.Vector3(0,0,1),-Math.PI/2);
  mesh.position.set(...info.point);
  mesh.name=info.label;
  group.add(mesh);
  let last=null;
  return function draw(status=''){
    if(status===last)return;
    last=status;
    pen.fillStyle='#151722';pen.fillRect(0,0,1024,160);
    pen.strokeStyle=info.normal==='west'?'#bd9aff':'#ffb96a';
    pen.lineWidth=5;pen.strokeRect(10,7,1004,146);
    pen.textAlign='center';pen.fillStyle='#ffdfb7';
    pen.font='italic 900 '+(status?'64':'89')+'px system-ui';
    pen.fillText(info.label,512,status?76:110,905);
    if(status){
      pen.font='800 42px system-ui';pen.fillStyle='#dbc2ff';pen.fillText(status,512,136);
      for(const x of [28,926])for(let j=0;j<3;j++)for(let i=0;i<4;i++){
        if((j+i)%2===0)pen.fillRect(x+19*i,44+19*j,19,19);
      }
    }
    texture.needsUpdate=true;
  };
}

function apronLighting(group,world){
  const positions=[];
  const push=(x,y,a,b,h)=>{
    const points=[[x-a,y-b],[x+a,y-b],[x-a,y+b],[x+a,y+b]];
    for(const k of [0,1,2,1,3,2])positions.push(...points[k],h);
  };
  for(const o of world.obstacles){
    if(!o.id.startsWith('east-workshop-')||!o.id.endsWith('-slab'))continue;
    const [x,y,z]=o.center, h=z+o.half[2]+.018;
    for(const u of [-10,-5,0,5,10])push(x+u,y-.25,.055,7.8,h);
    push(x,y-8.0,10,.057,h);
  }
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  const mesh=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({color:0xd4a66c,side:THREE.DoubleSide}));
  mesh.name='Workshop bay floor paint';
  group.add(mesh);
}

function quarryRibbon(group,world,ground,uniforms,common,paddock){
  const road=world.vaderland.routes.find(r=>r.name===paddock.course.name);
  const mud=world.vaderland.surface_detail?.quarry_mud;
  const [gx,gy]=paddock.course.gates[0].center;
  let chain=0,start=0,gateDistance=Infinity;
  const points=road.points.slice(0,-1);
  const normals=points.map(([x,y],i)=>{
    const [a,b]=points[(i+1)%points.length],length=Math.hypot(a-x,b-y);
    return [(y-b)/length,(a-x)/length];
  });
  const sections=road.points.map(([x,y],i)=>{
    if(i)chain+=Math.hypot(x-road.points[i-1][0],y-road.points[i-1][1]);
    const [nx,ny]=normals[(i+points.length-1)%points.length], [mx,my]=normals[i%points.length];
    const angle=1+nx*mx+ny*my;
    const d=Math.hypot(x-gx,y-gy);
    if(d<gateDistance){gateDistance=d;start=chain;}
    return [-road.width_m*.5,road.width_m*.5].map(u=>({
      x:x+u*(nx+mx)/angle,y:y+u*(ny+my)/angle,a:[u,chain],
    }));
  });
  const triangles=[];
  for(let i=1;i<sections.length;i++){
    const [a,b]=sections[i-1],[c,d]=sections[i];
    triangles.push([a,c,b],[b,c,d]);
  }
  const baked=ground.drapeTriangles(triangles,{offset:.071});
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(baked.pos,3));
  geometry.setAttribute('normal',new THREE.Float32BufferAttribute(baked.nor,3));
  geometry.setAttribute('coursePoint',new THREE.Float32BufferAttribute(baked.att,2));
  const material=new THREE.ShaderMaterial({
    uniforms:{...uniforms,startStripe:{value:start}},
    side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-4,
    vertexShader:'attribute vec2 coursePoint; varying vec2 route; varying vec3 p,n; void main(){route=coursePoint;p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}',
    fragmentShader:common+'\n'+[
      'uniform sampler2D granite,asphaltRough;uniform float startStripe;varying vec2 route;',
      mud?'uniform sampler2D quarryMud;':'',
      'void main(){',
      'float u=abs(route.x),v=route.y;',
      'float wash=fbm(p.xy*.16),grain=texture2D(granite,p.xy*.47).r;',
      'float debris=texture2D(asphaltRough,p.xy*.58).r;',
      'vec2 wheels=(vec2(u)-vec2(2.22,1.4))*vec2(1.93,2.34);float rut=exp(-wheels.x*wheels.x)+exp(-wheels.y*wheels.y)*.63;',
      'vec3 normalRoad=normalize(n),V=normalize(cameraPosition-p);',
      'vec3 c=mix(vec3(.093,.055,.039),vec3(.27,.165,.102),wash)*(.55+.86*grain);',
      'c*=1.-.30*rut*(.35+.65*debris);',
      'c*=.65+max(0.,dot(normalRoad,sun))*.42;',
      'c+=pow(1.-max(.0,dot(V,normalRoad)),2.9)*skySample(daySky,reflect(-V,normalRoad))*.17;',
      mud?[
        'vec2 uv=p.xy/2.2;',
        'vec3 clay=texture2D(quarryMud,uv).rgb;',
        'vec3 loam=texture2D(quarryMud,vec2(-uv.y,uv.x)*.71+vec2(.29,.47)).rgb;',
        'float pooled=smoothstep(.36,.69,fbm(vec2(route.x*.78,v*.095))+.14*rut);',
        'vec3 lit=mix(clay,loam,clamp(wash*1.20-.12,0.,1.))*(.75+.43*wash);',
        'lit*=1.-.37*pooled;',
        'float skim=.06+.35*pow(1.-max(0.,dot(V,normalRoad)),3.);',
        'c=mix(lit,skySample(daySky,reflect(-V,normalRoad)),skim*(.17+.75*pooled));',
        'c*=mix(1.,.58,night);',
      ].join('\n'):'',
      'float rim=smoothstep(5.6,5.72,u)*(1.-smoothstep(5.98,6.12,u));',
      'float dash=step(.72,fract(v/6.));',
      'c=mix(c,vec3(.63,.36,1.15),rim*dash*.82);',
      'float grid=1.-smoothstep(.57,.63,abs(v-startStripe));',
      'float tiles=mod(floor((route.x+6.5)*1.54)+step(startStripe,v),2.);',
      'c=mix(c,mix(vec3(.03,.025,.047),vec3(.85,.74,.68),tiles),grid);',
      'gl_FragColor=vec4(haze(c),1.);',
      '#include <colorspace_fragment>',
      '}',
    ].join('\n'),
  });
  const mesh=new THREE.Mesh(geometry,material);
  mesh.name='Lantern Quarry driving surface';
  group.add(mesh);
}

export function buildCathedralEast(group,world,ground,uniforms,common){
  const paddock=world.vaderland.cathedral_east;
  architecture(group,world,uniforms,common);
  apronLighting(group,world);
  quarryRibbon(group,world,ground,uniforms,common,paddock);
  let timer;
  for(const info of paddock.signs){
    const draw=board(group,info);
    if(info.normal==='west')timer=draw;
    else draw();
  }
  const update=timing=>{
    const race=timing?.[paddock.course.name];
    const status=race?.last!=null?'LAP '+race.last.toFixed(2)+' s':
      race?.splits?.length?'SPLIT '+race.splits.at(-1).toFixed(2)+' s':
      race?.start==null?'START • '+paddock.course.length_m.toFixed(0)+' m':'LAP IN PROGRESS';
    timer(status);
  };
  update();
  return {update};
}