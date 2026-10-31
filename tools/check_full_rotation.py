"""Blender-only sampled housing/frame check for the operator's full rotation.

Run against assets/derived/p0-v4-live.blend. Triangle intersections are
screening evidence only; mesh containment, moving parts, actuator travel,
transmission, deformation and continuous swept clearance are not certified.
"""
import bpy,json,math
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
j=json.loads((ROOT/'evidence/source/airframe_ledger.json').read_text())
objs={o.get('blendstra_id'):o for o in bpy.data.objects if o.type=='MESH'}
def mesh(o,mat):
 return [mat@v.co for v in o.data.vertices],[tuple(p.vertices) for p in o.data.polygons]
vertices=[];faces=[];identities=[]
for p in j['parts']:
 if p['body'] not in ('airframe','cabin') or p['id'] not in objs:continue
 o=objs[p['id']];vs,fs=mesh(o,o.matrix_world);offset=len(vertices);vertices.extend(vs);faces.extend(tuple(i+offset for i in f) for f in fs);identities.extend([p['name']]*len(fs))
fixed=BVHTree.FromPolygons(vertices,faces,all_triangles=True)
results=[]
for i in range(1,5):
 p=next(p for p in j['parts'] if p['body']==f'nacelle{i}' and 'open annular duct' in p['name'].lower())
 o=objs[p['id']];pivot=Vector(j['bodies'][f'nacelle{i}']['pivot_m'])
 for axis in 'XY':
  for angle in range(0,360,30):
   mat=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(angle),4,axis)@Matrix.Translation(-pivot)@o.matrix_world
   vs,fs=mesh(o,mat);moving=BVHTree.FromPolygons(vs,fs,all_triangles=True);hits=moving.overlap(fixed)
   results.append(dict(fan=i,axis=axis,angle_deg=angle,intersections=len(hits),parts=sorted({identities[b] for a,b in hits})[:30]))
# Exploratory placement sensitivity: translate both the pivot and housing up.
# Only the housing is moved; this does not redesign the mounts or drivetrain.
vertical=[]
for dz in [0.5,1.0,1.5,2.0]:
 blocked=0
 for i in range(1,5):
  p=next(p for p in j['parts'] if p['body']==f'nacelle{i}' and 'open annular duct' in p['name'].lower())
  o=objs[p['id']];pivot=Vector(j['bodies'][f'nacelle{i}']['pivot_m']);up=Matrix.Translation(Vector((0,0,dz)))
  for axis in 'XY':
   for angle in range(0,360,30):
    mat=up@Matrix.Translation(pivot)@Matrix.Rotation(math.radians(angle),4,axis)@Matrix.Translation(-pivot)@o.matrix_world
    vs,fs=mesh(o,mat);moving=BVHTree.FromPolygons(vs,fs,all_triangles=True)
    if moving.overlap(fixed):blocked+=1
 vertical.append(dict(pivot_and_housing_raise_m=dz,intersecting_sampled_poses=blocked,total_sampled_poses=96))
out=dict(status='SAMPLED_TRIANGLE_INTERSECTION_SCREEN',coverage='4 housings, X and Y axes, 30-degree steps; source-derived R5 geometry; stationary airframe and cabin only',limitations='Not continuous sweep; no moving fans, transmission, actuator, strength, tolerance or containment validation.',vertical_placement_sensitivity=vertical,results=results)
p=ROOT/'evidence/full_rotation_clearance.json';p.write_text(json.dumps(out,indent=2)+'\n')
print('FULL_ROTATION_SCREEN',len(results),'poses',sum(bool(x['intersections']) for x in results),'poses with intersections')
