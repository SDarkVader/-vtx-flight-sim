import json,struct
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'public/assets/phantom-a10-blendstra-81c823e2.glb'
with p.open('rb') as f:
 h=f.read(20); _,_,_,n,_=struct.unpack('<4sIIII',h); j=json.loads(f.read(n))
for i,node in enumerate(j['nodes']):
 name=node.get('name',''); extra=node.get('extras',{})
 if 'phantom_joint' in extra or '_CORE_GLOW' in name or ('WHEEL' in name and ('JOINT' in name or 'HUB' in name or 'TIRE' in name or 'TYRE' in name)):
  print(i,name,str(extra)[:400], 'children', node.get('children',[])[:8])
