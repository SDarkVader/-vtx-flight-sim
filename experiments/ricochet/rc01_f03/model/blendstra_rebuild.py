"""VTX Ricochet RC01 F01. Editable structural graph only. All units m, body +X forward, +Y starboard, +Z up. Size and materials provisional."""
import bpy, math, json
from mathutils import Vector
D={"overall_length_m":6.8,"span_m":9.6,"hull_beam_m":1.6,"wing_root_chord_m":2.1,"wing_tip_chord_m":1.13,"duct_ID_m":0.9,"duct_OD_m":1.04,"nominal_mass_kg":900,"buoyant_volume_target_m3":1.8}
ST=[('N0',3.30,.115,.24,.82),('N1',2.50,.45,.12,1.04),('N2',1.45,.68,.035,1.19),('N3',.22375,.80,0.,1.20),('N4',-.6485,.75,.035,1.16),('N5',-1.75,.38,.12,.91)]
V={};E=[]
def node(name,x,y,z):
 q=(round(x,5),round(y,5),round(z,5))
 if name in V and V[name]!=q:raise ValueError('Inconsistent node '+name)
 V[name]=q;return name
def edge(group,a,b,od=.034,wall=.0025,material='CFRP TUBE / UNVERIFIED'):
 if a==b:raise ValueError('Zero-length edge '+a)
 E.append(dict(group=group,a=a,b=b,OD_m=od,wall_m=wall,material=material))
for j,(p,x,w,k,deck) in enumerate(ST):
 levels={'K':(0,k),'PC':(-.80*w,k+.27*(deck-k)),'SC':(.80*w,k+.27*(deck-k)),'PS':(-w,k+.70*(deck-k)),'SS':(w,k+.70*(deck-k)),'PD':(-.50*w,deck),'SD':(.50*w,deck),'T':(0,deck+.075)}
 for n,(y,z) in levels.items():node(p+'_'+n,x,y,z)
 for a,b in [('K','PC'),('K','SC'),('PC','PS'),('SC','SS'),('PS','PD'),('SS','SD'),('PD','T'),('SD','T')]:edge('Hull transverse ring',p+'_'+a,p+'_'+b,.035,.003)
 if j:
  old=ST[j-1][0]
  for n in ['K','PC','SC','PS','SS','PD','SD','T']:edge('Hull longitudinal stringer',old+'_'+n,p+'_'+n,.031,.0025)
  for a,b in [('PC','PS'),('SC','SS')]:edge('Hull shear bay',old+'_'+a,p+'_'+b,.022,.002)
 if p in ('N2','N3','N4','N5'):edge('Bulkhead transverse tie',p+'_PS',p+'_SS',.030,.0025)
for k in ('N2','N3'):
 x,w=next((r[1],r[2]) for r in ST if r[0]==k)
 node(k+'_CANOPY_L',x,-.48*w,1.49);node(k+'_CANOPY_R',x,.48*w,1.49)
 edge('Cockpit protection hoop',k+'_PD',k+'_CANOPY_L',.028,.0025)
 edge('Cockpit protection hoop',k+'_SD',k+'_CANOPY_R',.028,.0025)
 edge('Cockpit protection hoop',k+'_CANOPY_L',k+'_CANOPY_R',.028,.0025)
for side in ('L','R'):edge('Cockpit upper rail','N2_CANOPY_'+side,'N3_CANOPY_'+side,.028,.0025)
Y=[.8,2.2,3.80,4.76]
def chord(y):return 2.1-(2.1-1.13)*y/4.8
def leading(y):return .82-.67*y/4.8
def wingz(y):return 1.10+math.tan(math.radians(2.0))*max(0,y-.8)
for side,sign in [('P',-1),('S',1)]:
 for i,y in enumerate(Y):
  z=wingz(y);le=leading(y);c=chord(y)
  for n,f in [('LE',0),('FS',.25),('RS',.70),('TE',1)]:node(f'W{side}{i}_{n}',le-f*c,sign*y,z)
  for u,v in [('LE','FS'),('FS','RS'),('RS','TE')]:edge('Wing rib / load path',f'W{side}{i}_{u}',f'W{side}{i}_{v}',.023,.002)
  if i:
   for n in ('LE','FS','RS','TE'):edge('Wing spanwise member',f'W{side}{i-1}_{n}',f'W{side}{i}_{n}',.044 if n in ('FS','RS') else .022,.003 if n in ('FS','RS') else .002)
  if i>=1:edge('Wing torsion bay',f'W{side}{i-1}_RS',f'W{side}{i}_FS',.020,.002)
 # wing roots connect at explicit shared spar/carry-through junctions
# Explicit structural junctions prevent wing carry-through tubes cutting through hull frames.
for spar,bulk in [('FS','N3'),('RS','N4')]:
 for side in ('P','S'):
  inner=bulk+'_'+('PS' if side=='P' else 'SS')
  outer=bulk+'_'+('PD' if side=='P' else 'SD')
  e=next(t for t in E if t['a']==inner and t['b']==outer and t['group']=='Hull transverse ring')
  E.remove(e)
  u=(1.10-V[inner][2])/(V[outer][2]-V[inner][2])
  x=V[inner][0];y=V[inner][1]+u*(V[outer][1]-V[inner][1])
  jn='JUNCTION_'+spar+'_'+side
  node(jn,x,y,1.10)
  edge('Hull transverse ring',inner,jn,.035,.003)
  edge('Hull transverse ring',jn,outer,.035,.003)
 edge('Wing carry-through',f'WP0_{spar}','JUNCTION_'+spar+'_P',.062,.004,'CFRP BOX / UNVERIFIED')
 edge('Wing carry-through','JUNCTION_'+spar+'_P','JUNCTION_'+spar+'_S',.062,.004,'CFRP BOX / UNVERIFIED')
 edge('Wing carry-through','JUNCTION_'+spar+'_S',f'WS0_{spar}',.062,.004,'CFRP BOX / UNVERIFIED')
for side,sgn in [('P',-1),('S',1)]:
 i=2;y=sgn*Y[i]
 f=f'W{side}{i}_FS';r=f'W{side}{i}_RS';xp=(V[f][0]+V[r][0])/2
 node('FLOAT_'+side+'_K',xp,y,.42)
 edge('Float braced hanger',f,'FLOAT_'+side+'_K',.028,.0025)
 edge('Float braced hanger',r,'FLOAT_'+side+'_K',.028,.0025)
 for tag,dx in [('F',.42),('A',-.42)]:
  node('FLOAT_'+side+'_'+tag,xp+dx,y,.42)
  edge('Float load spreader','FLOAT_'+side+'_K','FLOAT_'+side+'_'+tag,.035,.003)
node('PYLON_R',-1.75,0,1.02);node('PYLON_M',-2.30,0,1.70);node('PYLON_T',-2.62,0,2.30)
edge('Aft propulsion pylon','N5_T','PYLON_M',.062,.004)
edge('Aft propulsion pylon','N5_K','PYLON_M',.052,.004)
edge('Aft propulsion pylon','PYLON_M','PYLON_T',.065,.004)
edge('Aft propulsion pylon','N5_PS','PYLON_M',.035,.003)
edge('Aft propulsion pylon','N5_SS','PYLON_M',.035,.003)
for side,sgn in [('P',-1),('S',1)]:
 c=(-2.22,sgn*1.22,1.70)
 node('FAN_'+side+'_AXIS',*c)
 node('FAN_'+side+'_IN',c[0],c[1]-sgn*.60,c[2])
 node('FAN_'+side+'_LOW',c[0],c[1],c[2]-.60)
 edge('Duct support arm','PYLON_M','FAN_'+side+'_IN',.045,.003)
 edge('Duct support arm','N5_'+('PS' if sgn<0 else 'SS'),'FAN_'+side+'_LOW',.038,.003)
 edge('Duct support brace','FAN_'+side+'_IN','FAN_'+side+'_LOW',.025,.002)
for side,sgn in [('P',-1),('S',1)]:
 node('TAIL_'+side+'_SPAR',-2.75,sgn*1.55,2.30);node('TAIL_'+side+'_TE',-3.34,sgn*1.55,2.30)
 edge('Horizontal tail main spar','PYLON_T','TAIL_'+side+'_SPAR',.038,.003)
 edge('Tailtip chord member','TAIL_'+side+'_SPAR','TAIL_'+side+'_TE',.023,.002)
 edge('Tail longitudinal brace','PYLON_T','TAIL_'+side+'_TE',.025,.002)
adj={v:set() for v in V}
for t in E:
 a,b=t['a'],t['b'];assert a in V and b in V
 va,vb=Vector(V[a]),Vector(V[b]);ll=(va-vb).length
 if ll<.04:raise ValueError('Short member '+a+' '+b)
 t['length_m']=round(ll,5);adj[a].add(b);adj[b].add(a)
structural={k for k in V if not k.endswith('_AXIS') and k!='PYLON_R'}
seen=set();queue=['N3_K']
while queue:
 a=queue.pop()
 if a in seen:continue
 seen.add(a);queue.extend(adj[a]-seen)
if structural-seen:raise ValueError('Disconnected nodes '+str(structural-seen))
assert abs(9.6*(2.1+1.13)/2-15.504)<1e-7
assert max(abs(p[1]) for p in V.values())<=4.8
assert min(p[0] for p in V.values())>=-3.40 and max(p[0] for p in V.values())<=3.40
for t in E:assert t['wall_m']>0 and 2*t['wall_m']<t['OD_m']
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.gravity=(0,0,-9.80665)
COLS=['01_HULL_RINGS','02_HULL_LONGITUDINAL','03_WING_STRUCTURE','04_FLOAT_SUPPORTS','05_TAIL_PROPULSION','06_DATUMS']
for name in COLS:
 co=bpy.data.collections.new('RC01_'+name);bpy.context.scene.collection.children.link(co)
def material(name,rgba):
 m=bpy.data.materials.new(name);m.diffuse_color=rgba;m.use_nodes=True
 m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=rgba
 m.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value=.42
 return m
M={'hull':material('Titanium-grey CFRP concept',(.24,.31,.35,1)),'wing':material('Blue-grey wing concept',(.11,.28,.38,1)),'gold':material('Gold joint interface markers',(.92,.62,.11,1)),'tail':material('Tail graphite steel proxy',(.32,.36,.43,1))}
def collection(group):
 if group.startswith('Hull transverse') or group.startswith('Bulkhead'):return '01_HULL_RINGS'
 if group.startswith('Hull') or group.startswith('Cockpit'):return '02_HULL_LONGITUDINAL'
 if group.startswith('Wing'):return '03_WING_STRUCTURE'
 if group.startswith('Float'):return '04_FLOAT_SUPPORTS'
 return '05_TAIL_PROPULSION'
for i,t in enumerate(E):
 a,b=Vector(V[t['a']]),Vector(V[t['b']]);dv=b-a
 bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=t['OD_m']/2,depth=dv.length,location=(a+b)/2)
 o=bpy.context.object;o.rotation_euler=dv.to_track_quat('Z','Y').to_euler()
 o.name=f"RC01-F01-{i+1:03d}_{t['group'].replace(' ','_')}_{t['a']}-{t['b']}"
 o.data.materials.append(M['wing' if t['group'].startswith('Wing') else 'tail' if 'propulsion' in t['group'].lower() or 'tail' in t['group'].lower() or 'duct' in t['group'].lower() else 'hull'])
 for co in list(o.users_collection):co.objects.unlink(o)
 bpy.data.collections['RC01_'+collection(t['group'])].objects.link(o)
 for k,v in t.items():o['RC01_'+k]=v
 o['RC01_design_status']='SECTION SIZE PROVISIONAL; NOT LOAD-RATED'
for name,p in V.items():
 if name.endswith('_AXIS') or name=='PYLON_R':continue
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.045,location=p)
 o=bpy.context.object;o.name='JOINT_'+name;o.data.materials.append(M['gold'])
 for co in list(o.users_collection):co.objects.unlink(o)
 bpy.data.collections['RC01_06_DATUMS'].objects.link(o)
 o['RC01_joint_type']='COORDINATE SHARED WELD / DESIGN-ONLY'
 o['RC01_connected_members']=len(adj[name])
manifest={'revision':'RC01-F01','axes':'X nose; Y starboard; Z up; metres','dimensions':D,'stations':ST,'members':E,'nodes_m':V,'verification':{'graph_connected':True,'stations':len(ST),'member_count':len(E),'structural_nodes':len(structural),'unattached_reference_nodes':['FAN_P_AXIS','FAN_S_AXIS','PYLON_R'],'unverified':['tube layup and wall strength','joint design','hydrostatic geometry','mass and inertia','material limits']}}
bpy.data.texts.new('RC01_F01_PARTS_AND_DIMENSIONS.json').write(json.dumps(manifest,indent=2))

# F02: Bulkhead modules plus motion-space declarations, appended to F01 exact authored scene.
F02COLS=['07_BULKHEADS','08_BULKHEAD_BONDS','09_MOVEMENT_ENVELOPES']
for s in F02COLS:
 coll=bpy.data.collections.new('RC01_F02_'+s);bpy.context.scene.collection.children.link(coll)
foamCore=85.0; laminateDensity=1550.0; coreThickness=0.009; skinThickness=0.0015
panelThickness=coreThickness+2*skinThickness
mat_f02=material('F02 bulkhead carbon sandwich / nominal only',(.28,.44,.49,1))
mat_bond=material('F02 bonded tab interfaces / nominal',(.84,.57,.15,1))
bulkhead_rows=[]
def frame_outline(st):
 p,x,w,k,deck=st
 names=['K','SC','SS','SD','T','PD','PS','PC']
 return [(V[p+'_'+n][1],V[p+'_'+n][2]) for n in names]
def inset_2d(poly,r=0.90):
 cy=sum(v[0] for v in poly)/len(poly);cz=sum(v[1] for v in poly)/len(poly)
 return [(cy+r*(y-cy),cz+r*(z-cz)) for y,z in poly]
def clipz(poly, zlim, keep_below):
 out=[]
 for a,b in zip(poly,poly[1:]+poly[:1]):
  za=a[1];zb=b[1]
  inside=lambda z:z<=zlim if keep_below else z>=zlim
  ia,ib=inside(za),inside(zb)
  if ia:out.append(a)
  if ia!=ib:
   u=(zlim-za)/(zb-za)
   out.append((a[0]+u*(b[0]-a[0]),zlim))
 return out
def area_2d(poly):
 return abs(sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly)))*0.5)
def plate(pname,x,poly,role):
 if len(poly)<3 or area_2d(poly)<.005:return None
 n=len(poly)
 verts=[(x-panelThickness/2,y,z) for y,z in poly]+[(x+panelThickness/2,y,z) for y,z in poly]
 faces=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]
 faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 mesh=bpy.data.meshes.new('F02mesh_'+pname);mesh.from_pydata(verts,[],faces);mesh.update()
 ob=bpy.data.objects.new('F02_'+pname,mesh)
 bpy.data.collections['RC01_F02_07_BULKHEADS'].objects.link(ob);ob.data.materials.append(mat_f02)
 a=area_2d(poly)
 ob['F02_role']=role;ob['F02_area_m2']=a;ob['F02_thickness_m']=panelThickness
 ob['F02_mass_estimate_kg']=a*(coreThickness*foamCore+2*skinThickness*laminateDensity)
 ob['F02_material_status']='Corecell M80 density source, laminate effective density assumed; no strength qualification'
 ob['F02_perimeter_status']='NOT SEALED TO HULL: skin/bond/penetration design pending'
 return {'part_id':ob.name,'role':role,'area_m2':round(a,5),'thickness_m':panelThickness,
         'mass_estimate_kg':round(ob['F02_mass_estimate_kg'],3),'centroid_x_m':x,'status':'concept only'}
def tab_between(a,b,name):
 va=Vector(a);vb=Vector(b);d=vb-va
 if d.length<.008:return
 bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.014,depth=d.length,location=(va+vb)/2)
 o=bpy.context.object;o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
 o.name='F02_BOND_'+name;o.data.materials.append(mat_bond)
 for c in list(o.users_collection):c.objects.unlink(o)
 bpy.data.collections['RC01_F02_08_BULKHEAD_BONDS'].objects.link(o)
 o['F02_role']='design intent bonded standoff only; adhesion area not verified'
for st in ST:
 p,x,w,k,deck=st
 if p=='N0':continue
 bulkId='BH'+p[1:]
 x_panel=x+.085
 outline=inset_2d(frame_outline(st),.90)
 plates=[]
 if p in ('N1','N5'):
  parts=[('closed_web',outline,'FULL CLOSED DIAPHRAGM; NOT YET SEALED TO SKIN')]
 elif p=='N2':
  parts=[('lower_web',clipz(outline,.56,True),'COCKPIT LOWER SHEAR WEB; ACCESS GAP ABOVE'),
         ('upper_crown',clipz(outline,1.155,False),'COCKPIT CROWN TIE; ACCESS GAP BELOW')]
 else:
  parts=[('lower_web',clipz(outline,.93,True),'SPAR-CLEAR LOWER WEB; OPEN ABOVE'),
         ('upper_crown',clipz(outline,1.190,False),'UPPER CROWN; SPAR CLEARANCE BELOW')]
 for label,poly,role in parts:
  item=plate(bulkId+'_'+label,x_panel,poly,role)
  if item:bulkhead_rows.append(item);plates.append(item)
 # Intentional simple bonded standoffs: nose+keel region with longitudinal frame at station.
 anchorNames=['K','PC','SC']
 for n in anchorNames:
  anchor=Vector(V[p+'_'+n]);tb=Vector((x_panel,anchor.y*.90,anchor.z+.018))
  tab_between(anchor,tb,bulkId+'_'+n)
# Future moving component sweep and mass placeholders. These are NON-PHYSICAL design keepouts,
# not fitted actuators, qualified bearings, or validated motion clearances.
envelopes=[
 ('PILOT_SEAT_TRACK','linear X +/-0.12',85,(1.30,0,.80),(.66,.70,.88),'pilot mass used only in sensitivity example'),
 ('FUEL_CELL_PORT','fluid fill/slosh',None,(-1.05,-.23,.55),(.80,.27,.40),'density, usable mass, slosh and tanks unverified'),
 ('FUEL_CELL_STARBOARD','fluid fill/slosh',None,(-1.05,.23,.55),(.80,.27,.40),'paired fill must conserve lateral CG'),
 ('ENERGY_PACK_ALTERNATE','installation/service',None,(-1.02,0,.69),(.95,.50,.34),'ALTERNATIVE to competing fuel-envelope, not simultaneous'),
 ('FLOAT_PORT','retraction z 0.42 to 1.02',12,(-.38,-3.80,.72),(1.05,.50,.70),'12 kg nominal moving subsystem, not weighed'),
 ('FLOAT_STARBOARD','retraction z 0.42 to 1.02',12,(-.38,3.80,.72),(1.05,.50,.70),'paired movement; asymmetric failsafe required'),
 ('AILERON_PORT','hinge about Y, +/-25 deg',None,(-.72,-3.6,1.26),(.85,2.15,.28),'swept volume preliminary'),
 ('AILERON_STARBOARD','hinge about Y, +/-25 deg',None,(-.72,3.6,1.26),(.85,2.15,.28),'swept volume preliminary'),
 ('FLAP_PORT','hinge about Y, -5 to +35 deg',None,(-.80,-1.48,1.19),(.80,1.25,.27),'swept volume preliminary'),
 ('FLAP_STARBOARD','hinge about Y, -5 to +35 deg',None,(-.80,1.48,1.19),(.80,1.25,.27),'swept volume preliminary'),
 ('RUDDER','hinge Z +/-30 deg',None,(-2.97,0,2.04),(.72,.25,.51),'tail control interference to validate'),
 ('ELEVATOR_PORT','hinge Y +/-20 deg',None,(-3.07,-.86,2.30),(.62,1.32,.23),'tail control interference to validate'),
 ('ELEVATOR_STARBOARD','hinge Y +/-20 deg',None,(-3.07,.86,2.30),(.62,1.32,.23),'tail control interference to validate'),
 ('FAN_PORT_ROTOR_SWEEP','rotation around X',None,(-2.22,-1.22,1.70),(.34,.90,.90),'not installed; 0.90 m disk 0.070 m radial shell clearance nominal'),
 ('FAN_STARBOARD_ROTOR_SWEEP','rotation around X',None,(-2.22,1.22,1.70),(.34,.90,.90),'not installed; 0.90 m disk 0.070 m radial shell clearance nominal')]
for name,movement,mass,pos,size,note in envelopes:
 bpy.ops.object.empty_add(type='CUBE',location=pos)
 o=bpy.context.object;o.name='F02_KEEP_OUT_'+name
 o.empty_display_size=1;o.scale=tuple(q/2 for q in size)
 for c in list(o.users_collection):c.objects.unlink(o)
 bpy.data.collections['RC01_F02_09_MOVEMENT_ENVELOPES'].objects.link(o)
 o['F02_move_or_function']=movement
 o['F02_center_m']=list(pos);o['F02_bounds_m']=list(size)
 o['F02_mass_placeholder_kg']=mass if mass is not None else -1
 o['F02_note']=note
 fkey=name+'_LOC';bpy.context.scene['F02_'+fkey]=','.join(str(v) for v in pos)
 # all moving bodies are unmodeled placeholders, not active Blender joints
f02_manifest={
 'revision':'RC01-F02-01','parent':'RC01-F01',
 'status':'CONCEPT BULKHEAD WEBS; NO CONTINUOUS WATERTIGHT HULL; NO STRESS VALIDATION',
 'bulkhead_panels':bulkhead_rows,
 'material_assumptions':{'sandwich_total_thickness_m':panelThickness,'foam_core_m':coreThickness,
   'foam_nominal_density_kg_m3':foamCore,'each_face_m':skinThickness,'face_effective_density_kg_m3':laminateDensity},
 'bulkhead_model_mass_estimate_kg':round(sum(row['mass_estimate_kg'] for row in bulkhead_rows),3),
 'moving_keepouts':[{'id':n,'mode':m,'mass_placeholder_kg':w,'center_m':p,'bounds_m':s,'notes':note}
 for n,m,w,p,s,note in envelopes],
 'unresolved':['hull shell and flooded volume','bond sizing','composite laminate allowables',
 'structural water slap/slamming load cases','finite element / stiffness',
 'Munk added mass and yaw derivatives','mass CG and inertia complete ledger',
 'moving swept-volume collision on actuation','sealing of any spar/shaft penetrations']
}
bpy.data.texts.new('RC01_F02_BULKHEAD_AND_MOVING_PARTS.json').write(json.dumps(f02_manifest,indent=2))
bpy.context.scene['RC01_revision']='F02-bulkhead'
bpy.context.scene['F02_bulkhead_mass_estimate_kg']=f02_manifest['bulkhead_model_mass_estimate_kg']
bpy.context.scene['F02_unverified']='No skin or buoyancy; CG and moments not proven'
print('RC01_F02_DONE',len(bulkhead_rows),'panels',len(envelopes),'moving keepouts','bulkhead mass estimate',f02_manifest['bulkhead_model_mass_estimate_kg'])
import uuid
F01_SOURCE_ID_MAP={"RC01-F01-149_Wing_spanwise_member_WS1_FS-WS2_FS":"009463cf-828f-45f6-a1ed-ccdec95dd43b","RC01-F01-112_Wing_rib_/_load_path_WP1_RS-WP1_TE":"02647b44-a43f-44ac-8c41-8b72ff6b45f9","JOINT_N3_SD":"043894e4-49a3-438b-a523-61313fa1952e","RC01-F01-173_Wing_carry-through_JUNCTION_RS_P-JUNCTION_RS_S":"0589703a-4ea9-4387-9100-b2caac247de9","JOINT_WS3_FS":"0757d8a6-a6af-42a2-9cb2-f0da0409aa3a","JOINT_TAIL_P_SPAR":"079e4fbc-a62d-46ad-a7ff-10e7c960fcc3","JOINT_N3_PD":"07f3db11-12a2-4970-af6a-2b532da47460","JOINT_WP2_LE":"08232acb-fd7c-447d-8779-d2a4d9e710b7","JOINT_N3_K":"08b5b0f9-9e9e-4825-9019-1531e0620b14","RC01-F01-130_Wing_spanwise_member_WP2_FS-WP3_FS":"09e462ef-8e9c-47bd-b39d-5eb77965fa91","RC01-F01-163_Hull_transverse_ring_N3_SS-JUNCTION_FS_S":"09f44462-c132-4c46-8c0e-f8dbd3ad9e70","RC01-F01-029_Hull_transverse_ring_N2_PC-N2_PS":"0a3650e0-359f-448a-8c56-9d09fce2e87b","RC01-F01-019_Hull_longitudinal_stringer_N0_SC-N1_SC":"0a93535a-3d63-4c4b-bbab-9764fc02d57b","JOINT_N5_PD":"0a99a918-dce1-4b93-874e-2625d7386a61","RC01-F01-123_Wing_spanwise_member_WP1_RS-WP2_RS":"0c151be4-ee21-43c6-bcbb-0daa02a6b0ce","JOINT_N2_CANOPY_R":"0c7d238a-9a5c-4313-a710-230f061eec37","RC01-F01-183_Aft_propulsion_pylon_N5_T-PYLON_M":"102c9c65-2c51-408b-896f-36b3263a5d08","JOINT_TAIL_P_TE":"10de7c59-3095-4a43-9a68-5fbc273cb360","RC01-F01-071_Hull_longitudinal_stringer_N3_SC-N4_SC":"111f3821-2442-4cb6-abbf-910e833136c9","JOINT_WP0_TE":"112a1d7b-814a-4e4a-8ffb-9d487fb6325c","RC01-F01-035_Hull_longitudinal_stringer_N1_K-N2_K":"11480dc5-cc9c-4103-b809-e885de71b9eb","JOINT_N1_SC":"11558575-dd8f-47dd-9856-8cc64ea196b3","JOINT_N0_PD":"11dd0fdb-e98c-4364-944e-0adbf43ce2d7","JOINT_TAIL_S_SPAR":"121bd22c-3dc8-4c2d-bca5-ffe331190dc3","JOINT_N3_CANOPY_R":"156fc9e0-1091-45cc-9d69-eebb6c1feab5","RC01-F01-184_Aft_propulsion_pylon_N5_K-PYLON_M":"164401d5-bd52-43cc-b920-406ed07f0ad4","RC01-F01-114_Wing_spanwise_member_WP0_FS-WP1_FS":"165e5db3-5bf1-4b74-b5df-70060aa76673","RC01-F01-092_Hull_longitudinal_stringer_N4_SS-N5_SS":"1670ddd1-e10e-4398-bd25-4e0d9300eab9","RC01-F01-139_Wing_rib_/_load_path_WS1_RS-WS1_TE":"16f68d3a-cb66-4dd3-9e23-7eadc408fd07","JOINT_JUNCTION_FS_S":"176aa3ae-4ecb-43d9-b630-3bca117edb29","RC01-F01-167_Wing_carry-through_JUNCTION_FS_S-WS0_FS":"178c4a71-8b4e-4777-b07f-e4a696743741","JOINT_N3_T":"17c532f0-5c25-4b04-81a1-7bcef9ce538c","RC01-F01-027_Hull_transverse_ring_N2_K-N2_PC":"18781382-0131-4d54-976d-3551c4991798","JOINT_WP2_TE":"1bc76f4e-37a3-4029-89b5-e18dae3414d2","RC01-F01-043_Hull_shear_bay_N1_PC-N2_PS":"1d49e0a5-58d7-4c07-b53b-0219bc297fc5","JOINT_FAN_S_LOW":"1eac9692-553b-41a8-9a3a-f08f34e7a5bd","RC01-F01-117_Wing_torsion_bay_WP0_RS-WP1_FS":"1ed2bd66-41ec-42af-b899-a4ffb64b90dc","RC01-F01-170_Hull_transverse_ring_N4_SS-JUNCTION_RS_S":"1f73440e-7ab8-47d0-b37b-a5b8bfb365f8","RC01-F01-054_Hull_longitudinal_stringer_N2_SC-N3_SC":"205bd135-69d8-4749-83cc-6ce426baecf4","RC01-F01-081_Hull_transverse_ring_N5_K-N5_SC":"208d1e45-958b-42f5-be9a-8ce39af84335","RC01-F01-142_Wing_spanwise_member_WS0_RS-WS1_RS":"2119a281-ff30-449e-abf3-4dbc3c895ad7","RC01-F01-164_Hull_transverse_ring_JUNCTION_FS_S-N3_SD":"215c9292-5185-4274-906d-8ead26d169f3","RC01-F01-049_Hull_transverse_ring_N3_SC-N3_SS":"21da06ba-b9d4-42ac-b5e2-79d824501e63","RC01-F01-015_Hull_transverse_ring_N1_PD-N1_T":"21e8bf6e-8e4e-4e1d-804a-0b2941864c80","RC01-F01-140_Wing_spanwise_member_WS0_LE-WS1_LE":"2301a5c6-c81f-4002-8009-3b7066cfcf31","RC01-F01-007_Hull_transverse_ring_N0_PD-N0_T":"2371c545-c6d6-4c4f-84af-16c8b3913f1c","RC01-F01-179_Float_braced_hanger_WS2_FS-FLOAT_S_K":"237513a1-8a10-45f7-8fd6-5dc397339a45","RC01-F01-197_Horizontal_tail_main_spar_PYLON_T-TAIL_S_SPAR":"245f4d4e-e879-4986-889f-2b183359655e","RC01-F01-181_Float_load_spreader_FLOAT_S_K-FLOAT_S_F":"25d6e58f-df67-4725-9110-ee1bcb62d741","RC01-F01-195_Tailtip_chord_member_TAIL_P_SPAR-TAIL_P_TE":"26978d39-183f-46ef-91d4-5d83eb9c6ce8","JOINT_FLOAT_P_F":"27b57c72-2bb9-4858-bdfe-82b185a228ad","JOINT_N4_PS":"29ef4558-91f7-4fa7-9c0c-9105461c3919","RC01-F01-069_Hull_longitudinal_stringer_N3_K-N4_K":"2a791820-6689-4ac4-8058-77fe0f1ab65e","RC01-F01-138_Wing_rib_/_load_path_WS1_FS-WS1_RS":"2b209d31-9101-4ef3-8784-0d87558e9caf","RC01-F01-102_Cockpit_protection_hoop_N3_PD-N3_CANOPY_L":"2bfb6f76-001a-4958-9b39-f64766eb19c8","RC01-F01-105_Cockpit_upper_rail_N2_CANOPY_L-N3_CANOPY_L":"2ca0fa6c-5623-4296-9b33-2276e8b05c69","RC01-F01-146_Wing_rib_/_load_path_WS2_FS-WS2_RS":"2d7c06ad-943a-4494-be33-e51e965295ea","RC01-F01-115_Wing_spanwise_member_WP0_RS-WP1_RS":"2d811f81-0673-4a2b-9ebf-9243f4a8cc56","RC01-F01-155_Wing_rib_/_load_path_WS3_RS-WS3_TE":"2da7d18f-991f-4975-99ce-46e5405a0140","RC01-F01-011_Hull_transverse_ring_N1_PC-N1_PS":"2e5b4c00-573e-43a2-94fd-ecee7694603e","RC01-F01-124_Wing_spanwise_member_WP1_TE-WP2_TE":"2f47ef39-3059-4b4d-a63c-d20eb7446bb1","RC01-F01-185_Aft_propulsion_pylon_PYLON_M-PYLON_T":"30c83f83-98a5-4795-ac8a-b3eb2666964e","RC01-F01-003_Hull_transverse_ring_N0_PC-N0_PS":"30e1e989-18d6-433c-af0b-1ff6e3865fd2","RC01-F01-119_Wing_rib_/_load_path_WP2_FS-WP2_RS":"31a1281c-c9cd-4567-ae2a-69e2efffac8d","JOINT_N4_SC":"31e56c70-fbb0-4cd8-8232-f406db9839cf","RC01-F01-023_Hull_longitudinal_stringer_N0_SD-N1_SD":"320af96d-d837-4431-a224-04238224e94f","RC01-F01-107_Wing_rib_/_load_path_WP0_LE-WP0_FS":"3393becd-d6fc-4be3-90dc-4b9e82673a04","RC01-F01-078_Hull_shear_bay_N3_SC-N4_SS":"3454f4e6-40f9-4200-9c15-59a662e4db56","JOINT_N2_CANOPY_L":"346357bc-203a-4eb0-9530-5da7af993762","RC01-F01-084_Hull_transverse_ring_N5_PS-N5_PD":"346a7b96-84b8-4d52-aaba-2e76ea95ebc4","RC01-F01-055_Hull_longitudinal_stringer_N2_PS-N3_PS":"34a6c9a0-0b0e-42cd-8791-aa6c28a6dc4d","RC01-F01-063_Hull_transverse_ring_N4_K-N4_PC":"3509b36e-92cd-473d-b82b-65863d1c6dc4","RC01-F01-051_Hull_transverse_ring_N3_SD-N3_T":"36122d60-f149-45ec-aca2-91d1b0a9ed0c","JOINT_N0_SC":"37ce6d28-533c-497c-890f-93ee5823f7d6","RC01-F01-166_Wing_carry-through_JUNCTION_FS_P-JUNCTION_FS_S":"3869d4f4-24bb-4097-a67e-323d00877a57","RC01-F01-188_Duct_support_arm_PYLON_M-FAN_P_IN":"38e45c59-5755-43b8-8157-7aaedc8a94ec","RC01-F01-162_Hull_transverse_ring_JUNCTION_FS_P-N3_PD":"3902ef74-3d6a-443e-85de-8dca2c45090b","JOINT_N4_PD":"3a3fc268-572b-4848-8b48-347d546287d2","RC01-F01-061_Hull_shear_bay_N2_SC-N3_SS":"3c7e940a-df16-4a3f-9e07-7a2ae12a6dd0","RC01-F01-161_Hull_transverse_ring_N3_PS-JUNCTION_FS_P":"3cf818e1-b1e8-4a16-b6a9-b984d5b4fe6d","RC01-F01-141_Wing_spanwise_member_WS0_FS-WS1_FS":"3f6b46c2-8e32-468c-8ba4-12f25f346105","RC01-F01-086_Hull_transverse_ring_N5_PD-N5_T":"3fc6d80e-6e05-463b-b36c-afd926df5f9f","JOINT_WS0_FS":"405db83a-efde-4c53-83e0-4ffb11ceb990","RC01-F01-030_Hull_transverse_ring_N2_SC-N2_SS":"40632849-3558-4364-b8ca-006c20b749dc","RC01-F01-077_Hull_shear_bay_N3_PC-N4_PS":"4209cb68-253b-4a33-addb-83141ba1011f","RC01-F01-099_Cockpit_protection_hoop_N2_PD-N2_CANOPY_L":"421aeee9-b2fa-4eda-946b-d653ac670b3c","JOINT_N0_PC":"4254c222-ed9d-4ad4-a25a-6b62d4da0526","RC01-F01-088_Hull_longitudinal_stringer_N4_K-N5_K":"455e3c62-f7c9-4b27-9349-50c76caef21a","RC01-F01-057_Hull_longitudinal_stringer_N2_PD-N3_PD":"45f61157-2fbf-44f9-970c-38fd105c69c8","RC01-F01-159_Wing_spanwise_member_WS2_TE-WS3_TE":"494bba02-aef8-4bce-a08a-f83918d773a8","RC01-F01-144_Wing_torsion_bay_WS0_RS-WS1_FS":"4a5db5ff-f7d2-4aea-be3d-d4d70f55d2a3","RC01-F01-014_Hull_transverse_ring_N1_SS-N1_SD":"4ac51576-4493-44e2-8683-c601edece124","RC01-F01-194_Horizontal_tail_main_spar_PYLON_T-TAIL_P_SPAR":"4c4af93b-54f2-4cdf-ae17-8a76431fec56","RC01-F01-157_Wing_spanwise_member_WS2_FS-WS3_FS":"4c969571-5d42-49ea-bad0-15c7863b085f","JOINT_WS2_FS":"4dc0e290-ed20-40b1-989c-834aa49ab063","RC01-F01-116_Wing_spanwise_member_WP0_TE-WP1_TE":"4e523605-c81c-4669-9ef2-9adff311bc8c","JOINT_WS1_RS":"4e552245-6951-4799-bf14-c8181f820881","RC01-F01-153_Wing_rib_/_load_path_WS3_LE-WS3_FS":"4e5c3e65-fe38-4e2c-99ff-f5def80cf243","RC01-F01-193_Duct_support_brace_FAN_S_IN-FAN_S_LOW":"50c1b0cd-64a2-48ae-a580-be1bad38d7e1","RC01-F01-021_Hull_longitudinal_stringer_N0_SS-N1_SS":"51edc8ca-cafe-41ce-ae87-890cb5db3e5e","RC01-F01-196_Tail_longitudinal_brace_PYLON_T-TAIL_P_TE":"538677f7-1bae-42fb-80e3-0c5614ae3e0f","JOINT_N0_SS":"5436e02a-c4ef-4124-bd5f-a3f0f8a75150","RC01-F01-048_Hull_transverse_ring_N3_PC-N3_PS":"54c12cbb-8070-492e-b09e-d85c3215609e","RC01-F01-024_Hull_longitudinal_stringer_N0_T-N1_T":"55b6c614-27e8-4875-a333-f9cef1ad5cf9","JOINT_FLOAT_P_A":"560aee1c-2f35-4c08-bf4f-87a413c93a97","RC01-F01-165_Wing_carry-through_WP0_FS-JUNCTION_FS_P":"5858bd01-8f58-46b4-b9d8-744367ed3d07","RC01-F01-096_Hull_shear_bay_N4_PC-N5_PS":"5a3b7b92-fd16-4b6f-9382-01f0ffc76a11","RC01-F01-106_Cockpit_upper_rail_N2_CANOPY_R-N3_CANOPY_R":"5a73b96f-7293-462d-bbc6-bb4d8a8fd42f","RC01-F01-005_Hull_transverse_ring_N0_PS-N0_PD":"5b3a30a9-f09e-4959-9fa8-aad3dc893f44","RC01-F01-018_Hull_longitudinal_stringer_N0_PC-N1_PC":"5ba43ab5-933a-42a2-a04c-bc40bb45f820","RC01-F01-095_Hull_longitudinal_stringer_N4_T-N5_T":"5bc1efb9-9159-4d22-b718-8156c0e41e73","RC01-F01-037_Hull_longitudinal_stringer_N1_SC-N2_SC":"5dc62cb4-a431-4450-9140-364936e671e8","RC01-F01-131_Wing_spanwise_member_WP2_RS-WP3_RS":"5e4998e2-af38-457c-97a0-603b45df09ff","JOINT_WP3_FS":"5e4e71fc-ed76-426f-b88f-aae5ffaab1e5","RC01-F01-151_Wing_spanwise_member_WS1_TE-WS2_TE":"60ab222a-aa9d-4f9c-a77f-581e6149e014","RC01-F01-006_Hull_transverse_ring_N0_SS-N0_SD":"6275782e-000b-45a4-89fe-082c13fe625f","RC01-F01-012_Hull_transverse_ring_N1_SC-N1_SS":"62b5d4c0-0a0c-40f4-bc56-af5c6eea75ad","JOINT_WP2_FS":"6351aa34-6720-40b8-afbd-0c687df25e76","JOINT_N2_PD":"64d8e2ea-ebd4-442e-a8d9-818c9dc29cc1","JOINT_PYLON_T":"65cf06fe-6d4e-41d0-b72f-62ccb2d14f36","RC01-F01-066_Hull_transverse_ring_N4_SC-N4_SS":"65cf8a4a-5d25-4842-9b8b-a37ce97e64e0","RC01-F01-113_Wing_spanwise_member_WP0_LE-WP1_LE":"65d8f9e5-e352-4120-b207-4bd1699a71a5","RC01-F01-198_Tailtip_chord_member_TAIL_S_SPAR-TAIL_S_TE":"660db4b9-68ef-4b92-92fc-edd09c93ba9c","JOINT_WS1_FS":"6635f5e3-49ab-4752-b28f-eccc1560fe2f","JOINT_N1_PS":"675d774b-1b00-46c3-b191-c03fb550176a","JOINT_WS2_LE":"6899de7e-8df6-4ea3-b006-074f0e59e972","RC01-F01-177_Float_load_spreader_FLOAT_P_K-FLOAT_P_F":"6ac4d939-7d08-4c01-9386-5ea335b22ed6","RC01-F01-046_Hull_transverse_ring_N3_K-N3_PC":"6b7c6c7e-3130-44ac-85fc-50c50fe06bdf","RC01-F01-079_Bulkhead_transverse_tie_N4_PS-N4_SS":"6d38440d-6d1a-4c26-8270-a0521a895062","JOINT_N3_SC":"6d607f15-1326-45b7-8bea-c62f17207f41","JOINT_N5_T":"6dbea869-1d94-4626-be8c-7352bbd34745","JOINT_WP3_RS":"6e83a6c1-0a4f-4bd7-aad7-8e223bc6e769","RC01-F01-094_Hull_longitudinal_stringer_N4_SD-N5_SD":"6f892867-e00f-4238-a5af-98e910b86a62","JOINT_FLOAT_S_A":"6faaab69-6b95-432c-9347-7eb5827caccc","RC01-F01-070_Hull_longitudinal_stringer_N3_PC-N4_PC":"7016c455-1bb5-457b-a021-86115f11c7c9","RC01-F01-040_Hull_longitudinal_stringer_N1_PD-N2_PD":"72115961-ceb8-43e2-a6ee-e1804216fb2c","RC01-F01-156_Wing_spanwise_member_WS2_LE-WS3_LE":"7297db8b-264d-4146-9224-397290494be7","RC01-F01-076_Hull_longitudinal_stringer_N3_T-N4_T":"7494dceb-9994-4e83-b6e9-190dabf60aa0","RC01-F01-111_Wing_rib_/_load_path_WP1_FS-WP1_RS":"76c9ac73-74bc-4ad2-b4ff-8bdcdf67f678","RC01-F01-192_Duct_support_arm_N5_SS-FAN_S_LOW":"76eb1d52-800f-4ac9-bf58-939732d159f3","RC01-F01-050_Hull_transverse_ring_N3_PD-N3_T":"782e1683-150e-4436-b7ba-97db5de6809b","RC01-F01-160_Wing_torsion_bay_WS2_RS-WS3_FS":"78785549-5a58-497a-89e6-05371c1b089d","RC01-F01-045_Bulkhead_transverse_tie_N2_PS-N2_SS":"7892f0cf-94a9-4a84-ad4b-f0d096b4920f","JOINT_WS2_RS":"79834079-686a-4e3c-b02a-c7bc3b1e85ba","RC01-F01-074_Hull_longitudinal_stringer_N3_PD-N4_PD":"7aeb4c80-28fa-4a86-b12b-23a1e5ea641f","JOINT_TAIL_S_TE":"7c6ddd80-11b6-4a9a-a368-12a4459cdf46","JOINT_N1_SS":"7f9d1335-ad6b-4ac3-bf8b-6720e2f69d97","RC01-F01-097_Hull_shear_bay_N4_SC-N5_SS":"80aef511-dbc1-4ce1-81b7-c53b226cd34b","RC01-F01-047_Hull_transverse_ring_N3_K-N3_SC":"810888e4-1013-4b22-9fae-13adb3d6fabf","JOINT_WP0_FS":"810c0abf-111d-4123-b257-394ab4e15d69","JOINT_WS3_TE":"814a7899-152b-4a57-8365-88d0500ff4e7","JOINT_WS0_LE":"819aab62-ec69-48c6-9a89-da6d742fd31e","JOINT_N2_SD":"8346a5dd-71bc-4ab6-a9c6-d88e9f5cc379","JOINT_N5_K":"845e63a5-4fe9-4208-bf1f-42171c4e206e","RC01-F01-008_Hull_transverse_ring_N0_SD-N0_T":"847f552e-b747-43fc-ba49-e6330e9dacd1","RC01-F01-101_Cockpit_protection_hoop_N2_CANOPY_L-N2_CANOPY_R":"859806e8-f883-4be4-b062-ef9dd75272a4","RC01-F01-187_Aft_propulsion_pylon_N5_SS-PYLON_M":"85ec42bf-84bf-4ea2-8d9b-0b9a430bb7a9","RC01-F01-175_Float_braced_hanger_WP2_FS-FLOAT_P_K":"86231b00-0ae4-4f5d-8d98-10c646aacded","JOINT_FAN_P_LOW":"8627aa9e-c0d8-4fa5-b165-5d70526a710d","JOINT_FLOAT_P_K":"869a6ae6-2f49-415f-bbbf-c54582af3c16","JOINT_JUNCTION_RS_S":"87a82e3e-95a9-45ee-84c7-237e652b006f","RC01-F01-090_Hull_longitudinal_stringer_N4_SC-N5_SC":"886a55d9-feb8-4df7-8700-480890959af4","JOINT_N4_T":"8aa419af-436d-4c79-a6c2-dceff611bf8a","RC01-F01-041_Hull_longitudinal_stringer_N1_SD-N2_SD":"8c951980-478b-4e15-a408-f3993993a856","RC01-F01-121_Wing_spanwise_member_WP1_LE-WP2_LE":"8d58b534-54cc-4433-b98f-caf4978ad3b0","JOINT_N1_T":"8d618900-3e60-4a57-b32a-760ab4129a75","RC01-F01-060_Hull_shear_bay_N2_PC-N3_PS":"8d8ece5d-581b-43b2-a3ec-599aa4b3ce12","JOINT_WS2_TE":"8e7537c1-81b2-4098-88dc-b5a5f2059255","RC01-F01-104_Cockpit_protection_hoop_N3_CANOPY_L-N3_CANOPY_R":"8ef57152-d69f-42a0-a7b8-02cca2e25f5e","RC01-F01-132_Wing_spanwise_member_WP2_TE-WP3_TE":"8f824012-a4fb-44df-b3d2-915bcf8f6347","JOINT_WP3_LE":"90d9d0c4-7e35-4b58-ba5b-d4713665a0a4","RC01-F01-174_Wing_carry-through_JUNCTION_RS_S-WS0_RS":"9186f48e-c0fe-4d0e-acf7-601115638e39","JOINT_WP1_TE":"9237f047-faff-4460-ae4b-855c10c33305","RC01-F01-189_Duct_support_arm_N5_PS-FAN_P_LOW":"92985c4c-9dff-4533-bf79-c146a84aa634","JOINT_WS1_TE":"932360fb-d78c-4a6a-9776-2c498b591fc5","RC01-F01-109_Wing_rib_/_load_path_WP0_RS-WP0_TE":"955184b9-dc25-45a9-a4e1-1d6a4f3ca88a","JOINT_N0_SD":"96199f6d-4b05-429c-83b2-08444bffc6b2","RC01-F01-038_Hull_longitudinal_stringer_N1_PS-N2_PS":"9674543a-88f8-4876-8bfb-c0f800e8ae1e","JOINT_N2_PC":"96957e8a-cd28-4bbb-bde8-7b7240e0ade6","RC01-F01-145_Wing_rib_/_load_path_WS2_LE-WS2_FS":"96fb22e9-ee4c-4db1-b14e-5f45da53fda4","RC01-F01-126_Wing_rib_/_load_path_WP3_LE-WP3_FS":"9710caa1-cf6a-41a7-90f8-d527297a9b62","RC01-F01-127_Wing_rib_/_load_path_WP3_FS-WP3_RS":"97c2ed8c-04ff-4a08-ac7b-61a8f27fb6a4","RC01-F01-010_Hull_transverse_ring_N1_K-N1_SC":"981068fd-a831-4595-b00a-05c98e4e269f","RC01-F01-072_Hull_longitudinal_stringer_N3_PS-N4_PS":"988767ba-a83b-46ec-abbd-8d53caec0649","JOINT_WP0_RS":"98a2d84a-efc6-407b-a378-233f0b25a2df","JOINT_N5_SC":"9927d17b-7de2-4176-9f0f-77ee5a9785a3","RC01-F01-064_Hull_transverse_ring_N4_K-N4_SC":"9a184f0b-454c-4c3a-9d6b-69a319598cf7","JOINT_N1_PC":"9a4d5dca-f2f8-4f54-a28f-0f1572e19fc5","RC01-F01-017_Hull_longitudinal_stringer_N0_K-N1_K":"9b8414a9-a8e5-4aa0-bc9b-fbb54ca5a51c","JOINT_FLOAT_S_K":"9bd28375-b3bf-4bde-8d1a-44cf3da7f5e2","JOINT_N2_SS":"9c178391-22d6-4ef1-a3fa-48f4444eda38","RC01-F01-180_Float_braced_hanger_WS2_RS-FLOAT_S_K":"9cb2c344-1b05-4073-9c51-e9c7ecb6a905","RC01-F01-125_Wing_torsion_bay_WP1_RS-WP2_FS":"9ce7781f-02fe-4b06-af77-aaf6bedfb6f7","RC01-F01-056_Hull_longitudinal_stringer_N2_SS-N3_SS":"9d3e18ad-1a69-43a8-bb0d-5f3e60066859","JOINT_WP2_RS":"9e041d50-daf3-4f90-a442-03d98b84bbe0","RC01-F01-044_Hull_shear_bay_N1_SC-N2_SS":"9ef52d0d-bb8d-45f0-b390-8b399a549372","JOINT_N1_SD":"9f671f8e-5f8f-449a-b8ae-6d83c36296cb","JOINT_WS0_TE":"a0b76a96-08ac-4ebc-a9b3-f127b3f98f93","JOINT_N5_SS":"a19351a5-0f83-44bc-a7da-c5cee75f1c26","RC01-F01-083_Hull_transverse_ring_N5_SC-N5_SS":"a1c533f5-a214-4a3b-ad61-d55693f0fec1","JOINT_FAN_S_IN":"a1f51ccc-8def-4799-96cc-2fd74c469ab7","RC01-F01-004_Hull_transverse_ring_N0_SC-N0_SS":"a300fe1d-5017-456f-8288-3974a6a99c03","RC01-F01-176_Float_braced_hanger_WP2_RS-FLOAT_P_K":"a3569cc0-e4f4-4c0e-81fd-553c0c887bb4","JOINT_WP0_LE":"a431dd37-365a-4eba-a1c9-22b155261644","RC01-F01-136_Wing_rib_/_load_path_WS0_RS-WS0_TE":"a4e5f30f-be0a-4e81-aea0-982a49b09875","JOINT_N3_CANOPY_L":"a4f79e92-287d-4858-a434-e85d6fa9d19d","RC01-F01-103_Cockpit_protection_hoop_N3_SD-N3_CANOPY_R":"a56a4cfa-0d81-4a5b-bc54-a0fe8c350f09","RC01-F01-009_Hull_transverse_ring_N1_K-N1_PC":"a57cca0f-cf21-4262-bd05-5d5b410bbcf5","RC01-F01-098_Bulkhead_transverse_tie_N5_PS-N5_SS":"aa1dc21a-9d1f-4cd6-9cc5-a35bff84adac","JOINT_N5_PS":"abc93a3a-3e91-495d-9aa6-f04cabd1e7c5","RC01-F01-085_Hull_transverse_ring_N5_SS-N5_SD":"ac0aa769-8b67-413e-aaa6-625726aaf146","RC01-F01-134_Wing_rib_/_load_path_WS0_LE-WS0_FS":"aef0aab0-79a2-4ddb-8669-20b521afc2e5","RC01-F01-052_Hull_longitudinal_stringer_N2_K-N3_K":"af1ef912-9d27-4c9c-8e48-c07c986305c3","RC01-F01-042_Hull_longitudinal_stringer_N1_T-N2_T":"b08f055b-1b75-430e-93c5-d8e30c95951a","RC01-F01-122_Wing_spanwise_member_WP1_FS-WP2_FS":"b0eb7f26-f949-4c3e-a4fd-0f0883bdeb66","RC01-F01-039_Hull_longitudinal_stringer_N1_SS-N2_SS":"b3fe2009-3e1d-4b64-9a9e-33414e3cd8a5","RC01-F01-110_Wing_rib_/_load_path_WP1_LE-WP1_FS":"b4096237-2801-4663-8877-ced16e4d2a8b","RC01-F01-133_Wing_torsion_bay_WP2_RS-WP3_FS":"b50f2210-7474-4500-a409-d7ed720751b9","JOINT_N4_K":"b5fed7d5-3930-4725-a4ab-03566cd92c66","RC01-F01-020_Hull_longitudinal_stringer_N0_PS-N1_PS":"b6fedfb9-caae-4b61-8c1f-f4e00264489f","RC01-F01-137_Wing_rib_/_load_path_WS1_LE-WS1_FS":"b74c1f10-9335-4fa4-8bde-94df5a0ab19d","JOINT_N2_SC":"b76b63bf-fee5-4c5c-adad-1d2917813ddc","JOINT_N2_T":"b8275bd6-aba5-417b-aaac-7866dca27eac","RC01-F01-067_Hull_transverse_ring_N4_PD-N4_T":"b882945e-4b2b-4bea-b09c-8eddd8a7f281","JOINT_N5_PC":"b9b46ca4-ee76-40b3-a44f-0a071644a949","RC01-F01-148_Wing_spanwise_member_WS1_LE-WS2_LE":"ba37a1bc-1682-4977-9030-7d6fc501f62a","RC01-F01-001_Hull_transverse_ring_N0_K-N0_PC":"bb529808-8411-407a-8a04-609a0e7624e1","RC01-F01-199_Tail_longitudinal_brace_PYLON_T-TAIL_S_TE":"bbb397a5-017d-4192-8e65-1c466a2baee6","RC01-F01-172_Wing_carry-through_WP0_RS-JUNCTION_RS_P":"bc217c78-1b3d-4775-add5-a070e073fe09","RC01-F01-093_Hull_longitudinal_stringer_N4_PD-N5_PD":"bc9762b4-e32d-45bd-8edf-95f259b9c165","RC01-F01-129_Wing_spanwise_member_WP2_LE-WP3_LE":"bcb3d030-eab2-4ca6-84ee-5b133aad845e","JOINT_N4_SS":"be0614a8-6680-496b-ab03-2ad259ddc139","RC01-F01-190_Duct_support_brace_FAN_P_IN-FAN_P_LOW":"bf3b7b7f-06f0-4d0b-a3b2-df2375daeef9","JOINT_N3_PC":"c0e730b9-53b5-4e09-be9e-2c2bef4080dd","JOINT_WP1_RS":"c18a6218-ad8d-4acb-9097-e2c074deaf44","JOINT_N1_PD":"c1ffb1a7-924f-4890-ada7-f1b6c1a53dd5","JOINT_WS0_RS":"c25d0a22-7fbe-4149-a829-37200f1de966","RC01-F01-171_Hull_transverse_ring_JUNCTION_RS_S-N4_SD":"c2d2c625-25f2-439c-be7d-014e39f5241c","RC01-F01-080_Hull_transverse_ring_N5_K-N5_PC":"c367954c-8097-4b4f-a679-70c25ba7f52d","JOINT_N5_SD":"c3b7507c-1ec9-4beb-8920-f96ce2b2d85b","JOINT_JUNCTION_FS_P":"c522cc3a-51e1-4423-8c47-3b1447002148","RC01-F01-028_Hull_transverse_ring_N2_K-N2_SC":"c52f802f-90b4-42d2-b2cc-be7c11aa4e32","RC01-F01-128_Wing_rib_/_load_path_WP3_RS-WP3_TE":"c6386e74-607f-418b-a633-dcfaa8357ca1","RC01-F01-016_Hull_transverse_ring_N1_SD-N1_T":"c8b594e8-d4e0-4d6b-a7f7-6d84afd87fa6","RC01-F01-065_Hull_transverse_ring_N4_PC-N4_PS":"ca122015-502b-4eb3-9ee3-554f25998c09","JOINT_N2_PS":"cb26d680-3220-4ef9-8445-23b76630cccd","JOINT_N3_SS":"cb3b6cf0-0498-4d05-ba8e-5dde8834af7e","RC01-F01-036_Hull_longitudinal_stringer_N1_PC-N2_PC":"cbcda582-ddd5-451b-b2d4-c2f0de318154","JOINT_WP3_TE":"cc8587e5-48b0-4f61-817a-88319d96dacb","RC01-F01-152_Wing_torsion_bay_WS1_RS-WS2_FS":"cd06abdc-437a-4e44-bc25-8a7eeccc64f4","RC01-F01-002_Hull_transverse_ring_N0_K-N0_SC":"cd500441-7f6d-4d22-9bf1-ab8c8c219e7e","JOINT_FLOAT_S_F":"cdfe3692-245f-4fe4-8b6e-8c8d1cfd4171","JOINT_N2_K":"cf902eb2-ef74-4164-a222-ff1572fb6842","JOINT_FAN_P_IN":"d01c75cb-6e72-4d41-826f-d3cd71da7ba7","RC01-F01-025_Hull_shear_bay_N0_PC-N1_PS":"d28b7571-89f8-494d-8ecd-cfa22e81452b","RC01-F01-068_Hull_transverse_ring_N4_SD-N4_T":"d3a7f712-dabe-4e60-85d7-3c31cc5e56a4","RC01-F01-150_Wing_spanwise_member_WS1_RS-WS2_RS":"d3f37e7b-46fd-43e6-97b6-e67e147e18ce","RC01-F01-013_Hull_transverse_ring_N1_PS-N1_PD":"d564921f-8d8d-4bb0-b40e-4083ad7bc31a","RC01-F01-108_Wing_rib_/_load_path_WP0_FS-WP0_RS":"d749b668-e364-4d6e-8a9d-f46b71456770","JOINT_N1_K":"dacc5fe8-22af-4e2e-965d-144df36db2a8","RC01-F01-089_Hull_longitudinal_stringer_N4_PC-N5_PC":"db02c527-8b30-419e-8260-a7deea3cac71","JOINT_WS3_LE":"db1b78da-e2d5-43c6-b446-b477114794ab","RC01-F01-143_Wing_spanwise_member_WS0_TE-WS1_TE":"dbdbe845-ca00-4817-9a4f-7d4f52065499","RC01-F01-135_Wing_rib_/_load_path_WS0_FS-WS0_RS":"dc28a659-5a89-4048-88cd-4ffa43b637e3","RC01-F01-034_Hull_transverse_ring_N2_SD-N2_T":"dd4b95f3-0f26-41f0-80fc-6f0c575b8a4a","JOINT_WS3_RS":"ddcd506d-ea1b-4502-aa29-ed3745df179d","RC01-F01-178_Float_load_spreader_FLOAT_P_K-FLOAT_P_A":"deedbd42-e595-4433-812d-1afa3d2cde69","RC01-F01-120_Wing_rib_/_load_path_WP2_RS-WP2_TE":"e0ba4307-22b1-4c4e-bc81-839bc5f16eaa","RC01-F01-026_Hull_shear_bay_N0_SC-N1_SS":"e27199af-3f56-4d8f-a1d8-f99d9bf2be23","RC01-F01-073_Hull_longitudinal_stringer_N3_SS-N4_SS":"e2d94ebc-7db0-4e58-99a6-6d4f3de3e92d","RC01-F01-087_Hull_transverse_ring_N5_SD-N5_T":"e31b80d1-b4ca-4ec3-87ec-ac279b35c00f","RC01-F01-191_Duct_support_arm_PYLON_M-FAN_S_IN":"e37e8489-33c6-488b-af0b-25250ce4b68f","RC01-F01-032_Hull_transverse_ring_N2_SS-N2_SD":"e3b1ed20-384e-4e0f-81fc-a926238366bf","RC01-F01-091_Hull_longitudinal_stringer_N4_PS-N5_PS":"e4d0830e-3621-4824-89a2-b22b468e49c7","RC01-F01-158_Wing_spanwise_member_WS2_RS-WS3_RS":"e6106b59-1770-4f02-b63a-562a04a5a35f","JOINT_N0_K":"e6e7d271-fecf-4c0f-8f92-2f064337d783","JOINT_WP1_FS":"e70333f6-9127-4039-be26-a74107ab494e","JOINT_N3_PS":"e9c6a56b-86f6-4816-99a7-2570e31578c7","JOINT_N4_PC":"ea7480d4-3f64-4372-b957-8fc2c8b032c5","JOINT_PYLON_M":"ea88de8f-8341-45ad-a77d-c280c7cfdac0","RC01-F01-059_Hull_longitudinal_stringer_N2_T-N3_T":"eb82c55b-ef63-4f3e-ba7c-4d7bf8c12ded","RC01-F01-118_Wing_rib_/_load_path_WP2_LE-WP2_FS":"ebe66dc8-037f-4d7f-90c2-8e1962c08987","RC01-F01-169_Hull_transverse_ring_JUNCTION_RS_P-N4_PD":"ec022e2c-6628-4ee2-8f74-8049eab52224","RC01-F01-031_Hull_transverse_ring_N2_PS-N2_PD":"ed4490d7-4687-41ea-88c1-3309d1d0b4f5","JOINT_WS1_LE":"f0b7c471-5bd4-41ad-aa8b-fbd4ef64c2a0","RC01-F01-182_Float_load_spreader_FLOAT_S_K-FLOAT_S_A":"f10410c7-c350-4b1e-bf36-fd2f497f6c76","RC01-F01-186_Aft_propulsion_pylon_N5_PS-PYLON_M":"f2d0fbd8-9df4-4d97-a542-3857c70b2cc7","RC01-F01-075_Hull_longitudinal_stringer_N3_SD-N4_SD":"f2e3079f-d0d6-4715-9382-96db346e2c28","JOINT_WP1_LE":"f3628371-673d-4bf0-af1d-edf02fafc297","JOINT_JUNCTION_RS_P":"f47b6a19-1ca9-4ba7-95ef-d760daff529a","RC01-F01-168_Hull_transverse_ring_N4_PS-JUNCTION_RS_P":"f5216a47-25e0-426a-a8f7-a908dc5ee73e","RC01-F01-033_Hull_transverse_ring_N2_PD-N2_T":"f5a8abbc-fb46-4fd2-a330-70c9d729ccb0","RC01-F01-147_Wing_rib_/_load_path_WS2_RS-WS2_TE":"f6139d41-2456-4125-942a-6a11e2286a72","RC01-F01-100_Cockpit_protection_hoop_N2_SD-N2_CANOPY_R":"f74df751-cf71-4d10-8123-f1240db7c5c5","RC01-F01-082_Hull_transverse_ring_N5_PC-N5_PS":"f7ab6ec7-78db-46b9-b24b-b266d44aedc0","JOINT_N4_SD":"f96988e5-10ca-472c-b62a-b3da6a611642","RC01-F01-022_Hull_longitudinal_stringer_N0_PD-N1_PD":"fb6ef42f-6970-4c84-9bd2-47c2dc36b53b","JOINT_N0_T":"fb8e880d-c738-49ee-8c3d-dff336137c63","RC01-F01-154_Wing_rib_/_load_path_WS3_FS-WS3_RS":"fd946387-211e-4e7c-9c9a-4b265a589121","RC01-F01-062_Bulkhead_transverse_tie_N3_PS-N3_SS":"fdb41a34-7f71-4542-9321-af97a2b968eb","RC01-F01-053_Hull_longitudinal_stringer_N2_PC-N3_PC":"fe0acbf9-68da-40ce-af26-9d5d9abc69a9","RC01-F01-058_Hull_longitudinal_stringer_N2_SD-N3_SD":"fe9fbe75-966e-447b-833d-15c083c43143","JOINT_N0_PS":"ff122eb2-5c72-431b-9955-ae44d72ada77"}
for _obj in bpy.data.objects:
    _fixed=F01_SOURCE_ID_MAP.get(_obj.name)
    _obj['blendstra_id']=_fixed if _fixed else str(uuid.uuid5(uuid.NAMESPACE_URL,'vtx-rc01-f02:'+_obj.name))
print('RC01_FIXED_IDS',len(F01_SOURCE_ID_MAP),len(bpy.data.objects))


bpy.context.scene['RC01_revision']='F01-primary-frame';bpy.context.scene['RC01_member_count']=len(E)
bpy.context.scene['RC01_description']='Connected parametric skeleton. Not strength tested. No rotor/skins/moving joints.'
print('FRAME_RC01_F01_COMPLETE',len(E),'members',len(V),'nodes; connected:',len(seen))

# F03 isolated calm water hull/keel geometric reference. Builds only new objects;
# all F01/F02 parts remain identity-stable via source id manifest.
import uuid as _F03uuid
F03_COLLECTION=bpy.data.collections.new('RC01_F03_10_HYDROSTATIC_HULL')
bpy.context.scene.collection.children.link(F03_COLLECTION)
def _f03ring(st):
 name,x,w,k,deck=st
 return [(0.,k),(.80*w,k+.27*(deck-k)),(w,k+.70*(deck-k)),(.50*w,deck),
 (0,deck+.075),(-.50*w,deck),(-w,k+.70*(deck-k)),(-.80*w,k+.27*(deck-k))]
_F03verts=[(s[1],y,z) for s in ST for y,z in _f03ring(s)]
_F03faces=[]
for _j in range(len(ST)-1):
 for _k in range(8):
  _a=_j*8+_k;_b=_j*8+(_k+1)%8;_c=(_j+1)*8+_k;_d=(_j+1)*8+(_k+1)%8
  _F03faces += [(_a,_c,_b),(_b,_c,_d)]
for _k in range(1,7):_F03faces.append((0,_k,_k+1))
_F03base=(len(ST)-1)*8
for _k in range(1,7):_F03faces.append((_F03base,_F03base+_k+1,_F03base+_k))
mesh=bpy.data.meshes.new('RC01_F03_HULL_CLOSED_SURFACE_LOFT_MESH')
mesh.from_pydata(_F03verts,[],_F03faces);mesh.update()
import bmesh as _bm
_bmtest=_bm.new();_bmtest.from_mesh(mesh)
assert all(e.is_manifold for e in _bmtest.edges),'Non manifold hull'
_bmtest.free()
_mh=bpy.data.materials.new('F03 transparent hydro loft - not hull laminate')
_mh.use_nodes=True
_bs=_mh.node_tree.nodes.get('Principled BSDF')
_bs.inputs['Base Color'].default_value=(.10,.40,.49,1)
_bs.inputs['Alpha'].default_value=.32
_mh.diffuse_color=(.10,.40,.49,.32)
try:_mh.surface_render_method='DITHERED'
except:pass
_hull=bpy.data.objects.new('F03_HULL_WATERTIGHT_GEOMETRY_ONLY',mesh)
F03_COLLECTION.objects.link(_hull);_hull.data.materials.append(_mh)
_hull['blendstra_id']=str(_F03uuid.uuid5(_F03uuid.NAMESPACE_URL,'vtx-rc01-f03:closed_hull'))
_hull['F03_geometry'] = '48 vertices, 92 faces; manifold surface, nominal gross enclosed volume 4.807485243375001 m3'
_hull['F03_status']='CLOSED MESH ONLY - no bonded skin thickness, hatch seals or leak test'
_hull['F03_physics_coordinate']='body +X nose +Y starboard +Z up / future VTX +Y conversion required'
_mf=bpy.data.materials.new('F03 buoyant outboard sponson placeholder')
_mf.diffuse_color=(.14,.52,.56,1);_mf.use_nodes=True
_mf.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.14,.52,.56,1)
for _side,_sign in [('P',-1),('S',1)]:
 bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,location=(-.34,_sign*3.80,.42))
 _o=bpy.context.object
 _o.name='F03_SPN_'+_side+'_SEALED_VOLUME_CANDIDATE'
 _o.scale=(.56,.18,.14)
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 for _c in list(_o.users_collection):_c.objects.unlink(_o)
 F03_COLLECTION.objects.link(_o)
 _o.data.materials.append(_mf)
 _o['blendstra_id']=str(_F03uuid.uuid5(_F03uuid.NAMESPACE_URL,'vtx-rc01-f03:'+_o.name))
 _o['F03_status']='Buoyant sponson shape assumption, no ribs/laminate/hinge/impact proof'
 _o['F03_nominal_volume_m3']=(4/3)*math.pi*.56*.18*.14
F03_reference={'revision':'RC01-F03-01','source_parent':'F02 stable identity v832fd339',
 'gross_closed_hull_volume_m3':4.807485243375001,'estimated_waterline_body_z_m':.37433,
 'mass_budget_nominal_kg':900,
 'conditions':{'rho_freshwater_kg_m3':999.1,'g_m_s2':9.80665,'T_C':15,'p_Pa':101325,'calm_water':True},
 'only_geometric_waterproofness':True,'known_missing':['laminate/bond thickness','hull-frame joint interfaces','hatch and shaft seals','FEA','moving joint definition','CFD and planing pressure','final mass ledger']}
bpy.data.texts.new('RC01_F03_HYDRO_GEOMETRY.json').write(json.dumps(F03_reference,indent=2))
bpy.context.scene['RC01_revision']='F03 isolated water hull candidate'
print('F03_HULL_MANIFOLD_WITH_TWO_FLOATS',len(_F03verts),len(_F03faces))

