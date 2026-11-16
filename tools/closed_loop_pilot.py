"""Instrument-driven experimental VTX waypoint controller. No prerecorded flight path."""
import math

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def command(obs, target):
    pos=obs["gnss_xy_m"]
    vel=obs["gnss_velocity_mps"]
    z=obs["radar_clearance_m"] or 0.0
    vz=vel[2]
    rpm=min(obs["rotor_rpm"])
    dx,dy=target[0]-pos[0],target[1]-pos[1]
    dist=math.hypot(dx,dy)
    # Hold position while climbing; translate only after reaching safe clearance.
    if z<7.0:
        tx,ty=0.0,0.0
    else:
        tx=clamp(0.012*dx-0.22*vel[0],-3.0,3.0)
        ty=clamp(0.012*dy-0.22*vel[1],-3.0,3.0)
    # Reference trim is provisional; vertical speed feedback prevents open-loop climb.
    target_vz=clamp((10.0-z)*0.28,-0.35,0.65)
    collective=clamp(13.5+2.0*(target_vz-vz),0.0,20.0)
    if rpm<900:
        collective=0.0
    return dict(engine=1.0,collective_deg=[collective]*4,
                tilt_deg=[[tx,ty] for _ in range(4)],
                cabin_deg=[0.0,0.0,0.0],cabin_level=True),dist

def main():
    raise SystemExit('This prewritten waypoint navigator is offline only. Use live telemetry and individual learned pilot commands in the game.')
if __name__=="__main__":
    main()
