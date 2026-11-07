from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[1]
edge=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
fixture=root/'tests/phantom-effects-browser-fixture.html'
served=root/'public/phantom-effects-verification-temp.html'
if served.exists(): raise SystemExit('Temporary browser fixture already exists; refusing to overwrite')
try:
 served.write_text(fixture.read_text(encoding='utf8'),encoding='utf8')
 with tempfile.TemporaryDirectory(prefix='vtx-fx-check-') as profile:
  args=[str(edge),'--headless=new','--disable-gpu','--use-gl=swiftshader','--no-first-run','--disable-extensions','--disable-background-networking',f'--user-data-dir={profile}','--virtual-time-budget=12000','--dump-dom','http://127.0.0.1:18879/phantom-effects-verification-temp.html']
  p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
  html=p.stdout.decode('utf8','replace')
  start=html.find('<pre id="result">');end=html.find('</pre>',start)
  result=html[start:end+6]
  print(result)
  if p.returncode or start<0 or end<0 or 'FAIL' in result or 'pending' in result: raise SystemExit(1)
finally:
 served.unlink(missing_ok=True)
