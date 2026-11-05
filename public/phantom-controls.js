// Phantom (phantom-fbw-1) operator panel. Builds the same JSON the AI pilot sends to /api/action.
// Send only operator changes; the server holds the last accepted command.
// The panel sends NOTHING until the operator engages it (touches a control or presses "Take control").
// An open browser tab must never silently override another pilot holding the same authority
// (flight campaign D-1). It disengages when the sortie, run or authority changes.
export function heartbeatDue({engaged,pending,view,dirty,engagedRun}){
  if(!engaged||pending||!view?.active||view.paused||view.authority!=='manual')return false;
  if(engagedRun!==undefined&&view.run_id!==engagedRun)return false;
  return dirty;
}
const FIELDS=[['collective',0,1,0.01,0],['vertical_speed_m_s',-3,3,0.1,0],['pitch',-1,1,0.02,0],['roll',-1,1,0.02,0],['yaw',-1,1,0.02,0],['engine',0,1,0.05,1]];
export function createPhantomPanel({api,toast}){
  let dirty=false,pending=false,lastView=null,engaged=false,engagedRun;
  function engage(){if(!engaged){engaged=true;engagedRun=lastView?.run_id;toast?.('Phantom panel has taken manual control');}}
  function disengage(){engaged=false;engagedRun=undefined;dirty=false;}
  const cmd={schema:'phantom-fbw-1',engine:1,collective:0,vertical_speed_m_s:0,pitch:0,roll:0,yaw:0,stability_mode:'rate_damping'};
  let el=document.getElementById('phantom-panel');
  if(!el){el=document.createElement('section');el.id='phantom-panel';el.className='phantom-panel';
    el.style.cssText='position:relative;max-width:100%;background:rgba(10,24,32,.92);color:#e8f2f2;padding:12px;border-radius:8px;font:13px system-ui;display:none';
    el.innerHTML='<b>PHANTOM FBW · phantom-fbw-1</b><div id="ph-sliders"></div>'+
      '<label>Mode <select id="ph-mode"><option>rate_damping</option><option>attitude</option><option>attitude_vs</option><option>off</option></select></label> '+
      '<button id="ph-take">Take control</button> <button id="ph-gear">Legs/pods: VTOL</button> <button id="ph-brake">Brakes on</button> <button id="ph-wing">Wing deploy</button> <button id="ph-canard">Canards deploy</button>'+
      '<div id="ph-state" style="margin-top:6px;white-space:pre-wrap;font-family:monospace;font-size:11px"></div>';
    (document.querySelector('.controls-panel') || document.body).prepend(el);
    const s=el.querySelector('#ph-sliders');
    for(const [k,lo,hi,st,v] of FIELDS){const l=document.createElement('label');l.style.display='block';l.innerHTML=`${k} <output>${v}</output><input type=range min=${lo} max=${hi} step=${st} value=${v} style="width:100%">`;
      const i=l.querySelector('input'),o=l.querySelector('output');i.oninput=()=>{cmd[k]=+i.value;o.value=i.value;engage();dirty=true;};s.appendChild(l);}
    for(const [side,index] of [['Left',0],['Right',1]]){const l=document.createElement('label');l.style.display='block';l.innerHTML=`Front ${side.toLowerCase()} surface <output>0</output> deg <input type=range min=-20 max=25 step=1 value=0 style="width:100%">`;
      const i=l.querySelector('input'),o=l.querySelector('output');i.oninput=()=>{cmd.canard_pitch_deg=cmd.canard_pitch_deg||[0,0];cmd.canard_pitch_deg[index]=+i.value;o.value=i.value;engage();dirty=true;};s.appendChild(l);}
    el.querySelector('#ph-mode').onchange=e=>{cmd.stability_mode=e.target.value;engage();dirty=true;};
    el.querySelector('#ph-take').onclick=()=>{if(engaged)disengage();else{engage();dirty=true;}};
    let vtol=true,brakes=true,wing=false,can=true;
    el.querySelector('#ph-canard').textContent='Canards fold';
    el.querySelector('#ph-gear').onclick=e=>{engage();vtol=!vtol;cmd.pod_tilt_deg=Array(4).fill(vtol?90:0);cmd.leg_extension_m=Array(4).fill(vtol?.52:0);e.target.textContent='Legs/pods: '+(vtol?'VTOL':'ROAD');dirty=true;};
    el.querySelector('#ph-brake').onclick=e=>{engage();brakes=!brakes;cmd.brake=Array(4).fill(brakes?1:0);e.target.textContent='Brakes '+(brakes?'on':'off');dirty=true;};
    el.querySelector('#ph-wing').onclick=e=>{engage();wing=!wing;cmd.wing=wing?'deploy':'stow';e.target.textContent='Wing '+(wing?'stow':'deploy');dirty=true;};
    el.querySelector('#ph-canard').onclick=e=>{engage();can=!can;cmd.canard_fold=can?'deployed':'folded';e.target.textContent='Canards '+(can?'fold':'deploy');dirty=true;};
  }
  setInterval(async()=>{const v=lastView;if(!heartbeatDue({engaged,pending,view:v,dirty,engagedRun}))return;
    dirty=false;pending=true;try{await api('/api/action',{...cmd,authority:'manual',observation_id:v.observation.observation_id,reason:'Manual Phantom operator controls'});}
    catch(e){dirty=true;toast(e.message);}finally{pending=false;}},100);
  return {
    show(on){el.style.display=on?'block':'none';},
    update(v){if(engaged&&engagedRun===undefined)engagedRun=v.run_id;if(engaged&&(!v.active||v.authority!=='manual'||v.run_id!==engagedRun))disengage();lastView=v;const o=v.observation||{},t=v.rendering_truth||{};
      const tb=el.querySelector('#ph-take');if(tb)tb.textContent=engaged?'Release control':'Take control';
      el.querySelector('#ph-state').textContent=[engaged?'PANEL ENGAGED: manual controls':'panel idle: sends nothing',`t ${o.t_s?.toFixed?.(2)} s · ${v.time_scale}× · commands held`,
        `variant ${o.configuration?.airframe_variant} ${o.configuration?.load_state||''}`,`radar ${JSON.stringify(o.radar_altitude_m??o.radar_clearance_m)}`,
        `wing ${JSON.stringify(t.phantom?.wing_state)}`,`front L/R ${[t.phantom?.joints?.canard_left,t.phantom?.joints?.canard_right].map(x=>x==null?'-':(x*180/Math.PI).toFixed(1)).join(' / ')} deg | DRS ${t.phantom?.drs_deg?.toFixed?.(1)??'-'} deg`,`lamps ${(o.warning_lamps||[]).join(' ')}`].join('\n');},
  };
}
