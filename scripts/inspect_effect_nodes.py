import json,struct
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'public/assets/phantom-a10-blendstra-81c823e2.glb'
with p.open('rb') as f:
 header=f.read(20); magic,version,total,size,kind=struct.unpack('<4sIIII',header); assert magic==b'glTF' and kind==0x4e4f534a; data=json.loads(f.read(size))
names=[x.get('name','') for x in data.get('nodes',[])]
for category,fragment in [('drs','VTX_VISUAL_DRS_HINGE'),('petal','VTX_VISUAL_BOOSTER_'),('liner','CERAMIC_EXHAUST_LINER'),('wheel','WHEEL')]:
 matches=[n for n in names if fragment in n]
 print(category,len(matches),matches[:6])
print('nodes',len(names),'materials',len(data.get('materials',[])))
