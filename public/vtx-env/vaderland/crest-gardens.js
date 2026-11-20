import * as THREE from 'three';
import {leafyCluster} from './parallax-court.js';

const vertex='varying vec3 p,n;void main(){p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}';

function shellGeometry(solids){
  const xyz=[];
  for(const o of solids)for(const face of o.faces)for(const i of face){
    const v=o.vertices[i];xyz.push(v[0]+o.center[0],v[1]+o.center[1],v[2]+o.center[2]);
  }
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(xyz,3));geo.computeVertexNormals();
  return geo;
}

function plantTrees(root,trees,uniforms,spill){
  const palettes=[['#295129','#57763d','#86a252'],['#66512f','#967a40','#bd974c'],
    ['#31534c','#46735f','#799978']].map(set=>set.map(hex=>new THREE.Color(hex)));
  const material=new THREE.ShaderMaterial({vertexColors:true,side:THREE.DoubleSide,uniforms,
    vertexShader:`
      varying vec3 p,n,leafTint;
      void main(){
        p=(instanceMatrix*vec4(position,1.)).xyz;
        n=mat3(instanceMatrix)*normal;
        leafTint=instanceColor*color;
        gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);
      }`,
    fragmentShader:spill+`
      varying vec3 leafTint;
      void main(){
        vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;
        vec3 V=normalize(cameraPosition-p);
        float sunSide=max(0.,dot(N,sun));
        float skySide=.55+.45*max(0.,N.z);
        float duskSide=pow(1.-abs(dot(N,V)),3.);
        vec3 lit=vec3(.79,.88,1.15)*skySide*mix(.68,.36,night);
        lit+=vec3(1.,.79,.54)*(sunSide*mix(.62,.10,night)+duskSide*.15);
        vec3 c=leafTint*(lit+1.2*lampLight(N,V,.75));
        gl_FragColor=vec4(haze(c),1.);
        #include <colorspace_fragment>
      }`});
  const clusters=214,group=new THREE.InstancedMesh(leafyCluster(),material,clusters*trees.length);
  const node=new THREE.Object3D(),color=new THREE.Color();
  trees.forEach(({position:[x,y,z],height,turn,kind},tree)=>{
    const width=[.32,.27,.25][kind],depth=[.23,.27,.31][kind];
    for(let i=0;i<clusters;i++){
      const angle=i*2.39996323+turn,c=Math.cos(angle),s=Math.sin(angle);
      const elevation=1-2*(i+.5)/clusters,ring=Math.sqrt(1-elevation*elevation);
      const jitter=.5+.5*Math.sin(i*7.13+turn),radius=ring*(.62+.38*jitter);
      node.position.set(x+c*height*width*radius,y+s*height*width*radius*.9,
        z+height*(.66+depth*elevation+.036*Math.sin(4*angle)));
      node.rotation.set(.24*Math.sin(angle),.35*Math.cos(angle),angle);
      const size=height*(.038+.034*jitter);
      node.scale.set(size,size*(.8+.2*jitter),size*.78);node.updateMatrix();
      const index=tree*clusters+i,shading=.5+.5*elevation;
      group.setMatrixAt(index,node.matrix);
      const [dark,mid,light]=palettes[kind];
      color.copy(dark).lerp(mid,Math.min(1,1.5*shading)).lerp(light,.46*jitter*shading);
      group.setColorAt(index,color);
    }
  });
  group.name='Crest Gardens trees';
  group.computeBoundingSphere();root.add(group);
}

function lowMist(root,cells,uniforms){
  const quad=new THREE.PlaneGeometry(),geo=new THREE.InstancedBufferGeometry(),records=[];
  geo.setIndex(quad.index);
  for(const key of ['position','uv'])geo.setAttribute(key,quad.attributes[key]);
  for(const cell of cells)for(let i=0;i<cell.count;i++){
    const {r,g,b}=new THREE.Color(cell.tint);
    records.push({origin:cell.center,mistExtent:[...cell.spread,...cell.size],drift:cell.drift,tint:[r,g,b],
      seed:[(i+.5)/cell.count,.5+.5*Math.sin(i*23.37)]});
  }
  for(const [key,count] of Object.entries({origin:3,mistExtent:4,drift:2,tint:3,seed:2})){
    geo.setAttribute(key,new THREE.InstancedBufferAttribute(Float32Array.from(records.flatMap(v=>v[key])),count));
  }
  geo.instanceCount=records.length;
  const mat=new THREE.ShaderMaterial({uniforms,transparent:true,depthWrite:false,
    vertexShader:[
      'attribute vec2 seed,drift;attribute vec3 origin,tint;attribute vec4 mistExtent;uniform float clock;',
      'varying vec2 st;varying float fade,grain;varying vec3 color;',
      'void main(){float phase=fract(seed.x+clock*.023);vec3 q=origin;',
      'q.xy+=vec2((phase-.5)*mistExtent.x*2.,(seed.y-.5)*mistExtent.y*2.)+drift*sin(clock*.23+seed.y*6.283);',
      'q.z+=seed.y*.68+.14*sin(clock*.39+seed.x*6.28);',
      'vec4 pt=viewMatrix*vec4(q,1.);float d=max(1.,-pt.z);pt.xy+=position.xy*mistExtent.zw*(.65+seed.y*.55);',
      'fade=sin(phase*3.14159)*smoothstep(.8,5.,d)*(1.-smoothstep(165.,340.,d));',
      'grain=seed.y;color=tint;st=uv;gl_Position=projectionMatrix*pt;}',
    ].join('\n'),
    fragmentShader:[
      'uniform float clock,night;varying vec2 st;varying float fade,grain;varying vec3 color;',
      'void main(){vec2 uv=2.*st-1.;float a=max(0.,1.-dot(uv,uv));',
      'float curl=.54+.46*sin(uv.x*4.+uv.y*2.+grain*12.+clock*.26);',
      'gl_FragColor=vec4(color*(.48+.44*night),a*a*curl*fade*(.12+.07*night));',
      '#include <colorspace_fragment>','}',
    ].join('\n')});
  const patch=new THREE.Mesh(geo,mat);
  patch.name='Crest Gardens drifting mist';patch.frustumCulled=false;patch.renderOrder=4;root.add(patch);
  return patch;
}

export function buildCrestGardens(group,world,ground,uniforms,common){
  const park=world.vaderland.crest_gardens,[x,y]=park.center;
  const root=new THREE.Group();root.name='Crest Gardens';group.add(root);
  const local={...uniforms,gardenCenter:{value:new THREE.Vector2(x,y)},
    lampPos:{value:park.lamps.map(l=>new THREE.Vector4(...l.position,l.range_m))},
    lampInk:{value:park.lamps.map(l=>new THREE.Color(l.color))}};
  const lampCount=park.lamps.length;
  const spill=common+[
    'uniform vec2 gardenCenter;uniform float clock;',
    'uniform vec4 lampPos['+lampCount+'];uniform vec3 lampInk['+lampCount+'];',
    'uniform sampler2D slateColor,alloyColor;',
    'vec3 lampLight(vec3 N,vec3 V,float rough){vec3 result=vec3(0.);',
    'for(int i=0;i<'+lampCount+';i++){vec3 delta=lampPos[i].xyz-p;float d2=dot(delta,delta);',
    'float cutoff=1.-smoothstep(.62,1.,sqrt(d2)/lampPos[i].w);',
    'if(cutoff>.001){vec3 L=delta*inversesqrt(max(d2,.0001));',
    'float cone=smoothstep(-.12,.64,L.z),cosine=max(0.,dot(N,L));',
    'float sheen=pow(max(0.,dot(N,normalize(L+V))),mix(110.,11.,rough));',
    'result+=lampInk[i]*cutoff*cone*(9./(1.7+d2))*(.36*cosine+1.6*sheen);}}',
    'return result*mix(.13,1.,night);}',
  ].join('\n');
  function surface(name,geo,code,opts={}){
    const material=new THREE.ShaderMaterial({vertexShader:vertex,side:THREE.DoubleSide,uniforms:local,
      fragmentShader:spill+'void main(){vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;'+
      'vec3 V=normalize(cameraPosition-p),R=reflect(-V,N);float key=max(0.,dot(N,sun));vec3 c;'+
      code+'\n#include <colorspace_fragment>\n}',...opts});
    const object=new THREE.Mesh(geo,material);object.name=name;root.add(object);
  }
  const solids=world.obstacles.filter(o=>o.id.startsWith('crest-gardens-'));
  function shell(skin){return shellGeometry(solids.filter(o=>o.skin===skin));}
  const finishes={gardenSteel:['.032,.051,.070',.28],gardenStone:['.29,.235,.172',.65],
    gardenBronze:['.39,.217,.090',.37],gardenWood:['.24,.098,.063',.59]};
  for(const [skin,[rgb,rough]] of Object.entries(finishes)){
    surface(skin,shell(skin),'float grain=texture2D(alloyColor,vec2((p.x+p.y)*.28,p.z*.56)).r;'+
      'c=vec3('+rgb+')*(.73+.46*grain)*mix(.42+.52*key,.19+.21*key,night);'+
      'c+=skySample(daySky,R)*(.13+.19*'+(1-rough)+');'+
      'c+=lampLight(N,V,'+rough+');gl_FragColor=vec4(haze(c),1.);');
  }
  surface('Crest Gardens tree trunks',shell('gardenBark'),
    'float bark=fbm(vec2((p.x+p.y)*20.,p.z*.8));'+
    'c=vec3(.27,.18,.10)*(.65+.81*bark)*mix(.55+.51*key,.26+.27*key,night);'+
    'c+=lampLight(N,V,.89)*.35;gl_FragColor=vec4(haze(c),1.);');
  for(const [skin,ink] of [['gardenWarm','2.4,1.12,.39'],['gardenPearl','1.17,1.75,2.11']]){
    surface(skin,shell(skin),'c=vec3('+ink+')*mix(.37,1.,night);gl_FragColor=vec4(haze(c),1.);');
  }
  surface('Crest Gardens vaulted glass',shell('gardenGlass'),
    'float F=pow(1.-max(0.,dot(V,N)),4.);'+
    'c=skySample(daySky,R)*(.46+.45*F)+vec3(.036,.090,.112)+lampLight(N,V,.22);'+
    'gl_FragColor=vec4(haze(c),.26+.46*F);',{transparent:true,depthWrite:false});
  const corners=[[-31,-23],[31,-23],[31,23],[-31,23]].map(([u,v])=>({x:x+u,y:y+v,a:[]}));
  const tess=ground.drapeTriangles([[corners[0],corners[1],corners[2]],[corners[0],corners[2],corners[3]]],{offset:.036});
  const floor=new THREE.BufferGeometry();
  floor.setAttribute('position',new THREE.Float32BufferAttribute(tess.pos,3));
  floor.setAttribute('normal',new THREE.Float32BufferAttribute(tess.nor,3));
  surface('Crest Gardens paths and planted beds',floor,[
    'vec2 q=p.xy-gardenCenter;float border=1.-smoothstep(1.6,1.96,abs(abs(q.x)-28.3));',
    'float crossing=1.-smoothstep(3.1,3.65,abs(q.y-8.)),avenue=1.-smoothstep(4.25,5.1,abs(q.x));',
    'float path=max(avenue,max(crossing,border)),rough=texture2D(slateColor,p.xy/4.1).r;',
    'vec2 tile=q/vec2(1.9,.91);float line=min(abs(fract(tile.x+.5)-.5),abs(fract(tile.y+.5)-.5));',
    'float grout=smoothstep(.025,.058,line),leaf=fbm(p.xy*.245)*.47+fbm(p.xy*1.35)*.53;',
    'vec3 planted=mix(vec3(.023,.067,.041),vec3(.119,.239,.078),leaf);',
    'planted=mix(planted,vec3(.29,.145,.029),smoothstep(.60,.84,leaf)*.46);',
    'vec3 walks=(vec3(.16,.177,.177)+rough*.26)*(.54+.46*grout);',
    'c=mix(planted,walks,path)*mix(1.13,.39,night)+lampLight(N,V,mix(.9,.37,path))*(.48+.52*path);',
    'gl_FragColor=vec4(haze(c),1.);',
  ].join('\n'));
  const water=park.fountain;
  surface('Crest Gardens reflecting basin',new THREE.PlaneGeometry(water.half[0]*2,water.half[1]*2).translate(...water.center),[
    'vec2 q=p.xy-gardenCenter;float ripple=fbm(q*.4+vec2(clock*.17,0.))-0.5;',
    'vec3 W=normalize(N+vec3(ripple*.19,(fbm(q*.32-vec2(0.,clock*.14))-.5)*.18,0.));',
    'float F=pow(1.-max(.01,dot(V,W)),3.2);',
    'c=mix(vec3(.018,.083,.087)*mix(.8,.39,night),skySample(daySky,reflect(-V,W)),.23+.54*F);',
    'c+=lampLight(W,V,.12)*(1.1+.4*ripple);gl_FragColor=vec4(haze(c),1.);',
  ].join('\n'));
  plantTrees(root,park.trees,local,spill);
  const mist=lowMist(root,park.fog,local);
  return {update(camera){
    const dx=camera.position.x-x,dy=camera.position.y-y;
    mist.visible=dx*dx+dy*dy<395*395&&camera.position.z<155;
  }};
}
