"""Build an offline comparison gallery from actual survey camera captures."""
import argparse
import json
from pathlib import Path
from statistics import median


STAGES=[
    ('baseline','Main Airport v6','Original 8 × 8 km airport and its recorded scenery.'),
    ('01-geography','01 · Alpine coast','16 × 16 km terrain, north watershed and southwest Sound.'),
    ('02-city','02 · Meridian City','Northern city terrace, Exchange towers, rotunda and street grid.'),
    ('03-connections','03 · Connections','Two perimeter routes, three supported spans, the gallery and circuit.'),
    ('04-districts','04 · Districts','Localised canyon shelves, courtyard infill and a surveyed urban ground surface.'),
    ('05-meridian','05 · Meridian and Twin Falls','Connected road grades, level bridge bearings and gallery portals, terminal boulevard and dusk materials.')]


def run(root):
    rows=[]
    for folder,title,detail in STAGES:
        stage=root/folder
        survey=json.loads((stage/'survey.json').read_text('utf-8'))
        world=survey['world']
        renderfile=stage/'webgl.json'
        if folder=='baseline' and (stage/'recheck/webgl.json').exists():
            renderfile=stage/'recheck/webgl.json'
        render=json.loads(renderfile.read_text('utf-8'))
        rows.append(dict(folder=folder,title=title,detail=detail,
            views=sorted(p.stem for p in stage.glob('*.jpg')),
            fingerprint=survey['identity']['displayed_world_sha256'],
            half=world['half_m'],terrain=survey['terrain'],gpu=render['results']['panorama']['gpu'],
            timings={v:round(median(c['times']),2) for v,c in render['results'].items()},
            timing=render.get('timing','Original capture timing.'),
            roll_ms=round(survey['performance']['median_ms'],1)))
    table=''.join(f'<tr><th>{r["title"]}</th><td>{r["terrain"]["obstacles"]:,}</td><td>{r["roll_ms"]}</td><td>{r["timings"]["panorama"]}</td><td>{r["timings"]["ground"]}</td><td>{r["timings"]["flight"]}</td></tr>' for r in rows)
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vaderland · Local world review</title>
<style>
:root{color-scheme:dark;font-family:"Segoe UI",sans-serif;background:#0b121b;color:#ecf1f6}*{box-sizing:border-box}body{max-width:1530px;margin:auto;padding:clamp(16px,3vw,50px)}header{display:flex;align-items:end;justify-content:space-between;gap:2em}h1{font:normal clamp(46px,6vw,84px)/1 Georgia,serif;letter-spacing:-.05em;margin:.15em 0 .12em}header p{color:#edc384;margin:0}h2{font:normal 30px Georgia,serif;margin:1em 0 .35em}p,figcaption{color:#bbc8d5;line-height:1.5}select,input{accent-color:#e7b56e}label{display:inline-flex;flex-direction:column;gap:.35em;color:#d4bf9e;font-size:.86em}select{color:white;background:#192531;border:1px solid #485563;border-radius:4px;padding:8px .6em;font-size:1em}
nav{display:flex;flex-wrap:wrap;align-items:end;gap:.8em;margin:20px 0 10px}figure{margin:0}#frame{aspect-ratio:16/9;position:relative;background:#17212d;overflow:hidden;border:1px solid #3c4957;border-radius:6px}#frame img{width:100%;height:100%;object-fit:contain;position:absolute;inset:0}#after{clip-path:inset(0 0 0 0%)}#divider{position:absolute;height:100%;left:0;top:0;width:2px;background:#fbe0a3;pointer-events:none}#wipe{width:100%;margin:12px 0}a{color:#f1c37c}.receipts{display:flex;flex-wrap:wrap;gap:1em}table{border-collapse:collapse;width:100%;font-size:.9em}th,td{text-align:right;border-bottom:1px solid #30404d;padding:9px}th:first-child{text-align:left}.scroll{overflow:auto}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.gallery img{width:100%;border-radius:4px;display:block}.gallery a{text-decoration:none}.gallery figcaption{padding:5px 0}small{color:#b1becb}
</style><header><div><p>Environment review · 18 November 2026</p><h1>Vaderland</h1></div><small>16 × 16 km<br>Meridian and Twin Falls</small></header>
<nav><label>Before<select id="left"></select></label><label>After<select id="right"></select></label><label>Camera<select id="view"></select></label></nav>
<figure><div id="frame"><img id="before" alt="Earlier simulation render"><img id="after" alt="Later simulation render"><div id="divider"></div></div>
<input id="wipe" type="range" min="0" max="100" value="0" aria-label="Reveal earlier view from the left">
<figcaption id="caption"></figcaption></figure><h2>Explore the last survey</h2><div class="gallery" id="gallery"></div>
<h2>Measurements</h2><p>Plant time is median wall milliseconds per simulated second on the stock A10-C runway roll. Scene time is median milliseconds for a 1440 × 810 frame. The three fixed views use the same camera coordinates. The downloaded receipts identify each sampling method.</p>
<div class="scroll"><table><thead><tr><th>World</th><th>Collision solids</th><th>Plant ms</th><th>Aerial ms</th><th>Ground ms</th><th>Flight ms</th></tr></thead><tbody>TABLE</tbody></table></div>
<p class="receipts"><a href="05-meridian/roads.json">Road profiles</a><a href="05-meridian/traversal.json">Vehicle crossings</a><a href="05-meridian/contacts.json">Support and impacts</a><a href="05-meridian/webgl.json">GPU timings</a><a href="05-meridian/survey.json">World identity</a><a href="05-meridian/marine.json">Berth test</a></p>
<script>
const stages=DATA;
const names={panorama:"Aerial",ground:"Ground level",flight:"Aircraft height",terminal:"Terminal frontage",skyline:"Meridian skyline",waterfront:"Sound crossing",pass:"Twin Falls",gallery:"Gallery entrance",street:"Exchange Boulevard",circuit:"Sunset circuit"};
const el=id=>document.getElementById(id);
for(const id of ["left","right"])stages.forEach((s,i)=>el(id).add(new Option(s.title,i)));
el("left").value=4;el("right").value=5;
function setViews(){let a=stages[+el("left").value],b=stages[+el("right").value],old=el("view").value||"flight";el("view").replaceChildren();Object.keys(names).filter(k=>a.views.includes(k)&&b.views.includes(k)).forEach(k=>el("view").add(new Option(names[k],k)));if([...el("view").options].some(x=>x.value===old))el("view").value=old;show();}
function show(){let a=stages[+el("left").value],b=stages[+el("right").value],v=el("view").value;el("before").src=a.folder+"/"+v+".jpg";el("after").src=b.folder+"/"+v+".jpg";el("caption").textContent=names[v]+" · "+b.detail+" Drag the slider right to reveal "+a.title+".";}
for(const id of ["left","right"])el(id).onchange=setViews;el("view").onchange=show;el("wipe").oninput=()=>{let x=el("wipe").value+"%";el("after").style.clipPath="inset(0 0 0 "+x+")";el("divider").style.left=x;};
for(const k of ["terminal","pass","gallery","circuit","skyline","waterfront"]){const f=document.createElement("figure"),a=document.createElement("a"),img=new Image(),c=document.createElement("figcaption");a.href=img.src="05-meridian/"+k+".jpg";img.alt=c.textContent=names[k];a.append(img,c);f.append(a);el("gallery").append(f);}setViews();
</script></html>'''
    (root/'review.html').write_text(html.replace('TABLE',table).replace('DATA',json.dumps(rows)),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    run(parser.parse_args().directory)
