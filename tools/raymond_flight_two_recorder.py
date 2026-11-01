"""Flight Two evidence watcher. Observation only; no autonomous piloting."""
import json,time,urllib.request,subprocess,datetime,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:8765"
OUT=ROOT/"evidence"/"raymond-flight-two"
OUT.mkdir(parents=True,exist_ok=True)
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=8) as r:return json.load(r)
def record(name,obj):
    with (OUT/name).open("a",encoding="utf-8") as f:
        f.write(json.dumps(obj,default=str,ensure_ascii=False)+"\n")
start=time.monotonic()
last_run=None
for i in range(2400):
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        v=get("/api/observe")
        record("observations.jsonl",{"utc":now,"data":v})
        if i%10==0:
            view=get("/api/view")
            record("view_snapshots.jsonl",{"utc":now,"run_id":view.get("run_id"),"mode":view.get("mode"),"active":view.get("active"),"observation":view.get("observation")})
            last_run=view.get("run_id")
    except Exception as e:record("errors.jsonl",{"utc":now,"error":repr(e)})
    if i%60==0:
        (OUT/"heartbeat.json").write_text(json.dumps({"utc":now,"sample":i,"run_id":last_run},indent=2))
    time.sleep(1)
(OUT/"completed.txt").write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())

