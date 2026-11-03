// Phantom (phantom-fbw-1) operator panel. Builds the same JSON the AI pilot sends to /api/action.
// No setpoints are invented: the heartbeat re-sends the operator's own current command (< 5 s lease).
const FIELDS=[['collective',0,1,0.01,0],['vertical_speed_m_s',-3,3,0.1,0],['pitch',-1,1,0.02,0],['roll',-1,1,0.02,0],['yaw',-1,1,0.02,0],['engine',0,1,0.05,1]];
export function createPhantomPanel({api,toast}){
  const cmd={schema:'phantom-fbw-1',engine:1,collective:0,vertical_speed_m_s:0,pitch:0,roll:0,yaw:0,stability_mode:'rate_damping'};
  let el=document.getElementById('phantom-panel');
  if(!el){el=document.createElement('section');el.id='phantom-panel';el.className='phantom-panel';
    el.style.cssText='position:fixed;right:16px;bottom:16px;z-index:20;max-width:340px;background:rgba(10,24,32,.92);color:#e8f2f2;padding:12px;border-radius:8px;font:13px system-ui;display:none';
    el.innerHTML='<b>PHANTOM FBW · phantom-fbw-1</b><div id="ph-sliders"></div>'+
      '<label>Mode <select id="ph-mode"><option>rate_damping</option><option>attitude</option><option>attitude_vs</option><option>off</option></select></label> '+
      '<button id="ph-gear">Legs/pods: VTOL</button> <button id="ph-brake">Brakes on</button> <button id="ph-wing">Wing deploy</button> <button id="ph-canard">Canards deploy</button>'+
      '<div id="ph-state" style="margin-top:6px;white-space:pre-wrap;font-family:monospace;font-size:11px"></div>';
    document.body.appendChild(el);
    const s=el.querySelector('#ph-sliders');
    for(const [k,lo,hi,st,v] of FIELDS){const l=document.createElement('label');l.style.display='block';l.innerHTML=`${k} <output>${v}</output><input type=range min=${lo} max=${hi} step=${st} value=${v} style="width:100%">`;
      const i=l.querySelector('input'),o=l.querySelector('output');i.oninput=()=>{cmd[k]=+i.value;o.value=i.value;dirty=true;};s.appendChild(l);}
    el.querySelector('#ph-mode').onchange=e=>{cmd.stability_mode=e.target.value;dirty=true;};
    let vtol=true,brakes=true,wing=false,can=false;
    el.querySelector('#ph-gear').onclick=e=>{vtol=!vtol;cmd.pod_tilt_deg=Array(4).fill(vtol?90:0);cmd.leg_extension_m=Array(4).fill(vtol?.52:0);e.target.textContent='Legs/pods: '+(vtol?'VTOL':'ROAD');dirty=true;};
    el.querySelector('#ph-brake').onclick=e=>{brakes=!brakes;cmd.brake=Array(4).fill(brakes?1:0);e.target.textContent='Brakes '+(brakes?'on':'off');dirty=true;};
    el.querySelector('#ph-wing').onclick=e=>{wing=!wing;cmd.wing=wing?'deploy':'stow';e.target.textContent='Wing '+(wing?'stow':'deploy');dirty=true;};
    el.querySelector('#ph-canard').onclick=e=>{can=!can;cmd.canard_fold=can?'deployed':'folded';e.target.textContent='Canards '+(can?'fold':'deploy');dirty=true;};
  }
  let dirty=true,beat=0,pending=false,lastView=null;
  setInterval(async()=>{const v=lastView;if(pending||!v?.active||v.paused||v.authority!=='manual')return;beat++;if(!(dirty||beat%10===0))return;
    dirty=false;pending=true;try{await api('/api/action',{...cmd,authority:'manual',observation_id:v.observation.observation_id,reason:'Manual Phantom operator controls and command heartbeat'});}
    catch(e){dirty=true;toast(e.message);}finally{pending=false;}},100);
  return {
    show(on){el.style.display=on?'block':'none';},
    update(v){lastView=v;const o=v.observation||{},t=v.rendering_truth||{};
      el.querySelector('#ph-state').textContent=[`t ${o.t_s?.toFixed?.(2)} s · ${v.time_scale}× · lease ${o.lease_remaining_s} s`,
        `variant ${o.configuration?.airframe_variant} ${o.configuration?.load_state||''}`,`radar ${JSON.stringify(o.radar_altitude_m??o.radar_clearance_m)}`,
        `wing ${JSON.stringify(t.phantom?.wing_state)}`,`lamps ${(o.warning_lamps||[]).join(' ')}`].join('\n');},
  };
}
