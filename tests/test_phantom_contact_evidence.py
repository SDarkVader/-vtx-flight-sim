"""Engineering evidence identifies the solver's actual contact geometry."""
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
