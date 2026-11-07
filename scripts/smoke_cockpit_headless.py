from pathlib import Path
from html.parser import HTMLParser
import subprocess, tempfile, json

class Inspect(HTMLParser):
    def __init__(self): super().__init__(); self.ids=set(); self.canvas=0; self.phantom_panel=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'): self.ids.add(a['id'])
        if tag=='canvas' and 'data-engine' in a: self.canvas+=1
        if a.get('id')=='phantom-panel': self.phantom_panel=True
edge=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
with tempfile.TemporaryDirectory(prefix='vtx-edge-smoke-') as profile:
    args=[edge,'--headless=new','--disable-gpu','--use-gl=swiftshader','--no-first-run','--disable-extensions','--disable-background-networking',f'--user-data-dir={profile}','--virtual-time-budget=12000','--dump-dom','http://127.0.0.1:18879/']
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=35)
    parser=Inspect();parser.feed(r.stdout.decode('utf-8','replace'))
    required={'viewport','models','runway-start','phantom-start','engineering','history','open-records'}
    result={'browser_exit':r.returncode,'three_canvas':parser.canvas,'phantom_panel':parser.phantom_panel,'missing_ids':sorted(required-parser.ids)}
    print(json.dumps(result))
    if parser.canvas<1 or result['missing_ids']:raise SystemExit(1)
