import * as THREE from 'three';
import {controlDesk,architecturalLights} from './station.js';
import {buildCourseFurniture} from './course.js';
import {architecturalMetal} from './city-facades.js';
import {GLTFLoader} from '../../vendor/GLTFLoader.js';
import {loadPinnedGltf} from '../../visual-identity.js';

const colours={parallaxGlass:0x405564,parallaxAlloy:0x8b9aa2,parallaxBronze:0xaa754b,city17brass:0xaa754b,city17titanium:0x8b9aa2,city17soffit:0x3e4a58,city17atrium:0x41515a,city17signal:0x7ceee8,vault:0x465360,basalt:0x302f38,sandstone:0x9b896e,bronze:0xab7741,brightbronze:0xe2b274,
  darkbronze:0x47392f,gold:0xffc566,patina:0x57726b,leather:0x514539,visor:0x192f36,walnut:0x67503e,
  stone:0xa8a59b,pavestone:0x937f67,desk:0x38494f,blade:0x465464,canopy:0x726755,
  hallglass:0x385e75,barrelglass:0x526d84,cabglass:0x7197a3,officeglass:0x6c8c90,wingglass:0x426270,
  twist:0x3e606e,sail:0x6b7782,flute:0x647b77,lantern:0x4c5d77,exchange:0x3b505c,store:0x956d4f,beacon:0xf2ba70,
  blacksteel:0x363a45,crestsilver:0xbac5cc,crestgold:0xe4b76a,lamplens:0xffe4a4,planterstone:0x534f48,bark:0x564839};

export function district(group,w,uniforms,common,optics){
  const root=new THREE.Group();root.name='Meridian departments';group.add(root);
  const config=w.vaderland.operations,plaza=w.vaderland.civic_district,frames=new Map(),mats=new Map(),batches=new Map();
  const fixed=new THREE.Group();root.add(fixed);
  function moving(spec){
    if(!spec)return fixed;
    if(!frames.has(spec.name)){
      const node=new THREE.Group();root.add(node);node.position.set(...spec.origin);node.name=spec.name;
      frames.set(spec.name,{node,spec});
    }
    return frames.get(spec.name).node;
  }
  function material(skin){
    if(mats.has(skin))return mats.get(skin);
    const metalSkin = ({parallaxAlloy:'city17titanium',parallaxBronze:'city17brass'})[skin] ?? skin;
    const physical=architecturalMetal(metalSkin,uniforms,common)??optics?.material(skin);if(physical){mats.set(skin,physical);return physical;}
    const transparent=['cabglass','officeglass','barrelglass','hallglass'].includes(skin);
    const city=['twist','sail','flute','lantern','exchange','store','wingglass','city17atrium'].includes(skin);
    const parallax=skin==='parallaxGlass';
    const bronze=['bronze','brightbronze','darkbronze','gold','patina','leather','visor'].includes(skin);
    const finish=new THREE.ShaderMaterial({uniforms:{...uniforms,tint:{value:new THREE.Color(colours[skin]??0x858788)}},
      transparent,depthWrite:!transparent,side:THREE.DoubleSide,vertexShader:`
        varying vec3 p;varying vec3 n;varying vec3 local;
        void main(){vec4 world=modelMatrix*vec4(position,1.);p=world.xyz;n=normalize(mat3(modelMatrix)*normal);
        local=position;gl_Position=projectionMatrix*viewMatrix*world;}`,
      fragmentShader:'uniform sampler2D ceramic;uniform sampler2D clouds;uniform sampler2D lounge;uniform sampler2D offices;uniform sampler2D shops;uniform sampler2D metalPlate,cityDayReflection,cityNightReflection;uniform float cityReflectionReady;uniform vec3 tint;varying vec3 local;'+common+`
        float lineAt(float v,float period,float width){float d=abs(fract(v/period+.5)-.5)*period;
          return (1.-smoothstep(width,width+max(.016,fwidth(v)),d))*(1.-smoothstep(period*.28,period*.75,fwidth(v)));}
        void main(){vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;vec3 V=normalize(cameraPosition-p);
          float sunlit=max(dot(N,sun),0.);float fres=pow(1.-abs(dot(N,V)),3.);vec3 R=reflect(-V,N);
          vec3 sky=skySample(clouds,R);float grain=fbm(p.xy*.22+p.z*.132);
          vec3 c=tint*(.39+.85*sunlit)*(.86+.21*grain);float alpha=1.;
          ${transparent?`float u=abs(N.x)>abs(N.y)?p.y:p.x;float frame=max(lineAt(u,3.5,.053),lineAt(p.z,3.65,.057));
            c=mix(sky*vec3(.43,.62,.76)+tint*.18,vec3(.070,.077,.076),frame);alpha=.10+.23*fres+frame*.64;`:''}
          ${parallax?`float axis=p.y*.76+p.x*.65;
            vec2 pitch=vec2(3.1,4.53), coord=vec2(axis,p.z)/pitch;
            vec2 cell=floor(coord), window=fract(coord);
            float roomId=hash(cell+vec2(419.,171.));
            float section=hash(floor(cell/vec2(3.,2.))+vec2(79.,104.));
            float occupied=smoothstep(.29,.71,roomId*.48+section*.52);
            vec2 roomUV=(cell+window+vec2(dot(V,vec3(-N.y,N.x,0.))*.21,-.14*V.z))/vec2(6.2,3.);
            vec3 interior=texture2D(lounge,roomUV).rgb;
            vec3 lamp=mix(vec3(.67,.85,1.),vec3(1.,.66,.36),.36+.64*section);
            float frame=max(lineAt(axis,pitch.x,.10),lineAt(p.z,pitch.y,.20));
            float warmReveal=exp(-34.*abs(window.y-.88))*(1.-frame)*occupied;
            vec2 reflectUV=vec2(atan(R.y,R.x)/tau+.5,asin(clamp(R.z,-1.,1.))/3.14159265+.5);
            vec2 dx=dFdx(reflectUV),dy=dFdy(reflectUV);
            dx.x-=floor(dx.x+.5);dy.x-=floor(dy.x+.5);
            vec3 localLight=mix(textureGrad(cityDayReflection,reflectUV,dx,dy).rgb,
                               textureGrad(cityNightReflection,reflectUV,dx,dy).rgb,night);
            vec3 reflected=mix(sky*vec3(.70,.85,1.),localLight,
                               cityReflectionReady*.46*(1.-smoothstep(.18,.75,R.z)));
            vec3 glass=vec3(.011,.020,.033)+reflected*(.20+.46*fres);
            glass+=interior*lamp*occupied*(.55+night*.39)*(1.-.62*fres);
            glass+=lamp*warmReveal*(.14+.22*night);
            c=mix(glass,vec3(.054,.070,.083)+reflected*.12,frame);
            if(abs(N.z)>.72)c=mix(c,vec3(.095,.118,.146)+reflected*.13,smoothstep(.72,.93,abs(N.z)));
          `:''}
          ${city?`float axis=abs(N.x)>abs(N.y)?p.y:p.x;
            float floors=lineAt(p.z,3.62,.15),mull=lineAt(axis,2.35,.068),fins=lineAt(axis,9.4,.12);
            vec2 win=vec2(floor(axis/2.35),floor(p.z/3.62));float light=hash(win+vec2(67.,41.));
            vec3 room=texture2D(lounge,vec2(axis/18.+dot(V,vec3(N.y,-N.x,0.))*.026,fract(p.z/10.86))).rgb;
            vec3 glass=sky*(.33+.41*fres)+tint*.27+room*(.18+.61*smoothstep(.56,.93,light))*vec3(1.25,.85,.51);
            vec3 glazing=texture2D(offices,vec2(axis/22.4,p.z/28.96)).rgb;
            glass=mix(glass,glazing*(1.2+.43*sunlit)+sky*(.10+.19*fres),.89);
            ${skin==='store'||skin==='wingglass'?`glass=texture2D(shops,vec2(axis/18.,fract((p.z-29.4)/10.7))).rgb*1.48+sky*.09;`:''}
            if(photographic>.5){
              float bank=hash(floor(win/vec2(3.,2.)));vec3 tintLight=mix(vec3(.67,.84,1.),vec3(1.,.72,.47),bank);
              float lightLevel=smoothstep(.32,.83,light*.50+bank*.67);
              glass=mix(glass,glass*(.19+lightLevel*2.65)*tintLight+sky*.14,night);
            }
            c=mix(glass,vec3(.035,.042,.055),max(mull,floors)*.63);c=mix(c,vec3(.36,.29,.21)*(.6+.68*sunlit),fins);
            if(photographic>.5){vec3 ceramicTile=texture2D(ceramic,vec2(axis,p.z)/2.8).rgb;
              c=mix(c,ceramicTile*(.46+.7*sunlit)*mix(1.,.29,night),max(fins*.68,floors*.36));}
            c+=vec3(.83,.39,.095)*lineAt(p.z,28.96,.104)*(.35+.6*sunlit);
            ${skin==='city17atrium'?`vec3 halls=texture2D(lounge,vec2(axis/29.+dot(V,vec3(-N.y,N.x,0.))*.044,p.z/8.3)).rgb;
              float rib=max(lineAt(axis,4.15,.10),lineAt(p.z,4.15,.10));
              c=mix(halls*vec3(1.26,.91,.62)*(.90+.38*night)+sky*(.09+.37*fres),vec3(.028,.041,.053),rib*.91);`:''}
            if(abs(N.z)>.74)c=tint*(.41+.60*sunlit)+sky*.22;`:''}
          ${bronze?`float key=max(dot(N,normalize(vec3(-.4,-.72,.57))),0.);
            c=tint*(.27+1.07*sunlit+.73*key)*(.83+.18*grain)+sky*(.11+.40*fres);
            c+=vec3(.89,.43,.16)*pow(max(dot(R,normalize(vec3(.84,.41,.20))),0.),15.);`:''}
          ${['blade','vault','basalt','sandstone','beacon'].includes(skin)?`vec2 radial=p.yz-vec2(-325.,18.);
            float radius=length(radial);float angle=atan(radial.y,radial.x);float ends=abs(abs(p.x-1000.)-30.);
            bool barrel=abs(p.x-1000.)<31.2 && abs(p.y+325.)<16.2 && radius>11.4;
            if(barrel){float rim=ends<1.?max(lineAt(radius,13.48,.092),lineAt(radius,15.21,.092)):lineAt(p.x-1000.,6.,.073);
              float bleed=ends<1.?exp(-abs(radius-13.5)*3.1):exp(-abs(fract((p.x-1000.)/6.+.5)-.5)*17.);
              c+=vec3(1.67,.67,.14)*(rim+bleed*.22);c+=sky*(.22+.28*fres);c*=1.-.35*lineAt(angle,0.392699,.003);}
            ${skin==='blade'?'c+=sky*(.24+.35*fres);':''}
            ${skin==='beacon'?'c+=vec3(1.28,.53,.095);':''}`:''}
          vec3 alloy=texture2D(metalPlate,vec2((p.x+p.y*.72)*.16,(p.z+p.y*.12)*.15)).rgb;
          ${['vault','basalt','blade','sandstone','brightbronze','bronze','leather','walnut','patina'].includes(skin)?`c*=.51+.76*clamp(alloy.r*2.2,.04,.80);c+=sky*pow(fres,.60)*.18;`:''}
          if(abs(p.x-1000.)<31.2&&abs(p.y+325.)<16.3&&abs(p.z-18.)<16.){
            vec2 polar=p.yz-vec2(-325.,18.);float angle=atan(polar.y,polar.x),r=length(polar);
            if(r>14.65&&abs(p.x-1000.)<29.42){float seam=lineAt(p.x-1000.,5.,.048);
              float damp=texture2D(metalPlate,vec2(p.x*.23,angle*6.)).r;
              c=(vec3(.020,.030,.047)+vec3(.083,.096,.111)*damp)*(.52+.57*sunlit)+sky*(.045+.12*fres);
              float lamp=seam*smoothstep(.32,.49,abs(sin(angle*3.)));
              c+=vec3(1.8,.73,.14)*lamp+vec3(.23,.091,.024)*exp(-abs(fract(p.x/5.+.5)-.5)*12.);}}
          ${skin==='walnut'?`float timber=fbm(vec2(p.x*.19+p.y*.041,p.z*4.2+p.y*2.85));
            c=vec3(.111,.063,.036)*(.54+.95*timber)+sky*(.06+.13*fres);
            c+=vec3(.13,.066,.015)*pow(max(dot(R,normalize(vec3(-.6,.7,.29))),0.),14.);`:''}
          ${skin==='blade'?`c*=.55+.30*max(0.,N.x)+.18*grain;`:''}
          if(abs(p.x)<75. && abs(p.y+300.)<78.)c*=.79;
          gl_FragColor=vec4(haze(c*mix(1.,${city?'.76':'.68'},night)),alpha);
          #include <colorspace_fragment>
        }`});
    mats.set(skin,finish);return finish;
  }
  const shapes=w.obstacles.filter(o=>o.kind==='mesh' && (Object.hasOwn(colours,o.skin)||o.motion||o.source_visual));
  for(const o of shapes){
    if(o.source_visual)continue;
    // The earlier terminal lives in its own editable Blender asset.
    if(!o.id.startsWith('pickup-canopy-') && (o.id.startsWith('terminal-wing-')||['airport-rotunda','rotunda','tower-','signal-tower','arrivals-'].some(pre=>o.id.startsWith(pre))))continue;
    const parent=moving(o.motion),id=(o.motion?.name??'fixed')+'/'+o.skin;
    if(!batches.has(id))batches.set(id,{parent,skin:o.skin,xyz:[],uv:[],normals:[],spans:[]});
    const batch=batches.get(id),off=o.motion?.origin??[0,0,0],vertices=o.vertices.map(v=>new THREE.Vector3(...v));
    const sum=vertices.map(()=>new THREE.Vector3());
    const normal=o.faces.map(([i,j,k])=>{const n=new THREE.Vector3().crossVectors(
      vertices[j].clone().sub(vertices[i]),vertices[k].clone().sub(vertices[i])).normalize();
      for(const vertex of [i,j,k])sum[vertex].add(n);return n;});
    const smooth=(o.id.startsWith('aviator-')&&o.skin!=='gold')||o.skin==='parallaxGlass';
    o.faces.forEach((f,i)=>{for(const k of f){
      const v=vertices[k];batch.xyz.push(v.x+o.center[0]-off[0],v.y+o.center[1]-off[1],v.z+o.center[2]-off[2]);
      const n=smooth&&Math.abs(normal[i].z)<.92?sum[k].clone().normalize():normal[i];batch.normals.push(n.x,n.y,n.z);
      const [x,y,z]=batch.xyz.slice(-3),a=Math.abs(n.x),b=Math.abs(n.y),c=Math.abs(n.z);
      batch.uv.push((c>=a&&c>=b?x:a>b?y:x)/2,(c>=a&&c>=b?y:z)/2);
    }});
    batch.spans.push({end:batch.xyz.length/9,id:o.id});
  }
  for(const b of batches.values()){
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(b.xyz,3));
    g.setAttribute('uv',new THREE.Float32BufferAttribute(b.uv,2));
    g.setAttribute('normal',new THREE.Float32BufferAttribute(b.normals,3));g.computeBoundingSphere();
    const n=new THREE.Mesh(g,material(b.skin));n.name='Meridian '+b.skin;n.userData.surveySpans=b.spans;b.parent.add(n);
    if(b.skin==='blade'&&!optics){
      const rim=new THREE.LineSegments(new THREE.EdgesGeometry(g,12),new THREE.LineBasicMaterial({color:0xb3a489}));
      b.parent.add(rim);
    }
  }
  if(optics)for(const t of w.vaderland.frontage.trims){
    const xyz=[],origin=t.motion.origin;
    for(let i=1;i<t.edge.length;i++){
      const a=t.edge[i-1],b=t.edge[i];
      for(const p of [a[0],a[1],b[1],a[0],b[1],b[0]])xyz.push(...p.map((v,j)=>v-origin[j]));
    }
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(xyz,3));g.computeVertexNormals();
    moving(t.motion).add(new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0xc29950,metalness:.62,roughness:.27,
      emissive:0x975e23,emissiveIntensity:1.24,side:THREE.DoubleSide})));
  }
  function placard(txt,sub,width,height,xyz,angle=0){
    const c=document.createElement('canvas');c.width=1024;c.height=256;const g=c.getContext('2d');
    g.fillStyle='#122128';g.fillRect(0,0,1024,256);g.fillStyle='#c6985a';g.fillRect(38,27,948,3);g.fillRect(38,226,948,3);
    g.fillStyle='#f0ddba';g.textAlign='center';g.font='600 79px "Arial Narrow",system-ui';g.fillText(txt,512,119,930);
    g.font='500 43px system-ui';g.fillStyle='#9bcecb';g.fillText(sub,512,194,925);
    const tx=new THREE.CanvasTexture(c);tx.colorSpace=THREE.SRGBColorSpace;tx.anisotropy=8;
    const mesh=new THREE.Mesh(new THREE.PlaneGeometry(width,height),new THREE.MeshBasicMaterial({map:tx,side:THREE.DoubleSide}));
    mesh.rotation.order='ZYX';mesh.rotation.x=Math.PI/2;mesh.rotation.z=angle;mesh.position.set(...xyz);root.add(mesh);return mesh;
  }
  placard('ENGINEERING','MODEL DESIGN  /  RESERVED BAY',12.8,2.45,[37,-331.46,6.8]);
  placard('FLIGHT OPERATIONS','DISPATCH   /   AIRFIELD',7.3,1.5,[-26,-274.91,1.6]);
  placard('COMPLIANCE & RECORDS','ARTHUR FINCH',7.2,1.28,[1006.,-349.34,13.64]);
  placard('MERIDIAN OPERATIONS','EAST DEPARTMENTAL CAMPUS',17.8,2.7,[993.,-349.45,7.9]);
  if(optics){
    placard('MERIDIAN','V   /   OPERATIONS',5.1,1.62,[1032.545,-340.62,16.1],Math.PI/2);
    placard('MERIDIAN','V   /   OPERATIONS',5.1,1.62,[967.455,-309.38,16.1],-Math.PI/2);
  }
  placard('RAYMOND WINSTON','MERIDIAN TOWER   /   ARRIVALS',1.47,.34,[116.,-232.,90.83]);
  const crestSigns=[];
  for(const d of config.annex.doors){
    const s=d.id==='west'?-1:1;const a=s*Math.PI/2;
    const plate=placard(d.id.toUpperCase()+' IRIS','FLIGHT AXIS',4.6,.84,[d.center[0]+s*.64,d.center[1],d.center[2]+13.9],a);
    crestSigns.push(plate);
  }
  // Real flat floors and centre compass, raised only above the collision surface by paint thickness.
  function floor(x,y,z,a,b,compass=false){
    const market=compass && w.vaderland.quarter;
    const stalls=market?.stalls??[];
    const lenses=market?w.vaderland.frontage.lights.filter(l=>l.site==='plaza'):[];
    const surface=market?{...uniforms,
      stallLights:{value:stalls.map(s=>new THREE.Vector4(s.xy[0]-x,s.xy[1]-y,...s.front))},
      civicLights:{value:lenses.map(l=>new THREE.Vector2(l.xyz[0]-x,l.xyz[1]-y))},
    }:uniforms;
    const lighting=market?`uniform vec4 stallLights[${stalls.length}];uniform vec2 civicLights[${lenses.length}];`:'';
    const mat=new THREE.ShaderMaterial({uniforms:surface,side:THREE.DoubleSide,vertexShader:'varying vec3 p;varying vec3 n;void main(){p=(modelMatrix*vec4(position,1.)).xyz;n=vec3(0,0,1);gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}',
      fragmentShader:lighting+'uniform sampler2D paving;uniform sampler2D slateColor;uniform sampler2D slateNormal;uniform sampler2D slateRough;uniform sampler2D clouds;'+common+`void main(){vec2 xy=p.xy-vec2(${x.toFixed(4)},${y.toFixed(4)});vec2 grid=abs(fract(xy/vec2(2.4,1.2)+.5)-.5);
       float mortar=1.-smoothstep(.008,.032,min(grid.x,grid.y));float d=length(xy);
       float ring=1.-smoothstep(.045,.15,abs(d-43.4));float stripe=1.-smoothstep(.04,.14,min(abs(xy.x),abs(xy.y)));
       vec3 c=mix(vec3(.118,.136,.145),vec3(.27,.247,.20),fbm(p.xy*.28))*(1.-mortar*.42);
       c=mix(c,texture2D(paving,p.xy/3.8).rgb*.95,.78);
       ${optics&&!market?`vec2 uv=p.xy/2.;vec3 N=texture2D(slateNormal,uv).rgb*2.-1.;
          N=normalize(vec3(N.xy*.47,1.));vec3 V=normalize(cameraPosition-p);
          vec3 marble=texture2D(slateColor,uv).rgb;
          float reflectance=(.065+.53*pow(1.-max(dot(V,N),0.),3.))*(1.-.59*texture2D(slateRough,uv).r);
          c=marble*vec3(.60,.66,.73)*mix(1.,.19,night)+skySample(clouds,reflect(-V,N))*reflectance;
          vec2 pool=abs(fract((xy+vec2(5.5,3.))/vec2(22.,8.))-.5);
          c+=vec3(.19,.082,.023)*exp(-pool.x*pool.x*65.-pool.y*pool.y*23.);`:''}
       ${market?`vec2 tile=xy/vec2(1.62,.81);
          tile.x+=.5*mod(floor(tile.y),2.);
          vec2 cell=floor(tile),edge=(.5-abs(fract(tile)-.5))*vec2(1.62,.81);
          float gap=min(edge.x,edge.y);
          float join=1.-smoothstep(.006,.016+fwidth(gap)*.70,gap);
          float dressing=hash(cell);
          vec2 sampleUV=(xy+vec2(dressing*6.,hash(cell+4.)*6.))/2.8;
          vec3 slab=texture2D(slateColor,sampleUV).rgb;
          vec3 bumped=texture2D(slateNormal,sampleUV).xyz*2.-1.;
          vec3 N=normalize(vec3(bumped.xy*.58,1.)),V=normalize(cameraPosition-p);
          float polish=clamp(1.-texture2D(slateRough,sampleUV).r,.12,.82);
          vec3 R=reflect(-V,N);float fres=pow(1.-max(dot(V,N),0.),3.);
          c=slab*.72*mix(vec3(.88,.97,1.05),vec3(.41,.50,.59),night)*(.76+.39*dressing);
          c+=vec3(.040,.052,.064)*(.7+.4*dressing);
          c+=skySample(clouds,R)*(.06+.46*fres)*(.4+polish);
          c*=1.-.64*join;
          for(int i=0;i<${stalls.length};i++){
            vec4 lamp=stallLights[i];vec2 delta=xy-lamp.xy-lamp.zw*.9;
            vec2 axis=vec2(lamp.w,-lamp.z);float along=dot(delta,axis);
            vec2 near=lamp.xy+lamp.zw*.9+axis*clamp(along,-2.1,2.1)-xy;
            vec3 beam=normalize(vec3(near,3.12));float fall=9./(9.+dot(near,near));
            float spec=pow(max(dot(R,beam),0.),mix(19.,87.,polish));
            vec3 tint=i==2||i==5?vec3(.49,.83,.93):vec3(1.,.56,.26);
            c+=tint*fall*(.046+spec*.88)*(.27+.73*night)*(1.-.68*join);
          }
          for(int i=0;i<${lenses.length};i++){
            vec2 delta=civicLights[i]-xy;float fall=2.4/(2.4+dot(delta,delta));
            float sheen=pow(max(dot(R,normalize(vec3(delta,.55))),0.),29.);
            c+=mix(vec3(1.,.58,.26),vec3(.51,.43,1.),mod(float(i),2.))*fall*(.24+1.3*sheen)*night;
          }`:''}
       c+=${compass?'vec3(.65,.31,.075)*(ring+stripe)*.71':'vec3(0.)'}+vec3(.038,.059,.085)*pow(1.-abs(normalize(cameraPosition-p).z),4.);gl_FragColor=vec4(haze(c*mix(1.,${market?'.89':'.46'},night)),1.);
       #include <colorspace_fragment>
       }`});
    const mesh=new THREE.Mesh(new THREE.PlaneGeometry(a,b),mat);mesh.position.set(x,y,z);root.add(mesh);
  }
  floor(0,-300,.023,106,106);
  // The surveyed apron and walks sit on the level airfield heightfield.
  floor(1000,-322,.004,99,67);
  floor(1000,-353.1,.007,109,4.4);
  floor(1000,-455,.004,68,102);
  if(plaza){
    const [x,y,z]=plaza.plaza;floor(x,y,z+.025,207,127,true);
    placard(plaza.monument?'VADERLAND':'VADERLAND AVIATOR',plaza.monument?'V CREST PLAZA':'MERIDIAN CIVIC PLAZA',11.8,2.42,[x,y-8.53,z+6.25]);
    for(const [j,name] of ['ARCHIVE','EXCHANGE HALL','NIGHT MARKET','OBSERVATORY'].entries())
      placard(name,plaza.monument?'V CREST PLAZA':'AVIATOR PLAZA',16,2.10,[-263+j*46,2375.46,37.8]);
  }
  architecturalLights(root,w);
  const towerScope=controlDesk(root,w.runway);
  const clocks=buildCourseFurniture(root,w,placard);
  const loader=new GLTFLoader();
  const asset=file=>new URL(file,import.meta.url).href;
  const ready=Promise.all([
    loadPinnedGltf(loader,asset('raymond-winston-fa124932.glb'),'ad14812c56cfbab463e7dd662c6a885532edf1d6239579529101cd6ebaed6af3').then(({scene})=>{
      scene.rotation.order='ZYX';scene.rotation.x=Math.PI/2;scene.rotation.z=Math.PI;
      scene.position.set(...config.tower.station);
      for(const id of ['upper_armR','upper_armL']){const bone=scene.getObjectByName(id);if(bone)bone.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),-1.05));}
      const lod=new THREE.LOD();lod.position.copy(scene.position);scene.position.set(0,0,0);lod.addLevel(scene,0);lod.addLevel(new THREE.Group(),215);root.add(lod);
    }),
    loader.loadAsync(asset('finch-office-furniture.glb')).then(({scene})=>{
      scene.rotation.x=Math.PI/2;scene.position.set(575.2,-8.3,10.8);root.add(scene);
    }),
    loader.loadAsync(asset('finch-on-inspection.glb')).then(({scene})=>{
      scene.rotation.x=Math.PI/2;scene.updateMatrixWorld(true);
      const jobs=[];scene.traverse(n=>{if(n.isMesh)jobs.push(n);});
      const levels=new Map();
      for(const n of jobs){
        let p=n;while(p&&!p.userData.movingPart)p=p.parent;
        const name=p?.userData.movingPart??'body',spec=config.staff_moves[name];if(!spec)continue;
        const key=spec.name;let level=levels.get(key);
        if(!level){
          level=new THREE.Group();const lod=new THREE.LOD();lod.addLevel(level,0);lod.addLevel(new THREE.Group(),150);
          moving(spec).add(lod);levels.set(key,level);
        }
        const g=n.geometry.clone();g.applyMatrix4(n.matrixWorld);
        g.translate(spec.root[0]-spec.origin[0],spec.root[1]-spec.origin[1],spec.root[2]-spec.origin[2]);
        level.add(new THREE.Mesh(g,n.material));
      }
    }),
  ]);
  function update(t,doors={},timing,aircraftXY){
    clocks(timing);towerScope(aircraftXY);
    for(const {node,spec:s} of frames.values()){
      if(s.door){node.rotation.x=s.travel_rad*(doors?.[s.door]??1);continue;}
      const angle=2*Math.PI*t/s.period_s;
      if(!s.orbit){node.rotation.z=angle;continue;}
      const [x,y,rx,ry]=s.orbit,co=Math.cos(angle),sn=Math.sin(angle),yaw=Math.atan2(ry*co,-rx*sn)-Math.PI/2;
      const dx=s.origin[0]-s.root[0],dy=s.origin[1]-s.root[1];
      node.position.set(x+rx*co+Math.cos(yaw)*dx-Math.sin(yaw)*dy,y+ry*sn+Math.sin(yaw)*dx+Math.cos(yaw)*dy,s.origin[2]);
      node.rotation.order='ZYX';node.rotation.z=yaw;node.rotation.x=s.swing_rad*Math.sin(s.strides*angle);
    }
  }
  return {ready,update};
}
