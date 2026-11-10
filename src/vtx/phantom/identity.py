"""Aircraft identity: pins a canonical variant's physics configuration to its visual asset.

inputs/aircraft_identity.json lists, per pinned variant, the configuration hash, the parameter-file hash
(line endings normalised) and the visual asset with its hash. verify() compares a built aircraft against the pin."""
from __future__ import annotations
import hashlib, json, subprocess
from functools import lru_cache
from pathlib import Path
from .params import ROOT

IDENTITY_FILE = ROOT / 'inputs/aircraft_identity.json'


def text_sha256(path):
    """SHA-256 of a text file with CRLF folded to LF (the same value on Windows and Linux checkouts)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


@lru_cache(maxsize=16)
def _asset_sha256(path, mtime, size):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def asset_sha256(uri):
    path = ROOT / 'public' / str(uri).lstrip('/')
    if not path.is_file():
        return None
    st = path.stat()
    return _asset_sha256(str(path), st.st_mtime_ns, st.st_size)


@lru_cache(maxsize=1)
def git_commit():
    """Commit of the running checkout, or None outside a git checkout (e.g. a packaged build)."""
    try:
        out = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        version = ROOT / 'VERSION.txt'
        return None if not version.exists() else None


def pins():
    return {k: v for k, v in json.loads(IDENTITY_FILE.read_text(encoding='utf-8')).items() if not k.startswith('_')}


def verify(aircraft, experimental=False):
    """Compare a built Phantom against its pin. Returns the effective identity and every mismatch found."""
    P = aircraft.P; prov = aircraft.provenance
    asset = prov.get('render_asset')
    effective = dict(variant=aircraft.variant, revision=prov.get('revision'), config_sha256=P.config_sha256,
                     parameter_file_sha256=P.file_sha256, model_xml_sha256=prov.get('model_xml_sha256'),
                     render_asset=asset, render_asset_sha256=asset_sha256(asset), git_commit=git_commit())
    pin = pins().get(aircraft.variant)
    if pin is None:
        return dict(effective, pinned=False, verified=None, experimental=bool(experimental), mismatches=[],
                    status='not pinned (historical or reference variant)')
    mismatches = [dict(field=k, expected=pin[k], loaded=effective.get(k))
                  for k in ('config_sha256', 'parameter_file_sha256', 'render_asset', 'render_asset_sha256')
                  if effective.get(k) != pin[k]]
    if experimental:   # a declared experiment changes the configuration on purpose; it is labelled, never passed off as canonical
        mismatches = [m for m in mismatches if m['field'] != 'config_sha256']
    ok = not mismatches
    status = ('verified' if ok and not experimental else 'experimental configuration (declared overrides)' if ok
              else 'MISMATCH: ' + '; '.join(f"{m['field']} expected {m['expected']} loaded {m['loaded']}" for m in mismatches))
    return dict(effective, name=pin.get('name'), pinned=True, verified=ok and not experimental, experimental=bool(experimental),
                mismatches=mismatches, status=status)
