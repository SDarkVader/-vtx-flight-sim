"""One definition of the Argon R6 that flew the 3 November A-to-B sortie (run 20261103T125202-92636c).

Model, physics and display are pinned together here so that every R6 the game
shows or flies resolves to the same bytes:

  physics  airframe_variant 'r6-argon-20261103' in world 'r6-valley-20261103',
           MuJoCo model.xml sha256 d5b83de4… (byte-identical to the flight record)
  ledger   inputs/airframe_ledger_r6.json sha256 787b032b…
  display  public/assets/airframe-r6.glb sha256 d001ae20… (20 body containers
           at the MuJoCo body frames; connected transmission and landing gear)

`python tools/visual_r6/r6_unified.py` prints the identity report and exits
non-zero if any pin is broken. It builds the model in memory and writes nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RUN_ID = '20261103T125202-92636c'
FLIGHT_COMMIT = '0684b1a1e860d246955db856d233f8c0a2b32941'
VARIANT = 'r6-argon-20261103'
REQUEST = dict(gear_variant='critical-damping-proposal', rpm=1200.0, fuel_kg=10.0,
               engine_power_limit_kw=300.0, atmosphere_model='constant', wind_world_mps=(0.0, 0.0, 0.0))
MODEL_XML_SHA256 = 'd5b83de425ad8da24e128faafaff399dd3e457474a2dabb7bbf4165c56220d16'
LEDGER_SHA256 = '787b032b82c724984a88df596e81708687a5ae5f4d23396113e88fc1a162ab3e'
DISPLAY_ASSET = '/assets/airframe-r6.glb'
DISPLAY_SHA256 = 'd001ae20ba7665cbdbb8e910e4006df07bc855cbcf85c58211ff81e04ac82034'
# Superseded R6 display: P0-V4 geometry whose drive spindles stop ~0.45 m short of the
# rotor hubs and whose landing legs stop short of their pads. Never shown as R6.
RETIRED_DISPLAY_SHA256 = {
    '7325d0b303398c4ec0e9ece398cdcf63176db2555205b06c4d32a74a095c1489': 'airframe-r6-blendstra-rig.glb',
    '58ff9950622f7a3fce63aa3c1e9fc50cefe717e42506fb5bebfd25dea06a727c': 'r6-blendstra-reference.glb',
}
BODY_CONTAINERS = ('airframe', 'cabin', *(f'gear{i}' for i in range(1, 7)),
                   *(f'{k}{i}' for k in ('nacelle', 'rotor', 'shaft') for i in range(1, 5)))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def glb_json(path: Path) -> dict:
    blob = path.read_bytes()
    length, kind = struct.unpack_from('<II', blob, 12)
    if blob[:4] != b'glTF' or kind != 0x4E4F534A:
        raise ValueError(f'{path} is not a binary glTF')
    return json.loads(blob[20:20 + length])


def build_aircraft():
    sys.path.insert(0, str(ROOT / 'src'))
    from vtx.aircraft import Aircraft
    from vtx.r6_historical_valley import R6HistoricalValley
    return Aircraft(R6HistoricalValley(), airframe_variant=VARIANT, **REQUEST)


def registry_r6() -> dict:
    text = (ROOT / 'public/vtx-env/vehicle-registry.js').read_text(encoding='utf-8')
    line = next(l for l in text.splitlines() if re.match(r"\s*'r6'\s*:", l))
    asset = re.search(r"asset:'([^']+)'", line).group(1)
    digest = re.search(r"sha256:'([0-9a-f]{64})'", line).group(1)
    return dict(asset=asset.split('?')[0], sha256=digest, line=line.strip())


def container_frames(glb: dict) -> dict:
    """Root body containers in simulator (Z-up) coordinates: translation and quaternion w,x,y,z."""
    out = {}
    for i in glb['scenes'][glb.get('scene', 0)]['nodes']:
        n = glb['nodes'][i]
        x, y, z, w = n.get('rotation', [0, 0, 0, 1])
        out[n['name']] = dict(pos=list(n.get('translation', [0, 0, 0])), quat=[w, x, y, z])
    return out


def report() -> dict:
    import mujoco as mj
    import numpy as np
    ac = build_aircraft()
    xml_sha = hashlib.sha256(ac.xml.encode()).hexdigest()
    display = ROOT / 'public' / DISPLAY_ASSET.lstrip('/')
    reg = registry_r6()
    frames = container_frames(glb_json(display))
    mj.mj_forward(ac.model, ac.data)
    root = mj.mj_name2id(ac.model, mj.mjtObj.mjOBJ_BODY, 'airframe')
    ra, pa = ac.data.xmat[root].reshape(3, 3), ac.data.xpos[root]
    qa_conj = np.array(ac.data.xquat[root]) * [1, -1, -1, -1]
    worst_m, worst_deg, missing = 0.0, 0.0, []
    for name in BODY_CONTAINERS:
        bid = mj.mj_name2id(ac.model, mj.mjtObj.mjOBJ_BODY, name)
        if bid < 0 or name not in frames:
            missing.append(name)
            continue
        # Body frame relative to the airframe root at rest; the GLB stores it the same way.
        p0 = ra.T @ (ac.data.xpos[bid] - pa)
        q0 = np.zeros(4)
        mj.mju_mulQuat(q0, qa_conj, ac.data.xquat[bid])
        worst_m = max(worst_m, float(np.max(np.abs(np.asarray(frames[name]['pos']) - p0))))
        dot = abs(float(np.dot(frames[name]['quat'], q0)))
        worst_deg = max(worst_deg, float(np.degrees(2 * np.arccos(min(1.0, dot)))))
    checks = {
        'physics_model_identical_to_flight': xml_sha == MODEL_XML_SHA256,
        'ledger_identical_to_flight': ac.provenance['ledger_sha256'] == LEDGER_SHA256,
        'physics_names_display_asset': ac.provenance['render_asset'] == DISPLAY_ASSET,
        'display_asset_bytes_pinned': sha256(display) == DISPLAY_SHA256,
        'registry_r6_uses_display_asset': reg['asset'] == DISPLAY_ASSET and reg['sha256'] == DISPLAY_SHA256,
        'registry_r6_not_retired_visual': reg['sha256'] not in RETIRED_DISPLAY_SHA256,
        'display_has_all_20_bodies': not missing,
        'display_pivots_match_physics': worst_m < 1e-4 and worst_deg < 1e-3,
    }
    return dict(run_id=RUN_ID, flight_commit=FLIGHT_COMMIT, variant=VARIANT,
                model_xml_sha256=xml_sha, display_asset=DISPLAY_ASSET, display_sha256=sha256(display),
                registry_r6=reg, pivot_worst_offset_m=worst_m, pivot_worst_rotation_deg=worst_deg,
                missing_bodies=missing, checks=checks, ok=all(checks.values()))


if __name__ == '__main__':
    r = report()
    print(json.dumps(r, indent=1))
    sys.exit(0 if r['ok'] else 1)
