"""Read original Phantom flight records and write an isolated recovery inventory.

The output retains every applied command with its original patch and time. It
does not alter the archive or claim that a recorded pose is a reproducible flight.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re

FILES = ('metadata.json', 'aircraft_identity.json', 'model.xml',
         'phantom_parameters.json', 'phantom_ledger.json', 'events.jsonl',
         'phantom_steps.csv.gz', 'pilot-api.jsonl', 'pilot-before.json',
         'pilot_summary.json', 'summary.json')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inspect_run(folder):
    metadata = json.loads((folder / 'metadata.json').read_text(encoding='utf-8'))
    identity = json.loads((folder / 'aircraft_identity.json').read_text(encoding='utf-8'))
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    files = {name: {'sha256': digest(folder / name), 'bytes': (folder / name).stat().st_size}
             for name in FILES if (folder / name).is_file()}
    kinds = Counter()
    applied = []
    events = []
    first_truth = None
    peak_radar = None
    peak_baro = None
    airborne_start = last_airborne = None
    longest = None
    highest_strut = None
    with (folder / 'events.jsonl').open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            kind, payload = row.get('kind'), row.get('payload') or {}
            kinds[kind] += 1
            if kind == 'control_applied':
                applied.append({'t_s': payload.get('applied_sim_t_s', row.get('t_s')),
                                'sequence': payload.get('sequence'),
                                'requested': payload.get('requested')})
            elif kind in ('phantom_event', 'crash_capture', 'control_cancelled', 'sortie_end'):
                events.append({'kind': kind, 't_s': row.get('t_s'), 'payload': payload})
            elif kind == 'physics_audit':
                if first_truth is None:
                    first_truth = {'t_s': payload.get('t_s'), 'command': payload.get('command'),
                                   'body_poses': payload.get('body_poses'),
                                   'contact': payload.get('contact')}
                lift = (payload.get('phantom') or {}).get('nose_lift_m')
                if isinstance(lift, (int, float)) and (highest_strut is None or lift > highest_strut['m']):
                    highest_strut = {'m': lift, 't_s': payload.get('t_s')}
            elif kind == 'observation':
                t = payload.get('t_s')
                radar = payload.get('radar_altimeter_m')
                baro = payload.get('baro_m')
                if isinstance(radar, (int, float)) and (peak_radar is None or radar > peak_radar['m']):
                    peak_radar = {'m': radar, 't_s': t}
                if isinstance(baro, (int, float)) and (peak_baro is None or baro > peak_baro['m']):
                    peak_baro = {'m': baro, 't_s': t}
                ground = payload.get('radar_altimeter_ground_reference_m')
                airborne = (isinstance(t, (int, float)) and isinstance(radar, (int, float))
                            and isinstance(ground, (int, float)) and radar - ground > 1
                            and payload.get('weight_on_wheels') is False)
                if airborne and (last_airborne is None or t - last_airborne <= .25):
                    if airborne_start is None:
                        airborne_start = t
                    last_airborne = t
                else:
                    if airborne_start is not None:
                        segment = {'start_s': airborne_start, 'end_s': last_airborne,
                                   'duration_s': last_airborne - airborne_start}
                        if longest is None or segment['duration_s'] > longest['duration_s']:
                            longest = segment
                    airborne_start = t if airborne else None
                    last_airborne = t if airborne else None
    if airborne_start is not None:
        segment = {'start_s': airborne_start, 'end_s': last_airborne,
                   'duration_s': last_airborne - airborne_start}
        if longest is None or segment['duration_s'] > longest['duration_s']:
            longest = segment
    steps_count = 0
    peak_speed = None
    last_step = None
    with gzip.open(folder / 'phantom_steps.csv.gz', 'rt', encoding='utf-8', newline='') as source:
        for step in csv.DictReader(source):
            steps_count += 1
            speed = float(step['u'])
            if peak_speed is None or speed > peak_speed['m_s']:
                peak_speed = {'m_s': speed, 't_s': float(step['t'])}
            last_step = {key: step.get(key) for key in ('t', 'x', 'y', 'z', 'u', 'support', 'mode')}
    report = {'run_id': metadata['run_id'], 'archive': str(folder),
              'metadata': metadata, 'identity': identity,
              'outcome': summary.get('outcome'), 'files': files,
              'event_counts': dict(kinds), 'first_recorded_physical_state': first_truth,
              'peak_radar_altimeter': peak_radar, 'peak_baro_msl': peak_baro,
              'longest_observed_above_one_m_without_wheel_contact': longest,
              'highest_recorded_nose_lift_target': highest_strut,
              'step_samples': steps_count, 'peak_body_forward_speed': peak_speed,
              'last_step': last_step, 'events': events}
    return report, applied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('run_ids', nargs='+')
    args = parser.parse_args()
    archive, output = args.archive.resolve(), args.output_dir.resolve()
    if output == archive or output.is_relative_to(archive):
        raise ValueError('Output must be outside the original flight archive')
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+', run) for run in args.run_ids):
        raise ValueError('Invalid run ID')
    output.mkdir(parents=True, exist_ok=False)
    for run in args.run_ids:
        report, commands = inspect_run(archive / run)
        (output / f'{run}-inventory.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        (output / f'{run}-applied-controls.json').write_text(json.dumps(commands, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'run_id': run, 'outcome': report['outcome'],
                          'peak_radar': report['peak_radar_altimeter'],
                          'peak_baro': report['peak_baro_msl'],
                          'airborne_segment': report['longest_observed_above_one_m_without_wheel_contact'],
                          'peak_speed': report['peak_body_forward_speed'],
                          'max_nose_lift_target': report['highest_recorded_nose_lift_target'],
                          'applied_controls': len(commands), 'step_samples': report['step_samples']}), flush=True)


if __name__ == '__main__':
    main()
