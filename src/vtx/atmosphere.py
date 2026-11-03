"""Simple standard atmosphere for selectable, provisional simulation cases.

Altitude is geopotential metres referenced to mean sea level, not terrain AGL.
Model valid from -1 km through 20 km. No humidity, weather, or engine lapse.
Reference: https://ntrs.nasa.gov/api/citations/20120003268/downloads/20120003268.pdf
"""
import math


def standard_air_density(altitude_m):
    h = float(altitude_m)
    if not math.isfinite(h) or not -1000 <= h <= 20000:
        raise ValueError('ISA altitude must be finite and between -1000 and 20000 m')
    t0, p0, gas, gravity, lapse = 288.15, 101325., 287.05287, 9.80665, .0065
    t11 = t0-lapse*11000
    if h <= 11000:
        temperature=t0-lapse*h
        pressure=p0*(temperature/t0)**(gravity/(gas*lapse))
    else:
        temperature=t11
        p11=p0*(t11/t0)**(gravity/(gas*lapse))
        pressure=p11*math.exp(-gravity*(h-11000)/(gas*t11))
    return pressure/(gas*temperature)
