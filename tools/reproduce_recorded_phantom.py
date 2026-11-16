"""Re-run recorded manual controls through an isolated historical VTX solver.

No server or browser is started. An original runtime must match its recording;
an explicitly named integrated candidate must identify that recording as its
parent. In either case model and configuration must match before stepping.
The output directory must be new and separate from both source and archive.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('--integrated-variant', help='Explicit integrated candidate derived from this recorded run')
    args = parser.parse_args()
    runtime, record, output = args.runtime.resolve(), args.record.resolve(), args.output_dir.resolve()
    if any(output == root or output.is_relative_to(root) for root in (record, runtime)):
        raise ValueError('Output must be separate from the original record and runtime')
    if args.seconds <= 0:
        raise ValueError('Duration must be positive')
    metadata = json.loads((record / 'metadata.json').read_text(encoding='utf-8'))
    decisions = []
    with (record / 'events.jsonl').open(encoding='utf-8') as source:
        for line in source:
            if '"kind":"pilot_decision"' in line or '"kind": "pilot_decision"' in line:
                decisions.append(json.loads(line)['payload'])
    if metadata['operator'] != 'manual':
        raise ValueError('This harness currently reproduces manual-authority records only')
    if any(row['issued'].get('authority') != 'manual' for row in decisions):
        raise ValueError('Authority handover needs an explicit reconstruction')
    sys.path.insert(0, str(runtime / 'src'))
    output.mkdir(parents=True, exist_ok=False)
    os.environ['VTX_DATA_ROOT'] = str(output / 'lab')
    os.environ['VTX_ENFORCE_RELEASE'] = '0'
    from vtx.aircraft import DT
    from vtx.live_server import Laboratory, Mission, RUNTIME_SOURCE_SHA256
    from vtx.phantom.controls import PhantomAction

    expected_runtime = metadata.get('runtime_source_sha256')
    if args.integrated_variant:
        from vtx.phantom.flight_revisions import flight_revision
        revision = flight_revision(args.integrated_variant)
        if not revision or revision['parent_runtime_sha256'] != expected_runtime or not any(
                evidence['run_id'] == metadata['run_id'] for evidence in revision['evidence']):
            raise RuntimeError('Integrated variant does not identify this recorded parent and run')
    elif RUNTIME_SOURCE_SHA256 != expected_runtime:
        raise RuntimeError(f'Runtime fingerprint mismatch: {RUNTIME_SOURCE_SHA256} != {expected_runtime}')
    if abs(DT - .0025) > 1e-12:
        raise RuntimeError(f'Unexpected physics timestep: {DT}')
    request = dict(metadata['request'])
    if args.integrated_variant:
        request['airframe_variant'] = args.integrated_variant
    explicit_fuel = request.pop('fuel_kg_explicit', None)
    if explicit_fuel is False:
        request.pop('fuel_kg', None)
    lab = Laboratory(data_root=output / 'lab')
    lab.start(Mission(**request))
    aircraft = lab.aircraft
    for field in ('model_xml_sha256', 'config_sha256'):
        actual, expected = aircraft.provenance[field], metadata['airframe'][field]
        if actual != expected:
            raise RuntimeError(f'{field} mismatch: {actual} != {expected}')
    if lab.mission['environment'] != metadata['mission']['environment']:
        raise RuntimeError('Environment mismatch')
    print(json.dumps({'runtime_verified': RUNTIME_SOURCE_SHA256, 'model': aircraft.provenance['model_xml_sha256'],
                      'environment': lab.mission['environment'], 'fuel_kg': float(aircraft.fuel.sum()),
                      'recorded_decisions': len(decisions)}), flush=True)
    index = 0
    next_progress = 10.0
    while lab.active and float(aircraft.data.time) < args.seconds:
        t = float(aircraft.data.time)
        while index < len(decisions) and decisions[index]['issued_t_s'] <= t + 1e-8:
            issued = dict(decisions[index]['issued'])
            if 'expected_run_id' in issued:
                issued['expected_run_id'] = lab.run_id
            lab.accept_action(PhantomAction.model_validate(issued))
            index += 1
        lab.integrate()
        if aircraft.data.time >= next_progress:
            print(f'simulated {aircraft.data.time:.1f} s', flush=True)
            next_progress += 10.0
    simulated = float(aircraft.data.time)
    crashed = bool(aircraft.crashed)
    if lab.active:
        lab.stop('End isolated recorded-control reproduction')
    candidate_csv = lab.log_path / 'phantom_steps.csv.gz'
    original_csv = record / 'phantom_steps.csv.gz'
    fields = ('x', 'y', 'z', 'u', 'v', 'w', 'roll_deg', 'pitch_up_deg', 'yaw_left_deg',
              'support', 'flap_left', 'flap_right', 'tilt_FL', 'tilt_FR', 'tilt_RL', 'tilt_RR')
    maxima = {name: {'absolute_difference': 0.0, 't_s': None} for name in fields}
    compared = 0
    with gzip.open(original_csv, 'rt', encoding='utf-8', newline='') as old, gzip.open(candidate_csv, 'rt', encoding='utf-8', newline='') as new:
        for original, candidate in zip(csv.DictReader(old), csv.DictReader(new)):
            old_t, new_t = float(original['t']), float(candidate['t'])
            if abs(old_t - new_t) > .0001:
                raise RuntimeError(f'Telemetry time mismatch: {old_t} != {new_t}')
            compared += 1
            for field in fields:
                difference = abs(float(original[field]) - float(candidate[field]))
                if difference > maxima[field]['absolute_difference']:
                    maxima[field] = {'absolute_difference': difference, 't_s': old_t}
    result = {'record_run_id': metadata['run_id'], 'runtime_sha256': RUNTIME_SOURCE_SHA256,
              'recorded_parent_runtime_sha256': expected_runtime, 'integrated_variant': args.integrated_variant,
              'original_model_xml_sha256': metadata['airframe']['model_xml_sha256'],
              'generated_run_id': lab.run_id, 'generated_flight_dir': str(lab.log_path),
              'simulated_seconds': simulated, 'crashed': crashed, 'decisions_submitted': index,
              'compared_100_hz_samples': compared, 'max_absolute_differences': maxima,
              'notes': 'Recorded control patches were submitted at their recorded issue times through PhantomAction and Laboratory.accept_action; 20 ms transport and plant integration were retained.'}
    (output / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
