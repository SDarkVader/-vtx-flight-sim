import * as THREE from 'three';

const vertex = `
  varying vec3 p,n;
  void main(){
    p=position;n=normal;
    gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);
  }`;

const finishes = {
  marinaMetal:`
    float joints=line(p.x,3.4,.045);
    float corrugation=cos(p.y*19.6);
    vec3 base=mix(vec3(.039,.058,.062),vec3(.135,.213,.219),abs(N.z));
    base*=.89+.10*corrugation-.17*joints;
    c=base*(.50+.58*key)*mix(1.,.66,night)+sky*(.22+.31*edge);
    c+=spill(N,V,.36);
  `,
  marinaDeck:`
    float joint=max(line(p.x,1.8,.021),line(p.y,3.3,.022));
    float brush=fbm(vec2(p.x*11.,p.y*.47)+p.z*.4);
    vec3 concrete=(vec3(.258,.246,.215)+aggregate*.14)*(.82+.23*brush);
    c=concrete*(1.-.26*joint)*(.61+.39*key)*mix(1.,.42,night);
    c+=spill(N,V,.67);
  `,
  marinaTimber:`
    float ribbons=fbm(vec2(p.y*3.8+p.z*16.,p.x*.31));
    c=vec3(.34,.19,.101)*(.56+.88*ribbons)*(1.-line(p.y,.36,.012)*.24);
    c*=mix(1.,.54,night);c+=.42*spill(N,V,.65);
  `,
  marinaBasalt:`
    float stratum=fbm(vec2(p.x*.57+p.y*.41,p.z*.83));
    float grain=texture2D(granite,vec2(p.x*.66+p.z*.40,p.y*.73)).r;
    vec3 slate=mix(vec3(.062,.078,.088),vec3(.275,.241,.181),smoothstep(.22,.76,stratum));
    c=slate*(.55+.79*grain)*(.47+.99*key)*mix(1.,.54,night)+sky*.08;
    c+=spill(N,V,.7)*.67;
  `,
  marinaGlass:`
    float along=abs(N.x)>.6?p.y:p.x;
    float frame=max(line(along,1.74,.044),line(p.z,2.42,.052));
    vec3 reflected=sky*(.43+.48*edge)+vec3(.063,.187,.212)*(.18+.33*edge);
    c=mix(reflected,vec3(.065,.075,.059)+spill(N,V,.52),frame);
    alpha=.18+.58*edge+frame*.44;
  `,
  marinaWarm:'c=vec3(2.76,1.42,.53)*mix(.62,1.,night);',
  marinaTeal:'c=vec3(.49,1.88,2.02)*mix(.50,1.,night);',
};

function makeSign(group,spec){
  const canvas=document.createElement('canvas');
  canvas.width=768;canvas.height=128;
  const g=canvas.getContext('2d');
  g.fillStyle='#131e24';g.fillRect(0,0,768,128);
  g.fillStyle='#80c3c8';g.fillRect(0,0,11,128);
  g.strokeStyle='#977950';g.lineWidth=3;g.strokeRect(26,11,720,103);
  g.fillStyle='#fee3ab';g.textAlign='center';g.textBaseline='middle';
  g.font='800 70px system-ui';g.fillText(spec.label,390,66,670);
  const map=new THREE.CanvasTexture(canvas);map.colorSpace=THREE.SRGBColorSpace;
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(spec.width,spec.height),
    new THREE.MeshBasicMaterial({map,toneMapped:false}));
  const [x,y]=spec.normal;
  mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(
    new THREE.Vector3(-y,x,0),new THREE.Vector3(0,0,1),new THREE.Vector3(x,y,0),
  ));
  mesh.position.set(...spec.point);mesh.name=spec.label;group.add(mesh);
}

function courtMarkings(group,ground,marina){
  const landing=marina.landing;
  const [x,y]=landing,vertices=[];
  const slab=(target,west,east,a,b,offset)=>{
    const rect=[[west,a],[east,a],[east,b],[west,b]].map(([x,y])=>({x,y,a:[]}));
    const strip=ground.drapeTriangles([[rect[0],rect[1],rect[2]],[rect[0],rect[2],rect[3]]],{offset});
    target.push(...strip.pos);
  };
  for(let i=-4;i<=4;i++){
    const a=y+i*.61-.138;
    slab(vertices,x+.17,1001.96,a,a+.276,.046);
  }
  const laybys=[],borders=[];
  for(const [px,py] of marina.laybys){
    slab(laybys,px-1.91,px+2.10,py-3.84,py+3.84,.029);
    slab(borders,px-1.82,px-1.67,py-3.84,py+3.84,.046);
    for(const side of [-1,1]){
      const tip=py+side*3.7;
      slab(borders,px-1.82,px+1.8,tip-.063,tip+.063,.046);
    }
  }
  for(const [name,positions,color] of [['Stair connection crossing',vertices,'#b9c6bb'],
      ['Marina drop-off pavement',laybys,'#3c4650'],['Marina drop-off markings',borders,'#d7aa6d']]){
    const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
    const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({
      color,side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:-3,polygonOffsetUnits:-4,
    }));
    mesh.name=name;group.add(mesh);
  }
}

function roadLighting(group,ground,lights,uniforms){
  const xyz=[],poles=[],inks=[];
  for(const light of lights){
    const [x,y,z]=light.position, reach=light.reach;
    const c=new THREE.Color(light.color).toArray();
    const corners=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([i,j])=>({x:x+i*reach,y:y+j*reach,a:[]}));
    const {pos}=ground.drapeTriangles([[corners[0],corners[1],corners[2]],[corners[0],corners[2],corners[3]]],
      {offset:.052});
    xyz.push(...pos);
    for(let i=0;i<pos.length;i+=3){
      poles.push(x,y,z,reach);
      inks.push(...c);
    }
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(xyz,3));
  geometry.setAttribute('pole',new THREE.Float32BufferAttribute(poles,4));
  geometry.setAttribute('ink',new THREE.Float32BufferAttribute(inks,3));
  const material=new THREE.ShaderMaterial({
    uniforms,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,side:THREE.DoubleSide,
    vertexShader:`
      attribute vec4 pole;attribute vec3 ink;
      varying vec3 p,c;varying vec4 emitter;
      void main(){
        p=position;emitter=pole;c=ink;
        gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);
      }`,
    fragmentShader:`
      varying vec3 p,c;varying vec4 emitter;uniform float night;
      void main(){
        vec3 r=emitter.xyz-p;
        float lobed=smoothstep(.19,.68,normalize(r).z);
        float falloff=1.-smoothstep(.30,1.,length(r)/emitter.w);
        float reflected=lobed*falloff*16./(8.+dot(r,r));
        gl_FragColor=vec4(c,reflected*mix(.035,.54,night));
      }`,
  });
  const pool=new THREE.Mesh(geometry,material);
  pool.name='Shore road and quay light spill';pool.renderOrder=2;group.add(pool);
}

export function buildLanternMarina(group,world,ground,uniforms,common){
  const marina=world.vaderland.lantern_marina;
  const root=new THREE.Group();root.name='Lantern Marina interchange';group.add(root);
  const lights=marina.lamps;
  const local={...uniforms,quayLamps:{value:lights.map(l=>new THREE.Vector4(...l.position,l.reach))},
    quayColors:{value:lights.map(l=>new THREE.Color(l.color))}};
  const lighting=common+`
    uniform sampler2D granite;
    uniform vec4 quayLamps[${lights.length}];
    uniform vec3 quayColors[${lights.length}];
    float line(float x,float spacing,float width){
      float edge=abs(fract(x/spacing+.5)-.5)*spacing;
      return 1.-smoothstep(width,width+max(.015,fwidth(x)),edge);
    }
    vec3 spill(vec3 N,vec3 V,float rough){
      vec3 waterLight=vec3(0.);
      for(int i=0;i<${lights.length};i++){
        vec3 r=quayLamps[i].xyz-p;
        float d2=dot(r,r),reach=quayLamps[i].w;
        if(d2>=reach*reach) continue;
        vec3 L=r*inversesqrt(max(d2,.01));
        float soft=1.-smoothstep(.45,1.,sqrt(d2)/reach);
        float lambert=max(0.,dot(L,N));
        float spec=pow(max(0.,dot(N,normalize(L+V))),mix(95.,9.,rough));
        waterLight+=quayColors[i]*soft*(.66*lambert+.44*spec)*12./(4.+d2);
      }
      return waterLight*mix(.08,.74,night);
    }
  `;
  const bySkin=new Map(Object.keys(finishes).map(skin=>[skin,[]]));
  for(const o of world.obstacles){
    if(!o.id.startsWith('marina-')||!bySkin.has(o.skin))continue;
    const points=bySkin.get(o.skin);
    for(const triangle of o.faces)for(const i of triangle){
      points.push(...o.vertices[i].map((x,axis)=>x+o.center[axis]));
    }
  }
  for(const [skin,points] of bySkin){
    const geo=new THREE.BufferGeometry();
    geo.setAttribute('position',new THREE.Float32BufferAttribute(points,3));geo.computeVertexNormals();
    const glass=skin==='marinaGlass';
    const mat=new THREE.ShaderMaterial({uniforms:local,side:THREE.DoubleSide,vertexShader:vertex,
      transparent:glass,depthWrite:!glass,
      fragmentShader:lighting+`
        void main(){
          vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;
          vec3 V=normalize(cameraPosition-p),R=reflect(-V,N);
          float edge=pow(1.-max(0.,dot(N,V)),3.4),key=max(0.,dot(sun,N));
          float aggregate=texture2D(granite,vec2((p.x+.3*p.y)*.27,(p.y+.3*p.z)*.27)).r;
          vec3 sky=mix(skySample(daySky,R),skySample(nightSky,R),night),c;
          float alpha=1.;
          ${finishes[skin]}
          gl_FragColor=vec4(haze(c),alpha);
          #include <colorspace_fragment>
        }`});
    const mesh=new THREE.Mesh(geo,mat);mesh.name='Lantern Marina '+skin;root.add(mesh);
  }
  courtMarkings(root,ground,marina);
  roadLighting(root,ground,lights,uniforms);
  for(const sign of marina.signs)makeSign(root,sign);
}

export function marinaBathymetry(world,ground){
  const area=new THREE.Vector4(555,-1450,460,420),size=160;
  const bed=new Uint8Array(size*size),level=world.harbour.waterLevelM;
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    const z=ground.terrainZ(area.x+x/(size-1)*area.z,area.y+y/(size-1)*area.w);
    bed[y*size+x]=Math.round(255*THREE.MathUtils.clamp((level-z)/8,0,1));
  }
  const map=new THREE.DataTexture(bed,size,size,THREE.RedFormat);
  map.magFilter=map.minFilter=THREE.LinearFilter;map.needsUpdate=true;
  return {marinaDepthMap:{value:map},marinaDepthArea:{value:area}};
}
