"""Summarise a sweep_clearance.py result as a markdown table of moving parts.

Usage:  python tools/phantom/summarize_sweep.py evidence/phantom/a9_sweep.json [REGEX]
"""
import json
import re
import sys

d = json.load(open(sys.argv[1]))
pat = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
print(f"Frames swept: {d['frames'][0]}..{d['frames'][-1]} ({len(d['frames'])} samples); "
      f"surface sample spacing {d['sample_spacing_m'] * 1000:.0f} mm; {len(d['moving_objects'])} moving parts.\n")
print("| Moving part | Intersections (partner: frames) | Touching contacts, not penetrating | Minimum clearance (partner, frame) |")
print("| --- | --- | --- | --- |")
for name in sorted(d['per_object']):
    if pat and not pat.search(name):
        continue
    p = d['per_object'][name]
    hits = '; '.join(f"{k}: {v}" for k, v in p['collisions'].items()) or 'none'
    mc = p['min_clearance']
    clear = f"{mc['m'] * 1000:.1f} mm ({mc['partner']}, f{mc['frame']})" if mc else '> 250 mm'
    cont = '; '.join(f"{k}: {v}" for k, v in p.get('contacts', {}).items()) or 'none'
    print(f"| {name} | {hits} | {cont} | {clear} |")
static = [s for s in d['static_intersections_first_frame'] if not pat or pat.search(s['a']) or pat.search(s['b'])]
print(f"\nStatic intersections at frame {d['frames'][0]} involving matched parts: {len(static)}")
for s in static:
    print(f"- {s['a']} <-> {s['b']} ({s['triangle_pairs']} triangle pairs, {'PENETRATING' if s.get('confirmed', True) else 'touching only'})")
