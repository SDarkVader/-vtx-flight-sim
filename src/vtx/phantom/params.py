"""Phantom parameter loader: base + variant overlay, provenance labels, manifest coverage."""
from __future__ import annotations
import copy, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARAMETER_FILE = ROOT / 'inputs/phantom_parameters_v1.json'
MANIFEST_FILE = ROOT / 'inputs/phantom_simulation_manifest_v0.json'
A10B_CHARACTERISTICS_FILE = ROOT / 'evidence/phantom/a10b_characteristics.json'
LABELS = {'MEASURED-K', 'DERIVED', 'SYNTHETIC_UNVALIDATED', 'MANUFACTURER', 'REGULATORY_REFERENCE'}
VARIANTS = ('phantom-a10b', 'phantom-a10c', 'phantom', 'phantom-fx', 'phantom-a9', 'phantom-fx-a9')   # phantom-a10b = A10-B (current default); phantom-fx = A10-A; -a9 = earlier
DEFAULT_VARIANT = 'phantom-a10b'
CASSETTE_REVISIONS = ('A9', 'A10')


OVERLAY_DIR = ROOT / 'inputs/phantom_overlays'
_A10B_CHARACTERISTICS_CACHE = None


def load_a10b_characteristics():
    global _A10B_CHARACTERISTICS_CACHE
    if _A10B_CHARACTERISTICS_CACHE is None and A10B_CHARACTERISTICS_FILE.exists():
        _A10B_CHARACTERISTICS_CACHE = json.loads(A10B_CHARACTERISTICS_FILE.read_text(encoding='utf-8'))
    return copy.deepcopy(_A10B_CHARACTERISTICS_CACHE) if _A10B_CHARACTERISTICS_CACHE else {}


class PhantomConfigError(ValueError):
    pass


def _strip(d):
    return {k: (_strip(v) if isinstance(v, dict) else v) for k, v in d.items() if not k.startswith('_')}


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict) and 'v' not in v:
            _merge(a[k], v)
        else:
            a[k] = copy.deepcopy(v)
    return a


def _check_labels(node, path=''):
    if isinstance(node, dict):
        if 'v' in node and 'l' in node:
            if node['l'] not in LABELS:
                raise PhantomConfigError(f'{path}: label {node["l"]!r} not allowed')
            if 'u' not in node or 's' not in node:
                raise PhantomConfigError(f'{path}: number needs unit and source')
            return 1
        return sum(_check_labels(v, f'{path}.{k}' if path else k) for k, v in node.items())
    return 0


class Params:
    def __init__(self, variant='phantom', overrides=None, path=PARAMETER_FILE):
        if variant not in VARIANTS:
            raise PhantomConfigError(f'unknown Phantom variant {variant!r}')
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        # line endings folded to LF so a Windows (CRLF) checkout reports the same parameter-file identity as Linux
        self.file_sha256 = hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        self.variant = variant
        chain, v = [], variant
        while v:   # a variant may inherit another (e.g. phantom-fx-a9 = phantom-fx + A9 cassette)
            chain.insert(0, raw['variants'][v]); v = raw['variants'][v].get('inherits')
        self.tree = copy.deepcopy(raw['base'])
        for entry in chain:
            for name in entry.get('overlay_files', []):      # opt-in overlays named by a variant (inputs/phantom_overlays)
                _merge(self.tree, _strip(json.loads((OVERLAY_DIR / f'{name}.json').read_text(encoding='utf-8'))))
            _merge(self.tree, entry.get('overlay', {}))
        if overrides:
            _merge(self.tree, overrides)
        self.n_numbers = _check_labels(self.tree)
        self.variant_info = {k: v for k, v in raw['variants'][variant].items() if k != 'overlay'}
        self.manifest_map = raw['manifest_map']
        self.revision_log = raw['revision_log']
        self.config_sha256 = hashlib.sha256(json.dumps(self.tree, sort_keys=True).encode()).hexdigest()
        rev = self.cassette_revision = self.tree['geometry_sources']['wing_cassette_revision']
        if rev not in CASSETTE_REVISIONS:
            raise PhantomConfigError(f'unknown wing cassette revision {rev!r}')
        files = self.tree['geometry_sources']['revisions'][rev]
        h = ROOT / files['handover']
        if not h.exists():
            raise PhantomConfigError(f'wing cassette revision {rev}: missing {h.relative_to(ROOT)}')
        self.handover = json.loads(h.read_text())
        slide = next(j for j in self.handover['joints'] if j['name'] == f'{rev}_JOINT_WING_R_SLIDE')
        self.wing_stroke_m = -float(slide['range_m'][0])   # stowed slide position is -stroke
        self.geometry = json.loads((ROOT / self.tree['geometry_sources']['measured']).read_text())
        self.manifest_coverage()

    def node(self, key):
        n = self.tree
        for part in key.split('.'):
            n = n[part]
        return n

    def __getitem__(self, key):
        n = self.node(key)
        return n['v'] if isinstance(n, dict) and 'v' in n else n

    def get(self, key, default=None):
        """Value of an optional parameter (e.g. one supplied only by an overlay); default when absent."""
        try:
            return self[key]
        except (KeyError, TypeError):
            return default

    def label(self, key):
        return self.node(key)['l']

    def manifest_coverage(self):
        manifest = json.loads(MANIFEST_FILE.read_text())
        missing = []
        def walk(d, p=''):
            if isinstance(d, dict):
                for k, v in d.items():
                    walk(v, f'{p}.{k}' if p else k)
            elif isinstance(d, list):
                if d and isinstance(d[0], dict):
                    for it in d:
                        walk(it, p + '[]')
                elif any(x is None for x in d):
                    check(p)
            elif d is None:
                check(p)
        def check(p):
            m = self.manifest_map.get(p)
            if not m:
                missing.append(p); return
            if 'param' in m:
                try:
                    self.node(m['param'])
                except KeyError:
                    missing.append(p)
        walk(manifest)
        if missing:
            raise PhantomConfigError('manifest fields without a selected value: ' + ', '.join(sorted(set(missing))))
        return True

    def snapshot(self):
        return dict(variant=self.variant, parameter_file_sha256=self.file_sha256, config_sha256=self.config_sha256,
                    variant_info=self.variant_info, revision_log=self.revision_log, parameters=self.tree,
                    **({'characteristics': load_a10b_characteristics()} if self.variant == 'phantom-a10b' else {}))
