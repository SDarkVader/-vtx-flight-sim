"""Build a compact VTX flight catalogue from retained, local evidence.

Run from any directory: python flight_index_builder.py REPOSITORY_PATH
The source logs remain in place. This writes compact docs in the supplied
worktree and an absolute-path archive manifest in the PC backup.
"""
from __future__ import annotations

import hashlib
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

RUN = re.compile(r"^20\d{6}T\d{6}-[0-9a-f]{6}$")
LOCAL = Path(os.environ.get("VTX_OLD_CHECKOUT", Path.home() / "Documents" / "Github" / "-vtx-flight-sim"))
BACKUP = Path(os.environ.get("VTX_FLIGHT_BACKUP", Path.home() / "Documents" / "VTX-flight-logs-backup"))
LIVE = Path(os.environ.get("VTX_R6_ARCHIVE", Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "VTX" / "r6-live" / "evidence" / "flights"))
REMOTE_BRANCH = "work/a10-airport-cockpit"
MOBILE_ROOT = "evidence/phantom/mobile_flights_20261104"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def git_json(repo: Path, ref: str, path: str):
    data = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"],
                          capture_output=True, check=True).stdout
    return json.loads(data)


def retain_mobile_logs(repo: Path):
    """Keep the exact two mobile Sandbox logs on this PC and verify their hashes."""
    for run in ("20261104T022405-070aa5", "20261104T023710-072007"):
        target = BACKUP / run
        target.mkdir(parents=True, exist_ok=True)
        for name in ("summary.json", "key-events.jsonl", "events.jsonl.gz"):
            path = f"{MOBILE_ROOT}/{run}/{name}"
            data = subprocess.run(["git", "-C", str(repo), "show",
                                   f"origin/{REMOTE_BRANCH}:{path}"],
                                  capture_output=True, check=True).stdout
            dest = target / name
            if not dest.exists() or dest.read_bytes() != data:
                dest.write_bytes(data)
        summary = read_json(target / "summary.json")
        with gzip.open(target / "events.jsonl.gz", "rb") as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != summary["raw_events_sha256"]:
            raise RuntimeError(f"Mobile log failed SHA-256 check: {run}")


def retain_missing_local_records(repo: Path):
    """Fill archive gaps without overwriting any existing backup file."""
    roots = (LOCAL / "evidence" / "flights",
             repo / "evidence" / "phantom" / "flight_campaign_20261103" / "evidence" / "flights",
             repo / "pilot" / "flight_records")
    for root in roots:
        for source in root.iterdir():
            if not source.is_dir() or not RUN.match(source.name):
                continue
            dest = BACKUP / source.name
            dest.mkdir(parents=True, exist_ok=True)
            for file in source.iterdir():
                if file.is_file() and not (dest / file.name).exists():
                    shutil.copy2(file, dest / file.name)


def write_bench_index(repo: Path):
    base = repo / "evidence" / "phantom"
    takeoff = read_json(base / "a10_takeoff_series_20261104.json") or []
    proposals = read_json(base / "a10_p6_p7_p8_series_20261104.json") or []
    lines = ["# Phantom A10 plant bench runs", "",
             "These are flat-strip MuJoCo plant test cases with canned pilot schedules, distinct from timestamped live cockpit sorties. Full source data remains in the local repository checkout. None establishes a controlled landing or aircraft qualification.", "",
             "## Baseline take-off series", "",
             "| Run | Technique | Wheels off (m/s) | Max height (m) | Crash flag |",
             "| --- | --- | ---: | ---: | --- |"]
    for r in takeoff:
        wheels = r.get("wheels_off")
        speed = wheels[1] if isinstance(wheels, list) and len(wheels) > 1 else None
        lines.append(f"| `{r['run']}` | {r.get('technique','—')} | {fmt(speed)} | {fmt(r.get('max_height_m'))} | {fmt(r.get('crashed'))} |")
    lines += ["", "[Full baseline series](../evidence/phantom/a10_takeoff_series_20261104.json).", "",
              "## P6/P7/P8 and control-gain series", "",
              "| Run | Configuration | Wheels off (m/s) | Max height (m) | Crash flag |",
              "| --- | --- | ---: | ---: | --- |"]
    for r in proposals:
        lines.append(f"| `{r['run']}` | {r.get('config','—')} | {fmt(r.get('first_wheels_off_u_m_s'))} | {fmt(r.get('max_height_m'))} | {fmt(r.get('crashed'))} |")
    lines += ["", "[Full proposal series](../evidence/phantom/a10_p6_p7_p8_series_20261104.json). A `crashed: false` flag does not mean a successful flight; some runs bounced or reached the end of the strip. See the [analysis](phantom/A10_FIRST_FLIGHTS_20261104.md).", ""]
    (repo / "docs" / "FLIGHT_BENCH_INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(takeoff) + len(proposals)} A10 plant bench cases")


def fmt(value, digits=2):
    return "—" if value is None else str(value).lower() if isinstance(value, bool) else str(value) if isinstance(value, int) else f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def xy(value):
    if isinstance(value, list) and len(value) >= 2:
        return f"({fmt(value[0], 1)}, {fmt(value[1], 1)}) m"
    return "—"


def model(meta, summary, source):
    air = meta.get("airframe") or {}
    request = meta.get("request") or {}
    variant = (air.get("airframe_variant") or request.get("airframe_variant")
               or summary.get("variant") or (summary.get("final") or {}).get("variant"))
    cassette = air.get("wing_cassette_revision")
    if summary.get("source") == "retained Vercel Sandbox vtx-flight-lab snapshot":
        return "Phantom FX-A A10", "A10", variant or "phantom-fx"
    if "flight_campaign_20261103" in source:
        cassette = cassette or "A9"
    if variant in {"phantom", "phantom-fx"}:
        return f"Phantom {'FX-A' if variant == 'phantom-fx' else 'as drawn'} {cassette or 'revision unknown'}", cassette or "unknown", variant
    revision = air.get("revision") or ""
    if "r6" in revision.lower() or variant in {"r6", "r6_variator"}:
        return "P0-V4A R6", "—", variant or "r6"
    if "r5" in revision.lower() or variant == "light":
        return "P0-V4A R5", "—", variant or "light"
    if "r4" in revision.lower() or variant == "baseline":
        return "P0-V4A R4", "—", variant or "baseline"
    return revision or variant or "Unverified model", cassette or "—", variant or "—"


def main(repo: Path):
    retain_mobile_logs(repo)
    retain_missing_local_records(repo)
    candidates = defaultdict(list)
    roots = [
        (repo / "evidence" / "flights", "GitHub main / R4–R5"),
        (repo / "evidence" / "phantom" / "flight_campaign_20261103" / "evidence" / "flights", "GitHub main / 3 Nov Phantom campaign"),
        (repo / "pilot" / "flight_records", "GitHub main / R6 pilot record"),
        (LOCAL / "evidence" / "flights", "PC checkout / historic flights"),
        (BACKUP, "PC flight-log backup"),
        (LIVE, "PC live data root"),
    ]
    for root, label in roots:
        if not root.exists():
            continue
        for directory in root.iterdir():
            if directory.is_dir() and RUN.match(directory.name):
                candidates[directory.name].append((directory, label))
    for run in ("20261104T022405-070aa5", "20261104T023710-072007"):
        candidates[run].append((None, f"mobile branch / {REMOTE_BRANCH}"))

    docs = repo / "docs" / "flights"
    docs.mkdir(parents=True, exist_ok=True)
    rows = []
    local_manifest = {}
    for run in sorted(candidates):
        locations = candidates[run]
        selected = None
        all_hashes = set()
        raw = []
        for directory, label in locations:
            if directory is None:
                path = f"{MOBILE_ROOT}/{run}/summary.json"
                summary = git_json(repo, f"origin/{REMOTE_BRANCH}", path)
                meta = {}
                key = f"GitHub branch `{REMOTE_BRANCH}`: `{path}`"
                sha = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()
            else:
                summary = read_json(directory / "summary.json")
                meta = read_json(directory / "metadata.json") or {}
                key = f"{label}: `{directory}`"
                sha = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest() if summary else None
                raw += [str(f) for f in directory.iterdir() if f.is_file() and f.name.startswith("events.jsonl")]
                raw += [str(f) for f in directory.iterdir() if f.is_file() and "observations.jsonl" in f.name]
            if sha:
                all_hashes.add(sha)
            # Prefer an actual completed summary. The PC live root can supersede
            # an otherwise equivalent repository copy for source lookup.
            if summary and (selected is None or not selected[0]):
                selected = (summary, meta, key, directory)
            elif summary and selected and label == "PC live data root":
                selected = (summary, meta, key, directory)
            elif selected is None and meta:
                selected = (summary, meta, key, directory)

        if selected:
            summary, meta, key, directory = selected
            summary = summary or {}
        else:
            summary, meta, key, directory = {}, {}, locations[0][1], locations[0][0]
        mission = meta.get("mission") or summary.get("mission") or {}
        req = meta.get("request") or {}
        model_name, cassette, variant = model(meta, summary, key)
        outcome = summary.get("outcome") or summary.get("formal_server_outcome") or "No formal summary"
        reason = summary.get("reason") or summary.get("formal_server_reason") or "No outcome reason recorded."
        seconds = summary.get("simulated_seconds")
        if seconds is None:
            seconds = (summary.get("last_observation") or {}).get("t_s")
        max_alt = summary.get("max_barometric_altitude_m", summary.get("max_airframe_origin_altitude_m"))
        if run == "20261103T125202-92636c":
            # This result is explained in the pilot's detailed observed log.
            max_alt = "10.207 m radar clearance (sampled)"
        src_lines = [f"- {label}: run folder `{run}`" if directory else f"- {label}: `{MOBILE_ROOT}/{run}/summary.json`" for directory, label in locations]
        if key.startswith("GitHub main") and summary:
            rel = Path(directory).relative_to(repo).as_posix()
            src_lines.insert(0, f"- [Repository summary](../../{rel}/summary.json)")
        if run.startswith("20261104T02"):
            src_lines.insert(0, f"- [Branch summary](https://github.com/SDarkVader/-vtx-flight-sim/blob/{REMOTE_BRANCH}/{MOBILE_ROOT}/{run}/summary.json)")
        if len(all_hashes) > 1:
            src_lines.append(f"- **Conflict:** {len(all_hashes)} distinct summary contents found for this run ID; inspect copies before treating them as identical.")
        if not raw:
            raw_note = "Raw event log was not found in the scanned PC sources."
        else:
            preferred = sorted(set(raw), key=lambda p: (not p.startswith(str(BACKUP)), not p.startswith(str(LIVE)), p))[0]
            relative = f"VTX-flight-logs-backup/{run}/{Path(preferred).name}" if preferred.startswith(str(BACKUP)) else f"AppData/Local/VTX/r6-live/evidence/flights/{run}/{Path(preferred).name}" if preferred.startswith(str(LIVE)) else f"PC checkout/evidence/flights/{run}/{Path(preferred).name}"
            raw_note = f"Local full log: `{relative}`. This index does not upload raw events; earlier GitHub branches may already contain copies."
        local_manifest[run] = {
            "model": model_name, "outcome": outcome,
            "source_folders": [str(d) for d, _ in locations if d],
            "raw_event_files": sorted(set(raw)),
            "summary_sha256_variants": sorted(all_hashes),
        }
        lines = [
            f"# Flight {run}", "", f"- **Model:** {model_name}",
            f"- **Variant:** `{variant}`; wing cassette: {cassette}",
            f"- **Outcome:** {outcome}", f"- **Simulated time:** {fmt(seconds)} s",
            f"- **Maximum recorded altitude:** {fmt(max_alt)}{' m' if isinstance(max_alt, (int,float)) else ''}",
            f"- **Fuel used:** {fmt(summary.get('fuel_used_kg'))}{' kg' if summary.get('fuel_used_kg') is not None else ''}",
            f"- **Pilot decisions:** {fmt(summary.get('decisions') if summary.get('decisions') is not None else ', '.join(f'{k}: {v}' for k, v in (summary.get('pilot_decisions') or {}).items()) or None)}",
            "", "## Flight", "",
            f"Mission: {mission.get('label') or req.get('label') or 'No mission label recorded.'} Departure {xy(mission.get('departure'))}; destination {xy(mission.get('destination'))}.",
            "", f"Recorded result: {reason}", "",
            f"Left ground: {fmt(summary.get('left_ground'))}. Maximum recorded contact force: {fmt(summary.get('max_contact_force_n'))} N.",
            "", "## Evidence", "", *src_lines, "", raw_note, "",
        ]
        if summary.get("touchdowns"):
            lines += ["Touchdown sink rates (m/s): " + ", ".join(fmt(t.get("sink_rate_m_s")) for t in summary["touchdowns"]) + ".", ""]
        if summary.get("collisions"):
            lines += ["Recorded impact forces (N): " + ", ".join(fmt(c.get("force_n")) for c in summary["collisions"]) + ".", ""]
        if run == "20261104T023710-072007":
            lines += ["The retained events include a 33.73 m/s touchdown sink rate and an impact. No formal server outcome was saved before Sandbox expiry; this is not a controlled landing.", ""]
        if run == "20261103T125202-92636c":
            lines += ["[Detailed pilot narrative](../../pilot/flight_records/20261103T125202-92636c/PILOT_RECORD.md). The observed six-gear touchdown was 2.58 m from B; the formal landing criterion was not met.", ""]
        if run == "20261103T164155-6cf6cf" and not summary:
            lines += ["**Snapshot status:** active and paused when indexed on 4 November 2026. The summary is absent; do not infer a completed flight.", ""]
        (docs / f"{run}.md").write_text("\n".join(lines), encoding="utf-8")
        rows.append((run, model_name, outcome, fmt(seconds), f"[record](flights/{run}.md)"))

    groups = defaultdict(list)
    for row in rows:
        groups[row[1]].append(row)
    head = ["# VTX flight records", "", "Verified sources: PC flight-log backup, active PC data root, GitHub `main`, the A10 mobile branch, and the 3 November Phantom campaign. One row is one run ID; duplicate copies are listed in the individual record. A local full telemetry archive remains on the PC; this index adds only compact summaries online. A summary is evidence of a simulator run, not validation of a physical aircraft.", "", f"**{len(rows)} distinct timestamped run IDs** found. [A10 plant bench runs](FLIGHT_BENCH_INDEX.md) are indexed separately because they have no live flight run ID.", ""]
    for group, entries in sorted(groups.items()):
        head += [f"## {group}", "", "| Run | Outcome | Sim time (s) | Record |", "| --- | --- | ---: | --- |"]
        head += [f"| `{a}` | {c} | {d} | {e} |" for a, _, c, d, e in entries]
        head.append("")
    head += ["## Scope and version notes", "", "- The 3 November Phantom campaign used the A9 cassette even when the historic variant key was `phantom` or `phantom-fx`. The later A10 keys reused those names. The cassette revision in each run's metadata controls the label here.", "- The two 4 November mobile sorties are from the retained Vercel Sandbox and the `work/a10-airport-cockpit` branch. Their full compressed event logs are in the local PC archive and remain on that branch; no new raw logs are published by this index.", "- Google Drive run folders found in the 4 November 2026 search were historical mirrors through 3 November. No additional 4 November run folder was found there; contents were not byte-compared.", "- Blendstra's `VTX-A A10`, `A10 Phantom`, and `VTX Phantom A10 — Cassette model` are separate 3D assets, not flight records.", "- A10 flat-strip plant tests are synthetic bench trials and have separate identifiers. See [A10 plant bench index](FLIGHT_BENCH_INDEX.md).", ""]
    (repo / "docs" / "FLIGHT_INDEX.md").write_text("\n".join(head), encoding="utf-8")
    (BACKUP / "flight-archive-manifest.json").write_text(json.dumps(local_manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} timestamped flight records")
    write_bench_index(repo)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
