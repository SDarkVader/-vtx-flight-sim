import * as THREE from 'three';

const vertex=`
  varying vec3 p,n;
  void main(){
    p=position;n=normal;
    gl_Position=projectionMatrix*viewMatrix*vec4(position,1.);
  }`;

function geometry(positions,normals){
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  if(normals)geo.setAttribute('normal',new THREE.Float32BufferAttribute(normals,3));
  else geo.computeVertexNormals();
  return geo;
}

export function buildCathedral(group, world, ground, uniforms, common) {
  const data=world.vaderland.cathedral;
  const root=new THREE.Group();
  root.name='Cathedral of Velocity';
  group.add(root);
  const story={
    cathedralStone:`
      vec2 layer=vec2(p.y+p.x*.34,p.z);
      vec3 stone=texture2D(roofRock,layer*.112).rgb;
      vec2 course=abs(fract((layer+vec2(floor(p.z/2.55)*.69,0.))/vec2(3.0,2.55)+.5)-.5);
      float mortar=1.-smoothstep(.012,.028,min(course.x,course.y));
      c=(vec3(.044,.033,.032)+stone*vec3(.67,.52,.39))*(1.-mortar*.36);
      c*=vec3(.37,.42,.55)+vec3(1.06,.76,.54)*key;
      c+=reflected*.13+vec3(.13,.043,.010)*exp(-abs(p.x-2855.)*.24)*(.4+.84*night);`,
    cathedralIron:`
      vec3 grain=texture2D(alloyColor,vec2(p.y+p.x*.57,p.z)*.63).rgb;
      vec2 grid=abs(fract(vec2(p.y*.49+p.x*.68,p.z*.90)+.5)-.5);
      float rivet=exp(-75.*length(grid))*(.45+.55*key);
      c=(vec3(.017,.026,.039)+grain*.30)*(.51+key*.62);
      c+=reflected*(.10+.39*fres)+vec3(.52,.30,.105)*rivet;
      c+=vec3(.19,.077,.016)*exp(-abs(p.x-2855.)*.21)*(.43+.79*night);`,
    cathedralAmber:`c=vec3(2.72,1.14,.36)*(.68+.32*night);`,
    cathedralViolet:`c=vec3(.77,.20,1.61)*(.42+.58*night);`,
    cathedralSpeaker:`
      vec2 porthole=abs(fract(vec2(p.x+p.y,p.z)*14.)-.5);
      float perforation=1.-smoothstep(.19,.29,length(porthole));
      c=(vec3(.014,.019,.026)+reflected*.14+vec3(.065,.076,.093)*key)*(1.-.85*perforation);`,
  };
  const local={...uniforms,roofRock:uniforms.granite};
  const batches=new Map();
  for(const o of world.obstacles){
    if(!o.id.startsWith('cathedral-'))continue;
    if(!batches.has(o.skin))batches.set(o.skin,{pos:[],spans:[]});
    const b=batches.get(o.skin);
    for(const face of o.faces)for(const i of face){
      b.pos.push(...o.vertices[i].map((v,j)=>v+o.center[j]));
    }
    b.spans.push({end:b.pos.length/9,id:o.id});
  }
  for(const [skin,{pos,spans}] of batches){
    const material=new THREE.ShaderMaterial({uniforms:local,vertexShader:vertex,side:THREE.DoubleSide,
      fragmentShader:common+`
      uniform sampler2D roofRock,alloyColor;
      void main(){
        vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;
        vec3 V=normalize(cameraPosition-p),R=reflect(-V,N);
        vec3 reflected=skySample(daySky,R),c;
        float key=max(0.,dot(sun,N)),fres=pow(1.-abs(dot(N,V)),3.);
        ${story[skin]}
        gl_FragColor=vec4(haze(c),1.);
        #include <colorspace_fragment>
      }`});
    const mesh=new THREE.Mesh(geometry(pos),material);
    mesh.name='Cathedral '+skin;
    mesh.userData.surveySpans=spans;
    root.add(mesh);
  }

  const roads=world.vaderland.routes.filter(r=>['Gallery west approach','Cut-and-cover gallery','Gallery east approach'].includes(r.name));
  const westPaint=data.west_approach?2678:2755;
  const xy=[...roads.find(r=>r.name==='Gallery west approach').points.filter(p=>p[0]>westPaint&&p[1]<-4319),
    ...roads.find(r=>r.name==='Gallery east approach').points.filter(p=>p[0]<=3660)];
  // The straight bore is laid on its native triangles. Both transition ends reuse the established approaches.
  const stations=xy.filter((p,i)=>!i||Math.hypot(p[0]-xy[i-1][0],p[1]-xy[i-1][1])>.01);
  const lengths=[0];
  const normals=stations.slice(1).map((p,i)=>{
    const dx=p[0]-stations[i][0],dy=p[1]-stations[i][1],length=Math.hypot(dx,dy);
    lengths.push(lengths[i]+length);
    return [-dy/length,dx/length];
  });
  const edges=stations.map(([x,y],i)=>{
    const a=normals[Math.max(0,i-1)], b=normals[Math.min(i,normals.length-1)];
    const scale=1+Math.max(-.5,a[0]*b[0]+a[1]*b[1]);
    return [-10.72,10.72].map(k=>({x:x+k*(a[0]+b[0])/scale,y:y+k*(a[1]+b[1])/scale,a:[k,lengths[i]]}));
  });
  const surface=[];
  for(let i=1;i<edges.length;i++){
    const [p,q]=edges[i-1],[r,s]=edges[i];
    surface.push([p,r,q],[q,r,s]);
  }
  const road=ground.drapeTriangles(surface,{offset:.060});
  const roadVertex=`
    attribute vec2 alignment;
    varying vec2 roadCoordinate;
    varying vec3 p,n;
    void main(){
      roadCoordinate=alignment;p=position;n=normal;
      gl_Position=projectionMatrix*viewMatrix*vec4(position,1.);
    }`;
  const asphalt=new THREE.ShaderMaterial({uniforms,vertexShader:roadVertex,side:THREE.DoubleSide,
    polygonOffset:true,polygonOffsetFactor:-3,polygonOffsetUnits:-5,
    fragmentShader:common+`
      uniform sampler2D asphaltColor,asphaltRough,asphaltNormal;
      varying vec2 roadCoordinate;
      float stripe(float d,float w){return 1.-smoothstep(w*.8,w*.98+fwidth(d),abs(d));}
      void main(){
        vec3 V=normalize(cameraPosition-p);
        vec2 uv=p.xy/3.17;
        vec3 grit=texture2D(asphaltColor,uv).rgb;
        vec3 bump=texture2D(asphaltNormal,uv).rgb*2.-1.;
        float rough=texture2D(asphaltRough,uv).r;
        float wet=.34+.66*smoothstep(.27,.69,fbm(uv*vec2(.92,.58)));
        vec3 N=normalize(n+vec3(bump.xy*.18,0.)),R=reflect(-V,N);
        float z=max(.024,R.z);
        float u=${data.west_approach?'roadCoordinate.x':'p.y+4350.'};
        float chain=${data.west_approach?'roadCoordinate.y':'p.x'};
        float bore=smoothstep(2873.,2930.,p.x)*(1.-smoothstep(3477.,3530.,p.x));
        float reach=6.56/z;
        vec3 mirror=p+R*reach;
        float rib=exp(-abs(fract((mirror.x-2900.)/16.+.5)-.5)*58.);
        float fringe=1.-smoothstep(10.2,10.76,abs(mirror.y+4350.));
        vec3 brass=vec3(1.36,.57,.16),violet=vec3(.43,.26,1.12);
        vec3 tint=mix(brass,violet,smoothstep(-4.5,4.5,mirror.y+4350.));
        vec3 reflection=tint*rib*fringe*wet*(.67-.22*rough)*bore*(.16+.84*pow(1.-abs(V.z),2.));
        float wash=exp(-abs(fract((p.x-2900.)/16.+.5)-.5)*10.);
        vec3 bounce=mix(brass,violet,smoothstep(-7.,7.,u));
        vec3 c=grit*mix(mix(vec3(.74,.71,.69),vec3(.34,.37,.45),night),vec3(.145,.18,.23),bore);
        c+=bounce*(.08+.28*wet)*wash*bore*grit;
        c+=skySample(daySky,R)*wet*(.45-.28*bore)*pow(1.-abs(V.z),2.4)+reflection;
        float m=stripe(abs(u)-.49,.078),edge=stripe(abs(u)-10.48,.09);
        float dash=stripe(abs(u)-5.,${data.west_approach?'.103':'.088'})*step(${data.west_approach?'.62':'.68'},fract(chain/12.));
        float studs=stripe(abs(u)-10.34,.14)*stripe(fract(chain*.125+.5)-.5,.069);
        float paint=bore;
        ${data.west_approach?`
        float arrival=smoothstep(2690.,2735.,p.x)*(1.-smoothstep(2897.,2963.,p.x));
        paint=max(paint,arrival);
        float kerb=stripe(abs(u)-10.07,.21)*step(.46,fract((chain-.46*abs(u))/3.3));
        c=mix(c,mix(vec3(.85,.38,.079),vec3(.52,.33,.92),step(0.,u)),kerb*arrival*.74);
        `:''}
        c=mix(c,vec3(.56,.41,.23),m*.68*paint);
        c=mix(c,vec3(.62,.62,.65),(dash*.74+edge*.52)*paint);
        c+=mix(vec3(1.22,.53,.11),vec3(.61,.22,1.3),step(0.,u))*studs*(.4+.39*night);
        gl_FragColor=vec4(haze(c),1.);
        #include <colorspace_fragment>
      }`});
  const geo=geometry(road.pos,road.nor);
  geo.setAttribute('alignment',new THREE.Float32BufferAttribute(road.att,2));
  const track=new THREE.Mesh(geo,asphalt);
  track.name='Cathedral approach and bore surface';
  root.add(track);
}
