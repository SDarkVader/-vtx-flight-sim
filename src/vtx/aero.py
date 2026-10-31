"""Explicit provisional blade-element / axial-momentum model.

Planform comes from the saved mesh. Section polar, zero twist, duct neutrality
and axial inflow are hypotheses, not measured VTX performance. No empirical
hover efficiency is fitted to aircraft weight. Vortex-ring/edgewise accuracy is
blocked; the live plant records those out-of-model conditions.
"""
from __future__ import annotations
import math
import numpy as np


class BladeElementModel:
    def __init__(self,blade,rho=1.225,cl_max=1.2,cd0=.012):
        self.rho=rho;self.radius=blade['radius_m'];self.count=blade['count']
        nodes=np.array(blade['stations_m']);chord=np.array(blade['chord_m'])
        self.r=(nodes[:-1]+nodes[1:])/2
        self.dr=np.diff(nodes)
        self.chord=(chord[:-1]+chord[1:])/2
        self.cl_max=cl_max;self.cd0=cd0
        self.last_vi=0.

    def sections(self,omega,pitch,axial):
        tangential=abs(omega)*self.r
        phi=np.arctan2(axial,tangential+1e-9)
        alpha=pitch-phi
        cl=np.clip(2*math.pi*alpha,-self.cl_max,self.cl_max)
        # Post-stall loss, with drag increase: a disclosed synthetic polar.
        stall=np.maximum(abs(alpha)-math.radians(16),0)
        cl*=np.exp(-1.8*stall)
        cd=self.cd0+.02*cl*cl+1.2*np.sin(stall)**2
        dynamic=.5*self.rho*(tangential*tangential+axial*axial)*self.chord*self.count*self.dr
        lift=dynamic*cl;drag=dynamic*cd
        thrust=float(np.sum(lift*np.cos(phi)-drag*np.sin(phi)))
        torque=float(np.sum((lift*np.sin(phi)+drag*np.cos(phi))*self.r))
        return thrust,torque,float(np.max(abs(alpha)))

    def evaluate(self,omega,pitch_deg,axial_inflow=0.):
        if abs(omega)<.01:return dict(thrust_n=0.,torque_nm=0.,induced_mps=0.,max_alpha_deg=0.)
        pitch=math.radians(pitch_deg)
        # Unique normal-working-state fixed point solved by bounded bisection.
        # Negative thrust/autorotation is not qualified by this hover model.
        lo,hi=0.,max(abs(omega)*self.radius,abs(axial_inflow)+1)
        area=math.pi*self.radius**2
        for _ in range(18):
            vi=(lo+hi)/2
            thrust,_,_=self.sections(omega,pitch,axial_inflow+vi)
            momentum=2*self.rho*area*vi*math.hypot(axial_inflow+vi,0.)
            if thrust>momentum:lo=vi
            else:hi=vi
        vi=(lo+hi)/2
        thrust,torque,alpha=self.sections(omega,pitch,axial_inflow+vi)
        # No powered lift with an unspooled rotor; positive operating quadrant.
        # Descending-flow regimes are flagged by the caller as uncalibrated.
        return dict(thrust_n=max(0.,thrust),torque_nm=max(0.,torque),
                    induced_mps=vi,max_alpha_deg=math.degrees(alpha))


def ideal_hover(mass,area,rho=1.225,g=9.80665):
    weight=mass*g
    return dict(weight_n=weight,induced_velocity_mps=math.sqrt(weight/(2*rho*area)),
                ideal_induced_power_w=weight**1.5/math.sqrt(2*rho*area))
