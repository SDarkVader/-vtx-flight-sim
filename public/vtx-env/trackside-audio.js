const airportSpeakers = [
  [-3806,-33,2.75,0,.88], [-3784,-38,2.75,1,.74], [-3697,31,2.55,1,.90],
  [-3583,-29,2.55,0,.88], [-3489,30,2.55,1,.80],
].map(([x,y,z,channel,gain])=>({position:[x,y,z],direction:[0,-Math.sign(y)],channel,gain}));
const SPEED_OF_SOUND=343;
const MAX_RANGE=210;

export function tracksideSpeakers(world){
  return world?.vaderland?.cathedral?.west_approach?.speakers ??
    (world?.environment==='airport'?airportSpeakers:null);
}

export function speakerMix(speaker, listener, right, cockpit, tunnel){
  const [x,y,z]=speaker.position;
  const dx=x-listener.x,dy=y-listener.y,dz=z-listener.z;
  const distance=Math.max(1,Math.hypot(dx,dy,dz));
  const dot=-(speaker.direction[0]*dx+speaker.direction[1]*dy)/distance;
  const aim=.54+.46*Math.max(0,dot);
  const edge=Math.max(0,Math.min(1,(MAX_RANGE-distance)/72));
  const falloff=aim*edge*edge/(1+(distance/29)**1.27);
  const occlusion=tunnel*(cockpit?.58:.69);
  return {
    gain:falloff*(speaker.gain??1)*(cockpit?.62:1)*(1-occlusion),
    pan:Math.max(-.86,Math.min(.86,(dx*right.x+dy*right.y+dz*right.z)*.88/distance)),
    delay:Math.min(.70,distance/SPEED_OF_SOUND),
    cutoff:(cockpit?790:4400)/(1+distance/(cockpit?420:175)),
  };
}

export function createTracksideAudio(ctx,output,voicesCount=5){
  const splitter=ctx.createChannelSplitter(2);
  const voices=Array.from({length:voicesCount},()=>{
    const left=ctx.createGain(),right=ctx.createGain();
    const delay=ctx.createDelay(.76),tone=ctx.createBiquadFilter(),balance=ctx.createStereoPanner();
    const main=ctx.createGain(),echo=ctx.createDelay(.09),wet=ctx.createGain();
    tone.type='lowpass';tone.Q.value=.72;main.gain.value=0;
    echo.delayTime.value=.018;wet.gain.value=.23;
    splitter.connect(left,0);splitter.connect(right,1);
    left.connect(delay);right.connect(delay);delay.connect(tone);
    tone.connect(balance);tone.connect(echo);echo.connect(wet);wet.connect(balance);
    balance.connect(main);main.connect(output);
    return {left,right,delay,tone,balance,main,wet,lastDelay:null};
  });
  let player=null, layout=null, settleTimer=null;
  function cease(){
    if(!player)return;
    player.stop();
    player.disconnect();
    player=null;
  }
  return {
    update(buffer,positions,frame,tunnel){
      const active=buffer&&positions;
      if(active){
        clearTimeout(settleTimer);settleTimer=null;
        if(!player){
          player=ctx.createBufferSource();player.buffer=buffer;player.loop=true;player.connect(splitter);
          player.start(ctx.currentTime,ctx.currentTime%buffer.duration);
        }
      }else if(player&&!settleTimer){
        settleTimer=setTimeout(()=>{cease();settleTimer=null;},660);
      }
      const now=ctx.currentTime;
      voices.forEach((v,index)=>{
        const speaker=active?positions[index]:null;
        if(!speaker){
          v.main.gain.setTargetAtTime(0,now,.12);
          v.lastDelay=null;
          return;
        }
        if(layout!==positions){
          v.left.gain.setValueAtTime(speaker.channel===0?1:0,now);
          v.right.gain.setValueAtTime(speaker.channel===1?1:0,now);
        }
        const m=speakerMix(speaker,frame.listener,frame.right,frame.cockpit,tunnel);
        if(v.lastDelay==null||Math.abs(m.delay-v.lastDelay)>.075){
          v.delay.delayTime.cancelScheduledValues(now);
          v.delay.delayTime.setValueAtTime(m.delay,now);
        }else v.delay.delayTime.setTargetAtTime(m.delay,now,.12);
        v.lastDelay=m.delay;
        v.main.gain.setTargetAtTime(m.gain,now,.16);
        v.balance.pan.setTargetAtTime(m.pan,now,.14);
        v.tone.frequency.setTargetAtTime(m.cutoff,now,.19);
        v.wet.gain.setTargetAtTime(.16+.10*tunnel,now,.24);
      });
      layout=positions;
    },
  };
}
