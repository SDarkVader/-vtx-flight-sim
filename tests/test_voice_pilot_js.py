"""Runs the browser voice-pilot grammar test under Node (skipped where Node is unavailable)."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which('node') is None, reason='node not installed')
def test_voice_pilot_grammar():
    r = subprocess.run(['node', str(ROOT / 'tests/js/voice_pilot.test.mjs')], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
