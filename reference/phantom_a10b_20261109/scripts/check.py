import sys, math, json, numpy as np
sys.path.insert(0, sys.argv[1]); import camp as C
from vtx.phantom.params import Params
from vtx.phantom.plant import PhantomAircraft
from vtx.phantom.surface_aero import SurfaceAero
from vtx.world import TestWorld
P6={'proposals': {'p6_drs_stabilator': {'v': 1.0}}}
out={}
for tag,o in (('b835295b',None),('70089cca',P6)):
    P=Params('phantom-fx',o); assert P.config_sha256.startswith(tag)
    a=PhantomAircraft(TestWorld(),'phantom-fx',overrides=o,start_configuration='road'); mp=a.mass_properties()
    cg=np.array(mp['cg_body_m']); SA=SurfaceAero(P); V=60.; w=P.handover['aero_surfaces']['wing']; q=.5*SA.rho*V*V; cms=[]
    for al in (0.,4.):
        th=math.radians(al); vb=np.array([V*math.cos(th),0,-V*math.sin(th)])
        st=dict(wing_frac=dict(left=1.,right=1.),wing_locked=dict(left=True,right=True),flap=dict(left=0.,right=0.),aileron=dict(left=0.,right=0.),
                canard_pitch=dict(left=0.,right=0.),canard_deployed=dict(left=True,right=True),stab_te_up=math.radians(P['proposals.p6_stab_rest_te_up_deg']) if o else 0.0)
        r=SA.compute(vb,np.zeros(3),np.zeros(3),st); M=r['moment_body']-np.cross(cg,r['force_body']); cms.append(-M[1]/(q*w['S_ref_m2']*w['mac_m']))
    out[tag]=dict(mass=mp['mass_kg'],cg=[round(x,3) for x in cg],inertia_diag=[round(mp['inertia_body_kg_m2'][i][i]) for i in range(3)],cm_alpha_per_rad=(cms[1]-cms[0])/math.radians(4))
    out[tag]['vtol']=C.vtol_ceiling('phantom-fx',o,seconds=8.0)
    print(tag,json.dumps(out[tag],default=float)); sys.stdout.flush()
