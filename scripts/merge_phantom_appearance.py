from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
def stage(n): return subprocess.check_output(['git','-C',str(root),'show',f':{n}:public/vtx-env/phantom-look.js']).decode('utf-8')
base=stage(2); other=stage(3)
start=other.index('// Appearance only:'); end=other.index('export function attachPhantom',start)
helpers=other[start:end]
anchor='export function attachPhantom(model) {'
assert base.count(anchor)==1
base=base.replace(anchor,helpers+anchor+"\n  if (model.getObjectByName('A10_WING_L_PANEL_CFRP_TORSION_BOX')) {\n    stylePhantom(model);\n    addRearDeckDetail(model);\n  }")
(root/'public/vtx-env/phantom-look.js').write_text(base,encoding='utf-8',newline='\n')
