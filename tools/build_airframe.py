"""Blender-only, reproducible geometry → mass ledger and live GLB derivative.

The master is never saved/overwritten. Mass is allocated by uniform surface
density WITHIN each P01–P11 budget: an explicit distribution hypothesis, not CAD
material mass. Triangle integrals give centroids and full inertia, not guessed CG.
"""
import bpy
import json
import math
import re
from pathlib import Path
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
deps = bpy.context.evaluated_depsgraph_get()
objects = list(bpy.data.objects)
byname = {o.name:o for o in objects}
groups = {'airframe': np.zeros(3), 'cabin':np.array([0.,0.,1.56])}
pivots = []
for i in range(1,5):
    p = np.array(byname[f'V3 P02 | F{i} INNER vector axis Y'].matrix_world.translation)
    pivots.append(p)
    groups[f'nacelle{i}'] = p
    groups[f'rotor{i}'] = p
for i in range(1,7):
    groups[f'gear{i}'] = np.array(byname[f'V4 P10 | LANDING leg{i} replaceable contact foot'].matrix_world.translation)

def subsystem(o):
    a = o
    while a:
        if a.get('VTX_ID'):return a['VTX_ID']
        a = a.parent
    # A few cockpit pieces were reparented outside their P08 assembly.
    match = re.search(r'P(\d\d)', o.name)
    return 'P'+match.group(1) if match else None

def body_for(o):
    m = re.search(r'LANDING leg(\d)',o.name)
    if m and ('contact foot' in o.name or 'sliding piston' in o.name):return 'gear'+m.group(1)
    m = re.search(r'F(\d) radial drive shaft',o.name)
    if m:
        k='shaft'+m.group(1)
        groups[k]=np.array(o.matrix_world.translation)
        return k
    a=o
    while a:
        m=re.search(r'F(\d) rotor rotation shaft',a.name)
        if m:return 'rotor'+m.group(1)
        m=re.search(r'F(\d) INNER vector axis',a.name)
        if m:return 'nacelle'+m.group(1)
        if 'passenger cabin compensated' in a.name:return 'cabin'
        a=a.parent
    return 'airframe'

parts=[]; excluded=[]; source_meshes={}; blade_geometry=[]
for o in objects:
    if o.type!='MESH':continue
    sys=subsystem(o)
    if sys is None or 'wake' in o.name.lower():
        excluded.append({'name':o.name,'reason':'nonmechanical presentation/wake geometry'})
        continue
    group=body_for(o)
    ev=o.evaluated_get(deps)
    mesh=ev.to_mesh()
    mesh.calc_loop_triangles()
    verts=np.array([list(o.matrix_world @ v.co) for v in mesh.vertices],dtype=float)
    faces=np.array([list(t.vertices) for t in mesh.loop_triangles],dtype=int)
    tris=verts[faces]
    area=.5*np.linalg.norm(np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]),axis=1)
    total=float(area.sum())
    if total<1e-10:
        ev.to_mesh_clear();continue
    center=np.einsum('t,tij->j',area,tris)/(3*total)
    sums=tris.sum(axis=1)
    second=(np.einsum('t,tki,tkj->ij',area,tris,tris)+np.einsum('t,ti,tj->ij',area,sums,sums))/(12*total)
    cov=second-np.outer(center,center)
    per_mass=np.eye(3)*np.trace(cov)-cov
    rot=np.array(o.matrix_world.to_quaternion().to_matrix())
    local=verts@rot
    lo=local.min(axis=0);hi=local.max(axis=0)
    d=dict(name=o.name,id=o.get('blendstra_id'),subsystem=sys,body=group,
           area_m2=total,centroid_m=center.tolist(),inertia_per_kg_m2=per_mass.tolist(),
           bounds_m=[verts.min(axis=0).tolist(),verts.max(axis=0).tolist()],
           obb_center_m=(rot@((lo+hi)/2)).tolist(),obb_half_m=((hi-lo)/2).tolist(),
           obb_rotation=rot.tolist(),materials=[m.name for m in mesh.materials if m],
           status='CALCULATED_FROM_GEOMETRY_AND_PROVISIONAL_SUBSYSTEM_ALLOCATION',
           distribution_uncertainty='Unbounded without part masses, thickness and layups')
    if 'F1 blade 1' in o.name:
        relative=verts-pivots[0]
        direction=relative.mean(axis=0);theta=math.atan2(direction[1],direction[0])
        c,s=math.cos(theta),math.sin(theta)
        xy=np.column_stack([relative[:,0]*c+relative[:,1]*s,-relative[:,0]*s+relative[:,1]*c])
        radius=float(np.linalg.norm(relative[:,:2],axis=1).max())
        stations=np.linspace(.19,radius-.001,24)
        chord=[]
        for r in stations:
            ys=[]
            for tri in xy[faces]:
                for a,b in zip(tri,np.roll(tri,-1,axis=0)):
                    if (a[0]<=r<=b[0] or b[0]<=r<=a[0]) and abs(b[0]-a[0])>1e-9:
                        ys.append(float(a[1]+(r-a[0])*(b[1]-a[1])/(b[0]-a[0])))
            chord.append(max(ys)-min(ys) if ys else 0.)
        blade_geometry=dict(radius_m=radius,stations_m=stations.tolist(),chord_m=chord,
                            count=4,source_id=d['id'],twist_deg=0.,
                            twist_status='No aerodynamic twist/section definition supplied; zero-twist hypothesis',
                            source_neutral_thickness_m=float(relative[:,2].max()-relative[:,2].min()))
    parts.append(d)
    # Bake evaluated triangles in world coordinates for the derivative only.
    newmesh=bpy.data.meshes.new(o.name+' physics snapshot')
    newmesh.from_pydata(verts.tolist(),[],faces.tolist())
    for m in mesh.materials:newmesh.materials.append(m)
    source_meshes[o.name]=(newmesh,o.matrix_world.copy())
    ev.to_mesh_clear()

alloc={o['VTX_ID']:float(o['V4_mass_allocation_kg']) for o in objects if o.get('VTX_ID')}
for sys,mass in alloc.items():
    sub=[p for p in parts if p['subsystem']==sys]
    area=sum(p['area_m2'] for p in sub)
    for p in sub:
        p['mass_kg']=mass*p['area_m2']/area
        p['inertia_centroid_kg_m2']=(p['mass_kg']*np.array(p['inertia_per_kg_m2'])).tolist()

def aggregate(items):
    mass=sum(p['mass_kg'] for p in items)
    center=sum(p['mass_kg']*np.array(p['centroid_m']) for p in items)/mass
    inertia=np.zeros((3,3))
    for p in items:
        d=np.array(p['centroid_m'])-center
        inertia+=np.array(p['inertia_centroid_kg_m2'])+p['mass_kg']*(np.eye(3)*(d@d)-np.outer(d,d))
    assert np.linalg.eigvalsh(inertia).min()>0
    return dict(mass_kg=mass,centroid_m=center.tolist(),inertia_centroid_kg_m2=inertia.tolist())

bodies={name:dict(pivot_m=p.tolist(),**aggregate([x for x in parts if x['body']==name])) for name,p in groups.items()}
tanks=[dict(id=p['id'],centroid_m=p['centroid_m'],axis=byname[p['name']].matrix_world.to_quaternion()@Vector((0,0,1))) for p in parts if 'protected fuel cell' in p['name']]
for t in tanks:t['axis']=list(t['axis'])
ledger=dict(source_sha256='2db9abd64ba9b7078e6e539ba4c6b9177e58e335a085a8ea213b5ffa6e987e35',
            revision='P0-V4A-surface-allocation-r1',frame='world/body +Z up; +X east, +Y north; source cabin faces -Y',
            allocation_method='Uniform areal density within each V4 subsystem; exact surface triangle moments. NOT measured mass.',
            subsystem_allocations_kg=alloc,parts=parts,excluded=excluded,bodies=bodies,
            empty=aggregate(parts),rotor_pivots_m=[p.tolist() for p in pivots],
            blade=blade_geometry,tanks=tanks,gear_stroke_target_m=.25,
            fuel_inner_radius_m=.18,fuel_inner_length_m=.48)
(ROOT/'evidence/source/airframe_ledger.json').write_text(json.dumps(ledger,indent=2))

# Build a separate scene: deleting animated objects from this newer-version
# master crashes the older local Blender. Preserve the complete source scene.
live_scene=bpy.data.scenes.new('VTX solver derivative')
bpy.context.window.scene=live_scene
containers={}
for name,p in groups.items():
    e=bpy.data.objects.new(name,None);live_scene.collection.objects.link(e);e.location=p
    e['physical_body']=name;containers[name]=e
for part in parts:
    mesh,_=source_meshes[part['name']]
    name=part['name'];group=part['body'];pivot=groups[group]
    for v in mesh.vertices:v.co-=Vector(pivot)
    o=bpy.data.objects.new(name,mesh);live_scene.collection.objects.link(o)
    o.parent=containers[group];o['blendstra_id']=part['id'] or '';o['physical_body']=group
    if 'blade ' in name:
        c=np.array(part['centroid_m'])-pivot
        o['pitch_axis']=(c/np.linalg.norm(c)).tolist()
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type=='BSDF_PRINCIPLED' and 'Transmission Weight' in n.inputs:
                # Browser transparency is an explicit display derivative only.
                if 'glaz' in m.name.lower() or 'glass' in m.name.lower():
                    n.inputs['Alpha'].default_value=.27
                    m.surface_render_method='DITHERED'
bpy.ops.export_scene.gltf(filepath=str(ROOT/'public/assets/airframe-live.glb'),
                         export_format='GLB',export_animations=False,export_yup=False,
                         export_extras=True,export_cameras=False,export_lights=False,
                         use_active_scene=True)
print('BUILD_AIRFRAME',len(parts),'mapped parts',len(excluded),'presentation exclusions')
print('EMPTY',ledger['empty'],'BLADE',blade_geometry)
print('BODIES',[(k,round(v['mass_kg'],3)) for k,v in bodies.items()])
