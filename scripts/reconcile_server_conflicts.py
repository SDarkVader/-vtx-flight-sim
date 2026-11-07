"""One-time, explicit conflict-hunk reconciliation for the isolated worktree."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
pattern=re.compile(r'(?ms)^<<<<<<< HEAD\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n')
def apply(path, fn, count):
    p=root/path; text=p.read_text(encoding='utf-8'); matches=list(pattern.finditer(text))
    assert len(matches)==count,(path,len(matches))
    idx=iter(range(1,count+1))
    out=pattern.sub(lambda m: fn(next(idx),m.group(1),m.group(2)),text)
    assert '<<<<<<< HEAD' not in out
    p.write_text(out,encoding='utf-8',newline='\n')
def server(i,a,b):
    if i in {1,4,5,6,8,12,14,15,16,17}: return b
    if i in {2,3,9,19,20}: return a
    if i==7:
        s=a.replace('self.world.validate','flight_world.validate').replace('self.world.half','flight_world.half').replace('self.world.surface_z','flight_world.surface_z').replace('make_aircraft(self.world,request)','make_aircraft(flight_world,request)').replace('Aircraft(self.world,','Aircraft(flight_world,')
        return "        flight_world=self.world_for(request.ignore_scenery_collisions)\n"+s+"        self.flight_world=flight_world\n"
    if i==10: return a+"        if a.expected_run_id is not None and a.expected_run_id!=self.run_id:\n            raise HTTPException(409,'Flight changed; refresh before sending controls')\n"
    if i==11: return a.split('        row=dict(')[0]+b
    if i==13:return a+b
    if i==18:
        preview=a.split("@app.get('/api/validate')")[0]
        objective=b.split("@app.post('/api/destination')")[0]
        return preview+objective
    raise AssertionError(i)
def phantom(i,a,b):
    if i in {1,2,5,6,7,8}:return a
    if i in {3,4}:return b.replace('enable_a10_surfaces=True','enable_a10_surfaces=False')
    if i==9:return b
    raise AssertionError(i)
apply('src/vtx/live_server.py',server,20)
apply('src/vtx/phantom/live.py',phantom,9)
