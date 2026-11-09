import sys, json, numpy as np
sys.path.insert(0, sys.argv[1]); import camp as C
P6={'proposals': {'p6_drs_stabilator': {'v': 1.0}}}
a=C.plant('phantom-fx',P6,start_configuration='vtol')
a.set_command(dict(stability_mode='attitude_vs',collective=1.0,vertical_speed_m_s=2.0,brake=[0.0]*4)); C.run(a,12)
a.set_command(dict(vertical_speed_m_s=0.0)); log=[]
C.run(a,40,every=0.5,log=lambda a: log.append((float(a.data.time),float(a.data.qpos[2]),dict(a.bus.last))))
b=log[-1][2]; print('hover', json.dumps(dict(z=log[-1][1],dz_last20=log[-1][1]-log[-40][1],gen_kw=b['generator_w']/1e3,buf_kw=b['buffer_w']/1e3,soc=b['buffer_soc'],to_used=b['takeoff_rating_used_s'],buf_limit_kw=b['buffer_discharge_limit_w']/1e3,fuel_kg_s=b['fuel_flow_kg_s'])))
print('buffer_kwh', a.P['buffer.energy_kwh'] if 'buffer.energy_kwh' in str(a.P.tree) else 'see params')
r=C.takeoff_climb('phantom-fx',P6); r.pop('trace',None); print('to_climb',json.dumps(r,default=float))
r=C.takeoff_climb('phantom-fx',None); r.pop('trace',None); print('to_climb_noP6',json.dumps(r,default=float))
