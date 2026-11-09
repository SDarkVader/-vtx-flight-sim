import sys
from pygltflib import GLTF2
def table(f):
    g=GLTF2().load(f); t={}
    for n in g.nodes:
        if n.mesh is None: continue
        for k,p in enumerate(g.meshes[n.mesh].primitives):
            m=g.materials[p.material]
            t[(n.name,k)]=(m.name, m.alphaMode, m.pbrMetallicRoughness.baseColorFactor[3] if m.pbrMetallicRoughness and m.pbrMetallicRoughness.baseColorFactor else 1.0)
    return t
a=table(sys.argv[1]); b=table(sys.argv[2])
only_a=sorted(set(a)-set(b)); only_b=sorted(set(b)-set(a))
diff=[(k,a[k],b[k]) for k in sorted(set(a)&set(b)) if a[k]!=b[k]]
print('primitives: live-sim %d, animated %d | only in live-sim %d | only in animated %d | material differences %d' % (len(a),len(b),len(only_a),len(only_b),len(diff)))
for k in only_a[:6]: print('  only live-sim:',k)
for k in only_b[:6]: print('  only animated:',k)
for k,x,y in diff[:12]: print('  DIFF',k,'\n     live-sim:',x,'\n     animated:',y)
