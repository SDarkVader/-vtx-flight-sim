"""World identity includes actual terrain, collision geometry, and seed."""
import pytest
from vtx import live_server as server
from vtx.world import SandboxWorld


@pytest.mark.parametrize('variant', ['r6', 'phantom-a10c'])
def test_checkpoint_uses_recorded_world_seed(tmp_path, variant):
    lab=server.Laboratory(data_root=tmp_path)
    lab.world=SandboxWorld(seed=12345);lab.flight_world=lab.world
    lab.start(server.Mission(airframe_variant=variant,environment='sandbox'))
    expected=lab.mission['environment_identity']
    lab.checkpoint(force=True)
    if getattr(lab.aircraft,'is_phantom',False):lab.aircraft.step_log.close()
    lab.audit_file.close()
    recovered=server.Laboratory(data_root=tmp_path)
    assert recovered.active and recovered.paused
    assert recovered.world.seed==12345
    assert server.environment_identity(recovered.world,recovered.flight_world,recovered.aircraft)==expected
    recovered.stop('End isolated world seed test')


def test_changed_terrain_with_same_name_and_version_blocks_recovery(tmp_path,monkeypatch):
    lab=server.Laboratory(data_root=tmp_path)
    lab.start(server.Mission(airframe_variant='r6',environment='sandbox'))
    original_xml=lab.aircraft.provenance['model_xml_sha256']
    lab.checkpoint(force=True);lab.audit_file.close()
    before=lab.checkpoint_path.read_bytes()
    real_make=server.make_world
    def changed_world(environment,seed=41031):
        world=real_make(environment,seed=seed)
        world.heights[world.n//2,world.n//2]+=10.0
        return world
    monkeypatch.setattr(server,'make_world',changed_world)
    changed=changed_world('sandbox')
    candidate=server.Aircraft(changed,gear_variant='critical-damping-proposal',rpm=1200.,fuel_kg=10.,
                              airframe_variant='r6',engine_power_limit_kw=300.)
    assert candidate.provenance['model_xml_sha256']==original_xml
    recovered=server.Laboratory(data_root=tmp_path)
    assert recovered.recovery_blocked and not recovered.active
    assert 'environment data or heightfield differs' in recovered.error
    assert lab.checkpoint_path.read_bytes()==before


def test_visual_and_collision_worlds_have_distinct_fingerprints(tmp_path):
    lab=server.Laboratory(data_root=tmp_path)
    lab.start(server.Mission(airframe_variant='r6',environment='sandbox',ignore_scenery_collisions=True))
    identity=lab.mission['environment_identity']
    assert identity['displayed_world_sha256']!=identity['physics_world_sha256']
    lab.stop('End isolated collision-world test')


def test_public_world_and_view_share_cached_actual_terrain_fingerprint(tmp_path, monkeypatch):
    import asyncio
    original_fingerprint=server.world_fingerprint
    calls=[]
    def counted(world):
        calls.append(world)
        return original_fingerprint(world)
    monkeypatch.setattr(server,'world_fingerprint',counted)
    lab=server.Laboratory(data_root=tmp_path)
    monkeypatch.setattr(server,'lab',lab)
    assert len(calls)==1
    first=lab.view()['environment']
    public=asyncio.run(server.world())
    assert first['seed']==public['seed']
    assert first['displayed_world_sha256']==public['displayed_world_sha256']==original_fingerprint(lab.world)
    lab.view();lab.view();asyncio.run(server.world())
    assert len(calls)==1  # no terrain hashing for telemetry or world requests

    lab.world=SandboxWorld(seed=12345)
    original=asyncio.run(server.world());original_view=lab.view()['environment']
    changed=SandboxWorld(seed=12345)
    changed.heights[changed.n//2,changed.n//2]+=10
    lab.world=changed
    revised=asyncio.run(server.world());revised_view=lab.view()['environment']
    assert (original['environment'],original['id'],original['version'],original['seed']) == (
        revised['environment'],revised['id'],revised['version'],revised['seed'])
    assert original['displayed_world_sha256'] != revised['displayed_world_sha256']
    assert original_view['displayed_world_sha256']==original['displayed_world_sha256']
    assert revised_view['displayed_world_sha256']==revised['displayed_world_sha256']
    assert len(calls)==3

    lab.world=SandboxWorld(seed=54321)
    seeded=asyncio.run(server.world());seeded_view=lab.view()['environment']
    assert seeded['seed']==seeded_view['seed']==54321
    assert seeded['displayed_world_sha256']==seeded_view['displayed_world_sha256']
    assert seeded['displayed_world_sha256'] != original['displayed_world_sha256']
    assert len(calls)==4
