import * as THREE from 'three';

// The same authored faces supply both the native convex meshes and the visible room.
export function buildInstrumentRoom(group, world, uniforms, common) {
  const room = world.vaderland.instrument_room;
  const root = new THREE.Group();
  root.name = 'Parallax Instrument Room';
  group.add(root);
  const [axis, front] = room.basis.map(v=>new THREE.Vector3(...v));
  const origin = new THREE.Vector3(...room.origin);
  function point(u,d,z){
    return origin.clone().addScaledVector(axis,u).addScaledVector(front,d).add(new THREE.Vector3(0,0,z));
  }

  const lights = room.lights.map(([u,d,z])=>point(u,d,z));
  const rotation = new Map(), batches = new Map(), materials = new Map();
  const clock = {value:0};
  const roomUniforms = {
    ...uniforms, roomLamps:{value:lights}, roomTime:clock,
    roomOrigin:{value:origin}, roomAxis:{value:axis}, roomFront:{value:front},
  };
  const vertex = `
    attribute vec2 dialCoord;
    varying vec2 dialUV;
    varying vec3 p,n;
    void main(){
      vec4 world=modelMatrix*vec4(position,1.);
      p=world.xyz;
      dialUV=dialCoord;
      n=normalize(mat3(modelMatrix)*normal);
      gl_Position=projectionMatrix*viewMatrix*world;
    }`;
  const lightCode = `
    uniform vec3 roomLamps[${lights.length}],roomOrigin,roomAxis,roomFront;
    uniform float roomTime;
    varying vec2 dialUV;
    vec3 illumination(vec3 N,vec3 V,float rough){
      vec3 result=vec3(0.);
      for(int i=0;i<${lights.length};i++){
        vec3 source=roomLamps[i]-p;
        float d2=max(.20,dot(source,source));
        vec3 L=source*inversesqrt(d2),H=normalize(V+L);
        float hot=pow(max(dot(N,H),0.),mix(130.,12.,rough));
        float shade=max(0.,dot(N,L));
        vec3 colour=i<9 ? vec3(1.0,.52,.19) : i<14 ? vec3(.18,.80,1.0) : vec3(1.0,.55,.21);
        result+=colour*(shade*.73+hot*mix(1.4,.45,rough))/(1.+.80*d2);
      }
      return result*mix(.63,1.10,night);
    }`;
  function dial(accent){
    return `
      float r=length(dialUV),a=atan(dialUV.y,dialUV.x);
      float tick=1.-smoothstep(.08,.16,abs(fract(a/tau*38.+.5)-.5));
      float major=1.-smoothstep(.06,.15,abs(fract(a/tau*9.+.5)-.5));
      float scale=tick*(smoothstep(.71,.78,r)-smoothstep(.90,.94,r))+
                  major*(smoothstep(.60,.67,r)-smoothstep(.89,.93,r))*.70;
      float pointer=1.4+.61*sin(roomTime*.79+local.x*.83)+.16*sin(roomTime*2.4);
      float needle=exp(-abs(sin(a-pointer))*63.)*smoothstep(.08,.12,r)*
                   (1.-smoothstep(.74,.87,r))*step(0.,cos(a-pointer));
      float axle=1.-smoothstep(.074,.101,r);
      float edge=exp(-abs(r-.94)*96.);
      c=vec3(.014,.032,.042)+refl*.06;
      c+=${accent}*(scale*.72+needle*.81+edge*.38);
      c+=vec3(.74,.37,.10)*axle;
    `;
  }
  const finish = {
    roomDial0: dial('vec3(.12,.76,1.18)'),
    roomDial1: dial('vec3(1.11,.50,.14)'),
    roomFloor:`
      vec2 tiles = local.xy+vec2(floor(local.y/.88)*.71,0.);
      vec2 joints=abs(fract(tiles/vec2(1.42,.88)+.5)-.5);
      float seam=1.-smoothstep(.013,.028,min(joints.x,joints.y));
      vec3 stone=texture2D(slateColor,local.xy/2.28).rgb;
      float sweep=length(local.xy-vec2(-4.18,-5.57));
      float inlay=1.-smoothstep(.023,.045,min(abs(sweep-2.21),abs(sweep-2.38)));
      c=(vec3(.021,.025,.025)+stone*.26)*(1.-.55*seam);
      float contact=smoothstep(1.60,2.08,sweep);
      float wall=smoothstep(.04,.86,min(8.72-abs(local.x),local.y+11.01));
      c*=vec3(.46,.53,.63)*mix(.57,1.,contact*wall)+illumination(N,V,.37)*.18;
      c+=illumination(N,V,.20)*.32*contact+refl*fres*.18;
      if(N.z>.81&&R.z>.022){
        vec2 grain=texture2D(slateColor,local.xy*.72).rg-.5;
        vec2 mirror=local.xy+(5.345-local.z)*
                    (vec2(dot(R,roomAxis),dot(R,roomFront))+grain*.024)/R.z;
        vec2 dist=mirror-vec2(-2.2,-5.8);
        float arc=abs(length(dist)-2.92);
        float glow=exp(-arc*10.)*.31+exp(-arc*32.)*.36;
        float gap=smoothstep(.08,.19,fract(atan(dist.y,dist.x)*36./tau+.5));
        c+=vec3(1.,.45,.116)*glow*gap*(.32+.61*fres)*contact;
      }
      c=mix(c,vec3(.25,.115,.034)+illumination(N,V,.32)*.21,inlay*.79);`,
    roomStone:`
      vec2 uv=vec2(local.x+local.y,local.z)/1.45;
      if(abs(N.z)>.65)uv=local.xy/2.15;
      vec3 slate=texture2D(slateColor,uv).rgb;
      vec2 join=abs(fract(uv*vec2(.54,1.07)+.5)-.5);
      float seam=1.-smoothstep(.007,.028,min(join.x,join.y));
      c=(vec3(.017,.021,.027)+slate*vec3(.11,.097,.089))*(1.-seam*.56);
      float corner=smoothstep(.019,.89,min(max(0.,8.75-abs(local.x)),max(0.,local.y+11.10)));
      c*=mix(.34,.60,corner)+illumination(N,V,.60)*.78;
      c+=illumination(N,V,.68)*.075+refl*.036;`,
    roomMetal:`
      vec3 alloy=texture2D(alloyColor,vec2((local.x+local.y)*.67,local.z*1.76)).rgb;
      float edge=fbm(local.xy*19.+local.z*1.2);
      c=(vec3(.013,.022,.036)+alloy*.16)*(.62+.31*edge);
      c+=illumination(N,V,.39)*.33+refl*(.058+.34*fres);`,
    roomBronze:`
      float grain=texture2D(alloyColor,vec2((local.x+local.y)*1.21,local.z*1.4)).r;
      vec3 gold=vec3(.30,.20,.075);
      c=gold*(.29+.61*grain)*(vec3(.45,.43,.40)+illumination(N,V,.29)*1.8);
      vec3 raking=normalize(vec3(-.37,-.55,.75));
      float polished=pow(max(0.,dot(R,raking)),mix(72.,26.,grain));
      c+=refl*gold*(.27+.98*fres)+illumination(N,V,.20)*gold*.91;
      c+=vec3(.92,.62,.32)*polished*.74;`,
    roomWood:`
      float tone=fbm(vec2((local.x+local.y)*1.09,local.z*19.4+local.y*5.1));
      float knots=fbm(vec2(local.x*.28,local.y*1.95+local.z*4.41));
      c=mix(vec3(.055,.019,.010),vec3(.19,.082,.036),tone*.76+knots*.24);
      c*=.60+illumination(N,V,.45)*.90;
      c+=illumination(N,V,.36)*.096+refl*fres*.13;`,
    roomWarm:`c=vec3(2.43,1.33,.61)*mix(.53,1.,night);`,
    roomCyan:`
      float scan=.83+.17*sin(local.z*166.+roomTime*3.);
      c=vec3(.10,1.10,1.62)*scan*mix(.53,1.,night);`,
    roomOptic:`
      float mist=fbm(local.yz*30.);
      vec3 coated=vec3(.033,.13,.18)+vec3(.14,.043,.17)*fres;
      float ring=exp(-abs(N.z*.67+N.y*.43+R.z*.27)*4.4);
      c=coated+refl*(.33+.70*fres)+vec3(.12,.28,.32)*ring;
      alpha=.19+.41*fres+mist*.045;`,
    roomGlass:`
      float texture=fbm(local.xz*15.);
      float streak=pow(fbm(vec2(local.x*9.7,local.z*.39)),5.);
      float glancing=smoothstep(.31,1.,fres);
      c=vec3(.020,.048,.078)+refl*(.34+.31*fres)+vec3(.19,.13,.092)*streak;
      alpha=.071+.26*glancing+.045*texture+.16*streak;
      c+=illumination(N,V,.26)*.11;`,
  };
  function material(skin) {
    if(materials.has(skin))return materials.get(skin);
    const glass = skin === 'roomGlass' || skin === 'roomOptic';
    const result = new THREE.ShaderMaterial({
      uniforms:roomUniforms, vertexShader:vertex, side:glass?THREE.FrontSide:THREE.DoubleSide,
      transparent:glass, depthWrite:!glass,
      fragmentShader:common+lightCode+`
        uniform sampler2D slateColor,alloyColor;
        void main(){
          vec3 N=normalize(n);
          if(!gl_FrontFacing)N=-N;
          vec3 V=normalize(cameraPosition-p),R=reflect(-V,N);
          vec3 offset=p-roomOrigin,local=vec3(dot(offset,roomAxis),dot(offset,roomFront),offset.z);
          float fres=pow(1.-abs(dot(N,V)),3.);
          vec3 refl=skySample(daySky,R),c;
          float alpha=1.;
          ${finish[skin]}
          gl_FragColor=vec4(haze(c),alpha);
          #include <colorspace_fragment>
        }`,
    });
    materials.set(skin,result);
    return result;
  }
  for(const o of world.obstacles){
    if(!o.id.startsWith('instrument-'))continue;
    const motion=o.motion,key=(motion?.name??'fixed')+'/'+o.skin;
    if(motion&&!rotation.has(motion.name)){
      const pivot=new THREE.Group();
      pivot.position.set(...motion.origin);
      root.add(pivot);
      rotation.set(motion.name,{pivot,motion});
    }
    if(!batches.has(key))batches.set(key,{skin:o.skin,positions:[],dial:[],spans:[],motion});
    const batch=batches.get(key),offset=motion?.origin??[0,0,0];
    const isDial=o.skin.startsWith('roomDial');
    const radius=o.half[2];
    for(const face of o.faces)for(const i of face){
      const v=o.vertices[i];
      batch.positions.push(...v.map((x,k)=>x+o.center[k]-offset[k]));
      if(isDial)batch.dial.push((axis.x*v[0]+axis.y*v[1])/radius,v[2]/radius);
    }
    batch.spans.push({end:batch.positions.length/9,id:o.id});
  }
  for(const {skin,positions,dial,spans,motion} of batches.values()){
    const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
    if(dial.length)geometry.setAttribute('dialCoord',new THREE.Float32BufferAttribute(dial,2));
    geometry.computeVertexNormals();
    const mesh=new THREE.Mesh(geometry,material(skin));
    mesh.name='Instrument room '+skin;
    mesh.userData.surveySpans=spans;
    (motion?rotation.get(motion.name).pivot:root).add(mesh);
  }

  const label=document.createElement('canvas');
  label.width=990;label.height=166;
  const ctx=label.getContext('2d');
  ctx.fillStyle='#14161b';ctx.fillRect(0,0,label.width,label.height);
  ctx.strokeStyle='#826635';ctx.lineWidth=6;ctx.strokeRect(8,8,974,150);
  ctx.fillStyle='#ffaa67';ctx.font='600 72px "Barlow Condensed",system-ui';
  ctx.textAlign='center';ctx.textBaseline='middle';ctx.letterSpacing='6px';
  ctx.fillText('INSTRUMENT ROOM',495,81,910);
  const text=new THREE.CanvasTexture(label);
  text.colorSpace=THREE.SRGBColorSpace;text.anisotropy=8;
  const sign=new THREE.Mesh(new THREE.PlaneGeometry(2.36,.395),new THREE.MeshBasicMaterial({map:text}));
  sign.position.copy(point(0,.097,3.83));
  sign.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(
    axis.clone().negate(),new THREE.Vector3(0,0,1),front));
  root.add(sign);

  return {
    update(t){
      clock.value=t;
      for(const {pivot,motion} of rotation.values())pivot.rotation.z=2*Math.PI*t/motion.period_s;
    },
  };
}
