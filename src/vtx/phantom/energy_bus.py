"""Series turboelectric energy bus: turbogenerators + peak-power buffer -> HV DC bus -> loads.

Arbitration priority: avionics > flight actuators > cooling (minimum) > propulsion (proportional
derate) > buffer charging. A supply deficit becomes a propulsion scale factor < 1 that the plant
applies to every lift-fan and booster motor torque; nothing is created from nothing. Balance
residual per step = supply - (delivered loads + charging + losses accounted) and is logged.
Lumped thermal nodes: central liquid loop (generator, buffer and HV losses) with a radiator whose
rejection = static (powered fans) + ram term; per-pod motor nodes cooled by the fan stream.
"""
from __future__ import annotations
import math


class EnergyBus:
    def __init__(self, P, ledger):
        self.P = P
        self.n_gen = int(P['generators.count'])
        self.gen_rating = P['generators.power_each_w']
        self.gen_to = P['generators.takeoff_power_each_w']
        self.to_time = P['generators.takeoff_time_s']
        self.gen_eff = P['generators.efficiency']
        self.sfc = P['generators.sfc_kg_per_kwh'] / 3.6e6       # kg per J electrical
        self.idle = P['generators.idle_fraction']
        self.tau = P['generators.spool_tau_s']
        self.ramp = P['generators.ramp_fraction_per_s']
        bm = next(c for c in ledger.components if c.id == 'buffer_battery')
        self.buffer_mass = bm.mass_kg
        self.e_total = P['buffer.energy_j']
        self.p_cont = bm.mass_kg * P['buffer.specific_power_cont_w_kg']
        self.p_peak = bm.mass_kg * P['buffer.specific_power_peak_w_kg']
        self.peak_time = P['buffer.peak_time_s']
        self.p_charge = self.p_cont * P['buffer.charge_power_fraction']
        self.eta_buf = math.sqrt(P['buffer.round_trip_efficiency'])
        self.soc = P['buffer.soc_initial']; self.soc_min = P['buffer.soc_min']
        self.buf_T = P['atmosphere.temperature_k']; self.buf_Tmax = P['buffer.temperature_max_k']
        self.buf_C = bm.mass_kg * P['buffer.heat_capacity_j_kg_k']
        self.peak_credit = self.peak_time
        self.gen_power = [0.0] * self.n_gen     # electrical output now
        self.to_used = [0.0] * self.n_gen
        self.loop_T = P['atmosphere.temperature_k']
        self.loop_C = P['thermal.loop_heat_capacity_j_k']; self.loop_Tlim = P['thermal.loop_temperature_limit_k']
        self.rad_static = P['thermal.radiator_rejection_static_w']; self.rad_ram = P['thermal.radiator_rejection_ram_w_per_m_s']
        self.fan_power = P['thermal.cooling_fan_power_w']
        self.avionics = P['electrical.avionics_power_w']; self.accessory = P['electrical.accessory_power_w']
        self.standby = P['electrical.actuator_standby_power_w']
        self.motor_T = [P['atmosphere.temperature_k']] * 4
        self.motor_C = P['thermal.motor_heat_capacity_j_k']; self.motor_UA = P['thermal.motor_cooling_ua_w_k']
        self.motor_Tlim = P['thermal.motor_winding_limit_k']
        self.eta_drive = P['pods.motor_efficiency'] * P['pods.inverter_efficiency']
        self.energy = dict(fuel_kg=0.0, generator_j=0.0, buffer_out_j=0.0, buffer_in_j=0.0, propulsion_j=0.0, unmet_j=0.0, losses_j=0.0, residual_j=0.0)
        self.last = {}
        self.events = []

    def buffer_limits(self, dt=None):
        usable = max(0.0, (self.soc - self.soc_min) * self.e_total)
        pmax = self.p_cont + (self.p_peak - self.p_cont) * (self.peak_credit / self.peak_time)
        if self.buf_T >= self.buf_Tmax:
            pmax = min(pmax, 0.25 * self.p_cont)
        if dt:
            pmax = min(pmax, usable * self.eta_buf / dt)     # never discharge below soc_min within a step
        return (pmax if usable > 0 else 0.0), (self.p_charge if self.soc < 0.999 else 0.0)

    def step(self, dt, engine_lever, demand, fuel_available_kg, airspeed=0.0, motor_shaft_w=None, fan_flow_frac=None):
        """demand: dict avionics, actuators, propulsion (electrical W requested). Returns scale for propulsion."""
        T0 = self.P['atmosphere.temperature_k']
        cooling_req = self.fan_power if (self.loop_T > T0 + 5 or demand['propulsion'] > 1e4) else 0.2 * self.fan_power
        base = self.avionics + self.accessory * (engine_lever > 0) + self.standby + demand['actuators'] + cooling_req
        want = base + demand['propulsion']
        # generator: load-following setpoint with first-order spool and ramp limit
        gen_avail_total = 0.0
        for i in range(self.n_gen):
            running = engine_lever > 0 and fuel_available_kg > 1e-6
            lim = self.gen_rating
            if running and self.gen_to > self.gen_rating and self.to_used[i] < self.to_time:
                lim = self.gen_to
            cap = engine_lever * lim if running else 0.0
            target = min(cap, max(self.idle * self.gen_rating if running else 0.0, want / max(self.n_gen, 1)))
            dp = (target - self.gen_power[i]) * min(1.0, dt / self.tau)
            dp = max(-self.ramp * self.gen_rating * dt * 3, min(self.ramp * self.gen_rating * dt, dp)) if running else (target - self.gen_power[i]) * min(1.0, dt / self.tau)
            self.gen_power[i] = max(0.0, self.gen_power[i] + dp)
            if self.gen_power[i] > self.gen_rating * 1.001:
                self.to_used[i] += dt
            gen_avail_total += self.gen_power[i]
        b_dis, b_chg = self.buffer_limits(dt)
        supply_max = gen_avail_total + b_dis
        # arbitration
        delivered_base = min(base, supply_max)
        left = supply_max - delivered_base
        prop = min(demand['propulsion'], left)
        scale = prop / demand['propulsion'] if demand['propulsion'] > 1 else 1.0
        load = delivered_base + prop
        b_out = max(0.0, load - gen_avail_total)
        surplus = max(0.0, gen_avail_total - load)
        b_in = min(surplus, b_chg)
        gen_used = load - b_out + b_in
        # generators shed unused output (load following)
        if gen_avail_total > 0:
            f = gen_used / gen_avail_total
            self.gen_power = [g * f for g in self.gen_power]
        # buffer state
        e_out = b_out / self.eta_buf * dt; e_in = b_in * self.eta_buf * dt
        self.soc = min(1.0, max(0.0, self.soc - (e_out - e_in) / self.e_total))
        if b_out > self.p_cont:
            self.peak_credit = max(0.0, self.peak_credit - dt)
        else:
            self.peak_credit = min(self.peak_time, self.peak_credit + dt * 0.1)
        buf_loss = (e_out - b_out * dt) / dt + (b_in - b_in * self.eta_buf)
        self.buf_T += (buf_loss - 0.0) * dt / self.buf_C
        gen_loss = gen_used * (1 / self.gen_eff - 1)
        fuel = gen_used * self.sfc * dt
        # loop thermal
        q_in = gen_loss + 0.02 * prop + buf_loss * 0.5
        rej = (self.rad_static * (cooling_req / self.fan_power) + self.rad_ram * airspeed) * max(0.0, (self.loop_T - T0) / 60.0)
        self.loop_T += (q_in - rej) * dt / self.loop_C
        self.buf_T -= max(0.0, self.buf_T - self.loop_T) * 20 * dt / self.buf_C
        # motor nodes
        if motor_shaft_w is not None:
            for i, ps in enumerate(motor_shaft_w):
                heat = abs(ps) * (1 / self.eta_drive - 1)
                cool = self.motor_UA * (0.2 + 0.8 * (fan_flow_frac[i] if fan_flow_frac else 1)) * (self.motor_T[i] - T0)
                self.motor_T[i] += (heat - cool) * dt / self.motor_C
        unmet = want - load
        E = self.energy
        E['fuel_kg'] += fuel; E['generator_j'] += gen_used * dt; E['buffer_out_j'] += b_out * dt; E['buffer_in_j'] += b_in * dt
        E['propulsion_j'] += prop * dt; E['unmet_j'] += unmet * dt
        residual = (gen_used + b_out) - (load + b_in)
        E['residual_j'] += residual * dt
        self.last = dict(generator_w=gen_used, generator_available_w=gen_avail_total, generator_each_w=list(self.gen_power), takeoff_rating_used_s=list(self.to_used),
                         buffer_w=b_out - b_in, buffer_soc=self.soc, buffer_temperature_k=self.buf_T, buffer_discharge_limit_w=b_dis,
                         demand_w=want, delivered_w=load, unmet_w=unmet, propulsion_scale=scale, cooling_w=cooling_req,
                         loop_temperature_k=self.loop_T, motor_temperature_k=list(self.motor_T), fuel_flow_kg_s=fuel / dt if dt else 0.0,
                         bus_voltage_v=self.P['electrical.bus_voltage_v'] * (0.9 + 0.1 * self.soc), bus_current_a=load / self.P['electrical.bus_voltage_v'],
                         balance_residual_w=residual)
        return scale, fuel

    def motor_power_limit(self, i):
        """Thermal derate of a lift motor: peak below winding limit, continuous above."""
        if self.motor_T[i] >= self.motor_Tlim:
            return self.P['pods.motor_power_cont_w'] * 0.5
        return self.P['pods.motor_power_peak_w']

    def state(self):
        return dict(soc=self.soc, buf_T=self.buf_T, peak_credit=self.peak_credit, gen_power=self.gen_power, to_used=self.to_used, loop_T=self.loop_T,
                    motor_T=self.motor_T, energy=self.energy)

    def restore(self, s):
        self.soc = s['soc']; self.buf_T = s['buf_T']; self.peak_credit = s['peak_credit']; self.gen_power = list(s['gen_power'])
        self.to_used = list(s['to_used']); self.loop_T = s['loop_T']; self.motor_T = list(s['motor_T']); self.energy = dict(s['energy'])
