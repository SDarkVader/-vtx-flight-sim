"""Phantom mass ledger: labels, inertia validity, manifest coverage, ledger == MuJoCo."""
import json
import numpy as np
import pytest
import mujoco as mj
from vtx.phantom import params as params_mod
from vtx.phantom.params import Params, PhantomConfigError
from vtx.phantom.ledger import PhantomLedger
from vtx.phantom.plant import PhantomAircraft
from vtx.world import TestWorld

LABELS = {'MEASURED-K', 'DERIVED', 'SYNTHETIC_UNVALIDATED', 'MANUFACTURER', 'REGULATORY_REFERENCE'}
W = TestWorld()


@pytest.mark.parametrize('variant', ['phantom', 'phantom-fx'])
def test_every_component_labelled_and_physical(variant):
    L = PhantomLedger(Params(variant))
    for c in L.components:
        assert c.source_status in LABELS, c.id
        assert c.mass_kg > 0 and np.isfinite(c.mass_kg)
        I = np.array(c.inertia_kg_m2)
        assert np.allclose(I, I.T) and np.linalg.eigvalsh(I).min() >= 0, c.id


def test_unknown_label_rejected():
    with pytest.raises(PhantomConfigError):
        Params('phantom', {'pods': {'fm_open': {'v': 0.8, 'u': '-', 'l': 'GUESS', 's': 'x'}}})


def test_manifest_field_without_selection_fails(tmp_path, monkeypatch):
    m = json.loads(params_mod.MANIFEST_FILE.read_text())
    m['unselected_field_for_test'] = None
    p = tmp_path / 'manifest.json'; p.write_text(json.dumps(m))
    monkeypatch.setattr(params_mod, 'MANIFEST_FILE', p)
    with pytest.raises(PhantomConfigError, match='unselected_field_for_test'):
        Params('phantom')


@pytest.mark.parametrize('variant,start', [('phantom', 'vtol'), ('phantom', 'road'), ('phantom-fx', 'vtol')])
def test_ledger_equals_mujoco(variant, start):
    a = PhantomAircraft(W, variant, start_configuration=start, engines_running=False); a.spawn(0, 0, 0)
    mj.mj_forward(a.model, a.data)
    mp = a.mass_properties()
    q = a.L.configuration(pods=start, legs='extended' if start == 'vtol' else 'retracted')
    led = a.L.mass_properties(q, fuel_kg=list(a.fuel))
    assert mp['mass_kg'] == pytest.approx(led['mass_kg'], abs=1e-4)   # MJCF float formatting
    np.testing.assert_allclose(mp['cg_body_m'], led['cg_m'], atol=2e-3)
    np.testing.assert_allclose(mp['inertia_body_kg_m2'], led['inertia_about_cg_kg_m2'], rtol=2e-2, atol=5.0)
    assert np.linalg.eigvalsh(np.array(mp['inertia_body_kg_m2'])).min() > 0


def test_fx_c_load_state_lighter_than_fx_a():
    a = PhantomAircraft(W, 'phantom-fx', load_state='FX-A'); c = PhantomAircraft(W, 'phantom-fx', load_state='FX-C')
    assert sum(c.model.body_mass) < sum(a.model.body_mass) - 100


def test_physical_snapshot_tracks_body_origin_not_a_fixed_world_pivot():
    a = PhantomAircraft(W, 'phantom-fx', start_configuration='road', engines_running=False)
    a.spawn(0, 0, 0)
    mj.mj_forward(a.model, a.data)
    cg_world = np.array(a.mass_properties()['cg_world_m'])
    cg_body = np.array(a.mass_properties()['cg_body_m'])
    q = np.array([np.cos(.35), 0., np.sin(.35), 0.])
    rotation = np.zeros(9)
    mj.mju_quat2Mat(rotation, q)
    a.data.qpos[3:7] = q
    a.data.qpos[:3] = cg_world - rotation.reshape(3, 3) @ cg_body
    mj.mj_forward(a.model, a.data)
    snapshot = a.physical_snapshot()
    pose = snapshot['body_poses']['airframe']
    np.testing.assert_allclose(a.mass_properties()['cg_world_m'], cg_world, atol=1e-6)
    np.testing.assert_allclose(pose['position'], a.data.xpos[a.bids['airframe']], atol=1e-5)
    np.testing.assert_allclose(pose['quaternion_wxyz'], q, atol=1e-6)


def test_controller_uses_current_articulated_centre_of_gravity(monkeypatch):
    a = PhantomAircraft(W, 'phantom-fx', start_configuration='road', engines_running=False)
    a.spawn(0, 0, 0)
    seen = []
    original = a.fcc.update

    def capture(t, sensed, mass_kg, cg_x, g, fan_enabled, thrust_avail):
        seen.append(cg_x)
        return original(t, sensed, mass_kg, cg_x, g, fan_enabled, thrust_avail)

    monkeypatch.setattr(a.fcc, 'update', capture)
    mj.mj_forward(a.model, a.data)
    a.control_update(.01)
    first_actual = a.mass_properties()['cg_body_m'][0]
    for side in ('left', 'right'):
        jid = a.jid[f'wing_{side}']
        a.data.qpos[a.model.jnt_qposadr[jid]] = 0.0
        jid = a.jid[f'canard_{side}_fold']
        a.data.qpos[a.model.jnt_qposadr[jid]] = 0.0
    mj.mj_forward(a.model, a.data)
    a.control_update(.01)
    second_actual = a.mass_properties()['cg_body_m'][0]
    assert abs(second_actual - first_actual) > 1e-5
    assert seen[0] == pytest.approx(first_actual, abs=2e-3)
    assert seen[1] == pytest.approx(second_actual, abs=2e-3)
