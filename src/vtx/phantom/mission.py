"""Phantom footprint validation for mission points (four legs, swept envelope, fan clearance).

Uses the shared TestWorld surface; geometry from the parameter file. Checks: terrain boundary
and water (as legacy), four-foot support level within the oleo stroke margin, swept envelope
radius (hull, deployed wings, pods, canards) clear of edges, fan disks clear of the surface,
roof margin and local vertical approach column. Not a route check.
"""
from __future__ import annotations
import math
import numpy as np
from .params import Params


def footprint(variant):
    P = Params(variant)
    half_len = 2.45
    wing_half = P.handover['aero_surfaces']['wing']['span_m'] / 2
    pod_out = P['pods.hinge_y_m'] + P['pods.tyre_radius_m']
    swept = math.hypot(half_len, max(wing_half, pod_out)) + 0.3
    feet = [(1.1, 0.53), (1.1, -0.53), (-1.18, 0.53), (-1.18, -0.53)]
    pods = [(P['pods.hinge_x_front_m'], P['pods.hinge_y_m']), (P['pods.hinge_x_front_m'], -P['pods.hinge_y_m']),
            (P['pods.hinge_x_rear_m'], P['pods.hinge_y_m']), (P['pods.hinge_x_rear_m'], -P['pods.hinge_y_m'])]
    return dict(swept_radius_m=swept, feet=feet, pods=pods, fan_disk_bottom_m=P['pods.hinge_z_m'] - P['pods.tyre_half_width_m'] + 0.225 + 0.52 - 0.52,
                leg_margin_m=0.06)


def validate_phantom(world, point, variant='phantom', heading_rad=0.0):
    fp = footprint(variant)
    x, y = point.x_m, point.y_m
    out = dict(ok=False, variant=variant, footprint=fp)
    if max(abs(x), abs(y)) > world.half - 8:
        out['reason'] = 'Outside the surveyed terrain support boundary'; return out
    w = world.water
    if abs(x - w['x']) < w['half_x'] + 4 and abs(y - w['y']) < w['half_y'] + 4:
        out['reason'] = 'Water: no flotation or support model'; return out
    z = world.surface_z(x, y)
    c, s = math.cos(heading_rad), math.sin(heading_rad)
    fz = [world.surface_z(x + c * fx - s * fy, y + s * fx + c * fy) for fx, fy in fp['feet']]
    if max(fz) - min(fz) > fp['leg_margin_m']:
        out['reason'] = 'Uneven four-leg support exceeds the oleo stroke margin'; return out
    for px, py in fp['pods']:
        gz = world.surface_z(x + c * px - s * py, y + s * px + c * py)
        if gz > z + 0.25:
            out['reason'] = 'Fan disk clearance: surface rises under a lift fan'; return out
    for a in np.linspace(0, 2 * math.pi, 33)[:-1]:
        if world.surface_z(x + fp['swept_radius_m'] * math.cos(a), y + fp['swept_radius_m'] * math.sin(a)) > z + .15:
            out['reason'] = 'Swept envelope (wings, pods, canards) intersects a surface edge or obstacle'; return out
    for o in world.obstacles:
        ox, oy, oz = o['center']; hx, hy, hz = o['half']
        dx = max(abs(x - ox) - hx, 0); dy = max(abs(y - oy) - hy, 0)
        inside = abs(x - ox) <= hx and abs(y - oy) <= hy
        if inside and z >= oz + hz - .01:
            if not o['landable']:
                out['reason'] = 'This structure is not a supported landing surface'; return out
            if hx - abs(x - ox) < fp['swept_radius_m'] + 0.5 or hy - abs(y - oy) < fp['swept_radius_m'] + 0.5:
                out['reason'] = 'Roof edge: insufficient wing/pod margin'; return out
        elif math.hypot(dx, dy) < fp['swept_radius_m'] + 1.5 and oz + hz > z + .2:
            out['reason'] = 'Obstacle blocks the local vertical approach column'; return out
    out.update(ok=True, reason='Four-leg support, swept envelope, fan clearance and local vertical approach column are clear', surface_z_m=z)
    return out
