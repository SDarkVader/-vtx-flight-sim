// Photograph the actual WebGL world builder from recorded data. All requests end
// in this process. There is no server, clock, vehicle selection or live cockpit.
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {gunzipSync} from 'node:zlib';

const {chromium} = await import(process.env.VTX_PLAYWRIGHT
  ? pathToFileURL(process.env.VTX_PLAYWRIGHT).href : 'playwright-core');
const directory = path.resolve(process.argv[2]);
const root = process.env.VTX_PHOTO_PUBLIC || fileURLToPath(new URL('../../public/', import.meta.url));
const world = JSON.parse(gunzipSync(await readFile(path.join(directory, 'world.json.gz'))));
const marine=process.argv.includes('--marine')?JSON.parse(gunzipSync(await readFile(path.join(directory,'fleet-state.json.gz')))):null;
if(marine)marine.generation='offline-water-survey';
const origin = 'https://vaderland-survey.invalid';
const views = {
  panorama: {eye:[1750,-5800,1920], target:[-450,1550,340], fov:52},
  ground: {eye:[-340,-175,2.1], target:[110,1500,118], fov:58},
  flight: {eye:[-2270,-1670,280], target:[120,1550,205], fov:55},
  terminal: {eye:[307,-635,98],target:[0,-269,29],fov:53},
  apronEye: {eye:[-408,-161,2.1],target:[-34,-303,27],fov:61},
  gateCourt: {eye:[-90,-485,2.4],target:[36,-321,27],fov:60},
  hangarMouth: {eye:[31,44.0,2.2],target:[92,45,6.3],fov:61},
  shortFinal: {eye:[-4300,-8,47],target:[-2740,2,0],fov:47},
  airfieldPlan: {eye:[520,-1020,570],target:[0,-180,10],fov:50},
  terminalFront:{eye:[36,-745,151],target:[0,-265,24],fov:48},
  quayAir:{eye:[260,-757,97],target:[193,-576,7.4],fov:53},
  quayWater:{eye:[193,-629,8.35],target:[187,-524,17],fov:60},
  quayRoad:{eye:[174,-492,2.4],target:[205,-574,7.8],fov:60},
  arrivalsApproach:{eye:[-72,-468,2.0],target:[5,-360,19],fov:58},
  arrivalsHall:{eye:[-42,-398,2.25],target:[17,-383,8.],fov:63},
  crescent:{eye:[245,-547,67],target:[36,-314,20],fov:52},
  wingWalk:{eye:[156,-356,1.95],target:[91,-355,8.1],fov:62},
  irisAxis:{eye:[933,-325,18],target:[1050,-325,18],fov:50},
  irisClosed:{eye:[941,-324,17],target:[998,-325,18],fov:55,doors:{west:0,east:1}},
  deptExterior:{eye:[927,-395,25],target:[1005,-325,15],fov:54},
  irisFlight:{eye:[986,-325,18.3],target:[1100,-325,18.3],fov:59},
  complianceHall:{eye:[997.0,-340.5,12.05],target:[1001.5,-346.2,11.68],fov:61},
  circuitEntry:{eye:[382,-365,2.1],target:[559,-382,3.1],fov:58},
  hallInside:{eye:[-12,-362,2.1],target:[15,-285,6.6],fov:65},
  towerDesk:{eye:[116.78,-231.08,91.67],target:[116,-232.63,91.37],fov:55},
  records:{eye:[1002.12,-340.43,11.96],target:[1003.23,-342.09,11.56],fov:59},
  cityPlaza:{eye:[-145,2217,38.5],target:[-197,2340,66],fov:54},
  crestStreet:{eye:[-199,2246,34.0],target:[-183,2325,58],fov:56},
  crestNight:{eye:[-199,2246,34.0],target:[-183,2325,58],fov:56,mode:'night'},
  crestQuarter:{eye:[-199,2246,34.0],target:[-183,2325,58],fov:56,time:22,mode:'night'},
  crestDetail:{eye:[-168,2302,58],target:[-161,2326,67],fov:46},
  crestLibrary:{eye:[-246,2291,36.1],target:[-179,2327,62],fov:64,mode:'night'},
  irisNight:{eye:[936,-330,17],target:[1029,-325,18],fov:56,mode:'night'},
  quayNight:{eye:[193,-627,9],target:[188,-526,17],fov:58,mode:'night'},
  lastBrake:{eye:[1051,-359,1.65],target:[1150,-346,3.3],fov:61,mode:'night'},
  operationsStreet:{eye:[1073,-359.4,2.5],target:[1004,-331.2,12.9],fov:56,doors:{west:1,east:.48}},
  operationsStreetNight:{eye:[1073,-359.4,2.5],target:[1004,-331.2,12.9],fov:56,mode:'night',doors:{west:1,east:.48}},
  lensDetail:{eye:[1049,-330.,18.7],target:[1030,-322,20.3],fov:51,doors:{west:1,east:.46}},
  deskWide:{eye:[993.2,-342.3,12.3],target:[1004.5,-346.1,11.9],fov:70},
  civicAir:{eye:[180,1830,233],target:[-106,2350,137],fov:58},
  aviator:{eye:[-166,2270,78],target:[-183,2325,73.5],fov:47},
  aviatorQuarter:{eye:[-166,2270,78],target:[-183,2325,73.5],fov:47,time:30},
  arcade:{eye:[-264,2330,34],target:[-174,2382,45],fov:58},
  skyline: {eye:[-700,-1560,300],target:[-30,1400,183],fov:38},
  waterfront: {eye:[-915,-2740,175],target:[-2130,-1470,34],fov:49},
  pass: {eye:[-4460,2560,480],target:[-5300,3870,435],fov:52},
  falls: {eye:[-4690,4065,194],target:[-4805,4334,230],fov:61},
  crossing: {eye:[-4849,3199,186.4],target:[-5440,3200,197],fov:58},
  gorge: {eye:[-5260,2740,310],target:[-4940,3970,231],fov:60},
  gallery: {eye:[2865,-4352,149],target:[3120,-4350,148.8],fov:62},
  portal: {eye:[2850,-4369,150.4],target:[2977,-4348,147.6],fov:52},
  lanes: {eye:[3010,-4356.35,145.3],target:[3330,-4356.35,145.9],fov:65},
  galleryAir: {eye:[2680,-4590,325],target:[3265,-4350,144],fov:53},
  street: {eye:[-644,2463,37],target:[112,2515,115],fov:62},
  // Rooftop Quarter review cameras (NW wards and the A10-D approach).
  approachNW: {eye:[-1050,3150,560], target:[-150,2250,140], fov:58, mode:'dusk', time:27},
  approachDay: {eye:[-1050,3150,560], target:[-150,2250,140], fov:58, mode:'day', time:27},
  wardsAir: {eye:[-2750,4900,430], target:[-1650,3500,60], fov:58, mode:'dusk', time:27},
  wardsStreet: {eye:[-2200,3300,42.2], target:[-1500,3000,70], fov:62, mode:'dusk', time:27},
  cityFromRunway: {eye:[-700,-1560,300], target:[-30,1400,183], fov:38, mode:'dusk', time:27},
  circuit: {eye:[3780,-4610,570],target:[5350,-3100,155],fov:52},
};
if(world.vaderland.speedway){
  const gate=world.vaderland.speedway.timing.gates[0], [x,y,z]=gate.center;
  const [dx,dy]=gate.normal;
  views.velocityGrid={eye:[x-dx*70-3.8*dy,y-dy*70+3.8*dx,z+.91],target:[x+dx*200,y+dy*200,z+19],fov:64,mode:'night'};
  views.velocityDay={...views.velocityGrid,mode:'day'};
  views.velocityAvenue={eye:[-5,2071,29.5],target:[-31,2359,75],fov:61,mode:'night'};
  views.velocityAir={eye:[447,1700,205],target:[-105,2655,155],fov:62,mode:'night'};
  const survey=world.vaderland.speedway.timing.gates[3],p=survey.center,d=survey.normal;
  views.velocityEast={eye:[p[0]-d[0]*40,p[1]-d[1]*40,p[2]+2.1],target:[p[0]+d[0]*260,p[1]+d[1]*260,p[2]+5.3],fov:65,mode:'night'};
}
if(world.vaderland.quarter){
  const people=world.vaderland.quarter.people;
  const chosen=people.reduce((a,b)=>Math.hypot(b.center[0]+58,b.center[1]-2155)<Math.hypot(a.center[0]+58,a.center[1]-2155)?b:a);
  const [cx,cy]=chosen.center,[ax,ay]=chosen.a,r=Math.hypot(ax,ay),dx=ax/r,dy=ay/r;
  const z=chosen.origin[2],toward=cx<0?-1:1;
  const stall=world.vaderland.quarter.stalls?.[0];
  if(stall){
    const [xx,yy]=stall.xy,[nx,ny]=stall.front,[ax,ay]=stall.axis;
    views.eveningMarket={eye:[xx+nx*15+ax*7,yy+ny*15+ay*7,stall.z+1.68],target:[xx+ax-3*nx,yy+ay-3*ny,stall.z+2.75],fov:64,mode:'night',time:12};
    views.flowerStall={...views.eveningMarket};
    views.eveningMarket={eye:[-81.4,2271.3,32.91],target:[-113,2339,36.27],fov:61,mode:'night',time:12};
    views.marketAtDusk={...views.eveningMarket,mode:'day',time:25.};
    views.marketStreetAir={eye:[xx+nx*28+ax*34,yy+ny*28+ay*34,stall.z+22],target:[xx-13*ax,yy-13*ay,stall.z+3.3],fov:61,mode:'night',time:9};
  }
  views.marketWalk={eye:[cx-12*dx-toward*5,cy-12*dy,z+1.7],target:[cx+12*dx+toward*1.6,cy+12*dy,z+2.85],fov:66,mode:'night',time:9};
  views.marketWalkDay={...views.marketWalk,mode:'day',time:21};
  views.facadeStudy={eye:[2,2232,51],target:[50,2232,51],fov:47,mode:'night',time:27};
  if(world.vaderland.city_lights){
    views.avenueDusk={...views.velocityGrid,mode:'dusk',time:27};
    views.skylineDusk={...views.velocityAir,mode:'dusk',time:27};
    views.skylineDay={...views.velocityAir,mode:'day',time:27};
    views.wintergarden={eye:[-26,2160,45],target:[50,2238,68],fov:55,mode:'dusk',time:27};
    views.northlight={eye:[71,2654,231],target:[40,2722,229],fov:46,mode:'dusk',time:27};
    views.vesper={eye:[-143,2046,168],target:[-107,2079,155],fov:47,mode:'dusk',time:27};
    views.vestibule={eye:[-26,2147,31.5],target:[49,2236,49],fov:61,mode:'night',time:27};
    views.eveningFront={...views.marketWalk,mode:'dusk',time:27};
  }
  views.marketAbove={eye:[375,1703,151],target:[-83,2395,117],fov:65,mode:'night',time:26};
  views.marketTerrace={eye:[-368,2462,156],target:[76,2041,91],fov:62,mode:'night',time:31};
}
if(world.vaderland.city_lights){
  const [x,y,z]=world.vaderland.parallax?.point??[89.830665,2383.48142,53.427];
  views.parallaxSkyline={eye:[x-173,y-317,z+121],target:[x,y,z+80],fov:47,mode:'dusk',time:27};
  views.parallaxAvenue={eye:[16,2269,33.8],target:[x-28,y-25,103],fov:67,mode:'dusk',time:27};
  views.parallaxPass={eye:[x-102,y,150.],target:[x,y,150.],fov:53,mode:'dusk',time:27};
  views.parallaxFront={eye:[x-142,y+4,148],target:[x,y,143],fov:65,mode:'dusk',time:27};
  views.parallaxDetail={eye:[x-60,y+46,z+114],target:[x,y+25,z+105],fov:48,mode:'dusk',time:27};
}
if(world.vaderland.neighbourhoods){
  // Vaderland 33 review cameras, placed from the design data.
  const nb=world.vaderland.neighbourhoods;
  const pad=[...nb.pads].filter(p=>p.size==='L').sort((a,b)=>a.height_m-b.height_m)[0];
  const [px,py,pz]=pad.center;
  views.zoneDusk={eye:[px-48,py-62,pz+38],target:[px,py,pz],fov:50,mode:'dusk',time:27};
  const high=[...nb.pads].sort((a,b)=>b.height_m-a.height_m)[0];
  views.zoneHigh={eye:[high.center[0]+140,high.center[1]-160,high.center[2]+60],target:high.center,fov:46,mode:'dusk',time:27};
  const tr=world.vaderland.routes.find(r=>r.name===nb.tracks[0].name);
  const xs=tr.points.map(p=>p[0]),ys=tr.points.map(p=>p[1]);
  const cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;
  const tz=world.obstacles.find(o=>o.id===nb.tracks[0].ramps[0]).center[2];
  views.trackDay={eye:[cx-95,cy-85,tz+48],target:[cx,cy,tz],fov:52,mode:'day',time:27};
  const m=world.vaderland.missions[0],h=m.steps[1],[nx,ny]=h.normal;
  views.hoopRun={eye:[h.center[0]-nx*140,h.center[1]-ny*140,h.center[2]+6],target:[h.center[0]+nx*200,h.center[1]+ny*200,h.center[2]-20],fov:60,mode:'dusk',time:27};
  const lane=world.vaderland.routes.filter(r=>r.kind==='lane').sort((a,b)=>Math.hypot(a.points[0][0]+2100,a.points[0][1]-3900)-Math.hypot(b.points[0][0]+2100,b.points[0][1]-3900))[0];
  const [lx,ly]=lane.points[0],[mx,my]=lane.points.at(-1),lz=world.obstacles.find(o=>o.id.startsWith('nb-'))?.center[2]??45;
  views.laneLow={eye:[lx-(mx-lx)*.6+18,ly-(my-ly)*.6+14,lz+26],target:[(lx+mx)/2,(ly+my)/2,lz-6],fov:58,mode:'dusk',time:27};
}
if(world.vaderland.parallax){
  views.courtArrival={eye:[32.5,2356.6,32.7],target:[71,2380,42.2],fov:59,mode:'dusk',time:27};
  views.courtDrive={eye:[-4,2255,31.3],target:[4,2435,37],fov:58,mode:'dusk',time:27};
  views.courtGarden={eye:[51.1,2366,32.66],target:[70.4,2384.8,39.1],fov:63,mode:'dusk',time:27};
  views.courtCanopy={eye:[61.5,2371.6,33.05],target:[72.0,2385.4,37.3],fov:66,mode:'night',time:27};
  views.courtWindows={eye:[67.0,2374.1,33.55],target:[72.2,2378.5,34.55],fov:58,mode:'night',time:27};
  views.courtArmillary={eye:[49.6,2382.6,32.7],target:[58.5,2391,36.2],fov:59,mode:'dusk',time:27};
  views.courtAerial={eye:[-36,2291,65],target:[64,2379,42],fov:52,mode:'dusk',time:27};
}
if(Number(world.version)>=20){
  const room=world.vaderland.instrument_room??{
    origin:[71.999,2379.781,31.177],
    basis:[[-.10184,.9948,0],[-.9948,-.10184,0],[0,0,1]],
  };
  const [u,d]=room.basis;
  const at=(x,y,z)=>room.origin.map((p,i)=>p+x*u[i]+y*d[i]+(i===2?z:0));
  views.instrumentApproach={eye:at(-5.55,11.0,1.78),target:at(-1.8,-4.3,2.94),fov:61,mode:'dusk',time:27};
  views.instrumentDepth={eye:at(-5.8,1.55,1.68),target:at(-3.75,-5.56,3.0),fov:61,mode:'night',time:18};
  if(world.vaderland.instrument_room){
    views.instrumentInterior={eye:at(.49,-1.31,2.02),target:at(-3.52,-5.67,2.97),fov:71,mode:'night',time:27};
    views.instrumentBench={eye:at(-.12,-5.69,2.16),target:at(4.8,-9.58,2.2),fov:65,mode:'night',time:18};
    views.instrumentOptics={eye:at(.99,-3.02,2.18),target:at(5.31,-5.55,1.90),fov:66,mode:'night',time:26};
    views.instrumentReverse={eye:at(-6.89,-9.62,2.31),target:at(-3.11,-2.14,3.01),fov:65,mode:'dusk',time:27};
  }
}
if(world.vaderland.cathedral){
  views.cathedralEntry={eye:[2796,-4379,149.1],target:[2874,-4351,154.5],fov:52,mode:'dusk',time:31};
  views.cathedralRoad={eye:[2821,-4356,146.35],target:[2902,-4350,149.0],fov:60,mode:'dusk',time:31};
  views.cathedralVault={eye:[2915,-4356,146.0],target:[3116,-4350,147.25],fov:65,mode:'night',time:31};
  views.cathedralRidge={eye:[2732,-4449,198],target:[2905,-4350,150.],fov:47,mode:'dusk',time:31};
}
const browser = await chromium.launch({
  executablePath:process.env.VTX_CHROME || undefined, headless:true,
  args:['--enable-gpu','--ignore-gpu-blocklist','--disable-background-timer-throttling'],
});
try {
  const page = await browser.newPage({viewport:{width:1500,height:900}, deviceScaleFactor:1});
  const errors = [], external = new Set();
  page.on('pageerror', e => {errors.push(String(e));console.error(e);});
  page.on('console', m => { if(process.env.VTX_PHOTO_DIAGNOSTIC)console.log(m.type(),m.text().slice(0,500)); if(m.type()==='error'){errors.push(m.text());console.error(m.text());} });
  await page.routeWebSocket('**/*', () => {});
  await page.addInitScript(() => { window.__vtxNoRender = true; });
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if(url.origin!==origin){
      external.add(url.origin);
      return route.fulfill({status:200,contentType:'text/css',body:''});
    }
    if(request.method()!=='GET')return route.abort();
    if(url.pathname==='/api/world') return route.fulfill({json:world});
    if(marine && url.pathname==='/api/harbour/model'){
      const id=url.searchParams.get('boatId');
      if(!marine.boats.some(b=>b.id===id))return route.fulfill({status:404,body:''});
      const body=gunzipSync(await readFile(path.join(directory,'model-'+id+'.json.gz')));
      return route.fulfill({contentType:'application/json',body});
    }
    if(url.pathname.startsWith('/api/')) {
      const body = url.pathname.includes('harbour') ? marine??{available:false,boats:[],berths:[]}
        : url.pathname.includes('runs') ? {runs:[]} : {active:false,inspection_selection_known:false};
      return route.fulfill({json:body});
    }
    const relative = url.pathname==='/' ? 'index.html' : decodeURIComponent(url.pathname.slice(1));
    const file = path.resolve(root, relative);
    if(!file.startsWith(path.resolve(root)+path.sep)) return route.abort();
    try { return await route.fulfill({path:file}); }
    catch { return route.fulfill({status:404,body:''}); }
  });
  const built = page.waitForEvent('console', {predicate:m=>m.text().includes('terrain ready '+world.id),timeout:120000});
  await page.goto(origin+'/?debug&quality=high');
  await built;
  await page.evaluate(async () => {
    await document.fonts.ready;
    const v = window.__vtx;
    await v.environment.vaderland?.ready;
    v.renderer.setPixelRatio(1);
    v.renderer.setSize(1440,810,false);
    v.post?.setSize(1440,810);
  });
  if(world.vaderland.city_lights){
    const cycle=await page.evaluate(()=>{
      const button=document.getElementById('time-of-day'),time=window.__vtx.timeOfDay;
      const start=time.mode,states=[start];
      for(let i=0;i<3;i++){button.click();states.push(time.mode);}
      return states;
    });
    await writeFile(path.join(directory,'lighting-controls.json'),JSON.stringify(cycle));
    if(cycle.join('/')!=='dusk/night/day/dusk')errors.push('Dusk lighting control cycle '+cycle.join('/'));
  }
  if(process.argv.includes('--reflection-probes')){
    for(const mode of ['day','night']){
      const data=await page.evaluate(mode=>{
        const {THREE,scene,renderer,sky,environment,camera}=window.__vtx;
        const cam=camera.clone();cam.position.set(-12,2328,79);
        window.__vtx.timeOfDay.set(mode);sky.update(cam,0);environment.vaderland.update(cam,0,mode,27);
        const uniforms=[];
        scene.traverse(node=>{if(node.material?.uniforms?.cityReflectionReady)uniforms.push(node.material.uniforms.cityReflectionReady);});
        const saved=uniforms.map(u=>u.value);uniforms.forEach(u=>u.value=0);
        const rt=new THREE.WebGLCubeRenderTarget(512,{type:THREE.HalfFloatType,minFilter:THREE.LinearFilter});
        const eye=new THREE.CubeCamera(.35,20000,rt);eye.position.copy(cam.position);eye.update(renderer,scene);
        const screen=new THREE.Scene(),ortho=new THREE.Camera();
        const material=new THREE.ShaderMaterial({uniforms:{capture:{value:rt.texture}},depthTest:false,depthWrite:false,
          vertexShader:'varying vec2 st;void main(){st=uv;gl_Position=vec4(position.xy,0.,1.);}',
          fragmentShader:`varying vec2 st;uniform samplerCube capture;void main(){
            float a=(st.x-.5)*6.28318530718,e=(st.y-.5)*3.14159265359;
            vec3 d=vec3(cos(a)*cos(e),sin(a)*cos(e),sin(e));
            gl_FragColor=vec4(textureCube(capture,d).rgb,1.);
            #include <colorspace_fragment>
          }`});
        const plane=new THREE.PlaneGeometry(2,2);screen.add(new THREE.Mesh(plane,material));
        renderer.setSize(1536,768,false);renderer.render(screen,ortho);
        const result=renderer.domElement.toDataURL('image/png').split(',')[1];
        uniforms.forEach((u,i)=>u.value=saved[i]);plane.dispose();material.dispose();rt.dispose();
        renderer.setSize(1440,810,false);return result;
      },mode);
      await writeFile(path.join(directory,'avenue-reflection-'+mode+'.png'),Buffer.from(data,'base64'));
    }
  }
  const results = {};
  const extraRays=await readFile(path.join(directory,'architecture-rays.json'),'utf8').then(JSON.parse).catch(e=>{if(e.code!=='ENOENT')throw e;return [];});
  const gates=await readFile(path.join(directory,'gates.json'),'utf8').then(JSON.parse).catch(e=>{if(e.code!=='ENOENT')throw e;});
  if((gates||extraRays.length)&&!marine){
    const tested=await page.evaluate(({samples,hulls})=>{
      const {THREE,scene,environment,camera}=window.__vtx;
      const objects=[];
      scene.traverse(n=>{if(n.isMesh&&(n.userData.surveySpans||n.userData.sceneryIds||n.name==='Vaderland terrain'))objects.push(n);});
      return samples.map(p=>{
        environment.vaderland.update(camera,0,'day',p.time,p.doors);scene.updateMatrixWorld(true);
        const range=p.range_m??(p.direction[0]?140:95);
        const ray=new THREE.Raycaster(new THREE.Vector3(...p.origin),new THREE.Vector3(...p.direction),0,range);
        const hits=ray.intersectObjects(objects,false);
        const collider=h=>h.object.userData.surveySpans?.find(s=>h.faceIndex<s.end)?.id??
          h.object.userData.sceneryIds?.[h.instanceId]??(h.object.name==='Vaderland terrain'?'terrain':null);
        const h=hits.find(v=>collider(v));const native=p.distance_m>=0&&p.distance_m<range?p.geom:null;
        const actual=h?collider(h):null;
        const coincident=h&&hits.some(v=>v.distance-h.distance<.001&&collider(v)===native);
        const error=h&&native?Math.abs(h.distance-p.distance_m):null;
        function onSurface(id){
          const hull=hulls[id];if(!hull||!h)return false;
          const hit=h.point.clone(),m=hull.motion;
          if(m){
            const origin=new THREE.Vector3(...m.origin),axis=m.door||m.axis==='x'?new THREE.Vector3(1,0,0):new THREE.Vector3(0,0,1);
            const angle=m.door?m.travel_rad*(p.doors[m.door]??1):2*Math.PI*p.time/m.period_s;
            hit.sub(origin).applyAxisAngle(axis,-angle).add(origin);
          }
          hit.sub(new THREE.Vector3(...hull.center));
          return Math.abs(Math.max(...hull.planes.map(([x,y,z,d])=>x*hit.x+y*hit.y+z*hit.z+d)))<.0008;
        }
        const joint=native!==actual&&error!==null&&error<.0008&&onSurface(native)&&onSurface(actual);
        return {...p,native,actual,actual_m:h?.distance??null,error_m:error,coincident:!!coincident,shared_joint:!!joint,
          agrees:(native===actual||!!coincident||joint)&&(error===null||error<.002)};
      });
    },{samples:[...extraRays,...(gates?.probes??[]),...(gates?.travel??[]).map(s=>({...s,time:s.t,doors:{west:s.open,east:1}}))],
       hulls:Object.fromEntries(world.obstacles.filter(o=>o.motion || (world.vaderland.parallax && (o.id.startsWith('parallax-')||o.id.startsWith('court-')||o.id.startsWith('instrument-')||o.id.startsWith('cathedral-')))).map(o=>[o.id,{center:o.center,planes:o.planes,motion:o.motion}]))});
    await writeFile(path.join(directory,'client-gates.json'),JSON.stringify(tested,null,2));
    if(tested.some(s=>!s.agrees))errors.push('Rendered scenery differs from native collision surfaces');
  }
  const people=await readFile(path.join(directory,'market-people.json'),'utf8').then(JSON.parse).catch(e=>{if(e.code!=='ENOENT')throw e;});
  if(people&&!marine){
    const result=await page.evaluate(({camera:eye,heads})=>{
      const {THREE,scene,environment,camera}=window.__vtx;const cam=camera.clone();cam.position.set(...eye);
      const body=scene.getObjectByProperty('name','Meridian commuters'),matrix=new THREE.Matrix4(),v=new THREE.Vector3();
      let tick=null;
      return heads.map(s=>{
        if(s.time!==tick){environment.vaderland.update(cam,s.time,'night',s.time);tick=s.time;}
        const idx=body.userData.pedestrianHeads.get(s.name);
        if(idx===undefined)return {name:s.name,time:s.time,error_m:null};
        body.getMatrixAt(idx,matrix);v.setFromMatrixPosition(matrix);
        return {name:s.name,time:s.time,error_m:v.distanceTo(new THREE.Vector3(...s.head))};
      });
    },people);
    await writeFile(path.join(directory,'client-people.json'),JSON.stringify(result));
    if(result.some(v=>v.error_m===null||v.error_m>.002))errors.push('A commuter disagrees with its native transform');
  }
  const shells=await readFile(path.join(directory,'airport-shells.json'),'utf8').then(JSON.parse).catch(e=>{if(e.code!=='ENOENT')throw e;});
  if(shells && !marine){
    const test=await page.evaluate(({probes,hulls})=>{
      const {scene,THREE}=window.__vtx;scene.updateMatrixWorld(true);
      const items=[];
      scene.traverse(n=>{if(n.isMesh && (n.userData.surveySpans || n.userData.sceneryIds || n.name==='Vaderland terrain'))items.push(n);});
      return probes.map(p=>{
        const ray=new THREE.Raycaster(new THREE.Vector3(...p.origin),new THREE.Vector3(...p.direction),0,12000);
        function collider(h){
          return h.object.userData.surveySpans?.find(s=>h.faceIndex<s.end)?.id??
                 h.object.userData.sceneryIds?.[h.instanceId]??(h.object.name==='Vaderland terrain'?'terrain':null);
        }
        const h=ray.intersectObjects(items,false).find(hit=>collider(hit));
        const id=h?collider(h):null;
        const error=h&&p.distance_m>=0?Math.abs(h.distance-p.distance_m):null;
        function onSurface(key){
          const hull=hulls[key];if(!hull || !h)return false;
          const xyz=h.point.toArray().map((v,i)=>v-hull.center[i]);
          const signed=Math.max(...hull.planes.map(([nx,ny,nz,d])=>nx*xyz[0]+ny*xyz[1]+nz*xyz[2]+d));
          return Math.abs(signed)<.0008;
        }
        const shared=error!==null && error<.0008 && id!==p.geom && onSurface(id) && onSurface(p.geom);
        return {...p,client:id,client_m:h?.distance??null,error_m:error,shared_joint:shared};
      });
    },{probes:shells.probes,hulls:Object.fromEntries(world.obstacles.filter(o=>o.kind==='mesh').map(o=>[o.id,{center:o.center,planes:o.planes}]))});
    await writeFile(path.join(directory,'client-shells.json'),JSON.stringify(test,null,2));
    if(test.some(p=>p.geom!==p.client && !p.shared_joint || (p.error_m!==null && p.error_m>.04)))errors.push('Terminal shell survey mismatch');
  }
  const berths=await readFile(path.join(directory,'airport-berths.json'),'utf8').then(JSON.parse).catch(e=>{if(e.code!=='ENOENT')throw e;});
  if(berths && !marine){
    const compared=await page.evaluate(probes=>{
      const {THREE,scene,harbourLayer}=window.__vtx;
      scene.updateMatrixWorld(true);
      const objects=[...harbourLayer.structureNodes.values()];
      return probes.map(p=>{
        const ray=new THREE.Raycaster(new THREE.Vector3(...p.origin),new THREE.Vector3(...p.direction));
        const hit=ray.intersectObjects(objects,false)[0];
        return {label:p.label,client:hit?.object.name,client_m:hit?.distance??null,air_m:p.air.distance_m,
          marine_m:p.marine.distance_m,air_geom:p.air.geom,marine_geom:p.marine.geom};
      });
    },berths.probes);
    await writeFile(path.join(directory,'client-berths.json'),JSON.stringify(compared,null,2));
    if(world.vaderland.landing && compared.some(p=>!p.client || p.air_m<0 || p.marine_m<0 ||
       Math.max(Math.abs(p.air_m-p.client_m),Math.abs(p.marine_m-p.client_m))>.025))
      errors.push('Airport Landing dock bounds disagree between world models');
  }
  if(marine){
    const receipt=JSON.parse(await readFile(path.join(directory,'sound.json'),'utf8'));
    await page.evaluate(state=>window.__vtx.harbourLayer.update(state,{snap:true}),marine);
    await page.waitForFunction(count=>window.__vtx.harbourLayer.boats.size===count,marine.boats.length,{timeout:40000});
    const water=await page.evaluate(probes=>{
      const {scene,THREE,harbourLayer}=window.__vtx;
      scene.updateMatrixWorld(true);
      return probes.map(p=>{
        const ray=new THREE.Raycaster(new THREE.Vector3(...p.xy,3500),new THREE.Vector3(0,0,-1));
        const hit=ray.intersectObject(harbourLayer.water)[0];
        return {...p,client_m:hit?.point.z??null,error_m:hit?Math.abs(hit.point.z-p.surface_m):null};
      });
    },receipt.probes);
    await writeFile(path.join(directory,'client-water.json'),JSON.stringify(water,null,2));
    if(world.vaderland.harbour_surface && water.some(p=>p.lattice && p.depth_m>.1 && (p.error_m===null || p.error_m>.003)))
      errors.push('Surveyed water nodes disagree with the native free surface');
    const boat=marine.boats[0],[x,y]=boat.position,z=marine.water_level_m;
    const dx=Math.cos(boat.heading_rad),dy=Math.sin(boat.heading_rad);
    const point=(along,across,h)=>[x+along*dx-across*dy,y+along*dy+across*dx,z+h];
    views.harbourAir={eye:point(-180,130,135),target:point(4,0,1),fov:52};
    views.hull={eye:point(-23,13,7.6),target:point(-3,0,.6),fov:48};
    views.waterline={eye:point(-13,-7,2.3),target:point(-1,0,.6),fov:56};
  }
  const clearance = await readFile(path.join(directory,'clearance.json'),'utf8').then(JSON.parse).catch(e=>{if(e.code!=='ENOENT')throw e;});
  if(clearance){
    const compared=await page.evaluate(probes=>{
      const {scene,THREE}=window.__vtx;
      scene.updateMatrixWorld(true);
      const solid=[];
      scene.traverse(n=>{if(n.name==='Vaderland terrain'||n.name.startsWith('gallery-')||n.userData.sceneryIds)solid.push(n);});
      return probes.map(p=>{
        const ray=new THREE.Raycaster(new THREE.Vector3(...p.origin),new THREE.Vector3(...p.direction),0,10000);
        const hit=ray.intersectObjects(solid,false)[0];
        const name=hit?.object.name==='Vaderland terrain'?'terrain':hit?.object.userData.sceneryIds?.[hit.instanceId]??hit?.object.name??null;
        const error=hit && p.distance_m!==null?Math.abs(hit.distance-p.distance_m):null;
        return {label:p.label,client:name,client_distance_m:hit?.distance??null,native:p.geom,native_distance_m:p.distance_m,error_m:error,
          agrees:name===p.geom && (error===null || error<.03)};
      });
    },clearance.probes);
    await writeFile(path.join(directory,'client-rays.json'),JSON.stringify(compared,null,2));
    for(const test of compared)if(!test.agrees)errors.push('client/native ray '+JSON.stringify(test));
  }
  const traffic=await readFile(path.join(directory,'traffic.json'),'utf8').then(JSON.parse).catch(e=>{if(e.code!=='ENOENT')throw e;});
  const sets=[];
  if(traffic && !marine)sets.push(['traffic',await Promise.all([0,1,2,3].map(i=>readFile(path.join(directory,`lane-${i}-pose.json`),'utf8').then(JSON.parse)))]);
  if(!marine)for(const which of ['hangar','gangway','pickup','circle','speedway-scale']){
    const pose=await readFile(path.join(directory,which+'-pose.json'),'utf8').then(JSON.parse).catch(e=>{if(e.code!=='ENOENT')throw e;});
    if(pose)sets.push([which,[pose]]);
  }
  for(const [name,poses] of sets){
    const receipt=await page.evaluate(async ({poses,name})=>{
      const {scene,THREE}=window.__vtx;
      const {GLTFLoader}=await import('/vendor/GLTFLoader.js');
      const {loadPinnedGltf}=await import('/visual-identity.js');
      const {attachPhantom,updatePhantom}=await import('/vtx-env/phantom-look.js?v=20261118-a10d');
      const gltf=await loadPinnedGltf(new GLTFLoader(),poses[0].provenance.render_asset);
      const all=new THREE.Group();all.name='Recorded '+name;all.userData.photoSubject=name;scene.add(all);
      const bounds=[];
      for(const pose of poses){
        let model=gltf.scene.clone(true);
        if(!model.getObjectByName('airframe')){
          model.rotation.x=Math.PI/2;
          const group=new THREE.Group();group.name='airframe';group.add(model);model=group;
        }
        all.add(model);
        const rig=attachPhantom(model);
        for(const [name,spec] of Object.entries(pose.body_poses)){
          const node=model.getObjectByName(name);if(!node)continue;
          node.position.set(...spec.position);const [w,x,y,z]=spec.quaternion_wxyz;node.quaternion.set(x,y,z,w);
        }
        updatePhantom(rig,pose,false,[],true);model.updateMatrixWorld(true);
        const box=new THREE.Box3(),v=new THREE.Vector3();
        model.traverseVisible(n=>{
          const pos=n.isMesh?n.geometry?.attributes.position:null;
          if(!pos || n.material?.transparent && n.material.opacity===0) return;
          for(let i=0;i<pos.count;i++)box.expandByPoint(v.fromBufferAttribute(pos,i).applyMatrix4(n.matrixWorld));
        });
        bounds.push({time_s:pose.t_s,min:box.min.toArray(),max:box.max.toArray(),dimensions_m:box.getSize(v).toArray()});
      }
      const cabin=poses[0].body_poses.cabin,eye=new THREE.Vector3(...cabin.position);
      const [w,x,y,z]=cabin.quaternion_wxyz;
      const ahead=new THREE.Vector3(1,0,0).applyQuaternion(new THREE.Quaternion(x,y,z,w));
      all.visible=false;return {bounds,eye:eye.toArray(),target:eye.clone().addScaledVector(ahead,65).toArray()};
    },{poses,name});
    if(name==='traffic'){
      await writeFile(path.join(directory,'visual-envelopes.json'),JSON.stringify(receipt.bounds,null,2));
      views.traffic={eye:[3185,-4350,147.7],target:[3200,-4350,144.55],fov:62,subject:name};
    }else{
      const p=poses[0].body_poses.airframe.position;
      const delta=name==='hangar'?[-15,-5,2.8]:name==='gangway'?[-6,10,4.9]:[-11,-6,3.5];
      views[name+'Drive']={eye:p.map((v,i)=>v+delta[i]),target:[p[0],p[1],p[2]+.9],fov:52,subject:name};
      views[name+'Eye']={eye:receipt.eye,target:receipt.target,fov:64};
      if(name==='speedway-scale'){
        const q=poses[0].body_poses.airframe.position;
        views.velocityChase={eye:[q[0]+3.2,q[1]-11,q[2]+3.15],target:[q[0]-3,q[1]+22,q[2]+2.8],fov:60,subject:name,mode:'night'};
        views.velocityScale={eye:[q[0]+31,q[1]-49,q[2]+16],target:[q[0]-12,q[1]+45,q[2]+14],fov:59,subject:name,mode:'night'};
      }
    }
  }
  const selected=process.env.VTX_VIEWS?.split(',');
  if(process.argv.includes('--velocity-film')){
    const receipt=JSON.parse(await readFile(path.join(directory,'speedway-motion.json'),'utf8'));
    const dir=path.join(directory,'velocity-frames');await mkdir(dir,{recursive:true});
    const fps=receipt.frame_rate, light=world.vaderland.city_lights?'dusk':'night';
    await page.evaluate(light=>{window.__vtx.timeOfDay.set(light);window.__vtx.renderer.setSize(1280,720,false);},light);
    for(const [i,frame] of receipt.frames.entries()){
      const jpg=await page.evaluate(({frame,light})=>{
        const {THREE,scene,renderer,camera,environment,sky}=window.__vtx;
        const group=scene.getObjectByName('Recorded speedway-scale');group.visible=true;
        const model=group.children[0];
        for(const [name,s] of Object.entries(frame.bodies)){
          const node=model.getObjectByName(name);if(!node)continue;
          const [w,x,y,z]=s.quaternion_wxyz;node.position.set(...s.position);node.quaternion.set(x,y,z,w);
        }
        const craft=frame.bodies.airframe,[w,x,y,z]=craft.quaternion_wxyz,q=new THREE.Quaternion(x,y,z,w);
        const origin=new THREE.Vector3(...craft.position);
        const eye=new THREE.Vector3(-10.5,-1.75,2.85).applyQuaternion(q).add(origin);
        const ahead=new THREE.Vector3(31,0,2.42).applyQuaternion(q).add(origin);
        const cam=camera.clone();cam.aspect=16/9;cam.fov=64;cam.position.copy(eye);cam.lookAt(ahead);cam.updateProjectionMatrix();cam.updateMatrixWorld();
        sky.update(cam,frame.time_s);environment.vaderland.update(cam,frame.time_s,light,frame.time_s);
        renderer.render(scene,cam);return renderer.domElement.toDataURL('image/jpeg',.93).split(',')[1];
      },{frame,light});
      await writeFile(path.join(dir,String(i).padStart(4,'0')+'.jpg'),Buffer.from(jpg,'base64'));
    }
    await writeFile(path.join(directory,'velocity-film-timing.json'),JSON.stringify({fps,count:receipt.frames.length,
      first_native_s:receipt.frames[0].time_s,last_native_s:receipt.frames.at(-1).time_s,
      source:'speedway-motion.json',max_frame_phase_error_s:Math.max(...receipt.frames.map((f,i)=>Math.abs(f.time_s-(3+i/fps))))}));
    await page.evaluate(pose=>{
      const g=window.__vtx.scene.getObjectByName('Recorded speedway-scale'),model=g.children[0];
      for(const [name,s] of Object.entries(pose.body_poses)){
        const n=model.getObjectByName(name);if(!n)continue;
        const [w,x,y,z]=s.quaternion_wxyz;n.position.set(...s.position);n.quaternion.set(x,y,z,w);
      }
      model.updateMatrixWorld(true);g.visible=false;window.__vtx.renderer.setSize(1440,810,false);
    },sets.find(([name])=>name==='speedway-scale')[1][0]);
  }
  if(process.argv.includes('--instrument-film') && world.vaderland.instrument_room){
    const room=world.vaderland.instrument_room,directoryName='instrument-frames';
    const folder=path.join(directory,directoryName);await mkdir(folder,{recursive:true});
    const fps=24, count=fps*11;
    await page.evaluate(()=>{
      const v=window.__vtx;
      v.timeOfDay.set('dusk');v.renderer.setSize(1280,720,false);v.post?.setSize(1280,720);
    });
    for(let i=0;i<count;i++){
      const jpg=await page.evaluate(({i,fps,room})=>{
        const {THREE,scene,camera,renderer,sky,environment,post}=window.__vtx;
        const u=new THREE.Vector3(...room.basis[0]),d=new THREE.Vector3(...room.basis[1]);
        const origin=new THREE.Vector3(...room.origin);
        const at=(x,y,z)=>origin.clone().addScaledVector(u,x).addScaledVector(d,y).add(new THREE.Vector3(0,0,z));
        const t=i/fps,r=Math.min(1.,t/10.5),stride=r*r*(3.-2.*r);
        const turn=THREE.MathUtils.smoothstep(t,2.0,7.6);
        const cam=camera.clone();
        cam.position.copy(at(.22,7.4-13.15*stride,1.83+.13*stride));
        cam.up.set(0,0,1);cam.lookAt(at(-4.03*turn,-3.0-3.5*turn,2.32+.57*turn));
        cam.aspect=16/9;cam.fov=63;cam.updateProjectionMatrix();cam.updateMatrixWorld();
        const sceneryTime=12+t;
        sky.update(cam,t);
        environment.vaderland.update(cam,t,'dusk',sceneryTime);
        if(post)post.render(cam);else renderer.render(scene,cam);
        return renderer.domElement.toDataURL('image/jpeg',.92).split(',')[1];
      },{i,fps,room});
      await writeFile(path.join(folder,String(i).padStart(4,'0')+'.jpg'),Buffer.from(jpg,'base64'));
    }
    await writeFile(path.join(directory,'instrument-film-timing.json'),
                    JSON.stringify({frames:count,fps,first_scene_time_s:12}));
    await page.evaluate(()=>{
      const v=window.__vtx;v.renderer.setSize(1440,810,false);v.post?.setSize(1440,810);
    });
  }
  const courtFilm=process.argv.includes('--court-film');
  if(courtFilm||process.argv.includes('--parallax-film')){
    const source=courtFilm?'court-drive-motion.json':'parallax-flight.json';
    const [pass]=JSON.parse(await readFile(path.join(directory,source),'utf8'));
    const prefix=courtFilm?'court':'parallax';
    const folder=path.join(directory,prefix+'-frames');await mkdir(folder,{recursive:true});
    const fps=24, count=Math.floor(pass.frames.at(-1).time_s*fps);
    await page.evaluate(()=>{const v=window.__vtx;v.timeOfDay.set('dusk');v.renderer.setSize(1280,720,false);v.post?.setSize(1280,720);});
    for(let i=0;i<=count;i++){
      const tick=i/fps,j=pass.frames.findIndex(f=>f.time_s>=tick);
      const b=pass.frames[j],a=pass.frames[Math.max(0,j-1)];
      const fraction=a===b?0:(tick-a.time_s)/(b.time_s-a.time_s);
      const result=await page.evaluate(({a,b,fraction,tick,courtFilm})=>{
        const {THREE,scene,renderer,camera,sky,environment,post}=window.__vtx;
        const cam=camera.clone();
        const position=new THREE.Vector3(...a.position).lerp(new THREE.Vector3(...b.position),fraction);
        const rotation=f=>{const [w,x,y,z]=f.quaternion_wxyz;return new THREE.Quaternion(x,y,z,w);};
        const attitude=rotation(a).slerp(rotation(b),fraction);
        const offset=courtFilm?[2.4,-.25,1.64]:[4.5,0,1.35];
        const look=courtFilm?[1,-.23,.035]:[1,0,0];
        cam.position.copy(new THREE.Vector3(...offset).applyQuaternion(attitude).add(position));
        cam.up.set(0,0,1);cam.lookAt(cam.position.clone().add(new THREE.Vector3(...look).applyQuaternion(attitude)));
        cam.aspect=16/9;cam.fov=71;cam.updateProjectionMatrix();cam.updateMatrixWorld();
        sky.update(cam,tick);environment.vaderland.update(cam,tick,'dusk',27+tick);
        if(courtFilm&&post)post.render(cam);else renderer.render(scene,cam);
        return renderer.domElement.toDataURL('image/jpeg',.92).split(',')[1];
      },{a,b,fraction,tick,courtFilm});
      await writeFile(path.join(folder,String(i).padStart(4,'0')+'.jpg'),Buffer.from(result,'base64'));
    }
    await writeFile(path.join(directory,prefix+'-film-timing.json'),JSON.stringify({fps,frames:count+1,
      native_seconds:pass.frames.at(-1).time_s,source,offset_m:pass.offset_m}));
    await page.evaluate(()=>window.__vtx.renderer.setSize(1440,810,false));
  }
  if(process.argv.includes('--market-film') && views.eveningMarket){
    const dir=path.join(directory,'market-frames');await mkdir(dir,{recursive:true});
    await page.evaluate(()=>{window.__vtx.timeOfDay.set('night');window.__vtx.renderer.setSize(1280,720,false);});
    for(let i=0;i<150;i++){
      const jpg=await page.evaluate(({view,t})=>{
        const {scene,THREE,renderer,camera,environment,sky}=window.__vtx;
        for(const g of scene.children)if(g.userData.photoSubject)g.visible=false;
        const cam=camera.clone(),u=(t-12)/5;cam.aspect=16/9;cam.fov=62;
        cam.position.set(...view.eye);cam.position.x+=u*2.1;cam.position.y+=u*.87;
        cam.lookAt(new THREE.Vector3(...view.target));cam.updateProjectionMatrix();cam.updateMatrixWorld();
        sky.update(cam,t);environment.vaderland.update(cam,t,'night',t);renderer.render(scene,cam);
        return renderer.domElement.toDataURL('image/jpeg',.93).split(',')[1];
      },{view:views.eveningMarket,t:12+i/30});
      await writeFile(path.join(dir,String(i).padStart(4,'0')+'.jpg'),Buffer.from(jpg,'base64'));
    }
    await page.evaluate(()=>window.__vtx.renderer.setSize(1440,810,false));
  }
  if(process.argv.includes('--film')){
    const {frames}=JSON.parse(await readFile(path.join(directory,'flight-west.json'),'utf8'));
    const dir=path.join(directory,'flight-frames');await mkdir(dir,{recursive:true});
    await page.evaluate(()=>window.__vtx.timeOfDay.set('day'));
    const fps=30,count=Math.floor((frames.at(-1).t_s-frames[0].t_s)*fps)+1;
    let i=0;
    for(let j=0;j<count;j++){
      const t=frames[0].t_s+j/fps;
      while(i+2<frames.length&&frames[i+1].t_s<t)i++;
      const a=frames[i],b=frames[i+1];
      const data=await page.evaluate(({a,b,t})=>{
        const {THREE,scene,camera:base,renderer,sky,environment}=window.__vtx;
        renderer.setSize(1280,720,false);
        const f=(t-a.t_s)/(b.t_s-a.t_s);
        const quat=q=>new THREE.Quaternion(q[1],q[2],q[3],q[0]),att=quat(a.quat).slerp(quat(b.quat),f);
        const position=new THREE.Vector3(...a.position).lerp(new THREE.Vector3(...b.position),f);
        const eye=position.add(new THREE.Vector3(.8,0,.55).applyQuaternion(att));
        const cam=base.clone();cam.aspect=16/9;cam.fov=70;cam.updateProjectionMatrix();
        cam.position.copy(eye);cam.up.set(0,0,1).applyQuaternion(att);
        cam.lookAt(eye.clone().add(new THREE.Vector3(80,0,0).applyQuaternion(att)));cam.updateMatrixWorld();
        sky.update(cam,t);environment.vaderland.update(cam,t,'day',t,{west:1,east:1});
        renderer.render(scene,cam);return renderer.domElement.toDataURL('image/jpeg',.94).split(',')[1];
      },{a,b,t});
      await writeFile(path.join(dir,String(j).padStart(4,'0')+'.jpg'),Buffer.from(data,'base64'));
    }
    await writeFile(path.join(directory,'film-timing.json'),JSON.stringify({fps,count,pixels:[1280,720],physics_s:frames.at(-1).t_s,frames_source:'flight-west.json',synchronized:'Original MuJoCo position, SLERP attitude, 1:1 simulation time'}));
    await page.evaluate(()=>window.__vtx.renderer.setSize(1440,810,false));
  }
  if(process.argv.includes('--cadence')){
    const sets=[views.velocityGrid,views.marketStreetAir,views.eveningMarket,views.avenueDusk,views.skylineDusk,views.vesper].filter(Boolean);
    const report=[];
    for(const view of sets){
      const r=await page.evaluate(async view=>{
        const {THREE,scene,environment,camera,renderer,sky}=window.__vtx,cam=camera.clone();
        cam.aspect=16/9;cam.fov=view.fov;cam.position.set(...view.eye);cam.lookAt(new THREE.Vector3(...view.target));cam.updateProjectionMatrix();
        const light=view.mode??'night';window.__vtx.timeOfDay.set(light);const gl=renderer.getContext(),pixel=new Uint8Array(4),frames=[];
        for(let k=0;k<132;k++){
          const start=performance.now();const t=12+k/60;
          environment.vaderland.update(cam,t,light,t);sky.update(cam,t);renderer.render(scene,cam);gl.readPixels(720,405,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
          if(k>=12)frames.push(performance.now()-start);
          if(k%12===0)await new Promise(r=>setTimeout(r,0));
        }
        return {samples:frames,triangles:renderer.info.render.triangles,draws:renderer.info.render.calls};
      },view);report.push({view,...r});
    }
    await writeFile(path.join(directory,'frame-cadence.json'),JSON.stringify(report));
  }
  for (const [name,view] of Object.entries(views)) {
    if(selected&&!selected.includes(name))continue;
    if(marine && !['harbourAir','hull','waterline'].includes(name))continue;
    const capture = await page.evaluate(({eye,target,fov,subject,time=0,doors,mode='day'})=>{
      const {THREE,scene,renderer,sky,environment,camera:main}=window.__vtx;
      for(const layer of scene.children)if(layer.userData.photoSubject)layer.visible=layer.userData.photoSubject===subject;
      const camera = main.clone();
      camera.aspect=16/9; camera.fov=fov; camera.updateProjectionMatrix();
      camera.position.set(...eye); camera.lookAt(...target); camera.updateMatrixWorld();
      window.__vtx.timeOfDay.set(mode);sky.update(camera,0); environment.vaderland?.update(camera,0,mode,time,doors);
      const post=environment.vaderland?.cityGlow?window.__vtx.post:null;
      post?.setSize(1440,810);
      const draw=()=>{
        renderer.info.reset();
        if(post)post.render(camera);else renderer.render(scene,camera);
      };
      renderer.info.autoReset=false;
      draw();
      const gl=renderer.getContext(), ext=gl.getExtension('WEBGL_debug_renderer_info');
      gl.finish();
      const times=[],pixel=new Uint8Array(4);
      for(let i=0;i<21;i++){
        const t=performance.now();draw();
        gl.readPixels(720,405,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
        if(i>1) times.push(performance.now()-t);
      }
      renderer.info.autoReset=true;
      return {image:renderer.domElement.toDataURL('image/jpeg',.93).split(',')[1], times,bloom:!!post?.enabled,
        gpu:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),
        calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,
        near:camera.near,far:camera.far};
    },view);
    await writeFile(path.join(directory,name+'.jpg'),Buffer.from(capture.image,'base64'));
    delete capture.image; results[name]={...view,...capture};
  }
  if(process.argv.includes('--require-local-assets') && external.size)
    errors.push('Packaged scenery requested external assets from '+[...external].join(', '));
  await writeFile(path.join(directory,marine?'marine-webgl.json':'webgl.json'),JSON.stringify({world:world.id,quality:'high',pixels:[1440,810],
    timing:'Wall time including synchronous one-pixel framebuffer readback, 2 warm-up + 19 timed frames per view.',
    external_requests_intercepted:[...external],results,errors},null,2));
  console.log(world.id,Object.entries(results).map(([k,v])=>[k,v.calls,v.triangles]),Object.values(results)[0]?.gpu,errors);
  if(errors.length)process.exitCode=1;
} finally { await browser.close(); }
