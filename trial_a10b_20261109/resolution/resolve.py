"""resolve.py FILE CHOICE... : resolve conflict hunks in order. CHOICE: ours | theirs | ours+theirs | theirs+ours | @path (custom text file)."""
import sys, re, pathlib
path = pathlib.Path(sys.argv[1]); choices = sys.argv[2:]
lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
out, i, h = [], 0, 0
while i < len(lines):
    if lines[i].startswith('<<<<<<< '):
        ours, theirs = [], []; i += 1
        while not lines[i].startswith('======='): ours.append(lines[i]); i += 1
        i += 1
        while not lines[i].startswith('>>>>>>> '): theirs.append(lines[i]); i += 1
        i += 1
        c = choices[h] if h < len(choices) else choices[-1]; h += 1
        if c.startswith('@'): out.append(pathlib.Path(c[1:]).read_text(encoding='utf-8'))
        else:
            for part in c.split('+'): out.extend(ours if part == 'ours' else theirs)
    else:
        out.append(lines[i]); i += 1
path.write_text(''.join(out), encoding='utf-8')
print(path, 'resolved', h, 'hunks')
