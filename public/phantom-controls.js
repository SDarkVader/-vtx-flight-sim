// Phantom (phantom-fbw-1) operator panel. Builds the same JSON the AI pilot sends to /api/action.
// Send operator changes; the runtime holds the last accepted command.
// The panel sends NOTHING until the operator engages it (touches a control or presses "Take control").
// An open browser tab must never silently override another pilot holding the same authority
// (flight campaign D-1). It disengages when the sortie, run or authority changes.
export function heartbeatDue({engaged,pending,view,dirty,beat,engagedRun}){
  if(!engaged||pending||!view?.active||view.paused||view.authority!=='manual')return false;
  if(engagedRun!==undefined&&view.run_id!==engagedRun)return false;
  return dirty;
}
import {parseUtterance,statusReadback,createSpeech,speak} from './voice-pilot.js?v=1';
import {cockpitTelemetry} from './cockpit-telemetry.js?v=1';
const FIELDS=[['collective',0,1,0.01,0],['vertical_speed_m_s',-3,3,0.1,0],['pitch',-1,1,0.02,0],['roll',-1,1,0.02,0],['yaw',-1,1,0.02,0],['engine',0,1,0.05,1]];
export function createPhantomPanel({api,toast}){
  let dirty=false,beat=0,pending=false,lastView=null,engaged=false,engagedRun,voiceReason=null,pendingVoice=null; let vtol=true,legsExtended=true,brakes=true,wing=false,can=false;
  function engage(){if(!engaged){engaged=true;engagedRun=lastView?.run_id;toast?.('Phantom panel has taken manual control');}}
  function disengage(){engaged=false;engagedRun=undefined;dirty=false;}
  const cmd={schema:'phantom-fbw-1',engine:1,collective:0,vertical_speed_m_s:0,pitch:0,roll:0,yaw:0,stability_mode:'rate_damping'};
  let surfaceControls, steerInput;
  let el=document.getElementById('phantom-panel');
  if(!el){el=document.createElement('section');el.id='phantom-panel';el.className='phantom-panel';
    el.style.display='none';
    el.innerHTML='<b id="ph-aircraft">PHANTOM</b><div id="ph-feedback" style="margin:8px 0;font:12px monospace;white-space:pre-line"></div><div id="ph-surface-controls"></div><div id="ph-sliders"></div>'+
      '<label>Mode <select id="ph-mode"><option>rate_damping</option><option>attitude</option><option>attitude_vs</option><option>off</option></select></label> '+
      '<button id="ph-voice" title="Push to talk: boost 50 percent, brakes off, drive 80 percent, take-off configuration, downforce, nose up 8, status, confirm">🎙 Voice</button> <button id="ph-take">Take control</button> <button id="ph-gear">Pods / wheels: 90°</button> <button id="ph-legs">Legs: extended</button> <button id="ph-brake">Brakes on</button> <button id="ph-wing">Wing deploy</button> <button id="ph-canard">Canards deploy</button>'+
      '<input id="ph-say" type="text" placeholder="Type an instruction to the pilot, then Enter" aria-label="Typed pilot instruction" style="width:100%;margin-top:6px">'+
      '<div id="ph-voice-log" style="margin-top:6px;font-size:12px;color:#9fe6d6"></div><div id="ph-state" style="margin-top:6px;white-space:pre-wrap;font-family:monospace;font-size:11px"></div>';
    document.querySelector('.controls-panel').appendChild(el);
    surfaceControls=el.querySelector('#ph-surface-controls');
    const specs=[['Left aileron','aileron_trim_deg',-20,20,0],['Right aileron','aileron_trim_deg',-20,20,1],['Left flap','flap_deg',-5,35,0],['Right flap','flap_deg',-5,35,1],['Left canard','canard_pitch_deg',-20,25,0],['Right canard','canard_pitch_deg',-20,25,1],...['Front left','Front right','Rear left','Rear right'].flatMap((name,i)=>[[name+' wheel drive','wheel_drive',-1,1,i],[name+' brake','brake',0,1,i],[name+' pod tilt','pod_tilt_deg',0,90,i],[name+' leg extension','leg_extension_m',0,.52,i]]),['Left booster throttle','booster_throttle',0,1,0],['Right booster throttle','booster_throttle',0,1,1]];
    for(const [label,field,lo,hi,index] of specs){
      const row=document.createElement('label'); row.style.display='block'; row.textContent=label+' command '; 
      const input=document.createElement('input'); input.type='range'; input.min=lo; input.max=hi; input.step=hi<=1?0.01:1; input.value=0; input.dataset.commandField=field; input.dataset.commandIndex=index; input.style.width='100%'; input.setAttribute('aria-label',label+' command'); row.appendChild(input); if(['aileron_trim_deg','flap_deg','canard_pitch_deg','pod_tilt_deg','leg_extension_m','booster_throttle'].includes(field)){const actual=document.createElement('meter');actual.min=lo;actual.max=hi;actual.value=0;actual.style.width='100%';actual.dataset.actualField=field;actual.dataset.actualIndex=index;actual.setAttribute('aria-label',label+' actual position');row.appendChild(actual);const output=document.createElement('output');output.dataset.actualField=field;output.dataset.actualIndex=index;row.appendChild(output);} surfaceControls.appendChild(row);
      input.onchange=async()=>{const v=lastView;if(!v?.active||v.authority!=='manual')return; const values=[...(v.rendering_truth?.command?.[field]||Array(field==='wheel_drive'||field==='brake'||field==='pod_tilt_deg'||field==='leg_extension_m'?4:2).fill(0))]; values[index]=Number(input.value); try{await api('/api/action',{schema:'phantom-fbw-1',authority:'manual',expected_run_id:v.run_id,reason:'Manual '+label+' control',[field]:values});}catch(e){toast?.(e.message);}};
    }
    const steer=document.createElement('label'); steer.style.display='block'; steer.textContent='Wheel steering / yaw (left −, right +) '; steerInput=document.createElement('input'); steerInput.type='range'; steerInput.min=-1; steerInput.max=1; steerInput.step=.01; steerInput.value=0; steerInput.style.width='100%'; steerInput.setAttribute('aria-label','Wheel steering and yaw'); steer.appendChild(steerInput); const steerActual=document.createElement('output');steerActual.id='ph-steer-actual';steer.appendChild(steerActual); surfaceControls.appendChild(steer);
    steerInput.onchange=async()=>{const v=lastView;if(!v?.active||v.authority!=='manual')return;try{await api('/api/action',{schema:'phantom-fbw-1',authority:'manual',expected_run_id:v.run_id,reason:'Manual wheel steering and yaw',yaw:Number(steerInput.value)});}catch(e){toast?.(e.message);}};
    const note=document.createElement('p'); note.textContent='Wheel steering uses yaw while on the ground. DRS and booster vectoring follow pitch demand; rudder follows yaw demand.'; surfaceControls.appendChild(note);
    const s=el.querySelector('#ph-sliders');
    for(const [k,lo,hi,st,v] of FIELDS){const l=document.createElement('label');l.style.display='block';l.innerHTML=`${k} <output>${v}</output><input type=range min=${lo} max=${hi} step=${st} value=${v} style="width:100%">`;
      const i=l.querySelector('input'),o=l.querySelector('output');i.dataset.liveField=k;i.oninput=()=>{cmd[k]=+i.value;o.value=i.value;engage();dirty=true;};s.appendChild(l);}
    for(const [side,index] of [['Left',0],['Right',1]]){const l=document.createElement('label');l.style.display='block';l.innerHTML=`Front ${side.toLowerCase()} surface <output>0</output> deg <input type=range min=-20 max=25 step=1 value=0 style="width:100%">`;
      const i=l.querySelector('input'),o=l.querySelector('output');i.dataset.liveField='canard_pitch_deg';i.dataset.liveIndex=index;i.oninput=()=>{cmd.canard_pitch_deg=cmd.canard_pitch_deg||[0,0];cmd.canard_pitch_deg[index]=+i.value;o.value=i.value;engage();dirty=true;};s.appendChild(l);}
    el.querySelector('#ph-mode').onchange=e=>{cmd.stability_mode=e.target.value;engage();dirty=true;};
    el.querySelector('#ph-take').onclick=()=>{if(engaged)disengage();else{engage();dirty=true;}};
    el.querySelector('#ph-gear').onclick=e=>{engage();vtol=!vtol;cmd.pod_tilt_deg=Array(4).fill(vtol?90:0);e.target.textContent='Pods / wheels: '+(vtol?'90°':'0°');dirty=true;};
    el.querySelector('#ph-legs').onclick=e=>{engage();legsExtended=!legsExtended;cmd.leg_extension_m=Array(4).fill(legsExtended?.52:0);e.target.textContent='Legs: '+(legsExtended?'extended':'retracted');dirty=true;};
    el.querySelector('#ph-brake').onclick=e=>{engage();brakes=!brakes;cmd.brake=Array(4).fill(brakes?1:0);e.target.textContent='Brakes '+(brakes?'on':'off');dirty=true;};
    el.querySelector('#ph-wing').onclick=e=>{engage();wing=!wing;cmd.wing=wing?'deploy':'stow';e.target.textContent='Wing '+(wing?'stow':'deploy');dirty=true;};
    el.querySelector('#ph-canard').onclick=e=>{engage();can=!can;cmd.canard_fold=can?'deployed':'folded';e.target.textContent='Canards '+(can?'fold':'deploy');dirty=true;};
    // ---- voice pilot: patches this same cmd (same run and authority rules as the sliders)
    const vlog=el.querySelector('#ph-voice-log');
    const syncUi=()=>{for(const l of s.children){const k=l.firstChild.textContent.trim();if(k in cmd){l.querySelector('input').value=cmd[k];l.querySelector('output').value=cmd[k];}}
      el.querySelector('#ph-mode').value=cmd.stability_mode;
      if(cmd.brake){brakes=cmd.brake[0]>0.5;el.querySelector('#ph-brake').textContent='Brakes '+(brakes?'on':'off');}
      if(cmd.wing){wing=cmd.wing==='deploy';el.querySelector('#ph-wing').textContent='Wing '+(wing?'stow':'deploy');}
      if(cmd.canard_fold){can=cmd.canard_fold==='deployed';el.querySelector('#ph-canard').textContent='Canards '+(can?'fold':'deploy');}
      if(cmd.pod_tilt_deg){vtol=cmd.pod_tilt_deg[0]>45;el.querySelector('#ph-gear').textContent='Pods / wheels: '+(vtol?'90°':'0°');}};
    const apply=(r,heard)=>{Object.assign(cmd,JSON.parse(JSON.stringify(r.patch)));engage();dirty=true;voiceReason=`Voice: "${heard}" -> ${r.intent} ${JSON.stringify(r.patch)}`;syncUi();};
    // Local grammar: used only when the server's /api/pilot/command cannot be reached.
    const hearLocal=(text)=>{const r=parseUtterance(text);let reply=r.say;
      if(r.intent==='confirm'){if(pendingVoice&&Date.now()-pendingVoice.t<8000){apply(pendingVoice.r,pendingVoice.heard);reply='Confirmed. '+pendingVoice.r.say.replace(/\?$/,'.');}else reply='Nothing to confirm.';pendingVoice=null;}
      else if(r.intent==='cancel'){reply=pendingVoice?'Cancelled.':'Nothing pending.';pendingVoice=null;}
      else if(r.intent==='status'){reply=statusReadback(lastView);}
      else if(r.patch&&r.risky){pendingVoice={r,heard:text,t:Date.now()};reply=r.say+' Say confirm or cancel.';}
      else if(r.patch){apply(r,text);}
      return reply;};
    // The server interprets the instruction, sends it through /api/action's own checks and answers only after the
    // physics loop holds the command. The reply is spoken; "executed" comes from the plant, never from the parser.
    const hear=async(text,source='voice')=>{const t0=performance.now();let reply,detail='';
      const word=parseUtterance(text).intent;
      try{
        if(word==='cancel'){reply=pendingVoice?'Cancelled.':'Nothing pending.';pendingVoice=null;}
        else if(word==='confirm'&&!(pendingVoice&&Date.now()-pendingVoice.t<8000)){reply='Nothing to confirm.';pendingVoice=null;}
        else{const confirm=word==='confirm';const sent=confirm?pendingVoice.heard:text;pendingVoice=null;
          const r=await api('/api/pilot/command',{text:sent,source,confirm});reply=r.say;
          if(r.needs_confirmation)pendingVoice={heard:sent,t:Date.now(),server:true};
          if(r.executed&&r.patch){Object.assign(cmd,JSON.parse(JSON.stringify(r.patch)));syncUi();}
          detail=r.executed?` · executed, applied in ${r.applied_latency_ms} ms (action ${r.sequence})`:r.accepted?' · accepted, not yet applied':r.rejected?' · rejected':r.needs_confirmation?' · awaiting confirm':'';}
      }catch(e){reply=hearLocal(text);detail=' · server interpreter unavailable, local grammar used';}
      vlog.textContent=`heard: "${text}" → ${reply}${detail} · ${Math.round(performance.now()-t0)} ms`;speak(reply);return reply;};
    // Voice mode: hands-free, continuous listening that stays on (and is remembered) until switched off.
    // The pilot's own spoken replies are not fed back in as commands.
    let quietUntil=0;const speaking=()=>window.speechSynthesis?.speaking||performance.now()<quietUntil;
    const vbtn=el.querySelector('#ph-voice');
    const remember=(on)=>{try{localStorage.setItem('vtx-voice-mode',on?'on':'off');}catch{}};
    const speech=createSpeech({onText:(t)=>{if(speaking()){quietUntil=performance.now()+600;return;}hear(t,'voice');},
      onState:st=>{vbtn.textContent=st==='listening'?'🎙 Voice mode: ON (listening)':'🎙 Voice mode: off';vbtn.setAttribute('aria-pressed',String(st==='listening'));
        if(st.startsWith('error')){vlog.textContent='voice '+st+(st.includes('not-allowed')?' — allow the microphone for this page, then switch voice mode on again':'');if(st.includes('not-allowed')||st.includes('service-not-allowed')){speech.stop();remember(false);}}}});
    vbtn.textContent='🎙 Voice mode: off';
    vbtn.onclick=()=>{if(!speech){vlog.textContent='Voice needs the Web Speech API (Chrome or Edge).';return;}if(speech.listening){speech.stop();remember(false);}else{speech.start();remember(true);}};
    let wanted=false;try{wanted=localStorage.getItem('vtx-voice-mode')==='on';}catch{}
    if(wanted&&speech)speech.start();   // resumes hands-free after a reload when the microphone is already permitted
    window.__phantomVoice=(t)=>hear(t,'text');
    const say=el.querySelector('#ph-say');say.onkeydown=e=>{if(e.key==='Enter'&&say.value.trim()){hear(say.value.trim(),'text');say.value='';}e.stopPropagation();};   // typed fallback / tests: __phantomVoice('boost 50 percent')
  }
  setInterval(async()=>{const v=lastView;beat++;if(!heartbeatDue({engaged,pending,view:v,dirty,beat,engagedRun}))return;
    dirty=false;pending=true;try{await api('/api/action',{...cmd,authority:'manual',expected_run_id:v.run_id,observation_id:v.observation.observation_id,reason:voiceReason||'Manual Phantom operator controls'});voiceReason=null;}
    catch(e){dirty=true;toast(e.message);}finally{pending=false;}},100);
  return {
    show(on){el.style.display=on?'block':'none';},
    update(v){if(!engaged&&v.observation){const o=v.observation;if(Array.isArray(o.pod_tilt_deg)){vtol=o.pod_tilt_deg[0]>45;el.querySelector('#ph-gear').textContent='Pods / wheels: '+(vtol?'90°':'0°');}if(Array.isArray(o.leg_extension_m)){legsExtended=o.leg_extension_m[0]>.26;el.querySelector('#ph-legs').textContent='Legs: '+(legsExtended?'extended':'retracted');}}if(engaged&&engagedRun===undefined)engagedRun=v.run_id;if(engaged&&(!v.active||v.authority!=='manual'||v.run_id!==engagedRun))disengage();lastView=v;const o=v.observation||{},t=v.rendering_truth||{};
      for(const control of el.querySelectorAll('input,button,select'))control.disabled=!v.active&&control.id!=='ph-voice'&&control.id!=='ph-say';
      if(t.command){
        if(!engaged)for(const key of Object.keys(cmd))if(key!=='schema'&&t.command[key]!=null)cmd[key]=structuredClone(t.command[key]);
        if(!dirty&&!pending)for(const input of el.querySelectorAll('[data-live-field]')){const raw=t.command[input.dataset.liveField];const value=input.dataset.liveIndex!=null?raw?.[Number(input.dataset.liveIndex)]:raw;if(value!=null&&document.activeElement!==input){input.value=value;input.parentElement.querySelector('output').value=Number(value).toFixed(2);}}
        if(!dirty&&!pending&&document.activeElement!==el.querySelector('#ph-mode'))el.querySelector('#ph-mode').value=t.command.stability_mode||'rate_damping';
      }
      const fmt=(x)=>x!=null&&Number.isFinite(Number(x))?Number(x).toFixed(1)+'°':'—'; const pair=(x)=>Array.isArray(x)?x.map(fmt).join(' / '):'—'; const truth=t.phantom||{};
      el.querySelector('#ph-aircraft').textContent=(o.configuration?.airframe_variant||'phantom').toUpperCase()+' · LIVE CONTROLS';
      el.querySelector('#ph-feedback').textContent=['COMMAND: collective '+Number(t.command?.collective||0).toFixed(2)+' · pitch '+Number(t.command?.pitch||0).toFixed(2)+' · roll '+Number(t.command?.roll||0).toFixed(2)+' · yaw '+Number(t.command?.yaw||0).toFixed(2)+' · engine '+Number(t.command?.engine||0).toFixed(2)+' · vertical speed '+Number(t.command?.vertical_speed_m_s||0).toFixed(2),'ACTUAL SURFACES  LEFT / RIGHT','Ailerons  '+pair(o.aileron_deg),'Flaps     '+pair(o.flap_deg),'Canards   '+pair(o.canard_pitch_deg),'Canard fold '+pair(o.canard_fold_deg),'DRS '+fmt(truth.drs_deg)+' · booster vector '+fmt(truth.booster_vector_deg),'Rudder '+fmt(truth.rudder_deg),'Wheel steering '+pair(truth.steer_deg),'Wheel speed (rad/s) '+(truth.wheel_rad_s||[]).map(x=>Number(x).toFixed(2)).join(' / '),'Booster spool L/R '+(t.boosters||[]).map(x=>(100*Number(x.spool||0)).toFixed(0)+'%').join(' / '),'Booster thrust L/R '+(t.boosters||[]).map(x=>Number(x.thrust_n||0).toFixed(0)+' N').join(' / '),'Pods '+pair(o.pod_tilt_deg),'Wings '+[o.wing_state?.left||'—',o.wing_state?.right||'—'].join(' / '),'Legs (m) '+(o.leg_extension_m||[]).map(x=>Number(x).toFixed(2)).join(' / ')].join('\n');
      for(const input of surfaceControls.querySelectorAll('[data-command-field]')){const val=t.command?.[input.dataset.commandField]?.[Number(input.dataset.commandIndex)];if(val!=null&&document.activeElement!==input)input.value=val;}
      const actualFields={aileron_trim_deg:o.aileron_deg,flap_deg:o.flap_deg,canard_pitch_deg:o.canard_pitch_deg,pod_tilt_deg:o.pod_tilt_deg,leg_extension_m:o.leg_extension_m,booster_throttle:(t.boosters||[]).map(x=>x.spool)};
      for(const item of surfaceControls.querySelectorAll('[data-actual-field]')){const val=actualFields[item.dataset.actualField]?.[Number(item.dataset.actualIndex)];if(val!=null){if(item.tagName==='METER')item.value=val;else item.textContent='Actual: '+Number(val).toFixed(2)+(item.dataset.actualField==='leg_extension_m'?' m':item.dataset.actualField==='booster_throttle'?' spool':'°');}}
      el.querySelector('#ph-steer-actual').textContent='Actual front steering: '+pair(truth.steer_deg?.slice(0,2));
      if(document.activeElement!==steerInput&&t.command?.yaw!=null)steerInput.value=t.command.yaw;
      const tb=el.querySelector('#ph-take');if(tb)tb.textContent=engaged?'Release control':'Take control';
      el.querySelector('#ph-state').textContent=[!v.active?'Inspection preview: start a mission to enable Phantom controls':engaged?'PANEL ENGAGED: sending manual commands':'panel idle: sends nothing',`t ${o.t_s?.toFixed?.(2)} s · ${v.time_scale}× · commands held`,
        `variant ${o.configuration?.airframe_variant} ${o.configuration?.load_state||''}`,`radar clearance ${cockpitTelemetry(o).altitude} m`,
        `wing ${JSON.stringify(t.phantom?.wing_state)}`,`lamps ${(o.warning_lamps||[]).join(' ')}`].join('\n');},
  };
}
