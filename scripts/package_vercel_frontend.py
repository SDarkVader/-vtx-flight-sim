"""Pack the CDN source bytes that the Vercel function needs to verify a flight."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def package_frontend(public: Path, target: Path) -> None:
    public = public.resolve()
    files = sorted((p for p in public.rglob("*") if p.is_file()),
                   key=lambda p: p.relative_to(public).as_posix())
    if not files:
        raise ValueError(f"No frontend files in {public}")
    with TemporaryDirectory(dir=target.parent) as temp:
        output = Path(temp) / target.name
        with ZipFile(output, "w") as archive:
            for source in files:
                if not source.resolve().is_relative_to(public):
                    raise ValueError(f"Frontend file escapes {public}: {source}")
                # Fixed entry timestamps keep identical builds byte-for-byte reproducible.
                entry = ZipInfo(source.relative_to(public).as_posix())
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, source.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=6)
        output.replace(target)
    print(f"Packaged {len(files)} frontend files in {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    package_frontend(root / "public", root / "inputs/vercel_frontend.zip")
