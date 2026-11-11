"""Mid-air checkpoint recovery contracts; never touches the live server."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pytest

from vtx.live_server import Laboratory, Mission, normalize_saved_mission_request


def test_midair_restart_preserves_physics_and_requires_manual_resume():
    with TemporaryDirectory() as folder:
        root=Path(folder)
        with patch("vtx.live_server.ROOT",root):
            lab=Laboratory()
            lab.start(Mission(departure=[13.7,-28.4],destination=[-45,18],
                              authority="colin",fuel_kg=20))
            p=lab.aircraft
            p.data.qpos[:3]=[13.7,-28.4,42.]
            p.data.qvel[:3]=[3.,-2.,5.]
            p.data.time=7.5
            p.engine_spool=.6
            p.fuel[:]=[4.9]*4
            p.pitch[:]=[6.,7.,8.,9.]
            p.governor.integral_nm=17.
            p.step_count=123
            lab.left_ground=True
            lab.checkpoint(force=True)
            run_id=lab.run_id
            lab.audit_file.close()
            lab.audit_file=None

            restored=Laboratory()
            assert restored.active
            assert restored.paused
            assert restored.run_id==run_id
            assert restored.authority=="colin"
            assert restored.left_ground
            assert restored.aircraft.data.time==pytest.approx(7.5)
            np.testing.assert_allclose(restored.aircraft.data.qpos[:3],[13.7,-28.4,42.])
            np.testing.assert_allclose(restored.aircraft.data.qvel[:3],[3.,-2.,5.])
            np.testing.assert_allclose(restored.aircraft.pitch,[6.,7.,8.,9.])
            assert restored.aircraft.engine_spool==pytest.approx(.6)
            assert restored.aircraft.governor.integral_nm==pytest.approx(17.)
            assert not (root/"evidence/flights"/run_id/"summary.json").exists()
            restored.stop("test completed")
            assert not (root/"pilot/live-flight-checkpoint.json").exists()


def test_explicit_stop_disables_recovery():
    with TemporaryDirectory() as folder:
        root=Path(folder)
        with patch("vtx.live_server.ROOT",root):
            lab=Laboratory()
            lab.start(Mission(departure=[13.7,-28.4],destination=[-45,18]))
            lab.stop("operator stopped")
            recovered=Laboratory()
            assert not recovered.active
