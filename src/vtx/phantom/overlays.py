"""Opt-in parameter overlays (inputs/phantom_overlays/*.json), merged as Params overrides.

Overlays add physics or hardware that the base parameter file does not carry, without changing the base
configuration SHA of runs that do not use them:
  hull_lift_v1        forebody lifting-body / Munk term (tools/phantom/hull_lift_vlm.py)
  road_suspension_v1  sprung road wheels (slide joint per pod, sized from the ledger corner loads)

  overrides = overlays.load('hull_lift_v1', 'road_suspension_v1', extra={'proposals': {...}})
"""
from __future__ import annotations
import json
from pathlib import Path
from .params import ROOT, OVERLAY_DIR, _merge, _strip

AVAILABLE = tuple(sorted(p.stem for p in OVERLAY_DIR.glob('*.json')))


def load(*names, extra=None):
    out = {}
    for n in names:
        p = OVERLAY_DIR / f'{n}.json'
        if not p.exists():
            raise ValueError(f'unknown Phantom overlay {n!r}; available: {", ".join(AVAILABLE)}')
        _merge(out, _strip(json.loads(p.read_text())))
    if extra:
        _merge(out, extra)
    return out
