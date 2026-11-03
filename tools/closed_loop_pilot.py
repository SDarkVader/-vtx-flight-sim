"""Instrument-driven experimental VTX waypoint controller. No prerecorded flight path."""
import json, math, time
from pathlib import Path
from persistent_pilot import request, BASE

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
    view=request(BASE,"/api/view")
    if not view.get("active") or view.get("authority")!="colin":
        raise SystemExit("No active Colin sortie")
    run=view["run_id"]
    print("Controller for",run,"target",view["mission"]["destination"],flush=True)
    request(BASE,"/api/operator",{"stability_assist":1.0,"experimental_assist_wire":True})
    request(BASE,"/api/operator",{"paused":False})
    last=-1
    while True:
        view=request(BASE,"/api/view")
        if view.get("run_id")!=run or not view.get("active") or view.get("authority")!="colin":
            print("Flight ended or authority changed",flush=True);break
        if view.get("paused"):
            print("Operator paused flight",flush=True);break
        obs=request(BASE,"/api/observe")
        if obs["observation_id"]==last:
            time.sleep(0.3);continue
        last=obs["observation_id"]
        attitude=obs["attitude_xyz_deg"]
        rates=obs["gyro_world_deg_s"]
        if max(abs(x) for x in attitude[:2])>12 or max(abs(x) for x in rates)>15 or "IMPACT" in obs["warning_lamps"]:
            request(BASE,"/api/operator",{"paused":True})
            print("Flight paused on attitude/rate/impact guard",attitude,rates,flush=True);break
        target=view["mission"]["destination"]
        cmd,dist=command(obs,target)
        request(BASE,"/api/action",{**cmd,"authority":"colin",
          "observation_id":obs["observation_id"],
          "reason":"Closed-loop climb and waypoint guidance from live instruments"})
        if last%20==0:
            print("t",obs["t_s"],"clearance",obs["radar_clearance_m"],
                  "rpm",obs["rotor_rpm"],"distance",round(dist,1),flush=True)
        time.sleep(0.35)
if __name__=="__main__":
    main()
