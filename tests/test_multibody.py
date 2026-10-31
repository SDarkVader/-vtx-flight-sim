"""Independent conservation / mechanical checks, not flight demonstrations."""
import json
import math
from pathlib import Path
import mujoco as mj
import numpy as np
import pytest
from vtx.aircraft import Aircraft,DT,G
from vtx.aero import BladeElementModel,ideal_hover
from vtx.world import TestWorld
from vtx.mission_selection import MapPoint

def isolated():
    p=Aircraft();p.spawn(0,0,30);p.model.opt.gravity[:]=0
    mj.mj_forward(p.model,p.data)
    return p

def independent_momentum(p):
    m,d=p.model,p.data
    mass=m.body_mass.sum();cg=(m.body_mass[:,None]*d.xipos).sum(axis=0)/mass
    linear=np.zeros(3);angular=np.zeros(3)
    for i in range(1,m.nbody):
        v=np.zeros(6);mj.mj_objectVelocity(m,d,mj.mjtObj.mjOBJ_BODY,i,v,0)
        r=d.ximat[i].reshape(3,3);j=r@np.diag(m.body_inertia[i])@r.T
        linear+=m.body_mass[i]*v[3:]
        angular+=j@v[:3]+np.cross(d.xipos[i]-cg,m.body_mass[i]*v[3:])
    return linear,angular,cg

def test_source_allocation_and_positive_full_tensors():
    p=Aircraft();j=p.ledger
    assert j['subsystem_allocations_kg']['P10']>42 # material added, not mass-free extension
    assert j['empty']['mass_kg']==pytest.approx(sum(j['subsystem_allocations_kg'].values()))
    assert p.model.body_mass.sum()==pytest.approx(j['empty']['mass_kg']+170+60)
    for b in j['bodies'].values():
        i=np.array(b['inertia_centroid_kg_m2']);assert np.linalg.eigvalsh(i).min()>0
        assert np.allclose(i,i.T)
    assert len(j['parts'])==763 and len(j['excluded'])==32
    assert len({s['id'] for s in j['parts']})==763

def test_no_initial_interpenetration_and_full_gear_clearance():
    p=Aircraft();p.spawn(13.7,-28.4,0)
    assert not any(c.dist<0 for c in p.data.contact[:p.data.ncon])
    feet=[s for s in p.ledger['parts'] if 'contact foot' in s['name']]
    lowest=min(s['bounds_m'][0][2] for s in p.ledger['parts'] if s['body']=='airframe')
    assert lowest-min(f['bounds_m'][0][2] for f in feet)-.25>.05

def test_mass_parallel_axis_independent_from_solver():
    p=Aircraft();p.spawn(0,0,0);j=p.ledger
    parts=list(j['parts'])
    for x in [-.3,.3]:
        r=np.array([.2,.16,.45]);tensor=np.diag(85/5*(sum(r*r)-r*r))
        parts.append(dict(mass_kg=85,centroid_m=[x,.02,1.445],inertia_centroid_kg_m2=tensor))
    for t in j['tanks']:
        a=np.array(t['axis']);a/=np.linalg.norm(a);jp=15*.18**2/2;jt=15*(3*.18**2+.48**2)/12
        parts.append(dict(mass_kg=15,centroid_m=t['centroid_m'],inertia_centroid_kg_m2=jt*np.eye(3)+(jp-jt)*np.outer(a,a)))
    mass=sum(q['mass_kg'] for q in parts)
    cg=sum(q['mass_kg']*np.array(q['centroid_m']) for q in parts)/mass
    inertia=np.zeros((3,3))
    for q in parts:
        v=np.array(q['centroid_m'])-cg
        inertia+=np.array(q['inertia_centroid_kg_m2'])+q['mass_kg']*((v@v)*np.eye(3)-np.outer(v,v))
    actual=p.mass_properties()
    np.testing.assert_allclose(actual['inertia_world_kg_m2'],inertia,atol=2e-7)
    np.testing.assert_allclose(np.array(actual['cg_world_m'])-p.data.qpos[:3],cg,atol=1e-9)

def test_freefall_center_of_mass_has_full_gravity():
    p=isolated();p.model.opt.gravity[:]=[0,0,-G]
    _,_,initial=independent_momentum(p)
    for _ in range(80):mj.mj_step(p.model,p.data)
    mj.mj_forward(p.model,p.data)
    momentum,_,end=independent_momentum(p)
    np.testing.assert_allclose(momentum/p.model.body_mass.sum(),[0,0,-G*.2],atol=2e-8)
    # Semi-implicit position quadrature differs from continuous by 1/2*g*T*dt.
    assert end[2]-initial[2]==pytest.approx(-.5*G*.2*(.2+DT),abs=1e-7)

def test_solver_angular_momentum_matches_independent_body_sum():
    p=isolated();p.data.qvel[3:6]=[.2,-.3,.5]
    p.data.qvel[p.vadr['rotor1_spin']]=50
    mj.mj_forward(p.model,p.data);mj.mj_subtreeVel(p.model,p.data)
    _,h,_=independent_momentum(p)
    np.testing.assert_allclose(h,p.data.subtree_angmom[p.bids['airframe']],atol=1e-9)

def test_torque_free_total_inertial_momentum():
    p=isolated();p.data.qvel[3:6]=[.2,-.3,.5]
    mj.mj_forward(p.model,p.data);_,before,_=independent_momentum(p)
    for _ in range(400):mj.mj_step(p.model,p.data)
    mj.mj_forward(p.model,p.data);_,after,_=independent_momentum(p)
    assert np.linalg.norm(after-before)/np.linalg.norm(before)<.002

@pytest.mark.parametrize('sense',[1,-1])
def test_internal_rotor_spinup_exchanges_momentum_with_airframe(sense):
    p=isolated();p.data.eq_active[:]=0
    for _ in range(80):
        p.data.qfrc_applied[:]=0;p.data.qfrc_applied[p.vadr['rotor1_spin']]=sense*25
        mj.mj_step(p.model,p.data)
    mj.mj_forward(p.model,p.data);_,h,_=independent_momentum(p)
    assert np.linalg.norm(h)<.01
    assert sense*p.data.qvel[5]<0
    assert sense*p.joint('rotor1_spin')[1]>0

def test_gyro_magnitude_and_spin_sense_against_angular_momentum_equation():
    p=isolated();p.data.eq_active[:]=0
    answers=[]
    for sense in [1,-1]:
        p.data.qvel[:]=0;p.data.qvel[p.vadr['nacelle1_x']]=.3
        p.data.qvel[p.vadr['rotor1_spin']]=sense*50
        mj.mj_forward(p.model,p.data);answers.append(p.data.qfrc_bias[4])
    odd=(answers[0]-answers[1])/2
    jz=p.ledger['bodies']['rotor1']['inertia_centroid_kg_m2'][2][2]
    assert odd==pytest.approx(-jz*50*.3,rel=1e-5)

def test_force_impulse_and_actual_moment_arm():
    p=isolated();m,d=p.model,p.data
    f=np.array([120.,-80.,350.]);point=d.xpos[p.bids['rotor1']].copy()
    _,_,cg=independent_momentum(p)
    mj.mj_applyFT(m,d,f,np.zeros(3),point,p.bids['rotor1'],d.qfrc_applied)
    mj.mj_step(m,d);mj.mj_forward(m,d)
    linear,angular,_=independent_momentum(p)
    np.testing.assert_allclose(linear,f*DT,rtol=3e-5,atol=1e-5)
    np.testing.assert_allclose(angular,np.cross(point-cg,f)*DT,rtol=3e-4,atol=1e-4)

def test_zero_rpm_no_lift_and_provisional_800rpm_deficit():
    p=Aircraft();a=p.aero
    assert a.evaluate(0,30)['thrust_n']==0
    peak=max(a.evaluate(800*math.pi/30,b)['thrust_n'] for b in np.linspace(0,30,61))
    assert peak*4<p.model.body_mass.sum()*G
    for b in [10,15,20,25]:
        r=a.evaluate(800*math.pi/30,b)
        assert r['thrust_n']*r['induced_mps']<=r['torque_nm']*800*math.pi/30*1.005

def test_actuator_jacobian_is_physical_lever_and_no_root_wrench():
    p=Aircraft();m,d=p.model,p.data;tid=0
    start=m.ten_J_rowadr[tid];count=m.ten_J_rownnz[tid]
    jac=np.zeros(m.nv);jac[m.ten_J_colind[start:start+count]]=d.ten_J[start:start+count]
    np.testing.assert_allclose(jac[:6],0,atol=1e-12)
    # dL/dtheta = (.25*.30 + .12*.10)/sqrt(.10²+.30²).
    assert jac[p.vadr['nacelle1_x']]==pytest.approx((.25*.3+.12*.1)/math.hypot(.1,.3),rel=1e-10)

def test_gear_settles_on_six_contacts_without_underside_strike():
    p=Aircraft();p.spawn(0,0,0)
    for _ in range(1600):p.step()
    assert not p.crashed
    assert np.linalg.norm(p.data.qvel[:6])<.03
    assert sum(p.joint(f'gear{i}_stroke')[0]>.02 for i in range(1,7))==6

def test_fuel_recomputes_mass_and_inertia_and_obeys_power_accounting():
    p=Aircraft();p.spawn(0,0,0);initial=p.mass_properties();p.command['engine']=1
    p.command['collective_deg']=[12]*4
    for _ in range(1200):
        p.step()
        assert p.power['engine_w']<=469800*p.engine_spool+1e-5
        assert p.power['engine_w']<=p.power['fuel_chemical_w']+1e-6
    used=(p.fuel_initial-p.fuel).sum()
    assert used==pytest.approx(p.energy['engine_j']/3.6e6*.4,abs=1e-10)
    assert p.mass_properties()['mass_kg']<initial['mass_kg']
    assert not np.allclose(p.mass_properties()['inertia_world_kg_m2'],initial['inertia_world_kg_m2'])

@pytest.mark.parametrize('point',[(13.7,-28.4),(-42.5,78.1),(-73.13,-102.7),(150.,-95.)])
def test_arbitrary_world_support_including_roofs(point):
    w=TestWorld();answer=w.validate(MapPoint(*point),'departure')
    assert answer.valid,answer.reason

@pytest.mark.parametrize('point',[(115.,115.),(63.,45.),(600.,0.),(-265.,30.)])
def test_world_refuses_invalid_support_or_obstacle(point):
    w=TestWorld();answer=w.validate(MapPoint(*point),'destination')
    assert not answer.valid

def test_terrain_surface_matches_collision_ray():
    p=Aircraft();m,d=p.model,p.data
    for x,y in [(-345.,82.),(390.,-327.),(33.3,-44.7)]:
        geom=np.array([-1],dtype=np.int32)
        dist=mj.mj_ray(m,d,np.array([x,y,150.]),np.array([0,0,-1.]),None,1,-1,geom)
        assert 150-dist==pytest.approx(p.world.surface_z(x,y),abs=1e-6)

def test_physics_determinism_for_bench_inputs():
    a=Aircraft();b=Aircraft()
    for p in [a,b]:p.spawn(-12.3,42.1,0);p.command['engine']=.5
    for _ in range(80):a.step();b.step()
    np.testing.assert_array_equal(a.data.qpos,b.data.qpos)
