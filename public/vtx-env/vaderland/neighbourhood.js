// Vaderland 33: rooftop landing zones, mission hoops and ward-track ramps.
// Ramps draw exactly the native convex hulls; zone markings and hoops carry no collision.
// Markings are kept quiet: aviation-style white and amber, brighter only for the zone the
// active mission is heading to.
import * as THREE from 'three';

export const neighbourhoodSolid=id=>/^nbr-/.test(id);

const MARK={S:'#ff8a5c',M:'#ffc27a',L:'#f4efe6',XL:'#cfe6c8'};   // muted by size class

export function buildNeighbourhoods(group,w,uniforms,common){
  const plan=w.vaderland.neighbourhoods;if(!plan)return null;
  const root=new THREE.Group();root.name='Meridian rooftop zones';group.add(root);
  const r=ramps(w.obstacles.filter(o=>neighbourhoodSolid(o.id)),uniforms,common);if(r)root.add(r);
  const zones=landingZones(plan.pads,uniforms);root.add(zones.group);
  const missions=missionMarkers(w.vaderland.missions||[],uniforms);root.add(missions.group);
  const brake=w.vaderland.brake_line?brakeLineMarks(w.vaderland.brake_line,uniforms):null;if(brake)root.add(brake.group);
  return {update(seconds,timing){
    zones.time.value=seconds;if(brake)brake.time.value=seconds;
    const targets=new Set();
    for(const m of w.vaderland.missions||[]){
      const s=m.steps[timing?.[m.name]?.next??-1];
      if(s?.type==='land'&&s.pad&&timing?.[m.name]?.start!=null)targets.add(s.pad);
    }
    zones.setTargets(targets);missions.update(seconds,timing);
  }};
}

// ---- ramps: dark decks with amber chevrons so the take-off edge reads at speed --------------
function ramps(list,uniforms,common){
  if(!list.length)return null;
  const P=[],H=[];
  for(const o of list){
    for(const f of o.faces)for(const k of f){const v=o.vertices[k];P.push(v[0]+o.center[0],v[1]+o.center[1],v[2]+o.center[2]);H.push(o.ramp.heading);}
  }
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(P,3));
  g.setAttribute('heading',new THREE.Float32BufferAttribute(H,1));g.computeVertexNormals();
  const m=new THREE.ShaderMaterial({uniforms,vertexShader:`attribute float heading;varying float hd;varying vec3 p;varying vec3 n;
    void main(){hd=heading;p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}`,
    fragmentShader:common+`varying float hd;
    void main(){
      vec3 N=normalize(n);vec2 d=vec2(cos(hd),sin(hd));float u=dot(p.xy,d),v=dot(p.xy,vec2(-d.y,d.x));
      float chevron=step(.78,fract((u+abs(v)*.8)*.30));
      vec3 deck=mix(vec3(.045,.045,.05),vec3(.55,.32,.08),chevron);
      vec3 c=(N.z>.15?deck:vec3(.07,.07,.08))*(vec3(.30,.33,.42)+vec3(.95,.82,.66)*max(dot(N,sun),0.));
      gl_FragColor=vec4(haze(c),1.);
      #include <colorspace_fragment>
    }`});
  const mesh=new THREE.Mesh(g,m);mesh.name='Ward track ramps';mesh.userData.sceneryIds=list.map(o=>o.id);return mesh;
}

// ---- landing zones: painted ring and V, small perimeter lights, beacon only when targeted ----
function landingZones(pads,uniforms){
  const group=new THREE.Group();group.name='Rooftop landing zones';
  const time={value:0};
  const deckShader={
    vertexShader:`varying vec2 q;void main(){q=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`uniform float night,time,target;uniform vec3 tint;varying vec2 q;
    void main(){
      float r=length(q);if(r>1.06)discard;
      float ring=smoothstep(.88,.90,r)*(1.-smoothstep(.95,.97,r));
      vec2 a=abs(q);float vee=step(abs(q.y*.9-a.x*1.6+.18),.06)*step(q.y,.40)*step(-.36,q.y);
      float lamps=step(.965,fract(atan(q.y,q.x)*1.9099))*smoothstep(.99,1.,r)*(1.-smoothstep(1.03,1.05,r));
      float paint=ring+vee*.85;
      float lit=mix(.30,.75,night)*(1.+target*.8);
      vec3 c=tint*paint*lit+vec3(1.,.82,.55)*lamps*(.6+1.4*night)*(1.+target*(.5+.5*sin(time*3.)));
      gl_FragColor=vec4(c,clamp(paint+lamps,0.,1.));
    }`};
  const beamShader={
    vertexShader:`varying float h;void main(){h=position.z;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader:`uniform float night,target;uniform vec3 tint;varying float h;
    void main(){gl_FragColor=vec4(tint*(1.-h)*(1.-h)*.10*target*(.4+.6*night),1.);}`};
  const beamG=new THREE.CylinderGeometry(.5,1.,1,20,1,true).rotateX(Math.PI/2).translate(0,0,.5);
  const byId=new Map();
  for(const p of pads){
    const tint={value:new THREE.Color(MARK[p.size]??'#f4efe6')},target={value:0};
    const deck=new THREE.ShaderMaterial({uniforms:{night:uniforms.night,time,tint,target},...deckShader,transparent:true,depthWrite:false,
      polygonOffset:true,polygonOffsetFactor:-6,polygonOffsetUnits:-10,toneMapped:false});
    const disc=new THREE.Mesh(new THREE.PlaneGeometry(2.2,2.2),deck);
    disc.scale.setScalar(p.radius_m);disc.position.set(p.center[0],p.center[1],p.center[2]+.06);disc.name=p.id;
    const beam=new THREE.Mesh(beamG,new THREE.ShaderMaterial({uniforms:{night:uniforms.night,tint,target},...beamShader,transparent:true,depthWrite:false,
      blending:THREE.AdditiveBlending,side:THREE.DoubleSide,toneMapped:false}));
    beam.scale.set(p.radius_m*.5,p.radius_m*.5,60);beam.position.set(...p.center);beam.visible=false;
    group.add(disc,beam);byId.set(p.id,{target,beam});
  }
  return {group,time,setTargets(ids){for(const [id,z] of byId){const on=ids.has(id);z.target.value=on?1:0;z.beam.visible=on;}}};
}

// ---- mission hoops and runway touchdown boxes: thin, pale, the next one brighter -----------
function missionMarkers(missions,uniforms){
  const group=new THREE.Group();group.name='Mission hoops';
  const rows=[];
  for(const m of missions){
    const idle=new THREE.MeshBasicMaterial({color:new THREE.Color(.30,.28,.24),toneMapped:false,transparent:true,opacity:.55});
    const hot=new THREE.MeshBasicMaterial({color:new THREE.Color(1.,.78,.45),toneMapped:false});
    const markers=m.steps.map((s,i)=>{
      const node=new THREE.Group();node.name=m.name+' step '+(i+1);
      if(s.type==='hoop'){
        const ring=new THREE.Mesh(new THREE.TorusGeometry(s.radius_m,Math.max(.25,s.radius_m*.022),8,72),idle);
        ring.position.set(...s.center);
        ring.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),new THREE.Vector3(...s.normal));
        node.add(ring);
      }else if(s.type==='hover'){
        // Station-keeping volume: two thin rings and four faint uprights.
        const [x,y,z]=s.center,r=s.radius_m,hh=s.half_height_m;
        for(const dz of [-hh,hh]){
          const ring=new THREE.Mesh(new THREE.TorusGeometry(r,.12,6,64),idle);ring.position.set(x,y,z+dz);node.add(ring);
        }
        for(let k=0;k<4;k++){
          const a=k*Math.PI/2,post=new THREE.Mesh(new THREE.BoxGeometry(.08,.08,2*hh),idle);
          post.position.set(x+Math.cos(a)*r,y+Math.sin(a)*r,z);node.add(post);
        }
      }else if(s.shape==='box'){
        const [hx,hy]=s.half,z=s.center[2]+.08;
        const pts=[[-hx,-hy],[hx,-hy],[hx,hy],[-hx,hy],[-hx,-hy]].map(([x,y])=>new THREE.Vector3(s.center[0]+x,s.center[1]+y,z));
        for(let k=1;k<pts.length;k++){
          const a=pts[k-1],b=pts[k],len=a.distanceTo(b);
          const bar=new THREE.Mesh(new THREE.BoxGeometry(len,.6,.06),idle);
          bar.position.copy(a).lerp(b,.5);bar.rotation.z=Math.atan2(b.y-a.y,b.x-a.x);node.add(bar);
        }
      }
      group.add(node);return node;
    });
    rows.push({m,markers,idle,hot,next:-1});
  }
  return {group,update(seconds,timing){
    for(const row of rows){
      const state=timing?.[row.m.name],next=state?.start!=null||state?.next>0?state.next:0;
      if(row.next===next)continue;row.next=next;
      row.markers.forEach((node,i)=>node.traverse(o=>{if(o.isMesh)o.material=i===next?row.hot:row.idle;}));
    }
  }};
}

// ---- the Brake Line: sequenced approach lights on the ground and the A10-B's ghost track ----
// The rabbit runs towards the first gate, as approach lights do on a real runway. The ghost is a
// faint line of small lights along the exact path the A10-B flew on 9 November.
function brakeLineMarks(marks,uniforms){
  const group=new THREE.Group();group.name='The Brake Line';
  const time={value:0};
  const quad=(count,attrs)=>{
    const g=new THREE.InstancedBufferGeometry();
    g.setAttribute('position',new THREE.Float32BufferAttribute([-1,-1,0,1,-1,0,1,1,0,-1,1,0],3));g.setIndex([0,1,2,0,2,3]);g.instanceCount=count;
    for(const [n,size,data] of attrs)g.setAttribute(n,new THREE.InstancedBufferAttribute(new Float32Array(data),size));
    return g;
  };
  const material=(vertex,fragment)=>new THREE.ShaderMaterial({uniforms:{time,night:uniforms.night,blueHour:uniforms.blueHour},
    vertexShader:vertex,fragmentShader:fragment,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false});
  const lights=quad(marks.lights.length,[['light',4,marks.lights.flat()]]);
  const approach=new THREE.Mesh(lights,material(`
    attribute vec4 light;uniform float time;varying vec2 q;varying float flash;
    void main(){q=position.xy;
      flash=pow(max(0.,1.-abs(fract(time*.55+light.w/30.)-.985)*40.),2.);
      vec4 v=viewMatrix*vec4(light.xyz,1.);v.xy+=position.xy*max(.35,-v.z*.0018)*(1.+flash);
      gl_Position=projectionMatrix*v;}`,`
    uniform float night,blueHour;varying vec2 q;varying float flash;
    void main(){float r=dot(q,q);if(r>1.)discard;float lit=max(night,blueHour*.8);
      gl_FragColor=vec4(vec3(1.,.86,.62)*exp(-r*3.)*(.22+2.6*flash)*(.25+.75*lit),1.);}`));
  approach.frustumCulled=false;approach.name='Brake Line approach lights';
  const ghostG=quad(marks.ghost.length,[['ghost',3,marks.ghost.flat()],['order',1,marks.ghost.map((_,i)=>i)]]);
  const ghost=new THREE.Mesh(ghostG,material(`
    attribute vec3 ghost;attribute float order;uniform float time;varying vec2 q;varying float glow;
    void main(){q=position.xy;glow=.55+.45*sin(time*.8-order*.21);
      vec4 v=viewMatrix*vec4(ghost,1.);v.xy+=position.xy*max(.18,-v.z*.0012);gl_Position=projectionMatrix*v;}`,`
    uniform float night,blueHour;varying vec2 q;varying float glow;
    void main(){float r=dot(q,q);if(r>1.)discard;float lit=max(night,blueHour*.8);
      gl_FragColor=vec4(vec3(.95,.90,.80)*exp(-r*3.5)*.32*glow*lit,1.);}`));
  ghost.frustumCulled=false;ghost.name='A10-B ghost track, 9 November 2026';
  group.add(approach,ghost);
  return {group,time};
}
