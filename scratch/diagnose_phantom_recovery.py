"""Read-only diagnostics for the blocked local Phantom flight checkpoint."""
from pathlib import Path
import difflib
import hashlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from vtx.live_server import Mission, normalize_saved_mission_request
from vtx.world import TestWorld
from vtx.phantom.live import make_aircraft

data = Path(os.environ["LOCALAPPDATA"]) / "VTX" / "unified-live"
state = json.loads((data / "pilot" / "live-flight-checkpoint.json").read_text())
flight = data / "evidence" / "flights" / state["run_id"]
metadata = json.loads((flight / "metadata.json").read_text())
raw = normalize_saved_mission_request(metadata["request"])
if raw.pop("fuel_kg_explicit", True) is False:
    raw.pop("fuel_kg", None)
candidate = make_aircraft(TestWorld(), Mission(**raw))
old_xml = (flight / "model.xml").read_bytes()
new_xml = candidate.xml.encode()
print("RUN",state["run_id"],"TIME",state["plant"]["time"])
print("SAVED",state["model_xml_sha256"],"HASH_ARCHIVE",hashlib.sha256(old_xml).hexdigest())
print("CURRENT",hashlib.sha256(new_xml).hexdigest())
print("XML_LENGTH",len(old_xml),len(new_xml))
for field in ("qpos","qvel","act","ctrl","qacc_warmstart","eq_active"):
    actual=getattr(candidate.data,field)
    print("STATE",field,len(state["plant"][field]),len(actual))
print("CONFIG_SAVED",json.loads((flight/"phantom_parameters.json").read_text()).get("config_sha256"))
print("CONFIG_CURRENT",candidate.P.config_sha256)
print("PARAMETERS_SAVED",json.loads((flight/"phantom_parameters.json").read_text()).keys())
a=old_xml.decode().splitlines()
b=new_xml.decode().splitlines()
for line in list(difflib.unified_diff(a,b,fromfile="saved",tofile="current",n=0))[:42]:
    print("DIFF",line[:220])

import xml.etree.ElementTree as ET
snap=json.loads((flight/"phantom_parameters.json").read_text())["parameters"]
def flat(tree,prefix=""):
    out={}
    for k,v in tree.items():
        p=prefix+"."+k if prefix else k
        if isinstance(v,dict) and "v" not in v:
            out.update(flat(v,p))
        else:
            out[p]=v
    return out
before=flat(snap); after=flat(candidate.P.tree)
changes=[(k,before.get(k,"<MISSING>"),after.get(k,"<MISSING>")) for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
print("PARAMETER_CHANGES",len(changes))
for k,old,new in changes[:25]:
    print("PARAM",k,repr(old)[:120],"=>",repr(new)[:120])
a=ET.fromstring(old_xml); b=ET.fromstring(new_xml)
ET.indent(a);ET.indent(b)
diff=list(difflib.unified_diff(ET.tostring(a,encoding="unicode").splitlines(),ET.tostring(b,encoding="unicode").splitlines(),n=1))
print("XML_DIFF_LINES",len(diff))
for line in diff[:80]: print("XMLDIFF",line[:200])

s=state["plant"]
print("FLIGHT_STATE",json.dumps(dict(sim_time=s["time"],position=s["qpos"][:3],velocity=s["qvel"][:3],
    crashed=s["crashed"],airborne=s["airborne"],fuel=s["fuel"],max_alt=s["max_alt"],
    paused=state["paused"],authority=state["authority"],lease_expired=state["session"]["lease_expired"]),
    default=str))
