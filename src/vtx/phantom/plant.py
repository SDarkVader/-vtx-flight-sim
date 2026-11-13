"""Phantom MuJoCo plant: multibody model built from the mass ledger + live physics loop.

Physics 400 Hz (DT shared with the legacy aircraft); FCC, propulsion governors, energy bus and
surface aero at 100 Hz (held between updates); fan thrust, rotor aero torque and ram drag every
physics step from the current shaft speed; fuel mass/inertia update at 10 Hz (mj_setConst).
Motor torques are native MuJoCo joint actuators, so rotor reaction torque and gyroscopic coupling
come from the multibody dynamics. Aero/thrust forces enter through xfrc_applied at their points.
No pose, velocity or force is ever written to the vehicle except through these physical paths.
"""
from __future__ import annotations
import gzip, hashlib, io, json, math
import xml.etree.ElementTree as ET
import mujoco as mj
import numpy as np
from ..aircraft import DT
from .params import Params, ROOT, load_a10b_characteristics
from .ledger import PhantomLedger
from .geometry import PODS, SIDE, FRONT, WING_SIDES, WING_SIGN, PINS
from .propulsion import DuctedFan
from .energy_bus import EnergyBus
from .surface_aero import SurfaceAero
from .controls import FlightControl, default_command

AIRBORNE_DEBOUNCE_S = 0.25   # continuous no-support time before the plant counts itself airborne
POD_DOWN_PRELOAD_FRACTION = 0.8   # share of tilt-servo stall torque used to press a lowered pod onto its down-stop
VEH = dict(contype='2', conaffinity='1', group='3')
WING_STATES = ('stowed', 'hatch_opening', 'sliding_out', 'pinning', 'locked', 'unpinning', 'sliding_in', 'hatch_closing')


def f3(v):
    return ' '.join(f'{float(x):.6g}' for x in np.ravel(v))


def tyre_solref(P, L, mass=None):
    """Tyre N/m and N s/m -> MuJoCo (timeconst, dampratio) for the mass the contact acts on: a corner mass of
    total/4 when the wheel is rigid on its pod, the unsprung wheel mass when the road suspension overlay is on.
    MuJoCo's solref is an acceleration-level (mass-normalised) gain, not a force stiffness, so the
    physical values are converted: omega = sqrt(k/m), zeta = c/(2 sqrt(k m)), tc = 1/(zeta omega)."""
    k = P['contact.tyre_stiffness_n_m']; c = P['contact.tyre_damping_ns_m']
    m = mass if mass is not None else L.mass_properties(None)['mass_kg'] / 4
    w = math.sqrt(k / m); z = max(0.05, c / (2 * math.sqrt(k * m)))
    return f'{max(0.005, 1 / (z * w)):.5f} {z:.4f}'


def suspension_design(P, L, inert):
    """Road suspension overlay: per-corner spring, damper and preload from the ledger's static corner loads.
    Slide joint q (m, + = wheel up / bump) along the pod z axis, which is vertical in road stance. The spring is
    preloaded so that q = 0 (the design ride height) carries the static sprung corner load."""
    if P.get('suspension.enabled', 0.0) <= 0.5:
        return None
    mp = L.mass_properties(None); M = mp['mass_kg']; xcg = mp['cg_m'][0]
    g = P['atmosphere.gravity_m_s2']; f = P['suspension.ride_frequency_hz']; zeta = P['suspension.damping_ratio']
    xf = L.bodies['pod_FL_wheel'].anchor[0]; xr = L.bodies['pod_RL_wheel'].anchor[0]
    front = (xcg - xr) / (xf - xr)
    out = {}
    for k in PODS:
        m_u = inert[f'pod_{k}_wheel'][0]
        F = M * g * (front if FRONT[k] else 1 - front) / 2 - m_u * g          # static sprung load at this corner
        ms = F / g; w = 2 * math.pi * f
        kk = ms * w * w; c = 2 * zeta * math.sqrt(kk * ms)
        lift = 0.0   # built level; PhantomAircraft.nose_strut_update extends the strut at run time
        lo, hi = P['suspension.travel_m']
        out[k] = dict(stiffness_n_m=kk, damping_ns_m=c, preload_n=F, springref_m=-F / kk - lift, unsprung_kg=m_u, sprung_kg=ms,
                      travel_m=[lo - lift, hi - lift], ride_offset_m=-lift)
    return out


def steering_design(P):
    """control_effectors overlay: front steer-by-wire. Torque per wheel from the rack actuator force and steering arm
    (shared by two wheels); position loop stiff enough to reach full torque at 3 deg error."""
    if P.get('effectors.enabled', 0.0) <= 0.5:
        return None
    T = P['effectors.steering.rack_force_n'] * P['effectors.steering.steering_arm_m'] / 2
    kp = T / math.radians(3.0)
    return dict(max_deg=P['effectors.steering.max_deg'], torque_max_nm=T, kp_nm_rad=kp, kv_nms_rad=2 * math.sqrt(kp * 1.5))


def build_xml(L: PhantomLedger, world):
    P = L.p
    x = ET.Element('mujoco', model=f'VTX-PHANTOM-{P.variant}')
    ET.SubElement(x, 'compiler', angle='radian', autolimits='true', inertiafromgeom='false', fusestatic='false')
    opt = ET.SubElement(x, 'option', timestep=str(DT), gravity=f'0 0 {-P["atmosphere.gravity_m_s2"]}', integrator='implicitfast',
                        solver='Newton', iterations='50', tolerance='1e-10', cone='elliptic', jacobian='dense')
    ET.SubElement(opt, 'flag', energy='enable')
    ET.SubElement(x, 'size', njmax='4000', nconmax='2000')
    d = ET.SubElement(x, 'default')
    ET.SubElement(d, 'geom', friction='.75 .005 .0001', condim='4', solref='.008 1', solimp='.98 .999 .001', density='0', margin='.001')
    asset = ET.SubElement(x, 'asset')
    ET.SubElement(asset, 'hfield', name='terrain', nrow=str(world.n), ncol=str(world.n), size=f'{world.half} {world.half} 70 2')
    pieces = P.geometry['hull']['convex_pieces']
    for i, pc in enumerate(pieces):
        ET.SubElement(asset, 'mesh', name=f'hull_{i}', vertex=f3(pc['vertices']))
    wb = ET.SubElement(x, 'worldbody')
    ET.SubElement(wb, 'geom', name='terrain', type='hfield', hfield='terrain', contype='1', conaffinity='2', group='0')
    if getattr(world, 'environment_key', None) == 'sandbox':
        ET.SubElement(wb, 'geom', name='sandbox_boundary_floor', type='plane', pos='0 0 -0.2', size='0 0 0.1', contype='1', conaffinity='2')
    for o in world.obstacles:
        a = dict(name=o['id'], type=o['kind'], pos=f3(o['center']), contype='1', conaffinity='2', group='0')
        a['size'] = f3(o['half']) if o['kind'] == 'box' else f3([o['half'][0], o['half'][2]])
        ET.SubElement(wb, 'geom', **a)
    inert = L.body_inertials()
    susp = suspension_design(P, L, inert)
    steer = steering_design(P)
    els = {}
    C = P.tree
    for name, b in L.bodies.items():
        parent = wb if b.parent is None else els[b.parent]
        pos = b.anchor if b.parent is None else np.array(b.anchor) - L.bodies[b.parent].anchor
        e = ET.SubElement(parent, 'body', name=name, pos=f3(pos))
        els[name] = e
        m, com, J = inert[name]
        ET.SubElement(e, 'inertial', pos=f3(com), mass=f'{m:.9g}', fullinertia=f3([J[0][0], J[1][1], J[2][2], J[0][1], J[0][2], J[1][2]]))
        if b.parent is None:
            ET.SubElement(e, 'freejoint', name='free')
            for i in range(len(pieces)):
                ET.SubElement(e, 'geom', name=f'hull_{i}', type='mesh', mesh=f'hull_{i}', rgba='.3 .32 .35 1', **VEH)
            ET.SubElement(e, 'site', name='radar', pos=f3(P['sensors.radar_position_m']))
            continue
        if b.joint:
            ja = dict(name=name, type=b.joint, pos='0 0 0', axis=f3(b.axis))
            if b.range is not None:
                ja['range'] = f3(b.range); ja['limited'] = 'true'
            arm = damp = None
            if name.startswith('pod_') and name.count('_') == 1:
                arm = P['pods.tilt_armature_kg_m2']
            elif name.startswith('leg_') and name.endswith('_oleo'):
                k = P['contact.oleo_stiffness_n_m']
                ja.update(stiffness=str(k), springref=str(-P['contact.oleo_preload_n'] / k), damping=str(P['contact.oleo_damping_ns_m']))
            elif name.startswith('leg_'):
                arm = P['contact.leg_armature_kg']
            elif name.startswith('wing_'):
                arm = P['wing_actuators.slide_armature_kg']
            elif name.startswith('pin_'):
                arm = P['wing_actuators.pin_armature_kg']
            elif name.startswith(('flap_', 'aileron_')):
                arm = P['wing_actuators.surface_armature_kg_m2']
            elif name.startswith('canard_'):
                arm = P['wing_actuators.canard_armature_kg_m2']
            elif name.startswith('hatch_'):
                arm = P['wing_actuators.hatch_armature_kg_m2']
            elif name.endswith(('_fan', '_wheel', '_rotor')):
                damp = 0.002
            if arm:
                ja['armature'] = str(arm)
            if damp:
                ja['damping'] = str(damp)
            if steer and name.endswith('_wheel') and FRONT[name.split('_')[1]]:
                # control_effectors overlay: steer-by-wire about the pod z axis (vertical in road stance), first in the chain
                ET.SubElement(e, 'joint', name=f'{name[:-6]}_steer', type='hinge', pos='0 0 0', axis='0 0 1', limited='true',
                              range=f3([-math.radians(steer['max_deg']), math.radians(steer['max_deg'])]), armature='0.05', damping='5')
            if susp and name.endswith('_wheel'):
                # road suspension overlay: slide (pod z axis, + = bump) before the wheel spin hinge in the same body
                s = susp[name.split('_')[1]]
                ET.SubElement(e, 'joint', name=f'{name[:-6]}_susp', type='slide', pos='0 0 0', axis='0 0 1', limited='true',
                              range=f3(s['travel_m']), stiffness=f'{s["stiffness_n_m"]:.6g}', springref=f'{s["springref_m"]:.6g}',
                              damping=f'{s["damping_ns_m"]:.6g}')
            ET.SubElement(e, 'joint', **ja)
        if name.endswith('_wheel'):
            k = name.split('_')[1]
            ET.SubElement(e, 'geom', name=f'tyre_{k}', type='cylinder', size=f3([P['pods.tyre_radius_m'], P['pods.tyre_half_width_m']]),
                          zaxis=f3([0, SIDE[k], 0]), solref=tyre_solref(P, L, susp[k]['unsprung_kg'] if susp else None),
                          friction=f'{P["contact.tyre_friction"]} .01 .001', rgba='.08 .08 .08 1', **VEH)
        elif name.endswith('_oleo'):
            k = name.split('_')[1]
            fz = P['contact.foot_bottom_retracted_z_m'] + P['contact.foot_radius_m'] - b.anchor[2]
            ET.SubElement(e, 'geom', name=f'foot_{k}', type='sphere', size=str(P['contact.foot_radius_m']), pos=f'0 0 {fz:.6g}',
                          friction=f'{P["contact.foot_friction"]} .01 .001', rgba='.6 .6 .6 1', **VEH)
        elif name.startswith('wing_'):
            com = inert[name][1]
            ET.SubElement(e, 'geom', name=f'geom_{name}', type='box', pos=f3(com), size='0.35 0.6 0.03', rgba='.2 .22 .25 1', **VEH)
        elif name.startswith('canard_') and not name.endswith('_fold'):
            ET.SubElement(e, 'geom', name=f'geom_{name}', type='box', pos=f3(inert[name][1]), size='0.2 0.28 0.02', rgba='.2 .22 .25 1', **VEH)
    act = ET.SubElement(x, 'actuator')

    def pos_act(j, kp, kv, frc):
        ET.SubElement(act, 'position', name=f'act_{j}', joint=j, kp=str(kp), kv=str(kv), forcerange=f'{-frc} {frc}', forcelimited='true')
    for k in PODS:
        pos_act(f'pod_{k}', P['pods.tilt_kp_nm_rad'], P['pods.tilt_kv_nms_rad'], P['pods.tilt_stall_torque_nm'])
        if steer and FRONT[k]:
            pos_act(f'pod_{k}_steer', steer['kp_nm_rad'], steer['kv_nms_rad'], steer['torque_max_nm'])
        ET.SubElement(act, 'motor', name=f'act_pod_{k}_fan', joint=f'pod_{k}_fan', ctrlrange=f'{-P["pods.motor_torque_peak_nm"]} {P["pods.motor_torque_peak_nm"]}')
        ET.SubElement(act, 'motor', name=f'act_pod_{k}_wheel', joint=f'pod_{k}_wheel', ctrlrange=f'{-P["pods.hub_motor_torque_nm"]} {P["pods.hub_motor_torque_nm"]}')
        pos_act(f'leg_{k}', P['contact.leg_kp_n_m'], P['contact.leg_kv_ns_m'], P['contact.leg_force_max_n'])
    hl = P.handover['control_limits']
    for s in WING_SIDES:
        pos_act(f'wing_{s}', P['wing_actuators.slide_kp_n_m'], P['wing_actuators.slide_kv_ns_m'], hl['wing_slide']['stall_force_N'])
        for pin in PINS:
            pos_act(f'pin_{s}_{pin.lower()}', P['wing_actuators.pin_kp_n_m'], P['wing_actuators.pin_kv_ns_m'], P['wing_actuators.pin_force_n'])
        pos_act(f'flap_{s}', P['wing_actuators.surface_kp_nm_rad'], P['wing_actuators.surface_kv_nms_rad'], hl['flap']['stall_torque_Nm'])
        pos_act(f'aileron_{s}', P['wing_actuators.surface_kp_nm_rad'], P['wing_actuators.surface_kv_nms_rad'], hl['aileron']['stall_torque_Nm'])
        pos_act(f'canard_{s}_fold', P['wing_actuators.fold_kp_nm_rad'], P['wing_actuators.fold_kv_nms_rad'], P['wing_actuators.fold_stall_torque_nm'])
        pos_act(f'canard_{s}', P['wing_actuators.canard_kp_nm_rad'], P['wing_actuators.canard_kv_nms_rad'], hl['canard_pitch']['stall_torque_Nm'])
        pos_act(f'hatch_{s}', P['wing_actuators.hatch_kp_nm_rad'], P['wing_actuators.hatch_kv_nms_rad'], P['wing_actuators.hatch_stall_torque_nm'])
        ET.SubElement(act, 'motor', name=f'act_booster_{s}_rotor', joint=f'booster_{s}_rotor', ctrlrange=f'{-P["boosters.torque_max_nm"]} {P["boosters.torque_max_nm"]}')
    eq = ET.SubElement(x, 'equality')
    for s in WING_SIDES:
        ET.SubElement(eq, 'joint', name=f'lock_{s}', joint1=f'wing_{s}', polycoef='0 0 0 0 0', active='false', solref='.004 1')
    return ET.tostring(x, encoding='unicode')


def turbine_boosters(P):
    """P7: turbine engines replacing the EDF boosters (datasheet thrust, SFC and mass; momentum lapse; first-order spool).
    Returns None when the proposal is off. Thrust is per booster station (engines split equally between the two)."""
    opt = int(round(P['proposals.p7_booster_engine']))
    if opt == 0:
        return None
    k = {1: 'tj150', 2: 'fj33'}[opt]
    count = P['proposals.p7_tj150_count'] if opt == 1 else 1
    return dict(kind=k, count=count, t0_station_n=count / 2 * P[f'proposals.p7_{k}_thrust_n'], sfc_kg_per_n_s=P[f'proposals.p7_{k}_sfc_kg_per_n_h'] / 3600,
                tau_s=P[f'proposals.p7_{k}_t90_s'] / math.log(10), vj_m_s=P[f'proposals.p7_{k}_jet_velocity_m_s'],
                idle=P['proposals.p7_idle_thrust_fraction'], mass_station_kg=count / 2 * P[f'proposals.p7_{k}_mass_kg'] * P['proposals.p7_installation_mass_factor'])


class PhantomAircraft:
    is_phantom = True

    def __init__(self, world, variant='phantom', fuel_kg=None, occupants=None, start_configuration='vtol', engines_running=True,
                 buffer_soc=None, wind=None, overrides=None, load_state=None):
        self.world = world
        P = self.P = Params(variant, overrides)
        if load_state:
            spec = P.tree['load_states'][load_state]
            occupants = spec['occupants'] if occupants is None else occupants
            fuel_kg = spec['fuel_kg'] if spec['fuel_kg'] is not None and fuel_kg is None else fuel_kg
        self.load_state = load_state
        self.L = PhantomLedger(P, occupants)
        self.variant = self.airframe_variant = variant
        self.xml = build_xml(self.L, world)
        self.suspension = suspension_design(self.P, self.L, self.L.body_inertials())
        self.model = mj.MjModel.from_xml_string(self.xml)
        self.model.hfield_data[:] = (world.heights / 70).ravel()
        self.data = mj.MjData(self.model)
        m = self.model
        self.bids = {m.body(i).name: i for i in range(m.nbody)}
        self.jid = {m.joint(i).name: i for i in range(m.njnt)}
        self.aid = {m.actuator(i).name: i for i in range(m.nu)}
        self.eqid = {m.eq(i).name: i for i in range(m.neq)}
        self.gid = {m.geom(i).name: i for i in range(m.ngeom)}
        self.fan = DuctedFan.pod(P); self.booster = DuctedFan.booster(P)
        self.bus = EnergyBus(P, self.L)
        if buffer_soc is not None:
            self.bus.soc = float(buffer_soc)
        self.aero = SurfaceAero(P)
        self.fcc = FlightControl(P, self.fan, 0)
        self.fcc.cmd = default_command(start_configuration)
        if not engines_running:
            self.fcc.cmd['engine'] = 0.0
        cap = P['fuel.tank_capacity_kg']
        f = 2 * cap if fuel_kg is None else min(float(fuel_kg), 2 * cap)
        self.fuel = np.array([f / 2, f / 2]); self.fuel_initial = self.fuel.copy()
        self.fuel_bids = [self.bids['fuel_left'], self.bids['fuel_right']]
        self.fuel_inertia0 = [m.body_inertia[b].copy() / max(m.body_mass[b], 1e-9) for b in self.fuel_bids]
        self.wind = np.array(wind if wind is not None else P['atmosphere.wind_world_m_s'], float)
        self.start_configuration = start_configuration
        self.targets = {}; self.wing_state = {s: 'stowed' for s in WING_SIDES}; self.wing_timer = {s: 0.0 for s in WING_SIDES}
        self.faults = []; self.events = []; self.flags = set(); self.crashed = False; self.max_alt = 0.0; self.max_impact_n = 0.0
        self.step_count = 0; self.last_mass_update = 0.0
        self.fan_omega_cmd = [0.0] * 4; self.fan_state = [{} for _ in PODS]; self.booster_state = [{}, {}]
        self.motor_torque = np.zeros(4); self.booster_torque = np.zeros(2); self.prop_scale = 1.0
        self.aero_out = dict(force_body=np.zeros(3), moment_body=np.zeros(3), surfaces=[], hinge_moments={})
        self.alloc = {}; self.contacts = {}; self.airborne = False; self.first_contact_sink = None
        # P6: DRS stabilator actuator state (trailing edge up, rad); P7: turbine boosters (spool fraction per station)
        self.p6 = P['proposals.p6_drs_stabilator'] > 0.5
        self.stab_te_up = math.radians(P['proposals.p6_stab_rest_te_up_deg']) if self.p6 else 0.0
        self.jet = turbine_boosters(P)
        self.nose_lift = 0.0; self.nose_lift_max = float(P.get('suspension.nose_lift_m', 0.0))   # take-off stance strut extension (m)
        self.eff = P.get('effectors.enabled', 0.0) > 0.5          # control_effectors overlay: rudders, booster TVC, steering
        self.rudder = 0.0; self.tvc = [0.0, 0.0]                   # rad: rudder (+ = side force +y); TVC pitch (+ = thrust up), yaw (+ = thrust +y)
        self.jet_spool = [0.0, 0.0]
        self.no_support_since = None; self.support_force_n = 0.0
        self.ring = np.zeros((int(20 / DT), 32)); self.ring_i = 0; self.ring_full = False
        self.step_log = None; self.rng = np.random.default_rng(41031)
        self.peak_time_used = [0.0] * 4
        self.physics_data = load_a10b_characteristics() if variant == 'phantom-a10b' else None
        self.provenance = dict(revision=f'{variant}' if variant.endswith('-a9') or 'a10' in variant else f'{variant}-a10', airframe_variant=variant, render_asset=('/assets/phantom-a10b-visual.glb' if variant in ('phantom-a10b', 'phantom-a10c') else ('/assets/phantom-a10-blendstra-81c823e2.glb' if P.cassette_revision == 'A10' else f'/assets/phantom-{P.cassette_revision.lower()}.glb')),
                               model_xml_sha256=hashlib.sha256(self.xml.encode()).hexdigest(), parameter_file_sha256=P.file_sha256,
                               config_sha256=P.config_sha256, wing_cassette_revision=P.tree['geometry_sources']['wing_cassette_revision'],
                               physics_characteristics_uri='/evidence/phantom/a10b_characteristics.json' if variant == 'phantom-a10b' else None,
                               physics_model_doc_uri='/docs/phantom/PHANTOM_A10B_MODEL.md' if variant == 'phantom-a10b' else None,
                               ledger_mass_kg=self.mass_properties()['mass_kg'] if False else None)
        self.engine_power_limit_w = P['generators.count'] * P['generators.power_each_w']
        self.reference_rpm = None; self.gear_variant = 'phantom-legs-oleo'
        self.set_configuration(start_configuration)
        self.apply_fuel_mass(force=True)
        mj.mj_forward(m, self.data)
        self.provenance['ledger_mass_kg'] = float(sum(m.body_mass))

    # ------------------------------------------------------------ setup
    def joint(self, name):
        j = self.jid[name]
        return self.data.qpos[self.model.jnt_qposadr[j]], self.data.qvel[self.model.jnt_dofadr[j]]

    def set_q(self, name, v):
        self.data.qpos[self.model.jnt_qposadr[self.jid[name]]] = v

    def set_configuration(self, start):
        q = self.L.configuration(pods='vtol' if start == 'vtol' else 'road', legs='extended' if start == 'vtol' else 'retracted')
        for n, v in q.items():
            if n in self.jid:
                self.set_q(n, v)
        for k in PODS:
            self.set_q(f'leg_{k}_oleo', 0.0)
            if f'pod_{k}_susp' in self.jid:
                self.set_q(f'pod_{k}_susp', 0.0)
        # Preserve the road-start canard position.
        if start == 'road':
            for side in WING_SIDES:
                self.set_q(f'canard_{side}_fold', WING_SIGN[side] * math.pi / 2)
        self.targets = {n: float(self.joint(n)[0]) for n in self.jid if n != 'free' and not n.endswith(('_fan', '_wheel', '_rotor', '_oleo', '_susp'))}
        for n, a in self.aid.items():
            if n[4:] in self.targets:
                self.data.ctrl[a] = self.targets[n[4:]]

    def spawn(self, x, y, z):
        """Place the vehicle with its lowest support (feet in VTOL, tyres on road) 5 mm above surface z."""
        mj.mj_forward(self.model, self.data)
        lows = []
        for n, g in self.gid.items():
            if n.startswith(('foot_', 'tyre_')):
                gp = self.data.geom_xpos[g]
                if n.startswith('foot_'):
                    lows.append(gp[2] - self.model.geom_size[g][0])
                else:
                    ax = self.data.geom_xmat[g].reshape(3, 3)[:, 2]
                    lows.append(gp[2] - self.model.geom_size[g][0] * math.sqrt(max(0, 1 - ax[2] ** 2)) - self.model.geom_size[g][1] * abs(ax[2]))
        low = min(lows) - self.data.qpos[2]
        self.data.qpos[:3] = [x, y, z - low + 0.005]
        self.data.qpos[3:7] = [1, 0, 0, 0]
        self.data.qvel[:] = 0
        mj.mj_forward(self.model, self.data)
        self.spawn_z = float(self.data.qpos[2])
        rp = self.data.site_xpos[self.model.site('radar').id]
        h = self.ray_height(rp, np.array([0, 0, -1.0]))
        # Radar antenna height above the surface with the feet 5 mm clear; the static gear sink
        # changes it by a few cm (flight campaign D-18: the offset was unlabelled).
        self.radar_ground_reference_m = None if h is None else round(h - 0.005, 3)

    def apply_fuel_mass(self, force=False):
        m = self.model
        if not force and self.data.time - self.last_mass_update < 0.1:
            return
        for i, b in enumerate(self.fuel_bids):
            mm = max(float(self.fuel[i]), 1e-6)
            m.body_mass[b] = mm; m.body_inertia[b] = self.fuel_inertia0[i] * mm
        if not hasattr(self, "_scratch"):
            self._scratch = mj.MjData(m)
        mj.mj_setConst(m, self._scratch)
        self.last_mass_update = float(self.data.time)

    # ------------------------------------------------------------ state
    def R(self):
        return self.data.xmat[self.bids['airframe']].reshape(3, 3)

    def attitude(self):
        R = self.R()
        return dict(roll=math.atan2(R[2, 1], R[2, 2]), pitch_up=math.asin(max(-1, min(1, R[2, 0]))), yaw_left=math.atan2(R[1, 0], R[0, 0]))

    def rates_body(self):
        return self.data.qvel[3:6].copy()   # free joint angular velocity is in the body frame

    def vel_body(self):
        return self.R().T @ self.data.qvel[:3]

    def mass_properties(self):
        m, d = self.model, self.data
        b = self.bids['airframe']
        mass = float(m.body_subtreemass[b]); cg_w = d.subtree_com[b].copy()
        J = np.zeros((3, 3))
        for i in range(1, m.nbody):
            R = d.ximat[i].reshape(3, 3); I = R @ np.diag(m.body_inertia[i]) @ R.T
            r = d.xipos[i] - cg_w
            J += I + m.body_mass[i] * (r @ r * np.eye(3) - np.outer(r, r))
        Rb = self.R()
        return dict(mass_kg=mass, cg_world_m=cg_w.tolist(), cg_body_m=(Rb.T @ (cg_w - d.xpos[b])).tolist(), inertia_body_kg_m2=(Rb.T @ J @ Rb).tolist())

    def pod_axis(self, k):
        return self.data.xmat[self.bids[f'pod_{k}']].reshape(3, 3) @ np.array([0, SIDE[k], 0])

    def ray_height(self, p, direction):
        gid = np.zeros(1, np.int32)
        dist = mj.mj_ray(self.model, self.data, p, direction, np.array([1, 0, 0, 0, 0, 0], np.uint8), 1, -1, gid)
        return None if dist < 0 else float(dist)

    # ------------------------------------------------------------ commands
    def set_command(self, action):
        self.fcc.apply(action, float(self.data.time))
        for e in self.fcc.pti.log[-2:]:
            if e not in self.events:
                self.events.append(e)

    @property
    def command(self):
        return self.fcc.cmd

    def lease_failsafe(self):
        self.fcc.lease_failsafe()
        self.events.append(dict(event='command_lease_abort', t_s=float(self.data.time),
                                behaviour='collective 0, boosters 0, wheel drive 0, brakes on; all other targets held; no rescue'))

    def ramp(self, name, target, rate, dt):
        cur = self.targets[name]
        self.targets[name] = cur + max(-rate * dt, min(rate * dt, target - cur))

    # ------------------------------------------------------------ wing sequencer
    def deploy_window_ok(self, qdyn, hl):
        """Deployment guard (control_effectors overlay): predicted dynamic pressure at lock, from the current speed and
        acceleration over the remaining sequence time (hatch + slide + pins), within the transit limit."""
        ws = hl['wing_slide']; v = math.sqrt(max(0.0, 2 * qdyn / self.P['atmosphere.density_kg_m3']))
        T = 180.0 / hl['hatch']['rate_deg_s'] + ws['stroke_m'] / ws['max_speed_m_s'] + hl['locks']['engage_time_s']
        v_lock = v + max(0.0, getattr(self, 'accel_est', 0.0)) * T
        return 0.5 * self.P['atmosphere.density_kg_m3'] * v_lock * v_lock <= ws['transit_q_limit_Pa']

    def wing_sequencer(self, dt, qdyn):
        cmd = self.fcc.cmd['wing']; P = self.P; hl = P.handover['control_limits']
        guard = self.eff
        v = math.sqrt(2 * qdyn / P['atmosphere.density_kg_m3'])           # filtered along-track acceleration estimate
        if getattr(self, 'v_prev', None) is not None and dt > 0:
            self.accel_est = 0.9 * getattr(self, 'accel_est', 0.0) + 0.1 * (v - self.v_prev) / dt
        self.v_prev = v
        for s in WING_SIDES:
            st = self.wing_state[s]; slide = self.joint(f'wing_{s}')[0]; hatch = self.joint(f'hatch_{s}')[0]
            pins = [self.joint(f'pin_{s}_{p.lower()}')[0] for p in PINS]
            self.wing_timer[s] += dt
            new = st
            if cmd == 'deploy' and st in ('stowed', 'hatch_closing', 'sliding_in', 'unpinning'):
                new = 'hatch_opening' if st in ('stowed', 'hatch_closing') else 'sliding_out' if st == 'sliding_in' else 'pinning'
                if guard and new == 'hatch_opening' and not self.deploy_window_ok(qdyn, hl):
                    new = st                                      # guard: lock would be reached above the transit limit
                    if 'deploy_inhibited_q' not in self.flags:
                        self.flags.add('deploy_inhibited_q'); self.events.append(dict(event='wing_deploy_inhibited_q', t_s=float(self.data.time), q_pa=qdyn))
            if guard and st == 'hatch_opening' and qdyn > hl['wing_slide']['transit_q_limit_Pa']:
                new = 'hatch_closing'                             # guard: never leave the hatch open above the transit limit
                self.events.append(dict(event='wing_hatch_closed_by_q', side=s, t_s=float(self.data.time), q_pa=qdyn))
            if guard and st in ('sliding_out', 'pinning') and qdyn > hl['wing_slide']['transit_q_limit_Pa'] and f'transit_q_exceeded_{s}' not in self.flags:
                self.flags.add(f'transit_q_exceeded_{s}'); self.events.append(dict(event='wing_transit_q_exceeded', side=s, t_s=float(self.data.time), q_pa=qdyn))
            elif cmd == 'stow' and st in ('locked', 'pinning', 'sliding_out', 'hatch_opening'):
                new = 'unpinning' if st in ('locked', 'pinning') else 'sliding_in' if st == 'sliding_out' else 'hatch_closing'
            if new == 'hatch_opening' and hatch < 0.05 and max(pins) < -0.065:
                if qdyn <= hl['wing_slide']['transit_q_limit_Pa']:
                    new = 'sliding_out'
                elif 'q_interlock' not in self.flags:
                    self.flags.add('q_interlock'); self.events.append(dict(event='wing_transit_blocked_by_q', t_s=float(self.data.time), q_pa=qdyn))
            elif new == 'sliding_out' and slide > -0.002 and abs(self.joint(f'wing_{s}')[1]) < 0.01:
                new = 'pinning'
            elif new == 'pinning' and min(pins) > -0.003:
                new = 'locked'
            elif new == 'unpinning' and max(pins) < -0.065:
                new = 'sliding_in'
            elif new == 'sliding_in' and slide < -(P.wing_stroke_m - 0.003):
                new = 'hatch_closing'
            elif new == 'hatch_closing' and hatch > math.pi - 0.05:
                new = 'stowed'
            if new != st:
                self.events.append(dict(event='wing_state', side=s, t_s=float(self.data.time), before=st, after=new)); self.wing_timer[s] = 0.0
                st = self.wing_state[s] = new
            if st == 'pinning' and self.wing_timer[s] > 3.0 and f'pin_jam_{s}' not in self.flags:
                self.flags.add(f'pin_jam_{s}'); self.faults.append(dict(fault='pin_jam', side=s, t_s=float(self.data.time)))
            hatch_t = math.pi if st in ('stowed', 'hatch_closing') else 0.0
            pin_t = 0.0 if st in ('pinning', 'locked') else -0.07
            if abs(slide) > 0.003:
                pin_t = min(pin_t, -0.06)    # pins blocked by the mouth flange until the slide is on its stop
            slide_t = 0.0 if st in ('sliding_out', 'pinning', 'locked') else (-P.wing_stroke_m if st in ('sliding_in', 'hatch_closing', 'stowed') else self.targets[f'wing_{s}'])
            self.ramp(f'hatch_{s}', hatch_t, math.radians(hl['hatch']['rate_deg_s']), dt)
            for p in PINS:
                self.ramp(f'pin_{s}_{p.lower()}', pin_t, 0.07 / hl['locks']['engage_time_s'], dt)
            if st in ('sliding_out', 'sliding_in', 'pinning', 'locked', 'hatch_closing', 'stowed'):
                self.ramp(f'wing_{s}', slide_t, hl['wing_slide']['max_speed_m_s'], dt)
            self.data.eq_active[self.eqid[f'lock_{s}']] = 1 if st == 'locked' else 0

    def wing_locked(self, s):
        return self.wing_state[s] == 'locked'

    # ------------------------------------------------------------ 100 Hz update
    def control_update(self, dt):
        P = self.P; d = self.data; c = self.fcc.cmd; g = P['atmosphere.gravity_m_s2']
        att = self.attitude(); w = self.rates_body(); vb = self.vel_body()
        n = self.rng.normal
        sensed = dict(roll=att['roll'] + n(0, 1e-4), pitch_up=att['pitch_up'] + n(0, 1e-4), yaw=att['yaw_left'],
                      p=w[0] + n(0, 3e-4), q_up=-w[1] + n(0, 3e-4), r_left=w[2] + n(0, 3e-4), vz=float(d.qvel[2]) + n(0, 0.005))
        va = vb - self.R().T @ self.wind                     # air data (used by the wing-borne law only)
        sensed.update(qdyn=0.5 * P['atmosphere.density_kg_m3'] * float(va @ va), beta=math.atan2(float(va[1]), max(abs(float(va[0])), 1.0)))
        joint_positions = {name: float(self.joint(name)[0]) for name in self.L.bodies if name in self.jid}
        led = self.L.mass_properties(joint_positions, fuel_kg=list(self.fuel))
        fan_en = {k: abs(self.joint(f'pod_{k}')[0]) >= math.radians(P['pods.fan_enable_tilt_deg']) for k in PODS}
        avail = {k: self.fan.thrust_max * min(1.0, (self.bus.motor_power_limit(i) / P['pods.motor_power_peak_w']) ** (2 / 3)) for i, k in enumerate(PODS)}
        al = self.alloc = self.fcc.update(float(d.time), sensed, float(sum(self.model.body_mass)), led['cg_m'][0], g, fan_en, avail)
        # actuator targets (rate-limited)
        # Pod down-stop preload (ECU logic; no model or parameter change). A pod commanded fully down (0 deg, wheels
        # on the road) is driven slightly past its 0 deg hard stop, so the tilt servo presses it onto the stop
        # instead of only resisting once the pod has already been levered away. Without this, in the nose-up
        # take-off stance tyre side load pushed the rear pods ~7 deg off the stop above ~20 m/s; with the body
        # pitched that camber becomes opposing rear toe, the rear tyres scrub and hop, and the aircraft veers off
        # the runway. The preload is a fixed fraction of the servo's stall torque and is rate-limited like any
        # other tilt command, so the transition to and from a commanded tilt is unchanged.
        preload = POD_DOWN_PRELOAD_FRACTION * P['pods.tilt_stall_torque_nm'] / P['pods.tilt_kp_nm_rad']
        for i, k in enumerate(PODS):
            tilt_cmd = math.radians(al['tilt_deg'][i])
            self.ramp(f'pod_{k}', SIDE[k] * (tilt_cmd if tilt_cmd > 0.0 else -preload), P['pods.tilt_rate_rad_s'], dt)
            self.ramp(f'leg_{k}', -c['leg_extension_m'][i], P['contact.leg_rate_m_s'], dt)
        hl = P.handover['control_limits']
        v_air = float(np.linalg.norm(d.qvel[:3] - self.wind)); qdyn = 0.5 * P['atmosphere.density_kg_m3'] * v_air ** 2
        self.wing_sequencer(dt, qdyn)
        for j, s in enumerate(WING_SIDES):
            locked = self.wing_locked(s)
            flap = c['flap_deg'][j] if locked and v_air <= hl['flap']['max_speed_m_s'] else 0.0
            ail = al['aileron_deg'][j] if locked else 0.0
            self.ramp(f'flap_{s}', math.radians(flap), math.radians(hl['flap']['rate_deg_s']), dt)
            self.ramp(f'aileron_{s}', math.radians(ail), math.radians(hl['aileron']['rate_deg_s']), dt)
            deployed = c['canard_fold'] == 'deployed'
            self.ramp(f'canard_{s}_fold', 0.0 if deployed else WING_SIGN[s] * math.pi / 2, math.radians(hl['canard_fold']['rate_deg_s']), dt)
            can_ok = abs(self.joint(f'canard_{s}_fold')[0]) < math.radians(5)
            self.ramp(f'canard_{s}', math.radians(al['canard_deg'][j]) if can_ok else 0.0,
                      math.radians(P.get('effectors.canard_rate_deg_s', hl['canard_pitch']['rate_deg_s'])), dt)
        if self.p6:
            rest = P['proposals.p6_stab_rest_te_up_deg']; lo, hi = P['proposals.p6_stab_travel_deg']
            dem = float((self.fcc.last or {}).get('moment_demand', [0, 0, 0])[1])
            tgt = rest + float(np.clip(P['proposals.p6_stab_gain_deg_per_demand'] * dem, lo, hi))
            rate = P['proposals.p6_stab_rate_deg_s']
            if np.mean(c['brake']) > 0.3 and self.support_count() > 0 and v_air > 12.0:
                tgt = P['proposals.p6_airbrake_te_up_deg']    # airbrake while braking on the ground
            step = math.radians(rate) * dt
            self.stab_te_up += float(np.clip(math.radians(tgt) - self.stab_te_up, -step, step))
        if self.eff:
            self.effector_update(dt, c, v_air)
        if self.nose_lift_max > 0.0 and 'pod_FL_susp' in self.jid:
            self.nose_strut_update(dt)
        for n_, a in self.aid.items():
            if n_[4:] in self.targets:
                d.ctrl[a] = self.targets[n_[4:]]
        # lift-fan governors -> torque requests
        req = np.zeros(4); shaft = np.zeros(4)
        for i, k in enumerate(PODS):
            spin = P['pods.rotor_spin_sense'][k]; om = spin * self.joint(f'pod_{k}_fan')[1]
            st = self.fan_state[i] or dict(torque_nm=self.fan.k_q * om * om, ground_factor=1.0, advance_ratio=0.0)
            Tc = al['thrust'][i]
            lapse = max(0.2, 1 - st.get('advance_ratio', 0.0) / self.fan.j0) * st.get('ground_factor', 1.0)
            wc = min(self.fan.omega_for_thrust(Tc / lapse), self.fan.omega_max) if Tc > 0 else 0.0
            self.fan_omega_cmd[i] = wc
            tau = st['torque_nm'] + P['pods.rotor_inertia_kg_m2'] * 25.0 * (wc - om)
            plim = self.bus.motor_power_limit(i)
            tau = float(np.clip(tau, -0.3 * self.fan.torque_max_nm, self.fan.torque_max_nm))
            if om > 1 and tau * om > plim:
                tau = plim / om
            if wc == 0 and om < 5:
                tau = 0.0
            req[i] = tau; shaft[i] = tau * om
        breq = np.zeros(2)
        for j, s in enumerate(WING_SIDES):
            om = self.joint(f'booster_{s}_rotor')[1]
            wc = c['booster_throttle'][j] * 0.97 * self.booster.omega_max
            st = self.booster_state[j] or dict(torque_nm=self.booster.k_q * om * om)
            tau = float(np.clip(st['torque_nm'] + P['boosters.rotor_inertia_kg_m2'] * 25 * (wc - om), -0.3 * self.booster.torque_max_nm, self.booster.torque_max_nm))
            if om > 1 and tau * om > P['boosters.shaft_power_max_w']:
                tau = P['boosters.shaft_power_max_w'] / om
            if wc == 0 and om < 5:
                tau = 0.0
            breq[j] = tau
        jet_fuel = 0.0
        if self.jet:
            breq[:] = 0.0                                   # EDF rotors unpowered; turbines draw no electrical power
            a_sp = 1.0 - math.exp(-dt / self.jet['tau_s'])
            for j in range(2):
                thr = c['booster_throttle'][j] if self.fuel.sum() > 0 else 0.0
                tgt = 0.0 if thr <= 0 else max(self.jet['idle'], thr)
                self.jet_spool[j] += (tgt - self.jet_spool[j]) * a_sp
                jet_fuel += self.jet['sfc_kg_per_n_s'] * (self.booster_state[j] or {}).get('thrust_n', 0.0) * dt
        bshaft = np.array([breq[j] * self.joint(f'booster_{s}_rotor')[1] for j, s in enumerate(WING_SIDES)])
        hub = 0.0; wheel_tq = self.wheel_drive_torque(c)
        for i, k in enumerate(PODS):
            hub += abs(wheel_tq[i] * self.joint(f'pod_{k}_wheel')[1]) / 0.9
        eta = self.bus.eta_drive
        prop_e = float(np.sum(np.maximum(shaft, 0)) / eta + np.sum(np.maximum(bshaft, 0)) / P['boosters.efficiency'] + hub)
        act_w = float(np.sum(np.abs(d.actuator_force * d.actuator_velocity)[[self.aid[n_] for n_ in self.aid if 'fan' not in n_ and 'wheel' not in n_ and 'booster' not in n_]]) / P['electrical.actuator_efficiency'])
        fanflow = [min(1.0, self.fan_state[i].get('thrust_n', 0) / max(self.fan.thrust_max * 0.5, 1)) for i in range(4)]
        scale, fuel = self.bus.step(dt, c['engine'], dict(propulsion=prop_e, actuators=act_w), float(self.fuel.sum()), v_air, list(shaft), fanflow)
        fuel += jet_fuel
        self.prop_scale = scale
        for i, k in enumerate(PODS):
            tau = req[i] * (scale if req[i] > 0 else 1.0)
            self.motor_torque[i] = tau
            d.ctrl[self.aid[f'act_pod_{k}_fan']] = P['pods.rotor_spin_sense'][k] * tau
            wd = wheel_tq[i] * (scale if prop_e > 0 else 1)
            d.ctrl[self.aid[f'act_pod_{k}_wheel']] = SIDE[k] * wd
            self.model.dof_frictionloss[self.model.jnt_dofadr[self.jid[f'pod_{k}_wheel']]] = c['brake'][i] * P['pods.brake_torque_nm']
        for j, s in enumerate(WING_SIDES):
            self.booster_torque[j] = breq[j] * (scale if breq[j] > 0 else 1.0)
            d.ctrl[self.aid[f'act_booster_{s}_rotor']] = self.booster_torque[j]
        # fuel burn from tanks that hold fuel
        if fuel > 0 and self.fuel.sum() > 0:
            share = self.fuel / self.fuel.sum()
            self.fuel = np.maximum(0.0, self.fuel - fuel * share)
        # surface aero (held for the next 4 physics steps)
        Rb = self.R(); wind_b = Rb.T @ self.wind
        st = dict(wing_frac={s: (self.joint(f'wing_{s}')[0] + P.wing_stroke_m) / P.wing_stroke_m for s in WING_SIDES},
                  wing_locked={s: self.wing_locked(s) for s in WING_SIDES},
                  flap={s: self.joint(f'flap_{s}')[0] for s in WING_SIDES}, aileron={s: self.joint(f'aileron_{s}')[0] for s in WING_SIDES},
                  canard_pitch={s: self.joint(f'canard_{s}')[0] for s in WING_SIDES},
                  canard_deployed={s: abs(self.joint(f'canard_{s}_fold')[0]) < math.radians(5) for s in WING_SIDES},
                  stab_te_up=self.stab_te_up, rudder=self.rudder)
        # velocity of the body origin in body axes
        self.aero_out = self.aero.compute(vb, w, wind_b, st)
        self.aero_state = st
        self.check_contacts()

    # ------------------------------------------------------------ per-step forces
    def nose_strut_update(self, dt):
        """Take-off stance overlay: each front wheel's spring seat moves down on a rate-limited strut actuator, raising
        the nose. Extended while the wings are out in road stance, retracted otherwise. It is the suspension joint's own
        spring reference and travel that move, so the load path stays spring, damper and tyre."""
        m = self.model; P = self.P
        road = all(abs(self.joint(f'pod_{k}')[0]) < math.radians(10) for k in PODS)
        want = self.nose_lift_max if road and self.wing_state['left'] != 'stowed' else 0.0
        step = P.get('suspension.nose_lift_rate_m_s', 0.05) * dt
        self.nose_lift += float(np.clip(want - self.nose_lift, -step, step))
        lo, hi = P['suspension.travel_m']
        for k in PODS:
            if not FRONT[k]:
                continue
            j = self.jid[f'pod_{k}_susp']; base = self.suspension[k]['springref_m']
            m.qpos_spring[m.jnt_qposadr[j]] = base - self.nose_lift
            m.jnt_range[j] = [lo - self.nose_lift, hi - self.nose_lift]

    def effector_update(self, dt, c, v_air):
        """control_effectors overlay: rudders and booster thrust vectoring from the FCC moment demand; front steering
        from the yaw stick while on the road (speed-scheduled to a lateral-acceleration limit). All rate-limited."""
        P = self.P; dem = (self.fcc.last or {}).get('moment_demand', [0.0, 0.0, 0.0])
        def grp(g):
            return {k: P[f'effectors.{g}.{k}'] for k in P.tree['effectors'][g]}
        r = grp('rudder'); tv = grp('tvc')
        def lim(x, rate):
            return float(np.clip(x, -math.radians(rate) * dt, math.radians(rate) * dt))
        tgt = math.radians(float(np.clip(r['gain_deg_per_demand'] * dem[2], -r['travel_deg'], r['travel_deg'])))
        self.rudder += lim(tgt - self.rudder, r['rate_deg_s'])
        tp = -tv['pitch_gain_deg_per_demand'] * dem[1]; ty = tv['yaw_gain_deg_per_demand'] * dem[2]
        mag = math.hypot(tp, ty); k = min(1.0, tv['travel_deg'] / mag) if mag > 0 else 1.0
        for i, x in enumerate((tp * k, ty * k)):
            self.tvc[i] += lim(math.radians(x) - self.tvc[i], tv['rate_deg_s'])
        st = grp('steering')
        road = self.support_count() > 0 and all(abs(self.joint(f'pod_{k}')[0]) < math.radians(10) for k in PODS)
        L = abs(self.L.bodies['pod_FL_wheel'].anchor[0] - self.L.bodies['pod_RL_wheel'].anchor[0])
        dmax = min(st['max_deg'], math.degrees(math.atan(L * st['lat_accel_max_g'] * 9.80665 / max(v_air * v_air, 1e-6))))
        rate = st['rate_deg_s']
        if any(self.wing_state[s] != 'stowed' for s in WING_SIDES):           # take-off mode: calibrated lock while wings deploy / are out
            dmax = min(dmax, st['takeoff_lock_deg']); rate = st['takeoff_rate_deg_s']
        target = -math.radians(c['yaw'] * dmax) if road else 0.0                 # yaw +1 = nose right = wheels to the right
        for k in PODS:
            n = f'pod_{k}_steer'
            if n in self.targets:
                self.ramp(n, target, math.radians(rate), dt)

    def wheel_drive_torque(self, c):
        """Hub motor torque per wheel. Base plant: command x rated torque at any speed. With the wheel_drive_limits
        overlay: capped at rated power / wheel speed, and faded by traction control between 1x and 2x the slip limit."""
        P = self.P; T = [c['wheel_drive'][i] * P['pods.hub_motor_torque_nm'] for i in range(4)]
        if P.get('drive.limits_enabled', 0.0) <= 0.5:
            return T
        v = abs(float(self.vel_body()[0])); lam = P['drive.traction_slip_max']; r = P['pods.tyre_radius_m']
        out = []
        for i, k in enumerate(PODS):
            om = abs(float(self.joint(f'pod_{k}_wheel')[1]))
            t = math.copysign(min(abs(T[i]), P['pods.hub_motor_power_w'] / max(om, 1e-3)), T[i])
            slip = (om * r - v) / max(v, P['drive.slip_reference_speed_min_m_s'])
            out.append(t * float(np.clip((2 * lam - slip) / lam, 0.0, 1.0)))
        return out

    def apply_forces(self):
        d = self.data; P = self.P
        d.xfrc_applied[:] = 0; d.qfrc_applied[:] = 0
        for i, k in enumerate(PODS):
            b = self.bids[f'pod_{k}_fan']; spin = P['pods.rotor_spin_sense'][k]
            om = spin * self.joint(f'pod_{k}_fan')[1]
            a = self.pod_axis(k); p = d.xpos[b]
            v = self.point_velocity(b, p) - self.wind
            va = float(v @ a); vin = v - va * a
            # inflow: vehicle moving along +axis pushes air into the inlet
            h = None
            if self.step_count % 4 == 0 or not self.fan_state[i]:
                h = self.ray_height(p, -a)
                self.fan_heights = getattr(self, 'fan_heights', [None] * 4); self.fan_heights[i] = h
            else:
                h = getattr(self, 'fan_heights', [None] * 4)[i]
            st = self.fan.state(max(om, 0.0), va, float(np.linalg.norm(vin)), h, a[2])
            self.fan_state[i] = st
            F = st['thrust_n'] * a
            if st['ram_drag_n'] > 0:
                F = F - st['ram_drag_n'] * vin / max(np.linalg.norm(vin), 1e-9)
            mj.mj_applyFT(self.model, d, F, -spin * st['torque_nm'] * a if om > 0 else np.zeros(3), p, b, d.qfrc_applied)
        for j, s in enumerate(WING_SIDES):
            b = self.bids[f'booster_{s}_rotor']; om = self.joint(f'booster_{s}_rotor')[1]
            ax = self.R() @ np.array([1.0, 0, 0])
            dang = math.radians(P['proposals.p3_booster_vector_angle_deg']) + self.tvc[0]; dyaw = self.tvc[1]
            th_dir = self.R() @ np.array([math.cos(dang) * math.cos(dyaw), math.sin(dyaw), math.sin(dang) * math.cos(dyaw)])
            v = self.point_velocity(b, d.xpos[b]) - self.wind
            if self.jet:
                lapse = max(0.0, 1.0 - max(0.0, float(v @ ax)) / self.jet['vj_m_s'])
                T = self.jet_spool[j] * self.jet['t0_station_n'] * lapse
                st = dict(thrust_n=T, torque_nm=0.0, power_w=0.0, spool=self.jet_spool[j], fuel_kg_s=self.jet['sfc_kg_per_n_s'] * T, engine=self.jet['kind'])
            else:
                st = self.booster.state(max(om, 0.0), float(v @ ax), 0.0, None, 0.0)
            self.booster_state[j] = st
            mj.mj_applyFT(self.model, d, st['thrust_n'] * th_dir, -st['torque_nm'] * ax if om > 0 else np.zeros(3), d.xpos[b], b, d.qfrc_applied)
        Rb = self.R(); ab = self.bids['airframe']
        F = Rb @ self.aero_out['force_body']; M = Rb @ self.aero_out['moment_body']
        # moment given about the body origin; mj_applyFT applies at a point, so apply at the origin with that moment
        mj.mj_applyFT(self.model, d, F, M, d.xpos[ab], ab, d.qfrc_applied)
        for name, hm in self.aero_out['hinge_moments'].items():
            if name in self.jid:
                d.qfrc_applied[self.model.jnt_dofadr[self.jid[name]]] += hm

    def point_velocity(self, b, p):
        v6 = np.zeros(6)
        mj.mj_objectVelocity(self.model, self.data, mj.mjtObj.mjOBJ_XBODY, b, v6, 0)
        return v6[3:] + np.cross(v6[:3], p - self.data.xpos[b])

    # ------------------------------------------------------------ contacts
    def check_contacts(self):
        d, m = self.data, self.model
        sup = set(); f6 = np.zeros(6); hard = 0.0; sup_force = 0.0
        for i in range(d.ncon):
            con = d.contact[i]
            g1, g2 = con.geom1, con.geom2
            veh = g1 if m.geom_contype[g1] == 2 else g2 if m.geom_contype[g2] == 2 else None
            if veh is None:
                continue
            mj.mj_contactForce(m, d, i, f6)
            fn = abs(f6[0]); name = m.geom(veh).name
            self.max_impact_n = max(self.max_impact_n, fn)
            if name.startswith(('foot_', 'tyre_')):
                sup.add(name); sup_force += fn
            else:
                hard = max(hard, fn)
        if hard > self.P['contact.crash_force_n'] and not self.crashed:
            self.crashed = True; self.events.append(dict(event='collision', t_s=float(d.time), force_n=hard))
        # Debounced air/ground state: a bounce shorter than AIRBORNE_DEBOUNCE_S is not a new
        # flight phase, so one touchdown no longer logs several events (flight campaign D-14).
        if sup:
            self.no_support_since = None
        elif self.no_support_since is None:
            self.no_support_since = float(d.time)
        if not sup and d.time > 1 and float(d.time) - self.no_support_since >= AIRBORNE_DEBOUNCE_S:
            self.airborne = True
        elif sup and self.airborne:
            sink = float(-d.qvel[2]); self.airborne = False; self.first_contact_sink = sink
            self.events.append(dict(event='touchdown', t_s=float(d.time), sink_rate_m_s=sink, supports=sorted(sup)))
            if sink > self.P['contact.gear_sink_limit_m_s']:
                self.events.append(dict(event='hard_landing', t_s=float(d.time), sink_rate_m_s=sink)); self.flags.add('hard_landing')
        self.support = sorted(sup); self.support_force_n = sup_force

    def support_count(self):
        return len(getattr(self, 'support', []))

    # ------------------------------------------------------------ step
    def step(self):
        if self.step_count % 4 == 0:
            self.control_update(4 * DT)
        self.apply_forces()
        mj.mj_step(self.model, self.data)
        self.step_count += 1
        if not np.all(np.isfinite(self.data.qpos)):
            raise FloatingPointError('Phantom physics produced non-finite state')
        self.apply_fuel_mass()
        self.max_alt = max(self.max_alt, float(self.data.qpos[2] - getattr(self, 'spawn_z', 0)))
        self.record_ring()
        if self.step_log is not None and self.step_count % 4 == 0:
            self.write_step_row()

    RING_COLS = ['t', 'x', 'y', 'z', 'qw', 'qx', 'qy', 'qz', 'vx', 'vy', 'vz', 'p', 'q', 'r', 'T_FL', 'T_FR', 'T_RL', 'T_RR', 'tilt_FL', 'tilt_FR', 'tilt_RL', 'tilt_RR',
                 'Tcmd_FL', 'Tcmd_FR', 'Tcmd_RL', 'Tcmd_RR', 'gen_w', 'buffer_w', 'soc', 'prop_scale', 'support', 'crashed']

    def record_ring(self):
        d = self.data
        row = [d.time, *d.qpos[:7], *d.qvel[:3], *d.qvel[3:6], *[s.get('thrust_n', 0) for s in self.fan_state],
               *[abs(self.joint(f'pod_{k}')[0]) for k in PODS], *(self.alloc.get('thrust') or [0] * 4),
               self.bus.last.get('generator_w', 0), self.bus.last.get('buffer_w', 0), self.bus.soc, self.prop_scale, self.support_count(), float(self.crashed)]
        self.ring[self.ring_i] = row; self.ring_i = (self.ring_i + 1) % len(self.ring)
        if self.ring_i == 0:
            self.ring_full = True

    def dump_ring(self, path):
        r = np.roll(self.ring, -self.ring_i, axis=0) if self.ring_full else self.ring[:self.ring_i]
        np.savez_compressed(path, columns=np.array(self.RING_COLS), data=r, rate_hz=1 / DT, note='20 s pre-event ring buffer, truth channels at 400 Hz')

    STEP_COLS = None

    def step_row(self):
        d = self.data; att = self.attitude(); w = self.rates_body(); vb = self.vel_body(); fl = self.fcc.last; b = self.bus.last
        row = dict(t=d.time, x=d.qpos[0], y=d.qpos[1], z=d.qpos[2], u=vb[0], v=vb[1], w=vb[2], vz_world=d.qvel[2],
                   roll_deg=math.degrees(att['roll']), pitch_up_deg=math.degrees(att['pitch_up']), yaw_left_deg=math.degrees(att['yaw_left']),
                   p_deg_s=math.degrees(w[0]), q_up_deg_s=-math.degrees(w[1]), r_left_deg_s=math.degrees(w[2]),
                   mode=fl.get('mode'), coll_cmd=fl.get('collective_cmd'), coll_applied=fl.get('collective_applied'), vs_cmd=fl.get('vs_cmd'), vs_contrib=fl.get('vs_contribution'),
                   pti_axis=fl.get('pti_axis'), pti_value=fl.get('pti_value'), saturated=fl.get('saturated'),
                   pil_roll=fl.get('pilot_moment', [0] * 3)[0], pil_pitch=fl.get('pilot_moment', [0] * 3)[1], pil_yaw=fl.get('pilot_moment', [0] * 3)[2],
                   aug_roll=fl.get('augmentation_moment', [0] * 3)[0], aug_pitch=fl.get('augmentation_moment', [0] * 3)[1], aug_yaw=fl.get('augmentation_moment', [0] * 3)[2],
                   gen_w=b.get('generator_w'), buffer_w=b.get('buffer_w'), soc=b.get('buffer_soc'), unmet_w=b.get('unmet_w'), residual_w=b.get('balance_residual_w'),
                   loop_T=b.get('loop_temperature_k'), fuel_kg=float(self.fuel.sum()), mass_kg=float(sum(self.model.body_mass)), support=self.support_count())
        for i, k in enumerate(PODS):
            s = self.fan_state[i]
            row.update({f'Tcmd_{k}': (self.alloc.get('thrust') or [0] * 4)[i], f'T_{k}': s.get('thrust_n', 0), f'rpm_{k}': abs(self.joint(f'pod_{k}_fan')[1]) * 60 / (2 * math.pi),
                        f'tau_{k}': self.motor_torque[i], f'tilt_{k}': math.degrees(abs(self.joint(f'pod_{k}')[0])), f'tiltcmd_{k}': (self.alloc.get('tilt_deg') or [0] * 4)[i],
                        f'gef_{k}': s.get('ground_factor', 1), f'ram_{k}': s.get('ram_drag_n', 0), f'leg_{k}': -self.joint(f'leg_{k}')[0], f'oleo_{k}': self.joint(f'leg_{k}_oleo')[0]})
        for j, s in enumerate(WING_SIDES):
            row.update({f'Tb_{s}': self.booster_state[j].get('thrust_n', 0), f'slide_{s}': self.joint(f'wing_{s}')[0], f'flap_{s}': math.degrees(self.joint(f'flap_{s}')[0]),
                        f'ail_{s}': math.degrees(self.joint(f'aileron_{s}')[0]), f'canard_{s}': math.degrees(self.joint(f'canard_{s}')[0]), f'wingstate_{s}': self.wing_state[s]})
        F = self.aero_out['force_body']; M = self.aero_out['moment_body']
        row.update(aero_Fx=F[0], aero_Fy=F[1], aero_Fz=F[2], aero_Mx=M[0], aero_My=M[1], aero_Mz=M[2])
        return row

    def write_step_row(self):
        row = self.step_row()
        if self.STEP_COLS is None:
            self.STEP_COLS = list(row)
            self.step_log.write(','.join(self.STEP_COLS) + '\n')
        self.step_log.write(','.join(f'{v:.6g}' if isinstance(v, float) else str(v) for v in (row[c] for c in self.STEP_COLS)) + '\n')
        # Sync-flush once per simulated second so the log is readable mid-run and survives an
        # abnormal stop up to the last flush (flight campaign D-12).
        if self.step_count % int(round(1.0 / DT)) == 0:
            self.step_log.flush()

    # ------------------------------------------------------------ telemetry
    def physical_snapshot(self):
        d = self.data; mp = self.mass_properties(); b = self.bus.last
        poses = {}
        for n, i in self.bids.items():
            if n == 'world':
                continue
            q = d.xquat[i]
            poses[n] = dict(position=np.round(d.xpos[i], 5).tolist(), quaternion_wxyz=np.round(q, 6).tolist())
        joints = {n: round(float(self.joint(n)[0]), 6) for n in self.jid if n != 'free'}
        # render-only alias so the browser cockpit camera has a 'cabin' frame (driver seat, airframe-fixed)
        Rb = self.R(); seat = np.array(self.P['render.cockpit_eye_m']) if 'render' in self.P.tree else np.array([0.25, -0.35, 0.55])
        poses['cabin'] = dict(position=np.round(d.xpos[self.bids['airframe']] + Rb @ seat, 5).tolist(), quaternion_wxyz=poses['airframe']['quaternion_wxyz'])
        return dict(t_s=float(d.time), variant=self.variant, config_sha256=self.P.config_sha256, body_poses=poses, provenance=self.provenance, events=self.events[-20:],
                    phantom=dict(joints=joints, fan_rpm=[abs(self.joint(f'pod_{k}_fan')[1]) * 60 / (2 * math.pi) for k in PODS],
                                 wheel_rad_s=[self.joint(f'pod_{k}_wheel')[1] for k in PODS], wing_state=dict(self.wing_state),
                                 # render-only context for the booster glow / vectoring cowl (no effect on physics)
                                 booster_thrust_max_n=float(self.jet['t0_station_n'] if self.jet else self.booster.thrust_max),
                                 fan_thrust_max_n=float(self.fan.thrust_max),
                                 booster_engine=(self.jet['kind'] if self.jet else 'edf'),
                                 drs_deg=(math.degrees(self.stab_te_up) if self.p6 else None),
                                 booster_vector_deg=float(self.P['proposals.p3_booster_vector_angle_deg'] + math.degrees(self.tvc[0])),
                                 **({'booster_vector_yaw_deg': math.degrees(self.tvc[1]), 'rudder_deg': math.degrees(self.rudder),
                                     'nose_lift_m': float(self.nose_lift), 'steer_deg': [math.degrees(self.joint(f'pod_{k}_steer')[0]) if f'pod_{k}_steer' in self.jid else 0.0 for k in PODS]} if self.eff else {}),
                                 **({'physics_data': self.physics_data} if self.physics_data else {}),
                                 fan_rpm_max=float(self.fan.omega_max * 60 / (2 * math.pi))),
                    mass=mp, propulsors=[dict(pod=k, cmd_n=(self.alloc.get('thrust') or [0] * 4)[i], **{kk: (float(vv) if not isinstance(vv, bool) else vv) for kk, vv in self.fan_state[i].items()},
                                              motor_torque_nm=float(self.motor_torque[i])) for i, k in enumerate(PODS)],
                    boosters=[dict(side=s, **{kk: (vv if isinstance(vv, (bool, str)) else float(vv)) for kk, vv in self.booster_state[j].items()}) for j, s in enumerate(WING_SIDES)],
                    aero=dict(force_body_n=np.asarray(self.aero_out['force_body']).tolist(), moment_body_nm=np.asarray(self.aero_out['moment_body']).tolist(),
                              surfaces=self.aero_out['surfaces'], hinge_moments=self.aero_out['hinge_moments']),
                    energy=dict(b, totals=self.bus.energy), fcc=self.fcc.last, command=self.fcc.cmd, targets=self.targets,
                    fuel_kg=self.fuel.tolist(), contact=dict(support=getattr(self, 'support', []), max_contact_force_n=self.max_impact_n),
                    faults=self.faults, flags=sorted(self.flags), crashed=self.crashed,
                    mechanical_energy_j=float(d.energy[0] + d.energy[1]))

    def sensor_observation(self, rng, P=None):
        """Pilot-visible sensors only (no truth forces, thrust, inertia or contact manifold)."""
        P = self.P; d = self.data; n = rng.normal; att = self.attitude(); w = self.rates_body(); b = self.bus.last
        rp = self.data.site_xpos[self.model.site('radar').id]
        h = self.ray_height(rp, np.array([0, 0, -1.0]))
        return dict(
            frame_labels=dict(attitude='roll right-down +, pitch nose-up +, yaw nose-left + (ENU heading)', body_rates='p roll-right +, q nose-up +, r nose-left + (body axes)',
                              velocity_body='u forward, v left, w up (body axes)', velocity_world='x, y, z world (z up)',
                              radar_altimeter='antenna-to-surface distance along -z world, NOT gear clearance; on the gear it reads about radar_altimeter_ground_reference_m'),
            gnss_xy_m=np.round(d.qpos[:2] + n(0, P['sensors.gnss_noise_m'], 2), 2).tolist(),
            baro_m=round(float(d.qpos[2] + n(0, 0.01)), 2),
            radar_altimeter_m=None if h is None else round(h + n(0, P['sensors.radar_noise_m']), 3),
            radar_altimeter_ground_reference_m=getattr(self, 'radar_ground_reference_m', None),
            attitude_deg=dict(roll=round(math.degrees(att['roll']) + n(0, P['sensors.attitude_noise_deg']), 3),
                              pitch=round(math.degrees(att['pitch_up']) + n(0, P['sensors.attitude_noise_deg']), 3),
                              yaw=round(math.degrees(att['yaw_left']) + n(0, P['sensors.attitude_noise_deg']), 3)),
            body_rates_deg_s=dict(p=round(math.degrees(w[0]) + n(0, P['sensors.gyro_noise_deg_s']), 3), q=round(-math.degrees(w[1]) + n(0, P['sensors.gyro_noise_deg_s']), 3),
                                  r=round(math.degrees(w[2]) + n(0, P['sensors.gyro_noise_deg_s']), 3)),
            velocity_world_m_s=np.round(d.qvel[:3] + n(0, P['sensors.velocity_noise_m_s'], 3), 3).tolist(),
            velocity_body_m_s=np.round(self.vel_body() + n(0, P['sensors.velocity_noise_m_s'], 3), 3).tolist(),
            airspeed_m_s=round(float(np.linalg.norm(d.qvel[:3] - self.wind)), 2),
            fan_rpm=[round(abs(self.joint(f'pod_{k}_fan')[1]) * 60 / (2 * math.pi), 1) for k in PODS],
            pod_tilt_deg=[round(math.degrees(abs(self.joint(f'pod_{k}')[0])), 2) for k in PODS],
            leg_extension_m=[round(-self.joint(f'leg_{k}')[0], 3) for k in PODS],
            leg_compression_m=[round(self.joint(f'leg_{k}_oleo')[0], 4) for k in PODS],
            weight_on_wheels=self.support_count() > 0,
            wing_state=dict(self.wing_state), flap_deg=[round(math.degrees(self.joint(f'flap_{s}')[0]), 2) for s in WING_SIDES],
            aileron_deg=[round(math.degrees(self.joint(f'aileron_{s}')[0]), 2) for s in WING_SIDES],
            canard_pitch_deg=[round(math.degrees(self.joint(f'canard_{s}')[0]), 2) for s in WING_SIDES],
            canard_fold_deg=[round(math.degrees(self.joint(f'canard_{s}_fold')[0]), 1) for s in WING_SIDES],
            generator_kw=round(b.get('generator_w', 0) / 1000, 1), buffer_kw=round(b.get('buffer_w', 0) / 1000, 1), buffer_soc=round(self.bus.soc, 4),
            power_unmet_kw=round(b.get('unmet_w', 0) / 1000, 1), loop_temperature_c=round(self.bus.loop_T - 273.15, 1),
            motor_temperature_c=[round(t - 273.15, 1) for t in self.bus.motor_T],
            fuel_kg=np.round(self.fuel, 3).tolist(), stability_mode=self.fcc.cmd['stability_mode'],
            pti_active=self.fcc.pti.active, faults=[f['fault'] for f in self.faults],
            warning_lamps=(['IMPACT'] if self.crashed else []) + (['POWER_LIMITED'] if self.prop_scale < 0.999 else []) + (['FUEL_EXHAUSTED'] if self.fuel.sum() <= 1e-3 else [])
                          + (['HARD_LANDING'] if 'hard_landing' in self.flags else []),
            **({'suspension_m': [round(self.joint(f'pod_{k}_susp')[0], 4) for k in PODS]} if 'pod_FL_susp' in self.jid else {}))

    def checkpoint_state(self):
        d = self.data
        return dict(qpos=d.qpos.tolist(), qvel=d.qvel.tolist(), act=d.act.tolist(), ctrl=d.ctrl.tolist(), qacc_warmstart=d.qacc_warmstart.tolist(), time=float(d.time),
                    eq_active=d.eq_active.tolist(), cmd=self.fcc.cmd, vs_int=self.fcc.vs_int, targets=self.targets, wing_state=self.wing_state, fuel=self.fuel.tolist(),
                    bus=self.bus.state(), flags=sorted(self.flags), faults=self.faults, events=self.events[-200:], crashed=self.crashed, max_alt=self.max_alt,
                    max_impact_n=self.max_impact_n, step_count=self.step_count, airborne=self.airborne, spawn_z=getattr(self, 'spawn_z', 0.0),
                    stab_te_up=self.stab_te_up, jet_spool=list(self.jet_spool))

    def restore_state(self, s):
        d = self.data
        for k in ('qpos', 'qvel', 'act', 'ctrl', 'qacc_warmstart'):
            arr = np.asarray(s[k], float)
            if arr.shape != getattr(d, k).shape or not np.all(np.isfinite(arr)):
                raise ValueError('Invalid checkpoint array ' + k)
            getattr(d, k)[:] = arr
        d.time = s['time']; d.eq_active[:] = s['eq_active']
        self.fcc.cmd = s['cmd']; self.fcc.vs_int = s['vs_int']; self.targets = s['targets']; self.wing_state = s['wing_state']
        self.fuel = np.array(s['fuel']); self.bus.restore(s['bus']); self.flags = set(s['flags']); self.faults = s['faults']; self.events = s['events']
        self.crashed = s['crashed']; self.max_alt = s['max_alt']; self.max_impact_n = s['max_impact_n']; self.step_count = s['step_count']
        self.airborne = s['airborne']; self.spawn_z = s['spawn_z']
        self.stab_te_up = s.get('stab_te_up', self.stab_te_up); self.jet_spool = list(s.get('jet_spool', self.jet_spool))
        self.apply_fuel_mass(force=True); mj.mj_forward(self.model, d)
