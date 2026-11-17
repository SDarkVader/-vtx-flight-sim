import * as THREE from 'three';

const fmt=(n,d=1)=>Number.isFinite(n)?n.toFixed(d):'—';
export function drawBoatAvionics(c, boat, state) {
  const text=(s,x,y,size=21,color='#b8cdd0')=>{c.font=`600 ${size}px Inter, ui-monospace, monospace`;c.fillStyle=color;c.fillText(s,x,y);};
  const line=(x,y,w)=>{c.strokeStyle='#36505a';c.lineWidth=1;c.beginPath();c.moveTo(x,y);c.lineTo(x+w,y);c.stroke();};
  const bar=(x,y,w,value)=>{c.fillStyle='#293b43';c.fillRect(x,y,w,7);if(Number.isFinite(value)){c.fillStyle='#c6e879';c.fillRect(x,y,w*Math.max(0,Math.min(1,value)),7);}};
  const heading=Number.isFinite(boat.heading_rad)?(90-boat.heading_rad*180/Math.PI+720)%360:null;
  const status=state.error?'FLEET ERROR':boat.crashed?'IMPACT':boat.dockedAt?'MOORED':state.available?'UNDER WAY':'DATA STALE';
  c.clearRect(0,0,1000,260);c.fillStyle='#0a171d';c.fillRect(0,0,1000,260);
  c.strokeStyle='#536a72';c.lineWidth=2;c.strokeRect(2,2,996,256);
  text('RICOCHET / HELM',24,34,23,'#e4ece9');c.textAlign='right';text(status,976,34,21,state.error||boat.crashed?'#f1b35d':'#c6e879');c.textAlign='left';line(24,48,952);
  text('WATER SPEED',24,82,19);text(`${fmt(boat.speed_mps)} m/s`,24,134,44,'#eaf3ef');
  text('HEADING',366,82,19);text(`${fmt(heading,0)}°`,366,134,44,'#c6e879');
  text('FUEL',696,82,19);text(`${fmt(boat.fuel_kg)} kg`,696,134,44,'#eaf3ef');line(24,158,952);
  text('RUDDER',24,195,18);text(`${fmt(boat.command?.rudder_deg)}°`,170,195,25,'#e4ece9');line(24,224,264);
  for(const x of [24,90,156,222,288]){c.strokeStyle='#829ba3';c.beginPath();c.moveTo(x,219);c.lineTo(x,229);c.stroke();}
  if(Number.isFinite(boat.command?.rudder_deg)){c.fillStyle='#c6e879';c.fillRect(154+Math.max(-1,Math.min(1,boat.command.rudder_deg/35))*132,213,4,22);}
  text('THROTTLE',366,195,18);text(`${fmt(Number.isFinite(boat.command?.throttle)?boat.command.throttle*100:null,0)}%`,558,195,25,'#e4ece9');bar(366,221,264,boat.command?.throttle);
  text('REVERSE',696,195,18);text(`${fmt(Number.isFinite(boat.command?.reverse_bucket)?boat.command.reverse_bucket*100:null,0)}%`,895,195,25,'#e4ece9');bar(696,221,264,boat.command?.reverse_bucket);
}

export function updateBoatAvionics(rig, boat, state, now, doc=globalThis.document) {
  if(!rig||!boat||!doc?.createElement)return;
  if(!rig.avionics){
    const body=rig.bodies.get('airframe');if(!body)return;
    const canvas=doc.createElement('canvas');canvas.width=2000;canvas.height=520;
    const context=canvas.getContext('2d');context.setTransform(2,0,0,2,0,0);
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
    texture.generateMipmaps=false;texture.minFilter=THREE.LinearFilter;texture.magFilter=THREE.LinearFilter;texture.anisotropy=8;
    const root=new THREE.Group();root.name='ricochet-compact-helm';root.position.set(1.72,0,1.08);
    root.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(new THREE.Vector3(0,-1,0),new THREE.Vector3(0,0,1),new THREE.Vector3(-1,0,0)));
    const frame=new THREE.Mesh(new THREE.BoxGeometry(.270,.0776,.008),new THREE.MeshStandardMaterial({color:'#26343c',roughness:.5,metalness:.5,depthTest:false,depthWrite:false}));
    const screen=new THREE.Mesh(new THREE.PlaneGeometry(.26,.0676),new THREE.MeshBasicMaterial({map:texture,toneMapped:false,depthTest:false,depthWrite:false}));
    frame.renderOrder=10;screen.renderOrder=11;screen.position.z=.005;root.add(frame,screen);body.add(root);
    rig.avionics={root,texture,context,lastDraw:-Infinity};
  }
  rig.avionics.root.visible=!!rig.inCockpit;
  if(now-rig.avionics.lastDraw<200)return;
  rig.avionics.lastDraw=now;drawBoatAvionics(rig.avionics.context,boat,state);rig.avionics.texture.needsUpdate=true;
}