from pathlib import Path
import re
D=Path('/mnt/data/RC01_F03_CalmWater')
p=(D/'render_animation.py').read_text()
p=p.replace("rv=Rotation.from_euler('xyz',[math.radians(r.roll_deg),math.radians(r.pitch_deg),math.radians(r.yaw_deg)])", "rv=Rotation.from_euler('xyz',[math.radians(r.roll_deg),math.radians(r.pitch_deg),math.radians(r.yaw_deg + 90.0)])")
# Add direct objective orientation audit overlay to the animation
needle="    text(img,'CG*',cg[0]+11,cg[1]+14,.39,WHITE)\n    return cg"
replacement="""    text(img,'CG*',cg[0]+11,cg[1]+14,.39,WHITE)
    # Display independent markers for +BODY-X and world velocity. These are
    # projected in the identical world axes as the solved hull attitude.
    from scipy.spatial.transform import Rotation as _R
    o = np.array([.45,0.,.59])
    orient=_R.from_euler('xyz',[r.roll_deg,r.pitch_deg,r.yaw_deg+90.],degrees=True)
    body_x=orient.apply([1,0,0])
    p0=project(tx([o],r))[0]
    p1=project(tx([o+np.array([1.20,0,0])],r))[0]
    arrow(img,p0,p1,(95,242,238),3)
    text(img,'BODY +X',p1[0]+8,p1[1]-2,.37,(95,242,238))
    v=np.array([r.vx_mps,r.vy_mps,r.vz_mps]); sp=np.linalg.norm(v)
    if sp>.10:
        end=p0+(project([v/sp*1.3])[0]-project([[0,0,0]])[0])
        arrow(img,p0,end,(80,248,151),2)
        text(img,'VELOCITY',end[0]+8,end[1]+9,.35,(80,248,151))
    return cg"""
assert needle in p
p=p.replace(needle,replacement)
p=p.replace("text(img,'Follow camera  /  6 DOF pose from calculated trajectory',24,94,.48,WHITE)","text(img,'Follow camera / body +X heading corrected to lake +Y / arrows: heading & velocity',24,94,.42,WHITE)")
p=p.replace("text(img,'REDUCED-ORDER MODEL  -  NOT CFD / FEA / LIVE VTX',830,37,.46,GOLD,1)","text(img,'F03 RENDER FIX V2  -  REDUCED ORDER / NOT CFD',830,37,.43,GOLD,1)")
p=p.replace("('ROLL',row.roll_deg,'deg'),('PITCH',row.pitch_deg,'deg'),('YAW',row.yaw_deg,'deg'),", "('ROLL',row.roll_deg,'deg'),('PITCH',row.pitch_deg,'deg'),('YAW FROM +Y',row.yaw_deg,'deg'),")
p=p.replace("    text(img,'along lake axis',1065,243,.40,GRAY)", "    text(img,'along lake axis',1065,243,.40,GRAY)\n    body_head=np.array([math.cos(math.radians(row.yaw_deg+90)),math.sin(math.radians(row.yaw_deg+90))])\n    vv=np.array([row.vx_mps,row.vy_mps]); vf=float(np.dot(vv,body_head));vs=float(np.cross(np.append(body_head,0),np.append(vv,0))[2])\n    text(img,f'WORLD HEADING {row.yaw_deg+90.:6.2f} deg / FWD {vf:.2f} / SIDE {vs:+.2f} m/s',910,705,.40,WHITE)")
p=p.replace("out=str(D/'RC01_F03_calmwater_dynamics.mp4')", "out=str(D/'RC01_F03_calmwater_dynamics_orientation_fix_v2.mp4')")
p=p.replace("D/'RC01_F03_animation_preview.png'","D/'RC01_F03_animation_preview_orientation_fix_v2.png'")
p=p.replace("p=str(D/'RC01_F03_calmwater_h264.mp4')","p=str(D/'RC01_F03_calmwater_h264_orientation_fix_v2.mp4')")
p=p.replace("D/'RC01_F03_calmwater_preview.gif'","D/'RC01_F03_calmwater_preview_orientation_fix_v2.gif'")
(D/'render_animation_orientation_fix_v2.py').write_text(p)
print('Wrote patch',len(p))
