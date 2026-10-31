"""Blender-only sampled blade/frame interference audit of the derivative.

Triangle overlap is checked at neutral and ±20deg nacelle travel, collective
0/15/30deg and spin increments of 30deg. Discrete coverage is NOT swept,
elastic, tolerance or thermal-growth validation.
"""
import bpy,json,math
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
j=json.loads((ROOT/'evidence/source/airframe_ledger.json').read_text())
objs={o.get('blendstra_id'):o for o in bpy.data.objects if o.type=='MESH'}
parts={p['id']:p for p in j['parts']}
def mesh_world(o,matrix=None):
    mat=matrix or o.matrix_world
    return [mat@v.co for v in o.data.vertices],[tuple(p.vertices) for p in o.data.polygons]
def bvh_for(items):
    vertices=[];faces=[];identities=[]
    for p in items:
        o=objs[p['id']];vs,fs=mesh_world(o);offset=len(vertices)
        vertices.extend(vs);faces.extend([tuple(v+offset for v in f) for f in fs]);identities.extend([p['name']]*len(fs))
    return BVHTree.FromPolygons(vertices,faces,all_triangles=True),identities
frame,frame_ids=bvh_for([p for p in j['parts'] if p['body']=='airframe'])
findings=[];checks=0
for i in range(1,5):
    pivot=Vector(j['bodies'][f'nacelle{i}']['pivot_m']);to=Matrix.Translation(pivot);back=Matrix.Translation(-pivot)
    shaft=Vector(j['bodies'][f'rotor{i}']['pivot_m']);spin_to=Matrix.Translation(shaft);spin_back=Matrix.Translation(-shaft)
    blades=[p for p in j['parts'] if p['body']==f'rotor{i}' and 'blade ' in p['name']]
    fixed,fixed_ids=bvh_for([p for p in j['parts'] if p['body']==f'nacelle{i}'])
    for x in [-20,0,20]:
        for y in [-20,0,20]:
            tilt=to@Matrix.Rotation(math.radians(x),4,'X')@Matrix.Rotation(math.radians(y),4,'Y')@back
            for collective in [0,15,25,30]:
                for spin in range(0,360,30):
                    spinmat=spin_to@Matrix.Rotation(math.radians(spin),4,'Z')@spin_back
                    for p in blades:
                        o=objs[p['id']];axis=Vector(o.get('pitch_axis',[1,0,0]));pitch=spin_to@Matrix.Rotation(math.radians(collective),4,axis)@spin_back
                        verts,faces=mesh_world(o,tilt@spinmat@pitch@o.matrix_world)
                        moving=BVHTree.FromPolygons(verts,faces,all_triangles=True)
                        hits=moving.overlap(frame);checks+=1
                        if hits:
                            findings.append(dict(rotor=i,tilt_deg=[x,y],collective_deg=collective,spin_deg=spin,blade=p['id'],against='airframe',parts=sorted({frame_ids[b] for a,b in hits})))
                        # Nacelle components share the tilt; compare in neutral frame.
                        verts2,faces2=mesh_world(o,spinmat@pitch@o.matrix_world)
                        moving2=BVHTree.FromPolygons(verts2,faces2,all_triangles=True)
                        hits=moving2.overlap(fixed)
                        if hits:
                            findings.append(dict(rotor=i,tilt_deg=[x,y],collective_deg=collective,spin_deg=spin,blade=p['id'],against='nacelle',parts=sorted({fixed_ids[b] for a,b in hits})))
out=dict(revision=j['revision'],status='SAMPLED_TRIANGLE_INTERSECTION_AUDIT',checks=checks,findings=findings,
         coverage='4 rotors × 9 gimbal poses × 4 collectives × 12 spin angles × 4 blades. Not a continuous sweep or strength proof.')
(ROOT/'evidence/clearance_audit.json').write_text(json.dumps(out,indent=2))
print('CLEARANCE_AUDIT',checks,'checks',len(findings),'intersection configurations')
