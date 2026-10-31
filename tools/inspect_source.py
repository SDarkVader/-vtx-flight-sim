"""Run with Blender: extract source evidence without modifying the master."""
import bpy
import json
from pathlib import Path
from mathutils import Vector

OUT = Path('/workspace/vtx-flight-sim/evidence/source')
OUT.mkdir(parents=True, exist_ok=True)
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()

def safe(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if hasattr(v, 'to_list'):
        return v.to_list()
    try:
        return list(v)
    except TypeError:
        return str(v)

objects = []
for o in bpy.data.objects:
    d = dict(name=o.name, type=o.type, id=o.get('blendstra_id'),
             parent=o.parent.name if o.parent else None,
             matrix=[list(row) for row in o.matrix_world],
             location=list(o.matrix_world.translation),
             dimensions=list(o.dimensions),
             props={k:safe(v) for k,v in o.items()},
             materials=[m.name for m in getattr(o.data, 'materials', []) if m])
    if o.type == 'MESH':
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        d['vertices'] = len(pts)
        d['bounds'] = [[min(p[i] for p in pts) for i in range(3)],
                       [max(p[i] for p in pts) for i in range(3)]] if pts else None
        d['vertex_centroid'] = [sum(p[i] for p in pts)/len(pts) for i in range(3)] if pts else None
    objects.append(d)
result = dict(blender=bpy.app.version_string,
              unit_scale=bpy.context.scene.unit_settings.scale_length,
              frame=1, fps=bpy.context.scene.render.fps,
              frame_range=[bpy.context.scene.frame_start,bpy.context.scene.frame_end],
              objects=objects,
              texts={t.name:t.as_string() for t in bpy.data.texts})
(OUT/'native_inventory.json').write_text(json.dumps(result, indent=2))
print('SOURCE_INVENTORY',len(objects),'objects',len(result['texts']),'text blocks')
for o in objects:
    if o['type']=='EMPTY' or any(s in o['name'].lower() for s in ['blade','tank','fuel','pad','tilt','shaft','cabin']):
        print(o['name'],o['location'],o['dimensions'],o['props'])
