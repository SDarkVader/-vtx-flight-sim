"""Explicit historical flight parents for integrated, unpromoted candidates."""
from functools import lru_cache
import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[3] / 'inputs' / 'flight_revisions.json'


@lru_cache(maxsize=1)
def registry():
    value = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
    if value.get('schema') != 1:
        raise ValueError('Unsupported flight revision registry')
    return value


def flight_revision(variant):
    return registry()['revisions'].get(variant)
