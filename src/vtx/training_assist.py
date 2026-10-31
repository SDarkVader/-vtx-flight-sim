"""Experimental, simulation-only body-rate damping; not a flight safety system."""
import math


def assisted_collective(requested, body_rates_deg_s, level):
    """Blend bounded opposing pitch corrections while preserving pair totals.

    Assumes the four modeled fans are east, north, west, south, and positive
    collective increases upward thrust. Effectiveness changes with tilt and flow;
    this deliberately small fixed gain is an experimental hypothesis.
    """
    if len(requested)!=4 or len(body_rates_deg_s)!=3:
        raise ValueError('Expected four collectives and three body rates')
    if not all(math.isfinite(v) for v in [*requested,*body_rates_deg_s,level]) or not 0<=level<=1 or any(not 0<=v<=30 for v in requested):
        raise ValueError('Invalid assistance input')
    result=list(requested)
    def pair(positive,negative,desired):
        # Equal and opposite changes cannot exceed either actuator's headroom.
        amount=max(-min(result[positive],30-result[negative]),
                   min(desired,30-result[positive],result[negative]))
        result[positive]+=amount;result[negative]-=amount
    # A change in north/south thrust creates an X-axis moment; east/west Y.
    roll=max(-.5,min(.5,-.04*body_rates_deg_s[0]))*level
    pitch=max(-.5,min(.5,-.04*body_rates_deg_s[1]))*level
    pair(1,3,roll)
    pair(2,0,pitch)
    return result
