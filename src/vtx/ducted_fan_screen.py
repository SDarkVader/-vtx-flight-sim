"""Hover-only ducted-fan screening, not an installed thrust model.

The open-rotor figure of merit is a user-supplied experimental assumption. The
ideal duct bound is separate from it; they must not be combined as gains.
No result here models inlet blockage, fan dynamics, transition or descent.
"""
import math


def _positive(name, value):
    value=float(value)
    if not math.isfinite(value) or value <= 0:raise ValueError(f'{name} must be finite and positive')
    return value


def annulus_area(tip_radius_m, hub_radius_m):
    tip=_positive('tip_radius_m',tip_radius_m)
    hub=float(hub_radius_m)
    if not math.isfinite(hub) or hub < 0 or hub >= tip:raise ValueError('hub radius must be finite and in [0, tip radius)')
    return math.pi*(tip*tip-hub*hub)


def hover_power_w(thrust_n, area_m2, figure_of_merit_open, density_kg_m3=1.225):
    """Shaft power from assumed FM relative to the open actuator-disk ideal."""
    thrust=_positive('thrust_n',thrust_n)
    area=_positive('area_m2',area_m2)
    density=_positive('density_kg_m3',density_kg_m3)
    fm=_positive('figure_of_merit_open',figure_of_merit_open)
    return thrust**1.5/(fm*math.sqrt(2*density*area))


def hover_thrust_n(power_w, area_m2, figure_of_merit_open, density_kg_m3=1.225):
    power=_positive('power_w',power_w)
    area=_positive('area_m2',area_m2)
    density=_positive('density_kg_m3',density_kg_m3)
    fm=_positive('figure_of_merit_open',figure_of_merit_open)
    return (power*fm*math.sqrt(2*density*area))**(2/3)


def ideal_duct_bound_power_w(thrust_n, area_m2, exit_area_ratio, density_kg_m3=1.225):
    """Ideal duct actuator-disk bound, not an achievable efficiency claim."""
    thrust=_positive('thrust_n',thrust_n)
    area=_positive('area_m2',area_m2)
    sigma=_positive('exit_area_ratio',exit_area_ratio)
    density=_positive('density_kg_m3',density_kg_m3)
    return thrust**1.5/math.sqrt(4*density*area*sigma)
