"""Engineering evidence identifies the solver's actual contact geometry."""
import csv
import gzip
import json

import pytest

from vtx import live_server
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld


def test_contact_snapshot_reports_solver_geometry_and_location():
    world = TestWorld()
    aircraft = PhantomAircraft(world, 'phantom-a10c', start_configuration='road')
    aircraft.spawn(0, 0, world.surface_z(0, 0))
    for _ in range(400):
        aircraft.step()
    contacts = aircraft.physical_snapshot()['contact']['samples']
    assert contacts
    assert any(c['vehicle_geom'].startswith('tyre_') and c['other_geom'] == 'terrain' for c in contacts)
    assert all(len(c['position_world_m']) == 3 and isinstance(c['separation_m'], float) for c in contacts)


def test_collision_event_records_the_strongest_non_gear_contact():
    aircraft = PhantomAircraft(TestWorld(), 'phantom-a10c')
    threshold = aircraft.P['contact.crash_force_n']
    aircraft.contact_samples = lambda: [
        {'vehicle_geom': 'tyre_FR', 'other_geom': 'terrain', 'normal_force_n': threshold * 3},
        {'vehicle_geom': 'hull_2', 'other_geom': 'terrain', 'normal_force_n': threshold * 2},
    ]
    aircraft.check_contacts()
    event = next(e for e in aircraft.events if e['event'] == 'collision')
    assert event['contact']['vehicle_geom'] == 'hull_2'
    assert event['contact']['other_geom'] == 'terrain'
    assert aircraft.max_gear_load_n == threshold * 3
    assert aircraft.max_nongear_impact_n == threshold * 2


def test_a10d_landing_loads_survive_checkpoint_and_publish(tmp_path):
    lab = live_server.Laboratory(data_root=tmp_path)
    lab.start(live_server.Mission(airframe_variant='phantom-a10d',
                                  phantom={'start_configuration': 'road'}))
    aircraft = lab.aircraft
    gear_peak = 0.0
    for _ in range(80):
        lab.integrate()
        samples = aircraft.contact_samples()
        gear_peak = max([gear_peak, *(c['normal_force_n'] for c in samples
                                     if c['vehicle_geom'].startswith(('tyre_', 'foot_')))])
    assert gear_peak > 0.0
    assert aircraft.max_gear_load_n == gear_peak
    assert aircraft.max_nongear_impact_n == 0.0

    # Measure a separate below-crash-threshold impact without terminating the fixture.
    impact = aircraft.P['contact.crash_force_n'] / 2
    contact_samples = aircraft.contact_samples
    aircraft.contact_samples = lambda: [
        {'vehicle_geom': 'hull_2', 'other_geom': 'terrain', 'normal_force_n': impact},
    ]
    aircraft.check_contacts()
    aircraft.contact_samples = contact_samples
    lab.checkpoint(force=True)
    lab.aircraft.step_log.close()
    lab.audit_file.close()

    resumed = live_server.Laboratory(data_root=tmp_path)
    assert resumed.active and resumed.paused
    assert resumed.aircraft.max_gear_load_n == gear_peak
    assert resumed.aircraft.max_nongear_impact_n == impact
    for _ in range(24):
        resumed.integrate()
    final_gear = resumed.aircraft.max_gear_load_n
    run_path = resumed.log_path
    resumed.stop('Offline landing load fixture complete')

    summary = json.loads((run_path / 'summary.json').read_text())
    assert summary['max_gear_load_n'] == summary['final']['contact']['max_gear_load_n'] == final_gear
    assert summary['max_nongear_impact_n'] == summary['final']['contact']['max_nongear_impact_n'] == impact
    assert summary['contact_load_peaks_complete']
    assert summary['max_contact_force_n'] == max(final_gear, impact)
    events = [json.loads(line) for line in (run_path / 'events.jsonl').read_text().splitlines()]
    assert any(row['kind'] == 'physics_audit' and
               row['payload']['contact']['max_nongear_impact_n'] == impact for row in events)
    with gzip.open(run_path / 'phantom_steps.csv.gz', 'rt', newline='') as stream:
        last = list(csv.DictReader(stream))[-1]
    assert float(last['max_gear_load_n']) == pytest.approx(final_gear, rel=5e-6)
    assert float(last['max_nongear_impact_n']) == pytest.approx(impact, rel=5e-6)


def test_legacy_contact_peak_is_preserved_with_incomplete_classification():
    world = TestWorld()
    aircraft = PhantomAircraft(world, 'phantom-a10d', start_configuration='road')
    aircraft.spawn(0, 0, world.surface_z(0, 0))
    for _ in range(40):
        aircraft.step()
    state = aircraft.checkpoint_state()
    assert state['max_impact_n'] > 0.0
    for field in ('max_gear_load_n', 'max_nongear_impact_n', 'contact_load_peaks_complete'):
        del state[field]
    restored = PhantomAircraft(world, 'phantom-a10d', start_configuration='road')
    restored.restore_state(state)
    assert restored.max_impact_n == state['max_impact_n']
    assert not restored.physical_snapshot()['contact']['contact_load_peaks_complete']
