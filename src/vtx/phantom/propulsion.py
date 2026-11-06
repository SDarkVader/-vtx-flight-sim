"""Ducted-fan actuator-disk model for the Phantom pod fans and rear EDF boosters.

Convention (research note s1/s8): FM_open is referred to the OPEN-rotor ideal, so the static
shaft power is P = T^1.5 / (FM_open * sqrt(2 rho A)). With axial inflow V_a (positive into the
inlet) the induced velocity comes from momentum theory, v_i = -V_a/2 + sqrt(V_a^2/4 + T/(2 rho A)),
and P = T (V_a + v_i) / FM_open. In descent (-2 v_h < V_a < 0) the Leishman empirical induced
velocity is used and the descending-wake flag is raised. Thrust from shaft speed follows the
fixed-pitch law T = k_T w^2 (1 - J/J0) with J = V_a/(w R); k_T is DERIVED so the peak shaft
power is absorbed at design_speed_fraction of the tip-speed limit. Negative thrust (windmilling)
is NOT modelled: thrust is floored at zero above J0 (stated limitation). Ram (momentum) drag:
D = m_dot V_inplane with m_dot = sqrt(rho A sigma T). Ground effect: Cheeseman-Bennett
T_IGE/T_OGE = 1/(1-(R/4z)^2), capped, applied only with the axis within 30 deg of vertical.
"""
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class DuctedFan:
    area_m2: float
    r_tip_m: float
    fm_open: float
    sigma: float
    power_peak_w: float
    torque_max_nm: float
    tip_speed_max_m_s: float
    design_fraction: float = 0.97
    j0: float = 0.8
    rho: float = 1.225
    ge_cap: float = 1.25

    def __post_init__(self):
        self.omega_max = self.tip_speed_max_m_s / self.r_tip_m
        self.thrust_max = (self.fm_open * self.power_peak_w) ** (2 / 3) * (2 * self.rho * self.area_m2) ** (1 / 3)
        self.k_t = self.thrust_max / (self.design_fraction * self.omega_max) ** 2
        self.k_q = self.k_t ** 1.5 / (self.fm_open * math.sqrt(2 * self.rho * self.area_m2))
        self.equivalent_radius = math.sqrt(self.area_m2 / math.pi)

    @classmethod
    def pod(cls, P):
        rt, rh = P['pods.fan_r_tip_m'], P['pods.fan_r_hub_m']
        return cls(math.pi * (rt * rt - rh * rh), rt, P['pods.fm_open'], P['pods.duct_sigma'], P['pods.motor_power_peak_w'],
                   P['pods.motor_torque_peak_nm'], P['pods.tip_speed_max_m_s'], P['pods.design_speed_fraction'],
                   P['pods.zero_thrust_advance_ratio'], P['atmosphere.density_kg_m3'], P['pods.ground_effect_cap'])

    @classmethod
    def booster(cls, P):
        return cls(P['boosters.exit_area_m2'], P['boosters.rotor_radius_m'], P['boosters.fm_open'], 1.0, P['boosters.shaft_power_max_w'],
                   P['boosters.torque_max_nm'], P['boosters.tip_speed_max_m_s'], 0.97, 0.8, P['atmosphere.density_kg_m3'], 1.0)

    def ground_factor(self, height_m, axis_vertical_cos):
        if height_m is None or axis_vertical_cos < math.cos(math.radians(30)) or height_m <= 0:
            return 1.0
        x = self.equivalent_radius / (4 * max(height_m, 1e-3))
        return min(self.ge_cap, 1.0 / max(1e-6, 1 - x * x)) if x < 1 else self.ge_cap

    def induced(self, thrust, v_axial):
        """Return (v_i, descending_wake_flag). v_axial positive = flow entering the inlet (climb)."""
        if thrust <= 0:
            return 0.0, False
        vh = math.sqrt(thrust / (2 * self.rho * self.area_m2))
        if v_axial >= 0:
            return -v_axial / 2 + math.sqrt(v_axial * v_axial / 4 + vh * vh), False
        x = v_axial / vh
        if x <= -2:
            return -v_axial / 2 - math.sqrt(v_axial * v_axial / 4 - vh * vh), False
        k = [1.15, -1.125, -1.372, -1.718, -0.655]
        return vh * (k[0] + k[1] * x + k[2] * x * x + k[3] * x ** 3 + k[4] * x ** 4), True

    def state(self, omega, v_axial=0.0, v_inplane=0.0, height_m=None, axis_vertical_cos=0.0):
        """Thrust, aerodynamic torque, shaft power, ram drag for a shaft speed (rad/s, >= 0)."""
        w = abs(omega)
        if w < 1e-6:
            return dict(thrust_n=0.0, torque_nm=0.0, power_w=0.0, ram_drag_n=0.0, v_induced=0.0, ground_factor=1.0, descending_wake=False, advance_ratio=0.0)
        J = v_axial / (w * self.r_tip_m)
        gf = self.ground_factor(height_m, axis_vertical_cos)
        t0 = self.k_t * w * w * max(0.0, 1 - J / self.j0)
        vi, dw = self.induced(t0, v_axial)
        p_ideal = t0 * (v_axial + vi)
        # static calibration: at J = 0 this equals k_q w^3 exactly
        power = max(p_ideal, 0.0) / self.fm_open
        thrust = t0 * gf
        ram = math.sqrt(self.rho * self.area_m2 * self.sigma * thrust) * abs(v_inplane) if thrust > 0 else 0.0
        return dict(thrust_n=thrust, torque_nm=power / w, power_w=power, ram_drag_n=ram, v_induced=vi, ground_factor=gf,
                    descending_wake=dw, advance_ratio=J)

    def omega_for_thrust(self, thrust):
        return math.sqrt(max(thrust, 0.0) / self.k_t)

    def hover_power(self, thrust):
        return thrust ** 1.5 / (self.fm_open * math.sqrt(2 * self.rho * self.area_m2))

    def summary(self):
        return dict(area_m2=self.area_m2, r_tip_m=self.r_tip_m, equivalent_radius_m=self.equivalent_radius, fm_open=self.fm_open, sigma=self.sigma,
                    thrust_max_n=self.thrust_max, k_t=self.k_t, k_q=self.k_q, omega_max_rad_s=self.omega_max, power_peak_w=self.power_peak_w,
                    torque_max_nm=self.torque_max_nm, label='DERIVED from SYNTHETIC_UNVALIDATED fan inputs')
