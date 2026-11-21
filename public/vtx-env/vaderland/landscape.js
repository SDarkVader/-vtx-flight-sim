import * as THREE from 'three';
import {heightfieldZ} from '../landscape.js';
import {createGround} from '../ground.js';
import {primaryRunwayCues} from '../runway-layout.js';
import {followTide} from './tidal-surface.js';
import {airportTree,buildAirport} from './airfield.js';
import {dressHarbourDecks,dressLanding} from './landing.js';
import {buildTerminal} from './terminal.js';
import {district} from './district.js';
import {surveyedOptics} from './optics.js';
import {buildNightVelocity} from './velocity.js';
import {buildMarket} from './market.js';
import {avenueParcel} from './city-facades.js';
import {buildCrestGardens} from './crest-gardens.js';
import {buildLanternMarina,marinaBathymetry} from './lantern-marina.js';
import {buildParallaxCourt,meridianRain} from './parallax-court.js';
import {buildInstrumentRoom} from './instrument-room.js';
import {buildCathedral} from './cathedral.js';
import {buildMeridianYard} from './meridian-yard.js';
import {buildVerticalLoops} from './vertical-loops.js';
import {buildCathedralEast} from './cathedral-east.js';
import {buildAirTrialMarkers} from './air-trials.js';
import {buildCityLife} from './city-life.js';
import {buildNeighbourhoods,neighbourhoodSolid} from './neighbourhood.js';
import {buildLanternRace,lanternRaceSolid} from './lantern-race.js';
import {buildAtmosphere} from './atmosphere.js';
import {cityDensity,DENSITY_BOUNDS} from './city-density.js';

const vertex = `
varying vec3 p;
varying vec3 n;
void main(){
  vec4 positionWorld = modelMatrix * vec4(position,1.);
  p = positionWorld.xyz;
  n = normal;
  gl_Position = projectionMatrix * viewMatrix * positionWorld;
}`;

const common = `
uniform float night;
uniform float meridian;
uniform float airfieldSurvey;
uniform float arrivalsSurvey;
uniform float photographic;
uniform float marketPass;
uniform float blueHour;
uniform sampler2D daySky;
uniform sampler2D nightSky;
uniform sampler2D forecourtLight;
uniform float rooftopPass;
uniform sampler2D cityDensity;
uniform vec4 cityDensityBounds;
varying vec3 p;
varying vec3 n;
// Share of rooms occupied at night, from the surveyed floor-area density (1 = unchanged look).
float occupancyAt(vec2 xy){
  vec2 uv=(xy-cityDensityBounds.xy)/cityDensityBounds.zw;
  if(rooftopPass<.5||any(lessThan(uv,vec2(0.)))||any(greaterThan(uv,vec2(1.))))return rooftopPass<.5?1.:0.;
  return texture2D(cityDensity,uv).r;
}
float hash(vec2 a){
  vec3 p3 = fract(vec3(a.xyx)*.1031);
  p3 += dot(p3,p3.yzx+33.33);
  return fract((p3.x+p3.y)*p3.z);
}
float noise2(vec2 a){
  vec2 i=floor(a), f=fract(a);
  f=f*f*(3.-2.*f);
  return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);
}
float fbm(vec2 a){
  return .52*noise2(a)+.27*noise2(a*2.07+23.)+.14*noise2(a*4.1+91.)+.07*noise2(a*8.3);
}
#define sun (photographic>.5?normalize(vec3(-.89,.46,.19)):normalize(vec3(.89,-.45,.26)))
vec2 forecourtShadow(vec2 xy){
  if(arrivalsSurvey<.5)return vec2(1.);
  vec2 uv=(xy+vec2(480.,660.))/vec2(960.,800.);
  float boundary=min(min(uv.x,uv.y),min(1.-uv.x,1.-uv.y));
  return mix(vec2(1.),texture2D(forecourtLight,uv).rg,smoothstep(0.,.025,boundary));
}
vec3 haze(vec3 color){
  float d=length(cameraPosition-p);
  float amount=(1.-exp(-d*.000026))*exp(-max(0.,p.z)*.00020);
  vec3 air=mix(mix(vec3(.18,.20,.28),vec3(.075,.11,.20),meridian),vec3(.043,.055,.10),night);
  if(arrivalsSurvey>.5){
    vec3 ray=normalize(p-cameraPosition);
    float warm=pow(max(0.,dot(ray,normalize(vec3(.92,.36,.09)))),3.);
    vec3 atmosphere=mix(vec3(.112,.153,.226),vec3(.37,.204,.178),warm);
    float extinction=(1.-exp(-d*.000096))*exp(-max(0.,p.z)*.00017);
    return mix(color,atmosphere*mix(1.,.38,night),extinction);
  }
  return mix(color,air,amount*mix(1.,.69,meridian));
}
const float tau=6.2831853;
vec2 skyUv(vec3 d){
  float az=atan(d.x,d.y);
  return vec2(fract(.595+az/tau),clamp(atan(d.z,length(d.xy))/.96+.035,0.,1.));
}
vec3 skySample(sampler2D sky,vec3 direction){
  if(photographic>.5){
    vec3 d=normalize(direction);
    vec2 skyuv=vec2(fract(atan(d.y,d.x)/tau),clamp(asin(max(d.z,0.))*0.63662,.001,.999));
    vec2 dx=dFdx(skyuv),dy=dFdy(skyuv);dx.x-=floor(dx.x+.5);dy.x-=floor(dy.x+.5);
    vec3 daylight=textureGrad(daySky,skyuv,dx,dy).rgb, moon=textureGrad(nightSky,skyuv,dx,dy).rgb;
    vec3 sky=mix(daylight,moon,night);
    if(blueHour>.0){
      float west=pow(max(dot(d,normalize(vec3(-.89,.46,.16))),0.),4.);
      float horizon=exp(-max(0.,d.z)*3.75);
      vec3 twilight=daylight*mix(vec3(.27,.36,.64),vec3(1.42,.64,.32),west*horizon);
      twilight+=vec3(.17,.051,.016)*west*horizon*smoothstep(.12,.65,dot(daylight,vec3(.31,.51,.18)));
      sky=mix(sky,twilight,blueHour);
    }
    return sky;
  }
  vec2 uv=skyUv(direction);
  if(airfieldSurvey<.5)return texture2D(sky,uv).rgb;
  vec2 dx=dFdx(uv),dy=dFdy(uv);
  dx.x-=floor(dx.x+.5);dy.x-=floor(dy.x+.5);
  vec3 paint=textureGrad(sky,uv,dx,dy).rgb;
  float edge=min(uv.x,1.-uv.x);
  if(edge<.095){
    vec3 opposite=textureGrad(sky,vec2(1.-uv.x,uv.y),vec2(-dx.x,dx.y),vec2(-dy.x,dy.y)).rgb;
    paint=mix(paint,opposite,.5*(1.-smoothstep(0.,.095,edge)));
  }
  return paint;
}`;

const terrainFragment = common + `
uniform sampler2D reliefLight;
uniform sampler2D upland;
uniform sampler2D civic;
uniform sampler2D granite;
uniform float hasCivic;
uniform float fallsSurvey;
uniform float marinaSurvey;
uniform float raceOn;
uniform sampler2D raceLight;
uniform vec4 raceArea;
uniform float raceLevel;
void main(){
  vec3 normal=normalize(n);
  float slope=1.-normal.z;
  float macro=fbm(p.xy*.0016);
  float grain=fbm(p.xy*.095+17.);
  float variation=fbm(p.xy*.009+macro*4.);
  float stratum=fbm(vec2((p.x*.6+p.y*.4)*.012,p.z*.056+macro*7.));
  vec3 grass=mix(vec3(.055,.093,.032),vec3(.25,.235,.096),variation);
  vec3 forest=mix(vec3(.014,.042,.033),vec3(.075,.12,.048),grain);
  vec3 low=mix(grass,forest,smoothstep(.27,.60,macro+.11*variation)*smoothstep(14.,94.,p.z));
  vec3 substrate=texture2D(upland,p.xy*.088).rgb;
  low*=mix(vec3(1.),clamp(substrate*4.1,vec3(.34),vec3(1.9)),.75);
  vec2 urban=texture2D(civic,p.xy/16000.+.5).rg*hasCivic;
  low=mix(low,vec3(.085,.088,.091)*(.78+.37*grain),urban.g*.58);
  low=mix(low,vec3(.155,.148,.13)*(.79+.33*grain),urban.r*.87);
  float stone=smoothstep(.11,.43,slope+.08*variation)+.36*smoothstep(780.,1490.,p.z);
  vec3 rock=mix(vec3(.087,.069,.077),vec3(.41,.31,.255),variation*.44+.54*stratum);
  vec3 albedo=mix(low,rock,clamp(stone,0.,1.));
  float snow=smoothstep(960.,1310.,p.z+360.*(variation-.5)-slope*1250.-normal.x*210.);
  albedo=mix(albedo,vec3(.84,.87,.95),snow);
  float lambert=max(dot(normal,sun),0.);
  vec2 occ=texture2D(reliefLight,p.xy/16000.+.5).rg;
  vec3 light=vec3(.28,.34,.53)*occ.y + vec3(2.43,1.62,.92)*lambert*occ.x;
  vec3 lit=albedo*light*(.79+.36*grain);
  if(meridian>.5){
    vec3 weights=pow(abs(normal),vec3(4.)); weights/=max(dot(weights,vec3(1.)),.001);
    vec3 detail=texture2D(granite,p.zy*.014).rgb*weights.x+texture2D(granite,p.xz*.014).rgb*weights.y
               +texture2D(granite,p.xy*.014).rgb*weights.z;
    float seam=fbm(vec2(p.x*.012+p.y*.004+p.z*.024,p.z*.013-p.y*.007));
    float outcrop=smoothstep(.035,.22,slope+variation*.075)*smoothstep(85.,305.,p.z)+.48*smoothstep(520.,920.,p.z);
    float snowLine=smoothstep(690.,1070.,p.z+(seam-.42)*440.+normal.y*118.-slope*350.);
    snowLine*=1.-smoothstep(.44,.96,slope+(seam-.50)*.38);
    vec3 slate=mix(vec3(.045,.061,.095),vec3(.26,.20,.166),smoothstep(.28,.72,seam+normal.x*.12));
    slate*=clamp(detail*4.5,vec3(.33),vec3(2.05));
    vec3 uplandColor=mix(vec3(.018,.055,.032),vec3(.212,.215,.062),smoothstep(.27,.69,variation+macro*.13));
    uplandColor*=mix(vec3(1.),clamp(substrate*4.5,vec3(.42),vec3(1.6)),.68);
    uplandColor=mix(uplandColor,vec3(.085,.094,.105)*(.74+.4*grain),urban.g*.80);
    if(rooftopPass>.5){
      // Ward paving in soft, low-contrast patches rather than one pale slab or a lot grid.
      float wardPatch=fbm(p.xy*.006+11.),wardGreen=fbm(p.xy*.013+5.);
      vec3 wardPave=mix(vec3(.060,.064,.070),vec3(.115,.100,.084),smoothstep(.40,.64,wardPatch))*(.85+.25*grain);
      wardPave=mix(wardPave,vec3(.035,.060,.034)*(.8+.4*grain),smoothstep(.58,.74,wardGreen)*.7);
      uplandColor=mix(uplandColor,wardPave,urban.r*.91);
    }else{
      uplandColor=mix(uplandColor,vec3(.21,.192,.165)*(.81+.29*grain),urban.r*.91);
    }
    if(arrivalsSurvey>.5){
      float lawn=(1.-smoothstep(.73,1.,length((p.xy-vec2(0.,-397.))/vec2(390.,162.))));
      float mow=.5+.5*cos((p.x*.68+p.y*.43)*.72);
      vec3 planted=mix(vec3(.030,.071,.038),vec3(.093,.147,.061),variation)*(.85+.18*mow+.13*grain);
      planted*=mix(vec3(1.),clamp(substrate*4.8,vec3(.49),vec3(1.7)),.65);
      uplandColor=mix(uplandColor,planted,lawn*.94);
    }
    vec3 mat=mix(uplandColor,slate,clamp(outcrop,0.,1.));
    float relief=0.;
    if(rooftopPass>.5){
      // v33 rock: strata that dip and wander rather than level contour bands, dark fall-line
      // gullies and pale ribs on cliffs, vegetation on ledges and scree fans at the slope foot.
      float warp=fbm(p.xy*.0021+7.)*52.;
      float layer=p.z+dot(p.xy,vec2(.10,-.064))+warp;
      float strata=fbm(vec2(layer*.042,(p.x+p.y)*.0017));
      float bed=noise2(vec2(layer*.36,(p.x-p.y)*.009));
      vec2 down=normalize(normal.xy+vec2(1e-4));
      float across=dot(p.xy,vec2(-down.y,down.x));
      float gully=fbm(vec2(across*.052,p.z*.0055+across*.0009));
      float steep=smoothstep(.22,.72,slope);
      vec3 rock=mix(vec3(.078,.076,.084),vec3(.285,.245,.208),smoothstep(.30,.76,strata));
      rock=mix(rock,vec3(.155,.152,.160),.30*bed);
      rock*=mix(1.,.58+.62*gully,steep);
      rock*=clamp(detail*4.1,vec3(.40),vec3(1.75));
      float ledge=smoothstep(.60,.80,normal.z)*(1.-smoothstep(.88,.96,normal.z))*smoothstep(.42,.62,fbm(p.xy*.031+2.));
      vec3 moss=mix(vec3(.028,.050,.027),vec3(.098,.106,.048),fbm(p.xy*.07));
      rock=mix(rock,moss,ledge*.78);
      float scree=smoothstep(.16,.30,slope)*(1.-smoothstep(.44,.58,slope))*smoothstep(.52,.68,fbm(p.xy*.018+3.));
      rock=mix(rock,vec3(.235,.225,.215)*(.68+.62*hash(floor(p.xy*1.4))),scree*.55);
      mat=mix(uplandColor,rock,clamp(outcrop,0.,1.));
      relief=(gully-.5)*steep;
      // snow scoured from ridges and gathered in hollows and on lee faces, not a level line
      float scour=smoothstep(.55,.85,fbm(p.xy*.006+11.)+normal.x*.25);
      snowLine*=mix(1.,.45,scour)*(1.-.5*steep*gully);
    }
    if(fallsSurvey>.5){
      float gorge=1.-smoothstep(.64,1.,length((p.xy-vec2(-4950.,3580.))/vec2(820.,1130.)));
      float exposure=smoothstep(.065,.31,slope)*gorge;
      float bedding=fbm(vec2(p.x*.023+p.y*.007,p.z*.15+p.x*.017));
      vec3 bedrock=mix(vec3(.043,.073,.083),vec3(.32,.28,.22),smoothstep(.23,.78,bedding+.16*normal.x));
      bedrock*=clamp(detail*4.,vec3(.42),vec3(1.65));
      mat=mix(mat,bedrock,exposure);
    }
    mat=mix(mat,vec3(.65,.80,.99)*(.77+.23*grain),snowLine);
    float shade=rooftopPass>.5?clamp(lambert+relief*.55,0.,1.2):lambert;   // gullies catch and lose the light
    vec3 rim=vec3(1.93,.99,.49)*shade*occ.x;
    lit=mat*(vec3(.21,.31,.56)*occ.y+rim)*(.88+.19*grain);
    if(arrivalsSurvey>.5){
      vec2 shade=forecourtShadow(p.xy);
      lit*=mix(vec3(.52,.66,.88),vec3(1.),shade.x)*mix(.69,1.,shade.y);
    }
  }
  vec3 floorLight=lit*mix(1.,photographic>.5?.074:.36,night);
  if(marinaSurvey>.5 && p.x>840. && p.x<1210. && p.y>-1380. && p.y<-960.){
    float parcel=1.-smoothstep(.64,1.,length((p.xy-vec2(1023.,-1170.))/vec2(185.,205.)));
    float green=fbm(p.xy*.034+vec2(4.3,59.7));
    float speckle=fbm(p.xy*.46);
    vec3 grass=mix(vec3(.032,.071,.049),vec3(.129,.174,.097),green)*(.68+.61*speckle);
    float exposed=smoothstep(.046,.29,slope+.075*green);
    float sediment=fbm(vec2(p.x*.028+p.y*.014,p.z*.156+speckle*.12));
    vec3 grit=mix(vec3(.040,.064,.076),vec3(.191,.169,.130),sediment);
    float strand=1.-smoothstep(6.,11.5,p.z);
    vec3 bank=mix(grass,grit,max(exposed,.86*strand));
    bank*=mix(vec3(.36,.40,.50),vec3(.66,.69,.62),1.-night)*(.66+.74*lambert);
    floorLight=mix(floorLight,bank,parcel*.96);
  }
  if(raceOn>.5){
    // v33 Lantern Race banks: wet shingle and weed at the waterline instead of grass to the edge,
    // with the bank lanterns' light on it at night.
    vec2 ruv=(p.xy-raceArea.xy)/raceArea.zw;
    if(all(greaterThan(ruv,vec2(0.)))&&all(lessThan(ruv,vec2(1.)))){
      float fade=smoothstep(0.,.06,min(min(ruv.x,1.-ruv.x),min(ruv.y,1.-ruv.y)));
      float above=p.z-raceLevel;
      float shore=(1.-smoothstep(.45,2.4,above+.9*(fbm(p.xy*.23)-.5)))*fade;
      float wetBand=(1.-smoothstep(0.,.65,above))*fade;
      float stones=fbm(p.xy*2.6),pebble=noise2(p.xy*7.3);
      vec3 shingle=mix(vec3(.058,.056,.054),vec3(.205,.192,.172),smoothstep(.30,.72,stones))*(.72+.56*pebble);
      shingle=mix(shingle,vec3(.036,.064,.044),smoothstep(.60,.78,fbm(p.xy*.47+4.))*.55);
      shingle*=1.-.5*wetBand;
      vec3 rl=texture2D(raceLight,ruv).rgb;rl/=max(vec3(1e-3),1.-rl);
      vec3 shoreLit=shingle*(vec3(.30,.34,.44)+vec3(.95,.80,.62)*max(dot(normal,sun),0.)*1.15)*mix(1.,.32,night)
                   +shingle*rl*night*1.4;
      floorLight=mix(floorLight,shoreLit,shore*.92);
    }
  }
  if(marketPass>.5){
    vec2 q=abs((p.xy-vec2(0.,2480.))/vec2(1050.,1050.));float district=1.-smoothstep(.93,1.05,max(q.x,q.y));
    float stone=texture2D(granite,p.xy/4.5).r;
    if(rooftopPass>.5){
      // Urban ground in soft irregular patches (courts, worn paving, a little green), low contrast
      // and darker than the lit facades above it; no lot grid.
      float patchA=fbm(p.xy*.0045+3.1),patchB=fbm(p.xy*.011+17.);
      vec3 court=mix(vec3(.052,.055,.062),vec3(.088,.086,.084),stone);
      vec3 paving=mix(vec3(.095,.085,.074),vec3(.150,.132,.110),stone);
      vec3 green=mix(vec3(.030,.048,.030),vec3(.060,.082,.045),patchB);
      vec3 blocks=mix(court,paving,smoothstep(.42,.62,patchA));
      blocks=mix(blocks,green,smoothstep(.60,.74,patchB)*.8);
      vec3 nightLift=vec3(.36,.40,.47);
      floorLight=mix(floorLight,blocks*mix(vec3(1.),nightLift,night),district*.94);
    }else{
      float garden=fbm(p.xy*.012);
      vec3 blocks=mix(vec3(.135,.151,.123),vec3(.286,.260,.224),smoothstep(.30,.59,garden))*(.72+.64*stone);
      floorLight=mix(floorLight,blocks*mix(vec3(1.),vec3(.36,.40,.47),night),district*.94);
    }
  }
  gl_FragColor=vec4(haze(floorLight),1.);
  #include <colorspace_fragment>
}`;

function terrainTiles(group,w,uniforms) {
  const h=w.heights_m, n=h.length, step=2*w.half_m/(n-1), tile=80;
  const material=new THREE.ShaderMaterial({uniforms,vertexShader:vertex,fragmentShader:terrainFragment});
  for(let j0=0;j0<n-1;j0+=tile) for(let i0=0;i0<n-1;i0+=tile){
    const nx=Math.min(tile,n-1-i0)+1, ny=Math.min(tile,n-1-j0)+1;
    const pos=new Float32Array(nx*ny*3), normals=new Float32Array(pos.length);
    const indices=new Uint16Array((nx-1)*(ny-1)*6);
    let face=0;
    for(let v=0;v<ny;v++) for(let u=0;u<nx;u++){
      const i=i0+u,j=j0+v,k=v*nx+u;
      pos.set([i*step-w.half_m,j*step-w.half_m,h[j][i]],k*3);
      const x0=Math.max(0,i-1),x1=Math.min(n-1,i+1),y0=Math.max(0,j-1),y1=Math.min(n-1,j+1);
      const dx=(h[j][x1]-h[j][x0])/((x1-x0)*step),dy=(h[y1][i]-h[y0][i])/((y1-y0)*step);
      const length=Math.hypot(dx,dy,1);
      normals.set([-dx/length,-dy/length,1/length],k*3);
      if(u<nx-1 && v<ny-1){indices.set([k,k+1,k+nx+1,k,k+nx+1,k+nx],face);face+=6;}
    }
    const g=new THREE.BufferGeometry();
    g.setAttribute('position',new THREE.BufferAttribute(pos,3));
    g.setAttribute('normal',new THREE.BufferAttribute(normals,3));
    g.setIndex(new THREE.BufferAttribute(indices,1));g.computeBoundingSphere();
    const mesh=new THREE.Mesh(g,material);mesh.name='Vaderland terrain';group.add(mesh);
  }
}

function instanced(group,geometry,material,items){
  if(!items.length){geometry.dispose();material.dispose();return;}
  const mesh=new THREE.InstancedMesh(geometry,material,items.length);
  const dummy=new THREE.Object3D();
  for(let i=0;i<items.length;i++){
    const [x,y,z,sx,sy,sz,color,angle=0]=items[i];
    dummy.position.set(x,y,z);dummy.scale.set(sx,sy,sz);dummy.rotation.z=angle;dummy.updateMatrix();
    mesh.setMatrixAt(i,dummy.matrix);
    if(color)mesh.setColorAt(i,new THREE.Color(color));
  }
  mesh.computeBoundingSphere();group.add(mesh);return mesh;
}

function apron(group,w){
  const {runway,edgeLights,thresholdLights}=primaryRunwayCues(w);
  const pavement=[],paint=[],lamps=[];
  const rect=(list,x,y,z,length,width,color)=>list.push([x,y,z,length,width,1,color]);
  rect(pavement,0,0,.025,runway.length,38,'#5a5a56');
  rect(pavement,0,0,.04,runway.length,30,'#313544');
  rect(pavement,7,-72,.032,480,86,'#4d5055');
  rect(pavement,0,-45,.035,runway.length-100,12,'#424650');
  for(let x=runway.x0+80;x<runway.x1;x+=390)rect(pavement,x,-22,.038,12,45,'#434651');
  for(let x=runway.x0+50;x<runway.x1-35;x+=58)rect(paint,x,0,.065,26,.70,'#d9d6cc');
  for(const side of [-1,1]){
    rect(paint,0,side*14.3,.067,runway.length,.30,'#d9d6cc');
    const end=side*3880;
    for(let j=-5;j<=5;j++) if(j!==0)rect(paint,end,2.35*j,.069,24,1.0,'#e0dbca');
  }
  for(const [x,y,color] of [...edgeLights,...thresholdLights]){
    lamps.push([x,y,.24,1.1,1.1,1,color]);
  }
  instanced(group,new THREE.PlaneGeometry(),new THREE.MeshStandardMaterial({roughness:.88,polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-3}),pavement);
  instanced(group,new THREE.PlaneGeometry(),new THREE.MeshBasicMaterial({polygonOffset:true,polygonOffsetFactor:-4,polygonOffsetUnits:-5}),paint);
  instanced(group,new THREE.SphereGeometry(.5,5,3),new THREE.MeshBasicMaterial({toneMapped:false}),lamps);
}

function facadeMaterial(uniforms){
  const material=new THREE.ShaderMaterial({
    uniforms,
    vertexShader:`
      varying vec3 p; varying vec3 n; varying vec3 local; varying vec3 dim; varying vec3 tint;
      void main(){
        mat4 shape=instanceMatrix;
        vec4 wp=shape*vec4(position,1.);
        p=wp.xyz;local=position;n=normalize(mat3(shape)*normal);
        dim=vec3(length(shape[0].xyz),length(shape[1].xyz),length(shape[2].xyz));
        tint=instanceColor;
        gl_Position=projectionMatrix*viewMatrix*wp;
      }`,
    fragmentShader:common+`
      uniform sampler2D offices;uniform sampler2D clouds;uniform float civicPass;
      varying vec3 local; varying vec3 dim; varying vec3 tint;
      void main(){
        vec3 normal=normalize(n);
        bool roof=abs(normal.z)>.75;
        float side=abs(normal.x)>.5?p.y:p.x;
        vec2 modXY=vec2(side/3.3,p.z/4.2);
        vec2 cell=fract(modXY),pixel=max(fwidth(modXY),vec2(.001));
        float reveal=smoothstep(.12,.15+min(pixel.x,.12),cell.x)*(1.-smoothstep(.86,.90,cell.x))
                    *smoothstep(.22,.28+min(pixel.y,.12),cell.y)*(1.-smoothstep(.83,.92,cell.y));
        float seed=hash(floor(modXY)+floor(dim.xy));
        float lit=step(.72,seed)*(.35+.67*seed);
        vec3 glass=mix(vec3(.012,.025,.045),vec3(.09,.14,.18),clamp(.32+.53*normal.x+.23*local.z,0.,1.));
        vec3 glow=mix(vec3(1.08,.43,.065),vec3(.29,.58,.73),step(.964,seed));
        vec3 wall=mix(tint*.64+vec3(.028),glass,reveal);
        wall+=glow*lit*reveal*.94;
        float distant=smoothstep(.4,1.6,max(pixel.x,pixel.y));
        wall=mix(wall,(tint*.25+glass*.60+vec3(.084,.037,.010))*(.68+.32*noise2(floor(p.xy/15.)+floor(p.z/20.))),distant*.93);
        float top=(.5-local.z)*dim.z;
        float edge=1.-smoothstep(.20,.65,abs(top-1.4));
        wall+=vec3(1.8,.81,.15)*edge;
        wall*=.78+.35*max(dot(normal,sun),0.);
        if(roof){
          float metal=.8+.2*fbm(p.xy*.16);
          wall=(tint*vec3(.66,.83,.95)+vec3(.023))*metal;
        }
        if(meridian>.5){
          float floors=(p.z+.31)/4.2;
          float mullion=abs(fract(side/4.65)-.5);
          float gird=abs(fract(floors)-.5);
          float shell=smoothstep(.06,.14,mullion)*(1.-smoothstep(.29,.41,gird));
          float office=noise2(vec2(floor(side/17.),floor(floors*.5))+.07*floor(dim.xy));
          float district=hash(floor(dim.xy*3.));
          float groupLight=smoothstep(.40,.65,office+.09*district);
          float close=1.-smoothstep(.18,1.3,max(fwidth(floors),fwidth(side/4.65)));
          vec3 metal=mix(vec3(.027,.051,.083),vec3(.07,.09,.104),.5+.5*normal.x);
          vec3 reflection=mix(vec3(.02,.048,.086),vec3(.187,.15,.145),pow(abs(normal.x),2.));
          vec3 glazing=mix(reflection,vec3(.85,.39,.108)*(.70+.36*office),groupLight*.77);
          wall=mix(metal,mix(metal,glazing,shell),close);
          wall+=vec3(.31,.113,.032)*groupLight*(1.-close)*(.35+.65*step(.6,office));
          float sill=1.-smoothstep(.1,.42,abs(top-1.2));
          float averageSill=1.-smoothstep(.3,max(.55,fwidth(top)*1.1),abs(top-1.2));
          wall+=vec3(1.25,.47,.083)*mix(sill,averageSill*.83,1.-close);
          if(dim.z>55.){
            float edgeX=abs(abs(local.x)-.5)*dim.x,edgeY=abs(abs(local.y)-.5)*dim.y;
            float corner=1.-smoothstep(.35,1.1,max(edgeX,edgeY));
            wall+=vec3(.56,.26,.08)*corner;
          }
          if(roof){
            float joint=step(.98,fract(p.x/8.))+step(.98,fract(p.y/8.));
            wall=(vec3(.04,.062,.093)+tint*.22)*(.80+.24*noise2(p.xy*.14)-.17*joint);
          }
        }
        if(civicPass>.5&&!roof){
          float block=hash(floor(dim.xy*.47));vec3 R=reflect(normalize(p-cameraPosition),normal);
          vec3 glass=texture2D(offices,vec2(side/(22.+6.*block)+block,p.z/(30.+4.*block))).rgb;
          float floorGroup=noise2(vec2(floor(side/13.),floor(p.z/8.))+dim.xy);
          vec3 glaze=mix(vec3(.52,.68,.83),vec3(.94,.77,.55),smoothstep(.30,.67,floorGroup+block*.22));
          glass*=glaze*(.60+.52*floorGroup);glass+=skySample(clouds,R)*(.13+.17*block);
          wall=mix(glass,wall,.12)+vec3(.24,.119,.032)*edge;
          if(photographic>.5){
            vec2 bank=vec2(floor(side/7.1),floor(p.z/3.72));float occupied=hash(bank+floor(dim.xy));
            float face=hash(floor(dim.xy)+vec2(37.9,11.4));
            vec3 lamp=mix(vec3(.75,.87,1.),vec3(1.,.76,.47),smoothstep(.35,.74,occupied+.22*face));
            float band=1.-smoothstep(.30,.50,abs(fract(p.z/3.72)-.5));
            float window=band*smoothstep(.09,.14,fract(side/3.55))*(1.-smoothstep(.86,.96,fract(side/3.55)));
            float tenant=smoothstep(.28,.78,hash(vec2(floor(side/14.2),floor(p.z/3.72))+dim.xy));
            vec3 room=(glass*.45+vec3(.11,.13,.16))*lamp;
            vec3 windows=glass*.16+window*room*(.20+tenant*1.98)*(.70+.48*occupied);
            windows+=lamp*.07*window*smoothstep(.65,.91,occupied);
            wall=mix(wall,windows+vec3(.24,.34,.52)*edge*(.30+.60*face),night);
          }
        }
        gl_FragColor=vec4(haze(wall*mix(1.,.77,night)),1.);
        #include <colorspace_fragment>
      }`,
  });
  return material;
}

function roadPaint(group,w,ground,uniforms){
  const positions=[],colors=[],indices=[];
  const yard=w.vaderland.meridian_yard;
  const yardRoads=yard?w.vaderland.routes.filter(r=>r.kind==='experimental'):[];
  const junctions=yard?[w.vaderland.routes.find(r=>r.name==='Exchange Boulevard'),...yardRoads]:[];
  const shore=w.vaderland.lantern_marina;
  if(shore)junctions.push(...w.vaderland.routes.filter(r=>shore.junction_roads.includes(r.name)));
  const junctionBounds=junctions.map(r=>{
    const x=r.points.map(p=>p[0]),y=r.points.map(p=>p[1]),width=r.width_m/2;
    return [Math.min(...x)-width,Math.max(...x)+width,Math.min(...y)-width,Math.max(...y)+width];
  });
  const routeSegments=junctions.map(r=>r.points.slice(1).map(([x,y],i)=>{
    const [ax,ay]=r.points[i],dx=x-ax,dy=y-ay;
    return {ax,ay,dx,dy,squared:dx*dx+dy*dy,reach:r.width_m/2-.24};
  }));
  function underOtherRoad(x,y,road){
    return junctions.some((route,i)=>{
      if(route===road)return false;
      const [x0,x1,y0,y1]=junctionBounds[i];
      if(x<x0||x>x1||y<y0||y>y1)return false;
      return routeSegments[i].some(segment=>{
      const {ax,ay,dx,dy,squared,reach}=segment;
      if(!squared || Math.abs(x-ax)>Math.abs(dx)+reach || Math.abs(y-ay)>Math.abs(dy)+reach)return false;
      const along=Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/squared));
      return Math.hypot(x-ax-along*dx,y-ay-along*dy)<reach;
      });
    });
  }
  function strip(points,width,offset,color,deck,road){
    const shade=new THREE.Color(color);
    const emit=(last,pair)=>{
      const x=(last[0].x+last[1].x+pair[0].x+pair[1].x)*.25;
      const y=(last[0].y+last[1].y+pair[0].y+pair[1].y)*.25;
      if(road&&offset!==0&&underOtherRoad(x,y,road))return;
      const triangles=[[last[0],pair[0],last[1]],[pair[0],pair[1],last[1]]];
      const coords=deck===undefined ? ground.drapeTriangles(triangles,{offset:offset===0?.012:.024}).pos
        :triangles.flat().flatMap(p=>[p.x,p.y,deck+.025]);
      for(let j=0;j<coords.length;j+=3){
        indices.push(positions.length/3);positions.push(coords[j],coords[j+1],coords[j+2]);colors.push(shade.r,shade.g,shade.b);
      }
    };
    if(road?.kind==='experimental'||road?.kind==='marina-link'||road?.mitre){
      const normals=points.slice(1).map(([x,y],i)=>{
        const dx=x-points[i][0],dy=y-points[i][1],length=Math.hypot(dx,dy);
        return [-dy/length,dx/length];
      });
      const last=normals.length-1;
      const closed=road.kind!=='marina-link'&&points[0][0]===points.at(-1)[0]&&points[0][1]===points.at(-1)[1];
      const edges=points.map(([x,y],i)=>{
        const a=normals[i>0?i-1:closed?last:0],b=normals[i<=last?i:closed?0:last];
        const denominator=1+a[0]*b[0]+a[1]*b[1];
        return [-1,1].map(side=>{
          const turn=(offset+side*width*.5)/denominator;
          return {x:x+(a[0]+b[0])*turn,y:y+(a[1]+b[1])*turn,a:[]};
        });
      });
      for(let i=1;i<edges.length;i++)emit(edges[i-1],edges[i]);
      return;
    }
    for(let i=1;i<points.length;i++){
      const [x0,y0]=points[i-1],[x1,y1]=points[i],len=Math.hypot(x1-x0,y1-y0);
      const nx=-(y1-y0)/len,ny=(x1-x0)/len;
      const nearYard=road&&offset!==0&&Math.min(x0,x1)<1165&&Math.max(x0,x1)>910;
      const steps=Math.ceil(len/(nearYard?1.4:12));
      let last;
      for(let k=0;k<=steps;k++){
        const pair=[];
        for(const side of [-1,1]){
          const x=x0+(x1-x0)*k/steps+nx*(offset+side*width/2);
          const y=y0+(y1-y0)*k/steps+ny*(offset+side*width/2);
          pair.push({x,y,a:[]});
        }
        if(last)emit(last,pair);
        last=pair;
      }
    }
  }
  for(const r of w.vaderland.routes){
    if(r.kind==='taxi' || r.kind==='boardwalk' || r.kind==='arrivals' || r.kind==='speedway' || r.kind==='vertical-loop' || r.kind==='quarry')continue;
    const junction=junctions.includes(r)?r:undefined;
    const mitred=junction??(r.mitre?r:undefined);
    strip(r.points,r.width_m,0,r.surface_color??(r.kind==='track'?'#796957':'#323942'),r.deck_z_m,mitred);
    const edge=r.edge_color??(r.kind==='viaduct'?'#ffad55':r.kind==='express'?'#e6c58d':'#9da29d');
    for(const side of [-1,1])strip(r.points,r.kind==='viaduct'?1.05:.48,(r.width_m/2-.65)*side,edge,r.deck_z_m,mitred);
    if(r.width_m>40&&r.kind!=='apron')strip(r.points,.55,0,'#dfc887',r.deck_z_m);
    if(r.kind==='marina-link'&&r.width_m>10){
      let station=0;
      for(let i=1;i<r.points.length;i++){
        const [ax,ay]=r.points[i-1],[bx,by]=r.points[i];
        const dx=bx-ax,dy=by-ay,d=Math.hypot(dx,dy);
        for(let start=Math.floor(station/14)*14;start<station+d;start+=14){
          const from=Math.max(0,(start-station)/d),to=Math.min(1,(start+4.7-station)/d);
          if(to<=from)continue;
          const middle=(from+to)/2;
          if(underOtherRoad(ax+middle*dx,ay+middle*dy,r))continue;
          strip([[ax+from*dx,ay+from*dy],[ax+to*dx,ay+to*dy]],.19,0,'#edcd8d');
        }
        station+=d;
      }
    }
    if(r.lanes_each_way===2){
      const medianEdge=r.median_m/2, divider=medianEdge+r.lane_width_m;
      for(const sign of [-1,1])strip(r.points,.17,sign*medianEdge,'#e0ae58');
      let station=0;
      for(let i=1;i<r.points.length;i++){
        const a=r.points[i-1],b=r.points[i],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
        for(let mark=Math.floor(station/12)*12;mark<station+length;mark+=12){
          const u=Math.max(0,(mark-station)/length),v=Math.min(1,(mark+4-station)/length);
          if(v<=u)continue;
          const dash=[[a[0]+dx*u,a[1]+dy*u],[a[0]+dx*v,a[1]+dy*v]];
          for(const sign of [-1,1])strip(dash,.19,sign*divider,'#e5dfcb');
        }
        station+=length;
      }
    }
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.setIndex(indices);
  const paint=new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,
    polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-4});
  if(w.vaderland.gallery){
    paint.onBeforeCompile=shader=>{
      const district=w.vaderland.operations,court=w.vaderland.parallax_court;
      if(court)shader.uniforms.avenueStorefronts={value:court.storefronts.map(p=>new THREE.Vector3(...p))};
      if(district)Object.assign(shader.uniforms,{roadSky:uniforms.clouds,roadStone:uniforms.paving});
      const surveyed=w.vaderland.frontage,fixtures=surveyed?.lights.filter(l=>l.site==='frontage')??[];
      if(surveyed)Object.assign(shader.uniforms,{asphaltMap:uniforms.asphaltColor,normalRoad:uniforms.asphaltNormal,roughRoad:uniforms.asphaltRough,
        skyDay:uniforms.daySky,skyNight:uniforms.nightSky,afterdark:uniforms.night,bollards:{value:fixtures.map(l=>new THREE.Vector3(...l.xyz))}});
      shader.vertexShader='varying vec3 roadPoint;\n'+shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nroadPoint=position;');
      shader.fragmentShader=(surveyed?'uniform sampler2D asphaltMap,normalRoad,roughRoad,skyDay,skyNight;uniform float afterdark;uniform vec3 bollards['+fixtures.length+'];':'')+
        (court?meridianRain(court.storefronts.length):'')+
        (district?'uniform sampler2D roadSky;uniform sampler2D roadStone;':'')+'varying vec3 roadPoint;\n'+shader.fragmentShader.replace('#include <color_fragment>',`
        #include <color_fragment>
        float bore=smoothstep(2898.,2915.,roadPoint.x)*(1.-smoothstep(3485.,3502.,roadPoint.x))*(1.-smoothstep(10.75,13.,abs(roadPoint.y+4350.)));
        float bay=.5+.5*cos((roadPoint.x-2900.)*.392699);
        float verge=abs(roadPoint.y+4350.)/11.;
        vec3 bounce=vec3(.46,.52,.63)+pow(bay,4.)*verge*verge*vec3(.60,.32,.10);
        diffuseColor.rgb*=mix(vec3(1.),bounce,bore);
        ${district?`
        vec3 V=normalize(cameraPosition-roadPoint);
        vec3 R=reflect(-V,vec3(0.,0.,1.));
        vec2 uv=vec2(fract(.595+atan(R.x,R.y)/6.283185),clamp(R.z+.035,.01,.98));
        float grain=texture2D(roadStone,roadPoint.xy/2.82).r;
        float frost=texture2D(roadStone,roadPoint.xy/23.).g;
        float asphalt=1.-smoothstep(.085,.16,dot(diffuseColor.rgb,vec3(.25,.62,.13)));
        vec3 grit=diffuseColor.rgb*(.56+clamp(grain*2.,0.,.85));
        vec3 sheen=texture2D(roadSky,uv).rgb*pow(1.-abs(V.z),3.5)*(.11+.20*frost);
        diffuseColor.rgb=mix(diffuseColor.rgb,grit+sheen*(1.-bore),asphalt);`:''}
        ${surveyed?`
        vec2 roadUV=roadPoint.xy/4.04;vec3 grainColor=texture2D(asphaltMap,roadUV).rgb;
        vec3 N=texture2D(normalRoad,roadUV).rgb*2.-1.;
        float rough=texture2D(roughRoad,roadUV).r;N=normalize(vec3(N.xy*.40,1.));
        vec3 mirror=reflect(-V,N);vec2 direction=vec2(fract(atan(mirror.y,mirror.x)/6.283185),clamp(asin(max(mirror.z,0.))*.63662,.001,.999));
        vec3 reflected=mix(texture2D(skyDay,direction).rgb,texture2D(skyNight,direction).rgb,afterdark);
        float grazing=pow(1.-max(0.,dot(V,N)),3.4);
        vec3 litRoad=grainColor*mix(vec3(.65,.69,.76),vec3(.060,.093,.18),afterdark)+reflected*grazing*(.80-.50*rough);
        if(abs(roadPoint.x-1000.)<180.&&abs(roadPoint.y+351.)<86.){
          for(int i=0;i<${fixtures.length};i++){
            vec3 delta=bollards[i]-roadPoint;vec3 L=normalize(delta),H=normalize(L+V);
            float lobe=pow(max(dot(N,H),0.),mix(220.,65.,rough));
            litRoad+=vec3(1.,.48,.17)*(1.05+1.9*afterdark)*lobe/(1.+.013*dot(delta,delta));
          }
        }
        ${court?`litRoad=meridianAfterRain(litRoad,roadPoint,V,N,reflected,rough,afterdark);`:''}
        diffuseColor.rgb=mix(diffuseColor.rgb,litRoad,asphalt*(1.-bore));
        `:''}
      `);
    };
  }
  const mesh=new THREE.Mesh(g,paint);mesh.name='Surveyed roads';group.add(mesh);
}

function galleryFinish(group,w,uniforms){
  const g=w.vaderland.gallery;
  const earth=new THREE.ShaderMaterial({uniforms,vertexShader:vertex,fragmentShader:common+`
    void main(){
      float variation=fbm(p.xy*.11+p.z*.02);
      vec3 sod=mix(vec3(.047,.075,.035),vec3(.23,.217,.108),variation);
      float course=fract((p.z+p.x*.004)*1.38);
      vec3 face=mix(vec3(.083,.095,.087),vec3(.20,.20,.16),variation);
      face*=.72+.28*smoothstep(.02,.19,course);
      vec3 surface=mix(face,sod,smoothstep(.4,.8,normalize(n).z));
      gl_FragColor=vec4(haze(surface*(vec3(.37,.46,.56)+vec3(.98,.58,.32)*max(dot(normalize(n),sun),0.))*mix(1.,.35,night)),1.);
      #include <colorspace_fragment>
    }`});
  const material=new THREE.ShaderMaterial({uniforms,
    vertexShader:vertex,fragmentShader:common+`
      ${w.vaderland.cathedral?'uniform sampler2D alloyColor;':''}
      void main(){
        float bay=fract((p.x-2900.)/16.);
        float level=p.z-${g.floor_z_m.toFixed(3)};
        float normalUp=normalize(n).z;
        float joint=smoothstep(.006,.017,min(bay,1.-bay));
        float concrete=fbm(p.xy*.28+p.z*.09)+fbm(vec2(p.y+p.x,p.z)*1.6)*.27;
        vec3 color=mix(vec3(.115,.132,.15),vec3(.25,.235,.19),concrete)*(.74+.26*joint);
        if(normalUp<-.7){
          float rib=smoothstep(.03,.1,abs(fract((p.y+4350.)*.52)-.5));
          color*=vec3(.58,.69,.85)*(.75+.25*rib);
        }else if(normalUp>.7){
          color=mix(vec3(.105,.128,.066),vec3(.27,.25,.125),fbm(p.xy*.18));
        }else{
          float interior=1.-smoothstep(10.8,11.2,abs(p.y+4350.));
          float inset=smoothstep(.12,.16,bay)*(1.-smoothstep(.84,.88,bay));
          float kick=1.-smoothstep(.8,.87,level);
          color*=mix(vec3(1.),vec3(.51,.57,.63),kick);
          float lamp=exp(-abs(level-4.72)*16.)*inset;
          float reflected=exp(-abs(level-4.72)*1.0)*inset;
          vec3 light=p.y<-4350.?vec3(1.8,.88,.32):vec3(.56,1.06,1.48);
          color=color*vec3(.69,.77,.85)+light*(lamp*2.1+reflected*.13)*interior;
          float fascia=(1.-smoothstep(.2,.65,min(abs(p.x-2900.),abs(p.x-3500.))))*smoothstep(6.7,7.1,level);
          color+=vec3(1.1,.60,.21)*fascia*(.16+.84*(1.-smoothstep(.06,.14,abs(level-7.4))));
        }
        ${w.vaderland.cathedral?`
        float lateral=p.y+4350.;
        float interior=1.-smoothstep(10.84,11.15,abs(lateral));
        if(interior>.99&&normalUp<.7&&level>.2){
          vec3 brass=vec3(1.36,.57,.16),violet=vec3(.43,.26,1.12);
          vec3 tone=mix(brass,violet,smoothstep(-4.5,4.5,lateral));
          float station=(p.x-2900.)/16.;
          float ribDistance=abs(fract(station+.5)-.5)*16.;
          float collar=1.-smoothstep(.25,.58,ribDistance);
          float metal=texture2D(alloyColor,vec2(p.x+p.y*.11,p.z+lateral*.42)*.28).r;
          vec3 graphite=(vec3(.010,.012,.020)+metal*vec3(.026,.033,.041))*(.75+.25*joint);
          float wash=exp(-ribDistance*.51);
          if(normalUp<-.7){
            float coffer=smoothstep(.06,.13,abs(fract(lateral*.41+.5)-.5));
            float tube=1.-smoothstep(.052,.089,ribDistance);
            float fine=1.-smoothstep(.029,.061,abs(ribDistance-.21));
            float socket=smoothstep(.115,.16,abs(fract(lateral*.245+.5)-.5));
            float spine=1.-smoothstep(.54,.73,abs(lateral));
            color=graphite*(.57+.61*coffer)*(1.-.38*collar);
            color+=tone*(.081*wash+1.10*tube*socket+.24*fine);
            color+=vec3(.10,.15,.24)*spine*(.16+.24*wash);
          }else{
            float horizontal=abs(fract(level/1.42+.5)-.5)*1.42;
            float groove=1.-smoothstep(.013,.026,horizontal);
            float rail=1.-smoothstep(.044,.073,abs(level-.62));
            float service=1.-smoothstep(.028,.060,abs(level-4.36));
            float segment=smoothstep(.08,.18,bay)*(1.-smoothstep(.34,.43,bay));
            float jamb=1.-smoothstep(.142,.186,ribDistance);
            float beacon=1.-smoothstep(.085,.16,abs(level-1.12));
            color=graphite*(.94+.45*smoothstep(.82,1.1,level))*(1.-.68*groove)*(1.-.44*collar);
            color+=tone*(.12*wash*exp(-abs(level-4.9)*.57)+.72*service*segment);
            color+=vec3(.205,.33,.46)*rail*(.31+.69*wash)+tone*beacon*jamb*.78;
            color+=vec3(.032,.043,.046)*smoothstep(.58,.85,1.-level/6.6);
          }
          float depth=max(0.,distance(cameraPosition,p)-18.);
          color=mix(color,vec3(.097,.083,.109),.19*(1.-exp(-depth*.006)));
        }
        `:''}
        gl_FragColor=vec4(haze(color*mix(1.,.72,night)),1.);
        #include <colorspace_fragment>
      }`});
  for(const o of w.obstacles.filter(o=>o.id.startsWith('gallery-'))){
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(...o.half.map(h=>2*h)),o.role==='cover'?earth:material);
    mesh.position.set(...o.center);mesh.name=o.id;
    if(w.vaderland.cathedral)mesh.userData.surveySpans=[{end:12,id:o.id}];
    group.add(mesh);
  }
  const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=96;
  const ctx=canvas.getContext('2d');
  ctx.fillStyle='#202b30';ctx.fillRect(0,0,1024,96);
  ctx.fillStyle='#e4a45e';ctx.fillRect(0,84,1024,5);
  ctx.fillStyle='#f3ebd7';ctx.font='600 62px "Barlow Condensed", "Arial Narrow", sans-serif';
  ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText('LANTERN  GALLERY',512,44,860);
  const face=new THREE.CanvasTexture(canvas);face.colorSpace=THREE.SRGBColorSpace;face.anisotropy=8;
  const sign=new THREE.MeshBasicMaterial({map:face,polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-2});
  for(const [i,x] of g.portal_x_m.entries()){
    const plate=new THREE.Mesh(new THREE.PlaneGeometry(11.7,1.10),sign);
    plate.rotation.order='ZYX';plate.rotation.x=Math.PI/2;plate.rotation.z=i?Math.PI/2:-Math.PI/2;
    plate.position.set(x+(i ? .012 : -.012),g.center[1],g.ceiling_z_m+1.08);group.add(plate);
  }
}

function wayfindingLights(group,w){
  const pos=[],colors=[],sizes=[];
  function lamp(x,y,z,color,size){
    pos.push(x,y,z);new THREE.Color(color).toArray(colors,colors.length);sizes.push(size);
  }
  for(const r of w.vaderland.routes){
    const major=r.kind==='viaduct'||r.kind==='express'||r.kind==='boulevard';
    if(!major && r.width_m<40)continue;
    if(r.kind==='apron')continue;
    const step=major?19:55, points=r.points;
    let next=0,station=0;
    for(let i=1;i<points.length;i++){
      const a=points[i-1],b=points[i],dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
      if(!length)continue;
      while(next<=station+length){
        const t=(next-station)/length;
        for(const side of [-1,1]){
          const offset=side*(r.width_m/2-.85);
          const x=a[0]+t*dx-offset*dy/length,y=a[1]+t*dy+offset*dx/length;
          const z=r.deck_z_m??heightfieldZ(w,x,y);
          const color=side<0 && (r.kind==='viaduct'||r.kind==='express')?'#b498ff':'#ffc16b';
          lamp(x,y,z+.12,color,major?1.0:.85);
        }
        next+=step;
      }
      station+=length;
    }
  }
  const {edgeLights,thresholdLights}=primaryRunwayCues(w);
  for(const [x,y,color] of [...edgeLights,...thresholdLights])lamp(x,y,.26,color,1.2);
  for(const o of w.obstacles){
    if(o.role!=='architecture' || o.half[2]<20 || o.kind==='mesh')continue;
    const [x,y,z]=o.center,[a,b,c]=o.half;
    if(o.kind==='cylinder'){
      for(let i=0;i<16;i++){
        const angle=i*Math.PI/8;lamp(x+(a-.5)*Math.cos(angle),y+(a-.5)*Math.sin(angle),z+c+.12,'#ffd47c',.8);
      }
    }else for(const u of [-1,1])for(const v of [-1,1])lamp(x+u*(a-.36),y+v*(b-.36),z+c+.12,'#ffd385',.85);
  }
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
  g.setAttribute('tint',new THREE.Float32BufferAttribute(colors,3));
  g.setAttribute('radius',new THREE.Float32BufferAttribute(sizes,1));
  const m=new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    vertexShader:`attribute vec3 tint;attribute float radius;varying vec3 lightColor;
      void main(){vec4 q=modelViewMatrix*vec4(position,1.); gl_Position=projectionMatrix*q;
        gl_PointSize=clamp(3.3+680.*radius/max(1.,-q.z),3.3,19.);lightColor=tint*.82;}`,
    fragmentShader:`varying vec3 lightColor;void main(){float d=length(2.*gl_PointCoord-1.);
      if(d>=1.)discard;float v=exp(-5.8*d*d);gl_FragColor=vec4(lightColor,v*.85);
      #include <colorspace_fragment>
    }`});
  group.add(new THREE.Points(g,m));
}

function terminalFascia(group,o){
  const canvas=document.createElement('canvas');canvas.width=2048;canvas.height=144;
  const ctx=canvas.getContext('2d');ctx.textAlign='center';ctx.textBaseline='middle';
  ctx.fillStyle='#101e30';ctx.fillRect(0,0,2048,144);
  ctx.fillStyle='#ffb74d';ctx.fillRect(0,1,2048,6);ctx.fillRect(0,135,2048,4);
  ctx.font='600 91px system-ui';ctx.fillStyle='#ffe4a1';ctx.fillText('V A D E R L A N D     /     V T X',1024,70);
  const map=new THREE.CanvasTexture(canvas);map.colorSpace=THREE.SRGBColorSpace;map.anisotropy=8;
  const radius=o.half[0]+.055;
  const g=new THREE.CylinderGeometry(radius,radius,7.2,52,1,true,-1.1,2.2).rotateX(Math.PI/2);
  const sign=new THREE.Mesh(g,new THREE.MeshBasicMaterial({map,toneMapped:false,polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-3}));
  sign.position.set(o.center[0],o.center[1],o.center[2]+o.half[2]-5.6);group.add(sign);
}

function roofPads(group,w){
  const paint=[],rims=[];
  for(const o of w.obstacles){
    if(o.kind!=='box'||!o.landable||!o.id.endsWith('-crown')||o.half[0]<11||o.half[1]<11)continue;
    const [x,y,z]=o.center,[a,b,c]=o.half;
    if((Math.floor(Math.abs(x+y))%5)!==0)continue;
    const d=Math.min(a,b)*1.31,level=z+c+.055;
    rims.push([x,y,level,d,d,1,'#eac775']);
    for(const off of [-1,1])paint.push([x+off*d*.135,y,level+.003,d*.042,d*.42,1,'#dce2d8']);
    paint.push([x,y,level+.003,d*.27,d*.042,1,'#dce2d8']);
  }
  const mat=()=>new THREE.MeshBasicMaterial({side:THREE.DoubleSide,polygonOffset:true,polygonOffsetFactor:-2});
  instanced(group,new THREE.RingGeometry(.456,.50,48),mat(),rims);
  instanced(group,new THREE.PlaneGeometry(),mat(),paint);
}

function roofMark(group,o){
  const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512;
  const ctx=canvas.getContext('2d');ctx.clearRect(0,0,1024,512);
  ctx.textAlign='center';ctx.fillStyle='#f3cc78';ctx.font='600 82px system-ui';
  ctx.fillText('V A D E R L A N D',512,218);
  ctx.font='bold 132px system-ui';ctx.fillText('VTX',512,365);
  const map=new THREE.CanvasTexture(canvas);map.colorSpace=THREE.SRGBColorSpace;map.anisotropy=8;
  const mesh=new THREE.Mesh(new THREE.PlaneGeometry(94,47),new THREE.MeshBasicMaterial({map,transparent:true,
    depthWrite:false,polygonOffset:true,polygonOffsetFactor:-3}));
  mesh.position.set(o.center[0],o.center[1],o.center[2]+o.half[2]+.03);group.add(mesh);
}

// v33 conifer: drooping branch skirts with ragged tips and an irregular silhouette, darker
// towards the trunk. Same unit bounds and triangle budget as pineCrown.
function coniferCrown(){
  const vertices=[],colours=[];
  let seed=7;const rnd=()=>((seed=(seed*16807)%2147483647)/2147483647);
  const tri=(a,b,c,ka,kb,kc)=>{vertices.push(...a,...b,...c);
    for(const k of [ka,kb,kc])colours.push(k*.86,k,k*.80);};
  const tiers=8,n=14;
  for(let t=0;t<tiers;t++){
    const f=t/(tiers-1);
    const top=-.30+f*.80, droop=.16*(1.-.45*f);
    const outer=.56*Math.pow(1.-f*.92,.85), inner=outer*.16;
    const hub=[0,0,Math.min(.5,top+.05)];
    const ring=[];
    for(let j=0;j<n;j++){
      const a=(j+rnd()*.35)*Math.PI*2/n+t*.61, tip=j%2===0;
      const r=outer*(tip?1.:.62)*(.85+.3*rnd());
      ring.push([r*Math.cos(a),r*Math.sin(a),top-droop*(tip?1.:.55)-.03*rnd()]);
    }
    for(let j=0;j<n;j++){
      const a=ring[j],b=ring[(j+1)%n];
      const lightA=.55+.42*Math.hypot(a[0],a[1])/outer+.08*f, lightB=.55+.42*Math.hypot(b[0],b[1])/outer+.08*f;
      tri(a,b,hub,lightA,lightB,.34+.10*f);                          // upper face of the skirt
      tri(b,a,[0,0,top-droop*1.25],lightB*.62,lightA*.62,.22);     // shaded underside
    }
  }
  const mesh=new THREE.BufferGeometry();
  mesh.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
  mesh.setAttribute('color',new THREE.Float32BufferAttribute(colours,3));mesh.computeVertexNormals();
  return mesh;
}

function pineCrown(){
  const vertices=[],colours=[];
  const triangle=(points,shade)=>{
    vertices.push(...points.flat());for(let i=0;i<3;i++)colours.push(shade*.91,shade,shade*.88);
  };
  for(let tier=0;tier<7;tier++){
    const base=-.5+tier*.122,radius=.55*(1.-tier*.119),peak=Math.min(.5,base+.40);
    const ring=[];
    for(let j=0;j<16;j++){
      const angle=j*Math.PI/8+tier*.47,tip=j%2===0;
      const r=radius*(tip?1.:.58)*(.92+.08*Math.sin(j*13+tier*5));
      ring.push([r*Math.cos(angle),r*Math.sin(angle),base+(tip?0.:.055)+.019*Math.cos(7*j+tier)]);
    }
    for(let j=0;j<ring.length;j++){
      const a=ring[j],b=ring[(j+1)%ring.length];
      triangle([a,b,[0,0,peak]],.72+tier*.045+(j%3)*.055);
      triangle([b,a,[0,0,base+.07]],.54+tier*.031);
    }
  }
  const mesh=new THREE.BufferGeometry();
  mesh.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
  mesh.setAttribute('color',new THREE.Float32BufferAttribute(colours,3));mesh.computeVertexNormals();
  return mesh;
}

function structures(group,w,uniforms){
  const blocks=[],drums=[],pines=[],trunks=[],engineering=[],columns=[];
  const boxIds=[],columnIds=[],market=new Set(w.vaderland.quarter?.retained??[]);
  for(const o of w.obstacles){
    if(neighbourhoodSolid(o.id)||lanternRaceSolid(o.id))continue;
    if(market.has(o.id)||o.id.startsWith('crest-gardens-')||(w.vaderland.city_lights&&avenueParcel(o)))continue;
    const [x,y,z]=o.center,[a,b,c]=o.half;
    if(w.vaderland.airfield && (o.finish || airportTree(o)))continue;
    if(w.vaderland.gallery && o.id.startsWith('gallery-'))continue;
    if(['pier','deck','wall','dock'].includes(o.role)){
      (o.kind==='box'?engineering:columns).push([x,y,z,a*2,b*2,c*2,o.color]);
      (o.kind==='box'?boxIds:columnIds).push(o.id);
    }else if(o.kind==='box'){
      blocks.push([x,y,z,a*2,b*2,c*2,o.color]);
    }else if(o.role==='architecture'){
      drums.push([x,y,z,a*2,a*2,c*2,o.color]);
      if(o.id==='airport-rotunda-crown')roofMark(group,o);
      if(Number(w.version)>=5 && o.id==='airport-rotunda-drum')terminalFascia(group,o);
    }else if(o.role==='conifer'){
      trunks.push([x,y,z,2*a,2*a,2*c,'#645443']);
      pines.push([x,y,z+c*.12,o.crown_radius_m*2,o.crown_radius_m*2,c*1.76,o.color]);
    }else{
      trunks.push([x,y,z-c*.52,a*.45,a*.45,c*.96,'#534737']);
      pines.push([x,y,z+c*.12,a*1.7,a*1.7,c*1.76,o.color]);
    }
  }
  instanced(group,new THREE.BoxGeometry(),facadeMaterial(uniforms),blocks);
  instanced(group,new THREE.CylinderGeometry(.5,.5,1,48).rotateX(Math.PI/2),facadeMaterial(uniforms),drums);
  const boxes=instanced(group,new THREE.BoxGeometry(),new THREE.MeshStandardMaterial({roughness:.72,metalness:.18}),engineering);
  const pierMaterial=new THREE.MeshStandardMaterial({roughness:.72,metalness:.18});
  if(w.vaderland.neighbourhoods){
    // v33: cast concrete. Formwork lifts every 1.2 m, rain streaks down the faces, a darker wet base.
    pierMaterial.roughness=.9;pierMaterial.metalness=.02;
    pierMaterial.onBeforeCompile=shader=>{
      shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vWorld;')
        .replace('#include <worldpos_vertex>','#include <worldpos_vertex>\nvWorld=(modelMatrix*instanceMatrix*vec4(transformed,1.)).xyz;');
      shader.fragmentShader=shader.fragmentShader.replace('#include <common>',`#include <common>
        varying vec3 vWorld;
        float h1(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
        float n1(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h1(i),h1(i+vec2(1,0)),f.x),mix(h1(i+vec2(0,1)),h1(i+1.),f.x),f.y);}`)
        .replace('#include <color_fragment>',`#include <color_fragment>
        float lift=smoothstep(.0,.06,abs(fract(vWorld.z/1.2)-.5)-.44);
        float streak=n1(vec2((vWorld.x+vWorld.y)*.9,vWorld.z*.05));
        float grime=n1(vWorld.xy*.15+vWorld.z*.02);
        vec3 concrete=vec3(.44,.43,.40)*(.80+.22*grime)*(1.-.18*streak)*(1.-.22*lift);
        diffuseColor.rgb=concrete;`);
    };
  }
  const piers=instanced(group,new THREE.CylinderGeometry(.5,.5,1,28).rotateX(Math.PI/2),pierMaterial,columns);
  if(boxes)boxes.userData.sceneryIds=boxIds;
  if(piers)piers.userData.sceneryIds=columnIds;
  instanced(group,new THREE.CylinderGeometry(.5,.5,1,5).rotateX(Math.PI/2),new THREE.MeshStandardMaterial(),trunks);
  const detailed=Number(w.version)>=5;
  instanced(group,w.vaderland.neighbourhoods?coniferCrown():detailed?pineCrown():new THREE.ConeGeometry(.6,1,7).rotateX(Math.PI/2),
    new THREE.MeshStandardMaterial({roughness:1,vertexColors:detailed}),pines);
  if(w.vaderland.gallery)galleryFinish(group,w,uniforms);
}

function wetChannel(group,w,stream,ground,uniforms){
  let s=0, last;
  const triangles=[];
  for(let i=0;i<stream.points.length;i++){
    const p=stream.points[i],a=stream.points[Math.max(0,i-1)],b=stream.points[Math.min(i+1,stream.points.length-1)];
    if(i)s+=Math.hypot(p[0]-stream.points[i-1][0],p[1]-stream.points[i-1][1]);
    const dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);
    const pair=[-1,1].map(sign=>({x:p[0]-sign*dy/len*stream.width_m/2,
      y:p[1]+sign*dx/len*stream.width_m/2,a:[sign,s]}));
    if(last)triangles.push([last[0],pair[0],last[1]],[pair[0],pair[1],last[1]]);
    last=pair;
  }
  const draped=ground.drapeTriangles(triangles,{offset:.024});
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(draped.pos,3));
  g.setAttribute('normal',new THREE.Float32BufferAttribute(draped.nor,3));
  g.setAttribute('flow',new THREE.Float32BufferAttribute(draped.att,2));
  const mat=new THREE.ShaderMaterial({uniforms,side:THREE.DoubleSide,transparent:true,depthWrite:false,
    polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-4,
    vertexShader:'attribute vec2 flow; varying vec2 channel;'+vertex.replace('p = positionWorld.xyz;','channel=flow; p = positionWorld.xyz;'),
    fragmentShader:'varying vec2 channel; uniform float clock; uniform sampler2D clouds;'+common+`
    void main(){
      float side=abs(channel.x);
      float s=channel.y;
      float edge=fbm(vec2(channel.x*6.,s*.09))*.13;
      float cover=1.-smoothstep(.78+edge,1.,side);
      float chutes=smoothstep(.04,.55,1.-normalize(n).z);
      float strands=fbm(vec2(channel.x*23.+sin(s*.042)*.5,(s-clock*8.)*.095));
      float breakers=fbm(vec2(channel.x*8.,(s-clock*2.)*.11));
      float foam=smoothstep(.27,.76,strands)*chutes+smoothstep(.68,.82,breakers)*(.24+.5*side);
      vec3 norm=normalize(vec3(.09*(strands-.50),.09*(breakers-.50),1.));
      vec3 view=normalize(cameraPosition-p);
      vec3 reflection=skySample(clouds,reflect(-view,norm))*vec3(.52,.67,.8);
      vec3 water=mix(vec3(.013,.071,.077),vec3(.039,.153,.157),breakers);
      water=mix(water,reflection,.12+.33*pow(1.-clamp(dot(norm,view),0.,1.),3.));
      vec3 whitewater=mix(vec3(.22,.39,.43),vec3(.77,.85,.82),strands);
      vec3 river=mix(water,whitewater,clamp(foam,0.,1.));
      if(rooftopPass>.5){
        // v33: deep centre, shallow edges, two moving ripple layers, sun glints, fast sheeting on the falls
        float fall=smoothstep(.30,.75,1.-normalize(n).z);
        vec2 r1=vec2(channel.x*3.1,(s-clock*(3.+11.*fall))*.21),r2=vec2(channel.x*7.3+1.7,(s-clock*(5.+17.*fall))*.47);
        float w1=fbm(r1),w2=fbm(r2);
        vec3 N2=normalize(vec3((w1-.5)*.22+(w2-.5)*.12,(w2-.5)*.16,1.));
        vec3 sky2=skySample(clouds,reflect(-view,N2))*vec3(.50,.62,.72);
        vec3 deep=mix(vec3(.006,.030,.036),vec3(.020,.090,.092),side*side);
        float fres=pow(1.-clamp(dot(N2,view),0.,1.),4.);
        vec3 surface=mix(deep,sky2,.10+.55*fres);
        surface+=vec3(1.,.86,.62)*pow(max(dot(reflect(-view,N2),sun),0.),180.)*1.6*(1.-night);
        float sheet=fall*smoothstep(.35,.70,fbm(vec2(channel.x*31.,(s-clock*24.)*.16)));
        float bankFoam=smoothstep(.80,.97,side)*smoothstep(.45,.70,w2);
        float churn=clamp(foam*.8+sheet+bankFoam*.7,0.,1.);
        river=mix(surface,mix(vec3(.30,.44,.47),vec3(.86,.92,.90),w1),churn);
      }
      gl_FragColor=vec4(haze(river*mix(1.,.36,night)),cover);
      #include <colorspace_fragment>
    }`});
  const mesh=new THREE.Mesh(g,mat);mesh.name='Twin Falls wet bed';group.add(mesh);
}

// v33: mist rising from the foot of each steep chute, found from the stream geometry.
function fallsMist(group,w,stream,uniforms){
  const pts=stream.points,emitters=[];
  for(let i=4;i<pts.length-4;i++){
    const up=pts[i-4],here=pts[i],down=pts[i+4];
    const za=heightfieldZ(w,...up),zb=heightfieldZ(w,...here),zc=heightfieldZ(w,...down);
    const above=(za-zb)/Math.max(1,Math.hypot(up[0]-here[0],up[1]-here[1]));
    const below=(zb-zc)/Math.max(1,Math.hypot(down[0]-here[0],down[1]-here[1]));
    if(above>.45&&below<.18&&!emitters.some(e=>Math.hypot(e[0]-here[0],e[1]-here[1])<60))emitters.push([here[0],here[1],zb,above]);
  }
  if(!emitters.length)return;
  const count=1400*emitters.length,seeds=new Float32Array(count*4),origin=new Float32Array(count*4);
  let state=6151;const next=()=>((state=Math.imul(state,1664525)+1013904223>>>0)/4294967296);
  for(let i=0;i<count;i++){const e=emitters[i%emitters.length];
    origin.set([e[0],e[1],e[2],Math.min(1.5,e[3])],i*4);for(let k=0;k<4;k++)seeds[i*4+k]=next();}
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(count*3),3));
  g.setAttribute('origin',new THREE.Float32BufferAttribute(origin,4));g.setAttribute('seed',new THREE.Float32BufferAttribute(seeds,4));
  const m=new THREE.ShaderMaterial({uniforms:{clock:uniforms.clock,night:uniforms.night},transparent:true,depthWrite:false,fog:false,
    vertexShader:`attribute vec4 origin,seed;uniform float clock;varying float alpha;varying vec2 spin;
      void main(){
        float life=fract(seed.w+clock*(.05+.04*seed.z));
        float a=seed.x*6.2831853,r=(4.+seed.y*28.)*(.35+.65*life)*origin.w;
        vec3 p=origin.xyz+vec3(cos(a)*r,sin(a)*r,2.+life*(14.+26.*seed.z)*origin.w);
        p.xy+=vec2(.9,.35)*life*18.;
        alpha=sin(life*3.14159)*(.035+.045*seed.y)*smoothstep(.0,.25,life);
        vec4 v=viewMatrix*vec4(p,1.);gl_Position=projectionMatrix*v;
        gl_PointSize=clamp((14.+34.*life)*500./max(1.,-v.z),2.,240.);spin=vec2(cos(seed.z*6.),sin(seed.z*6.));
      }`,
    fragmentShader:`uniform float night;varying float alpha;varying vec2 spin;
      void main(){vec2 q=gl_PointCoord-.5;float r=dot(q,q)*4.;if(r>1.)discard;
        float soft=(1.-r)*(1.-r);gl_FragColor=vec4(mix(vec3(.80,.86,.90),vec3(.16,.19,.25),night),alpha*soft);}`});
  const mist=new THREE.Points(g,m);mist.frustumCulled=false;mist.renderOrder=3;mist.name='Twin Falls mist';group.add(mist);
}

function streams(group,w,ground,uniforms){
  for(const stream of w.vaderland.streams||[]){
    if(Number(w.version)>=6){wetChannel(group,w,stream,ground,uniforms);if(w.vaderland.neighbourhoods)fallsMist(group,w,stream,uniforms);continue;}
    const pos=[],colors=[],index=[];
    for(let i=0;i<stream.points.length;i++){
      const p=stream.points[i],a=stream.points[Math.max(0,i-1)],b=stream.points[Math.min(i+1,stream.points.length-1)];
      const length=Math.hypot(b[0]-a[0],b[1]-a[1]);
      const slope=Math.abs(heightfieldZ(w,...b)-heightfieldZ(w,...a))/length;
      const color=new THREE.Color(slope>.32?'#e0f5ff':slope>.12?'#a6d7dc':'#307f8c');
      for(const side of [-1,1]){
        const x=p[0]-side*(b[1]-a[1])/length*stream.width_m/2,y=p[1]+side*(b[0]-a[0])/length*stream.width_m/2;
        pos.push(x,y,heightfieldZ(w,x,y)+.13);colors.push(color.r,color.g,color.b);
      }
      if(i){const j=(i-1)*2;index.push(j,j+2,j+1,j+2,j+3,j+1);}
    }
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
    g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.setIndex(index);
    group.add(new THREE.Mesh(g,new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,
      polygonOffset:true,polygonOffsetFactor:-2,polygonOffsetUnits:-5})));
  }
}

export function buildVaderland(group,w,scene,camera,sky,harbour){
  const previous={fog:scene.fog,far:camera.far,sky:sky.group.visible};
  const newest=Number(w.version)>=5;
  const uniforms={night:{value:0},meridian:{value:newest?1:0},airfieldSurvey:{value:w.vaderland.airfield?1:0},fallsSurvey:{value:Number(w.version)>=6?1:0},clock:{value:0},
    waterClock:{value:0},physicalTide:{value:w.vaderland.harbour_surface?1:0},clouds:{value:null},reliefLight:{value:null},lounge:{value:null},
    arrivalsSurvey:{value:w.vaderland.arrivals?1:0},forecourtLight:{value:null},tree0:{value:null},tree1:{value:null},tree2:{value:null},
    upland:{value:null},granite:{value:null},civic:{value:null},hasCivic:{value:Number(w.version)>=4?1:0},
    marinaSurvey:{value:w.vaderland.lantern_marina?1:0}};
  let disposed=false;
  const loader=new THREE.TextureLoader();
  const resources=[];
  function texture(name,url,srgb,repeat){
    return new Promise((resolve,reject)=>{
      const t=loader.load(new URL(url,import.meta.url).href,resolve,undefined,reject);
      t.colorSpace=srgb?THREE.SRGBColorSpace:THREE.NoColorSpace;
      if(repeat){t.wrapS=THREE.RepeatWrapping;t.wrapT=THREE.RepeatWrapping;t.anisotropy=8;}
      uniforms[name].value=t;resources.push(t);
    });
  }
  Object.assign(uniforms,{offices:{value:null},shops:{value:null},metalPlate:{value:null},paving:{value:null},civicPass:{value:w.vaderland.civic_district?1:0}});
  const neutralDensity=new THREE.DataTexture(new Uint8Array([255,255,255,255]),1,1);neutralDensity.needsUpdate=true;
  Object.assign(uniforms,{rooftopPass:{value:w.vaderland.neighbourhoods?1:0},cityDensity:{value:neutralDensity},
    cityDensityBounds:{value:new THREE.Vector4(DENSITY_BOUNDS.x0,DENSITY_BOUNDS.y0,DENSITY_BOUNDS.x1-DENSITY_BOUNDS.x0,DENSITY_BOUNDS.y1-DENSITY_BOUNDS.y0)}});
  const neutralRace=new THREE.DataTexture(new Uint8Array([0,0,0,255]),1,1);neutralRace.needsUpdate=true;
  Object.assign(uniforms,{raceOn:{value:0},raceLight:{value:neutralRace},raceArea:{value:new THREE.Vector4(0,0,1,1)},raceLevel:{value:0}});
  const density=w.vaderland.neighbourhoods?cityDensity(w):null;
  if(density){
    const bytes=new Uint8Array(density.nx*density.ny*4);
    density.level.forEach((v,k)=>{bytes[k*4]=bytes[k*4+1]=bytes[k*4+2]=Math.round(Math.min(1,v)*255);bytes[k*4+3]=255;});
    const tex=new THREE.DataTexture(bytes,density.nx,density.ny);tex.magFilter=tex.minFilter=THREE.LinearFilter;tex.needsUpdate=true;
    uniforms.cityDensity.value=tex;
  }
  Object.assign(uniforms,{photographic:{value:w.vaderland.frontage?1:0},marketPass:{value:w.vaderland.quarter?1:0},streetFronts:{value:null},daySky:{value:null},nightSky:{value:null},sceneryClock:{value:0}});
  Object.assign(uniforms,{courtGlow:{value:w.vaderland.parallax_court?1:0},courtRooms:{value:null},blueHour:{value:0},cityDayReflection:{value:null},cityNightReflection:{value:null},cityReflectionReady:{value:0}});
  uniforms.gardenDistrict={value:w.vaderland.crest_gardens?1:0};
  const optics=w.vaderland.frontage?surveyedOptics(group,w,uniforms):null;
  const departments=w.vaderland.operations?district(group,w,uniforms,common,optics):null;
  const reliefFile=w.vaderland.quarter?'relief-market.png':w.vaderland.speedway?'relief-velocity.png':w.vaderland.civic_district?'relief-civic.png':w.vaderland.arrivals?'relief-arrivals.png':w.vaderland.landing?'relief-landing.png':w.vaderland.airfield?'relief-airport.png':({'1':'relief-light.png','2':'relief-city.png','3':'relief-routes.png','4':'relief-final.png',
    '5':'relief-meridian.png','6':'relief-falls.png'})[w.version]??'relief-gallery.png';
  const cityReflections=w.vaderland.city_lights?Promise.all(['Day','Night'].map(mode=>{
    const key='city'+mode+'Reflection';
    const loaded=texture(key,'./avenue-reflection-'+mode.toLowerCase()+'.webp',true,false);
    uniforms[key].value.wrapS=THREE.RepeatWrapping;
    return loaded;
  })).then(()=>{uniforms.cityReflectionReady.value=1;}):null;
  const mud=w.vaderland.surface_detail?.quarry_mud;
  if(mud)uniforms.quarryMud={value:null};
  const mudReady=mud?texture('quarryMud','./surveyed-materials/quarry-mud.webp',true,true):null;
  const courtInteriors=w.vaderland.parallax_court?texture('courtRooms','./parallax-night-venues.webp',true,false):null;
  const ready=Promise.all([optics?.ready,departments?.ready,cityReflections,courtInteriors,mudReady,...(w.vaderland.quarter?[texture('streetFronts','./meridian-street-frontages.webp',true,false)]:[]),...(departments?[...['offices','shops','paving'].map(k=>texture(k,'./meridian-'+k+'.webp',true,true)),texture('metalPlate','./meridian-metal.webp',true,true)]:[]),texture('clouds','./alpine-dusk.jpg',true,false),
    ...(w.vaderland.arrivals?[texture('lounge','./meridian-lounge.webp',true,true),texture('forecourtLight','./terminal-light.png',false,false),
      ...['spruce','linden','pine'].map((name,i)=>texture('tree'+i,'./meridian-'+name+'.webp',true,false)),
      buildTerminal(group,w,uniforms,common)]:[]),
    texture('reliefLight','./'+reliefFile,false,false),texture('upland','./upland.jpg',true,true),
    ...(w.version==='4'?[texture('civic','./civic-ground.png',false,false)]:[]),
    ...(newest?[texture('civic','./civic-meridian.png',false,false),texture('granite','./gneiss.jpg',true,true)]:[])]);
  sky.group.visible=false;
  scene.fog=new THREE.Fog('#a19aa9',4700,22500);
  camera.far=31000;camera.updateProjectionMatrix();
  const dome=new THREE.Mesh(new THREE.SphereGeometry(17000,48,24).rotateX(Math.PI/2),new THREE.ShaderMaterial({
    uniforms,side:THREE.BackSide,depthWrite:false,depthTest:false,
    vertexShader:'varying vec3 ray;varying vec3 p;varying vec3 n;void main(){ray=position;p=position;n=normal;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader:`uniform sampler2D clouds; varying vec3 ray;`+common+`
    void main(){vec3 d=normalize(ray);vec3 c=skySample(clouds,d);
      if(photographic>.5){
        c=mix(c,mix(vec3(.069,.084,.101),vec3(.007,.013,.03),night),smoothstep(.0,.16,-d.z));
        float city=exp(-length((cameraPosition.xy-vec2(440.,2760.))/vec2(2400.,2200.)));
        float glow=exp(-abs(d.z-.033)*4.6)*city*night;
        c+=mix(vec3(.040,.066,.111),vec3(.108,.064,.044),.5+.5*d.x)*glow;
        gl_FragColor=vec4(c,1.);
        #include <colorspace_fragment>
        return;
      }
      float east=clamp(.5+.5*dot(d.xy,normalize(vec2(.94,.35))),0.,1.);
      float horizon=1.-smoothstep(.02,.45,abs(d.z));
      c=mix(c,c*vec3(.38,.59,.85)+vec3(.014,.023,.055),horizon*(1.-east*east));
      c=mix(c,vec3(.119,.139,.196),smoothstep(.0,.19,-d.z));
      if(meridian>.5){
        float dusk=smoothstep(.25,.98,dot(d.xy,normalize(vec2(.92,.38))))*(1.-smoothstep(.04,.27,d.z));
        float L=dot(c,vec3(.24,.64,.12));
        c=mix(c,vec3(L*.23,L*.42,L*.91)+vec3(.003,.009,.035),.75*(1.-dusk));
        c*=1.-.22*smoothstep(.12,.65,d.z);
      }
      c*=mix(vec3(1.),vec3(.23,.31,.51),night);gl_FragColor=vec4(c,1.);
      #include <colorspace_fragment>
    }`,
  }));dome.renderOrder=-120;dome.frustumCulled=false;group.add(dome);
  terrainTiles(group,w,uniforms);
  if(w.vaderland.airfield){
    buildAirport(group,w,uniforms,common,instanced);
    if(!w.vaderland.arrivals)terminalFascia(group,w.obstacles.find(o=>o.id==='airport-rotunda-drum'));
  }else apron(group,w);
  structures(group,w,uniforms);
  let cathedralEast=null;
  const airMarks=w.vaderland.air_trials?buildAirTrialMarkers(group,w.vaderland.air_trials):null;
  const ground=w.vaderland.routes.length?createGround(w,null):null;
  const gardens=w.vaderland.crest_gardens?buildCrestGardens(group,w,ground,uniforms,common):null;
  const market=w.vaderland.quarter?buildMarket(group,w,ground,uniforms,common):null;
  const cityLife=density&&!globalThis.__vtxNoCityLife?buildCityLife(group,w,uniforms,density):null;
  if(cityLife)console.log('city life',JSON.stringify(cityLife.stats));
  const wards=w.vaderland.neighbourhoods?buildNeighbourhoods(group,w,uniforms,common):null;
  const atmosphere=density&&!globalThis.__vtxNoAtmosphere?buildAtmosphere(group,w,density):null;
  const court=w.vaderland.parallax_court?buildParallaxCourt(group,w,ground,uniforms,common):null;
  const room=w.vaderland.instrument_room?buildInstrumentRoom(group,w,uniforms,common):null;
  if(ground){
    roadPaint(group,w,ground,uniforms);
    if(w.vaderland.speedway)buildNightVelocity(group,w,ground,uniforms);
    if(w.vaderland.cathedral)buildCathedral(group,w,ground,uniforms,common);
    if(w.vaderland.meridian_yard)buildMeridianYard(group,w,uniforms,common);
    if(w.vaderland.vertical_loops)buildVerticalLoops(group,w,uniforms,common);
    if(w.vaderland.cathedral_east)cathedralEast=buildCathedralEast(group,w,ground,uniforms,common);
    if(w.vaderland.lantern_marina)buildLanternMarina(group,w,ground,uniforms,common);
  }
  const lanternRace=w.vaderland.lantern_race?buildLanternRace(group,w,uniforms,common,ground):null;
  if(lanternRace){console.log('lantern race',JSON.stringify(lanternRace.stats));resources.push(lanternRace);}
  if(newest){wayfindingLights(group,w);roofPads(group,w);}
  streams(group,w,ground,uniforms);
  if(harbour){
    harbour.routes.visible=false;
    const oldPath=harbour.root.getObjectByName('airport-harbour-walkway');
    if(w.vaderland.airfield && oldPath)oldPath.visible=false;
    if(w.vaderland.landing)dressLanding(group,w,harbour,uniforms,common);
    const marina=w.vaderland.lantern_marina;
    const depthMap=marina?marinaBathymetry(w,ground):null;
    if(marina){
      dressHarbourDecks(harbour,marina.dock_finishes,uniforms,common);
      resources.push(depthMap.marinaDepthMap.value);
    }
    const lanternLights=w.harbour?.timeTrial?w.obstacles.filter(o=>o.role==='race-mark'&&!lanternRaceSolid(o.id)):[];
    const glowUniforms=lanternLights.length?{
      lanternPosition:{value:lanternLights.map(o=>new THREE.Vector3(o.center[0],o.center[1],o.center[2]+o.half[2]-.35))},
      lanternColor:{value:lanternLights.map(o=>new THREE.Color(o.color))},
    }:{};
    const lanternDecl=lanternLights.length?
      'uniform vec3 lanternPosition['+lanternLights.length+'],lanternColor['+lanternLights.length+'];':'';
    const showDisplacement=w.vaderland.surface_detail?.water_displacement;
    const waterVertex=showDisplacement?'varying float surfaceOffset;\n'+vertex.replace(
      'p = positionWorld.xyz;', 'p = positionWorld.xyz;surfaceOffset=position.z;'):vertex;
    harbour.water.material.dispose();
    const depthShader=marina?'uniform sampler2D marinaDepthMap;uniform vec4 marinaDepthArea;':'';
    const raceWater=lanternRace?.water;
    harbour.water.material=new THREE.ShaderMaterial({uniforms:{...uniforms,...glowUniforms,...depthMap,...raceWater?.uniforms},side:THREE.DoubleSide,vertexShader:waterVertex,
      fragmentShader:'uniform sampler2D clouds;uniform sampler2D reliefLight;uniform float clock;uniform float waterClock;uniform float physicalTide;'+lanternDecl+depthShader+(raceWater?raceWater.declarations:'')+(showDisplacement?'varying float surfaceOffset;\n':'')+common+`
      void main(){vec3 v=normalize(cameraPosition-p);
        float ripple=fbm(p.xy*.038+vec2(mix(clock,waterClock,physicalTide)*.15,0.));
        vec3 norm=normalize(vec3(.14*(ripple-.5),.12*(fbm(p.xy*.047)-.5),1.));
        if(physicalTide>.5)norm=normalize(normalize(n)+vec3(norm.xy*.32,0.));${raceWater?raceWater.normal:''}
        vec3 refl=reflect(-v,norm);vec3 skyLight=skySample(clouds,refl);
        float depth=texture2D(reliefLight,p.xy/16000.+.5).b;
        vec3 sea=mix(vec3(.032,.32,.30),vec3(.008,.061,.099),smoothstep(.04,.94,depth));
        sea*=.78+.41*fbm(p.xy*.003);
        float fres=.055+.31*pow(1.-clamp(dot(norm,v),0.,1.),3.);
        if(meridian>.5){
          sea=mix(vec3(.011,.275,.26),vec3(.004,.036,.074),smoothstep(.04,.72,depth));
          float glint=pow(max(0.,dot(refl,normalize(vec3(.87,.47,.11)))),128.);
          sea+=vec3(1.1,.49,.17)*glint*(.20+.9*ripple);
          skyLight=mix(skyLight,skyLight*vec3(.33,.55,.76),.68);fres*=.49;
        }
        vec3 reflections=vec3(0.);
        ${lanternLights.length?`
        if(p.x>420.&&p.x<810.&&p.y>-1350.&&p.y<-1020.){
          vec3 rippled=normalize(norm+vec3((ripple-.5)*.20,(fbm(p.xy*.18)-.5)*.13,0.));
          vec3 reflected=reflect(-v,rippled);
          for(int i=0;i<${lanternLights.length};i++){
            vec3 ray=lanternPosition[i]-p;
            float d2=dot(ray,ray);
            if(d2<2250.){
              float spec=pow(max(0.,dot(reflected,ray*inversesqrt(max(d2,.01)))),76.);
              reflections+=lanternColor[i]*spec*(22./(12.+d2))*mix(.36,1.4,night);
            }
          }
        }`:''}
        vec3 surfaceColor=mix(sea,skyLight,fres)*mix(1.,.34,night)+reflections;
        ${marina?`
        vec2 quayUV=(p.xy-marinaDepthArea.xy)/marinaDepthArea.zw;
        vec2 b=min(quayUV,1.-quayUV);
        if(min(b.x,b.y)>0.){
          float depthM=texture2D(marinaDepthMap,quayUV).r*8.;
          float sand=exp(-depthM*.88);
          float rippleTime=mix(clock,waterClock,physicalTide);
          vec3 chartNormal=normalize(norm+vec3(.022*cos(p.x*2.56+p.y*.33+rippleTime*.84),
                                                .018*sin(p.y*2.12-p.x*.95-rippleTime*.65),0.));
          vec3 localSky=skySample(clouds,reflect(-v,chartNormal));
          float glancing=pow(1.-max(0.,dot(v,chartNormal)),4.25);
          float sediment=fbm(p.xy*.38);
          vec3 bed=mix(vec3(.011,.036,.050),vec3(.078,.151,.134)*(.81+.44*sediment),sand);
          vec3 localSea=mix(bed,localSky,.15+.52*glancing)*mix(1.,.40,night);
          float dissolve=smoothstep(0.,.075,min(b.x,b.y));
          surfaceColor=mix(surfaceColor,localSea+reflections,dissolve*.96);
        }`:''}
        ${raceWater?raceWater.colour:''}
        ${showDisplacement?`
        float nativeSlope=length(normalize(n).xy);
        float raised=smoothstep(.008,.070,surfaceOffset);
        float crests=raised*smoothstep(.012,.075,nativeSlope);
        float trough=smoothstep(.010,.070,-surfaceOffset);
        vec3 reflected=skySample(clouds,reflect(-v,normalize(n)));
        surfaceColor=mix(surfaceColor,reflected*mix(.55,.38,night),
          smoothstep(.013,.10,nativeSlope)*.37);
        surfaceColor*=1.-.20*trough;
        surfaceColor+=vec3(.23,.34,.35)*crests*(.67+.33*ripple);
        `:''}
        gl_FragColor=vec4(haze(surfaceColor),1.);
        #include <colorspace_fragment>
      }`});
    if(w.vaderland.harbour_surface)harbour.setWaterSurface(followTide(harbour.water,w.vaderland.harbour_surface));
    group.add(harbour.root);
  }
  return {ready:Promise.all([ready,court?.ready,gardens?.ready]),cityGlow:!!court,hasDusk:!!w.vaderland.city_lights,update(cam,seconds,mode='day',physicsTime=0,doors,timing,aircraftXY){
    if(disposed)return;
    dome.position.copy(cam.position);uniforms.clock.value=seconds;
    uniforms.blueHour.value=mode==='dusk'&&w.vaderland.city_lights?1:0;
    uniforms.night.value=mode==='night'?1:uniforms.blueHour.value*.65;
    room?.update(physicsTime);
    gardens?.update(cam);
    cathedralEast?.update(timing);
    airMarks?.(timing);
    cityLife?.update(seconds,mode);
    wards?.update(seconds,timing);
    atmosphere?.update(cam,seconds,mode);
    market?.update(cam,physicsTime);optics?.update(mode,cam,physicsTime);departments?.update(physicsTime,doors,timing,aircraftXY);
  }, dispose(){
    disposed=true;scene.fog=previous.fog;camera.far=previous.far;camera.updateProjectionMatrix();
    sky.group.visible=previous.sky;resources.forEach(t=>t.dispose());optics?.dispose();
  }};
}
