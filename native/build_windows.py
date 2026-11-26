"""Export the native Windows prototype and stage its verified offline runtime."""

import argparse
from hashlib import file_digest, sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native"
BASE = "274d125e00fe47d859a54c63472fb40890978e5b"
RUNTIME_SHA256 = "bed80ec18f8c30fedf7723b05db37ca726e692d6fd8e9d7f75a46fd5e9cdaac5"
MODEL_SHA256 = "45364301f2950ca57e5b34ac73d29b0abe11471dd82f0fe0e5068da70418a93e"
GAME_PATHS = (
    "public", "inputs", "assets", "src/vtx", "docs/phantom", "evidence/source",
    "LICENSE", "VERSION.txt", "experiments/ricochet/rc01_f03/model/RC01_F03_cad_stations.npz",
    "pilot/flight_records/20261103T125202-92636c/PILOT_RECORD.md",
    *("evidence/phantom/" + name for name in (
        "a10_handover.json", "a10_mujoco_fragment.xml", "a10b_characteristics.json",
        "a9_handover.json", "a9_mujoco_fragment.xml", "hull_lift_vlm.json",
        "phantom_geometry.json", "wing_loads_results.json",
    )),
)


def file_sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def run(*args, **options):
    return subprocess.run(args, cwd=ROOT, check=True, **options)


def source_hash(directory):
    digest = sha256()
    for path in sorted(directory.rglob("*.py"), key=lambda p: p.relative_to(directory).as_posix()):
        name = path.relative_to(directory).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def stage_game(output):
    # Use the reviewed Windows checkout bytes. Git archive can normalize the
    # line endings that the simulator includes in its runtime identity.
    run("git", "diff", "--quiet", BASE, "--", *GAME_PATHS)
    tracked = run("git", "ls-tree", "-rz", "--name-only", BASE, "--", *GAME_PATHS, capture_output=True)
    game = output / "game"
    for name in tracked.stdout.decode("utf-8").split("\0"):
        if not name:
            continue
        source = ROOT / name
        if source.is_symlink():
            raise ValueError(f"Unexpected symlink in portable package: {name}")
        target = game / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (game / "BUILD_COMMIT").write_text(BASE + "\n", encoding="ascii")
    shutil.copy2(SOURCE / "runtime" / "launch_backend.py", game / "launch_backend.py")
    if source_hash(game / "src" / "vtx") != RUNTIME_SHA256:
        raise ValueError("Packaged source bytes do not match the verified Windows runtime.")
    for glb in (game / "public" / "assets" / "phantom-a10b-visual.glb",
                SOURCE / "flight" / "phantom-a10b-visual.glb"):
        if file_sha(glb) != MODEL_SHA256:
            raise ValueError(f"Aircraft GLB does not match the reviewed Phantom visual: {glb}")


def stage_runtime(output, original):
    run("git", "diff", "--quiet", "8266b5cc", BASE, "--", "packaging/windows/runtime-win-x64.txt")
    built = output / "runtime"
    shutil.copytree(original, built, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    probe = run(str(built / "python.exe"), "-B", "-c",
                "import fastapi, mujoco, struct, sys, uvicorn; "
                "assert struct.calcsize('P') == 8; "
                "assert sys.version_info[:3] == (3, 14, 3); "
                "assert mujoco.__version__ == '3.17.0'; "
                "print(f'{sys.version.split()[0]}, MuJoCo {mujoco.__version__}, FastAPI {fastapi.__version__}, Uvicorn {uvicorn.__version__}')",
                capture_output=True, text=True)
    return probe.stdout.strip()


def export_project(temp, output, godot, template):
    project = temp / "export-project"
    shutil.copytree(SOURCE, project, ignore=shutil.ignore_patterns(".godot", "__pycache__"))
    path = project / "export_presets.cfg"
    preset = path.read_text(encoding="utf-8")
    setting = 'custom_template/release=""'
    if preset.count(setting) != 1:
        raise ValueError("The Windows release preset is missing.")
    engine_template = template.as_posix()
    if '"' in engine_template or "\n" in engine_template:
        raise ValueError("Unsupported export template path.")
    path.write_text(preset.replace(setting, f'custom_template/release="{engine_template}"'), encoding="utf-8")
    command = [str(godot), "--headless", "--path", str(project)]
    with (temp / "godot-import.log").open("wb") as log:
        run(*command, "--editor", "--import", stdout=log, stderr=subprocess.STDOUT)
    executable = output / "VTX Native Flight.exe"
    with (temp / "godot-export.log").open("wb") as log:
        run(*command, "--export-release", "Windows x64", str(executable), stdout=log, stderr=subprocess.STDOUT)
    if not executable.is_file():
        raise ValueError("The Godot export did not produce a Windows executable.")
    return executable


def make_zip(output, archive):
    with ZipFile(archive, "x", compression=ZIP_DEFLATED, compresslevel=3) as package:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                package.write(path, Path(output.name) / path.relative_to(output))
    (archive.parent / "SHA256SUMS.txt").write_text(f"{file_sha(archive)}  {archive.name}\n", encoding="utf-8")


def stage_benchmark(output, source):
    target = output / "benchmark-data"
    target.mkdir()
    fingerprints = {}
    for filename in ("world.json", "route.json", "provenance.json"):
        entry = target / filename
        shutil.copy2(source / filename, entry)
        fingerprints[filename] = file_sha(entry)
    shutil.copy2(SOURCE / "benchmark" / "Run Meridian Graphics Test.cmd", output)
    return fingerprints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New build workspace")
    parser.add_argument("--godot", type=Path, required=True, help="Godot 4.7.2 console executable")
    parser.add_argument("--template", type=Path, required=True, help="Matching verified Windows x64 release template")
    parser.add_argument("--runtime-from", type=Path, required=True, help="Verified preview runtime folder")
    parser.add_argument("--benchmark-data", type=Path, help="Verified Meridian world and replay data directory")
    parser.add_argument("--skip-zip", action="store_true", help="Stage an unpacked build for readiness checks.")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Build this prototype on Windows.")
    workspace = args.output.resolve()
    workspace.mkdir()
    output = workspace / ("VTX Meridian Graphics" if args.benchmark_data else "VTX Native Flight")
    output.mkdir()
    godot = args.godot.resolve(strict=True)
    template = args.template.resolve(strict=True)
    version = run(str(godot), "--version", capture_output=True, text=True).stdout.strip()
    if version != "4.7.2.stable.official.ed1daf0bf":
        parser.error("Expected the pinned Godot 4.7.2 stable editor.")
    executable = export_project(workspace, output, godot, template)
    stage_game(output)
    runtime_versions = stage_runtime(output, args.runtime_from.resolve(strict=True))
    for name in ("README.md", "GODOT-LICENSE.txt"):
        shutil.copy2(SOURCE / name, output / name)
    identity = {
        "type": "Local unsigned native Windows x64 G1 prototype",
        "physics_source": BASE, "physics_source_sha256": RUNTIME_SHA256,
        "godot": version, "python_runtime": runtime_versions,
        "windows_export_template_sha256": file_sha(template),
        "executable_sha256": file_sha(executable), "phantom_visual_sha256": MODEL_SHA256,
    }
    if args.benchmark_data:
        identity["meridian_benchmark_sha256"] = stage_benchmark(output, args.benchmark_data.resolve(strict=True))
    (output / "BUILD_MANIFEST.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    if not args.skip_zip:
        archive_name = "VTX-Meridian-Graphics-win-x64.zip" if args.benchmark_data else "VTX-Native-Flight-win-x64.zip"
        make_zip(output, workspace / archive_name)
    print(executable, flush=True)


if __name__ == "__main__":
    main()
