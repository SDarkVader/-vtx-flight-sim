from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
pattern=re.compile(r'(?ms)^<<<<<<< HEAD\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n')
def apply(path, count, fn):
 p=root/path; s=p.read_text(encoding='utf-8'); matches=list(pattern.finditer(s)); assert len(matches)==count,(path,len(matches)); index=iter(range(1,count+1)); out=pattern.sub(lambda m:fn(next(index),m.group(1),m.group(2)),s); assert '<<<<<<< HEAD' not in out; p.write_text(out,encoding='utf-8',newline='\n')
def app(i,a,b):
 if i==1:return b.replace("./vtx-env/phantom-look.js?v=2","./vtx-env/phantom-look.js?v=20261106-road-ready-fixed-2-fixed")
 if i in (2,3,6,7):return a
 if i in (4,5):return b
 if i==8:return a.replace("api('/api/destination',{destination:p})","api('/api/destination',{run_id:last.run_id,destination:p})")
 if i==9:
  objective=b[:b.index("$('start').onclick")]
  return objective+a.replace("authority:$('pilot').value,time_scale", "ignore_scenery_collisions:$('ignore-scenery').checked,landing_precision_m:$('landing-precision').value===''?null:Number($('landing-precision').value),authority:$('pilot').value,time_scale")
 if i==10:
  header=b[:b.index(' if(v.rendering_truth?.phantom)')]
  return header+a
 if i==11:
  a=a.replace('if(dirty||manualBeat%10===0)', 'if(dirty)').replace("authority:'manual',observation_id:last.observation.observation_id","authority:'manual',expected_run_id:last.run_id,observation_id:last.observation.observation_id").replace('Manual operator controls and command heartbeat','Manual operator controls').replace('Live connection lost; physical command lease still applies.','Live connection lost; reconnecting. Last accepted controls remain held.')
  return a
 if i==12:return b.replace("truth.provenance.render_asset||", "visualAsset(truth.provenance.render_asset)||")
 if i==13:return a
 raise AssertionError(i)
def html(i,a,b):
 if i==2:return a
 if i!=1:raise AssertionError(i)
 # Preserve checkpoint selector and add the airport's instruments, test options, and pilot objective.
 instrument=b[b.index('<div id="cockpit-frame"'):b.index('<div id="attitude">')]
 a=a.replace('<div id="attitude">',instrument+'<div id="attitude">',1)
 a=a.replace('1,800 × 1,800 m','8,000 × 8,000 m')
 a=a.replace('<label class="control-label">LOWER FRAME', '<label><input id="ignore-scenery" type="checkbox"> Ignore scenery collisions for this flight</label><label class="control-label">LANDING PRECISION / m (OPTIONAL)<input id="landing-precision" type="number" min="0.01" step="any" placeholder="Not specified"></label><p id="landing-evidence" class="muted small">No landing recorded yet.</p><label class="control-label">LOWER FRAME',1)
 start=b.index('<div class="section-label decisions-label">03 / PILOT OBJECTIVE')
 end=b.index('<div class="section-label decisions-label">04 / OBSERVATION',start)
 a=a.replace('<div class="section-label decisions-label">03 / OBSERVATION',b[start:end]+'<div class="section-label decisions-label">03 / OBSERVATION',1)
 return a
apply('public/app.js',13,app)
apply('public/index.html',2,html)
