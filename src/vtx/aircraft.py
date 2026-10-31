"""Mass-bearing P0-V4 experimental multibody plant; no flight controller.

MuJoCo integrates the free airframe, two-axis nacelles, spinning rotors/shafts,
occupied cabin gimbal and six sliding gear bodies. Motor/constraint reactions
are internal. Aerodynamic loads and ground/obstacle contact are external.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import mujoco as mj
import numpy as np
from .aero import BladeElementModel, ideal_hover
from .world import TestWorld

ROOT=Path(__file__).resolve().parents[2]
LEDGER_PATH=ROOT/'evidence/source/airframe_ledger.json'
DT=.0025
G=9.80665


def fmt(v):return ' '.join(f'{float(x):.12g}' for x in np.asarray(v).ravel())


def inertial(parent,info,pivot):
    j=np.array(info['inertia_centroid_kg_m2'])
    ET.SubElement(parent,'inertial',mass=str(info['mass_kg']),
                  pos=fmt(np.array(info['centroid_m'])-pivot),
                  fullinertia=fmt([j[0,0],j[1,1],j[2,2],j[0,1],j[0,2],j[1,2]]))


def build_model(ledger,world,gear_variant='baseline',fuel_kg=60.,rpm=800.):
    xml=ET.Element('mujoco',model='VTX-P0-V4A-experimental')
    ET.SubElement(xml,'compiler',angle='radian',autolimits='true',inertiafromgeom='false',fusestatic='false')
    ET.SubElement(xml,'option',timestep=str(DT),gravity=f'0 0 {-G}',integrator='implicitfast',
                  solver='Newton',iterations='50',tolerance='1e-10',cone='elliptic',jacobian='dense')
    size=ET.SubElement(xml,'size',njmax='4000',nconmax='2000')
    default=ET.SubElement(xml,'default')
    ET.SubElement(default,'geom',friction='.75 .005 .0001',condim='4',solref='.008 1',solimp='.98 .999 .001',density='0',margin='.001')
    ET.SubElement(default,'joint',damping='0',armature='0')
    asset=ET.SubElement(xml,'asset')
    ET.SubElement(asset,'hfield',name='terrain',nrow=str(world.n),ncol=str(world.n),size=f'{world.half} {world.half} 70 2')
    wb=ET.SubElement(xml,'worldbody')
    ET.SubElement(wb,'geom',name='terrain',type='hfield',hfield='terrain',contype='1',conaffinity='2')
    for o in world.obstacles:
        args=dict(name=o['id'],type=o['kind'],pos=fmt(o['center']),contype='1',conaffinity='2')
        args['size']=fmt(o['half']) if o['kind']=='box' else fmt([o['half'][0],o['half'][2]])
        ET.SubElement(wb,'geom',**args)
    air=ET.SubElement(wb,'body',name='airframe',pos='0 0 0')
    ET.SubElement(air,'freejoint',name='free')
    inertial(air,ledger['bodies']['airframe'],np.zeros(3))
    bodies={'airframe':air};pivots={k:np.array(v['pivot_m']) for k,v in ledger['bodies'].items()}
    for name,info in ledger['bodies'].items():
        if name=='airframe':continue
        parent=air;relative=pivots[name]
        if name.startswith('rotor'):
            parent=bodies['nacelle'+name[-1]];relative=pivots[name]-pivots['nacelle'+name[-1]]
        b=ET.SubElement(parent,'body',name=name,pos=fmt(relative))
        bodies[name]=b
        inertial(b,info,pivots[name])
        if name.startswith('nacelle') or name=='cabin':
            # Two serial hinge coordinates at the measured common pivot.
            # No massive outer bearing ring is invented where the source rig is empty.
            limit=math.radians(20 if name!='cabin' else 15)
            for axis in 'xy':
                ET.SubElement(b,'joint',name=name+'_'+axis,type='hinge',axis='1 0 0' if axis=='x' else '0 1 0',range=fmt([-limit,limit]))
        elif name.startswith('rotor'):
            ET.SubElement(b,'joint',name=name+'_spin',type='hinge',axis='0 0 1',limited='false')
        elif name.startswith('shaft'):
            a=np.array(info['centroid_m']);a[2]=0;a/=np.linalg.norm(a)
            ET.SubElement(b,'joint',name=name+'_spin',type='hinge',axis=fmt(a),limited='false')
        elif name.startswith('gear'):
            effective_mass=(ledger['empty']['mass_kg']+170+fuel_kg)/6
            stiffness=effective_mass*G/(.25/4)
            ratio=.55 if gear_variant=='baseline' else 1.
            damping=2*ratio*math.sqrt(stiffness*effective_mass)
            ET.SubElement(b,'joint',name=name+'_stroke',type='slide',axis='0 0 1',range='0 .25',stiffness=str(stiffness),damping=str(damping),springref='0')
    # Explicit crew ballast model tied to the source seat geometry. No human
    # anthropometric measurement is claimed: ellipsoid distribution is provisional.
    for i,x in enumerate([-.3,.3]):
        b=ET.SubElement(bodies['cabin'],'body',name=f'occupant{i+1}',pos=fmt(np.array([x,.02,1.445])-pivots['cabin']))
        radii=np.array([.2,.16,.45]);j=85/5*(np.sum(radii*radii)-radii*radii)
        ET.SubElement(b,'inertial',mass='85',pos='0 0 0',diaginertia=fmt(j))
    for i,t in enumerate(ledger['tanks']):
        pos=np.array(t['centroid_m']);axis=np.array(t['axis']);mass=fuel_kg/4
        r,L=.18,.48
        jp=.5*mass*r*r; jt=mass*(3*r*r+L*L)/12
        tensor=jt*np.eye(3)+(jp-jt)*np.outer(axis,axis)
        info=dict(mass_kg=mass,centroid_m=pos.tolist(),inertia_centroid_kg_m2=tensor.tolist())
        b=ET.SubElement(air,'body',name=f'fuel{i+1}',pos=fmt(pos))
        inertial(b,info,pos)
    # Colliders are traceable, disclosed OBB/capsule/swept-envelope derivatives.
    # Aircraft self-contact is screened separately; assembly interfaces overlap
    # intentionally in concept geometry, so blanket convex self-contact is invalid.
    for i,p in enumerate(ledger['parts']):
        name=p['body'];b=bodies[name];pivot=pivots[name]
        if name in ['cabin'] or name.startswith('rotor'):continue
        if name.startswith('gear') and 'contact foot' not in p['name']:continue
        if 'blade' in p['name'] or 'stator' in p['name']:continue
        lo,hi=np.array(p['bounds_m']);half=np.array(p['obb_half_m'])
        if max(half)<.025:continue
        center=np.array(p['obb_center_m'])-pivot
        rot=np.array(p['obb_rotation']);q=np.zeros(4);mj.mju_mat2Quat(q,rot.ravel())
        args=dict(name=f'part_{i}',contype='2',conaffinity='1',rgba='.35 .4 .45 1')
        # Annular ducts and load rings remain open collision shapes.
        annular=('duct' in p['name'] or 'ring' in p['name'].lower()) and (hi[0]-lo[0]>.5) and abs((hi[0]-lo[0])-(hi[1]-lo[1]))<.15
        if annular:
            radius=((hi[0]-lo[0])+(hi[1]-lo[1]))/4
            thickness=max(.018,min((hi[2]-lo[2])/2,.065))
            radius=max(.1,radius-thickness)
            z=(hi[2]+lo[2])/2
            for seg in range(20):
                a=2*math.pi*seg/20;c=2*math.pi*(seg+1)/20
                pts=np.array([[radius*math.cos(a),radius*math.sin(a),z],[radius*math.cos(c),radius*math.sin(c),z]])
                pts[:,:2]+=(lo[:2]+hi[:2])/2
                pts-=pivot
                ET.SubElement(b,'geom',**{**args,'name':f'part_{i}_{seg}'},type='capsule',fromto=fmt(pts),size=str(thickness))
        else:
            ET.SubElement(b,'geom',**args,type='box',pos=fmt(center),quat=fmt(q),size=fmt(np.maximum(half,.003)))
    ET.SubElement(bodies['cabin'],'geom',name='cabin_shell',type='sphere',pos='0 0 0',size='.95',contype='2',conaffinity='1')
    for i in range(1,5):
        ET.SubElement(bodies[f'rotor{i}'],'geom',name=f'rotor_disk{i}',type='cylinder',size=fmt([ledger['blade']['radius_m'],.044]),contype='2',conaffinity='1',friction='.8 .04 .001')
    tendons=ET.SubElement(xml,'tendon')
    for i in range(1,5):
        pivot=pivots[f'nacelle{i}']
        for index in range(2):
            mount=ledger['mechanism']['nacelle_actuators'][index]
            tip=np.array(mount['tip_m']);base=np.array(mount['root_m'])
            root_site=f'ema{i}_{index}_root';tip_site=f'ema{i}_{index}_tip'
            ET.SubElement(air,'site',name=root_site,pos=fmt(pivot+base),size='.01')
            ET.SubElement(bodies[f'nacelle{i}'],'site',name=tip_site,pos=fmt(tip),size='.01')
            tendon=ET.SubElement(tendons,'spatial',name=f'ema{i}_{index}',width='.01')
            ET.SubElement(tendon,'site',site=root_site);ET.SubElement(tendon,'site',site=tip_site)
    eq=ET.SubElement(xml,'equality')
    senses=[1,-1,1,-1]
    for i in range(2,5):
        ET.SubElement(eq,'joint',name=f'branch{i}',joint1=f'rotor{i}_spin',joint2='rotor1_spin',polycoef=fmt([0,senses[i-1],0,0,0]),solref='.003 1')
    for i in range(1,5):
        ET.SubElement(eq,'joint',name=f'highspeed_branch{i}',joint1=f'shaft{i}_spin',joint2='rotor1_spin',polycoef=fmt([0,6016/rpm*senses[i-1],0,0,0]),solref='.003 1')
    sensor=ET.SubElement(xml,'sensor')
    ET.SubElement(sensor,'subtreeangmom',name='total_H',body='airframe')
    ET.SubElement(sensor,'subtreelinvel',name='total_v',body='airframe')
    ET.SubElement(sensor,'subtreecom',name='total_cg',body='airframe')
    text=ET.tostring(xml,encoding='unicode')
    model=mj.MjModel.from_xml_string(text)
    model.hfield_data[:]=(world.heights/70).ravel()
    return model,text


class Aircraft:
    def __init__(self,world=None,gear_variant='baseline',rpm=800.,fuel_kg=60.):
        self.ledger=json.loads(LEDGER_PATH.read_text())
        self.world=world or TestWorld()
        self.gear_variant=gear_variant;self.reference_rpm=float(rpm)
        self.model,self.xml=build_model(self.ledger,self.world,gear_variant,fuel_kg,rpm)
        self.data=mj.MjData(self.model)
        self.bids={name:mj.mj_name2id(self.model,mj.mjtObj.mjOBJ_BODY,name) for name in self.ledger['bodies']}
        self.jids={mj.mj_id2name(self.model,mj.mjtObj.mjOBJ_JOINT,i):i for i in range(self.model.njnt)}
        self.qadr={n:int(self.model.jnt_qposadr[i]) for n,i in self.jids.items()}
        self.vadr={n:int(self.model.jnt_dofadr[i]) for n,i in self.jids.items()}
        self.aero=BladeElementModel(self.ledger['blade'])
        self.command=dict(engine=0.,collective_deg=[0.]*4,tilt_deg=[[0.,0.] for _ in range(4)],cabin_deg=[0.,0.])
        self.pitch=np.zeros(4);self.target_angles=np.zeros((4,2));self.cabin_target=np.zeros(2)
        self.engine_spool=0.;self.fuel=np.full(4,fuel_kg/4)
        self.fuel_initial=self.fuel.copy();self.fuel_bids=[mj.mj_name2id(self.model,mj.mjtObj.mjOBJ_BODY,f'fuel{i}') for i in range(1,5)]
        self.initial_fuel_inertia=self.model.body_inertia[self.fuel_bids].copy()
        self.wind=np.zeros(3)
        self.rotors=[dict(thrust_n=0.,torque_nm=0.,induced_mps=0.,max_alpha_deg=0.) for _ in range(4)]
        self.integrity=np.ones(4)
        self.power=dict(engine_w=0.,rotor_aero_w=0.,servo_w=0.,gear_loss_w=0.,fuel_chemical_w=0.)
        self.energy=dict(engine_j=0.,rotor_aero_j=0.,gear_loss_j=0.,servo_j=0.,fuel_chemical_j=0.)
        self.events=[];self.flags=set();self.crashed=False;self.max_alt=0.;self.max_impact_n=0.
        self.step_count=0;self.last_mass_update=0.;self.last_collision=None
        self.provenance={
            'revision':self.ledger['revision'],'ledger_sha256':hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest(),
            'physics':'MuJoCo '+mj.__version__,'dt_s':DT,'aero_rate_hz':100,
            'gear_variant':gear_variant,'reference_rpm':rpm,'model_xml_sha256':hashlib.sha256(self.xml.encode()).hexdigest(),
            'status':'CALIBRATION_BLOCKED — conditional engineering experiment',
            'hypotheses':dict(mass_distribution='uniform subsystem surface density',
                polar='2pi slope; CLmax1.2; stall16deg; CD0.012+0.02CL^2',
                nacelle_torque_limit_nm=1100.,nacelle_command_rate_deg_s=20.,
                pitch_rate_deg_s=12.,pitch_lag_s=.15,engine_spool_s=2.,
                engine_continuous_w=469800.,transmission_efficiency=.95,
                overall_ratio=6016/rpm,rotor_spin_senses=[1,-1,1,-1],
                highspeed_shaft_topology='ideal equivalent ratio; CV/tooth compliance unmodeled',
                installed_torque_limit_nm=484700/(6016*2*math.pi/60),
                sfc_kg_kwh=.4,fuel_density_kg_l=.8,body_CdA_m2=1.65,
                gear='linear spring: static compression quarter stroke; damping ratio '+str(.55 if gear_variant=='baseline' else 1.),
                self_contact='CAD clearance audit; no all-part multibody self-contact',
                structural_failure='rigid load paths; no laminate failure allowables or FEA',
                rotor_map='axial BEMT; duct gain=1; no CFD/interference/edgewise qualification')}
        mj.mj_forward(self.model,self.data)

    def spawn(self,x,y,z):
        """Operator mission setup ONLY, never exposed in the pilot action API."""
        mj.mj_resetData(self.model,self.data)
        lowest=min(p['bounds_m'][0][2] for p in self.ledger['parts'] if 'replaceable contact foot' in p['name'])
        self.data.qpos[:3]=[x,y,z-lowest+.01]
        self.data.qpos[3:7]=[1,0,0,0]
        mj.mj_forward(self.model,self.data)

    def set_command(self,cmd):
        self.command={k:cmd[k] for k in self.command}

    def joint(self,name):return self.data.qpos[self.qadr[name]],self.data.qvel[self.vadr[name]]

    def servo(self,name,target,limit=1100.):
        q,v=self.joint(name)
        # Local position servo only: no airframe attitude/altitude feedback.
        # Ten local servos share a provisional 5 kW engine-driven supply. With
        # no running engine there is no invented battery/actuator energy.
        cap=min(limit*self.engine_spool,500*self.engine_spool/max(abs(v),.1))
        torque=float(np.clip(4200*(target-q)-260*v,-cap,cap))
        self.data.qfrc_applied[self.vadr[name]]+=torque
        return abs(torque*v)

    def refresh_aero(self):
        for i in range(4):
            bid=self.bids[f'rotor{i+1}'];axis=self.data.xmat[bid].reshape(3,3)[:,2]
            velocity=np.zeros(6);mj.mj_objectVelocity(self.model,self.data,mj.mjtObj.mjOBJ_BODY,bid,velocity,0)
            relative=velocity[3:]-self.wind
            axial=float(relative@axis)
            rpm=self.joint(f'rotor{i+1}_spin')[1]
            value=self.aero.evaluate(rpm,self.pitch[i],axial)
            if np.linalg.norm(relative-axis*axial)>5:self.flags.add('EDGEWISE_FLOW_UNCALIBRATED')
            if axial<-.5*max(value['induced_mps'],1):self.flags.add('DESCENDING_WAKE_UNCALIBRATED')
            self.rotors[i]={k:v*self.integrity[i] if k in ['thrust_n','torque_nm'] else v for k,v in value.items()}

    def linear_actuator(self,i,index,angles):
        """Local EMA position servo applies equal/opposite forces at real anchors.

        Spatial-tendon Jacobians distribute the physical force through both
        bodies. These are not direct body torques or a flight attitude loop.
        """
        ax,ay=angles
        rx=np.array([[1,0,0],[0,math.cos(ax),-math.sin(ax)],[0,math.sin(ax),math.cos(ax)]])
        ry=np.array([[math.cos(ay),0,math.sin(ay)],[0,1,0],[-math.sin(ay),0,math.cos(ay)]])
        mount=self.ledger['mechanism']['nacelle_actuators'][index]
        tip=np.array(mount['tip_m']);base=np.array(mount['root_m'])
        wanted=np.linalg.norm(rx@ry@tip-base)
        tid=mj.mj_name2id(self.model,mj.mjtObj.mjOBJ_TENDON,f'ema{i}_{index}')
        speed=self.data.ten_velocity[tid]
        cap=min(4622*self.engine_spool,500*self.engine_spool/max(abs(speed),.01))
        force=float(np.clip(67200*(wanted-self.data.ten_length[tid])-4160*speed,-cap,cap))
        # MuJoCo 3.17 stores tendon Jacobians in CSR even when the constraint
        # solver uses dense Jacobians; structure belongs to the model.
        start=int(self.model.ten_J_rowadr[tid]);count=int(self.model.ten_J_rownnz[tid])
        cols=self.model.ten_J_colind[start:start+count]
        self.data.qfrc_applied[cols]+=self.data.ten_J[start:start+count]*force
        return abs(force*speed)

    def step(self):
        m,d=self.model,self.data
        d.qfrc_applied[:]=0.;d.xfrc_applied[:]=0.
        self.engine_spool+=np.clip(self.command['engine']-self.engine_spool,-DT/2,DT/2)
        self.pitch+=np.clip((np.array(self.command['collective_deg'])-self.pitch)*DT/.15,-12*DT,12*DT)
        requested=np.radians(self.command['tilt_deg'])
        self.target_angles+=np.clip(requested-self.target_angles,-math.radians(20)*DT,math.radians(20)*DT)
        self.cabin_target+=np.clip(np.radians(self.command['cabin_deg'])-self.cabin_target,-math.radians(12)*DT,math.radians(12)*DT)
        servo_power=0.
        for i in range(4):
            for index in range(2):servo_power+=self.linear_actuator(i+1,index,self.target_angles[i])
        for j,a in enumerate('xy'):servo_power+=self.servo(f'cabin_{a}',self.cabin_target[j],600.)
        if self.step_count%4==0:self.refresh_aero()
        aero_power=0.
        for i in range(4):
            bid=self.bids[f'rotor{i+1}'];axis=d.xmat[bid].reshape(3,3)[:,2]
            omega=self.joint(f'rotor{i+1}_spin')[1]
            spin_sign=1 if omega>=0 else -1
            r=self.rotors[i]
            d.xfrc_applied[bid,:3]+=r['thrust_n']*axis
            d.xfrc_applied[bid,3:]+=-spin_sign*r['torque_nm']*axis
            aero_power+=r['torque_nm']*abs(omega)
        # Airframe drag is external atmospheric force, no synthetic rate damping.
        vel=np.zeros(6);mj.mj_objectVelocity(m,d,mj.mjtObj.mjOBJ_BODY,self.bids['airframe'],vel,0)
        v=vel[3:]-self.wind
        d.xfrc_applied[self.bids['airframe'],:3]+=-.5*1.225*1.65*np.linalg.norm(v)*v
        omega=self.joint('rotor1_spin')[1]
        target=self.engine_spool*self.reference_rpm*2*math.pi/60
        # A mechanical speed governor is disclosed; it cannot command aircraft pose.
        ratio=6016/self.reference_rpm
        torque_cap=484700/(6016*2*math.pi/60)*ratio*.95*self.engine_spool
        power_cap=max(0.,469800*self.engine_spool-servo_power)
        torque_cap=min(torque_cap,power_cap*.95/max(abs(omega),1.))
        torque=float(np.clip(180*(target-omega),0.,torque_cap)) if self.fuel.sum()>.001 else 0.
        # Nonregenerative servo supply is charged to the prime mover too.
        d.qfrc_applied[self.vadr['rotor1_spin']]+=torque
        engine_power=torque*max(omega,0)/.95+servo_power
        burn=engine_power/3.6e6*.4*DT
        if burn>0:self.fuel=np.maximum(self.fuel-burn/4,0.)
        chemical=burn/DT*43e6
        self.power=dict(engine_w=engine_power,rotor_aero_w=aero_power,servo_w=servo_power,
                        gear_loss_w=torque*max(omega,0)*(1/.95-1),fuel_chemical_w=chemical)
        for k,vv in self.power.items():self.energy[k.replace('_w','_j')]+=vv*DT
        mj.mj_step(m,d)
        if d.time-self.last_mass_update>=.1:
            for i,bid in enumerate(self.fuel_bids):
                m.body_mass[bid]=max(float(self.fuel[i]),1e-9)
                m.body_inertia[bid]=self.initial_fuel_inertia[i]*max(self.fuel[i]/self.fuel_initial[i],1e-9)
            # Recalculate model constants using a scratch data object; never reset
            # the live state while fuel changes. Exhaust carries outgoing mass.
            scratch=mj.MjData(m);mj.mj_setConst(m,scratch)
            self.last_mass_update=d.time
        self.step_count+=1
        self.check_contacts()
        altitude=float(d.xpos[self.bids['airframe'],2]-self.world.surface_z(*d.xpos[self.bids['airframe'],:2]))
        self.max_alt=max(self.max_alt,altitude)
        if not np.all(np.isfinite(d.qpos)) or not np.all(np.isfinite(d.qvel)):raise RuntimeError('Nonfinite physical state')

    def check_contacts(self):
        for c in self.data.contact[:self.data.ncon]:
            if c.dist>.002:continue
            g1,g2=int(c.geom1),int(c.geom2)
            b1,b2=int(self.model.geom_bodyid[g1]),int(self.model.geom_bodyid[g2])
            if b1 and b2:continue
            geom=g2 if b1==0 else g1;body=int(self.model.geom_bodyid[geom])
            name=mj.mj_id2name(self.model,mj.mjtObj.mjOBJ_BODY,body)
            force=np.zeros(6)
            idx=next((i for i in range(self.data.ncon) if self.data.contact[i].geom1==g1 and self.data.contact[i].geom2==g2),0)
            mj.mj_contactForce(self.model,self.data,idx,force)
            self.max_impact_n=max(self.max_impact_n,float(np.linalg.norm(force[:3])))
            if name and not name.startswith('gear'):
                if not self.crashed:
                    self.events.append(dict(type='collision',t_s=float(self.data.time),body=name,
                                            force_n=float(np.linalg.norm(force[:3])),position_m=c.pos.tolist()))
                self.crashed=True
                self.last_collision=name
                # Rigid impacts continue; a rotor contact invalidates the intact
                # aero model. No invented material strength threshold is used.
                if name.startswith('rotor'):self.integrity[int(name[-1])-1]=0.

    def mass_properties(self):
        m,d=self.model,self.data
        mass=float(m.body_mass.sum())
        center=np.sum(m.body_mass[:,None]*d.xipos,axis=0)/mass
        inertia=np.zeros((3,3))
        for i in range(1,m.nbody):
            rot=d.ximat[i].reshape(3,3);offset=d.xipos[i]-center
            inertia+=rot@np.diag(m.body_inertia[i])@rot.T+m.body_mass[i]*(np.eye(3)*(offset@offset)-np.outer(offset,offset))
        return dict(mass_kg=mass,cg_world_m=center.tolist(),inertia_world_kg_m2=inertia.tolist())

    def physical_snapshot(self):
        return dict(t_s=float(self.data.time),qpos=self.data.qpos.tolist(),qvel=self.data.qvel.tolist(),
                    body_poses={n:dict(position=self.data.xpos[b].tolist(),quaternion_wxyz=self.data.xquat[b].tolist()) for n,b in self.bids.items()},
                    pitch_deg=self.pitch.tolist(),fuel_kg=self.fuel.tolist(),rotors=self.rotors,
                    integrity=self.integrity.tolist(),power=self.power,energy=self.energy,
                    events=self.events,flags=sorted(self.flags),mass=self.mass_properties(),
                    ncon=int(self.data.ncon),crashed=self.crashed,provenance=self.provenance)
