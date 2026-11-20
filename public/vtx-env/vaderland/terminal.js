import * as THREE from 'three';
import {GLTFLoader} from '../../vendor/GLTFLoader.js';

export async function buildTerminal(group,w,uniforms,common){
  const url=new URL(w.vaderland.arrivals.asset,import.meta.url).href;
  const {scene:model}=await new GLTFLoader().loadAsync(url);
  model.rotation.x=Math.PI/2;
  function inscription(band){
    const c=document.createElement('canvas');c.width=1536;c.height=band?176:1536;
    const x=c.getContext('2d');x.fillStyle='#ffcc76';x.textAlign='center';x.textBaseline='middle';
    if(band){x.font='600 108px system-ui';x.fillText('V A D E R L A N D     /     V T X',768,88,1450);}
    else{
      for(const k of [-1,1]){
        x.save();x.translate(768,488);x.scale(k,1);
        x.beginPath();x.moveTo(0,48);x.lineTo(270,-121);x.lineTo(128,-102);x.lineTo(0,-7);x.fill();
        x.beginPath();x.moveTo(18,-52);x.lineTo(123,-128);x.lineTo(74,-117);x.lineTo(20,-79);x.fill();x.restore();
      }
      x.font='600 113px system-ui';x.fillText('V A D E R L A N D',768,715,1190);
      x.font='bold 199px system-ui';x.fillText('VTX',768,905,725);
    }
    const tex=new THREE.CanvasTexture(c);tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=8;return tex;
  }
  const finishUniforms={...uniforms,roofMark:{value:inscription(false)},bandMark:{value:inscription(true)}};
  const materials=new Map();
  const skins=['Glass','Nickel','Skylight','Bronze','Light','Stone','Planting','Soffit','Shaft','Mark'];
  function finish(name){
    if(materials.has(name))return materials.get(name);
    const m=new THREE.ShaderMaterial({uniforms:finishUniforms,vertexShader:`
      varying vec3 p;varying vec3 n;
      void main(){vec4 q=modelMatrix*vec4(position,1.);p=q.xyz;
        n=normalize(mat3(modelMatrix)*normal);gl_Position=projectionMatrix*viewMatrix*q;}`,
      fragmentShader:'uniform sampler2D clouds;uniform sampler2D lounge;uniform sampler2D reliefLight;uniform sampler2D roofMark;uniform sampler2D bandMark;'+common+`
      float seam(float x,float pitch,float thickness){
        float pix=fwidth(x);float s=abs(fract(x/pitch+.5)-.5)*pitch;
        return (1.-smoothstep(thickness,thickness+min(pix,pitch*.25),s))*(1.-smoothstep(pitch*.19,pitch*.65,pix));
      }
      void main(){
        vec3 N=normalize(n),V=normalize(cameraPosition-p),R=reflect(-V,N);
        float incidence=clamp(dot(V,N),0.,1.),direct=max(dot(N,sun),0.);
        float fres=pow(1.-incidence,3.);
        vec3 sky=skySample(clouds,R);
        float grain=fbm(p.xy*.16+p.z*.11);
        vec2 xy=p.xy-vec2(0.,-300.);
        float radius=length(xy),ang=atan(xy.x,-xy.y),arc=ang*max(radius,1.);
        bool hub=radius<88. && p.z>-.8;
        float along=hub?arc:abs(p.x)*.86-(p.y+310.)*.50;
        int kind=${skins.indexOf(name)};
        vec3 c;
        if(kind==0){
          bool tower=length(p.xy-vec2(116.,-235.))<14.;
          float floorZ=tower?90.5:(hub && p.z>15.5?16.:.6);
          float height=tower?5.5:hub?13.6:12.;
          vec2 room=vec2(along/(tower?24.:42.),clamp((p.z-floorZ)/height,0.,1.));
          vec3 tangent=normalize(vec3(-N.y,N.x,0.)+vec3(.000001));
          room+=vec2(dot(V,tangent)*.048,V.z*.067);
          vec3 interior=texture2D(lounge,vec2(room.x,clamp(room.y,.012,.988))).rgb;
          float division=max(seam(along,3.85,.052),seam(p.z-floorZ,height*.51,.064));
          float shade=1.-.56*smoothstep(.80,1.,(p.z-floorZ)/height);
          c=interior*vec3(1.46,1.31,1.12)*shade+vec3(.014,.026,.039);
          c=mix(c,sky*vec3(.67,.80,.99),.115+.57*fres);
          c=mix(c,vec3(.036,.044,.052)*(.73+.66*direct),division);
          if(hub && abs(ang)<.89 && p.z>23.4 && p.z<27.8){
            vec4 word=texture2D(bandMark,vec2(ang/1.78+.5,(p.z-23.4)/4.4));
            float end=1.-smoothstep(.865,.89,abs(ang));c=mix(c,vec3(.020,.029,.041),.95*end);
            c=mix(c,word.rgb*1.36,word.a*end);
          }
        }else if(kind==2){
          float frames=seam(along,4.8,.079);
          c=mix(vec3(.014,.047,.074)+sky*(.28+.31*fres),vec3(.065,.073,.076),frames);
        }else if(kind==4){
          c=vec3(1.8,.89,.24);
        }else if(kind==3 || kind==9){
          c=vec3(.19,.083,.025)*(.55+.92*direct)+sky*(.12+.44*fres)+vec3(.04,.024,.009);
        }else if(kind==5 || kind==6){
          c=(kind==5?vec3(.19,.176,.15):vec3(.032,.080,.042))*(.7+.5*grain)*(.62+.8*direct);
        }else if(kind==7){
          c=vec3(.14,.079,.043)*(.78+.20*grain);
          if(N.z<-.6){
            float board=fract((p.x+.1)/.27);
            float grain=fbm(vec2(p.x*7.4,p.y*.52));
            c=mix(vec3(.055,.033,.024),vec3(.246,.134,.061),grain);
            c*=1.-.65*seam(p.x+.1,.27,.020);
            c*=.78+.22*smoothstep(.04,.78,board);
            c+=vec3(1.25,.69,.22)*seam(p.y+395.,4.65,.078);
          }
        }else if(kind==8){
          c=mix(vec3(.18,.18,.18),vec3(.39,.35,.30),.5+.5*dot(N,sun))+sky*.12;
        }else{
          float seamLine=hub?max(seam(radius,5.0,.043),seam(ang*60.,6.73198,.034)):seam(along,2.35,.040);
          c=mix(vec3(.040,.060,.088),vec3(.096,.121,.137),grain)*(.68+.64*direct);
          c+=sky*vec3(.26,.29,.35)*(.55+.75*fres);
          c*=1.-.43*seamLine;
          float shine=pow(max(0.,dot(R,normalize(vec3(.91,.35,.12)))),36.);
          c+=vec3(.51,.24,.067)*shine;
          if(hub && p.z>30.9 && N.z>.30){
            c=mix(c,c*vec3(.55,.64,.83),.73);
            vec4 logo=texture2D(roofMark,xy/137.+.5);
            if(max(abs(xy.x),abs(xy.y))<68.5)c=mix(c,logo.rgb*1.65,logo.a);
            c+=vec3(.57,.284,.065)*(1.-smoothstep(.06,.21,abs(radius-62.)));
          }
        }
        ${w.vaderland.operations?`if(hub&&N.z<-.87&&p.z>13.9&&p.z<16.){
          float ribs=max(seam(radius,7.0,.16),seam(ang*40.,7.854,.13));
          float lamp=seam(radius,14.,.085)*(.40+.60*step(.23,fract(ang*3.81)));
          c=mix(vec3(.039,.049,.060),vec3(.105,.086,.070),grain)*(1.-ribs*.65);
          c+=vec3(1.76,.82,.21)*lamp+vec3(.21,.084,.026)*exp(-abs(fract(radius/14.+.5)-.5)*19.);
        }`:''}
        gl_FragColor=vec4(haze(c*mix(1.,kind==0||kind==4?.90:.54,night)),1.);
        #include <colorspace_fragment>
      }`});
    materials.set(name,m);return m;
  }
  // The Blender source preserves individual architectural members. A static
  // material needs only one draw in the playable world. Keep the triangle-to-
  // survey mapping so a ray still identifies its exact native collision hull.
  model.updateMatrixWorld(true);
  const batches=new Map();
  model.traverse(node=>{
    if(!node.isMesh)return;
    let parent=node;while(parent && !parent.userData.sceneryId)parent=parent.parent;
    const id=parent?.userData.sceneryId??null;
    const g=node.geometry.index?node.geometry.toNonIndexed():node.geometry.clone();
    g.applyMatrix4(node.matrixWorld);
    const mats=Array.isArray(node.material)?node.material:[node.material];
    const sections=g.groups.length?g.groups:[{start:0,count:g.attributes.position.count,materialIndex:0}];
    for(const section of sections){
      const key=mats[section.materialIndex].name;
      if(!batches.has(key))batches.set(key,{positions:[],normals:[],spans:[],vertices:0});
      const b=batches.get(key),first=section.start*3,last=first+section.count*3;
      b.positions.push(g.attributes.position.array.slice(first,last));
      b.normals.push(g.attributes.normal.array.slice(first,last));
      b.vertices+=section.count;b.spans.push({end:b.vertices/3,id});
    }
    g.dispose();
  });
  for(const [name,b] of batches){
    const g=new THREE.BufferGeometry();
    for(const [attribute,parts] of [['position',b.positions],['normal',b.normals]]){
      let cursor=0;const data=new Float32Array(b.vertices*3);
      for(const part of parts){data.set(part,cursor);cursor+=part.length;}
      g.setAttribute(attribute,new THREE.BufferAttribute(data,3));
    }
    g.computeBoundingSphere();
    const mesh=new THREE.Mesh(g,finish(name));mesh.name='Meridian terminal '+name;
    mesh.userData.surveySpans=b.spans;group.add(mesh);
  }
}
