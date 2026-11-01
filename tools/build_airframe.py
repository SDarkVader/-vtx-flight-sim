"""Blender-only, reproducible geometry → mass ledger and live GLB derivative.

The master is never saved/overwritten. Mass is allocated by uniform surface
density WITHIN each P01–P11 budget: an explicit distribution hypothesis, not CAD
material mass. Triangle integrals give centroids and full inertia, not guessed CG.
"""
import bpy
import json
import math
import re
import sys
from pathlib import Path
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
deps = bpy.context.evaluated_depsgraph_get()
objects = list(bpy.data.objects)
byname = {o.name:o for o in objects}
mechanism=json.loads((ROOT/'inputs/live_mechanism.json').read_text())
repairs=[]
revision=1 if '--baseline' in sys.argv else (2 if '--r2' in sys.argv else (3 if '--r3' in sys.argv else (4 if '--r4' in sys.argv else (6 if '--r6' in sys.argv else 5))))
baseline_r4=json.loads((ROOT/'evidence/source/airframe_ledger_r4.json').read_text()) if revision>=5 else None
baseline_parts={p['id']:p for p in baseline_r4['parts']} if baseline_r4 else {}
repair_objects=objects if revision>=2 else []
previous_gear_area=None
previous_gear_path=ROOT/'evidence/source/r2_gear_area.json'

def fit_segment(o,a,b,reason,status='PROPOSED_ASSEMBLY_REPAIR_NOT_QUALIFIED_HARDWARE'):
    """A separately recorded proposed assembly repair, never a master overwrite."""
    a,b=Vector(a),Vector(b)
    before=[list(row) for row in o.matrix_world]
    local_z=[v.co.z for v in o.data.vertices]
    span=max(local_z)-min(local_z)
    direction=b-a
    rotation=Vector((0,0,1)).rotation_difference(direction.normalized()).to_matrix().to_4x4()
    matrix=Matrix.Translation((a+b)/2)@rotation@Matrix.Diagonal((1.,1.,direction.length/span,1.))
    o.animation_data_clear()
    o.matrix_world=matrix
    repairs.append(dict(id=o.get('blendstra_id'),name=o.name,reason=reason,
                        before_world_matrix=before,after_world_matrix=[list(row) for row in matrix],
                        proposed_endpoints_m=[list(a),list(b)],status=status))

def translate_part(o,dx,dy,dz,reason,status='PROPOSED_ASSEMBLY_REPAIR_NOT_QUALIFIED_HARDWARE'):
    """Translate an object in world space and record before/after provenance."""
    before=[list(row) for row in o.matrix_world]
    o.animation_data_clear()
    matrix=o.matrix_world.copy()
    matrix.translation+=Vector((dx,dy,dz))
    o.matrix_world=matrix
    repairs.append(dict(id=o.get('blendstra_id'),name=o.name,reason=reason,
                        before_world_matrix=before,after_world_matrix=[list(row) for row in matrix],
                        translation_delta_m=[float(dx),float(dy),float(dz)],status=status))

# R2 fixes independently verified zero-transform source defects. Keep all IDs.
# Endpoints come from source branch outlets, nacelle pivots and gearbox bounds;
# actuator anchor offsets are explicit new interface proposals, not recovered CAD.
if revision < 6:
    for i in range(1,5):
        pivot=np.array(byname[f'V3 P02 | F{i} INNER vector axis Y'].matrix_world.translation)
        if revision>=4:pivot[2]-=mechanism['bearing_below_rotor_m']
        x,y,z=pivot
        for o in repair_objects:
            if f'F{i} vertical torque shaft extension' in o.name:
                fit_segment(o,[x,y,.42],[x,y,2.07],'Connect radial branch output elevation to local gearbox input; source was at origin')
            if f'F{i} vectoring output shaft stub' in o.name:
                fit_segment(o,[x,y,2.16],[x,y,2.31],'Connect proposed local gearbox output to rotor bearing at measured pivot')
            for axis_index in (1,2):
                if f'F{i} actuator {axis_index} ' in o.name:
                    mount=mechanism['nacelle_actuators'][axis_index-1]
                    tip=pivot+np.array(mount['tip_m'])
                    base=pivot+np.array(mount['root_m'])
                    if 'compression body' in o.name:a,b=base,base+.60*(tip-base)
                    else:a,b=tip-.60*(tip-base),tip
                    fit_segment(o,a,b,'Proposed linear-actuator root and nacelle anchors; 0.25/0.35m lever offsets, overlapping barrel/piston')
            match=re.search(rf'F{i} redundant digital bus ([AB]) (\d+)',o.name)
            if match:
                offset=-.035 if match.group(1)=='A' else .035
                radial=pivot.copy();radial[2]=0;radial/=np.linalg.norm(radial)
                tangent=np.array([-radial[1],radial[0],0.])
                route=[np.array([0.,.53,.58]),radial*.85+np.array([0,0,1.14]),
                       radial*1.75+np.array([0,0,1.14]),radial*2.4+np.array([0,0,1.85]),pivot]
                k=int(match.group(2));a,b=route[k]+offset*tangent,route[k+1]+offset*tangent
                fit_segment(o,a,b,'Separate and route source buses along lower frame and protected rotor support')
for o in repair_objects:
    if 'Short-stroke fly-by-wire yoke stem' in o.name:
        fit_segment(o,[-.24,-.52,1.20],[-.24,-.73,1.245],'Connect source yoke base to source grip midpoint instead of origin')
    if 'Yoke lateral grips' in o.name:
        fit_segment(o,[-.40,-.73,1.245],[-.08,-.73,1.245],'Align source transverse yoke to the existing cushioned grips instead of origin')
if revision>=3:
    for o in objects:
        if 'replaceable contact foot' in o.name:
            before=[list(row) for row in o.matrix_world]
            matrix=o.matrix_world.copy();matrix.translation.z-=.25;o.matrix_world=matrix
            repairs.append(dict(id=o.get('blendstra_id'),name=o.name,reason='R3: extend gear 0.25 m so full stroke leaves ~50 mm fixed-underside clearance',before_world_matrix=before,after_world_matrix=[list(row) for row in matrix],status='PROPOSED_GEAR_EXTENSION; BUCKLING/RATINGS_UNKNOWN'))
        if 'sliding piston and hardstop' in o.name:
            zz=[v.co.z for v in o.data.vertices]
            a=o.matrix_world@Vector((0,0,min(zz)));b=o.matrix_world@Vector((0,0,max(zz)))
            if a.z>b.z:a,b=b,a
            a.z-=.25
            fit_segment(o,a,b,'R3: extend piston to lowered contact foot; retain upper pressure-body interface')
if 4 <= revision < 6:
    for o in objects:
        dz=0.
        if any(s in o.name for s in ['fixed X bearing support ring','fixed Y ring trunnion','static trunnion boss']):dz=-.28
        if 'pitch actuator ring' in o.name:dz=-.18
        if 'CV joint' in o.name or 'primary trunnion load head' in o.name or 'transverse hub support' in o.name:dz=-.28
        if dz:
            before=[list(row) for row in o.matrix_world]
            matrix=o.matrix_world.copy();matrix.translation.z+=dz;o.matrix_world=matrix
            repairs.append(dict(id=o.get('blendstra_id'),name=o.name,reason='R4: separate stationary bearing/pitch rings from the swept blades; gimbal pivot lowered 0.28m',before_world_matrix=before,after_world_matrix=[list(row) for row in matrix],status='PROPOSED_BEARING_STACK; LOADS/DEFLECTION_UNQUALIFIED'))
        if 'PRIMARY deep-angle axial leg' in o.name or 'UPPER nacelle tie' in o.name:
            zz=[v.co.z for v in o.data.vertices]
            a=o.matrix_world@Vector((0,0,min(zz)));b=o.matrix_world@Vector((0,0,max(zz)))
            if a.z>b.z:a,b=b,a
            b.z-=.28
            fit_segment(o,a,b,'R4: refit upper brace endpoint to the lowered bearing-stack load head; preserve lower frame anchor')

if revision>=6:
    mechanism=dict(mechanism)
    mechanism['bearing_below_rotor_m']=0.33
    mechanism['nacelle_actuators']=[
        dict(axis=1,root_m=[0.0,0.385,-0.280],tip_m=[0.0,0.365,0.180]),
        dict(axis=2,root_m=[0.385,0.0,-0.280],tip_m=[0.365,0.0,0.180]),
    ]
    # 1. Central 4-way reduction gearbox, P01 turboshaft & turbine input coupling
    for p01_name in [
        'P01 | M250 C30P class turboshaft schematic',
        'P01 | Compressor shell',
        'P01 | Turbine heat shielding',
    ]:
        translate_part(byname[p01_name],0.0,0.0,-0.120,
                       f'R6: lower {p01_name} 0.120m at x=0 to clear F2 radial shaft (z=0.420m) and P05 cabin gimbal rings while preserving lateral CG symmetry')
    translate_part(byname['P01 | Mount A'],-0.165,0.0,-0.120,
                   'R6: shift P01 Mount A -0.165m X and -0.120m Z outboard of F2 carbon shaft enclosure')
    translate_part(byname['P01 | Mount B'],+0.165,0.0,-0.120,
                   'R6: shift P01 Mount B +0.165m X and -0.120m Z symmetrically with Mount A')
    translate_part(byname['P03 | Four way reduction gearbox'],0.0,-0.025,-0.145,
                   'R6: lower central 4-way splitter 0.145m and shift -0.025m Y to clear P05 cabin gimbal rings while enclosing z=0.420m radial drive shafts')
    translate_part(byname['V2 P03 | Power turbine flexible coupling (schematic)'],0.0,-0.025,-0.120,
                   'R6: translate turbine output flexible coupling coaxially with lowered P01 M250 output shaft')
    translate_part(byname['V2 P03 | Transmission input flexible guard'],0.0,+0.040,-0.120,
                   'R6: translate transmission input flexible guard over turbine-to-splitter coupling without rotating local axis')

    # 2. Four point-symmetric radial transmission branches (F1..F4) seated in the z=0.420m lower truss plane
    branch_cfg={
        1:dict(axis='x',sign=+1,off=-0.155,z_shaft=0.420,r_in=0.260,r_out=2.460,bg_dx=0.0,bg_dy=-0.060,bg_dz=0.0,z_spindle_lo=0.600),
        3:dict(axis='x',sign=-1,off=+0.155,z_shaft=0.420,r_in=0.260,r_out=2.460,bg_dx=0.0,bg_dy=+0.060,bg_dz=0.0,z_spindle_lo=0.600),
        2:dict(axis='y',sign=+1,off=-0.210,z_shaft=0.420,r_in=0.260,r_out=2.460,bg_dx=-0.105,bg_dy=0.0,bg_dz=0.0,z_spindle_lo=0.600),
        4:dict(axis='y',sign=-1,off=+0.210,z_shaft=0.420,r_in=0.380,r_out=2.460,bg_dx=+0.105,bg_dy=0.0,bg_dz=0.0,z_spindle_lo=0.600),
    }
    for i,cfg in branch_cfg.items():
        s,off,zs=cfg['sign'],cfg['off'],cfg['z_shaft']
        if cfg['axis']=='x':
            p_shaft_a,p_shaft_b=[s*cfg['r_in'],off,zs],[s*cfg['r_out'],off,zs]
            p_enc_a,p_enc_b=[s*0.450,off,zs],[s*2.350,off,zs]
            b_dx,b_dy,b_dz=0.0,off,zs-0.420
        else:
            p_shaft_a,p_shaft_b=[off,s*cfg['r_in'],zs],[off,s*cfg['r_out'],zs]
            p_enc_a,p_enc_b=[off,s*0.450,zs],[off,s*2.350,zs]
            b_dx,b_dy,b_dz=off,0.0,zs-0.420
        fit_segment(byname[f'P03 | F{i} radial drive shaft'],p_shaft_a,p_shaft_b,
                    f'R6: point-symmetric radial drive shaft F{i} offset to clear P10 landing gear legs and P01 M250 turboshaft')
        fit_segment(byname[f'P03 | F{i} carbon shaft enclosure'],p_enc_a,p_enc_b,
                    f'R6: coaxial carbon shaft enclosure for offset radial branch F{i}')
        translate_part(byname[f'V2 P03 | F{i} shaft bearing at R1.19'],b_dx,b_dy,b_dz,
                       f'R6: inner radial shaft support bearing R1.19 co-translated with branch F{i}')
        translate_part(byname[f'V2 P03 | F{i} shaft bearing at R2.15'],b_dx,b_dy,b_dz,
                       f'R6: outer radial shaft support bearing R2.15 co-translated with branch F{i}')
        translate_part(byname[f'P03 | F{i} bevel gearhead'],cfg['bg_dx'],cfg['bg_dy'],cfg['bg_dz'],
                       f'R6: position F{i} 90-deg bevel gearhead to bridge offset radial shaft (z={zs:.3f}m) and vertical column axis (r=2.600m)')

    # 3. Upper Gimbal / CV Joint / Nacelle Stack for F1..F4 (gimbal pivot at z=1.980m, 0.330m below rotor hub)
    for i in range(1,5):
        orig_piv=Vector(byname[f'V3 P02 | F{i} INNER vector axis Y'].matrix_world.translation)
        px,py=orig_piv.x,orig_piv.y
        z_piv=1.980
        radial=Vector((px,py,0.0)).normalized()
        tangent=Vector((-radial.y,radial.x,0.0))
        cfg=branch_cfg[i]
        fit_segment(byname[f'V3 P03 | F{i} vertical torque shaft extension'],[px,py,cfg['z_spindle_lo']-0.015],[px,py,1.920],
                    f'R6: connect F{i} bevel gearhead vertical output to CV joint outer yoke at z=1.920m')
        fit_segment(byname[f'P03 | F{i} rising fan spindle'],[px,py,cfg['z_spindle_lo']+0.005],[px,py,1.880],
                    f'R6: coaxial stationary rising fan spindle housing for F{i} vertical shaft')
        for rname in [
            f'V3 P06 | F{i} fixed X bearing support ring',
            f'V3 P06 | F{i} fixed Y ring trunnion',
            f'V3 P06 | F{i} static trunnion boss -1',
            f'V3 P06 | F{i} static trunnion boss 1',
            f'V4 P06 | F{i} primary trunnion load head L',
            f'V4 P06 | F{i} primary trunnion load head R',
        ]:
            translate_part(byname[rname],0.0,0.0,-0.330,
                           f'R6: lower F{i} gimbal bearing ring/trunnion stack 0.330m (z_piv=1.980m) for 20-deg 360-deg tilt clearance')
        translate_part(byname[f'V4 P06 | F{i} transverse hub support'],-0.120*radial.x,-0.120*radial.y,-0.330,
                       f'R6: lower F{i} transverse hub support 0.330m and shift 0.120m inboard (r=2.480m) to clear vertical torque shaft')
        for bname in [
            f'V4 P06 | F{i} PRIMARY deep-angle axial leg L',
            f'V4 P06 | F{i} PRIMARY deep-angle axial leg R',
            f'V4 P06 | F{i} UPPER nacelle tie L',
            f'V4 P06 | F{i} UPPER nacelle tie R',
        ]:
            o=byname[bname]
            zz=[v.co.z for v in o.data.vertices]
            a=o.matrix_world@Vector((0,0,min(zz)));b=o.matrix_world@Vector((0,0,max(zz)))
            if a.z>b.z:a,b=b,a
            b.z-=0.330
            fit_segment(o,a,b,f'R6: refit F{i} upper structural brace endpoint to lowered trunnion load head (dz=-0.330m)')
        translate_part(byname[f'V3 P03 | F{i} CV joint outer yoke'],0.0,0.0,1.940-2.345,
                       f'R6: position F{i} CV joint lower yoke at z=1.940m below gimbal center (z=1.980m)')
        translate_part(byname[f'V3 P03 | F{i} torque transfer spherical CV primary'],0.0,0.0,1.980-2.252,
                       f'R6: center F{i} constant-velocity spherical torque ball exactly on 2-axis gimbal intersection (z=1.980m)')
        fit_segment(byname[f'V3 P03 | F{i} CV boot envelope'],[px,py,2.015],[px,py,2.085],
                    f'R6: fit F{i} CV boot envelope between gimbal CV ball (z=1.980m) and nacelle-local gearbox input (z=2.095m)')
        fit_segment(byname[f'V4 P03 | F{i} nacelle-local 7.5:1 reduction gearbox V4 candidate'],[px,py,2.095],[px,py,2.215],
                    f'R6: seat F{i} nacelle-local 7.5:1 epicyclic gearbox inside lower stator boss (z=2.095..2.215m)')
        fit_segment(byname[f'V3 P03 | F{i} vectoring output shaft stub'],[px,py,2.215],[px,py,2.310],
                    f'R6: connect F{i} nacelle-local gearbox output (z=2.215m) to rotor hub at z=2.310m')
        translate_part(byname[f'P02 | F{i} pitch actuator ring'],0.0,0.0,-0.105,
                       f'R6: position F{i} collective pitch swash/actuator ring at z=2.205m inside tilting nacelle envelope')
        fit_segment(byname[f'V2 P02 | F{i} collective pitch servo drive representation'],[px,py,2.095],[px,py,2.205],
                    f'R6: align F{i} collective pitch servo drive coaxially with tilting nacelle stator boss and pitch ring')
        act_dirs=[Vector((0.0,1.0,0.0)),Vector((1.0,0.0,0.0))]
        for axis_idx in (1,2):
            adir=act_dirs[axis_idx-1]
            base=Vector((px,py,z_piv))+0.385*adir+Vector((0.0,0.0,-0.280))
            tip=Vector((px,py,z_piv))+0.365*adir+Vector((0.0,0.0,+0.180))
            fit_segment(byname[f'V3 P06 | F{i} actuator {axis_idx} compression body'],base,base+0.38*(tip-base),
                        f'R6: place F{i} vectoring actuator {axis_idx} barrel at 0.385m lever offset outside r=0.304m gimbal ring')
            fit_segment(byname[f'V3 P06 | F{i} actuator {axis_idx} tensile piston'],tip-0.32*(tip-base),tip,
                        f'R6: place F{i} vectoring actuator {axis_idx} piston at 0.365m lever offset with 20-deg stroke separation')
            fit_segment(byname[f'V3 P06 | F{i} actuator {axis_idx} pivot clevis'],tip-0.28*(tip-base),tip,
                        f'R6: place F{i} vectoring actuator {axis_idx} upper clevis at nacelle gimbal attachment')
        for ab_letter,off_b in [('A',-0.035),('B',+0.035)]:
            r_np=np.array([radial.x,radial.y,0.0])
            t_np=np.array([tangent.x,tangent.y,0.0])
            route=[
                r_np*0.78+np.array([0.0,0.0,0.68]),
                r_np*1.15+np.array([0.0,0.0,0.72]),
                r_np*1.85+np.array([0.0,0.0,1.10]),
                r_np*2.38+np.array([0.0,0.0,1.80]),
                r_np*2.48+np.array([0.0,0.0,1.88]),
            ]
            for k in range(4):
                seg_obj=byname[f'V3 P11 | F{i} redundant digital bus {ab_letter} 0{k}']
                fit_segment(seg_obj,route[k]+off_b*t_np,route[k+1]+off_b*t_np,
                            f'R6: route F{i} redundant digital bus {ab_letter} outside cabin sphere to stationary hub support')

    # 4. Four Protected Fuel Tanks (P07), Saddle Links (P06) & Protected Supply Plumbing
    bay_signs={1:(+1,+1),2:(-1,+1),3:(-1,-1),4:(+1,-1)}
    dr_tank,dz_tank=-0.006,+0.115
    translate_part(byname['V2 P07 | Central fuel-feed manifold (schematic)'],0.0,-0.520,-0.020,
                   'R6: position central fuel-feed manifold at y=-0.520m, z=0.300m inside lower truss frame aft of 4-way gearbox and clear of P01 turbine')
    for bay,(sx,sy) in bay_signs.items():
        ur=Vector((sx/math.sqrt(2),sy/math.sqrt(2),0.0))
        dx,dy=dr_tank*ur.x,dr_tank*ur.y
        translate_part(byname[f'P07 | F{bay} protected fuel cell'],dx,dy,dz_tank,
                       f'R6: center F{bay} protected fuel tank at R=1.474m, Z=0.945m inside octagonal truss bay {bay} to eliminate shear-diagonal & vertical-web collisions')
        for part in [
            'energy-isolated saddle hoop 1',
            'energy-isolated saddle hoop 2',
            'flexible saddle liner 1',
            'flexible saddle liner 2',
            'clamp attach 1',
            'clamp attach 2',
            'accessible pickup and shutoff valve',
        ]:
            translate_part(byname[f'V4 P07 | BAY{bay} {part}'],dx,dy,dz_tank,
                           f'R6: co-translate BAY{bay} {part} with centered protected fuel cell')
        for gr in ['fuel guard rail -1','fuel guard rail 1']:
            translate_part(byname[f'V4 P07 | BAY{bay} {gr}'],dx,dy,dz_tank+0.012,
                           f'R6: co-translate BAY{bay} {gr} with tank and +12mm Z clearance above lower saddle link')
        for s_idx in (1,2):
            c_in=byname[f'V4 P07 | BAY{bay} saddle{s_idx} clevis-1']
            c_out=byname[f'V4 P07 | BAY{bay} saddle{s_idx} clevis1']
            translate_part(c_in,dx-0.052*ur.x,dy-0.052*ur.y,dz_tank,
                           f'R6: move BAY{bay} saddle{s_idx} inner clevis radially onto outer face of saddle hoop to eliminate tank wall penetration')
            translate_part(c_out,dx+0.052*ur.x,dy+0.052*ur.y,dz_tank,
                           f'R6: move BAY{bay} saddle{s_idx} outer clevis radially onto outer face of saddle hoop to eliminate tank wall penetration')
            p_cin=c_in.matrix_world.translation.copy()-0.015*ur
            p_cout=c_out.matrix_world.translation.copy()+0.015*ur
            for lohi in ('lower','upper'):
                lnk_in=byname[f'V4 P06 | BAY{bay} saddle{s_idx} triangulated link inner {lohi}']
                pts_in=[lnk_in.matrix_world@v.co for v in lnk_in.data.vertices]
                pts_in_sorted=sorted(pts_in,key=lambda p:p.x**2+p.y**2)
                ring_end_in=sum(pts_in_sorted[:8],Vector((0,0,0)))/8
                fit_segment(lnk_in,ring_end_in,p_cin+Vector((0,0,-0.020 if lohi=='lower' else +0.020)),
                            f'R6: refit BAY{bay} saddle{s_idx} inner {lohi} triangulated link from inner ring to external saddle clevis')
                lnk_out=byname[f'V4 P06 | BAY{bay} saddle{s_idx} triangulated link outer {lohi}']
                pts_out=[lnk_out.matrix_world@v.co for v in lnk_out.data.vertices]
                pts_out_sorted=sorted(pts_out,key=lambda p:p.x**2+p.y**2)
                ring_end_out=sum(pts_out_sorted[-8:],Vector((0,0,0)))/8
                fit_segment(lnk_out,ring_end_out,p_cout+Vector((0,0,-0.020 if lohi=='lower' else +0.020)),
                            f'R6: refit BAY{bay} saddle{s_idx} outer {lohi} triangulated link from outer ring to external saddle clevis')
        valve_pos=byname[f'V4 P07 | BAY{bay} accessible pickup and shutoff valve'].matrix_world.translation.copy()
        w0=valve_pos+Vector((0,0,-0.030))
        w1=Vector((sx*0.860,sy*0.860,0.650))
        w2=Vector((sx*0.540,sy*0.540-0.180,0.340))
        w3=Vector((sx*0.105,-0.520+sy*0.095,0.300))
        fit_segment(byname[f'V4 P07 | BAY{bay} protected supply pipe / segment1'],w0,w1,
                    f'R6: route BAY{bay} fuel supply pipe segment 1 from tank bottom valve below lower inner ring')
        fit_segment(byname[f'V4 P07 | BAY{bay} protected supply pipe / segment2'],w1,w2,
                    f'R6: route BAY{bay} fuel supply pipe segment 2 along lower truss bay clear of P01 turbine & P11 radiator')
        fit_segment(byname[f'V4 P07 | BAY{bay} protected supply pipe / segment3'],w2,w3,
                    f'R6: route BAY{bay} fuel supply pipe segment 3 to lowered central fuel-feed manifold')

bpy.context.view_layer.update()
groups = {'airframe': np.zeros(3), 'cabin':np.array([0.,0.,1.56])}
pivots = []
for i in range(1,5):
    p = np.array(byname[f'V3 P02 | F{i} INNER vector axis Y'].matrix_world.translation)
    if revision>=4:p[2]-=mechanism['bearing_below_rotor_m']
    pivots.append(p)
    groups[f'nacelle{i}'] = p
    groups[f'rotor{i}'] = np.array(byname[f'V3 P02 | F{i} rotor rotation shaft (slow visual)'].matrix_world.translation)
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
    moving_actuator=re.search(r'F(\d) actuator [12] (tensile piston|pivot clevis)',o.name)
    if moving_actuator:return 'nacelle'+moving_actuator.group(1)
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
    if revision>=5 and sys=='P06' and o.name.startswith('P06 | F'):
        excluded.append({'name':o.name,'id':o.get('blendstra_id'),'reason':'R5 experimental retirement of legacy box-spar module; newer triangulated primary frame retained',
                         'removed_allocation_kg':baseline_parts[o.get('blendstra_id')]['mass_kg']})
        continue
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
gear_area=sum(p['area_m2'] for p in parts if p['subsystem']=='P10')
if revision==2:
    previous_gear_path.write_text(json.dumps(dict(area_m2=gear_area,allocation_kg=42.),indent=2))
if revision>=3:
    previous_gear_area=json.loads(previous_gear_path.read_text())['area_m2']
    # Preserve the R2 areal mass density, including the added piston material.
    alloc['P10']=42.*gear_area/previous_gear_area
for sys,mass in alloc.items():
    sub=[p for p in parts if p['subsystem']==sys]
    area=sum(p['area_m2'] for p in sub)
    for p in sub:
        p['mass_kg']=baseline_parts[p['id']]['mass_kg'] if baseline_r4 else mass*p['area_m2']/area
        p['inertia_centroid_kg_m2']=(p['mass_kg']*np.array(p['inertia_per_kg_m2'])).tolist()
if baseline_r4:
    alloc={s:sum(p['mass_kg'] for p in parts if p['subsystem']==s) for s in alloc}

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
            revision=f'P0-V4A-assembly-r{revision}',frame='world/body +Z up; +X east, +Y north; source cabin faces -Y',
            allocation_method=('R4 per-part allocated masses preserved; 32 legacy P06 box-spar parts removed; exact retained surface triangle moments. NOT measured mass.' if baseline_r4 else 'Uniform areal density within each V4 subsystem; exact surface triangle moments. NOT measured mass.'),
            subsystem_allocations_kg=alloc,parts=parts,excluded=excluded,bodies=bodies,
            empty=aggregate(parts),rotor_pivots_m=[groups[f'rotor{i}'].tolist() for i in range(1,5)],
            nacelle_pivots_m=[p.tolist() for p in pivots],
            blade=blade_geometry,tanks=tanks,gear_stroke_target_m=.25,
            fuel_inner_radius_m=.18,fuel_inner_length_m=.48,assembly_repairs=repairs,
            mechanism=mechanism,
            gear_design_reference_mass_kg=(baseline_r4['empty']['mass_kg'] if baseline_r4 else aggregate(parts)['mass_kg'])+170+60,
            lightening_status=('R6 coherent transmission, 1.98m gimbal bearing stack, and centered bay fuel-tank placement on R5 lightened structure. Structural strength remains unverified.' if revision==6 else ('R5 legacy box spars retired; primary trusses/rings, drive, tanks and gear retained. Structural strength remains unverified.' if baseline_r4 else None)))
ledger_path=ROOT/('evidence/source/airframe_ledger_r6.json' if revision==6 else 'evidence/source/airframe_ledger.json')
repairs_path=ROOT/('evidence/source/assembly_repairs_r6.json' if revision==6 else 'evidence/source/assembly_repairs.json')
glb_path=ROOT/('public/assets/airframe-r6.glb' if revision==6 else 'public/assets/airframe-live.glb')
blend_path=(ROOT/'assets/derived')/('p0-v4-r6.blend' if revision==6 else 'p0-v4-live.blend')
ledger_path.write_text(json.dumps(ledger,indent=2))
repairs_path.write_text(json.dumps(repairs,indent=2))

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
bpy.ops.export_scene.gltf(filepath=str(glb_path),
                         export_format='GLB',export_animations=False,export_yup=False,
                         export_extras=True,export_cameras=False,export_lights=False,
                         use_active_scene=True)
derived=ROOT/'assets/derived';derived.mkdir(exist_ok=True)
live_scene['airframe_revision']=ledger['revision']
live_scene['mass_distribution']=ledger['allocation_method']
live_scene['physics_definition']=f"src/vtx/aircraft.py; {ledger_path.relative_to(ROOT).as_posix()}"
bpy.data.libraries.write(str(blend_path),{live_scene},fake_user=True)
print('BUILD_AIRFRAME',len(parts),'mapped parts',len(excluded),'presentation exclusions')
print('EMPTY',ledger['empty'],'BLADE',blade_geometry)
print('BODIES',[(k,round(v['mass_kg'],3)) for k,v in bodies.items()])
