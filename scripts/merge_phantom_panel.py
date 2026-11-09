from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
def stage(n): return subprocess.check_output(['git','-C',str(root),'show',f':{n}:public/phantom-controls.js']).decode('utf-8')
a=stage(2); b=stage(3)
start=b.index("    for(const [side,index] of [['Left',0],['Right',1]])")
end=b.index("    el.querySelector('#ph-mode').onchange",start)
anchor="    el.querySelector('#ph-mode').onchange"
assert a.count(anchor)==1
a=a.replace(anchor,b[start:end]+anchor)
a=a.replace("authority:'manual',observation_id:v.observation.observation_id", "authority:'manual',expected_run_id:v.run_id,observation_id:v.observation.observation_id")
(root/'public/phantom-controls.js').write_text(a,encoding='utf-8',newline='\n')
