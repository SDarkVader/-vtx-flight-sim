"""Inspect coordinate conversion in the supplied and simulator GLB exports."""
import bpy
import sys
from mathutils import Vector
import statistics

models=[]
for path in sys.argv[sys.argv.index('--')+1:]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    print('FILE',path)
    for o in bpy.data.objects:
        if o.name in ('nacelle1','Phase2_Duct_Lip_Glow_F1'):
            print('OBJECT',o.name,'world',list(o.matrix_world.translation),'local',list(o.location),'parent',o.parent.name if o.parent else None)
    models.append({o.get('blendstra_id'):sum((o.matrix_world@Vector(c) for c in o.bound_box),Vector())/8 for o in bpy.data.objects if o.type=='MESH' and o.get('blendstra_id')})
if len(models)==2:
    distances=sorted(((models[0][k]-models[1][k]).length,k) for k in models[0].keys()&models[1].keys())
    print('MATCHED_BOUNDS_DISTANCE',len(distances),'median',statistics.median(d for d,k in distances),'max',distances[-1])
