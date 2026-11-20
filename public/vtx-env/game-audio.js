import {createTracksideAudio,tracksideSpeakers} from './trackside-audio.js';

const cueNames=['airport','highlands','meridian','harbour','cathedral','event','trackside'];
const clamp=(x,lo=0,hi=1)=>Math.min(hi,Math.max(lo,x));
const smooth=(x)=>{const a=clamp(x);return a*a*(3-2*a);};
const finite=(value)=>Number.isFinite(value)?value:0;
const distance=(a,b)=>Math.hypot(a.x-b[0],a.y-b[1],a.z-b[2]);

export function acousticScene(world, p, flight={}) {
  const v=world?.vaderland;
  const g=v?.gallery;
  const key=world?.environment;
  const harbour=world?.harbour?.origin;
  const waterfront=harbour&&Math.hypot(p.x-harbour[0],p.y-harbour[1])<560&&p.z<110;
  let tunnel=0,cue=v||key==='sandbox'||key==='r6-valley-20261103'?'highlands':'airport';
  if(g){
    const [a,b]=g.portal_x_m, y=g.center[1];
    const across=g.clear_width_m/2-Math.abs(y-p.y);
    const vertical=Math.min(p.z-g.floor_z_m,g.ceiling_z_m-p.z);
    const along=Math.min(p.x-a,b-p.x);
    tunnel=smooth((along+6)/18)*smooth((across+.6)/1.5)*smooth((vertical+.45)/1.25);
    if(v.cathedral && Math.hypot(Math.min(0,p.x-a,b-p.x),p.y-y)<660)cue='cathedral';
  }
  const city=v?.civic_district?.plaza ?? [-183,2325];
  if(v&&Math.hypot(p.x-city[0],p.y-city[1])<1090)cue='meridian';
  if(v&&Math.hypot(p.x,p.y+145)<690&&!flight.water)cue='airport';
  if(flight.water||waterfront)cue='harbour';
  const courses=[v?.operations?.course,v?.civic_district?.course,v?.speedway?.timing,v?.cathedral?.timing];
  const xy=flight.observation?.gnss_xy_m;
  let event=null;
  if(flight.active && xy){
    for(const course of courses.filter(Boolean)){
      const run=flight.timing?.[course.name];
      if(!Number.isFinite(run?.start)||!Number.isInteger(run.next))continue;
      const finish=course.gates[run.next];
      const begin=course.gates[(run.next+course.gates.length-1)%course.gates.length];
      if(!begin||!finish)continue;
      const coursePoints=course===v.cathedral?.timing?v.cathedral.points:null;
      const [ax,ay]=begin.center,[bx,by]=finish.center, dx=bx-ax,dy=by-ay;
      const q=clamp(((xy[0]-ax)*dx+(xy[1]-ay)*dy)/Math.max(dx*dx+dy*dy,1));
      const proximity=coursePoints
        ? coursePoints.some(([x,y],i)=>i%6===0&&Math.hypot(x-xy[0],y-xy[1])<74)
        : Math.hypot(xy[0]-ax-q*dx,xy[1]-ay-q*dy)<200;
      const altitude=flight.observation.radar_altimeter_m;
      if(proximity&&(!Number.isFinite(altitude)||altitude<7)&&(!event||event.start<run.start)){
        event={name:course.name,start:run.start,gate:run.next};
      }
    }
  }
  return {cue,tunnel,event};
}

function makeAirBuffer(ctx) {
  const n=ctx.sampleRate*4;
  const buffer=ctx.createBuffer(1,n,ctx.sampleRate),data=buffer.getChannelData(0);
  let seed=12027, slow=0;
  for(let i=0;i<n;i++){
    seed=(Math.imul(1664525,seed)+1013904223)>>>0;
    const white=seed/2147483648-1;
    slow=.971*slow+.029*white;
    data[i]=(.52*white+.48*slow)*Math.min(i/800,(n-i)/800,1);
  }
  return buffer;
}

function makeTunnelImpulse(ctx) {
  const buffer=ctx.createBuffer(2,Math.round(ctx.sampleRate*1.05),ctx.sampleRate);
  for(let channel=0;channel<2;channel++){
    const data=buffer.getChannelData(channel);
    const reflections=channel?[.053,.091,.147,.223]:[.041,.082,.161,.239];
    for(const [i,delay] of reflections.entries()){
      const start=Math.round(delay*ctx.sampleRate);
      for(let j=0;j<46;j++)data[start+j]+=(.35/(1+i*.36))*Math.exp(-j/6);
    }
    let seed=43+channel*59, last=0;
    for(let i=Math.round(.058*ctx.sampleRate);i<data.length;i++){
      seed=(Math.imul(1664525,seed)+1013904223)>>>0;
      last=.75*last+.25*(seed/2147483648-1);
      data[i]+=.032*last*Math.exp(-7*i/ctx.sampleRate);
    }
  }
  return buffer;
}

function gain(ctx,to,level=0) {
  const node=ctx.createGain();
  node.gain.value=level;
  node.connect(to);
  return node;
}

function filter(ctx,to,type,hz,q=.71) {
  const node=ctx.createBiquadFilter();
  node.type=type;node.frequency.value=hz;node.Q.value=q;node.connect(to);
  return node;
}

function noiseVoice(ctx,buffer,bus,type,freq,q) {
  const level=gain(ctx,bus), eq=filter(ctx,level,type,freq,q), source=ctx.createBufferSource();
  source.buffer=buffer;source.loop=true;source.connect(eq);source.start(0,(freq/271)%buffer.duration);
  return {eq,level};
}

function motorVoice(ctx,bus) {
  const pan=ctx.createStereoPanner();pan.connect(bus);
  const main=gain(ctx,pan),harmonic=gain(ctx,main,.23);
  const shaft=ctx.createOscillator(),blade=ctx.createOscillator();
  shaft.type='triangle';shaft.frequency.value=60;
  blade.type='sine';blade.frequency.value=432;
  shaft.connect(main);blade.connect(harmonic);shaft.start();blade.start();
  return {pan,main,shaft,blade};
}

const movingJoint=/^(leg_(FL|FR|RL|RR)$|pod_(FL|FR|RL|RR)$|wing_|hatch_|flap_|stab_)/;
const wheelSupport=/^(tyre_|wheel|caster)/i;

function vehicleValues(truth, observation) {
  const p=truth?.phantom;
  const rotors=truth?.rotor_spin_rad_s?.map(x=>Math.abs(x)*60/(2*Math.PI));
  const rpm=p?.fan_rpm??rotors??[];
  const velocity=observation?.velocity_world_m_s;
  const speed=velocity?Math.hypot(...velocity.slice(0,2)):Math.abs(finite(observation?.airspeed_m_s));
  const support=truth?.contact?.support??[];
  const longitudinal=Math.abs(finite(observation?.velocity_body_m_s?.[0]??speed));
  const slip=['FL','FR','RL','RR'].reduce((largest,corner,i)=>{
    const radius=p?.wheel_collision_geometry?.[corner]?.radius_m, omega=p?.wheel_rad_s?.[i];
    if(!support.includes('tyre_'+corner)||!Number.isFinite(radius)||!Number.isFinite(omega))return largest;
    return Math.max(largest,Math.abs(longitudinal-Math.abs(omega)*radius));
  },0);
  return {
    rpm, maxRpm:p?.fan_rpm_max||(rotors?1800:4500), joints:p?.joints||{},
    support,speed,slip,
    air:Math.abs(finite(observation?.airspeed_m_s)),
    thrust:(truth?.boosters??[]).reduce((sum,x)=>sum+Math.max(0,finite(x.thrust_n)),0),
    position:truth?.body_poses?.airframe?.position,
    wings:p?.wing_state,
    time:truth?.t_s,
    valve:finite(p?.transition_ecu?.airbrake_weight),
  };
}

export function createGameAudio(effectsButton, musicButton, reportError=console.warn) {
  let patch=null, initializing=false, effects=false, music=false, timer=-Infinity;
  let loading=null,sleepTimer=null;
  let last=null, selected=null, origin=0, cueVersion=0, previous=null, previousWorld=null, previousGate=null;
  let previousDoors=null, doorLevel=0;
  const ranges=new Map();
  const clips=new Map(), activeClips=new Map();

  function approach(param,value,seconds=.14){
    param.setTargetAtTime(value,patch.ctx.currentTime,seconds);
  }

  function assemble(){
    const Ctx=globalThis.AudioContext??globalThis.webkitAudioContext;
    if(!Ctx)throw Error('This browser has no Web Audio support');
    const ctx=new Ctx({sampleRate:24000}),limit=ctx.createDynamicsCompressor();
    limit.threshold.value=-12;limit.ratio.value=3;limit.connect(ctx.destination);
    const master=gain(ctx,limit,1.14), score=gain(ctx,master), foley=gain(ctx,master);
    const mix=ctx.createGain(), outside=filter(ctx,foley,'lowpass',12000);
    const reverb=ctx.createConvolver();reverb.normalize=false;reverb.buffer=makeTunnelImpulse(ctx);
    const send=gain(ctx,reverb), reflected=filter(ctx,foley,'lowpass',4600);
    reverb.connect(reflected);
    mix.connect(outside);mix.connect(send);
    const cabin=gain(ctx,foley,.69), air=makeAirBuffer(ctx);
    const trackside=createTracksideAudio(ctx,gain(ctx,master,.89));
    const ambience=noiseVoice(ctx,air,mix,'bandpass',470,.43);
    const vent=noiseVoice(ctx,air,mix,'bandpass',157,1.13);
    const road=noiseVoice(ctx,air,mix,'bandpass',335,.76);
    const grip=noiseVoice(ctx,air,mix,'bandpass',1360,2.2);
    const wake=noiseVoice(ctx,air,mix,'bandpass',748,.56);
    const wind=noiseVoice(ctx,air,mix,'bandpass',980,.54);
    const jetBody=noiseVoice(ctx,air,mix,'bandpass',220,.56);
    const jetShear=noiseVoice(ctx,air,mix,'bandpass',1175,.49);
    const servo=noiseVoice(ctx,air,cabin,'bandpass',990,3.0);
    const doors=noiseVoice(ctx,air,mix,'bandpass',295,2.2);
    const fanwash=noiseVoice(ctx,air,mix,'bandpass',590,.57);
    const transistor=noiseVoice(ctx,air,cabin,'bandpass',224,4.6);
    const fans=Array.from({length:4},()=>motorVoice(ctx,mix));
    const neighbours=Array.from({length:4},()=>motorVoice(ctx,mix));
    patch={ctx,score,trackside,foley,mix,outside,send,reflected,cabin,ambience,vent,road,grip,wake,wind,
      jetBody,jetShear,servo,doors,fanwash,transistor,fans,neighbours};
    origin=ctx.currentTime;
  }

  async function preload(){
    const pending=cueNames.map(async name=>{
      const url=new URL('./audio/'+name+'.ogg',import.meta.url);
      const response=await fetch(url);
      if(!response.ok)throw Error('Score audio unavailable for '+name);
      const buffer=await patch.ctx.decodeAudioData(await response.arrayBuffer());
      clips.set(name,buffer);
    });
    const results=await Promise.allSettled(pending);
    if(results.some(x=>x.status==='rejected'))throw Error('Some soundtrack stems could not load');
  }

  function cue(name){
    const buffer=clips.get(name);
    if(!buffer||selected===name)return;
    selected=name;
    const version=++cueVersion, {ctx,score}=patch;
    const at=ctx.currentTime+.025;
    let part=activeClips.get(name);
    if(!part){
      const source=ctx.createBufferSource(), level=gain(ctx,score);
      source.buffer=buffer;source.loop=true;source.connect(level);
      source.start(at,(at-origin)%buffer.duration);
      part={source,level};activeClips.set(name,part);
    }
    for(const [k,stem] of activeClips){
      approach(stem.level.gain,k===name?1:0,k===name?.48:.53);
      if(k!==name)setTimeout(()=>{
        if(version===cueVersion&&selected!==k&&activeClips.get(k)===stem){
          stem.source.stop();stem.level.disconnect();activeClips.delete(k);
        }
      },3200);
    }
  }

  function pulse(kind,strength,bus=patch.mix) {
    if(!strength)return;
    const {ctx}=patch, at=ctx.currentTime+.008;
    const out=gain(ctx,bus), tone=ctx.createOscillator();
    const base=kind==='tyre'?88:kind==='relay'?344:kind==='gate'?582:66;
    const end=kind==='tyre'?.18:kind==='gate'?.30:.12;
    tone.type=kind==='relay'?'triangle':'sine';
    tone.frequency.setValueAtTime(base*1.22,at);
    tone.frequency.exponentialRampToValueAtTime(base,at+end);
    out.gain.setValueAtTime(.0001,at);
    out.gain.linearRampToValueAtTime(strength,at+.011);
    out.gain.exponentialRampToValueAtTime(.0001,at+end);
    tone.connect(out);tone.start(at);tone.stop(at+end+.02);
    tone.onended=()=>out.disconnect();
  }

  function soundMotor(voice,rpm,level,pan,bladeFactor){
    const shaft=Math.max(15,rpm/60);
    approach(voice.shaft.frequency,shaft,.10);
    approach(voice.blade.frequency,shaft*bladeFactor,.11);
    approach(voice.main.gain,level,.15);
    approach(voice.pan.pan,pan,.15);
  }

  function mixFrame(frame){
    const {world,listener,observation,timing,active,cockpit,water}=frame;
    const scene=acousticScene(world,listener,{observation,timing,active,water});
    const inside=scene.tunnel, enclosed=cockpit?1:0;
    const speakers=tracksideSpeakers(world);
    patch.trackside.update(music?clips.get('trackside'):null,speakers,frame,inside);
    if(music&&!speakers){
      cue(scene.event?'event':scene.cue);
      approach(patch.score.gain,scene.event?.40:.30,.24);
    }else{
      approach(patch.score.gain,0,.18);
    }
    if(!effects)return;
    approach(patch.outside.frequency, enclosed?1060:12000-inside*5400,.20);
    approach(patch.reflected.frequency,enclosed?1850:4100,.20);
    approach(patch.send.gain,inside*(enclosed?.28:.66),.22);
    approach(patch.ambience.level.gain,(1-inside*.77)*(enclosed?.042:.091),.27);
    approach(patch.ambience.eq.frequency,({harbour:638,meridian:275,cathedral:376})[scene.cue]??459,.32);
    approach(patch.vent.level.gain,inside*.077,.20);
    approach(patch.transistor.level.gain,enclosed*.035,.25);
    const me=vehicleValues(frame.truth,observation);
    const near=me.position?1/(1+(distance(listener,me.position)/20)**1.35):0;
    for(const [i,voice] of patch.fans.entries()){
      const rpm=finite(me.rpm[i]),power=clamp(rpm/me.maxRpm);
      soundMotor(voice,rpm,near*.056*power**1.73,[ -.315,.315,-.23,.23 ][i],frame.truth?.phantom?7:3);
    }
    const machines=frame.truth?.boosters??[];
    const maxThrust=frame.truth?.phantom?.booster_thrust_max_n;
    const jetLoad=clamp(me.thrust/(Number.isFinite(maxThrust)&&maxThrust>0?2*maxThrust:6000));
    const spool=machines.length?machines.reduce((n,b)=>Math.max(n,finite(b.spool)),0):0;
    approach(patch.fanwash.level.gain,near*.059*me.rpm.reduce((a,b)=>a+clamp(b/me.maxRpm),0)/4,.14);
    approach(patch.jetBody.level.gain,near*.095*jetLoad**.78,.13);
    approach(patch.jetShear.level.gain,near*.073*jetLoad**.83*(.48+.52*clamp(spool)),.14);
    approach(patch.jetBody.eq.frequency,132+143*clamp(spool)+.8*Math.min(me.air,100),.23);
    approach(patch.jetShear.eq.frequency,770+780*clamp(spool)+5*Math.min(me.air,100),.22);
    approach(patch.wind.level.gain,(enclosed?.053:.091)*clamp(me.air/68)**1.22*near,.18);
    approach(patch.road.level.gain,me.support.some(x=>wheelSupport.test(x))?.078*clamp(me.speed/24)*near:0,.14);
    approach(patch.road.eq.frequency,265+Math.min(850,me.speed*13),.18);
    approach(patch.grip.level.gain,.054*near*clamp((me.slip-1.35)/10)*clamp(me.speed/8),.13);
    let doorMoved=false;
    if(previousWorld===world&&previousDoors&&world?.vaderland?.operations){
      for(const [side,x] of [['west',940],['east',1060]]){
        const delta=Math.abs(finite(frame.doors?.[side])-finite(previousDoors[side]));
        if(delta>.0002&&frame.doors?.[side]!=null){
          doorMoved=true;
          const range=distance(listener,[x,-325,18]);
          doorLevel=Math.max(doorLevel,.086*clamp(delta*85)/(1+(range/16)**2));
        }
      }
    }
    if(!doorMoved)doorLevel*=.83;
    approach(patch.doors.level.gain,doorLevel,.13);
    previousDoors=frame.doors;

    const moved=previous?.time!==me.time;
    const continuous=previous && previousWorld===world && moved && me.time>previous.time && me.time-previous.time<.6;
    if(continuous){
      const step=me.time-previous.time;
      let travel=Math.abs(me.valve-previous.valve)*2.5;
      for(const [key,value] of Object.entries(me.joints)){
        if(movingJoint.test(key)&&Number.isFinite(previous.joints[key]))travel+=Math.abs(value-previous.joints[key]);
      }
      approach(patch.servo.level.gain,near*(enclosed?.074:.053)*clamp(travel/step),.09);
      const contacts=me.support.filter(x=>!previous.support.includes(x));
      if(Object.keys(me.wings??{}).some(k=>previous.wings?.[k]&&me.wings[k]!==previous.wings[k]&&['locked','stowed'].includes(me.wings[k]))){
        pulse('relay',near*.072,patch.cabin);
      }
      if(contacts.length && frame.clock-(previous.impactAt??-Infinity)>440){
        const tyres=contacts.some(x=>wheelSupport.test(x));
        pulse(tyres?'tyre':'foot',near*(tyres?.072:.12)*Math.min(1,contacts.length*.5));
        me.impactAt=frame.clock;
      }else me.impactAt=previous.impactAt;
    }else if(moved||frame.clock-(previous?.seenAt??-Infinity)>260){
      approach(patch.servo.level.gain,0,.09);
    }
    if(moved||previousWorld!==world){previous={...me,seenAt:frame.clock};previousWorld=world;}
    const gate=scene.event?scene.event.name+'-'+scene.event.gate+'-'+scene.event.start:null;
    if(gate&&gate!==previousGate)pulse('gate',.064,patch.cabin);
    previousGate=gate;

    const other=(frame.neighbours?.()??[]).map(o=>({...o,range:distance(listener,o.position)}))
      .filter(o=>o.range<310).sort((a,b)=>a.range-b.range);
    let wakeLevel=0;
    for(const [i,voice] of patch.neighbours.entries()){
      const o=other[i];
      if(!o){soundMotor(voice,60,0,0,4);continue;}
      const [x,y,z]=o.position;
      const direction=frame.right;
      const pan=clamp(((x-listener.x)*direction.x+(y-listener.y)*direction.y+(z-listener.z)*direction.z)/Math.max(1,o.range),-.93,.93);
      const falloff=1/(1+(o.range/21)**1.65);
      if(o.type==='boat')wakeLevel+=.106*falloff*clamp(finite(o.speed)/13);
      const occlusion=inside&&o.range>28?.60:1;
      const prior=ranges.get(o.id);
      const radial=prior&&frame.clock-prior.clock<500
        ? clamp((o.range-prior.range)*1000/Math.max(1,frame.clock-prior.clock),-110,110):0;
      ranges.set(o.id,{clock:frame.clock,range:o.range});
      soundMotor(voice,o.rpm*343/(343+radial),falloff*occlusion*o.level,pan,o.type==='boat'?3:5);
    }
    approach(patch.wake.level.gain,Math.min(.13,wakeLevel),.21);
    for(const [id,range] of ranges)if(frame.clock-range.clock>=500)ranges.delete(id);
  }

  async function toggle(channel){
    if(initializing)return;
    const nextEffects=channel==='effects'?!effects:effects;
    const nextMusic=channel==='music'?!music:music;
    initializing=true;
    try{
      clearTimeout(sleepTimer);
      if(nextEffects||nextMusic){
        if(!patch)assemble();
        if(patch.ctx.state!=='running')await patch.ctx.resume();
      }
      effects=nextEffects;music=nextMusic;
      approach(patch.foley.gain,effects?1:0,.085);
      if(!music){
        approach(patch.score.gain,0,.10);
        patch.trackside.update(null,null,last,0);
      }
      if(music&&!loading){
        loading=preload().then(()=>{if(music&&last)mixFrame(last);}).catch(error=>{
          loading=null;reportError(error);
        });
      }
      if((effects||music)&&last)mixFrame(last);
      if(!effects&&!music){
        sleepTimer=setTimeout(()=>{if(!effects&&!music&&!initializing)void patch.ctx.suspend().catch(reportError);},560);
      }
      effectsButton.setAttribute('aria-pressed',String(effects));
      effectsButton.textContent=effects?'Audio on':'Audio off';
      musicButton.setAttribute('aria-pressed',String(music));
      musicButton.textContent=music?'Music on':'Music off';
    }catch(error){reportError(error);}
    finally{initializing=false;}
  }
  effectsButton.addEventListener('click',()=>void toggle('effects'));
  musicButton.addEventListener('click',()=>void toggle('music'));

  return {update(frame){
    if(frame.clock-timer<100)return;
    timer=frame.clock;last=frame;
    if(effects||music)mixFrame(frame);
  }};
}
