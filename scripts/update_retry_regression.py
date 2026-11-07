from pathlib import Path
p=Path(__file__).resolve().parents[1]/'tests/test_live_interface.py'
s=p.read_text(encoding='utf-8')
a='''    lab.aircraft.spawn(13.7,-28.4,4)
    for _ in range(3000):
        lab.integrate()
        if lab.aircraft.crashed:break
    assert lab.aircraft.crashed
    memory_hash=hashlib.sha256(lab.memory_path.read_bytes()).hexdigest()
    first=started['run_id'];new=lab.retry({'authority':'manual','airframe_variant':'light'})
'''
b='''    lab.aircraft.spawn(13.7,-28.4,4)
    memory_hash=hashlib.sha256(lab.memory_path.read_bytes()).hexdigest()
    first=started['run_id']
    for _ in range(3000):
        lab.integrate()
        if lab.run_id!=first:break
    assert lab.run_id!=first
    new={'run_id':lab.run_id}
'''
assert s.count(a)==1
p.write_text(s.replace(a,b),encoding='utf-8',newline='\n')
