"""Document conditional design comparisons; this is NOT a flight script."""
import json,math
from pathlib import Path
import numpy as np
from vtx.aircraft import Aircraft,G,ROOT
from vtx.aero import BladeElementModel,ideal_hover

p=Aircraft();ledger=p.ledger;mass=p.model.body_mass.sum()
rows=[]
for cl in [.8,1.2,1.6]:
    a=BladeElementModel(ledger['blade'],cl_max=cl)
    for rpm in [800,1200]:
        scans=[(pitch,a.evaluate(rpm*math.pi/30,pitch)) for pitch in np.linspace(0,30,121)]
        peak=max(scans,key=lambda v:v[1]['thrust_n'])
        rows.append(dict(cl_max_assumed=cl,rpm=rpm,ratio=6016/rpm,
                         max_collective_deg=float(peak[0]),four_rotor_peak_thrust_n=peak[1]['thrust_n']*4,
                         shaft_power_at_peak_w=peak[1]['torque_nm']*rpm*math.pi/30*4,
                         thrust_weight_ratio=peak[1]['thrust_n']*4/(mass*G),
                         centrifugal_load_ratio_vs_800=(rpm/800)**2,
                         tip_mach=rpm*math.pi/30*ledger['blade']['radius_m']/340.3))
gear=[]
for variant in ['baseline','critical-damping-proposal']:
    c=Aircraft(gear_variant=variant);c.spawn(0,0,.20)
    for _ in range(1600):c.step()
    gear.append(dict(variant=variant,initial_drop_m=.20,max_contact_force_n=c.max_impact_n,
                     underside_collision=c.crashed,final_speed_mps=float(np.linalg.norm(c.data.qvel[:3])),
                     final_gear_compression_m=[float(c.joint(f'gear{i}_stroke')[0]) for i in range(1,7)]))
out=dict(status='Conditional calculations and drop benches; NOT piloted flights or calibrated performance',
         revision=ledger['revision'],mass_kg=float(mass),empty_kg=ledger['empty']['mass_kg'],
         ideal_lower_bound=ideal_hover(mass,4*math.pi*ledger['blade']['radius_m']**2),
         polar_speed_sensitivity=rows,landing_gear_comparison=gear,
         conclusions=['800 rpm fails to support allocated weight for every listed provisional CLmax.',
           '1200 rpm requires a different gearset and 2.25x centrifugal load; it is a proposal, not qualified hardware.',
           'No installed engine derating, laminate/gear/CV ratings or rotor polar measurements are supplied.'])
(ROOT/'evidence/engineering_screen.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
