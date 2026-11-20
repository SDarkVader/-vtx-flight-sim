"""Capture an offline world survey and a repeatable road roll with the stock A10-C."""
import argparse
import gzip
import hashlib
import json
import os
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import time

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def dump(destination, data):
    destination.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def version(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--world', default='airport')
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(exist_ok=True, parents=True)
    os.environ['VTX_DATA_ROOT'] = str(directory / 'isolated-data')
    from vtx import live_server as server
    from vtx.frontend_identity import server_frontend_manifest
    from vtx.phantom.plant import PhantomAircraft, DT
    from vtx.world import ENVIRONMENTS, make_world

    world = make_world(args.world)
    public = world.public()
    public['displayed_world_sha256'] = server.world_fingerprint(world)
    raw = json.dumps(public, separators=(',', ':'), allow_nan=False).encode()
    (directory / 'world.json.gz').write_bytes(gzip.compress(raw, compresslevel=4, mtime=0))
    historical = {}
    for key in ('airport', 'sandbox', 'r6-valley-20261103'):
        historical[key] = server.world_fingerprint(make_world(key))
    clocks = []
    for _ in range(5):
        start = time.perf_counter()
        make_world(args.world)
        clocks.append((time.perf_counter() - start) * 1000)
    start = time.perf_counter()
    aircraft = PhantomAircraft(world, 'phantom-a10c', start_configuration='road')
    compile_ms = (time.perf_counter() - start) * 1000
    aircraft.spawn(-3885, 0, world.terrain_z(-3885, 0))
    aircraft.set_command(dict(brake=[0.] * 4, wheel_drive=[0.75] * 4))
    samples, step_ms = [], []
    for _ in range(8):
        start = time.perf_counter()
        for _ in range(round(1 / DT)):
            aircraft.step()
        step_ms.append((time.perf_counter() - start) * 1000)
        samples.append(dict(t=aircraft.data.time, position=aircraft.data.qpos[:3].tolist(),
                            tyre_support=aircraft.support_count(), crashed=bool(aircraft.crashed)))
    zmin = float(world.heights.min())
    manifest = server_frontend_manifest()
    dump(directory / 'frontend.json', manifest)
    dump(directory / 'survey.json', dict(
        commit=version('rev-parse', 'HEAD'), source_tree=version('rev-parse', 'HEAD^{tree}'),
        runtime=server.RUNTIME_SOURCE_SHA256, python=sys.version, mujoco=mujoco.__version__,
        numpy=np.__version__, platform=platform.platform(), environments=list(ENVIRONMENTS),
        world={k: public[k] for k in ('environment','id','version','seed','label','half_m','runway','approach_corridor')},
        identity=server.environment_identity(world, world, aircraft), historical_worlds=historical,
        terrain=dict(samples=world.n, step_m=2*world.half/(world.n-1), min_m=zmin,
                     max_m=float(world.heights.max()), obstacles=len(world.obstacles),
                     water=world.water), public_json_bytes=len(raw), gzip_bytes=(directory/'world.json.gz').stat().st_size,
        aircraft=dict(variant=aircraft.variant, config=aircraft.P.config_sha256,
                      xml=aircraft.provenance['model_xml_sha256'], visual=aircraft.provenance['render_asset'],
                      state_sha256=sha(aircraft.data.qpos.tobytes()+aircraft.data.qvel.tobytes())),
        performance=dict(world_build_ms=clocks, aircraft_compile_ms=compile_ms,
                         wall_ms_per_sim_second=step_ms, median_ms=statistics.median(step_ms)),
        road_roll=samples))
    print(args.world, public['displayed_world_sha256'], world.heights.shape, samples[-1], flush=True)


if __name__ == '__main__':
    main()
