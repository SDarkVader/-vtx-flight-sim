"""VTX Phantom A9: telescopic stacked-sleeve wing cassette, flaps, ailerons, two-axis canards.

Builds on an open A8 scene. No file paths: the same script runs locally and as a Blendstra
revision. Locally:
  blender -b --disable-autoexec assets/source/phantom-a8/phantom-a8.blend \
      --python tools/phantom/build_a9_cassette.py -- assets/derived/phantom-a9-cassette.blend
Geometry and limits follow engineering/phantom/wing_loads.py (case A9_cassette_build) and
docs/phantom/WING_CASSETTE_STUDY.md. Kinematic CAD only: not FEA/CFD qualified.
"""
import bpy
import bmesh
import math
import sys
from mathutils import Vector, Matrix

SC = bpy.context.scene
REV = 'A9'
FPS = 24

# ---------------------------------------------------------------- geometry (m, model X fwd, Z up)
BAY_X = (-1.4765, -0.6345)        # sleeve inner x (rear, front)
WALL = 0.015                      # 1.5/12/1.5 mm CFRP-Nomex sandwich (buckling-sized, wing_loads.py carry_through)
SANDWICH_KG_M2 = 6.1              # 2 x 1.5 mm IM7/8552 + 12 mm 48 kg/m3 core, +15% joints
Z_BOT, Z_MID, Z_TOP = 0.815, 0.9405, 1.066
CELL = {'R': (Z_MID + WALL / 2, Z_TOP - WALL), 'L': (Z_BOT + WALL, Z_MID - WALL / 2)}  # inner z per wing
Y_FLANK = 1.245
Y_SKIN_IN = 1.2385                 # hull skin inner face at the flank
Y_FLANGE = (1.232, 1.238)
WING = dict(c_root=0.80, c_tip=0.32, x_le_root=-0.66, x_le_tip=-1.14, y_root=1.231, y_tip=2.595,
            tc_root=0.11, tc_tip=0.10, m=0.02, p=0.4, hinge_frac=0.725, flap=(0.05, 0.50), ail=(0.55, 0.95))
TONGUE_LEN = 1.05
STROKE = 1.37
PIN_STATIONS = (1.17, 0.24)       # deployed |y| of lock stations (outboard, inboard)
PIN_R = 0.016
CAN = dict(c_root=0.60, c_tip=0.36, x_le_root=1.95, x_le_tip=1.90, y_root=1.26, y_tip=1.84, z=0.95,
           tc=0.09, spindle_x=1.80, pivot=(1.95, 1.20))

# timeline (frames @24 fps); A8 pod/leg keys after frame 100 are shifted by T_SHIFT
T = dict(door=(84, 108), canard_unfold=(96, 132), slide=(108, 228), lock=(228, 240), flap=(246, 268, 296, 318),
         ail=(250, 262, 274, 286, 298), cpitch=(250, 264, 280, 298), unlock=(322, 334), slide_in=(334, 454),
         door_close=(454, 478), canard_fold=(444, 480))
T_SHIFT = 380
END = 530


# ---------------------------------------------------------------- helpers
def collection(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in SC.collection.children:
        SC.collection.children.link(c)
    return c


def material(name, rgb, metal=0.0, rough=0.4, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    if emit:
        b.inputs['Emission Color'].default_value = (*rgb, 1)
        b.inputs['Emission Strength'].default_value = emit
    m.diffuse_color = (*rgb, 1)
    return m


MAT = {}


def mats():
    def pick(names, fallback):
        for n in names:
            if n in bpy.data.materials:
                return bpy.data.materials[n]
        return fallback()
    MAT['body'] = pick(['A6 sharp graphite armour facet'], lambda: material('A9 graphite facet', (0.03, 0.03, 0.035), 0.3, 0.35))
    MAT['amber'] = pick(['A6 amber accent light'], lambda: material('A9 amber accent', (1.0, 0.45, 0.02), 0, 0.3, 4))
    MAT['ti'] = pick(['Ti6Al4V local pivot metal'], lambda: material('A9 Ti-6Al-4V', (0.55, 0.56, 0.6), 1, 0.3))
    MAT['cfrp'] = material('A9 CFRP structural laminate (IM7/8552 class)', (0.06, 0.06, 0.07), 0.1, 0.45)
    MAT['steel'] = material('A9 PH13-8Mo pin steel', (0.7, 0.7, 0.72), 1, 0.25)
    MAT['act'] = material('A9 electromechanical actuator housing', (0.18, 0.2, 0.24), 0.6, 0.4)
    MAT['duct'] = material('A9 induction duct CFRP', (0.12, 0.12, 0.13), 0.1, 0.5)


def link(ob, coll, parent=None, props=None):
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = parent.matrix_world.inverted()
    for k, v in (props or {}).items():
        ob[k] = v
    ob['a9_revision'] = REV
    return ob


def mesh_object(name, verts, faces, coll, mat=None, parent=None, props=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    return link(ob, coll, parent, props)


def box(name, lo, hi, coll, mat=None, parent=None, props=None):
    v = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return mesh_object(name, v, f, coll, mat, parent, props)


def cylinder(name, p0, p1, r, coll, mat=None, parent=None, props=None, n=20):
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0).normalized()
    u = ax.orthogonal().normalized()
    w = ax.cross(u)
    verts = []
    for p in (p0, p1):
        for i in range(n):
            a = 2 * math.pi * i / n
            verts.append(tuple(p + r * (math.cos(a) * u + math.sin(a) * w)))
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return mesh_object(name, verts, faces, coll, mat, parent, props)


def prism(name, poly, axis, a0, a1, coll, mat=None, parent=None, props=None):
    """Extrude a closed 2D polygon along a world axis ('x' poly in (y,z); 'y' poly in (x,z))."""
    n = len(poly)
    verts = []
    for a in (a0, a1):
        for u, v in poly:
            verts.append((a, u, v) if axis == 'x' else (u, a, v))
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return mesh_object(name, verts, faces, coll, mat, parent, props)


def empty(name, loc, coll, axes=None, parent=None, props=None, size=0.12):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'ARROWS'
    e.empty_display_size = size
    m = Matrix.Identity(4)
    if axes is not None:
        x = Vector(axes).normalized()
        y = Vector((0, 0, 1)).cross(x)
        if y.length < 1e-6:
            y = Vector((0, 1, 0)).cross(x)
        y.normalize()
        z = x.cross(y)
        m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(loc)
    e.matrix_world = m
    return link(e, coll, parent, props)


def evaluated_mesh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)


def apply_boolean(target, cutter, op='DIFFERENCE'):
    if target.type == 'CURVE':
        target = curve_to_mesh(target)
    if target.data.users > 1:
        target.data = target.data.copy()
    mod = target.modifiers.new('a9_bool', 'BOOLEAN')
    mod.operation = op
    mod.object = cutter
    # Manifold solver for closed inputs (robust on the A8 hull); exact solver with self-intersection
    # handling for open or self-touching cosmetic panels.
    manifold = is_closed(target) and is_closed(cutter)
    if manifold:
        try:
            mod.solver = 'MANIFOLD'
        except TypeError:          # Blender without the Manifold solver
            manifold = False
    if not manifold:
        mod.solver = 'EXACT'
        mod.use_self = True
        mod.use_hole_tolerant = True
    me = evaluated_mesh(target)
    # Triangulate concave n-gons (faces wrapped round holes) once, in local space: a later world-space
    # triangulation of such faces is orientation-dependent and can span the hole.
    # (moving A9 parts only; static A8 panels keep their n-gons, whose triangulation cannot change with pose)
    if target.name.startswith(REV):
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4], quad_method='BEAUTY', ngon_method='EAR_CLIP')
        bm.to_mesh(me)
        bm.free()
    target.modifiers.clear()
    old = target.data
    target.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return target


def is_closed(ob):
    if ob.type != 'MESH' or not len(ob.data.polygons):
        return False
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    ok = all(e.is_manifold for e in bm.edges)
    bm.free()
    return ok


def curve_to_mesh(ob):
    me = evaluated_mesh(ob)
    new = bpy.data.objects.new(ob.name + '_MESH', me)
    for c in ob.users_collection:
        c.objects.link(new)
    new.matrix_world = Matrix.Identity(4)
    new.data.transform(Matrix.Identity(4))
    me.transform(ob.matrix_world)
    for k in ob.keys():
        new[k] = ob[k]
    new['a9_converted_from_curve'] = ob.name
    name = ob.name
    bpy.data.objects.remove(ob)
    new.name = name
    return new


def world_bounds(ob):
    # mesh vertices when available: bound_box stays zero for objects not yet evaluated by the depsgraph
    if ob.type == 'MESH' and len(ob.data.vertices):
        pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    else:
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def touches(a, b):
    """True if the evaluated surfaces (or volumes) of a and b actually intersect; bounding boxes are only a pre-filter."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    trees = []
    for ob in (a, b):
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        if me is None or not len(me.polygons):
            ev.to_mesh_clear()
            return False
        bm = bmesh.new()
        bm.from_mesh(me)
        ev.to_mesh_clear()
        bm.transform(ob.matrix_world)
        trees.append((BVHTree.FromBMesh(bm), [v.co.copy() for v in bm.verts]))
        bm.free()
    if trees[0][0].overlap(trees[1][0]):
        return True
    # wholly contained small part: any vertex of b inside a (closed a only)
    loc = trees[0][0].find_nearest(trees[1][1][0])
    return bool(loc[0] is not None and (trees[1][1][0] - loc[0]).dot(loc[1]) < 0 and is_closed(a))


def overlaps(ob, lo, hi):
    a, b = world_bounds(ob)
    return all(a[i] < hi[i] and b[i] > lo[i] for i in range(3))


def key(ob, path, idx, frames_vals):
    for f, v in frames_vals:
        getattr(ob, path)[idx] = v
        ob.keyframe_insert(data_path=path, index=idx, frame=f)


def fcurves(ob):
    ad = ob.animation_data
    out = []
    if not ad or not ad.action:
        return out
    try:
        for layer in ad.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
    except AttributeError:
        out = list(ad.action.fcurves)
    return out


# ---------------------------------------------------------------- aerofoils
def naca(t, m=0.0, p=0.4, n=26):
    """Closed loop (upper TE->LE, lower LE->TE) of (x/c, z/c); closed trailing edge."""
    xs = [(1 - math.cos(math.pi * i / (n - 1))) / 2 for i in range(n)]
    up, lo = [], []
    for x in xs:
        yt = 5 * t * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        if m and x < p:
            yc, dy = m / p ** 2 * (2 * p * x - x * x), 2 * m / p ** 2 * (p - x)
        elif m:
            yc, dy = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x * x), 2 * m / (1 - p) ** 2 * (p - x)
        else:
            yc, dy = 0.0, 0.0
        th = math.atan(dy)
        up.append((x - yt * math.sin(th), yc + yt * math.cos(th)))
        lo.append((x + yt * math.sin(th), yc - yt * math.cos(th)))
    return up[::-1] + lo[1:-1]


def thickness_camber(t, m, p, x):
    yt = 5 * t * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    yc = (m / p ** 2 * (2 * p * x - x * x)) if x < p else (m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x * x))
    return yt, yc


def interp_contour(contour, xc, upper):
    """z/c of the upper or lower contour at x/c = xc."""
    n = len(contour)
    half = contour[:n // 2 + 1] if upper else contour[n // 2:] + [contour[0]]
    pts = sorted(half)
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if x0 <= xc <= x1:
            return z0 + (z1 - z0) * (xc - x0) / max(1e-9, x1 - x0)
    return pts[-1][1]


def section_parts(t, m, p, chord, xh_frac, gap, n=26, arc_n=10):
    """Fixed-part polygon (LE..cut) and control-surface polygon (nose arc about hinge..TE), in (x/c, z/c)."""
    full = naca(t, m, p, n)
    yt, yc = thickness_camber(t, m, p, xh_frac)
    r = yt
    cut = xh_frac - (r + gap / chord)
    up = [q for q in full[:len(full) // 2 + 1] if q[0] <= cut]
    lo = [q for q in full[len(full) // 2:] if q[0] <= cut]
    fixed = [(cut, interp_contour(full, cut, True))] + up[::-1][::-1] if False else None
    # fixed: upper from cut to LE, lower from LE to cut
    upper_sorted = sorted([q for q in full[:len(full) // 2 + 1]], key=lambda q: -q[0])
    lower_sorted = sorted([q for q in full[len(full) // 2:]], key=lambda q: q[0])
    fixed = [(cut, interp_contour(full, cut, True))] + [q for q in upper_sorted if q[0] < cut] + \
            [q for q in lower_sorted if 0 < q[0] < cut] + [(cut, interp_contour(full, cut, False))]
    surf_up = [q for q in upper_sorted if q[0] > xh_frac][::-1]   # hinge -> TE
    surf_lo = [q for q in lower_sorted if q[0] > xh_frac][::-1]   # TE -> hinge
    surf = [(xh_frac, yc + r)] + surf_up + surf_lo[1:] if False else None
    surf = [(xh_frac, yc + r)] + [q for q in sorted(surf_up)] + [q for q in sorted(surf_lo, key=lambda q: -q[0])][1:] + [(xh_frac, yc - r)]
    for i in range(1, arc_n):
        a = -math.pi / 2 - math.pi * i / arc_n
        surf.append((xh_frac + r * math.cos(a) / 1.0, yc + r * math.sin(a)))
    return full, fixed, surf, (xh_frac, yc), r


def resample(poly, n):
    """Resample a closed polygon to n points by arc length (keeps loft topology constant)."""
    pts = [Vector((p[0], p[1])) for p in poly] + [Vector(poly[0])]
    seg = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seg)
    out, acc, j = [], 0.0, 0
    for k in range(n):
        s = total * k / n
        while j < len(seg) - 1 and acc + seg[j] < s:
            acc += seg[j]
            j += 1
        f = (s - acc) / max(1e-12, seg[j])
        q = pts[j].lerp(pts[j + 1], f)
        out.append((q.x, q.y))
    return out


def loft(name, sections, coll, mat=None, parent=None, props=None):
    """sections: list of lists of 3D points, same length, closed."""
    n = len(sections[0])
    verts = [v for s in sections for v in s]
    faces = [tuple(range(n))[::-1], tuple(range((len(sections) - 1) * n, len(sections) * n))]
    for k in range(len(sections) - 1):
        a, b = k * n, (k + 1) * n
        faces += [(a + i, a + (i + 1) % n, b + (i + 1) % n, b + i) for i in range(n)]
    return mesh_object(name, verts, faces, coll, mat, parent, props)


# ---------------------------------------------------------------- A9 build
def retire_a8():
    gone = []
    names = [n for n in bpy.data.objects.keys() if any(k in n for k in (
        'WING_AERODYNAMIC_ENVELOPE', 'WING_AMBER_OUTER_EDGE', 'PHANTOM_WING_HINGE_', 'WING_TITANIUM_ROOT_FAIRING',
        'TITANIUM_BEARING_LOAD_DISTRIBUTION', 'SEALED_REMOVABLE_FLUSH_FAIRING', 'MOUNT_001_WING_CARBON',
        'NOSE_CANARD_STOWED_BLADE', 'CANARD_AMBER_EDGE', 'NOSE_CANARD_HINGE_', 'CANARD_LEFT_', 'CANARD_RIGHT_',
        'SHOULDER_INLET_LEFT_SEALING', 'SHOULDER_INLET_RIGHT_SEALING', 'SHOULDER_INLET_LEFT_SWEPT', 'SHOULDER_INLET_RIGHT_SWEPT'))]
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob:
            gone.append(n)
            bpy.data.objects.remove(ob, do_unlink=True)
    return gone


def wing_geometry(side):
    s = 1 if side == 'R' else -1
    zin = CELL[side]
    zc = 0.5 * (zin[0] + zin[1])
    W = WING
    full_root = naca(W['tc_root'], W['m'], W['p'])
    zmin = min(q[1] for q in full_root) * W['c_root']
    zmax = max(q[1] for q in full_root) * W['c_root']
    z_chord = zc - 0.5 * (zmin + zmax)       # chord plane height centring the root in its cell
    return s, zc, z_chord


def station(y_abs):
    W = WING
    f = (y_abs - W['y_root']) / (W['y_tip'] - W['y_root'])
    return (W['c_root'] + (W['c_tip'] - W['c_root']) * f, W['x_le_root'] + (W['x_le_tip'] - W['x_le_root']) * f,
            W['tc_root'] + (W['tc_tip'] - W['tc_root']) * f)


def build_wing(side, coll):
    s, zc, z_chord = wing_geometry(side)
    W = WING
    span = W['y_tip'] - W['y_root']
    eta = lambda e: W['y_root'] + e * span
    slide = empty(f'{REV}_JOINT_WING_{side}_SLIDE', (-1.05, s * W['y_root'], zc), coll, axes=(0, s, 0), props=dict(
        joint_type='slide', axis_world=[0, s, 0], range_m=[-STROKE, 0.0], ref_value_m=0.0, ref_pose='deployed',
        actuator='ball-screw EMA, 2.5 kN stall, 0.30 m/s max, brake on loss of power',
        note='0 = deployed and seated on mouth flange (hard stop); -1.37 = stowed (inboard stop)'))
    NP = 48

    def sec(y_abs, part):
        c, xle, t = station(y_abs)
        full, fixed, surf, hinge, r = section_parts(t, W['m'], W['p'], c, W['hinge_frac'], 0.010)
        poly = {'full': full, 'fixed': fixed, 'surf': surf}[part]
        poly = resample(poly, NP)
        return [(xle - px * c, s * y_abs, z_chord + pz * c) for px, pz in poly], (xle - hinge[0] * c, z_chord + hinge[1] * c)

    gap = 0.004
    bands = [(0.0, W['flap'][0], 'full'), (W['flap'][0], W['flap'][1], 'fixed'), (W['flap'][1], W['ail'][0], 'full'),
             (W['ail'][0], W['ail'][1], 'fixed'), (W['ail'][1], 1.0, 'full')]
    bm_all = bmesh.new()
    for e0, e1, part in bands:
        ys = [eta(e0 + (e1 - e0) * k / 4) for k in range(5)]
        tmp = loft('tmp', [sec(y, part)[0] for y in ys], coll)
        tmp.data.transform(tmp.matrix_world)
        bm_all.from_mesh(tmp.data)
        bpy.data.objects.remove(tmp)
    me = bpy.data.meshes.new(f'{REV}_WING_{side}_PANEL')
    bm_all.to_mesh(me)
    bm_all.free()
    panel = link(bpy.data.objects.new(f'{REV}_WING_{side}_PANEL_CFRP_TORSION_BOX', me), coll, slide, dict(
        section='NACA 2411 root -> 2410 tip (stand-in for a 64A2xx-class section; CFD to select)',
        box='CFRP torsion box 15-60% chord, root depth 79 mm, caps 4.0 mm, webs 2.8 mm (DERIVED)',
        mass_kg=10.05, mass_basis='DERIVED wing_loads.py panel incl. secondary structure'))
    me.materials.append(MAT['body'])
    # tongue (full cell chord carry-through extension) and root seal/stop plate
    y_plate = W['y_root'] - 0.008
    tongue = box(f'{REV}_WING_{side}_TONGUE_CARRY_THROUGH_BOX',
                 (BAY_X[0] + 0.010, min(s * (y_plate - TONGUE_LEN), s * y_plate), zc - 0.045),
                 (BAY_X[1] - 0.010, max(s * (y_plate - TONGUE_LEN), s * y_plate), zc + 0.045), coll, MAT['cfrp'], slide,
                 dict(role='root tongue: transfers wing bending as a spanwise couple to the two lock stations (0.94 m apart)',
                      mass_kg=7.39, mass_basis='DERIVED, incl. Ti lug inserts'))
    plate = box(f'{REV}_WING_{side}_ROOT_SEAL_STOP_PLATE', (BAY_X[0] + 0.006, min(s * y_plate, s * (y_plate + 0.008)), zc - 0.0495),
                (BAY_X[1] - 0.006, max(s * y_plate, s * (y_plate + 0.008)), zc + 0.0495), coll, MAT['ti'], slide,
                dict(role='outboard hard stop: seats against mouth flange; fills slot flush when deployed', mass_kg=0.9))
    # bores in tongue for front lock pins (pins live in the tongue) and rear pin sockets
    for st in PIN_STATIONS:
        yy = s * st
        cut = cylinder('cut', (BAY_X[1] + 0.02, yy, zc), (BAY_X[1] - 0.25, yy, zc), PIN_R + 0.002, coll)
        apply_boolean(tongue, cut)
        bpy.data.objects.remove(cut)
        cut = cylinder('cut', (BAY_X[0] - 0.02, yy, zc), (BAY_X[0] + 0.07, yy, zc), PIN_R + 0.002, coll)
        apply_boolean(tongue, cut)
        bpy.data.objects.remove(cut)
        # front pin: carried by the tongue, driven forward into the sleeve front-wall bushing
        fp = empty(f'{REV}_JOINT_WING_{side}_LOCK_FRONT_{"OUT" if st > 1 else "IN"}', (BAY_X[1] - 0.06, yy, zc), coll,
                   axes=(1, 0, 0), parent=slide, props=dict(joint_type='slide', axis_world=[1, 0, 0], range_m=[-0.07, 0.0],
                                                           ref_value_m=0.0, ref_pose='locked (as built)',
                                                           actuator='tongue-mounted lock EMA, irreversible screw + spring, 2 proximity sensors'))
        cylinder(f'{REV}_WING_{side}_LOCK_PIN_FRONT_{"OUT" if st > 1 else "IN"}', (BAY_X[1] + 0.012, yy, zc), (BAY_X[1] - 0.108, yy, zc),
                 PIN_R, coll, MAT['steel'], fp, dict(part='hollow pin 32/22 mm PH13-8Mo, double-shear in Ti lug', mass_kg=0.35))
    # control surfaces
    surfaces = {}
    for nm, (e0, e1) in (('FLAP', W['flap']), ('AILERON', W['ail'])):
        y0, y1 = eta(e0) + gap, eta(e1) - gap
        h0 = sec(y0, 'surf')[1]
        h1 = sec(y1, 'surf')[1]
        p0 = Vector((h0[0], s * y0, h0[1]))
        p1 = Vector((h1[0], s * y1, h1[1]))
        axis = (p1 - p0) if s < 0 else (p0 - p1)          # local X points toward -Y: +angle = trailing edge down
        hinge = empty(f'{REV}_JOINT_{nm}_{side}', tuple(p0), coll, axes=tuple(axis), parent=slide, props=dict(
            joint_type='hinge', axis_world=list(axis.normalized()), range_deg=[-5, 35] if nm == 'FLAP' else [-20, 20],
            ref_value_deg=0.0, positive='trailing edge down', rate_deg_s=15 if nm == 'FLAP' else 80,
            actuator_stall_torque_Nm=60 if nm == 'FLAP' else 72,
            actuator='rotary EMA inside the wing on the hinge line + torque tube, irreversible, mass-balanced surface',
            interlock='neutral and locked whenever the wing is not fully deployed and pinned'))
        ys = [y0 + (y1 - y0) * k / 4 for k in range(5)]
        surf = loft(f'{REV}_WING_{side}_{nm}', [sec(y, 'surf')[0] for y in ys], coll, MAT['body'], hinge,
                    dict(mass_kg=1.0 if nm == 'FLAP' else 0.8, hinge_line_frac=W['hinge_frac']))
        surfaces[nm] = (hinge, surf)
        # rotary EMA inside the fixed wing, on the hinge line, in the full-chord band inboard of the surface
        # (no external fairing: everything must pass the root-profile slot). Drives the surface by torque tube.
        e_act = (W['flap'][0] * 0.5) if nm == 'FLAP' else 0.5 * (W['flap'][1] + W['ail'][0])
        ya = eta(e_act)
        c, xle, t = station(ya)
        xa = xle - 0.60 * c
        full = naca(t, W['m'], W['p'])
        za = z_chord + 0.5 * (interp_contour(full, 0.60, True) + interp_contour(full, 0.60, False)) * c
        depth = (interp_contour(full, 0.60, True) - interp_contour(full, 0.60, False)) * c
        cylinder(f'{REV}_WING_{side}_{nm}_ROTARY_EMA', (xa, s * (ya - 0.045), za), (xa, s * (ya + 0.045), za), 0.42 * depth, coll,
                 MAT['act'], slide, dict(contains=f'{nm.lower()} rotary EMA + torque tube to the surface hinge', mass_kg=0.9,
                                          diameter_m=round(0.84 * depth, 4)))
    # ball-screw nut (bored, rides on the screw behind the rear wall) and arm through the rear-wall slot
    zs = zc + 0.038 if side == 'R' else zc - 0.038
    y_car = s * (W['y_root'] - 0.55)
    nut = box(f'{REV}_WING_{side}_SLIDE_NUT_CARRIAGE', (BAY_X[0] - 0.066, y_car - 0.04, zs - 0.019),
              (BAY_X[0] - 0.024, y_car + 0.04, zs + 0.019), coll, MAT['act'], slide,
              dict(role='ball-screw nut', mass_kg=0.45))
    cut = cylinder('cut', (BAY_X[0] - 0.045, y_car - 0.06, zs), (BAY_X[0] - 0.045, y_car + 0.06, zs), 0.0115, coll)
    apply_boolean(nut, cut)
    bpy.data.objects.remove(cut)
    box(f'{REV}_WING_{side}_SLIDE_NUT_ARM', (BAY_X[0] - 0.024, y_car - 0.03, zs - 0.007), (BAY_X[0] + 0.012, y_car + 0.03, zs + 0.007),
        coll, MAT['ti'], slide, dict(role='nut arm through rear-wall slot to the tongue', mass_kg=0.15))
    return slide, surfaces, zc


def build_sleeve(coll):
    lo_y, hi_y = -Y_FLANK, Y_FLANK
    x0, x1 = BAY_X[0] - WALL, BAY_X[1] + WALL
    parts = []
    for nm, z0 in (('BOTTOM', Z_BOT), ('MID', Z_MID - WALL / 2), ('TOP', Z_TOP - WALL)):
        parts.append(box(f'{REV}_SLEEVE_{nm}_PLATE', (x0, lo_y + 0.007, z0), (x1, hi_y - 0.007, z0 + WALL), coll, MAT['cfrp']))
    front = box(f'{REV}_SLEEVE_FRONT_WALL', (BAY_X[1], lo_y + 0.007, Z_BOT), (x1, hi_y - 0.007, Z_TOP), coll, MAT['cfrp'])
    rear = box(f'{REV}_SLEEVE_REAR_WALL', (x0, lo_y + 0.007, Z_BOT), (BAY_X[0], hi_y - 0.007, Z_TOP), coll, MAT['cfrp'])
    # closed ends: upper cell closed at -Y, lower cell closed at +Y; flanges with root-profile holes at the mouths
    for side in ('R', 'L'):
        s, zc, z_chord = wing_geometry(side)
        z0, z1 = CELL[side]
        ye = -s * (Y_FLANK - 0.007)
        box(f'{REV}_SLEEVE_{side}_CELL_CLOSED_END', (BAY_X[0], min(ye, ye + s * 0.006), z0),
            (BAY_X[1], max(ye, ye + s * 0.006), z1), coll, MAT['cfrp'])
        fl = box(f'{REV}_SLEEVE_{side}_MOUTH_FLANGE_STOP', (BAY_X[0], min(s * Y_FLANGE[0], s * Y_FLANGE[1]), z0),
                 (BAY_X[1], max(s * Y_FLANGE[0], s * Y_FLANGE[1]), z1), coll, MAT['ti'],
                 props=dict(role='mouth flange: outboard hard stop and seal land for the root plate'))
        cut = slot_cutter(side, 0.003, (s * 1.20, s * 1.30))
        apply_boolean(fl, cut)
        bpy.data.objects.remove(cut)
        for st in PIN_STATIONS:
            yy = s * st
            for wall, xa, xb in ((front, BAY_X[1] - 0.01, x1 + 0.01), (rear, x0 - 0.01, BAY_X[0] + 0.01)):
                cut = cylinder('cut', (xa, yy, zc), (xb, yy, zc), PIN_R + 0.0015, coll)
                apply_boolean(wall, cut)
                bpy.data.objects.remove(cut)
        zs = zc + 0.038 if side == 'R' else zc - 0.038
        y_car = s * (WING['y_root'] - 0.55)
        ya, yb = sorted((y_car - s * (STROKE + 0.06), y_car + s * 0.06))
        cut = box('cut', (x0 - 0.01, ya - 0.045, zs - 0.0115), (BAY_X[0] + 0.01, yb + 0.045, zs + 0.0115), coll)
        apply_boolean(rear, cut)
        bpy.data.objects.remove(cut)
    # bonded assembly -> one rigid carry-through object (plates, walls, closed ends, Ti mouth flanges)
    parts = [ob for ob in coll.objects if ob.name.startswith(f'{REV}_SLEEVE') and 'SUPPORT' not in ob.name]
    mass = 0.0
    for ob in parts:
        lo, hi = world_bounds(ob)
        d = sorted(hi[i] - lo[i] for i in range(3))
        mass += (SANDWICH_KG_M2 * d[1] * d[2]) if ob.active_material == MAT['cfrp'] else 4430.0 * d[0] * d[1] * d[2] * 0.5
    bm = bmesh.new()
    mats_used = []
    for ob in parts:
        me = ob.data.copy()
        me.transform(ob.matrix_world)
        mi = len(mats_used)
        mats_used.append(ob.active_material)
        for p in me.polygons:
            p.material_index = mi
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        bpy.data.objects.remove(ob)
    me = bpy.data.meshes.new(f'{REV}_SLEEVE')
    bm.to_mesh(me)
    bm.free()
    for m in mats_used:
        me.materials.append(m)
    link(bpy.data.objects.new(f'{REV}_SLEEVE_CARRY_THROUGH_BOX', me), coll, props=dict(
        role='twin-cell CFRP sandwich sleeve (1.5/12/1.5 mm) with Ti mouth flanges: the wing carry-through box; replaces MOUNT_001',
        mass_kg=round(mass, 2), mass_basis='DERIVED: sandwich areal mass x panel areas + Ti flanges (50% solidity)'))


def slot_cutter(side, offset, y_range):
    """Prism of the root aerofoil profile grown by `offset`, extruded across y_range."""
    s, zc, z_chord = wing_geometry(side)
    W = WING
    full = resample(naca(W['tc_root'], W['m'], W['p']), 64)
    pts = [Vector((W['x_le_root'] - px * W['c_root'], z_chord + pz * W['c_root'])) for px, pz in full]
    cen = sum(pts, Vector((0, 0))) / len(pts)
    grown = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i - 1], pts[(i + 1) % n]
        tng = (b - a).normalized()
        nrm = Vector((tng.y, -tng.x))
        if nrm.dot(pts[i] - cen) < 0:
            nrm = -nrm
        grown.append(tuple(pts[i] + nrm * offset))
    coll = bpy.context.scene.collection
    me = prism('cut', grown, 'y', y_range[0], y_range[1], collection(f'{REV}_TMP'))
    return me


def build_lock_and_drive(side, coll):
    s, zc, z_chord = wing_geometry(side)
    out = []
    for st in PIN_STATIONS:
        yy = s * st
        tag = 'OUT' if st > 1 else 'IN'
        hp = empty(f'{REV}_JOINT_WING_{side}_LOCK_REAR_{tag}', (BAY_X[0] - 0.07, yy, zc), coll, axes=(1, 0, 0), props=dict(
            joint_type='slide', axis_world=[1, 0, 0], range_m=[-0.07, 0.0], ref_value_m=0.0, ref_pose='locked (as built)',
            actuator='sleeve-mounted lock EMA, irreversible screw + spring, dual sensors'))
        cylinder(f'{REV}_WING_{side}_LOCK_PIN_REAR_{tag}', (BAY_X[0] + 0.048, yy, zc), (BAY_X[0] - 0.072, yy, zc), PIN_R, coll,
                 MAT['steel'], hp, dict(part='hollow pin 32/22 mm PH13-8Mo', mass_kg=0.35))
        hsg = cylinder(f'{REV}_WING_{side}_LOCK_ACTUATOR_REAR_{tag}', (BAY_X[0] - 0.090, yy, zc), (BAY_X[0] - 0.165, yy, zc), 0.022, coll,
                       MAT['act'], props=dict(part='lock EMA housing; pin retracts into its bore', mass_kg=0.8))
        cut = cylinder('cut', (BAY_X[0] - 0.080, yy, zc), (BAY_X[0] - 0.150, yy, zc), PIN_R + 0.0015, coll)
        apply_boolean(hsg, cut)
        bpy.data.objects.remove(cut)
    zs = zc + 0.038 if side == 'R' else zc - 0.038
    y_car = s * (WING['y_root'] - 0.55)
    ya, yb = sorted((y_car - s * (STROKE + 0.05), y_car + s * 0.05))
    cylinder(f'{REV}_WING_{side}_SLIDE_BALL_SCREW', (BAY_X[0] - 0.045, ya, zs), (BAY_X[0] - 0.045, yb, zs), 0.010, coll, MAT['steel'],
             props=dict(part='ball screw 20 mm lead 10 mm', mass_kg=2.4))
    ym = ya - 0.09 if s > 0 else yb + 0.09
    cylinder(f'{REV}_WING_{side}_SLIDE_MOTOR', (BAY_X[0] - 0.045, ym, zs), (BAY_X[0] - 0.045, ym + 0.085, zs), 0.022, coll, MAT['act'],
             props=dict(part='slide BLDC motor + brake + resolver', mass_kg=1.6))
    return out


def build_door(side, coll):
    s, zc, z_chord = wing_geometry(side)
    yo = s * (Y_FLANK + 0.0075)
    hinge = empty(f'{REV}_JOINT_HATCH_{side}', (-1.05, yo, Z_MID), coll, axes=(1, 0, 0), props=dict(
        joint_type='hinge', axis_world=[1, 0, 0], range_deg=[-180, 0], ref_value_deg=-180, ref_pose='open (flight)',
        positive='right-hand about +X', rate_deg_s=180, actuator='rotary EMA + over-centre latch, 25 N m stall',
        latch_load_at_VD_N=2105))
    z0, z1 = CELL[side]
    door = box(f'{REV}_HATCH_{side}_FLUSH_DOOR', (BAY_X[0] - 0.004, min(yo, yo - s * 0.006), z0 - 0.003 if side == 'L' else Z_MID + 0.0015),
               (BAY_X[1] + 0.004, max(yo, yo - s * 0.006), Z_MID - 0.0015 if side == 'L' else z1 + 0.003), coll, MAT['body'], hinge,
               dict(role='flush slot door; flips 180 deg to lie on the blank cell face below/above', mass_kg=0.8))
    box(f'{REV}_HATCH_{side}_AMBER_EDGE', (BAY_X[0] - 0.004, min(yo, yo + s * 0.002), (z0 - 0.003) if side == 'L' else z1 - 0.004),
        (BAY_X[1] + 0.004, max(yo, yo + s * 0.002), (z0 + 0.003) if side == 'L' else z1 + 0.003), coll, MAT['amber'], hinge)
    return hinge


def build_canard(side, coll):
    s = 1 if side == 'R' else -1
    C = CAN
    piv = (C['pivot'][0], s * C['pivot'][1], C['z'])
    fold = empty(f'{REV}_JOINT_CANARD_{side}_FOLD', piv, coll, axes=(0, 0, 1), props=dict(
        joint_type='hinge', axis_world=[0, 0, 1], range_deg=sorted([0, 90 * s]), ref_value_deg=0, ref_pose='deployed',
        rate_deg_s=60, actuator='fold rotary EMA + shoot-bolt lock; fold pin bearings 0.20 m apart',
        note='+90 deg (R) / -90 deg (L) = stowed over the front fender'))
    pitch = empty(f'{REV}_JOINT_CANARD_{side}_PITCH', (C['spindle_x'], s * C['y_root'], C['z']), coll, axes=(0, -1, 0), parent=fold,
                  props=dict(joint_type='hinge', axis_world=[0, -1, 0], range_deg=[-20, 25], ref_value_deg=0, positive='nose up',
                             rate_deg_s=40, actuator_stall_torque_Nm=420, actuator='rotary EMA on fold yoke, irreversible'))
    secs = []
    for k in range(6):
        f = k / 5
        y = C['y_root'] + (C['y_tip'] - C['y_root']) * f
        c = C['c_root'] + (C['c_tip'] - C['c_root']) * f
        xle = C['x_le_root'] + (C['x_le_tip'] - C['x_le_root']) * f
        poly = resample(naca(C['tc']), 40)
        secs.append([(xle - px * c, s * y, C['z'] + pz * c) for px, pz in poly])
    loft(f'{REV}_CANARD_{side}_ALL_MOVING_BLADE', secs, coll, MAT['body'], pitch,
         dict(section='NACA 0009', area_m2=0.278, mass_kg=3.5, pivot_frac_mac=0.25))
    tip = secs[-1]
    i_le = max(range(len(tip)), key=lambda i: tip[i][0])
    cylinder(f'{REV}_CANARD_{side}_AMBER_EDGE', Vector(secs[0][i_le]) + Vector((0.004, s * 0.01, 0)),
             Vector(tip[i_le]) + Vector((0.004, 0, 0)), 0.003, coll, MAT['amber'], pitch)
    cylinder(f'{REV}_CANARD_{side}_TI_SPINDLE', (C['spindle_x'], s * (C['y_root'] + 0.05), C['z']),
             (C['spindle_x'], s * (C['y_root'] - 0.16), C['z']), 0.0215, coll, MAT['ti'], pitch,
             dict(part='Ti-6Al-4V spindle OD 43 mm (DERIVED >= 38 mm)', mass_kg=1.0))
    # Fold yoke: angular wedge carrying the spindle bearings (0.20 m apart) and the pitch EMA; rotates with the fold.
    y0, y1 = sorted((s * (C['y_root'] - 0.17), s * (C['y_root'] - 0.010)))
    yoke = prism(f'{REV}_CANARD_{side}_FOLD_YOKE_AND_PITCH_EMA',
                 [(1.745, 0.935), (1.770, 0.985), (1.955, 0.985), (1.985, 0.955), (1.985, 0.916), (1.765, 0.916)],
                 'y', y0, y1, coll, MAT['ti'], fold, dict(part='fold yoke with spindle bearings 0.20 m apart and pitch EMA', mass_kg=2.2))
    cut = cylinder('cut', (C['spindle_x'], s * (C['y_root'] + 0.02), C['z']), (C['spindle_x'], s * (C['y_root'] - 0.20), C['z']), 0.0235, coll)
    apply_boolean(yoke, cut)
    bpy.data.objects.remove(cut)
    # Fixed root pod: faceted Ti/CFRP fairing on the fender corner that houses the fold pin and its lower bearing,
    # and the A-frame struts that carry canard lift, drag and pitching moment into the front wheel-pod reaction pylon.
    pod_secs = []
    for z, (xa, xb, ya_, yb_) in ((0.78, (1.835, 2.125, 1.010, 1.255)), (0.86, (1.860, 2.080, 1.060, 1.250)),
                                  (0.912, (1.890, 2.020, 1.120, 1.235))):
        pod_secs.append([(xa, s * ya_, z), (xb, s * ya_, z), (xb, s * yb_, z), (xa, s * yb_, z)][::s])
    pod = mesh_object(f'{REV}_CANARD_{side}_ROOT_POD', [v for sec in pod_secs for v in sec],
                      [(0, 1, 2, 3)[::-1], (8, 9, 10, 11)] + [(k * 4 + i, k * 4 + (i + 1) % 4, (k + 1) * 4 + (i + 1) % 4, (k + 1) * 4 + i)
                                                               for k in range(2) for i in range(4)],
                      coll, MAT['body'], props=dict(part='canard root pod: faceted fairing over fold pin, lower bearing and strut node',
                                                     mass_kg=1.6))
    pylon = cylinder(f'{REV}_CANARD_{side}_FOLD_PIN', (piv[0], piv[1], 0.914), (piv[0], piv[1], 0.80), 0.020, coll, MAT['ti'],
                     props=dict(part='fold pin; bearings at z 0.80 (pod base) and 0.91 (yoke) - spherical plain, see report', mass_kg=0.8))
    # Node pads bolted to the reaction-pylon top: outside the front-wheel rotation envelope (>= 18 mm) and clear of
    # the radiator ram inlet (|y| <= 0.748 for x >= 1.78) and the nose CFD probe.
    node = box(f'{REV}_CANARD_{side}_STRUT_NODE_A', (1.812, min(s * 0.752, s * 0.80), 0.5415), (1.850, max(s * 0.752, s * 0.80), 0.575),
               coll, MAT['ti'], props=dict(part='Ti node pad A bolted to the wheel-pod reaction pylon top', mass_kg=0.3))
    node_b = box(f'{REV}_CANARD_{side}_STRUT_NODE_B', (1.700, min(s * 0.62, s * 0.66), 0.5415), (1.740, max(s * 0.62, s * 0.66), 0.575),
                 coll, MAT['ti'], props=dict(part='Ti node pad B bolted to the wheel-pod reaction pylon top', mass_kg=0.3))
    strut_paths = [[(1.930, s * 1.10, 0.800), (1.835, s * 0.78, 0.560)], [(1.860, s * 1.10, 0.800), (1.720, s * 0.64, 0.560)]]
    struts = [polyline_tube(f'{REV}_CANARD_{side}_STRUT_{t}', pth, 0.015, coll, MAT['ti']) for t, pth in zip('AB', strut_paths)]
    for st in struts:
        st['part'] = 'Ti-6Al-4V tube strut (A-frame): pod base to reaction-pylon node, routed outside the wheel rotation sweep'
        st['mass_kg'] = 0.7
    # Tunnel the A8 cosmetic panels where the pod and struts pass through them.
    for k, part in enumerate([pod, node, node_b] + struts):
        lo, hi = world_bounds(part)
        for ob in list(SC.objects):
            if ob.type not in {'MESH', 'CURVE'} or ob.name.startswith(REV) or ob.name.startswith('cut') or ob.name.startswith('WHEEL_'):
                continue
            if overlaps(ob, lo, hi) and touches(part, ob):
                if k >= 3:   # strut: tunnel with 4 mm radial clearance, extended past both ends
                    a_, b_ = Vector(strut_paths[k - 3][0]), Vector(strut_paths[k - 3][1])
                    ext = (b_ - a_).normalized() * 0.05
                    cutter = cylinder('cut_strut', a_ - ext, b_ + ext, 0.019, coll)
                else:
                    cutter = part.copy()
                    cutter.data = part.data.copy()
                    SC.collection.objects.link(cutter)
                    lo_, hi_ = world_bounds(part)
                    c = (Vector(lo_) + Vector(hi_)) / 2
                    cutter.data.transform(Matrix.Translation(c) @ Matrix.Diagonal((1.06, 1.06, 1.06, 1)) @ Matrix.Translation(-c))
                name = ob.name
                apply_boolean(ob, cutter)
                bpy.data.objects.remove(cutter)
                o2 = bpy.data.objects.get(name)
                if o2:
                    o2['a9_change'] = 'tunnelled for canard root pod / A-frame strut'
    # pod, fold pin, struts and node bracket are one welded/bolted fixed structure
    parts = [pod, pylon, node, node_b] + struts
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
    me = bpy.data.meshes.new(f'{REV}_CANARD_{side}_ROOT')
    bm.to_mesh(me)
    bm.free()
    for m in mats_used:
        me.materials.append(m)
    link(bpy.data.objects.new(f'{REV}_CANARD_{side}_ROOT_STRUCTURE', me), coll, props=dict(
        part='canard root: faceted pod + fold pin (bearings z 0.80/0.91) + Ti A-frame struts to the wheel-pod reaction pylon node',
        mass_kg=1.6 + 0.8 + 0.6 + 1.4, mass_basis='DERIVED/SYNTHETIC part masses'))
    return fold, pitch


def shoulder_section(x, zr, zv, zh, yh, zf, yf=Y_FLANK, zlow=0.60):
    """Faceted haunch cross-section: central spine (zr), valley (zv) at |y| 0.72, haunch crest (zh) at |y| yh,
    flank top (zf) at |y| yf, flank down to 0.81, underside held at z 0.80 outboard of |y| 0.68 (clear of the
    rear-wheel rotation sweep, top z 0.78) and dropping to zlow inboard (inside the A8 hull)."""
    half = [(0.66, zlow), (0.68, 0.80), (yf - 0.035, 0.80), (yf, 0.81), (yf, zf), (yh, zh), (0.72, zv), (0.30, zr - 0.02)]
    pts = [(0.0, zlow)] + half + [(0.0, zr)] + [(-y, z) for (y, z) in reversed(half)]
    return [(x, y, z) for y, z in pts]


def polyline_tube(name, pts, r, coll, mat):
    bm = bmesh.new()
    for a, b in zip(pts, pts[1:]):
        c = cylinder('tmp_seg', a, b, r, coll, n=10)
        c.data.transform(c.matrix_world)
        bm.from_mesh(c.data)
        bpy.data.objects.remove(c)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    return link(bpy.data.objects.new(name, me), coll)


def build_shoulders_and_hull(coll, removed):
    hull = bpy.data.objects['PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL']
    tmp = collection(f'{REV}_TMP')
    # Main haunch over the cassette (x -0.613..-1.665): spine continues the canopy line and falls aft, haunch
    # crests rise aft toward the fins. Skin over the cassette cavity (|y|<=1.2385, z<=1.068): >= 10 mm everywhere.
    secs = [shoulder_section(-0.613, 1.165, 1.078, 1.112, 1.06, 1.080),
            shoulder_section(-1.10, 1.140, 1.078, 1.125, 1.06, 1.080),
            shoulder_section(-1.665, 1.105, 1.077, 1.135, 1.06, 1.080),
            shoulder_section(-1.90, 0.990, 0.930, 1.030, 1.02, 0.980, yf=1.18, zlow=0.55),
            shoulder_section(-2.12, 0.860, 0.840, 0.905, 0.95, 0.860, yf=1.08, zlow=0.50)]
    sh = loft(f'{REV}_CASSETTE_HAUNCH', secs, tmp)
    apply_boolean(hull, sh, 'UNION')
    bpy.data.objects.remove(sh)
    # Forward-raked haunch blades behind each door (outboard of the glass and above the door top z 0.762)
    for s in (1, -1):
        blade = [[(-0.625, s * y, z) for y, z in ((0.88, 0.80), (1.245, 0.81), (1.245, 1.080), (1.06, 1.112), (0.88, 1.09))],
                 [(-0.46, s * y, z) for y, z in ((0.95, 0.83), (1.20, 0.835), (1.20, 1.000), (1.06, 1.030), (0.95, 1.01))],
                 [(-0.30, s * y, z) for y, z in ((1.04, 0.88), (1.10, 0.88), (1.10, 0.920), (1.07, 0.925), (1.04, 0.92))]]
        bl = loft(f'{REV}_HAUNCH_BLADE', blade, tmp)
        apply_boolean(hull, bl, 'UNION')
        bpy.data.objects.remove(bl)
    for side in ('R', 'L'):
        s, _, _ = wing_geometry(side)
        cut = slot_cutter(side, 0.006, (s * 1.18, s * 1.45))
        apply_boolean(hull, cut)
        bpy.data.objects.remove(cut)
    # interior cavity for the sleeve and lock drives (keeps the hull a skin around the cassette)
    cav = box('cut', (-1.655, -Y_SKIN_IN, Z_BOT - 0.002), (BAY_X[1] + WALL + 0.0005, Y_SKIN_IN, Z_TOP + 0.002), collection(f'{REV}_TMP'))
    apply_boolean(hull, cav)
    bpy.data.objects.remove(cav)
    hull['a9_change'] = ('union with faceted cassette haunches x -0.30..-2.12 (spine, twin crests, raked blades); '
                         'root-profile slots at |y|=1.245; interior cassette cavity')
    # amber crease along each haunch crest, blade tip to tail (sits 6 mm proud of the ridge)
    for s in (1, -1):
        crest = [(-0.30, 1.07, 0.926), (-0.46, 1.06, 1.034), (-0.613, 1.06, 1.116), (-1.10, 1.06, 1.129), (-1.665, 1.06, 1.139),
                 (-1.90, 1.02, 1.034), (-2.12, 0.95, 0.909)]
        polyline_tube(f'{REV}_HAUNCH_{"R" if s > 0 else "L"}_AMBER_CREASE', [(x, s * y, z + 0.006) for x, y, z in crest], 0.0035,
                      coll, MAT['amber'])
    return hull


def cut_conflicts(new_names):
    """Trim A8 parts that occupy the cassette bay, glass aft of the shoulder, and the canard fold volume."""
    bay_lo, bay_hi = (-1.672, -1.30, 0.81), (-0.613, 1.30, 1.095)
    glass_lo, glass_hi = (-3.0, -1.3, 0.0), (-0.613, 1.3, 2.0)
    bay = box('cut_bay', bay_lo, bay_hi, collection(f'{REV}_TMP'))
    glass = box('cut_glass', glass_lo, glass_hi, collection(f'{REV}_TMP'))
    changed = []
    skip = {'PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL'}
    fin_map = Matrix.Translation((-1.675, 0, 0)) @ Matrix.Diagonal((0.78, 1, 1, 1)) @ Matrix.Translation((1.28, 0, 0))
    fwd = box('cut_fwd', (-1.672, -1.3, 0.0), (0.0, 1.3, 2.0), collection(f'{REV}_TMP'))
    for ob in list(SC.objects):
        if ob.type not in {'MESH', 'CURVE'} or ob.name in skip or ob.name.startswith(REV) or ob.name.startswith('cut'):
            continue
        if 'RAKED_V_TAIL' in ob.name or 'FIN_AMBER_RAKE' in ob.name:
            ob.matrix_world = fin_map @ ob.matrix_world
            ob['a9_change'] = 'raked fin shortened 22% in x so it starts behind the cassette shoulder (x -1.675) and ends at the tail'
            changed.append((ob.name, 'fin x-scaled 0.78 about its root and moved aft 0.395 m (no cut)'))
            continue
        if 'CENTRAL_REAR_DORSAL' in ob.name:
            name = ob.name
            apply_boolean(ob, fwd)
            changed.append((name, 'dorsal forward of x -1.672 removed; the haunch spine replaces it'))
            continue
        if 'SIDEGLASS' in ob.name or 'CANOPY_GASKET' in ob.name:
            if overlaps(ob, glass_lo, glass_hi):
                name = ob.name
                apply_boolean(ob, glass)
                changed.append((name, 'trimmed aft of x -0.613 (rear quarter glass shortened)'))
            continue
        if overlaps(ob, bay_lo, bay_hi):
            name = ob.name
            res = apply_boolean(ob, bay)
            changed.append((name, 'trimmed by cassette bay x -1.672..-0.613, z 0.81..1.095'))
            res['a9_change'] = 'trimmed by cassette bay'
    bpy.data.objects.remove(bay)
    bpy.data.objects.remove(glass)
    bpy.data.objects.remove(fwd)
    return changed


def build_supports(coll):
    """Ti posts from the torsion-sill tops (z 0.585, |y| 0.435-0.665) to the sleeve; clear of the rear motor
    bulkhead (x <= -1.39) and the rear shear walls (|y| <= 0.60). The hull skin is pierced where they pass."""
    hull = bpy.data.objects['PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL']
    for x in (-0.70, -1.30):
        for s in (1, -1):
            lo, hi = (x - 0.03, s * 0.635 - 0.028, 0.586), (x + 0.03, s * 0.635 + 0.028, Z_BOT - 0.0005)
            box(f'{REV}_SLEEVE_SUPPORT_POST_{"R" if s > 0 else "L"}_{"F" if x > -1 else "A"}', lo, hi, coll, MAT['ti'],
                props=dict(role='sleeve support into torsion sill (vertical shear and roll couple to tub)', mass_kg=0.9))
            cut = box('cut', (lo[0] - 0.003, min(lo[1], hi[1]) - 0.003, 0.58), (hi[0] + 0.003, max(lo[1], hi[1]) + 0.003, Z_BOT + 0.001),
                      collection(f'{REV}_TMP'))
            apply_boolean(hull, cut)
            bpy.data.objects.remove(cut)


def build_induction(coll):
    """Relocated engine induction: rear-fender front-face inlets, ducted below the sleeve to the A8 engine interface.
    Returns (ducts, cutters): cutters are the same path grown 15 mm and extended, for tunnelling the A8 panels."""
    ducts, cutters = [], []
    for s in (1, -1):
        path = [(-0.885, 1.06, 0.665), (-1.05, 1.00, 0.70), (-1.12, 0.78, 0.755), (-1.55, 0.76, 0.765), (-1.66, 0.55, 0.70),
                (-1.71, 0.39, 0.665), (-1.792, 0.39, 0.665)]

        def rings(w, h, ext=0.0):
            pts = [Vector(q) for q in path]
            tang = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
            pts[0] = pts[0] - tang[0] * ext            # extend the ends only; ring orientations follow the duct path
            pts[-1] = pts[-1] + tang[-1] * ext
            secs = []
            for i, q in enumerate(pts):
                a = tang[i]
                side = Vector((0, 0, 1)).cross(a).normalized()
                p = Vector((q.x, s * q.y, q.z))
                side.y *= s
                secs.append([tuple(p + side * dy + Vector((0, 0, dz)))
                             for dy, dz in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))])
            return secs
        w, h = 0.12, 0.07
        ducts.append(loft(f'{REV}_INDUCTION_DUCT_{"R" if s > 0 else "L"}', rings(w, h), coll, MAT['duct'],
                          props=dict(role='engine induction relocated from shoulder to rear-fender front face', mass_kg=1.6,
                                     area_m2=w * h, note='geometric routing only; mass flow not sized (A8 engine TBD)')))
        cutters.append(loft('cut_duct', rings(w + 0.03, h + 0.03, ext=0.02), collection(f'{REV}_TMP')))
    return ducts, cutters


def retime_a8():
    for ob in SC.objects:
        if ob.name.startswith('JOINT_WHEEL_POD_') or ob.name.startswith('JOINT_LEG_SLIDE_'):
            for fc in fcurves(ob):
                for kp in fc.keyframe_points:
                    if kp.co.x > 100:
                        kp.co.x += T_SHIFT
                        kp.handle_left.x += T_SHIFT
                        kp.handle_right.x += T_SHIFT
                fc.update()


def animate(wings, doors, canards):
    for side, (slide, surfaces, zc) in wings.items():
        s = 1 if side == 'R' else -1
        y_dep = slide.location.y
        y_st = y_dep - s * STROKE
        key(slide, 'location', 1, [(1, y_st), (T['slide'][0], y_st), (T['slide'][1], y_dep), (T['slide_in'][0], y_dep),
                                   (T['slide_in'][1], y_st), (END, y_st)])
        for ob in SC.objects:
            if ob.name.startswith(f'{REV}_JOINT_WING_{side}_LOCK_'):
                x_lock = ob.location.x
                x_free = x_lock - 0.07
                key(ob, 'location', 0, [(1, x_free), (T['lock'][0], x_free), (T['lock'][1], x_lock), (T['unlock'][0], x_lock),
                                        (T['unlock'][1], x_free), (END, x_free)])
        fh, _ = surfaces['FLAP']
        ah, _ = surfaces['AILERON']
        d = math.radians
        rx = fh.rotation_euler.x
        key(fh, 'rotation_euler', 0, [(1, rx), (T['flap'][0], rx), (T['flap'][1], rx + d(30)), (T['flap'][2], rx + d(30)),
                                      (T['flap'][3], rx), (END, rx)])
        rx = ah.rotation_euler.x
        sgn = 1 if side == 'R' else -1
        a = T['ail']
        key(ah, 'rotation_euler', 0, [(1, rx), (a[0], rx), (a[1], rx + sgn * d(20)), (a[2], rx - sgn * d(20)), (a[3], rx + sgn * d(10)),
                                      (a[4], rx), (END, rx)])
    for side, h in doors.items():
        r0 = h.rotation_euler.x
        key(h, 'rotation_euler', 0, [(1, r0), (T['door'][0], r0), (T['door'][1], r0 - math.pi), (T['door_close'][0], r0 - math.pi),
                                     (T['door_close'][1], r0), (END, r0)])
    for side, (fold, pitch) in canards.items():
        s = 1 if side == 'R' else -1
        z0 = fold.rotation_euler.z
        st = z0 + s * math.pi / 2
        key(fold, 'rotation_euler', 2, [(1, st), (T['canard_unfold'][0], st), (T['canard_unfold'][1], z0), (T['canard_fold'][0], z0),
                                        (T['canard_fold'][1], st), (END, st)])
        p0 = pitch.rotation_euler.x
        c = T['cpitch']
        key(pitch, 'rotation_euler', 0, [(1, p0), (c[0], p0), (c[1], p0 + math.radians(20)), (c[2], p0 - math.radians(15)), (c[3], p0), (END, p0)])
    SC.frame_start, SC.frame_end = 1, END
    SC.render.fps = FPS


def main():
    mats()
    removed = retire_a8()
    changed = cut_conflicts(set())
    coll_s = collection(f'{REV}_01 TELESCOPIC WING CASSETTE (SLEEVE = CARRY-THROUGH)')
    coll_w = collection(f'{REV}_02 WINGS FLAPS AILERONS')
    coll_c = collection(f'{REV}_03 TWO-AXIS NOSE CANARDS')
    coll_b = collection(f'{REV}_04 CASSETTE SHOULDERS, HATCHES, INDUCTION')
    hull = build_shoulders_and_hull(coll_b, removed)
    build_sleeve(coll_s)
    build_supports(coll_s)
    wings, doors, canards = {}, {}, {}
    for side in ('R', 'L'):
        wings[side] = build_wing(side, coll_w)
        build_lock_and_drive(side, coll_s)
        doors[side] = build_door(side, coll_b)
        canards[side] = build_canard(side, coll_c)
    ducts, duct_cutters = build_induction(coll_b)
    for d in duct_cutters:
        for name in ('PHANTOM_REAR_LEFT_WIDEBODY_ANGULAR_FENDER', 'PHANTOM_REAR_RIGHT_WIDEBODY_ANGULAR_FENDER',
                     'PHANTOM_LEFT_AFT_WHEEL_TO_ENGINE_FAIRING', 'PHANTOM_RIGHT_AFT_WHEEL_TO_ENGINE_FAIRING',
                     'PHANTOM_LEFT_BOOSTER_FAIRING_TAPER', 'PHANTOM_RIGHT_BOOSTER_FAIRING_TAPER',
                     'PHANTOM_LEFT_SIDEBLADE_AMBER', 'PHANTOM_RIGHT_SIDEBLADE_AMBER',
                     'PHANTOM_A8_INTEGRATED_DUCTED_FACETED_CFRP_HULL'):
            ob = bpy.data.objects.get(name)
            if ob and overlaps(ob, *world_bounds(d)) and touches(d, ob):
                apply_boolean(ob, d)
                o2 = bpy.data.objects.get(name)
                if o2 is not None and not o2.get('a9_change'):
                    o2['a9_change'] = 'tunnelled for relocated induction duct'
    retime_a8()
    animate(wings, doors, canards)
    tmp = bpy.data.collections.get(f'{REV}_TMP')
    if tmp:
        for ob in list(tmp.objects):
            bpy.data.objects.remove(ob)
        bpy.data.collections.remove(tmp)
    SC['vtx_revision'] = 'A9 telescopic stacked-sleeve wing cassette (approved Option T, 2026-11-02)'
    SC['a9_removed_objects'] = ', '.join(removed)
    SC['a9_trimmed_objects'] = ', '.join(n for n, _ in changed)
    SC['a9_status'] = 'kinematic CAD; loads DERIVED in engineering/phantom/wing_loads.py; not FEA/CFD/flight qualified'
    SC['a9_frame_convention'] = 'X forward, Z up, right-handed; A8 names RIGHT = +Y, LEFT = -Y'
    SC.frame_set(2)
    SC.frame_set(1)
    bpy.context.view_layer.update()
    return removed, changed


if not __import__('os').environ.get('A9_IMPORT_ONLY'):   # runs locally (--python) and as a Blendstra revision script
    removed, changed = main()
    print('A9_BUILD removed', len(removed), 'trimmed', len(changed))
    for n, why in changed:
        print('  TRIM', n, '-', why)
    if '--' in sys.argv:
        args = sys.argv[sys.argv.index('--') + 1:]
        if args:
            import os
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args[0]), copy=True)
            print('A9_SAVED', args[0])
