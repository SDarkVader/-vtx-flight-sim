from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'src/vtx/live_server.py';s=p.read_text(encoding='utf-8')
anchor="\ndef read_decision_timeline(path, limit=200):\n"
endpoint='''
@app.get('/api/runs/{run_id}/findings')
async def run_findings(run_id: str):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):
        raise HTTPException(400,'Invalid run ID')
    folder=lab.data_root/'evidence'/'flights'/run_id
    result={}
    for key,filename in (('pilot_summary','pilot_summary.json'),('engineering_findings','engineering_findings.json')):
        path=folder/filename
        if path.is_file():
            result[key]=json.loads(path.read_text(encoding='utf-8'))
    if not result:
        raise HTTPException(404,'No failure summaries recorded for this run')
    return result

'''
assert s.count(anchor)==1
s=s.replace(anchor,'\n'+endpoint+anchor)
if '\nimport re\n' not in s:s=s.replace('import os\n','import os\nimport re\n',1)
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'public/app.js';s=p.read_text(encoding='utf-8')
anchor="  article.append(replayButton,timelineButton,document.createTextNode("
assert s.count(anchor)==1
replacement="""  const findingsButton=document.createElement('button');
  findingsButton.textContent='Pilot summary & engineering findings';
  findingsButton.onclick=guard(async()=>{try{const result=await api('/api/runs/'+encodeURIComponent(r.run_id)+'/findings');const box=$('timeline-events');box.replaceChildren();const detail=document.createElement('pre');detail.textContent=JSON.stringify(result,null,2);detail.style.whiteSpace='pre-wrap';box.appendChild(detail);$('timeline').hidden=false;}catch(e){toast(e.message||'No failure summary for this run.');}});
  article.append(findingsButton);
"""+anchor
s=s.replace(anchor,replacement)
p.write_text(s,encoding='utf-8',newline='\n')
