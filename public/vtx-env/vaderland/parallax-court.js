import * as THREE from 'three';
import {GLTFLoader} from '../../vendor/GLTFLoader.js';

const vertex = `
  varying vec3 p,n;
  void main(){
    p=position;
    n=normal;
    gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);
  }`;

function surveyedMesh(solids, material) {
  const pos=[],spans=[];
  for(const solid of solids){
    for(const face of solid.faces){
      for(const i of face){
        const point=solid.vertices[i];
        pos.push(point[0]+solid.center[0],point[1]+solid.center[1],point[2]+solid.center[2]);
      }
    }
    spans.push({end:pos.length/9,id:solid.id});
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
  geometry.computeVertexNormals();
  const mesh=new THREE.Mesh(geometry,material);
  mesh.userData.surveySpans=spans;
  return mesh;
}

export function buildParallaxCourt(group,world,ground,uniforms,common){
  const court=world.vaderland.parallax_court;
  const root=new THREE.Group();
  root.name='Parallax Court';
  group.add(root);
  const local={...uniforms,courtLamps:{value:court.lamps.map(p=>new THREE.Vector3(...p))}};
  const lighting=`
    uniform vec3 courtLamps[${court.lamps.length}];
    vec3 canopyLight(vec3 N,vec3 V,float rough){
      vec3 c=vec3(0.);
      for(int i=0;i<${court.lamps.length};i++){
        vec3 delta=courtLamps[i]-p;
        float d2=max(1.,dot(delta,delta));
        vec3 L=delta*inversesqrt(d2);
        float cone=smoothstep(.04,.81,L.z);
        float fall=1./(1.+d2*.058);
        float h=pow(clamp(dot(N,normalize(L+V)),0.,1.),mix(190.,24.,rough));
        c+=vec3(1.,.48,.15)*cone*fall*(max(0.,dot(N,L))*.15+h*1.9);
      }
      return c*(.18+.95*night);
    }`;
  const finishes={
    courtBark:`
      float grain=fbm(p.xy*15.+p.z*2.);
      c=mix(vec3(.034,.017,.009),vec3(.11,.064,.021),grain)+canopyLight(N,V,.6)*.27;`,
    courtShell:`
      vec3 alloy=texture2D(alloyColor,p.xy*.33).rgb;
      float seams=1.-smoothstep(.012,.056,abs(fract((p.x+p.y*.12)/3.+.5)-.5));
      vec3 top=(vec3(.010,.025,.049)+alloy*.21)*(1.-seams*.48)+refl*.39;
      float ribbon=exp(-abs(p.z-(31.1+fract(p.y*.17)*9.))*.16);
      float grain=texture2D(alloyColor,vec2(p.y*.72,(p.x+p.z)*.82)).r;
      float seamEdge=1.-smoothstep(.021,.062,abs(fract(p.y*.401+.56)-.5));
      vec3 soffit=(vec3(.011,.019,.025)+alloy*.074)*(1.-seams*.56)*(1.-seamEdge*.48);
      soffit+=refl*(.13+.11*grain)+vec3(.068,.052,.033)*grain;
      soffit+=vec3(.19,.096,.035)*(.29+ribbon*.20)*mix(.45,1.,night);
      c=mix(soffit,top,smoothstep(-.20,.28,N.z));`,
    courtBronze:`
      float g=texture2D(alloyColor,vec2((p.x+p.y*.87)*.48,p.z*.84)).r;
      c=vec3(.018,.012,.011)+vec3(.39,.17,.038)*(g*.78+.52*facing)+refl*(.20+.52*fres);
      c+=vec3(.08,.036,.009)*(1.-smoothstep(.02,1.2,abs(p.z-37.)));
      c+=vec3(.98,.43,.12)*pow(max(dot(R,sun),0.),44.);`,
    courtAmber:`c=vec3(2.07,1.09,.37)*(.40+.60*night);`,
    courtTeal:`c=vec3(.22,1.41,1.85)*(.31+.69*night);`,
    courtStone:`
      vec3 stone=texture2D(slateColor,vec2((p.x+p.y)*.41,p.z*1.42)).rgb;
      float ledge=1.-smoothstep(.007,.029,abs(fract(p.z*.82+.4)-.5));
      c=(vec3(.055,.064,.069)+stone*.33)*(1.-ledge*.27)*(mix(.8,.40,night)+facing*.29);
      c+=refl*.10+canopyLight(N,V,.7)*.44;
      if(N.z>.75)c=vec3(.032,.026,.012)+stone*.077;`,
  };
  for(const [skin,finish] of Object.entries(finishes)){
    const material=new THREE.ShaderMaterial({uniforms:local,side:THREE.DoubleSide,vertexShader:vertex,
      fragmentShader:common+lighting+`
        uniform sampler2D slateColor,alloyColor;
        void main(){
          vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;
          vec3 V=normalize(cameraPosition-p),R=reflect(-V,N);
          float facing=max(0.,dot(N,sun)),fres=pow(1.-abs(dot(N,V)),3.);
          vec3 refl=skySample(daySky,R),c;
          ${finish}
          gl_FragColor=vec4(haze(c),1.);
          #include <colorspace_fragment>
        }`});
    const mesh=surveyedMesh(world.obstacles.filter(o=>o.skin===skin),material);
    mesh.name='Parallax Court '+skin;
    root.add(mesh);
  }
  const paved=ground.drapeTriangles(court.paving.map(t=>t.map(([x,y])=>({x,y,a:[]}))),{offset:.052});
  const pavement=new THREE.BufferGeometry();
  pavement.setAttribute('position',new THREE.Float32BufferAttribute(paved.pos,3));
  pavement.setAttribute('normal',new THREE.Float32BufferAttribute(paved.nor,3));
  root.add(new THREE.Mesh(pavement,new THREE.ShaderMaterial({vertexShader:vertex,side:THREE.DoubleSide,
    polygonOffset:true,polygonOffsetFactor:-3,polygonOffsetUnits:-7,
    fragmentShader:common+lighting+`
      uniform sampler2D slateColor,slateNormal;
      uniform vec2 courtOrigin,courtAxis,courtFront;
      void main(){
        vec2 delta=p.xy-courtOrigin;
        vec2 courtXY=vec2(dot(delta,courtAxis),dot(delta,courtFront));
        vec2 uv=courtXY/2.48;
        vec3 V=normalize(cameraPosition-p);
        vec3 noise=texture2D(slateNormal,uv).rgb*2.-1.;
        float wet=smoothstep(.26,.56,fbm(courtXY*.46+vec2(.17,7.)))*.78+.15;
        vec3 N=normalize(n+vec3(noise.xy*mix(.22,.052,wet),0.));
        vec3 stone=texture2D(slateColor,uv).rgb;
        vec2 seam=abs(fract(vec2((courtXY.x+floor(courtXY.y/.98)*.54)/2.16,courtXY.y/.98)+.5)-.5);
        float grit=1.-smoothstep(.010,.032+fwidth(seam.x)*.42,min(seam.x,seam.y));
        float band=1.-smoothstep(.050,.13,abs(courtXY.x));
        float outline=1.-smoothstep(.013,.046,abs(abs(courtXY.x)-.74));
        vec3 c=(vec3(.038,.052,.066)+stone*.46)*(1.-grit*.34)*mix(1.08,.44,night);
        c+=skySample(daySky,reflect(-V,N))*pow(1.-max(0.,dot(N,V)),2.6)*mix(.21,.72,wet);
        c+=canopyLight(N,V,mix(.62,.12,wet));
        c+=vec3(.54,.25,.08)*(band*.11+outline*.24)*(.55+.65*night);
        gl_FragColor=vec4(haze(c),1.);
        #include <colorspace_fragment>
      }` ,
    uniforms:{...local,courtOrigin:{value:new THREE.Vector2(...court.door)},courtAxis:{value:new THREE.Vector2(...court.axis)},
      courtFront:{value:new THREE.Vector2(...court.front)}},
  })));

  const nameplate=document.createElement('canvas');
  nameplate.width=1400;nameplate.height=172;
  const ctx=nameplate.getContext('2d');
  ctx.fillStyle='#161b22';ctx.fillRect(0,0,1400,172);
  ctx.strokeStyle='#80562d';ctx.lineWidth=4;ctx.strokeRect(7,7,1386,158);
  ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle='#ffe3a6';
  ctx.font='600 82px "Barlow Condensed", system-ui';
  ctx.letterSpacing='11px';ctx.fillText('PARALLAX EXCHANGE',700,84,1250);
  const texture=new THREE.CanvasTexture(nameplate);
  texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=8;
  const sign=new THREE.Mesh(new THREE.PlaneGeometry(10.8,1.32),
    new THREE.MeshBasicMaterial({map:texture,side:THREE.DoubleSide}));
  const [dx,dy]=court.axis, [nx,ny]=court.front;
  sign.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(
    new THREE.Vector3(-dx,-dy,0),new THREE.Vector3(0,0,1),new THREE.Vector3(nx,ny,0)));
  sign.position.set(court.door[0]+nx*.19,court.door[1]+ny*.19,court.datum+6.41);
  root.add(sign);

  buildGarden(root,court);
  const halos=new THREE.BufferGeometry();
  halos.setAttribute('position',new THREE.Float32BufferAttribute(court.lamps.flatMap(([x,y,z])=>[x,y,z-.11]),3));
  root.add(new THREE.Points(halos,new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,
    blending:THREE.AdditiveBlending,
    vertexShader:`varying float strength;uniform float night;void main(){
      vec4 view=viewMatrix*vec4(position,1.);gl_Position=projectionMatrix*view;
      gl_PointSize=clamp(1980./max(5.,-view.z),5.,116.);
      strength=night*min(1.,11./max(4.,-view.z));}`,
    fragmentShader:`varying float strength;void main(){
      vec2 uv=gl_PointCoord*2.-1.;float r=length(uv);
      float halo=(exp(-r*r*21.)*.35+exp(-r*5.1)*.22)*(1.-smoothstep(.49,1.,r));
      gl_FragColor=vec4(1.,.56,.21,halo*strength);}` })));
  const loader=new GLTFLoader();
  const flowerAsset=new URL('./surveyed-materials/wildflowers.glb',import.meta.url);
  const ready=loader.loadAsync(flowerAsset.href).then(({scene})=>{

    scene.rotation.x=Math.PI/2;scene.updateMatrixWorld(true);
    const poses=[];
    for(const bed of court.beds){
      const count=8;
      for(let i=0;i<count;i++){
        const theta=i*2.39996+bed.seed;
        const r=.80*Math.sqrt(i/count);
        const node=new THREE.Object3D();
        node.position.set(bed.point[0]+r*bed.radii[0]*Math.cos(theta),
                          bed.point[1]+r*bed.radii[1]*Math.sin(theta),bed.point[2]-.085);
        node.scale.setScalar(1.54+.64*(.5+.5*Math.sin(i*6.1+bed.seed)));
        node.rotation.z=theta;node.updateMatrix();
        poses.push(node.matrix);
      }
    }
    scene.traverse(node=>{
      if(!node.isMesh)return;
      const material=node.material.clone();
      material.side=THREE.DoubleSide;
      if(material.map){material.transparent=false;material.alphaTest=.34;material.depthWrite=true;}
      material.color.multiplyScalar(1.32);
      const plants=new THREE.InstancedMesh(node.geometry.clone().applyMatrix4(node.matrixWorld),material,poses.length);
      poses.forEach((matrix,i)=>plants.setMatrixAt(i,matrix));
      plants.computeBoundingSphere();
      root.add(plants);
    });
  });
  return {ready};
}

export function leafyCluster(){
  const positions=[],tints=[];
  for(let i=0;i<12;i++){
    const az=i*2.39996323,f=1.-2.*(i+.5)/12;
    const out=new THREE.Vector3(Math.cos(az),Math.sin(az),f*.85).normalize();
    const side=new THREE.Vector3(-Math.sin(az),Math.cos(az),.46*Math.cos(i*5.2)).normalize();
    const center=out.clone().multiplyScalar(.42).add(new THREE.Vector3(0,0,f*.41));
    const stem=center.clone().addScaledVector(out,-.49),tip=center.clone().addScaledVector(out,.54);
    const left=center.clone().addScaledVector(side,.25),right=center.clone().addScaledVector(side,-.25);
    const crease=center.clone().add(new THREE.Vector3(0,0,.11));
    for(const [triangle,light] of [[[stem,left,crease],.75],[[left,tip,crease],1.04],
                                  [[tip,right,crease],.89],[[right,stem,crease],.63]]){
      for(const point of triangle){positions.push(...point.toArray());tints.push(light,light,light);}
    }
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  geometry.setAttribute('color',new THREE.Float32BufferAttribute(tints,3));
  geometry.computeVertexNormals();
  return geometry;
}

function buildGarden(root,court){
  const foliage=[],flower=[],node=new THREE.Object3D();
  const greens=[0x24452e,0x45633a,0x587145,0x324932,0x768352];
  const blooms=[0xb474be,0x9b4c91,0xe3a6c4,0xffba6d,0xeed8af];
  function add(batch,x,y,z,sx,sy,sz,angle,tint){
    node.position.set(x,y,z);node.rotation.set(.16,.29,angle);node.scale.set(sx,sy,sz);node.updateMatrix();
    batch.push([node.matrix.clone(),tint]);
  }
  court.beds.forEach(({point:[x,y,z],radii:[a,b],seed,tree})=>{
    for(let i=0;i<70;i++){
      const angle=i*2.39996+seed*.27,r=.81*Math.sqrt(i/70),k=.5+.5*Math.sin(i*7.24+seed);
      const px=x+Math.cos(angle)*a*r,py=y+Math.sin(angle)*b*r,h=.13+.44*k;
      if(seed===3&&r<.42)continue;
      add(foliage,px,py,z+h*.44,.22+.24*k,.20+.19*k,h,angle,greens[(i+seed)%5]);
      if(i%3===0)add(flower,px,py,z+h,.093+.047*k,.087,.061,angle,blooms[(i+seed)%5]);
    }
    if(!tree)return;
    for(let i=0;i<176;i++){
      const az=i*2.39996,d=1.-2.*i/175,r=Math.sqrt(1.-d*d),k=.5+.5*Math.sin(i*7.13+seed);
      const scale=r*(.53+.47*k);
      add(foliage,x+Math.cos(az)*a*.74*scale,y+Math.sin(az)*b*1.10*scale,
          z+2.74+d*1.25+Math.sin(az)*.25,.18+.28*k,.18+.26*k,.16+.24*k,az,greens[(i+seed+1)%5]);
    }
  });
  for(const [batch,geometry,emissive] of [[foliage,leafyCluster(),0x182b14],
                                          [flower,new THREE.IcosahedronGeometry(1,0),0x39251b]]){
    const mesh=new THREE.InstancedMesh(geometry,new THREE.MeshStandardMaterial({side:THREE.DoubleSide,
      vertexColors:!!geometry.attributes.color,roughness:.82,emissive,emissiveIntensity:.52}),batch.length);
    batch.forEach(([matrix,color],i)=>{mesh.setMatrixAt(i,matrix);mesh.setColorAt(i,new THREE.Color(color));});
    mesh.computeBoundingSphere();root.add(mesh);
  }
}

export function meridianRain(count){
  return `
    uniform vec3 avenueStorefronts[${count}];
    float rainNoise(vec2 x){
      vec2 i=floor(x),f=fract(x);
      f=f*f*(3.-2.*f);
      vec4 s=sin(vec4(dot(i,vec2(127.1,311.7)))+vec4(0.,127.1,311.7,438.8));
      vec4 r=fract(s*43758.545);
      return mix(mix(r.x,r.y,f.x),mix(r.z,r.w,f.x),f.y);
    }
    vec3 meridianAfterRain(vec3 base,vec3 p,vec3 V,vec3 bump,vec3 sky,float rough,float night){
      float section=smoothstep(2219.,2270.,p.y)*(1.-smoothstep(2425.,2480.,p.y))*
                    (1.-smoothstep(33.,46.,abs(p.x+21.)));
      if(section<.001)return base;
      float damp=smoothstep(.32,.64,rainNoise(p.xy*vec2(.61,.24))*.75+
                                             rainNoise(p.xy*vec2(1.32,.86))*.25);
      float wet=.25+.75*damp;
      vec3 N=normalize(vec3(bump.xy*(.09+rough*.06),1.));
      vec3 ray=reflect(-V,N);
      float fresnel=pow(1.-clamp(dot(N,V),0.,1.),2.4);
      vec3 c=base*mix(.74,.40,damp)+sky*(.13+fresnel*.38)*wet;
      if(ray.x>.001){
        for(int j=0;j<${count};j++){
          vec3 src=avenueStorefronts[j];
          float d=(src.x-p.x)/ray.x;
          if(d<=0.||d>260.)continue;
          vec3 hit=p+ray*d;
          float local=1.-smoothstep(4.5,16.,abs(hit.y-src.y));
          float panel=exp(-abs(hit.z-src.z)*.75)*local;
          float jamb=.28+.72*pow(.5+.5*cos(hit.y*2.5),.68);
          float lamp=exp(-abs(hit.y-src.y)*.43-abs(hit.z-src.z-1.5)*2.1);
          vec3 tint=j%3==1?vec3(.74,.33,.10):vec3(1.37,.51,.115);
          c+=tint*(panel*jamb*.35+lamp*.26)*wet*(.34+1.15*night)*(1./(1.+.0027*d));
        }
      }
      return mix(base,c,section);
    }`;
}
