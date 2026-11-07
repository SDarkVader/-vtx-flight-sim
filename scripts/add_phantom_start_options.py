from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'public/index.html';s=p.read_text(encoding='utf-8')
anchor='<div class="coordinates"><label style="width:100%">INITIAL FUEL'
assert s.count(anchor)==1
s=s.replace(anchor,'<label class="control-label" id="phantom-start-label">PHANTOM START CONFIGURATION<select id="phantom-start"><option value="vtol">Vertical pods / legs extended</option><option value="road">Wheels down / road</option></select></label>'+anchor)
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'public/app.js';s=p.read_text(encoding='utf-8')
needle=" phantomMissionNote.style.display=phantom?'':'none';"
assert s.count(needle)==1
s=s.replace(needle,needle+"\n $('phantom-start-label').style.display=phantom?'':'none';")
needle="label:'Map-selected live ground-to-ground attempt'};if(!phantom)"
assert s.count(needle)==1
s=s.replace(needle,"label:'Map-selected live ground-to-ground attempt'};if(phantom)request.phantom={start_configuration:$('phantom-start').value};if(!phantom)")
s=s.replace("['dep','dest','drive','gear','airframe','initial-fuel'", "['dep','dest','drive','gear','airframe','phantom-start','initial-fuel'")
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'public/phantom-controls.js';s=p.read_text(encoding='utf-8')
s=s.replace('<button id="ph-gear">Legs/pods: VTOL</button>','<button id="ph-gear">Pods: vertical</button> <button id="ph-legs">Legs: extended</button>')
s=s.replace('let vtol=true,brakes=true,wing=false,can=false;','let vtol=true,legsExtended=true,brakes=true,wing=false,can=false;')
old="el.querySelector('#ph-gear').onclick=e=>{engage();vtol=!vtol;cmd.pod_tilt_deg=Array(4).fill(vtol?90:0);cmd.leg_extension_m=Array(4).fill(vtol?.52:0);e.target.textContent='Legs/pods: '+(vtol?'VTOL':'ROAD');dirty=true;};"
new="el.querySelector('#ph-gear').onclick=e=>{engage();vtol=!vtol;cmd.pod_tilt_deg=Array(4).fill(vtol?90:0);e.target.textContent='Pods: '+(vtol?'vertical':'road');dirty=true;};\n    el.querySelector('#ph-legs').onclick=e=>{engage();legsExtended=!legsExtended;cmd.leg_extension_m=Array(4).fill(legsExtended?.52:0);e.target.textContent='Legs: '+(legsExtended?'extended':'retracted');dirty=true;};"
assert s.count(old)==1;s=s.replace(old,new)
s=s.replace("el.querySelector('#ph-gear').textContent='Legs/pods: '+(vtol?'VTOL':'ROAD');", "el.querySelector('#ph-gear').textContent='Pods: '+(vtol?'vertical':'road');")
needle="    update(v){if(engaged&&engagedRun===undefined)"
repl="    update(v){if(!engaged&&v.observation){const o=v.observation;if(Array.isArray(o.pod_tilt_deg)){vtol=o.pod_tilt_deg[0]>45;el.querySelector('#ph-gear').textContent='Pods: '+(vtol?'vertical':'road');}if(Array.isArray(o.leg_extension_m)){legsExtended=o.leg_extension_m[0]>.26;el.querySelector('#ph-legs').textContent='Legs: '+(legsExtended?'extended':'retracted');}}if(engaged&&engagedRun===undefined)"
# State variables are scoped within panel construction; move them to the function scope for update().
s=s.replace('let dirty=false,beat=0,pending=false,lastView=null,engaged=false,engagedRun,voiceReason=null,pendingVoice=null;', 'let dirty=false,beat=0,pending=false,lastView=null,engaged=false,engagedRun,voiceReason=null,pendingVoice=null; let vtol=true,legsExtended=true,brakes=true,wing=false,can=false;')
s=s.replace('    let vtol=true,legsExtended=true,brakes=true,wing=false,can=false;\n','')
assert s.count(needle)==1;s=s.replace(needle,repl)
p.write_text(s,encoding='utf-8',newline='\n')
