"""VTX Phantom A10: split-level telescopic wing cassette -> both deployed wings at ONE height.

A9 stowed the two wings stacked (right in the upper cell, left in the lower cell), so the deployed
chord planes sat 0.118 m apart. A10 keeps A9's tongue length (1.05 m) and lock-station spacing
(0.94 m) but re-arranges the sleeve into two LEVELS instead of two CELLS:

  * upper "panel level" (A9 upper-cell height, z 0.948..1.051): both wing PANELS, each on its own
    side only. Panels never cross the centreline (stroke 1.205 m, stowed roots at |y| 0.026), so
    both can share one level -> common deployed chord plane by construction.
  * lower "tongue level" (z 0.830..0.944): two fore/aft CHANNELS split by a spanwise divider spar.
    Right tongue runs in the front channel, left tongue in the rear channel; only the tongues cross
    the centreline, side by side in x, never stacked.
  * a Ti root joggle frame (riser) on each wing joins the panel root (upper level) to its tongue
    (lower level).

Reuses the A9 builder by import (A9_IMPORT_ONLY=1) with patched constants; A9 itself is untouched.
  blender -b --disable-autoexec assets/source/phantom-a8/phantom-a8.blend \
      --python tools/phantom/build_a10_cassette.py -- assets/derived/phantom-a10-cassette.blend
Kinematic CAD only: not FEA/CFD qualified. Loads: engineering/phantom/wing_loads.py case A10_split_level.
"""
import bpy
import bmesh
import json
import math
import os
import sys
import importlib.util
from mathutils import Vector, Matrix

os.environ['A9_IMPORT_ONLY'] = '1'
_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('build_a9_cassette', os.path.join(_here, 'build_a9_cassette.py'))
a9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a9)

REV = 'A10'
a9.REV = REV
SC = a9.SC
BAY_X, WALL = a9.BAY_X, a9.WALL
Z_BOT, Z_MID, Z_TOP = a9.Z_BOT, a9.Z_MID, a9.Z_TOP
UPPER = (Z_MID + WALL / 2, Z_TOP - WALL)          # A9 upper cell = A10 panel level, both sides
a9.CELL = {'R': UPPER, 'L': UPPER}
STROKE = 1.205
a9.STROKE = STROKE
C_TIP = 0.42
Y_TIP = 2.429
a9.WING = dict(a9.WING, y_tip=Y_TIP, c_tip=C_TIP, x_le_tip=-1.46 + C_TIP)
WING = a9.WING
PIN_STATIONS = a9.PIN_STATIONS
PIN_R = a9.PIN_R
TONGUE_LEN = a9.TONGUE_LEN
# lower level
Z_FLOOR = Z_BOT + WALL                  # 0.830 bottom-plate top
X_DIV = 0.5 * (BAY_X[0] + BAY_X[1])     # -1.0555 divider centre
DIV_T = 0.015
CH = {'R': (X_DIV + DIV_T / 2, BAY_X[1]), 'L': (BAY_X[0], X_DIV - DIV_T / 2)}   # channel inner x (aft, fwd)
TZ = (0.846, 0.941)                     # tongue z
ZP = 0.900                              # lock pin axis z
ZS = 0.864                              # drive screw axis z
SCREW_R = 0.010
DIV_TOP = 0.944


def tongue_x(side):
    a, b = CH[side]
    return a + 0.010, b - 0.010


def build_wing(side, coll):
    s = 1 if side == 'R' else -1
    slide, surfaces, zc = a9.build_wing(side, coll)
    # drop the A9 full-chord tongue, front pins and nut carriage; A10 replaces them below
    for ob in list(bpy.data.objects):
        n = ob.name
        if n.startswith(f'{REV}_WING_{side}_TONGUE') or n.startswith(f'{REV}_WING_{side}_LOCK_PIN_FRONT') or \
                n.startswith(f'{REV}_JOINT_WING_{side}_LOCK_FRONT') or n.startswith(f'{REV}_WING_{side}_SLIDE_NUT'):
            bpy.data.objects.remove(ob, do_unlink=True)
    M = a9.MAT
    y_plate = WING['y_root'] - 0.008
    x0, x1 = tongue_x(side)
    y_in = y_plate - TONGUE_LEN
    lo_y, hi_y = sorted((s * y_in, s * y_plate))
    tongue = a9.box(f'{REV}_WING_{side}_TONGUE_CARRY_THROUGH_BOX', (x0, lo_y, TZ[0]), (x1, hi_y, TZ[1]), coll, M['cfrp'], slide,
                    dict(role=f'half-chord root tongue in the {"front" if side == "R" else "rear"} channel of the tongue level: '
                              'wing bending reacted as a spanwise couple between lock stations 0.94 m apart',
                         mass_kg=7.6, mass_basis='DERIVED wing_loads.py A10 tongue check (0.095 m deep, 0.39 m wide) incl. Ti lug inserts'))
    # screw bore through the whole tongue, pin bores at both faces of each station
    cut = a9.cylinder('cut', (0.5 * (x0 + x1), s * (y_in - 0.05), ZS), (0.5 * (x0 + x1), s * (y_plate + 0.05), ZS), SCREW_R + 0.0015, coll)
    a9.apply_boolean(tongue, cut)
    bpy.data.objects.remove(cut)
    # root joggle frame: carries panel bending/shear from the panel level down into the tongue
    ry0, ry1 = sorted((s * (y_plate - 0.030), s * y_plate))
    jog = a9.box(f'{REV}_WING_{side}_ROOT_JOGGLE_FRAME', (x0, ry0, TZ[0] + 0.01), (x1, ry1, UPPER[0] + 0.010), coll, M['ti'], slide,
           dict(role='Ti root joggle frame: joins panel root rib (panel level) to the tongue (tongue level); continuous bending/shear path',
                mass_kg=2.1, mass_basis='SYNTHETIC part mass'))
    cut = a9.cylinder('cut', (0.5 * (x0 + x1), s * (y_in - 0.05), ZS), (0.5 * (x0 + x1), s * (y_plate + 0.05), ZS), SCREW_R + 0.0015, coll)
    a9.apply_boolean(jog, cut)
    bpy.data.objects.remove(cut)
    # guide shoes (PTFE-lined, captive on floor rails) at both ends of the tongue
    xm = 0.5 * (x0 + x1)
    for k, yy in enumerate((y_in + 0.05, y_plate - 0.08)):
        for xr in (x0 + 0.06, x1 - 0.06):
            ylo, yhi = sorted((s * (yy - 0.04), s * (yy + 0.04)))
            a9.box(f'{REV}_WING_{side}_GUIDE_SHOE_{k}{"F" if xr > xm else "A"}', (xr - 0.020, ylo, Z_FLOOR + 0.011), (xr + 0.020, yhi, TZ[0] + 0.002),
                   coll, M['act'], slide, dict(part='PTFE-lined guide shoe, captive on floor rail (1 mm running clearance)', mass_kg=0.12))
    # lock pins: all four carried by the tongue (R: front wall + divider; L: divider + rear-wall EMAs as A9)
    for st in PIN_STATIONS:
        yy = s * st
        tag = 'OUT' if st > 1 else 'IN'
        faces = [('FRONT', x1, +1), ('REAR', x0, -1)]   # identical on both wings (mass/stiffness matching)
        for face, xf, d in faces:
            ax = (d, 0, 0)
            jp = a9.empty(f'{REV}_JOINT_WING_{side}_LOCK_{face}_{tag}', (xf - d * 0.05, yy, ZP), coll, axes=ax, parent=slide, props=dict(
                joint_type='slide', axis_world=[d, 0, 0], range_m=[-0.07, 0.0], ref_value_m=0.0, ref_pose='locked (as built)',
                actuator='tongue-mounted lock EMA (irreversible screw + spring), dual proximity sensors',
                engages={('R', 'FRONT'): 'front wall bushing', ('R', 'REAR'): 'divider spar bushing',
                         ('L', 'FRONT'): 'divider spar bushing', ('L', 'REAR'): 'rear wall bushing'}[(side, face)]))
            a9.cylinder(f'{REV}_WING_{side}_LOCK_PIN_{face}_{tag}', (xf + d * 0.012, yy, ZP), (xf - d * 0.108, yy, ZP), PIN_R, coll,
                        M['steel'], jp, dict(part='hollow pin 32/22 mm PH13-8Mo, double shear in Ti lug', mass_kg=0.35))
            cut = a9.cylinder('cut', (xf + d * 0.02, yy, ZP), (xf - d * 0.20, yy, ZP), PIN_R + 0.002, coll)
            a9.apply_boolean(tongue, cut)
            bpy.data.objects.remove(cut)
        # station lock EMA inside the tongue, offset inboard of the pins
        ye = s * (st - 0.06)
        a9.cylinder(f'{REV}_WING_{side}_LOCK_EMA_{tag}', (x0 + 0.03, ye, ZP), (x1 - 0.03, ye, ZP), 0.018, coll, M['act'], slide,
                    dict(part='station lock EMA + toggle yoke driving the station pins', mass_kg=0.8))
    # rotating-nut drive on the tongue's inboard end (stationary screw passes through)
    yn0, yn1 = sorted((s * (y_in - 0.06), s * (y_in - 0.002)))
    nut = a9.cylinder(f'{REV}_WING_{side}_SLIDE_ROTATING_NUT_AND_BEARINGS', (xm, yn0, ZS), (xm, yn1, ZS), 0.028, coll, M['act'], slide,
                      dict(part='rotating ball nut in angular-contact bearing pair (the slide bearing of the drive)', mass_kg=0.9))
    cut = a9.cylinder('cut', (xm, yn0 - 0.01, ZS), (xm, yn1 + 0.01, ZS), SCREW_R + 0.0015, coll)
    a9.apply_boolean(nut, cut)
    bpy.data.objects.remove(cut)
    xmot = xm + (0.075 if side == 'R' else -0.075)
    a9.cylinder(f'{REV}_WING_{side}_SLIDE_MOTOR', (xmot, yn0, ZS + 0.012), (xmot, yn1, ZS + 0.012), 0.024, coll, M['act'], slide,
                dict(part='slide BLDC motor + power-off brake + resolver, belt to nut', mass_kg=1.6))
    slide['note'] = '0 = deployed, root plate seated on mouth flange (hard stop); -1.205 = stowed (inboard elastomer stop)'
    slide['range_m'] = [-STROKE, 0.0]
    slide['actuator'] = 'rotating-nut ball screw (stationary 20 mm screw, 40 mm lead), 2.5 kN stall, 0.30 m/s max, brake on loss of power'
    return slide, surfaces, zc


def build_sleeve(coll):
    M = a9.MAT
    x0, x1 = BAY_X[0] - WALL, BAY_X[1] + WALL
    yl = a9.Y_FLANK - 0.007
    a9.box(f'{REV}_SLEEVE_BOTTOM_PLATE', (x0, -yl, Z_BOT), (x1, yl, Z_BOT + WALL), coll, M['cfrp'])
    a9.box(f'{REV}_SLEEVE_TOP_PLATE', (x0, -yl, Z_TOP - WALL), (x1, yl, Z_TOP), coll, M['cfrp'])
    front = a9.box(f'{REV}_SLEEVE_FRONT_WALL', (BAY_X[1], -yl, Z_BOT), (x1, yl, Z_TOP), coll, M['cfrp'])
    rear = a9.box(f'{REV}_SLEEVE_REAR_WALL', (x0, -yl, Z_BOT), (BAY_X[0], yl, Z_TOP), coll, M['cfrp'])
    div = a9.box(f'{REV}_SLEEVE_DIVIDER_SPAR', (X_DIV - DIV_T / 2, -yl, Z_FLOOR), (X_DIV + DIV_T / 2, yl, DIV_TOP), coll, M['cfrp'])
    for side in ('R', 'L'):
        s = 1 if side == 'R' else -1
        fl = a9.box(f'{REV}_SLEEVE_{side}_MOUTH_FLANGE_STOP', (BAY_X[0], min(s * a9.Y_FLANGE[0], s * a9.Y_FLANGE[1]), Z_FLOOR),
                    (BAY_X[1], max(s * a9.Y_FLANGE[0], s * a9.Y_FLANGE[1]), Z_TOP - WALL), coll, M['ti'])
        cut = a9.slot_cutter(side, 0.003, (s * 1.20, s * 1.30))
        a9.apply_boolean(fl, cut)
        bpy.data.objects.remove(cut)
        for st in PIN_STATIONS:
            yy = s * st
            walls = [(front, BAY_X[1] - 0.01, x1 + 0.01), (div, X_DIV - 0.02, X_DIV + 0.02)] if side == 'R' else \
                    [(div, X_DIV - 0.02, X_DIV + 0.02), (rear, x0 - 0.01, BAY_X[0] + 0.01)]
            for wall, xa, xb in walls:
                cut = a9.cylinder('cut', (xa, yy, ZP), (xb, yy, ZP), PIN_R + 0.0062, coll)
                a9.apply_boolean(wall, cut)
                bpy.data.objects.remove(cut)
    parts = [ob for ob in coll.objects if ob.name.startswith(f'{REV}_SLEEVE')]
    mass = 0.0
    for ob in parts:
        lo, hi = a9.world_bounds(ob)
        d = sorted(hi[i] - lo[i] for i in range(3))
        mass += (a9.SANDWICH_KG_M2 * d[1] * d[2]) if ob.active_material == M['cfrp'] else 4430.0 * d[0] * d[1] * d[2] * 0.5
    merge(parts, f'{REV}_SLEEVE_CARRY_THROUGH_BOX', coll, dict(
        role='split-level CFRP sandwich sleeve (1.5/12/1.5 mm): panel level over two tongue channels split by a spanwise divider spar; '
             'Ti mouth flanges = outboard hard stops; the wing carry-through box',
        mass_kg=round(mass, 2), mass_basis='DERIVED: sandwich areal mass x panel areas + Ti flanges (50% solidity)'))
    # fixed running gear: floor rails, bushings, screws and end anchors, inboard stops
    for side in ('R', 'L'):
        s = 1 if side == 'R' else -1
        tx0, tx1 = tongue_x(side)
        for k, xr in enumerate((tx0 + 0.06, tx1 - 0.06)):
            a9.box(f'{REV}_SLEEVE_{side}_FLOOR_RAIL_{k}', (xr - 0.010, -yl + 0.01, Z_FLOOR), (xr + 0.010, yl - 0.01, Z_FLOOR + 0.010), coll,
                   M['ti'], props=dict(part='Ti guide rail bonded/bolted to the floor sandwich', mass_kg=0.9))
        xm = 0.5 * (tx0 + tx1)
        a9.cylinder(f'{REV}_SLEEVE_{side}_STATIONARY_SCREW', (xm, -a9.Y_FLANGE[0], ZS), (xm, a9.Y_FLANGE[0], ZS), SCREW_R, coll, M['steel'],
                    props=dict(part='stationary pre-tensioned ball screw 20 mm, 40 mm lead, anchored in both mouth flanges', mass_kg=2.2))
        ys = -s * (TONGUE_LEN + STROKE - WING['y_root'] + 0.008 + 0.075)
        ylo, yhi = sorted((ys, ys - s * 0.03))
        a9.box(f'{REV}_SLEEVE_{side}_INBOARD_ELASTOMER_STOP', (tx1 - 0.10, ylo, TZ[0]), (tx1 - 0.02, yhi, TZ[0] + 0.05), coll, M['act'],
               props=dict(part='inboard elastomer stop (stowed hard stop)', mass_kg=0.2))
        for st in PIN_STATIONS:
            yy = s * st
            xs = [(BAY_X[1], BAY_X[1] + WALL)] if side == 'R' else [(BAY_X[0] - WALL, BAY_X[0])]
            xs.append((X_DIV - DIV_T / 2, X_DIV + DIV_T / 2))
            for xa, xb in xs:
                b = a9.cylinder(f'{REV}_SLEEVE_{side}_BUSHING_{"OUT" if st > 1 else "IN"}_{"F" if xa > -0.9 else ("D" if xa > -1.2 else "A")}',
                                (xa, yy, ZP), (xb, yy, ZP), PIN_R + 0.0060, coll, M['steel'],
                                props=dict(part='flanged self-lubricating bushing (lined) for lock pin', mass_kg=0.1))
                cut = a9.cylinder('cut', (xa - 0.01, yy, ZP), (xb + 0.01, yy, ZP), PIN_R + 0.0015, coll)
                a9.apply_boolean(b, cut)
                bpy.data.objects.remove(cut)


def merge(parts, name, coll, props):
    bm = bmesh.new()
    mats_used = []
    for ob in parts:
        me = ob.data.copy()
        me.transform(ob.matrix_world)
        for p in me.polygons:
            p.material_index = len(mats_used)
        mats_used.append(ob.active_material)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        bpy.data.objects.remove(ob)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats_used:
        me.materials.append(m)
    return a9.link(bpy.data.objects.new(name, me), coll, props=props)


def build_door(side, coll):
    """Both doors as the A9 right door: hinged along X at the panel-level sill, flip 180 deg outward onto the blank lower face."""
    s = 1 if side == 'R' else -1
    yo = s * (a9.Y_FLANK + 0.0075)
    hinge = a9.empty(f'{REV}_JOINT_HATCH_{side}', (-1.05, yo, Z_MID), coll, axes=(s, 0, 0), props=dict(
        joint_type='hinge', axis_world=[s, 0, 0], range_deg=[-180, 0], ref_value_deg=-180, ref_pose='open (flight)',
        positive='right-hand about axis_world', rate_deg_s=180, actuator='rotary EMA + over-centre latch, 25 N m stall',
        latch_load_at_VD_N=2105))
    z1 = UPPER[1]
    M = a9.MAT
    a9.box(f'{REV}_HATCH_{side}_FLUSH_DOOR', (BAY_X[0] - 0.004, min(yo, yo - s * 0.006), Z_MID + 0.0015),
           (BAY_X[1] + 0.004, max(yo, yo - s * 0.006), z1 + 0.003), coll, M['body'], hinge,
           dict(role='flush slot door; flips 180 deg outward to lie on the blank lower sleeve face', mass_kg=0.8))
    a9.box(f'{REV}_HATCH_{side}_AMBER_EDGE', (BAY_X[0] - 0.004, min(yo, yo + s * 0.002), z1 - 0.004),
           (BAY_X[1] + 0.004, max(yo, yo + s * 0.002), z1 + 0.003), coll, M['amber'], hinge)
    # fixed hinge knuckles + hatch EMA housing (aft of the door, inside the flank line)
    for k, xk in enumerate((BAY_X[1] + 0.02, BAY_X[0] - 0.02)):
        a9.cylinder(f'{REV}_HATCH_{side}_HINGE_KNUCKLE_{k}', (xk - 0.012, yo + s * 0.0035, Z_MID), (xk + 0.012, yo + s * 0.0035, Z_MID),
                    0.0035, coll, M['ti'], props=dict(part='hatch hinge knuckle (fixed half)', mass_kg=0.05))
    return hinge


def build_supports(coll):
    """Ti posts under the front wall, divider spar and rear wall, with flanged top/base fittings and
    diagonal braces (Warren truss in the |y| = 0.635 planes): sill -> post -> sleeve with real joints."""
    hull = bpy.data.objects['PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL']
    M = a9.MAT
    tmp = a9.collection(f'{REV}_TMP')
    xs = (-0.70, X_DIV, -1.30)
    for s in (1, -1):
        sd = 'R' if s > 0 else 'L'
        for x, tag in zip(xs, 'FDA'):
            lo, hi = (x - 0.03, s * 0.635 - 0.028, 0.596), (x + 0.03, s * 0.635 + 0.028, Z_BOT - 0.0105)
            a9.box(f'{REV}_SLEEVE_SUPPORT_POST_{sd}_{tag}', lo, hi, coll, M['ti'],
                   props=dict(role='sleeve support post into torsion sill (vertical shear + roll couple to tub)', mass_kg=0.9))
            a9.box(f'{REV}_SLEEVE_SUPPORT_TOP_FITTING_{sd}_{tag}', (x - 0.05, s * 0.635 - 0.029, Z_BOT - 0.010),
                   (x + 0.05, s * 0.635 + 0.029, Z_BOT - 0.0005), coll, M['ti'],
                   props=dict(part='flanged top fitting: 4 bolts into sleeve floor insert', mass_kg=0.35))
            a9.box(f'{REV}_SLEEVE_SUPPORT_BASE_FITTING_{sd}_{tag}', (x - 0.05, s * 0.635 - 0.03, 0.5855),
                   (x + 0.05, s * 0.635 + 0.03, 0.596), coll, M['ti'],
                   props=dict(part='base shoe: bolted to torsion-sill cap', mass_kg=0.3))
            cut = a9.box('cut', (x - 0.053, s * 0.635 - 0.048, 0.58), (x + 0.053, s * 0.635 + 0.048, Z_BOT + 0.001), tmp)
            a9.apply_boolean(hull, cut)
            bpy.data.objects.remove(cut)
        for k, (xa, xb) in enumerate(((xs[0], xs[1]), (xs[1], xs[2]))):
            p0 = (xa - 0.048 * (1 if xb < xa else -1), s * 0.635, 0.610)
            p1 = (xb + 0.048 * (1 if xb < xa else -1), s * 0.635, Z_BOT - 0.025)
            a9.cylinder(f'{REV}_SLEEVE_SUPPORT_BRACE_{sd}_{k}', p0, p1, 0.012, coll, M['ti'],
                        props=dict(part='Ti tube diagonal brace with end clevises (triangulates posts: fore/aft and pitch loads)', mass_kg=0.6))
            cut = a9.cylinder('cut', p0, p1, 0.016, tmp)
            a9.apply_boolean(hull, cut)
            bpy.data.objects.remove(cut)


def animate(wings, doors, canards):
    T, END = a9.T, a9.END
    for side, (slide, surfaces, zc) in wings.items():
        s = 1 if side == 'R' else -1
        y_dep = slide.location.y
        y_st = y_dep - s * STROKE
        a9.key(slide, 'location', 1, [(1, y_st), (T['slide'][0], y_st), (T['slide'][1], y_dep), (T['slide_in'][0], y_dep),
                                      (T['slide_in'][1], y_st), (END, y_st)])
        for ob in SC.objects:
            if ob.name.startswith(f'{REV}_JOINT_WING_{side}_LOCK_'):
                d = ob['axis_world'][0]
                x_lock = ob.location.x
                x_free = x_lock - d * 0.07
                a9.key(ob, 'location', 0, [(1, x_free), (T['lock'][0], x_free), (T['lock'][1], x_lock), (T['unlock'][0], x_lock),
                                           (T['unlock'][1], x_free), (END, x_free)])
        fh, _ = surfaces['FLAP']
        ah, _ = surfaces['AILERON']
        dg = math.radians
        rx = fh.rotation_euler.x
        a9.key(fh, 'rotation_euler', 0, [(1, rx), (T['flap'][0], rx), (T['flap'][1], rx + dg(30)), (T['flap'][2], rx + dg(30)),
                                         (T['flap'][3], rx), (END, rx)])
        rx = ah.rotation_euler.x
        a = T['ail']
        a9.key(ah, 'rotation_euler', 0, [(1, rx), (a[0], rx), (a[1], rx + s * dg(20)), (a[2], rx - s * dg(20)), (a[3], rx + s * dg(10)),
                                         (a[4], rx), (END, rx)])
    for side, h in doors.items():
        r0 = h.rotation_euler.x
        a9.key(h, 'rotation_euler', 0, [(1, r0), (T['door'][0], r0), (T['door'][1], r0 - math.pi), (T['door_close'][0], r0 - math.pi),
                                        (T['door_close'][1], r0), (END, r0)])
    for side, (fold, pitch) in canards.items():
        s = 1 if side == 'R' else -1
        z0 = fold.rotation_euler.z
        st = z0 + s * math.pi / 2
        a9.key(fold, 'rotation_euler', 2, [(1, st), (T['canard_unfold'][0], st), (T['canard_unfold'][1], z0), (T['canard_fold'][0], z0),
                                           (T['canard_fold'][1], st), (END, st)])
        p0 = pitch.rotation_euler.x
        c = T['cpitch']
        a9.key(pitch, 'rotation_euler', 0, [(1, p0), (c[0], p0), (c[1], p0 + math.radians(20)), (c[2], p0 - math.radians(15)),
                                            (c[3], p0), (END, p0)])
    SC.frame_start, SC.frame_end = 1, END
    SC.render.fps = a9.FPS


HANDOVER_AERO = dict(
    wing=dict(S_ref_m2=None, S_exposed_each_m2=None, span_m=round(2 * Y_TIP, 3), mac_m=None, x_ac_mac_m=None, y_mac_m=None,
              ac_height_R_m=None, ac_height_L_m=None, section='NACA 2411 -> 2410 (stand-in)', incidence_deg=0.0,
              CLalpha_per_rad_M0=None, CLmax_clean=1.2, CLmax_flap=1.6, cm0=-0.04,
              basis='DERIVED/SYNTHETIC, wing_loads.py A10_split_level; ac heights MEASURED-K from the A10 panels'),
    aileron=dict(eta=[0.55, 0.95], area_each_m2=None, cf_c=0.28, tau=0.64, Ch_delta=-0.70, Ch_alpha=-0.35),
    flap=dict(eta=[0.05, 0.50], area_each_m2=None, cf_c=0.28, tau=0.64),
    canard=dict(area_each_m2=0.278, x_pivot_m=1.80, y_root_m=1.26, y_tip_m=1.84, z_m=0.95, section='NACA 0009', CLalpha_per_rad=3.0,
                pivot_frac_mac=0.25))


def main():
    a9.mats()
    removed = a9.retire_a8()
    changed = a9.cut_conflicts(set())
    coll_s = a9.collection(f'{REV}_01 SPLIT-LEVEL WING CASSETTE (SLEEVE = CARRY-THROUGH)')
    coll_w = a9.collection(f'{REV}_02 WINGS FLAPS AILERONS (COMMON HEIGHT)')
    coll_c = a9.collection(f'{REV}_03 TWO-AXIS NOSE CANARDS')
    coll_b = a9.collection(f'{REV}_04 CASSETTE SHOULDERS, HATCHES, INDUCTION')
    a9.build_shoulders_and_hull(coll_b, removed)
    build_sleeve(coll_s)
    build_supports(coll_s)
    wings, doors, canards = {}, {}, {}
    for side in ('R', 'L'):
        wings[side] = build_wing(side, coll_w)
        doors[side] = build_door(side, coll_b)
        canards[side] = a9.build_canard(side, coll_c)
    ducts, duct_cutters = a9.build_induction(coll_b)
    for d in duct_cutters:
        for name in ('PHANTOM_REAR_LEFT_WIDEBODY_ANGULAR_FENDER', 'PHANTOM_REAR_RIGHT_WIDEBODY_ANGULAR_FENDER',
                     'PHANTOM_LEFT_AFT_WHEEL_TO_ENGINE_FAIRING', 'PHANTOM_RIGHT_AFT_WHEEL_TO_ENGINE_FAIRING',
                     'PHANTOM_LEFT_BOOSTER_FAIRING_TAPER', 'PHANTOM_RIGHT_BOOSTER_FAIRING_TAPER',
                     'PHANTOM_LEFT_SIDEBLADE_AMBER', 'PHANTOM_RIGHT_SIDEBLADE_AMBER',
                     'PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL'):
            ob = bpy.data.objects.get(name)
            if ob and a9.overlaps(ob, *a9.world_bounds(d)) and a9.touches(d, ob):
                a9.apply_boolean(ob, d)
                o2 = bpy.data.objects.get(name)
                if o2 is not None and not o2.get('a9_change'):
                    o2['a9_change'] = 'tunnelled for relocated induction duct'
    a9.retime_a8()
    animate(wings, doors, canards)
    tmp = bpy.data.collections.get(f'{REV}_TMP')
    if tmp:
        for ob in list(tmp.objects):
            bpy.data.objects.remove(ob)
        bpy.data.collections.remove(tmp)
    for ob in list(bpy.data.objects):
        if ob.name.startswith('cut'):
            bpy.data.objects.remove(ob)
    SC['vtx_revision'] = 'A10 split-level telescopic wing cassette: both deployed wings at one height (2026-11-03)'
    SC['vtx_revision_tag'] = REV
    SC['a10_removed_objects'] = ', '.join(removed)
    SC['a10_trimmed_objects'] = ', '.join(n for n, _ in changed)
    SC['a10_status'] = 'kinematic CAD; loads DERIVED in engineering/phantom/wing_loads.py (A10_split_level); not FEA/CFD/flight qualified'
    SC['a10_frame_convention'] = 'X forward, Z up, right-handed; A8 names RIGHT = +Y, LEFT = -Y'
    SC['handover_stroke_m'] = STROKE
    SC['handover_loads_case'] = 'A10_split_level'
    SC['handover_heights_file'] = 'evidence/phantom/a10_wing_heights.json'
    SC.frame_set(2)
    SC.frame_set(1)
    bpy.context.view_layer.update()
    return removed, changed


if __name__ == '__main__' or True:
    removed, changed = main()
    print('A10_BUILD removed', len(removed), 'trimmed', len(changed))
    if '--' in sys.argv:
        args = sys.argv[sys.argv.index('--') + 1:]
        if args:
            out = os.path.abspath(args[0])
            bpy.ops.wm.save_as_mainfile(filepath=out, copy=True)
            print('A10_SAVED', out)
            if len(args) > 1:
                bpy.ops.export_scene.gltf(filepath=os.path.abspath(args[1]), export_format='GLB', export_animations=True)
                print('A10_GLB', args[1])
