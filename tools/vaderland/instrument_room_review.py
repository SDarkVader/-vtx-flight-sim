"""Audit the real aperture, mechanical display, retained frontage and native/render rays."""
import argparse
import json
import math
from pathlib import Path

import mujoco as mj
import numpy as np
from scipy.optimize import linprog

from airport_pass import probe
from instrument_room import touching
from parallax_review import planes
from streets import StreetIndex
from vtx.phantom.plant import PhantomAircraft
from vtx.world import make_world


def audit(out):
    out.mkdir(parents=True, exist_ok=True)
    w = make_world('vaderland-21')
    room = w.vaderland['instrument_room']
    origin, basis = np.asarray(room['origin']), np.asarray(room['basis'])
    def at(u,d,z):
        return origin + np.array([u,d,z]) @ basis

    by_id = {o['id']:o for o in w.obstacles}
    fixtures = [o for o in w.obstacles if o['id'].startswith('instrument-')]
    repairs = [o for o in w.obstacles if o.get('parent','').startswith('market-block-17-instrument-')]
    detached = [o['id'] for o in fixtures+repairs if o.get('parent') and not touching(o,by_id[o['parent']])]
    streets = StreetIndex(w)
    street_space = {o['id']:issues for o in fixtures if (issues:=streets.overlaps(o))}

    # A continuous, body-height corridor enters the room without using the window panes.
    bounds = [(-1.11,1.11),(-7.2,7.5),(.48,2.84)]
    local_blockers = []
    for o in w.obstacles:
        centre = np.asarray(o['center'])
        if np.any(abs(centre[:2]-origin[:2]) > 14+np.asarray(o['half'][:2])):
            continue
        if centre[2]-o['half'][2] > origin[2]+bounds[2][1]:
            continue
        # The two hoop swept discs lie in a compact area beside the aisle.
        p = planes(o)
        if linprog(np.zeros(3), A_ub=p[:,:3]@basis.T, b_ub=-p[:,3]-p[:,:3]@origin,
                   bounds=bounds,method='highs').success:
            local_blockers.append(o['id'])
    moving = [o for o in fixtures if 'motion' in o]
    max_sweep = 0.
    for o in moving:
        pivot=np.asarray(o['motion']['origin'])
        pts=np.asarray(o['vertices'])+o['center']
        max_sweep=max(max_sweep,float(np.linalg.norm(pts[:,:2]-pivot[:2],axis=1).max()))
    local_pivot=(np.asarray(moving[0]['motion']['origin'])-origin)@np.linalg.inv(basis)
    mechanism_margin=bounds[0][0]-local_pivot[0]-max_sweep

    plane=PhantomAircraft(w,'phantom-a10c',start_configuration='road')
    plane.spawn(-3885,0,0)
    rays,door_hits=[],[]
    def cast(t,label,o,d,limit):
        r=probe(plane,o.tolist(),d.tolist())
        rays.append(dict(**r,range_m=limit,label=label,time=t,doors={'west':1,'east':1}))
        return r
    fwd=-basis[1]/np.linalg.norm(basis[1])
    for u in (-1.05,-.60,0.,.60,1.05):
        for z in (.54,.91,1.36,1.72,2.30,2.72):
            ray=cast(0.,'Clear central doorway',at(u,2.33,z),fwd,9.)
            if 0<=ray['distance_m']<9.:
                door_hits.append(ray['geom'])
    for u in (-9.2,-7.9,-6.1,-4.2,-2.51,1.91,3.8,5.7,7.71,9.22):
        for z in (.41,.96,1.85,3.73,5.13,5.77,6.66):
            cast(0.,'Fabric and glazing',at(u,2.13,z),fwd,16.)

    for direction in (-1.,1.):
        for d in (-5.20,-5.02,-4.8,-4.61):
            for z in (1.87,2.01,2.21):
                cast(0.,'Optical assembly',at(5.29-direction*2.69,d,z),
                     basis[0]*direction/np.linalg.norm(basis[0]),5.38)

    for t in (0.,8.,18.,27.,41.,62.):
        plane.scenery.apply(plane.data,scene_time=t)
        mj.mj_kinematics(plane.model,plane.data)
        for a in np.linspace(0,math.tau,10,endpoint=False)+.037:
            local=np.array([math.cos(a),math.sin(a),0.])
            direction=-(local@basis);direction/=np.linalg.norm(direction)
            for z in (1.31,2.37,2.91,3.64,4.17):
                point=at(-4.18+2.38*local[0],-5.57+2.38*local[1],z)
                cast(t,'Clock-driven orrery',point,direction,4.76)

    result={
        'fixtures':len(fixtures),'support_joints_missing':detached,
        'street_envelope_intrusions':street_space,'door_hits':door_hits,'corridor_hits':local_blockers,
        'verified_width_m':2.22,'max_moving_radius_m':max_sweep,'mechanism_margin_m':mechanism_margin,
        'native_rays':len(rays),'moving_rays_returning_mechanism':sum(
            r['label']=='Clock-driven orrery' and (r['geom'] or '').startswith('instrument-orbit-') for r in rays),
    }
    (out/'room-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'architecture-rays.json').write_text(json.dumps(rays),encoding='utf-8')
    print(json.dumps(result,indent=2))
    if detached or door_hits or street_space or local_blockers or mechanism_margin<.3:
        raise SystemExit('Instrument Room audit failed')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out',type=Path)
    audit(parser.parse_args().out)
