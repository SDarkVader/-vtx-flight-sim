with open('public/vtx-env/tactical-minimap.js', 'r', encoding='utf-8') as f:
    c = f.read()

target = "pt: [-30, 290]"
repl = "pt: [-30, 220]"

if target in c:
    c = c.replace(target, repl)
    with open('public/vtx-env/tactical-minimap.js', 'w', encoding='utf-8') as f:
        f.write(c)
    print('Updated volcano point in tactical-minimap.js successfully!')
else:
    print('target not found')
