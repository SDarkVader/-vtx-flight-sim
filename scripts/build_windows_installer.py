"""Build the per-user Windows preview installer from an exact Git revision."""
from argparse import ArgumentParser
from hashlib import file_digest
from pathlib import Path
from subprocess import check_output, run
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "packaging" / "windows"
PYTHON_SHA256 = "ad4961a479dedbeb7c7d113253f8db1b1935586b73c27488712beec4f2c894e6"
GAME_PATHS = (
    "public", "inputs", "assets", "src/vtx", "scripts/launch_unified.py",
    "docs/phantom", "evidence/source", "LICENSE", "VERSION.txt",
    "experiments/ricochet/rc01_f03/model/RC01_F03_cad_stations.npz",
    "pilot/flight_records/20261103T125202-92636c/PILOT_RECORD.md",
    *("evidence/phantom/" + name for name in (
        "a10_handover.json", "a10_mujoco_fragment.xml", "a10b_characteristics.json",
        "a9_handover.json", "a9_mujoco_fragment.xml", "hull_lift_vlm.json",
        "phantom_geometry.json", "wing_loads_results.json",
    )),
)


def sha256(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def prepare_game(stage, workspace, revision):
    archive = workspace / "game-source.zip"
    run(["git", "archive", "--format=zip", f"--output={archive}", revision,
         "--", *GAME_PATHS], cwd=ROOT, check=True)
    game = stage / "game"
    with ZipFile(archive) as source:
        source.extractall(game)
    (game / "BUILD_COMMIT").write_text(revision + "\n", encoding="ascii")


def prepare_runtime(stage, archive):
    if sha256(archive) != PYTHON_SHA256:
        raise ValueError("Expected the verified CPython 3.14.3 Windows x64 embeddable archive")
    runtime = stage / "runtime"
    with ZipFile(archive) as source:
        source.extractall(runtime)
    (runtime / "python314._pth").write_text("python314.zip\n.\nLib/site-packages\n", encoding="ascii")
    run(["uv", "pip", "install", "--python", sys.executable, "--target",
         str(runtime / "Lib" / "site-packages"), "--only-binary", ":all:", "--require-hashes",
         "-r", str(WINDOWS / "runtime-win-x64.txt")], check=True)


def write_uninstall_manifest(stage, manifest):
    lines = []
    for file in sorted(stage.rglob("*")):
        if file.is_file():
            relative = str(file.relative_to(stage))
            if any(char in relative for char in ('$', '"', '\r', '\n')):
                raise ValueError(f"Unsupported packaged filename {relative!r}")
            lines.append(f'  Delete "$INSTDIR\\{relative}"')
    for directory in sorted((p for p in stage.rglob("*") if p.is_dir()),
                            key=lambda p: (-len(p.parts), p)):
        lines.append(f'  RMDir "$INSTDIR\\{directory.relative_to(stage)}"')
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check_runtime(stage, data):
    python = stage / "runtime" / "python.exe"
    game = stage / "game"
    run([str(python), "-B", str(game / "scripts" / "launch_unified.py"), "--desktop",
         "--port", "51876", "--initial-environment", "vaderland-33",
         "--data-root", str(data), "--check"], cwd=game, check=True)
    smoke = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0, str(Path.cwd() / 'src')); "
        "import fastapi, mujoco, scipy, uvicorn, websockets; "
        "from vtx.dashboard_site import app; from vtx.world import make_world; "
        "from vtx.ricochet.hull_geometry import load_f03_main_hull_mesh; "
        "world = make_world('vaderland-33'); "
        "assert world.id == 'vaderland-33' and world.harbour; "
        "load_f03_main_hull_mesh(); "
        "assert any(getattr(route, 'path', None) == '/ws' for route in app.routes); "
        "print('Bundled runtime, web cockpit and Vaderland 33 loaded')"
    )
    run([str(python), "-B", "-c", smoke], cwd=game, check=True)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True, help="Path to the NSIS makensis executable")
    parser.add_argument("--python-archive", type=Path, required=True, help="Verified embeddable CPython archive")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for the installer and staging")
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.version_info[:3] != (3, 14, 3) or sys.maxsize <= 2**32:
        parser.error("Build with CPython 3.14.3 on 64-bit Windows")
    revision = check_output(["git", "rev-parse", "--verify", f"{args.revision}^{{commit}}"],
                            cwd=ROOT, text=True).strip()
    workspace = args.output_dir.resolve()
    workspace.mkdir()
    stage = workspace / "stage"
    prepare_game(stage, workspace, revision)
    prepare_runtime(stage, args.python_archive.resolve())
    check_runtime(stage, workspace / "smoke-data")
    manifest = workspace / "uninstall-files.nsh"
    write_uninstall_manifest(stage, manifest)
    installer = workspace / f"VTX-Vaderland-33-{revision[:8]}-win-x64-Setup.exe"
    run([str(args.compiler.resolve()), "/V2", f"/DBUILD_ID={revision[:8]}",
         f"/DSTAGE_DIR={stage}", f"/DOUTPUT_FILE={installer}", f"/DUNINSTALL_FILES={manifest}",
         str(WINDOWS / "Vaderland.nsi")], check=True)
    (workspace / "installer.sha256").write_text(f"{sha256(installer)}  {installer.name}\n", encoding="ascii")
    print(installer)


if __name__ == "__main__":
    main()
