"""Visualize (do not synthesize) saved RC-01 F03 dynamics logs; camera follows aircraft."""
from pathlib import Path
import numpy as np, pandas as pd, cv2, math, json, subprocess
from scipy.spatial.transform import Rotation
from ricochet_water_solver import ST,RING,hull_mesh
D=Path(__file__).resolve().parent
DATA=pd.read_csv(D/'RC01_F03_nominal_timeseries.csv')
RESULT=json.loads((D/'RC01_F03_results.json').read_text())
WIDTH,HEIGHT=1280,720; F=15;DURATION=24
BLUE=(207,157,49); TEAL=(221,191,74);GOLD=(70,190,237);WHITE=(230,238,242);GRAY=(151,164,175);BG=(32,26,21)
font=cv2.FONT_HERSHEY_SIMPLEX
# All colours use BGR (OpenCV)
view=np.array([9.,-13.,7.5]);view/=np.linalg.norm(view)
right=np.cross(np.array([0.,0.,1.]),view);right/=np.linalg.norm(right)
up=np.cross(view,right);up/=np.linalg.norm(up)
CENTER=np.array([440,318]);SCALE=65
mesh=hull_mesh();verts=mesh.vertices;faces=mesh.faces
# float points / section polygons F01
floats=[]
for y in [-3.8,3.8]:
    RINGS=np.array([[-.34+sx,y, .42+sz] for sx,sz in [(-.56,0),(-.3,.14),(.3,.14),(.56,0),(.3,-.14),(-.3,-.14)]])
    floats.append(RINGS)

def tx(body,r):
    rv=Rotation.from_euler('xyz',[math.radians(r.roll_deg),math.radians(r.pitch_deg),math.radians(r.yaw_deg + 90.0)])
    world=rv.apply(np.asarray(body,dtype=float))
    world[:,2]+=r.z_origin_m
    return world

def project(points):
    points=np.atleast_2d(points)
    return np.column_stack([CENTER[0]+SCALE*(points@right),CENTER[1]-SCALE*(points@up)]).astype(np.int32)

def line(img,a,b,col,thick=1):cv2.line(img,tuple(map(int,a)),tuple(map(int,b)),col,thick,cv2.LINE_AA)
def text(img,s,x,y,size=.5,color=WHITE,weight=1):cv2.putText(img,str(s),(int(x),int(y)),font,size,color,weight,cv2.LINE_AA)
def rect(img,x0,y0,x1,y1,col,alpha=1.0):
    if alpha==1:cv2.rectangle(img,(x0,y0),(x1,y1),col,-1)
    else:
        over=img.copy();cv2.rectangle(over,(x0,y0),(x1,y1),col,-1);cv2.addWeighted(over,alpha,img,1-alpha,0,img)

def arrow(img,p0,p1,color=GOLD,thickness=3):
    cv2.arrowedLine(img,tuple(p0.astype(int)),tuple(p1.astype(int)),color,thickness,cv2.LINE_AA,tipLength=.17)

def hull_artist(img,r):
    coords=tx(verts,r);proj=project(coords)
    # moderate mesh overlay: silhouette solid tinted, retained frame visible in outlines
    tris=[]
    for f in faces:
        pp=proj[f];normal=np.cross(coords[f[1]]-coords[f[0]],coords[f[2]]-coords[f[0]])
        if np.linalg.norm(normal)<1e-8:continue
        normal/=np.linalg.norm(normal)
        dot=abs(float(np.dot(normal,view)))
        tris.append((np.mean(coords[f]@view), pp, dot))
    tris.sort(key=lambda x:x[0],reverse=False)
    layer=img.copy()
    for depth,poly,dot in tris:
        strength=int(56+45*dot)
        cv2.fillConvexPoly(layer,poly,(strength+25,strength+8,strength-10),cv2.LINE_AA)
    cv2.addWeighted(layer,.75,img,.25,0,img)
    # bulkhead reference polygons on the hull and load arrows
    for st,q in zip(ST,RING):
        pts=np.column_stack([np.full(len(q),st[1]),q])
        p=project(tx(pts,r));cv2.polylines(img,[p],True,(137,183,190),1,cv2.LINE_AA)
    # forward and aft wing skeleton, each contains conceptual spar locations
    for sign in (-1,1):
        root=np.array([[.82,.80*sign,1.10],[.82-2.10,.80*sign,1.10]])
        tip=np.array([[.15,4.76*sign,1.23],[.15-1.13,4.76*sign,1.23]])
        wpoly=np.array([root[0],tip[0],tip[1],root[1]])
        pw=project(tx(wpoly,r));over=img.copy();cv2.fillPoly(over,[pw],(75,79,88));cv2.addWeighted(over,.8,img,.2,0,img)
        cv2.polylines(img,[pw],True,GOLD,2,cv2.LINE_AA)
        # spars
        for t in [.25,.7]:
            sp=np.stack([root[0]*(1-t)+root[1]*t,tip[0]*(1-t)+tip[1]*t]);pr=project(tx(sp,r));line(img,*pr,(138,185,211),2)
        # Float supports and floats; no simulated deformation of these virtual solids
        aft=np.array([[-.34,3.80*sign,.42],[-.34,3.80*sign,1.23]])
        pr=project(tx(aft,r));line(img,*pr,(177,165,106),3)
        ff=floats[0 if sign<0 else 1]
        pf=project(tx(ff,r));cv2.fillPoly(img,[pf],(96,126,119));cv2.polylines(img,[pf],True,(180,202,171),2,cv2.LINE_AA)
    # rear ducted fans represented as axis+annulus, no fabricated spinning rotor kinetics
    for sign in (-1,1):
        yy=sign*1.22;ctr=np.array([-2.22,yy,1.70]);n=36
        circle=np.array([ctr+np.array([0,.45*np.cos(a),.45*np.sin(a)]) for a in np.linspace(0,2*math.pi,n)])
        pp=project(tx(circle,r));cv2.polylines(img,[pp],True,GOLD,2,cv2.LINE_AA)
        c=project(tx([ctr],r))[0];cv2.circle(img,tuple(c),4,GOLD,-1,cv2.LINE_AA)
    # tail pylon
    for a,b in [([-1.75,0,.91],[-2.3,0,1.7]),([-2.3,0,1.7],[-2.62,0,2.3])]:
        p=project(tx([a,b],r));line(img,*p,GOLD,4)
    # three bulkhead force arrows, scaled only visually using same recorded applied force
    for i in [2,3,4]:
        st=ST[i];p=np.array([st[1],0,st[3]+.3])
        at=project(tx([p],r))[0]
        load=float(r[f'load_{st[0]}_N'])/1000
        end=at+np.array([0,-round(18+16*load)])
        arrow(img,at,end,TEAL,2)
        text(img,f'{st[0]} {load:.1f} kN',end[0]-43,end[1]-10,.38,TEAL,1)
    # CG nominal plus force arrow
    cg=project(tx([[.45,0,.59]],r))[0]
    cv2.circle(img,tuple(cg),6,(255,255,255),1,cv2.LINE_AA)
    cv2.line(img,tuple(cg+[-10,0]),tuple(cg+[10,0]),WHITE,1,cv2.LINE_AA)
    cv2.line(img,tuple(cg+[0,-10]),tuple(cg+[0,10]),WHITE,1,cv2.LINE_AA)
    text(img,'CG*',cg[0]+11,cg[1]+14,.39,WHITE)
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
        # Near-coincident arrows demonstrate low lateral slip.
    return cg

def draw_water(img,r):
    # Studio tank appearance, no false wave forces: waterline fixed at z=0.
    water=img.copy();rect(water,0,126,883,590,(57,57,51)); water[72:591,0:884]=cv2.addWeighted(water[72:591,0:884],.55,img[72:591,0:884],.45,0)
    # still water plane as light grid in projected perspective, scrolling with simulated distance
    # coordinates in body-following frame; lake long axis is test direction
    phase=r.y_m%2.5
    for j in np.arange(-24.,24.,2.5):
        y=j-phase
        P=np.array([[-24,y,0],[24,y,0]])
        pr=project(P)
        line(water,*pr,(85,81,68),1)
    for x in np.arange(-24.,25.,2.5):
        pr=project([[-x,-26,0],[-x,26,0]])
        line(water,*pr,(79,79,65),1)
    img[72:591,0:884]=water[72:591,0:884]
    # water baseline and calm condition text
    text(img,'CALM WATER  |  free surface 0.00 m  |  no waves',28,555,.45,(156,179,190))

def draw_plot(img,field,c,xx,yy,ww,hh,y_lim,label):
    series=DATA[field].values;T=DATA.time_s.values
    cv2.rectangle(img,(xx,yy),(xx+ww,yy+hh),(65,62,57),1)
    a,b=y_lim
    iy=lambda y:round(yy+hh-(float(y)-a)/(b-a)*hh)
    pts=np.column_stack([xx+np.rint(T/DURATION*ww),np.rint([iy(v) for v in series])]).astype(np.int32)
    cv2.polylines(img,[pts],False,c,1,cv2.LINE_AA)
    text(img,label,xx+6,yy-5,.42,c)

def render(t):
    row=DATA.iloc[min(int(round(t/.02)),len(DATA)-1)]
    img=np.full((HEIGHT,WIDTH,3),BG,dtype=np.uint8)
    rect(img,0,0,WIDTH,72,(21,23,27))
    text(img,'VTX    RICOCHET  /  RC-01 F03',26,37,.85,WHITE,2)
    text(img,'ISOLATED CALM-WATER ENGINEERING TEST',26,58,.42,TEAL,1)
    text(img,'F03 RENDER FIX V2  -  REDUCED ORDER / NOT CFD',830,37,.43,GOLD,1)
    rect(img,0,72,884,595,(42,41,38))
    draw_water(img,row)
    hull_artist(img,row)
    text(img,'Follow camera / heading corrected to world +Y (lake axis)',24,94,.43,WHITE)
    text(img,'CYAN: BODY +X   GREEN: VELOCITY   (nearly coincident = forward travel)',25,117,.35,(154,206,218))
    # bottom 125px plot region
    rect(img,0,593,884,HEIGHT,(27,29,31))
    # mini charts
    draw_plot(img,'pitch_deg',(148,177,239),40,631,260,55,(-3,4),'Pitch deg')
    draw_plot(img,'roll_deg',TEAL,338,631,240,55,(-4,4),'Roll deg')
    draw_plot(img,'hydro_buoyancy_N',GOLD,619,631,220,55,(7000,10500),'Buoyancy N')
    curx=int(40+t/DURATION*260)
    cv2.line(img,(curx,632),(curx,686),(215,221,226),1,cv2.LINE_AA)
    # right dashboard
    rect(img,885,72,WIDTH,720,(23,26,31))
    text(img,'TELEMETRY / WATER TEST',909,109,.58,WHITE,2)
    text(img,f'T+ {t:05.2f} s',915,143,.52,GOLD)
    text(img,f'{math.hypot(row.vx_mps,row.vy_mps):.2f}',914,200,1.7,WHITE,2)
    text(img,'m/s  surface speed',1049,201,.43,GRAY)
    text(img,f'{row.y_m:.2f} m',912,243,.76,TEAL,2)
    text(img,'along lake axis',1065,243,.40,GRAY)
    body_head=np.array([math.cos(math.radians(row.yaw_deg+90)),math.sin(math.radians(row.yaw_deg+90))])
    vv=np.array([row.vx_mps,row.vy_mps]); vf=float(np.dot(vv,body_head));vs=float(np.cross(np.append(body_head,0),np.append(vv,0))[2])
    text(img,f'WORLD HEADING {row.yaw_deg+90.:6.2f} deg / FWD {vf:.2f} / SIDE {vs:+.2f} m/s',910,705,.40,WHITE)
    for i,(title,v,unit) in enumerate([
        ('ROLL',row.roll_deg,'deg'),('PITCH',row.pitch_deg,'deg'),('YAW FROM +Y',row.yaw_deg,'deg'),
        ('BUOYANCY',row.hydro_buoyancy_N/1000,'kN'),('THRUST',row.thrust_N/1000,'kN'),
        ('MUNK SENS.',row.munk_sensitivity_yaw_Nm,'N m')]):
        yy=276+i*41;text(img,title,913,yy,.41,GRAY)
        text(img,f'{v:+.2f} {unit}',1111,yy,.54,WHITE)
    rect(img,909,523,1261,527,(60,75,83))
    text(img,'BULKHEAD WATER FORCE ALLOCATION',910,553,.43,TEAL)
    for i,s in enumerate(ST):
        load=row[f'load_{s[0]}_N']/1000
        yy=578+i*19;text(img,s[0],912,yy,.38,GRAY)
        cv2.rectangle(img,(950,yy-11),(1185,yy-1),(54,53,47),-1)
        cv2.rectangle(img,(950,yy-11),(min(1185,950+round(load/3*235)),yy-1),TEAL,-1)
        text(img,f'{load:.2f}',1200,yy,.38,WHITE)
    # timeline
    bar=int((WIDTH-45)*t/DURATION)
    rect(img,20,708,20+bar,713,TEAL)
    return img

def main():
    out=str(D/'RC01_F03_calmwater_dynamics_orientation_fix_v2.mp4')
    writer=cv2.VideoWriter(out,cv2.VideoWriter_fourcc(*'mp4v'),F,(WIDTH,HEIGHT))
    for frame in range(int(DURATION*F)+1):writer.write(render(frame/F))
    writer.release()
    frame=render(15.4)
    cv2.imwrite(str(D/'RC01_F03_animation_preview_orientation_fix_v2.png'),frame)
    # transcode MP4 to H264 for broad compatibility and GIF preview
    p=str(D/'RC01_F03_calmwater_h264_orientation_fix_v2.mp4')
    subprocess.run(['ffmpeg','-y','-v','error','-i',out,'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart','-crf','22',p],check=True)
    subprocess.run(['ffmpeg','-y','-v','error','-i',p,'-vf','fps=8,scale=720:-1:flags=lanczos,palettegen','-frames:v','1',str(D/'palette.png')],check=True)
    subprocess.run(['ffmpeg','-y','-v','error','-i',p,'-i',str(D/'palette.png'),'-lavfi','fps=8,scale=720:-1:flags=lanczos [x]; [x][1:v] paletteuse','-t','12',str(D/'RC01_F03_calmwater_preview_orientation_fix_v2.gif')],check=True)
    print('Created',p,(D/'RC01_F03_calmwater_preview_orientation_fix_v2.gif').stat().st_size)
if __name__=='__main__':main()
