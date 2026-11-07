"""Unified launcher never replaces a running simulator or pins the R6 airframe."""
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_unified.py"
spec = importlib.util.spec_from_file_location("vtx_launch_unified", PATH)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_existing_port_refused_without_mutating_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "port_available", lambda host, port: False)
    monkeypatch.setenv("VTX_DATA_ROOT", "original")
    with pytest.raises(RuntimeError, match="already occupied"):
        launcher.configure(tmp_path, 8765)
    assert launcher.os.environ["VTX_DATA_ROOT"] == "original"


def test_isolated_port_allows_all_vehicle_variants(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "port_available", lambda host, port: True)
    launcher.configure(tmp_path, 8799)
    assert launcher.os.environ["VTX_ENFORCE_RELEASE"] == "0"
    assert launcher.os.environ["VTX_DATA_ROOT"] == str(tmp_path.resolve())


def test_check_does_not_start_server(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(launcher, "port_available", lambda host, port: True)
    assert launcher.main(["--port", "8799", "--data-root", str(tmp_path), "--check"]) == 0
    assert "no flight started" in capsys.readouterr().out
