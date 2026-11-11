"""RC01 F03 isolated calm-water, 6-DOF *reduced-order* exploratory solver.
Not a validated planing, CFD, FEA, or MuJoCo experiment. Deterministic, source geometry.
Body +X nose, +Y starboard (sign conversion needed in VTX Phantom), +Z up. SI.
"""
import json, math, csv, argparse
from pathlib import Path
import numpy as np
import trimesh
from scipy.optimize import root
from scipy.stats import qmc
from scipy.spatial.transform import Rotation

ST=[('N0',3.30,.115,.24,.82),('N1',2.50,.45,.12,1.04),('N2',1.45,.68,.035,1.19),('N3',.22375,.80,0.,1.20),('N4',-.6485,.75,.035,1.16),('N5',-1.75,.38,.12,.91)]
G=9.80665; RHO_W=999.1; RHO_A=1.225; P_ATM=101325.; T_A=288.15
# Test-water bathymetry is a virtual separate branch; not in world.py or visual terrain.
LAKE={'center_xy_m':[-265.,30.], 'half_extent_xy_m':[28.,80.], 'surface_z_m':0.,'assumed_bottom_z_m':-3.,'wave_height_m':0.}

def ring(s):
 _,x,w,k,deck=s
 return np.array([[0,k],[.80*w,k+.27*(deck-k)],[w,k+.70*(deck-k)],[.50*w,deck],[0,deck+.075],[-.50*w,deck],[-w,k+.70*(deck-k)],[-.80*w,k+.27*(deck-k)]],float)

RING=[ring(s) for s in ST]

def hull_mesh():
    verts=np.array([[s[1],y,z] for s,q in zip(ST,RING) for y,z in q]);faces=[]
    for j in range(len(ST)-1):
        for k in range(8):
            a=j*8+k;b=j*8+(k+1)%8;c=(j+1)*8+k;d=(j+1)*8+(k+1)%8
            faces.extend([[a,c,b],[b,c,d]])
    for k in range(1,7):faces.append([0,k,k+1])
    base=(len(ST)-1)*8
    for k in range(1,7):faces.append([base,base+k+1,base+k])
    m=trimesh.Trimesh(vertices=verts,faces=faces,process=False)
    assert m.is_watertight and m.is_winding_consistent and m.volume>0,(m.is_watertight,m.is_winding_consistent,m.volume)
    return m

def hull_samples(power=15):
    r=qmc.Sobol(d=3,scramble=False).random_base2(m=power)
    lo=np.array([-1.75,-.8,0.]);hi=np.array([3.3,.8,1.28]);pts=lo+(hi-lo)*r
    ins=np.zeros(len(pts),bool)
    for j in range(len(ST)-1):
        xhi=ST[j][1];xlo=ST[j+1][1]
        ix=np.where((pts[:,0]<=xhi)&(pts[:,0]>=xlo))[0]
        if not len(ix):continue
        alpha=(xhi-pts[ix,0])/(xhi-xlo)
        rr=(1-alpha[:,None,None])*RING[j][None,:,:]+alpha[:,None,None]*RING[j+1][None,:,:]
        ps=pts[ix,1:3];dr=rr[:,(np.arange(8)+1)%8,:]-rr
        cross=dr[:,:,0]*(ps[:,None,1]-rr[:,:,1])-dr[:,:,1]*(ps[:,None,0]-rr[:,:,0])
        ins[ix]=(np.all(cross>=-1e-10,axis=1)|np.all(cross<=1e-10,axis=1))
    m=hull_mesh();return pts[ins],m.volume

def float_samples(power=11):
    # Two hull-like streamlined volume approximations. Shape candidate for sponsons.
    s=qmc.Sobol(d=3,scramble=False).random_base2(m=power)
    unit=2*s-1
    inside=unit[(unit*unit).sum(axis=1)<=1]
    vol=(4/3)*math.pi*.56*.18*.14
    both=[]
    for y in (-3.80,3.80):
        pts=inside*np.array([.56,.18,.14])+np.array([-.34,y,.42])
        both.append((pts,vol))
    return both

class Hydro:
    def __init__(self,cg=(.45,0,.59),with_floats=True,sample_power=15):
        h,vol=hull_samples(sample_power)
        self.groups=[('HULL',h,vol)]
        if with_floats:
            self.groups += [('FLOAT_PORT',*float_samples()[0]),('FLOAT_STARBOARD',*float_samples()[1])]
        self.cg=np.array(cg,dtype=float)
        self.rho=RHO_W;self.name='F03 initial cross-section/float candidate'
        self.total_vol=sum(v for _,_,v in self.groups)
        xh=self.groups[0][1][:,0]
        X=np.array([s[1] for s in ST])
        W=np.zeros((len(xh),len(X)))
        for j in range(len(X)-1):
            mask=(xh<=X[j])&(xh>=X[j+1]);lam=(X[j]-xh[mask])/(X[j]-X[j+1])
            W[mask,j]+=1-lam;W[mask,j+1]+=lam
        self.hull_station_weights=W

    def compute(self,position,angles):
        # world coordinate position of body origin; static water surface at z=0.
        rot=Rotation.from_euler('xyz',angles).as_matrix()
        outF=np.zeros(3);outM=np.zeros(3);by={};centres={};b_force=[]
        for name,body_pts,volume in self.groups:
            transformed=body_pts@rot.T
            depth=-(transformed[:,2]+position[2])
            eps=.009
            wet_weight=np.clip(.5+depth/(2*eps),0.,1.)
            n=float(wet_weight.sum())
            elemF=self.rho*G*volume/max(len(body_pts),1)
            fz=n*elemF
            partF=np.array([0.,0.,fz]);outF+=partF
            if n>0:
                originCG=self.cg@rot.T
                c=np.sum(transformed*wet_weight[:,None],axis=0)/n
                aboutCG=c-originCG
                partM=np.cross(aboutCG,partF)
                centres[name]=(c+position).tolist()
                outM+=partM
            by[name]=fz
            if name=='HULL':
                dist_force=elemF*(wet_weight @ self.hull_station_weights)
                for st,station_f in zip(ST,dist_force):by['BULKHEAD_'+st[0]+'_N']=float(station_f)
            b_force.append(fz)
        return outF,outM,by,centres

    def equilibrium(self,mass=900.,allow_pitch=True):
        def residual(v):
            z,pitch=v
            f,m,_,_=self.compute(np.array([0,0,z]),[0,pitch,0])
            return [(f[2]-mass*G)/(mass*G),(m[1])/(mass*G*1.5)]
        if allow_pitch:
            r=root(residual,[-.34,-.02],tol=1e-8)
            if not r.success:raise RuntimeError('Could not find heave/pitch hydrostatic equilibrium: '+str(r.message))
            z,pitch=r.x
        else:
            from scipy.optimize import brentq
            z=brentq(lambda d:self.compute([0,0,d],[0,0,0])[0][2]-mass*G,-1.0,0.1)
            pitch=0
        f,m,by,centres=self.compute([0,0,z],[0,pitch,0])
        return {'z0_m':float(z),'pitch_rad':float(pitch),'pitch_deg':float(math.degrees(pitch)),
                'total_buoyancy_N':float(f[2]),'net_buoyancy_residual_N':float(f[2]-mass*G),
                'by_N':by,'buoyancy_centres_m':centres}

    def roll_restoring(self,mass,z0,pitch):
        tests=[]
        for deg in [-5.,0.,5.]:
            f,m,_,_=self.compute([0,0,z0],[math.radians(deg),pitch,0])
            tests.append((deg,m[0],f[2]))
        k=-(tests[-1][1]-tests[0][1])/(2*math.radians(5))
        return {'Kroll_Nm_per_rad':float(k),'roll_restoring_torque_at_plus5_Nm':float(tests[-1][1]),'tests':tests}


def inertia(mass):
    # provisional nominal inertia tensor only. Not computed from actual components yet.
    return np.diag([1750,1900,2400])*mass/900.

def run_case(name,mass=900,cg=(.45,0,.59),with_floats=True,seconds=24,dt=.02,drag_area=.27,
             dynamic=True,thrust_profile='nominal'):
    H=Hydro(cg,with_floats)
    eq=H.equilibrium(mass)
    z0=eq['z0_m'];pi=eq['pitch_rad']
    stiffness=H.roll_restoring(mass,z0,pi)
    # Numerically estimate pitch restoring stiffness with the *same* hull geometry.
    e=.025
    pos=np.array([0.,0.,z0]);mp=H.compute(pos,[0,pi+e,0])[1][1];mm=H.compute(pos,[0,pi-e,0])[1][1]
    Kpitch=-(mp-mm)/(2*e)
    outcome={'name':name,'mass_kg':mass,'cg_body_m':list(cg),'with_floats':with_floats,'eq':eq,
      'static_roll':stiffness,'static_Kpitch_Nm_per_rad':float(Kpitch),
      'total_closed_nominal_geometry_volume_m3':H.total_vol,
      'inertia_estimate_kgm2':inertia(mass).diagonal().tolist(),
      'model_fidelity':'reduced-order hydrostatics, lumped hydrodynamic drag and provisional joint loads; NOT CFD/planing/FEA'}
    if not dynamic: return outcome,[]
    tvals=np.arange(0,seconds+dt/2,dt)
    state=np.zeros(12)
    # coordinates: xyz origin relative to lake; then xyz Euler; vworld then angular vel world.
    state[2]=z0;state[3]=math.radians(3.0);state[4]=pi;state[5]=math.pi/2
    I=inertia(mass)
    log=[]
    last_fb=np.zeros(3)
    for t in tvals:
        x,y,z,roll,pitch,yaw=state[:6]
        vel=state[6:9];omega=state[9:12]
        rot=Rotation.from_euler('xyz',[roll,pitch,yaw]).as_matrix()
        F_h,M_h,by,centres=H.compute(state[:3],state[3:6])
        # zero-thrust 0-3 s; forward 3-16 s; starboard yaw 16-20 s; zero 20-24 s
        if thrust_profile=='nominal':
            thrust=0. if t<3 or t>=21 else (1100. if t<16 else 900.)
            dthrust=0. if t<16 or t>=21 else 120.
        else:thrust=dthrust=0.
        # Port y-negative starboard y-positive, fan force split controls yaw.
        Tp=(thrust-dthrust)/2;Ts=(thrust+dthrust)/2
        rp=np.array([-2.22,-1.22,1.70])-H.cg;rs=np.array([-2.22,1.22,1.70])-H.cg
        T_body=np.array([Tp+Ts,0,0])
        moment_thrust=np.cross(rp,[Tp,0,0])+np.cross(rs,[Ts,0,0])
        F_t=rot@T_body
        M_t=rot@moment_thrust
        # water motion damping, not validated resistance model
        vb=rot.T@vel
        Cx=RHO_W*drag_area*.5
        Fd_body=np.array([-Cx*vb[0]*abs(vb[0]),-950*vb[1],-2850*vb[2]])
        Fd=rot@Fd_body
        # Munk-type yaw sensitivity: potential-flow slender-body *estimated*, not calibrated.
        beta=math.atan2(vb[1],max(abs(vb[0]),.15))
        added_mass_long=70.;added_mass_trans=270.
        u=max(abs(vb[0]),0)
        M_munk=(added_mass_trans-added_mass_long)*u*u*math.sin(beta)*math.cos(beta)
        damp_body=np.array([-1800*omega[0],-2200*omega[1],-1700*omega[2]+M_munk])
        M_d=rot@damp_body
        F_tot=F_h+F_t+Fd+np.array([0,0,-mass*G])
        M_tot=M_h+M_t+M_d
        # world inertia: transform body principal hypothetical inertia
        acceleration=F_tot/mass
        # angular velocities and inertia are BODY coordinates. Preserve axis convention under world yaw.
        Mbody=rot.T@M_tot
        alpha_body=np.linalg.solve(I,Mbody-np.cross(omega,I@omega))
        # semi-implicit Euler; limited speed and angle only as safety abort / not artificial stabilizer
        if t<seconds:
            state[6:9]+=dt*acceleration
            state[9:12]+=dt*alpha_body
            state[:3]+=dt*state[6:9]
            newrot=Rotation.from_matrix(rot)*Rotation.from_rotvec(state[9:12]*dt)
            state[3:6]=newrot.as_euler("xyz")
        x,y,z=state[:3];roll,pitch,yaw=state[3:6]
        port=by.get('FLOAT_PORT',0);star=by.get('FLOAT_STARBOARD',0)
        # pressure allocation to nearest bulkhead station is *not* an FEA joint reaction.
        # It is a station load proxy, useful for further load-path sizing.
        p_by=[]
        for j,s in enumerate(ST):
            xx=s[1];dist=min(abs(xx-p[1]) for p in ST)
            p_by.append(0.)
        rec=dict(time_s=float(t),x_m=float(x),y_m=float(y),z_origin_m=float(z),
           roll_deg=float(math.degrees(roll)),pitch_deg=float(math.degrees(pitch)),yaw_deg=float(math.degrees(yaw-math.pi/2)),
           vx_mps=float(state[6]),vy_mps=float(state[7]),vz_mps=float(state[8]),
           roll_rate_radps=float(state[9]),pitch_rate_radps=float(state[10]),yaw_rate_radps=float(state[11]),
           hydro_buoyancy_N=float(F_h[2]),hull_buoyancy_N=float(by['HULL']),
           port_float_buoyancy_N=float(port),starboard_float_buoyancy_N=float(star),
           hydro_roll_torque_Nm=float(M_h[0]),hydro_pitch_torque_Nm=float(M_h[1]),
           thrust_N=float(thrust),differential_thrust_N=float(dthrust),
           drag_x_N=float(Fd[0]),pitch_moment_thrust_Nm=float(M_t[1]),
           munk_sensitivity_yaw_Nm=float(M_munk),yaw_torque_thrust_Nm=float(M_t[2]),
           net_vertical_accel_mps2=float(acceleration[2]),
           **{'load_'+ss[0]+'_N':float(by.get('BULKHEAD_'+ss[0]+'_N',0)) for ss in ST})
        log.append(rec)
        # abort *after logging* if nonphysical overwhelming energy or instability; no clamping to keep it afloat
        if any(not np.isfinite(v) for v in state) or abs(roll)>math.radians(70) or abs(pitch)>math.radians(60) or abs(state[2])>4:
            outcome['abort']={'time_s':float(t),'reason':'divergence / capsize / excessive trim'}
            break
        if (abs(x)>LAKE['half_extent_xy_m'][0]-5 or abs(y)>LAKE['half_extent_xy_m'][1]-5):
            # Initial prototype does not spawn outside footprint; +X test axis uses narrow side 56m.
            outcome['abort']={'time_s':float(t),'reason':'lake footprint safety margin'}
            break
    outcome['summary']={'duration_s':log[-1]['time_s'],'distance_along_lake_m':log[-1]['y_m'],
      'maximum_speed_mps':max(math.hypot(r['vx_mps'],r['vy_mps']) for r in log),
      'maximum_abs_roll_deg':max(abs(r['roll_deg']) for r in log),
      'maximum_abs_pitch_deg':max(abs(r['pitch_deg']) for r in log),
      'maximum_abs_yaw_deg':max(abs(r['yaw_deg']) for r in log),
      'max_munk_abs_Nm':max(abs(r['munk_sensitivity_yaw_Nm']) for r in log),
      'max_hydro_pitch_torque_Nm':max(abs(r['hydro_pitch_torque_Nm']) for r in log),
      'max_float_buoyancy_N':max(r['port_float_buoyancy_N']+r['starboard_float_buoyancy_N'] for r in log),
      'min_hull_buoyancy_N':min(r['hull_buoyancy_N'] for r in log)}
    return outcome,log

def write_csv(path,rows):
    if not rows:return
    with open(path,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

if __name__=='__main__':
    out=Path(__file__).resolve().parent
    main,log=run_case('F03 nominal',mass=900,cg=(.45,0,.59),with_floats=True)
    cases=[]
    for mass in (750,900,1050):
        for zcg in (.42,.59,.74):
            res,_=run_case('mass'+str(mass)+'_cgz'+str(zcg),mass=mass,cg=(.45,0,zcg),dynamic=False)
            cases.append({'mass_kg':mass,'cg_z_m':zcg,'eq_z_m':res['eq']['z0_m'],
              'eq_pitch_deg':res['eq']['pitch_deg'],'Kroll_Nm_rad':res['static_roll']['Kroll_Nm_per_rad'],
              'Kpitch_Nm_rad':res['static_Kpitch_Nm_per_rad']})
    nofloat,_=run_case('no outboard floats',mass=900,cg=(.45,0,.59),with_floats=False,dynamic=False)
    outcome={'run':'RC01_F03_calmwater_20261111','location':LAKE,'environment':{'g_m_s2':G,'p0_pa':P_ATM,'air_temp_K':T_A,'air_density_kgm3':RHO_A,'freshwater_rho_kgm3':RHO_W,'wind_mps':0.,'waves_m':0.},
             'hull_mesh':{'source':'F01 six station loft; F02 bulkheads remain interior','watertight_closed_surface':True,'mesh_volume_m3':hull_mesh().volume},
             'nominal':main,'sensitivity_mass_CG':cases,'without_outboard_floats':nofloat,
             'scope':'Independent reduced-order numerical test, not executed by live VTX MuJoCo runtime; no FEA/contact or viscous CFD',
             'limits':['No planing pressure force law','No slam, spray or free-surface CFD','Not a joint deformation simulation','Unknown fuel tank/engine mass properties','Not a measured thruster map','No actual bathymetry in current VTX lake']}
    write_csv(out/'RC01_F03_nominal_timeseries.csv',log)
    write_csv(out/'RC01_F03_mass_cg_sensitivity.csv',cases)
    with open(out/'RC01_F03_results.json','w') as f:json.dump(outcome,f,indent=2)
    hull_mesh().export(out/'RC01_F03_closed_hull_reference.glb')
    np.savez_compressed(out/'RC01_F03_cad_stations.npz',xs=np.array([s[1] for s in ST]),rings=np.stack(RING))
    print(json.dumps({'watertight_hull_m3':hull_mesh().volume,'eq':main['eq'],
      'static_roll':main['static_roll'],'static_Kpitch':main['static_Kpitch_Nm_per_rad'],
      'nominal_summary':main.get('summary'),'no_floats_Kroll':nofloat['static_roll']['Kroll_Nm_per_rad'],
      'sensitivity':cases},indent=2))
