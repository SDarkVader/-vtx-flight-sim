from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'src/vtx/live_server.py'
s=p.read_text(encoding='utf-8')
a="        if obs and self.aircraft.data.time-obs['t_s']>1.:raise HTTPException(409,'Observation is more than one simulated second old; observe again')\n"
b="        if p.data.time-self.last_command_time>5 and not self.lease_expired:\n            p.set_command(dict(engine=p.command['engine'],collective_deg=[0.]*4,tilt_deg=p.command['tilt_deg'],cabin_deg=p.command['cabin_deg']))\n            self.lease_expired=True;self.log('command_lease_expired',dict(behavior='feather collective; keep bench engine and servos powered; no flight rescue'))\n"
assert s.count(a)==1 and s.count(b)==1
s=s.replace(a,'').replace(b,'').replace('20 ms simulated transport, held targets; 5 simulated seconds lease then feather collective while engine remains available; experimental rate damping is shadow-only','20 ms simulated transport; accepted targets remain held until changed, authority transfers, or flight ends')
p.write_text(s,encoding='utf-8',newline='\n')
p=root/'src/vtx/phantom/live.py';s=p.read_text(encoding='utf-8')
a="    if p.data.time - lab.last_command_time > LEASE_S and not lab.lease_expired:\n        p.lease_failsafe(); lab.lease_expired = True\n        lab.log('command_lease_expired', dict(event='ABORT', behavior='collective 0, boosters 0, wheel drive 0, brakes on; all other targets held; no flight rescue'))\n        p.dump_ring(lab.log_path / 'lease_abort_ring.npz')\n"
assert s.count(a)==1
s=s.replace(a,'').replace("    lease_rem = max(0.0, LEASE_S - (float(d.time) - lab.last_command_time))\n",'').replace("lease_remaining_s=round(lease_rem, 3)","command_mode='hold_until_changed'").replace("lease_remaining_s=max(0.0, LEASE_S - (float(d.time) - lab.last_command_time))","command_mode='hold_until_changed'")
s=s.replace("    if lab.lease_expired:\n        obs['warning_lamps'] = obs['warning_lamps'] + ['COMMAND_LEASE_EXPIRED']\n",'')
p.write_text(s,encoding='utf-8',newline='\n')
