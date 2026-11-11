from pathlib import Path
p=Path(r'C:\Users\steve\Documents\GitHub\-vtx-flight-sim\src\vtx\live_server.py')
s=p.read_text(encoding='utf-8')
import re
blocks=list(re.finditer(r'(?m)^<<<<<<< HEAD\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n',s,re.S|re.M))
assert len(blocks)==6,len(blocks)
def merge(i,a,b):
 if i==0:return a+b
 if i==1:
  return """        departure_check=self.world.validate(MapPoint(*request.departure),'departure')
        if not departure_check.valid:raise ValueError('INVALID_DEPARTURE: '+departure_check.reason)
        target=MapPoint(*request.destination)
        if max(abs(target.x_m),abs(target.y_m))>self.world.half-8:
            raise ValueError('Destination outside surveyed map boundary')
        arrival_check=self.world.validate(target,'destination')
        target_z=self.world.surface_z(*request.destination)
        if phantom_live.is_phantom_variant(request.airframe_variant):
            self.aircraft=phantom_live.make_aircraft(self.world,request)
        else:
            self.aircraft=Aircraft(self.world,request.gear_variant,request.reference_rpm,
"""
 if i==2:return a
 if i==3:return a.replace('def accept_action(self,a:Action):','def accept_action(self,a):')
 if i==4:return a
 if i==5:return a+'\n'+b
for i,m in reversed(list(enumerate(blocks))):
 s=s[:m.start()]+merge(i,m.group(1),m.group(2))+s[m.end():]
import ast
ast.parse(s)
backup=p.with_suffix('.py.pre-restart-conflict-backup')
assert not backup.exists()
backup.write_bytes(p.read_bytes())
p.write_text(s,encoding='utf-8')
print('Resolved six conflict blocks; original backed up:',backup)
