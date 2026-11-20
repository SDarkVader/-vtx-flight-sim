import * as THREE from 'three';
import {createGround} from '../ground.js';

export function buildCourseFurniture(group,w,placard){
  const ground=createGround(w,null),maps=[],vertices=[],colors=[];
  function paint(x,y,dx,dy,halfWidth,halfLength,color){
    const q=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([u,v])=>({x:x-dy*u*halfWidth+dx*v*halfLength,y:y+dx*u*halfWidth+dy*v*halfLength,a:[]}));
    const baked=ground.drapeTriangles([[q[0],q[1],q[2]],[q[0],q[2],q[3]]],{offset:.089}).pos;
    const c=new THREE.Color(color);for(let i=0;i<baked.length;i+=3){vertices.push(...baked.slice(i,i+3));colors.push(c.r,c.g,c.b);}
  }
  // Opposing lanes share the same physical surface. Paired edge studs mark distance;
  // the measured approach to the east hairpin gains one transverse bar every 25 m.
  const access=w.vaderland.operations.annex.access;
  const stations=[0];
  for(let i=1;i<access.points.length;i++){
    const a=access.points[i-1],b=access.points[i];stations.push(stations.at(-1)+Math.hypot(b[0]-a[0],b[1]-a[1]));
  }
  function mark(s,fn){
    let i=stations.findIndex(v=>v>s);if(i<1)return;
    const a=access.points[i-1],b=access.points[i],l=stations[i]-stations[i-1],dx=(b[0]-a[0])/l,dy=(b[1]-a[1])/l;
    fn(a[0]+dx*(s-stations[i-1]),a[1]+dy*(s-stations[i-1]),dx,dy);
  }
  for(let s=8;s<stations.at(-1);s+=16){
    mark(s,(x,y,dx,dy)=>{
      for(const k of [-1,1]){
        const u=k*(access.width_m/2-.45);
        paint(x-dy*u,y+dx*u,dx,dy,.16,.47,k>0?'#8bbaba':'#e4b577');
      }
      paint(x,y,dx,dy,.07,1.75,'#d9bf86');
    });
  }
  const apex=stations[9];
  if(w.vaderland.frontage){
    for(let s=0;s<stations.at(-1);s+=2){
      mark(s,(x,y,dx,dy)=>{
        if(x<892||x>1098||y>-346)return;
        for(const side of [-1,1])paint(x-dy*side*.16,y+dx*side*.16,dx,dy,.046,1.03,'#ce9e42');
      });
    }
    for(let k=-5;k<=5;k++)paint(950.4,-359.76+k*.78,.995,.102,.23,1.58,'#d4cebb');
  }
  for(const direction of [-1,1])for(let k=1;k<=4;k++){
    mark(apex-direction*25*k,(x,y,dx,dy)=>{
      for(let j=0;j<5-k;j++){
        const u=-direction*(access.width_m/2-1.23),v=direction*j*.86;
        paint(x-dy*u+dx*v,y+dx*u+dy*v,dx,dy,.76,.15,'#ffd189');
      }
    });
  }
  const yard=w.vaderland.meridian_yard;
  for(const course of [w.vaderland.operations.course,w.vaderland.civic_district?.course,
      w.vaderland.speedway?.timing,w.vaderland.cathedral?.timing,...(yard?.courses??[])].filter(Boolean)){
    for(const [j,gate] of course.gates.entries()){
      const [x,y]=gate.center,[dx,dy]=gate.normal,wide=gate.width_m;
      if(!j){
        for(let row=0;row<2;row++)for(let k=0;k<12;k++){
          const u=(k-5.5)*wide/12,v=row*.43;
          paint(x+dx*v-dy*u,y+dy*v+dx*u,dx,dy,wide/24,.215,(row+k)%2?'#343b43':'#e4d9cc');
        }
      }else{
        for(const side of [-1,1])for(let tick=0;tick<3;tick++){
          const u=side*(wide*.5-.45),v=-tick*1.5;
          paint(x+dx*v-dy*u,y+dy*v+dx*u,dx,dy,.32,.42,'#efb95d');
        }
      }
    }
    const p=course.name==='Meridian Operations'?[1015,-349.40,7.4]:[-171,2375.43,35.5];
    let board;
    if(course===w.vaderland.speedway?.timing){
      const wall=w.obstacles.find(o=>o.id==='courtyard-430');
      const [x,y,z]=wall.center;
      board=placard(course.name.toUpperCase(),'MERIDIAN START',17,3.5,[x-wall.half[0]-.035,y,z+1.9],-Math.PI/2);
    }else if(course===w.vaderland.cathedral?.timing){
      board=placard('CATHEDRAL OF VELOCITY','CIRCUIT',9.08,2.70,w.vaderland.cathedral.sign,-Math.PI/2);
      const approach=w.vaderland.cathedral.west_approach;
      if(approach){
        const angle=Math.atan2(approach.normal[1],approach.normal[0])-Math.PI/2;
        placard('WEST APPROACH','CATHEDRAL CIRCUIT',15.85,2.32,approach.sign,angle);
      }
    }else if(yard?.courses.includes(course)){
      const index=yard.courses.indexOf(course);
      board=placard(course.name.toUpperCase(),index?'PRECISION DRIVING':'HANDLING AND CORNERING',
        6.42,2.06,yard.boards[index],-Math.PI/2);
    }else board=placard(course.name.toUpperCase(),'TIMING',course.name==='Meridian Operations'?12:10,2.2,p);
    maps.push({board,course,last:''});
  }
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
  group.add(new THREE.Mesh(g,new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:-3.4,polygonOffsetUnits:-7})));
  return states=>{
    for(const m of maps){
      const s=states?.[m.course.name];const splits=s?.splits??[];
      const status=s?.last!=null?'LAP  '+s.last.toFixed(2)+' s':splits.length?'SPLIT '+splits.length+'    '+splits.at(-1).toFixed(2)+' s':'START  /  '+(m.course.length_m/1000).toFixed(2)+' KM';
      if(status!==m.last){
        const tex=m.board.material.map,ctx=tex.image.getContext('2d');
        ctx.fillStyle='#122128';ctx.fillRect(30,143,964,78);ctx.textAlign='center';ctx.fillStyle='#9bcecb';ctx.font='500 43px system-ui';
        ctx.fillText(status,512,194,925);tex.needsUpdate=true;m.last=status;
      }
    }
  };
}
