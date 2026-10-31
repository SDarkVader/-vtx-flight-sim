"""Fuel/nozzle design arithmetic and clamped-shaft bench; never a pilot."""
import argparse,json,math,hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco as mj
from vtx.aircraft import Aircraft,ROOT,DT,G
from vtx.aero import ideal_hover


def exhaust_case(mdot,velocity,exit_temperature_k=700.,duct_wall_m=.001,
                 total_duct_length_m=1.,material_density_kg_m3=8000.):
    """Explicit sensitivity inputs, pressure-matched static outlet, NOT C30P data.

    Two equal downward outlets; ideal-gas sizing with assumed R=287J/kg/K.
    Mass is straight thin-wall tubing only: excludes bends, mounts and shielding.
    No values returned here are connected to live aircraft forces.
    """
    rho=101325/(287*exit_temperature_k)
    area_total=mdot/(rho*velocity)
    diameter=math.sqrt(4*(area_total/2)/math.pi)
    mass=material_density_kg_m3*math.pi*diameter*duct_wall_m*total_duct_length_m
    thrust=mdot*velocity
    return dict(status='HYPOTHETICAL STATIC SENSITIVITY, NOT ENGINE DATA OR INSTALLED HARDWARE',
        exhaust_mass_flow_kg_s=mdot,exit_velocity_m_s=velocity,
        assumed_exit_temperature_k=exit_temperature_k,ambient_pressure_pa=101325,
        assumed_gas_constant_j_kg_k=287,pressure_thrust_n=0,
        outlet_count=2,total_area_m2=area_total,each_diameter_m=diameter,
        upward_reaction_n=thrust,jet_kinetic_power_w=.5*mdot*velocity**2,
        straight_duct_mass_kg=mass,assumed_wall_m=duct_wall_m,
        assumed_total_straight_length_m=total_duct_length_m,
        assumed_density_kg_m3=material_density_kg_m3,
        shaft_derate_unknown=True,installed_net_lift_unknown=True)


def dynamometer(mode):
    """Actual articulated plant, housing fixed to a test stand above terrain.

    Engine and collective steps are a disclosed load bench, not a flight trace.
    World weld reactions are represented by removing only the root free joint.
    """
    p=Aircraft(rpm=1200,fuel_kg=10,governor_mode=mode,engine_power_limit_kw=300.)
    tree=ET.fromstring(p.xml);root=tree.find('./worldbody/body[@name="airframe"]')
    root.remove(root.find('freejoint'));root.set('pos','0 0 30')
    p.model=mj.MjModel.from_xml_string(ET.tostring(tree,encoding='unicode'))
    p.model.hfield_data[:]=(p.world.heights/70).ravel();p.data=mj.MjData(p.model)
    p.jids={mj.mj_id2name(p.model,mj.mjtObj.mjOBJ_JOINT,i):i for i in range(p.model.njnt)}
    p.qadr={n:int(p.model.jnt_qposadr[i]) for n,i in p.jids.items()}
    p.vadr={n:int(p.model.jnt_dofadr[i]) for n,i in p.jids.items()}
    mj.mj_forward(p.model,p.data);p.command['engine']=1.
    samples=[]
    for k in range(int(24/DT)):
        # Demand a sustained normal rotor load, then unload the stand.
        p.command['collective_deg']=[20. if 5<=p.data.time<20 else 0.]*4
        p.step()
        assert p.power['engine_w']<=300000*p.engine_spool+1e-5
        if k%40==0:samples.append(dict(t_s=float(p.data.time),rpm=p.joint('rotor1_spin')[1]*30/math.pi,
            engine_kw=p.power['engine_w']/1000,governor=p.governor.telemetry.copy()))
    loaded=[s for s in samples if 18<s['t_s']<20]
    return dict(status='CLAMPED DYNAMOMETER, NOT PILOTED FLIGHT',mode=mode,
        loaded_rpm_mean=float(np.mean([s['rpm'] for s in loaded])),
        loaded_engine_kw_mean=float(np.mean([s['engine_kw'] for s in loaded])),
        peak_engine_kw=max(s['engine_kw'] for s in samples),
        peak_rpm=max(s['rpm'] for s in samples),fuel_used_kg=float((p.fuel_initial-p.fuel).sum()),
        samples=samples)


def study(bench=False):
    old=Aircraft(fuel_kg=60).mass_properties();new=Aircraft(fuel_kg=10).mass_properties()
    a=16.;oldideal=ideal_hover(old['mass_kg'],a);newideal=ideal_hover(new['mass_kg'],a)
    thrust=(old['mass_kg']-new['mass_kg'])*G
    result=dict(status='CONDITIONAL ENGINEERING CALCULATION; NO STABILITY OR EXHAUST LIFT CLAIM',
        baseline=old,reduced_fuel=new,weight_removed_n=thrust,
        ideal_induced_power_saved_w=oldideal['ideal_induced_power_w']-newideal['ideal_induced_power_w'],
        ideal_hover_power_ratio=newideal['ideal_induced_power_w']/oldideal['ideal_induced_power_w'],
        fuel_plan=dict(initial_total_kg=10,per_cell_kg=2.5,reference_sfc_kg_kwh=.4,
            maximum_continuous_kw=469.8,planning_duration_s=120,planning_reserve_kg=2,
            max_power_fuel_for_duration_kg=469.8*.4*120/3600,
            minimum_with_planning_reserve_kg=469.8*.4*120/3600+2,
            claim='Planning allowance only; no qualified endurance/reserve'),
        exhaust_status='CALIBRATION_BLOCKED; live exhaust lift remains zero. Published engine outlets point UP.',
        required_measured_inputs=['Exhaust airflow, total pressure and total temperature vs shaft load',
            'Existing outlet areas and installed inlet/exit momentum',
            'Duct pressure loss and resulting shaft-power/SFC penalty',
            'Added duct, insulation and mounting masses and load paths',
            'Plume, ground impingement, recirculation and thermal clearances'],
        hypothetical_outlets=[exhaust_case(m,v) for m in [1.,2.,4.] for v in [100.,200.]],
        equivalent_jet_to_fuel_mass_saving=[dict(hypothetical_exhaust_kg_s=m,
            required_velocity_m_s=thrust/m,jet_ke_w=thrust**2/(2*m)) for m in [1.,2.,4.]])
    if bench:result['shaft_bench']=[dynamometer(m) for m in ['legacy-p','pi']]
    (ROOT/'evidence/power_fuel_exhaust_study.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='shaft_bench'},indent=2))
    if bench:print('SHAFT_BENCH', [{k:v for k,v in r.items() if k!='samples'} for r in result['shaft_bench']])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dynamometer',action='store_true')
    study(parser.parse_args().dynamometer)
