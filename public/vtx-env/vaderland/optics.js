import * as THREE from 'three';
import {GLTFLoader} from '../../vendor/GLTFLoader.js';

export function marketPlanting(w){
  const beds=w.obstacles.filter(o=>o.id.startsWith('plaza-linden-')).map(o=>({
    xy:o.center.slice(0,2),z:o.center[2]-o.half[2],h:o.half[2]*2.6,anchor:o.id,
  }));
  return [...w.vaderland.quarter.trees,...beds];
}

// Linear reflection probes have the same optical orientation as the photographed skies.
export function surveyedOptics(group,w,uniforms){
  const base=new URL('./surveyed-materials/',import.meta.url),loader=new THREE.TextureLoader();
  const tasks=[],textures=[],materials=new Map(),subsets=[],env={},spots=[],marketTrees=[];
  const url=file=>new URL(file,base).href;
  function load(name,file,srgb=false,tile=true){
    let tex;tasks.push(new Promise((resolve,reject)=>{tex=loader.load(url(file),resolve,undefined,reject);}));
    tex.colorSpace=srgb?THREE.SRGBColorSpace:THREE.NoColorSpace;
    tex.anisotropy=16;if(tile)tex.wrapS=tex.wrapT=THREE.RepeatWrapping;
    textures.push(tex);uniforms[name]={value:tex};
    return tex;
  }
  for(const k of ['asphalt','slate','alloy']){
    load(k+'Color',k+'-base.webp',true);load(k+'Normal',k+'-normal.webp');load(k+'Rough',k+'-rough.webp');
  }
  load('ceramic','facade-base.webp',true);
  for(const k of ['day','night']){
    load(k+'Sky','sky-'+k+'.webp',true,false);
    tasks.push(fetch(url('probe-'+k+'.f16')).then(r=>{if(!r.ok)throw Error('Missing reflection probe');return r.arrayBuffer();}).then(raw=>{
      const tex=new THREE.DataTexture(new Uint16Array(raw),512,256,THREE.RGBAFormat,THREE.HalfFloatType);
      tex.mapping=THREE.EquirectangularReflectionMapping;tex.colorSpace=THREE.LinearSRGBColorSpace;
      tex.magFilter=tex.minFilter=THREE.LinearFilter;tex.needsUpdate=true;env[k]=tex;textures.push(tex);
    }));
  }
  const specs={
    blacksteel:['alloy',0x8091a4,.92,.61],crestgold:['alloy',0xffbb61,.94,.42],
    crestsilver:['alloy',0xc8d2db,.90,.46],blade:['alloy',0x777d89,.88,.60],
    vault:['alloy',0xb1ab9f,.81,.61],sandstone:['slate',0xa99a88,.17,.84],
    basalt:['slate',0x85888d,.16,.84],planterstone:['slate',0xa39d92,.19,.80],
    pavestone:['slate',0xb1a89c,.08,.88],canopy:['alloy',0xd0b79a,.69,.66],
  };
  function material(skin){
    if(skin==='city17signal')return new THREE.MeshBasicMaterial({color:new THREE.Color(.38,1.7,1.65),toneMapped:false});
    if(skin==='lamplens')return new THREE.MeshBasicMaterial({color:new THREE.Color(3.7,2.55,1.25),toneMapped:false});
    if(!specs[skin])return null;
    if(materials.has(skin))return materials.get(skin);
    const [k,tint,metalness,roughness]=specs[skin];
    const m=new THREE.MeshStandardMaterial({color:tint,map:uniforms[k+'Color'].value,normalMap:uniforms[k+'Normal'].value,
      roughnessMap:uniforms[k+'Rough'].value,metalness,roughness,side:THREE.DoubleSide,envMapIntensity:1.25});
    m.normalScale.setScalar(k==='alloy'?.24:.66);materials.set(skin,m);return m;
  }
  const lamps=w.vaderland.frontage.lights.map(v=>({...v}));
  const portLights=[], lightMetal=[];
  for(const lamp of w.vaderland.speedway?.lights??[]){
    lamps.push({xyz:lamp.xyz,site:lamp.sign>0?'velocityCyan':'velocityViolet',size:.36,station:lamp.station_m});
  }
  for(const d of w.vaderland.operations.annex.doors){
    const [x,y,z]=d.center,sign=d.id==='west'?-1:1;
    // Light channels sit on the front skin of the actual brass pupil and fixed outer bezel.
    // Each small break is a housing joint. Both surfaces leave the clear aperture untouched.
    const shellX=x+sign*1.055;
    for(const [rad,width,segments,active,tint] of [[12.38,.145,40,40,0xffae51],[17.98,.104,56,56,0xb98343],[13.90,.19,44,10,0x74edec]]){
      const coords=[];
      for(let j=0;j<active;j++){
        const start=j/segments*2*Math.PI+(active<segments?.92:0),end=start+2*Math.PI/segments*.975;
        const pair=a=>[-1,1].map(s=>[shellX+sign*.009,y+(rad+s*width/2)*Math.cos(a),z+(rad+s*width/2)*Math.sin(a)]);
        for(let k=0;k<4;k++){
          const a=pair(start+(end-start)*k/4),b=pair(start+(end-start)*(k+1)/4);
          coords.push(...a[0],...a[1],...b[1],...a[0],...b[1],...b[0]);
        }
      }
      const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(coords,3));
      const mat=new THREE.MeshBasicMaterial({color:tint,side:THREE.DoubleSide,toneMapped:false});
      lightMetal.push({mat,tint});group.add(new THREE.Mesh(geo,mat));
    }
    for(const side of [-1,1]){
      const spot=new THREE.SpotLight(side<0?0xffbc70:0x93b8e8,12000,65,.87,.7,2);
      spot.position.set(x+sign*8.8,y+side*17.4,z-15.2);
      spot.target.position.set(x,y+side*5.7,z+3);group.add(spot,spot.target);portLights.push(spot);
    }
    for(let i=0;i<28;i++){
      const a=i*Math.PI/14,r=12.52;
      lamps.push({xyz:[x+sign*1.05,y+r*Math.cos(a),z+r*Math.sin(a)],site:i>4&&i<10?'irisStatus':'iris',size:.19});
    }
  }
  for(const dock of w.obstacles.filter(o=>o.id.startsWith('deck-airport-landing-'))){
    const [x,y,z]=dock.center,[a,b,h]=dock.half;
    for(const s of [-1,1])for(const off of [-.78,.78]){
      lamps.push({xyz:[x+s*(a-.13),y+off*b,z+h+.025],site:'quay',size:.18});
    }
  }
  const colors={frontage:['#ffe4a4','#ffae4b'],plaza:['#ffd69c','#aa86ff'],iris:['#ffda85','#ffae46'],
    irisStatus:['#bbfff2','#59eadc'],quay:['#9fe6dd','#4ad3e4'],
    velocityCyan:['#e8f4e6','#67e8ff'],velocityViolet:['#f8dfb5','#cf86ff']};
  const vertices=[],c0=[],c1=[],sizes=[],phase=[];
  lamps.forEach((l,i)=>{
    vertices.push(...l.xyz);for(const [k,arr] of [[0,c0],[1,c1]])new THREE.Color(colors[l.site][k]).toArray(arr,arr.length);
    sizes.push(l.size);phase.push(l.station!==undefined?l.station/76:l.site==='irisStatus'?i*.21:l.site==='quay'?1.2:-1);
    if(l.site==='plaza'){
      const light=new THREE.SpotLight(0xffd29a,16500,101,.81,.68,2);
      light.position.set(...l.xyz);light.position.z+=.10;
      light.target.position.set(-183+(l.xyz[0]+183)*.35,2325,58.5);group.add(light,light.target);spots.push(light);
    }
  });
  const g=new THREE.BufferGeometry();
  for(const [key,array,n] of [['position',vertices,3],['daylight',c0,3],['afterdark',c1,3],['radius',sizes,1],['phase',phase,1]])
    g.setAttribute(key,new THREE.Float32BufferAttribute(array,n));
  const glare=new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,depthTest:true,blending:THREE.AdditiveBlending,
    vertexShader:`uniform float night;uniform float sceneryClock;attribute vec3 daylight;attribute vec3 afterdark;attribute float radius;
      attribute float phase;varying vec3 lightColor;varying float strength;
      void main(){vec4 q=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*q;
        lightColor=mix(daylight,afterdark,night);float range=length(q.xyz);
        strength=(.68+.67*night)*(phase<0.?1.:.90+.10*sin(sceneryClock*1.17+phase));
        gl_PointSize=clamp((6100.+night*2600.)*radius/max(3.,range),3.,138.);}`,
    fragmentShader:`varying vec3 lightColor;varying float strength;
      void main(){vec2 uv=gl_PointCoord*2.-1.;float r=length(uv);if(r>=1.)discard;
        float core=exp(-r*r*175.);float halo=exp(-r*6.3)*.32;
        float streak=exp(-abs(uv.y)*90.)*exp(-abs(uv.x)*5.1)*.26;
        float diffraction=.08*exp(-abs(uv.y-uv.x)*51.)*exp(-r*9.);
        gl_FragColor=vec4(lightColor*2.6+core*.93,(core+halo+streak+diffraction)*strength*(1.-smoothstep(.66,1.,r)));}`});
  const sources=new THREE.Points(g,glare);sources.renderOrder=6;group.add(sources);
  // Scanned living plants stand inside the solid landscape beds. Foliage LODs use the same roots.
  const gltf=new GLTFLoader();
  for(const [kind,size] of [['heath',2.96],['wildflowers',1.64],['street-tree',1]]){
    tasks.push(gltf.loadAsync(url(kind+'.glb')).then(({scene})=>{
      scene.rotation.x=Math.PI/2;scene.updateMatrixWorld(true);
      const objects=[];scene.traverse(n=>{if(n.isMesh)objects.push(n);});
      for(const n of objects){
        const geom=n.geometry.clone().applyMatrix4(n.matrixWorld),poses=[];
        if(kind==='street-tree')for(const [i,tree] of w.vaderland.frontage.trees.entries()){
          const node=new THREE.Object3D();node.position.set(...tree.center);node.rotation.z=i*2.09;
          node.scale.setScalar(tree.height);node.updateMatrix();poses.push(node.matrix);
        }
        else for(const [j,bed] of w.vaderland.frontage.beds.entries()){
          const [x,y,z]=bed.center,[a,b]=bed.half,count=kind==='heath'?4:8;
          for(let i=0;i<count;i++){
            const angle=(j*1.7+i*2.4),s=size*(.76+.23*(1+Math.sin(i*6.2+j)));
            const node=new THREE.Object3D();node.position.set(x+(i/(count-1)-.5)*a*1.45,y+Math.sin(angle)*b*.51,z-.02);
            node.rotation.z=angle;node.scale.setScalar(s);node.updateMatrix();poses.push(node.matrix);
          }
        }
        const leafMaterials=Array.isArray(n.material)?n.material:[n.material];
        for(const mat of leafMaterials)if(mat.transparent&&mat.map){mat.transparent=false;mat.alphaTest=.27;mat.depthWrite=true;mat.side=THREE.DoubleSide;}
        const mesh=new THREE.InstancedMesh(geom,n.material,poses.length);poses.forEach((p,i)=>mesh.setMatrixAt(i,p));
        mesh.computeBoundingSphere();group.add(mesh);subsets.push(mesh);
        if(kind==='street-tree'&&w.vaderland.quarter){
          const trees=marketPlanting(w);
          const urban=new THREE.InstancedMesh(geom,n.material,trees.length);
          urban.count=0;urban.frustumCulled=false;urban.instanceMatrix.setUsage(THREE.DynamicDrawUsage);group.add(urban);
          const matrices=trees.map((t,i)=>{
            const object=new THREE.Object3D();object.position.set(...t.xy,t.z);object.rotation.z=i*2.41;
            object.scale.setScalar(t.h);object.updateMatrix();return object.matrix;
          });
          marketTrees.push({urban,trees,matrices});
        }
      }
    }));
  }
  const velocity=w.vaderland.speedway?.lights??[];
  const roadLights=velocity.length?Array.from({length:4},()=>{
    const light=new THREE.PointLight(0xe7f4ff,2800,112,2);group.add(light);return light;
  }):[];
  let mood,lastRoadPosition=null,lastTreePosition=null;
  function update(mode,cam,t){
    uniforms.sceneryClock.value=t;
    const probe=env[mode==='dusk'?'day':mode];
    if(mood!==mode&&probe){
      mood=mode;
      for(const m of materials.values()){m.envMap=probe;m.envMapIntensity=mode==='night'?2.9:mode==='dusk'?1.9:1.55;m.needsUpdate=true;}
      spots.forEach((s,i)=>{s.color.set(mode==='night'?['#ffc176','#82c6f0','#ca82fa','#facda3'][i]:'#ffcf96');s.intensity=mode==='night'?22500:mode==='dusk'?18600:12000;});
      portLights.forEach(s=>{s.intensity=mode==='night'?20500:mode==='dusk'?16200:9800;});
      for(const {mat,tint} of lightMetal)mat.color.setHex(tint).multiplyScalar(mode==='night'?2.9:1.16);
      for(const n of subsets){for(const m of (Array.isArray(n.material)?n.material:[n.material])){m.envMap=probe;m.envMapIntensity=1.25;m.needsUpdate=true;}}
    }
    const nearPlaza=Math.hypot(cam.position.x+183,cam.position.y-2325)<900;
    spots.forEach(s=>{s.visible=nearPlaza;});
    const nearPortal=Math.hypot(cam.position.x-1000,cam.position.y+325)<350;
    portLights.forEach(s=>{s.visible=nearPortal;});
    for(const n of subsets)n.visible=nearPortal;
    if(marketTrees.length&&(!lastTreePosition||cam.position.distanceToSquared(lastTreePosition)>25)){
      lastTreePosition=cam.position.clone();
      for(const {urban,trees,matrices} of marketTrees){
        let count=0;
        for(const [i,tree] of trees.entries()){
          if(Math.hypot(cam.position.x-tree.xy[0],cam.position.y-tree.xy[1],cam.position.z-tree.z)<154)
            urban.setMatrixAt(count++,matrices[i]);
        }
        urban.count=count;urban.instanceMatrix.needsUpdate=true;
      }
    }
    if(roadLights.length && (!lastRoadPosition || cam.position.distanceToSquared(lastRoadPosition)>36)){
      lastRoadPosition=cam.position.clone();
      const nearest=velocity.map(l=>({l,d:cam.position.distanceToSquared(new THREE.Vector3(...l.xyz))})).sort((a,b)=>a.d-b.d);
      roadLights.forEach((light,j)=>{
        const {l,d}=nearest[j];light.position.set(...l.xyz);
        light.color.set(l.sign>0?'#acf0ff':'#d6baff');light.visible=d<112*112;
      });
    }
    for(const lamp of roadLights)lamp.intensity=mode==='night'?3400:280;
  }
  return {material,ready:Promise.all(tasks),update,dispose(){textures.forEach(t=>t.dispose());}};
}
