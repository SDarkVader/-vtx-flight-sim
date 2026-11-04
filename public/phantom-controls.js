// Phantom (phantom-fbw-1) operator panel. Builds the same JSON the AI pilot sends to /api/action.
// No setpoints are invented: the heartbeat re-sends the operator's own current command (< 5 s lease).
// The panel sends NOTHING until the operator engages it (touches a control or presses "Take control").
// An open browser tab must never silently override another pilot holding the same authority
// (flight campaign D-1). It disengages when the sortie, run or authority changes.
export function heartbeatDue({engaged,pending,view,dirty,beat,engagedRun}){
  if(!engaged||pending||!view?.active||view.paused||view.authority!=='manual')return false;
  if(engagedRun!==undefined&&view.run_id!==engagedRun)return false;
  return dirty||beat%10===0;
}
import {parseUtterance,statusReadback,createSpeech,speak} from './voice-pilot.js?v=1';
const FIELDS=[['collective',0,1,0.01,0],['vertical_speed_m_s',-3,3,0.1,0],['pitch',-1,1,0.02,0],['roll',-1,1,0.02,0],['yaw',-1,1,0.02,0],['engine',0,1,0.05,1]];
export function createPhantomPanel({api,toast}){
  let dirty=false,beat=0,pending=false,lastView=null,engaged=false,engagedRun,voiceReason=null,pendingVoice=null;
  function engage(){if(!engaged){engaged=true;engagedRun=lastView?.run_id;toast?.('Phantom panel has taken manual control');}}
  function disengage(){engaged=false;engagedRun=undefined;dirty=false;}
  const cmd={schema:'phantom-fbw-1',engine:1,collective:0,vertical_speed_m_s:0,pitch:0,roll:0,yaw:0,stability_mode:'rate_damping'};
  let el=document.getElementById('phantom-panel');
  if(!el){el=document.createElement('section');el.id='phantom-panel';el.className='phantom-panel';
    el.style.cssText='position:fixed;right:16px;bottom:16px;z-index:20;max-width:340px;background:rgba(10,24,32,.92);color:#e8f2f2;padding:12px;border-radius:8px;font:13px system-ui;display:none';
    el.innerHTML='<b>PHANTOM FBW · phantom-fbw-1</b><div id="ph-sliders"></div>'+
      '<label>Mode <select id="ph-mode"><option>rate_damping</option><option>attitude</option><option>attitude_vs</option><option>off</option></select></label> '+
      '<button id="ph-voice" title="Push to talk: boost 50 percent, brakes off, drive 80 percent, take-off configuration, downforce, nose up 8, status, confirm">🎙 Voice</button> <button id="ph-take">Take control</button> <button id="ph-gear">Legs/pods: VTOL</button> <button id="ph-brake">Brakes on</button> <button id="ph-wing">Wing deploy</button> <button id="ph-canard">Canards deploy</button>'+
      '<div id="ph-voice-log" style="margin-top:6px;font-size:12px;color:#9fe6d6"></div><div id="ph-state" style="margin-top:6px;white-space:pre-wrap;font-family:monospace;font-size:11px"></div>';
    document.body.appendChild(el);
    const s=el.querySelector('#ph-sliders');
    for(const [k,lo,hi,st,v] of FIELDS){const l=document.createElement('label');l.style.display='block';l.innerHTML=`${k} <output>${v}</output><input type=range min=${lo} max=${hi} step=${st} value=${v} style="width:100%">`;
      const i=l.querySelector('input'),o=l.querySelector('output');i.oninput=()=>{cmd[k]=+i.value;o.value=i.value;engage();dirty=true;};s.appendChild(l);}
    el.querySelector('#ph-mode').onchange=e=>{cmd.stability_mode=e.target.value;engage();dirty=true;};
    el.querySelector('#ph-take').onclick=()=>{if(engaged)disengage();else{engage();dirty=true;}};
    let vtol=true,brakes=true,wing=false,can=false;
    el.querySelector('#ph-gear').onclick=e=>{engage();vtol=!vtol;cmd.pod_tilt_deg=Array(4).fill(vtol?90:0);cmd.leg_extension_m=Array(4).fill(vtol?.52:0);e.target.textContent='Legs/pods: '+(vtol?'VTOL':'ROAD');dirty=true;};
    el.querySelector('#ph-brake').onclick=e=>{engage();brakes=!brakes;cmd.brake=Array(4).fill(brakes?1:0);e.target.textContent='Brakes '+(brakes?'on':'off');dirty=true;};
    el.querySelector('#ph-wing').onclick=e=>{engage();wing=!wing;cmd.wing=wing?'deploy':'stow';e.target.textContent='Wing '+(wing?'stow':'deploy');dirty=true;};
    el.querySelector('#ph-canard').onclick=e=>{engage();can=!can;cmd.canard_fold=can?'deployed':'folded';e.target.textContent='Canards '+(can?'fold':'deploy');dirty=true;};
    // ---- voice pilot: patches this same cmd (same heartbeat, lease and authority rules as the sliders)
    const vlog=el.querySelector('#ph-voice-log');
    const syncUi=()=>{for(const l of s.children){const k=l.firstChild.textContent.trim();if(k in cmd){l.querySelector('input').value=cmd[k];l.querySelector('output').value=cmd[k];}}
      el.querySelector('#ph-mode').value=cmd.stability_mode;
      if(cmd.brake){brakes=cmd.brake[0]>0.5;el.querySelector('#ph-brake').textContent='Brakes '+(brakes?'on':'off');}
      if(cmd.wing){wing=cmd.wing==='deploy';el.querySelector('#ph-wing').textContent='Wing '+(wing?'stow':'deploy');}
      if(cmd.canard_fold){can=cmd.canard_fold==='deployed';el.querySelector('#ph-canard').textContent='Canards '+(can?'fold':'deploy');}
      if(cmd.pod_tilt_deg){vtol=cmd.pod_tilt_deg[0]>45;el.querySelector('#ph-gear').textContent='Legs/pods: '+(vtol?'VTOL':'ROAD');}};
    const apply=(r,heard)=>{Object.assign(cmd,JSON.parse(JSON.stringify(r.patch)));engage();dirty=true;voiceReason=`Voice: "${heard}" -> ${r.intent} ${JSON.stringify(r.patch)}`;syncUi();};
    const hear=(text)=>{const r=parseUtterance(text);let reply=r.say;
      if(r.intent==='confirm'){if(pendingVoice&&Date.now()-pendingVoice.t<8000){apply(pendingVoice.r,pendingVoice.heard);reply='Confirmed. '+pendingVoice.r.say.replace(/\?$/,'.');}else reply='Nothing to confirm.';pendingVoice=null;}
      else if(r.intent==='cancel'){reply=pendingVoice?'Cancelled.':'Nothing pending.';pendingVoice=null;}
      else if(r.intent==='status'){reply=statusReadback(lastView);}
      else if(r.patch&&r.risky){pendingVoice={r,heard:text,t:Date.now()};reply=r.say+' Say confirm or cancel.';}
      else if(r.patch){apply(r,text);}
      vlog.textContent=`heard: "${text}" → ${reply}`;speak(reply);};
    const speech=createSpeech({onText:hear,onState:st=>{el.querySelector('#ph-voice').textContent=st==='listening'?'🎙 Listening…':'🎙 Voice';if(st.startsWith('error'))vlog.textContent='voice '+st;}});
    el.querySelector('#ph-voice').onclick=()=>{if(!speech){vlog.textContent='Voice needs the Web Speech API (Chrome or Edge).';return;}speech.listening?speech.stop():speech.start();};
    window.__phantomVoice=hear;   // typed fallback / tests: __phantomVoice('boost 50 percent')
  }
  setInterval(async()=>{const v=lastView;beat++;if(!heartbeatDue({engaged,pending,view:v,dirty,beat,engagedRun}))return;
    dirty=false;pending=true;try{await api('/api/action',{...cmd,authority:'manual',observation_id:v.observation.observation_id,reason:voiceReason||'Manual Phantom operator controls and command heartbeat'});voiceReason=null;}
    catch(e){dirty=true;toast(e.message);}finally{pending=false;}},100);
  return {
    show(on){el.style.display=on?'block':'none';},
    update(v){if(engaged&&engagedRun===undefined)engagedRun=v.run_id;if(engaged&&(!v.active||v.authority!=='manual'||v.run_id!==engagedRun))disengage();lastView=v;const o=v.observation||{},t=v.rendering_truth||{};
      const tb=el.querySelector('#ph-take');if(tb)tb.textContent=engaged?'Release control':'Take control';
      el.querySelector('#ph-state').textContent=[engaged?'PANEL ENGAGED: sending manual commands':'panel idle: sends nothing',`t ${o.t_s?.toFixed?.(2)} s · ${v.time_scale}× · lease ${o.lease_remaining_s} s`,
        `variant ${o.configuration?.airframe_variant} ${o.configuration?.load_state||''}`,`radar ${JSON.stringify(o.radar_altitude_m??o.radar_clearance_m)}`,
        `wing ${JSON.stringify(t.phantom?.wing_state)}`,`lamps ${(o.warning_lamps||[]).join(' ')}`].join('\n');},
  };
}
