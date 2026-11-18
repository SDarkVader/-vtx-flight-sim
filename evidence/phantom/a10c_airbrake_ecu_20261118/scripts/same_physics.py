"""Previous-model check: fly the A10-C without the ECU, and its pinned flown revision, on a given source tree and
print exact state digests (qpos, qvel, actuator state, fuel, random-generator state, buffer charge).
Run it on this tree and on the previous runtime, exported for example with
    git archive ac9f1e72b5a5fc9830dd13554885bc48537400a1 src inputs evidence/phantom evidence/source | tar -x -C <dir>
    python -I evidence/phantom/a10c_airbrake_ecu_20261118/scripts/same_physics.py <dir>
    python -I evidence/phantom/a10c_airbrake_ecu_20261118/scripts/same_physics.py .
Identical digests mean identical physics. The airborne case uses this tree's test harness set-up (public plant API only)."""
import sys, hashlib, json
from pathlib import Path

root = Path(sys.argv[1]).resolve()
HERE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'src'))
import numpy as np   # noqa: E402
from vtx.world import TestWorld   # noqa: E402
from vtx.phantom.plant import PhantomAircraft   # noqa: E402


def runtime_sha256(src_vtx):
    """The reviewed-runtime identity of the tree flown (same hashing as vtx.live_server.runtime_source_sha256)."""
    h = hashlib.sha256()
    for path in sorted(src_vtx.rglob('*.py'), key=lambda p: p.relative_to(src_vtx).as_posix()):
        rel = path.relative_to(src_vtx).as_posix().encode('utf-8'); contents = path.read_bytes()
        h.update(len(rel).to_bytes(4, 'big')); h.update(rel); h.update(len(contents).to_bytes(8, 'big')); h.update(contents)
    return h.hexdigest()


def digest(a):
    h = hashlib.sha256()
    for arr in (a.data.qpos, a.data.qvel, a.data.act if a.data.act.size else np.zeros(0), np.asarray(a.fuel)):
        h.update(np.ascontiguousarray(arr, dtype=np.float64).tobytes())
    h.update(json.dumps(a.rng.bit_generator.state, sort_keys=True, default=str).encode())
    h.update(repr(float(a.bus.soc)).encode())
    return h.hexdigest()[:16]


out = {}
w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10c', start_configuration='vtol'); a.spawn(0, 0, w.surface_z(0, 0))
a.set_command(dict(stability_mode='attitude', collective=0.83))
for _ in range(2000): a.step()
a.set_command(dict(pitch=0.2, roll=0.3, yaw=0.2))
for _ in range(2000): a.step()
a.set_command(dict(stability_mode='attitude_vs', vertical_speed_m_s=0.0, collective=0.5, pitch=0.0, roll=0.0, yaw=0.0))
for _ in range(2000): a.step()
out['S1_vtol'] = (digest(a), round(float(a.data.qpos[2]), 6), a.events[-1].get('event') if a.events else None)

w = TestWorld(); a = PhantomAircraft(w, 'phantom-a10c-runway-20261112', start_configuration='road'); a.spawn(0, 0, w.surface_z(0, 0))
a.set_command(dict(wing='deploy', canard_fold='deployed', brake=[1.0] * 4))
for _ in range(3600): a.step()
a.set_command(dict(brake=[0.0] * 4, booster_throttle=[0.8, 0.8], stability_mode='rate_damping'))
for _ in range(4000): a.step()
out['S2_runway_rev'] = (digest(a), round(float(a.data.qvel[0]), 6), a.wing_state)

sys.path.insert(1, str(HERE / 'tools/phantom'))
import a10c_airbrake_test as T   # noqa: E402
a = T.build('off', 'reference')
a.set_command(dict(pod_tilt_deg=[90.] * 4, booster_throttle=[0., 0.], stability_mode='attitude_vs', vertical_speed_m_s=0.0, collective=0.5, pitch=0.0))
for _ in range(3200): a.step()
out['S3_airbrake_manual'] = (digest(a), round(float(a.data.qvel[0]), 6), round(float(a.data.qpos[2]), 6))
out['config'] = PhantomAircraft(TestWorld(), 'phantom-a10c').P.config_sha256[:16]
out['runtime_sha256'] = runtime_sha256(root / 'src' / 'vtx')
out['source'] = root.name
print(json.dumps(out))
