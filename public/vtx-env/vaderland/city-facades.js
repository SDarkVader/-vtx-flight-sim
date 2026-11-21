import * as THREE from 'three';

// These are the established city parcels. The authored civic buildings at V Crest Plaza have their own finishes.
export function avenueParcel(o) {
  const match = /^(market-block-\d+|ward-\d+-\d+-\d+|courtyard-\d+-\d+-\d+)(?:-|$)/.exec(o.id);
  return match?.[1] ?? (o.id.startsWith('courtyard-') ? o.id.replace(/-(?:body|crown)$/, '') : null);
}

export function parcelSeed(id) {
  let value = 2166136261;
  for (let i = 0; i < id.length; i++) value = Math.imul(value ^ id.charCodeAt(i), 16777619);
  return (value >>> 0) / 4294967296;
}

// Real perimeter lengths keep the same width of glazing on a flat elevation and around a rounded corner.
export function wallPerimeter(vertices) {
  const points = vertices.map(([x,y]) => [x,y]).sort((a,b) => a[0]-b[0] || a[1]-b[1]);
  const unique = points.filter((p,i) => !i || p[0]!==points[i-1][0] || p[1]!==points[i-1][1]);
  function chain(seq) {
    const out = [];
    for (const p of seq) {
      while (out.length >= 2) {
        const a=out[out.length-2], b=out[out.length-1];
        if ((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])>1e-8) break;
        out.pop();
      }
      out.push(p);
    }
    out.pop();
    return out;
  }
  const ring = [...chain(unique), ...chain([...unique].reverse())];
  let length=0;
  const edges=ring.map((a,i)=>{
    const b=ring[(i+1)%ring.length], dx=b[0]-a[0],dy=b[1]-a[1], span=Math.hypot(dx,dy);
    const edge={a,dx,dy,span,offset:length};
    length+=span;
    return edge;
  });
  const u=vertices.map(([x,y])=>{
    // Project along the ray from the centre onto the outer footprint of this storey section.
    for (const {a,dx,dy,span,offset} of edges) {
      const det=x*dy-y*dx;
      if (det<=1e-10) continue;
      const t=(a[0]*y-a[1]*x)/det;
      if (t>=-1e-7 && t<=1.0000001) return offset+Math.max(0,Math.min(1,t))*span;
    }
    return 0;
  });
  return {u,length};
}

export function avenueMaterial(uniforms, common) {
  return new THREE.ShaderMaterial({uniforms,side:THREE.DoubleSide,
    vertexShader:`
      attribute vec4 building; attribute vec2 metres; attribute float roofHeight;
      varying vec4 use; varying vec2 wall; varying float top; varying vec3 p,n;
      void main(){
        p=position; n=normal; use=building; wall=metres; top=roofHeight;
        gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);
      }`,
    fragmentShader:common+`
      uniform sampler2D offices,lounge,streetFronts,alloyColor,slateColor,ceramic;
      uniform sampler2D cityDayReflection,cityNightReflection,courtRooms;
      uniform float cityReflectionReady,sceneryClock,courtGlow;
      const float gardenDistrict=${uniforms.gardenDistrict?.value?'1.':'0.'};
      varying vec4 use; varying vec2 wall; varying float top;

      vec3 localReflection(vec3 r,vec3 sky,float z){
        // Photographed from the avenue in this version. The roof elevation and sky take over at high incidence.
        float az=atan(r.y,r.x)/tau+.5;
        float el=asin(clamp(r.z,-1.,1.))/3.14159265+.5;
        vec2 uv=vec2(az,el),dx=dFdx(uv),dy=dFdy(uv);
        dx.x-=floor(dx.x+.5);dy.x-=floor(dy.x+.5);
        vec3 district=mix(textureGrad(cityDayReflection,uv,dx,dy).rgb,
                          textureGrad(cityNightReflection,uv,dx,dy).rgb,night);
        float city=cityReflectionReady*(1.-smoothstep(.12,.75,r.z))*(1.-.77*smoothstep(100.,280.,z));
        return mix(sky,district,city*.9);
      }
      float ribbon(float x,float stepM,float halfWidth) {
        float w=max(.015,min(.8,fwidth(x)));
        float d=abs(fract(x/stepM+.5)-.5)*stepM;
        return (1.-smoothstep(max(0.,halfWidth-w*.5),halfWidth+w*.5,d))*
               (1.-smoothstep(stepM*.35,stepM*.95,fwidth(x)));
      }
      float inset(vec2 st,vec2 mn,vec2 mx,vec2 pitch) {
        vec2 dist=min(st-mn,mx-st)*pitch;
        return min(dist.x,dist.y);
      }
      vec3 shopPhoto(float idx,vec2 uv) {
        vec2 tile=.5*vec2(mod(idx,2.),1.-floor(idx/2.));
        return textureGrad(streetFronts,tile+.006+fract(uv)*.488,dFdx(uv)*.488,dFdy(uv)*.488).rgb;
      }

      void main(){
        vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;
        vec3 V=normalize(cameraPosition-p),R=reflect(-V,N),T=normalize(vec3(-N.y,N.x,.000001));
        float facing=max(.01,dot(N,V)),fres=pow(1.-min(1.,facing),4.);
        float kind=floor(use.x+.5),family=floor(use.y+.5),seed=floor(use.z*4095.+.5)/4095.;
        float direct=max(dot(N,sun),0.),h=wall.y,u=wall.x;
        float nightfall=smoothstep(.01,.91,night);
        float district=gardenDistrict*(1.-smoothstep(370.,1240.,distance(p.xy,vec2(-200.,2210.))));
        float parcel=fract(seed*13.91);
        vec3 enamel=parcel<.20?vec3(.26,.120,.064):parcel<.38?vec3(.113,.239,.204):
                    parcel<.59?vec3(.080,.136,.216):parcel<.83?vec3(.262,.250,.207):vec3(.219,.125,.147);
        vec3 sky=skySample(daySky,R),refl=localReflection(R,sky,p.z);
        float phase=floor(seed*701.);
        float districtMask=courtGlow*(1.-smoothstep(210.,440.,length((p.xy-vec2(28.,2356.))*vec2(1.24,.93))));
        float stripPower=districtMask*nightfall;
        float dark=night*night;
        vec3 signal=seed<.26?vec3(.045,1.04,1.45):seed<.49?vec3(1.65,.53,.095):
                    seed<.73?vec3(.53,.24,1.27):vec3(.97,.19,.43);
        bool roof=N.z>.70 || kind==6.;
        bool shop=kind<.5;
        bool tower=kind==5.;
        bool residence=kind==1.||kind==3.;
        bool brick=kind==3.||(kind==1.&&seed<.53);
        vec3 graphite=mix(vec3(.029,.046,.070),vec3(.064,.106,.117),seed);
        vec3 copper=mix(vec3(.18,.083,.042),vec3(.38,.205,.105),seed);
        vec3 body=brick?mix(vec3(.185,.052,.034),vec3(.28,.118,.065),seed):
                       residence?mix(vec3(.115,.078,.067),vec3(.26,.24,.178),seed):
                       seed<.30?copper:seed<.75?graphite:vec3(.155,.178,.185);
        vec3 light=mix(vec3(.31,.38,.50)+vec3(.92,.74,.54)*direct,
                       vec3(.052,.080,.132)+vec3(.055,.073,.105)*max(0.,N.y*.47+.4),nightfall);
        body=mix(body,enamel,district*mix(.30,.76,step(.38,seed)));
        float metal=texture2D(alloyColor,vec2(u*.39,h*.45)).r;
        float stone=texture2D(slateColor,vec2(u,h)/2.8).r;
        vec3 c;
        if(roof || kind==7.){
          vec2 xy=roof?p.xy:wall;
          float folded=max(ribbon(xy.x,4.25,.035),ribbon(xy.y,7.,.039));
          c=mix(graphite*1.9,copper*.81,step(.82,seed))*(.74+stone*.63)*(1.-folded*.47)*light;
          c+=refl*(.07+.36*fres)+vec3(.015,.019,.031)*nightfall;
        }else{
          float floorH=shop?7.85:tower?3.72:3.48;
          float bayW=shop?3.34:tower?mix(2.55,3.78,seed):residence?mix(3.05,4.15,seed):4.34;
          vec2 pitch=vec2(bayW,floorH);
          vec2 bay=vec2(u+seed*13.,h-(shop?0.:7.85))/pitch;
          vec2 id=floor(bay),st=fract(bay);
          float bank=hash(vec2(floor((id.x+phase)/3.),id.y)+vec2(phase,13.));
          float room=hash(id+vec2(13.2+phase,phase*.73+19.));
          float floorGroup=hash(vec2(floor(id.x/5.),floor(id.y/3.))+vec2(phase,8.3));
          float venue=shop?courtGlow*(1.-smoothstep(100.,152.,length((p.xy-vec2(63.,2370.))*vec2(1.45,1.)))):0.;
          float closed=step(.94,room)*float(residence);
          float pier=(tower?.049:shop?mix(.052,.084,venue):brick?.19:residence?.141:.086)+closed*.13;
          vec2 lo=vec2(pier,tower?.13:shop?.11:residence?.23:.17);
          vec2 hi=vec2(1.-pier,tower?.96:shop?.88:residence?.85:.91);
          float aa=max(.018,min(.70,max(fwidth(u),fwidth(h))*.68));
          float distanceToPane=inset(st,lo,hi,pitch);
          float pane=smoothstep(-aa,aa,distanceToPane);
          float facingT=dot(V,T);
          float depth=shop?mix(.28,.44,venue):tower?.12:brick?.32:.23;
          vec2 recessed=st-vec2(facingT,V.z)*depth/(max(.20,facing)*pitch);
          float back=smoothstep(-aa,aa,inset(recessed,lo,hi,pitch));
          vec2 inside=clamp((recessed-lo)/(hi-lo),vec2(.009),vec2(.991));
          vec2 dU=dFdx(bay)/(hi-lo),dV=dFdy(bay)/(hi-lo);
          // Each pane sees a single photographed room bay. Projected reveals occlude it at an oblique angle.
          vec2 officeTile=floor(vec2(bank,room)*vec2(4.,7.));
          vec3 office=textureGrad(offices,(officeTile+.05+.90*inside)/vec2(4.,7.),
                                 dU*.90/vec2(4.,7.),dV*.90/vec2(4.,7.)).rgb;
          vec2 interiorUV=vec2(fract(id.x*.139+phase*.083)+inside.x*.109,.14+inside.y*.68);
          vec3 suite=textureGrad(lounge,interiorUV,dU*vec2(.109,.68),dV*vec2(.109,.68)).rgb;
          vec3 interior=residence?mix(suite,office,.32):mix(office,suite,.19);
          if(shop)interior=shopPhoto(mod(family+floor(seed*17.),2.),vec2(u/16.7+seed,h/7.85)+
                                     vec2(facingT,V.z)*.014);
          if(venue>.001){
            // A business spans two consecutive panes. Each pane sees an angle into the same interior.
            float column=id.x+phase;
            float tenant=mod(floor(column*.5)+floor(seed*715.)+id.y+family,4.);
            vec2 cell=.5*vec2(mod(tenant,2.),1.-floor(tenant*.5));
            vec2 viewRoom=vec2((mod(column,2.)+inside.x)*.5,inside.y);
            viewRoom=clamp(viewRoom+.068*vec2(-facingT,V.z),vec2(.02),vec2(.98));
            vec3 afterHours=textureGrad(courtRooms,cell+.014+viewRoom*.472,
                                       dU*vec2(.236,.472),dV*vec2(.236,.472)).rgb;
            interior=mix(interior,afterHours,venue);
          }
          float exposure=.61*bank+.25*room+.14*floorGroup;
          // Fewer rooms are occupied away from the busy core (unchanged where occupancy is 1).
          float occupancy=occupancyAt(p.xy);
          // In the v33 night city some whole blocks are dark: closed offices, more of them after dusk.
          float closedBlock=rooftopPass*step(.64-.10*dark,fract(seed*7.31+.17))*float(!shop);
          occupancy*=mix(1.,.22,closedBlock);
          float vacancy=(1.-occupancy)*.38;
          float on=shop?smoothstep(.10+vacancy,.38+vacancy,bank):smoothstep((residence?.40:.39)+vacancy,(residence?.66:.64)+vacancy,exposure);
          // A small number of independent tenancies turn on/off over minutes on the shared simulation clock.
          if(!shop && room>.958){
            float minute=sceneryClock/(143.+77.*bank)+phase*.73;
            float prev=hash(id+floor(minute)+phase),next=hash(id+floor(minute)+phase+1.);
            on*=mix(step(.35,prev),step(.35,next),smoothstep(.95,.987,fract(minute)));
          }
          float level=shop?mix(.070,1.10,smoothstep(.18,.70,bank)):mix(.002,.11+1.08*room,on*on);
          level*=mix(.59,1.48,floorGroup);
          level*=mix(.35,1.,occupancy);
          float bright=shop?max(.2,bank):smoothstep(.66,.84,exposure);
          level*=1.+dark*bright*(shop?.23:1.48);

          vec3 amber=mix(vec3(1.14,.48,.17),vec3(1.28,.79,.43),room);
          vec3 neutral=mix(vec3(.63,.85,1.17),vec3(1.02,.98,.86),room);
          vec3 lamp=shop||residence?mix(amber,neutral,smoothstep(.67,.94,bank)):
                                 mix(neutral,amber,smoothstep(.45,.73,bank+seed*.10));
          lamp=mix(lamp,vec3(.95,.94,1.),venue);
          if(!shop&&!residence)lamp=mix(lamp,mix(neutral,signal,.38),dark*floorGroup*.74);
          vec3 districtLamp=bank<.23?vec3(.53,.92,1.14):bank<.50?vec3(1.25,.59,.32):
                            bank<.72?vec3(1.09,1.02,.78):bank<.88?vec3(.80,1.11,.91):vec3(1.21,.81,.79);
          lamp=mix(lamp,districtLamp,district*nightfall*(.35+.50*floorGroup)*(1.-venue*.4));
          level*=mix(1.,mix(.48,1.22,smoothstep(.33,.74,exposure)),district*.57);
          float blinds=room>.72&&inside.y>1.-(room-.70)*2.45?.40:1.;
          float ceiling=exp(-pow((inside.y-.88)/.13,2.))*(1.-.89*venue);
          float lum=dot(interior,vec3(.2126,.7152,.0722));
          vec3 emitted=(interior*1.85+vec3(.038,.031,.020)+
                        vec3(1.)*ceiling*(.14+.95*lum))*lamp*level*blinds;
          emitted+=lamp*bright*level*(1.-venue*.985)*exp(-pow((inside.y-.84)*16.,2.))*
                   smoothstep(.13,.36,inside.x)*(1.-smoothstep(.63,.85,inside.x))*.85;
          vec3 glassTint=seed<.24?vec3(.35,.57,.58):seed<.69?vec3(.35,.50,.70):vec3(.67,.55,.45);
          vec3 glass=vec3(.002,.004,.008)+refl*glassTint*(.30+.57*fres)*(1.-.40*dark);
          glass+=office*glassTint*(.12+.13*direct)*mix(1.,.30,nightfall)*(1.-venue*.94);
          glass+=emitted*mix(.33,2.25,nightfall)*mix(.27,1.,back)*(1.-.55*fres);
          if(shop){
            vec3 shopDay=interior*(.65+.63*direct)+refl*(.07+.25*fres);
            glass=mix(shopDay,glass+interior*.18,nightfall);
          }
          // Opaque wall, the shadowed reveal and the frame have distinct responses to light.
          float joint=0.;
          if(brick){
            vec2 brickXY=vec2(u/.48+.5*mod(floor(h/.19),2.),h/.19);
            float mx=1.-smoothstep(.016,.052+fwidth(u)*.43,abs(fract(brickXY.x+.5)-.5));
            float my=1.-smoothstep(.03,.084+fwidth(h)*.55,abs(fract(brickXY.y+.5)-.5));
            joint=max(mx,my)*(1.-smoothstep(.075,.29,max(fwidth(u),fwidth(h))));
          }
          vec3 opaque=body*(.76+.34*stone+.16*metal)*light*(1.-.30*joint);
          float sill=ribbon(h-7.85,floorH,.076);
          float vertical=ribbon(u+seed*13.,bayW*(tower?3.:4.),tower?.105:.14);
          opaque=mix(opaque,(graphite*.55+refl*.075)*light+(copper*.31*direct),vertical*.86);
          opaque+=vec3(.097,.082,.069)*sill*(.48+.52*max(0.,N.x));
          float mullion=ribbon(u+seed*13.,bayW,.024);
          float band=ribbon(h-7.85,floorH*(tower?5.:3.),tower?.23:.14);
          opaque=mix(opaque,opaque*(.51+.26*direct)+refl*.071,district*max(mullion*.64,band*.63));
          opaque+=enamel*district*(.11+.23*direct)*band;
          float reveal=1.-smoothstep(0.,depth+.10,-distanceToPane);
          opaque*=1.-.55*reveal*(1.-pane);
          float trim=exp(-abs(distanceToPane+.035)/max(.030,aa*.65));
          opaque+=mix(copper*.27,vec3(.041,.064,.083),float(tower))*trim;
          float spill=exp(-max(0.,-distanceToPane)/(.09+.12*bright))*level*nightfall;
          opaque+=lamp*spill*(.058+.17*bright)*(1.-pane)*(1.-.93*venue);
          // Keep the reveal dark and recover detail in bright rooms before adding the spill.
          float roomGain=shop?mix(.86,1.11,venue):1.34;
          vec3 luminous=glass*roomGain;
          float peak=max(luminous.r,max(luminous.g,luminous.b));
          luminous*=1./(1.+max(.0,peak-.19)*(shop?.91:.42));
          float hotSpill=exp(-max(0.,-distanceToPane)/(.13+.085*bright))*level*stripPower;
          luminous+=lamp*(shop?.063:.18)*bright*ceiling*level*stripPower*(1.-fres);
          opaque+=lamp*(hotSpill*mix(.31,.027,venue))*(1.-pane);
          float metalRim=exp(-abs(distanceToPane+.083)/max(.022,aa*.55));
          opaque=mix(opaque,opaque*.41+refl*.045+vec3(.014,.009,.006)+
                     vec3(.34,.21,.087)*metalRim*.36,venue);
          luminous=mix(luminous,luminous*(.47+.51*back)+refl*(.08+.19*fres),venue);
          glass=mix(glass,luminous,districtMask*nightfall);
          c=mix(opaque,glass,pane);
          float belt=h-(shop?6.63:top-.78);
          float spine=abs(fract((u+seed*4.)/(tower?18.4:32.)+.5)-.5)*(tower?18.4:32.);
          float breaks=smoothstep(.09,.19,fract((u+phase)/7.2));
          vec3 hue=shop?mix(vec3(1.5,.56,.12),vec3(.06,.98,1.35),step(.73,seed)):
            mix(vec3(.085,1.02,1.56),vec3(1.54,.52,.105),step(.48,seed));
          float corona=exp(-abs(belt)*3.8)*.20;
          float beltCore=exp(-abs(belt)*24.)*breaks;
          float spineFade=smoothstep(9.,17.,h)*(1.-smoothstep(top-4.,top-.48,h));
          float spineCore=exp(-spine*22.)*spineFade*float(tower);
          float spineWash=exp(-spine*3.0)*spineFade*float(tower);
          c+=hue*stripPower*(beltCore*.89+corona+spineCore*.86+spineWash*.114);
          float mechanical=ribbon(h-7.85, floorH*(tower?9.:6.),tower?.39:.19);
          c=mix(c,body*.56*light+refl*.09+vec3(.006,.012,.021),mechanical*(shop?.0:.61));
          float rim=1.-smoothstep(.08,.29+aa,abs(h-top+.57));
          if(!shop)c+=mix(copper,vec3(.085,.32,.36),step(.81,seed))*rim*(.27+.44*nightfall);
          if(tower && top>60. && seed>.40){
            float crownLevel=top-3.1-2.*floor(seed*3.);
            float crown=exp(-abs(h-crownLevel)*2.7);
            float strip=ribbon(u+seed*17.,31.+floor(seed*8.),.23);
            float lobby=smoothstep(9.,17.,h)*(1.-smoothstep(top-16.,top-4.,h));
            float liftZ=12.+(.5-.5*cos(tau*(sceneryClock/(46.+seed*52.)+seed)))*max(1.,top-23.);
            float lift=exp(-abs(h-liftZ)*.56)*ribbon(u+seed*17.,31.+floor(seed*8.),.65);
            c+=signal*dark*(crown*1.51+strip*lobby*.44+lift*lobby*1.52);
          }
        }
        gl_FragColor=vec4(haze(c),1.);
        #include <colorspace_fragment>
      }`});
}

export function architecturalMetal(skin,uniforms,common) {
  const index=['city17brass','city17titanium','city17soffit'].indexOf(skin);
  if(index<0)return null;
  return new THREE.ShaderMaterial({uniforms,side:THREE.DoubleSide,
    vertexShader:`varying vec3 p,n;varying vec2 st;
      void main(){vec4 wp=modelMatrix*vec4(position,1.);p=wp.xyz;
        n=normalize(mat3(modelMatrix)*normal);st=uv;gl_Position=projectionMatrix*viewMatrix*wp;}`,
    fragmentShader:'uniform sampler2D alloyColor,alloyNormal,alloyRough;varying vec2 st;'+common+`
      void main(){
        vec3 N=normalize(n);if(!gl_FrontFacing)N=-N;
        vec3 T=abs(N.z)>.9?vec3(1.,0.,0.):normalize(vec3(-N.y,N.x,0.));
        vec3 bump=texture2D(alloyNormal,st).rgb*2.-1.;
        N=normalize(N+.15*(T*bump.x+cross(N,T)*bump.y));
        vec3 V=normalize(cameraPosition-p),R=reflect(-V,N);
        vec3 sky=skySample(daySky,R);
        float grain=texture2D(alloyColor,st).r,rough=texture2D(alloyRough,st).r;
        float grazing=pow(1.-abs(dot(N,V)),2.);
        vec3 tint=${['vec3(.42,.217,.092)','vec3(.29,.36,.415)','vec3(.080,.106,.142)'][index]};
        vec3 moon=normalize(vec3(.47,-.62,.61));
        float key=max(dot(N,sun),0.),fill=max(0.,dot(N,moon));
        float underside=.5-.5*N.z, frontage=.48+.29*N.x-.18*N.y;
        vec3 c=tint*(.56+grain*.49)*(vec3(.25,.31,.43)+vec3(1.26,.85,.47)*key*(1.-.80*night)+.28*fill);
        c+=sky*(.38+.55*grazing)*(1.-.42*rough);
        // Light from the occupied gallery and the recessed rim grazes brushed metal and the underside.
        c+=tint*vec3(.94,.42,.18)*frontage*(.21+.55*underside)*(.50+.50*night);
        c+=vec3(1.30,.73,.32)*pow(max(dot(R,sun),0.),mix(85.,23.,rough));
        c+=vec3(.32,.46,.69)*pow(max(dot(R,moon),0.),mix(62.,16.,rough))*.46;
        gl_FragColor=vec4(haze(c),1.);
        #include <colorspace_fragment>
      }`});
}
