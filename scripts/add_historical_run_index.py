from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'src/vtx/live_server.py';s=p.read_text(encoding='utf-8')
anchor="@app.get('/api/runs/{run_id}/findings')"
endpoint='''@app.get('/api/archive/runs')
async def archive_runs():
    """Read legacy PC summary records without writing to their archives."""
    local=os.environ.get('LOCALAPPDATA')
    if not local:
        return dict(records=[],available=False)
    records=[]
    for source in ('r6-live','unified-live'):
        folder=Path(local)/'VTX'/source/'evidence'/'flights'
        for path in sorted(folder.glob('*/summary.json'),reverse=True)[:200]:
            try:
                data=json.loads(path.read_text(encoding='utf-8'))
                records.append(dict(source=source,run_id=data.get('run_id',path.parent.name),
                    recorded_outcome=data.get('outcome'),simulated_seconds=data.get('simulated_seconds'),
                    mission=data.get('mission'),record_status='historical summary; original assessment'))
            except (OSError,ValueError,TypeError):
                continue
    return dict(records=records,available=True)

'''
assert s.count(anchor)==1;s=s.replace(anchor,endpoint+anchor);p.write_text(s,encoding='utf-8',newline='\n')
p=root/'public/app.js';s=p.read_text(encoding='utf-8');anchor=" $('history-dialog').showModal();\n});\n$('open-records')"
replacement=""" try{const archive=await api('/api/archive/runs');const heading=document.createElement('h3');heading.textContent='Historical PC flight summaries (read only)';$('runs').appendChild(heading);if(!archive.records.length){const empty=document.createElement('p');empty.textContent='No historical summaries found in the configured PC archives.';$('runs').appendChild(empty);}for(const r of archive.records){const row=document.createElement('p');row.textContent=`${r.run_id} · ${r.source} · recorded outcome: ${r.recorded_outcome||'unknown'} · ${Number.isFinite(r.simulated_seconds)?r.simulated_seconds.toFixed(1)+' s':'duration unknown'}`;$('runs').appendChild(row);}}catch(e){const notice=document.createElement('p');notice.textContent='Historical archive unavailable: '+e.message;$('runs').appendChild(notice);}
 $('history-dialog').showModal();
});
$('open-records')"""
assert s.count(anchor)==1;s=s.replace(anchor,replacement);p.write_text(s,encoding='utf-8',newline='\n')
