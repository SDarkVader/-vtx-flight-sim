"""Exercise production publication without contacting providers."""
import importlib
from unittest.mock import Mock

import pytest


SHA = "a" * 40
OTHER = "b" * 40


@pytest.fixture
def production(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(__import__("pathlib").Path(__file__).resolve().parents[1] / ".github/scripts"))
    module = importlib.import_module("vercel_production")
    for key, value in {
        "GITHUB_SHA": SHA, "GITHUB_REF_NAME": "main", "GITHUB_REPOSITORY_ID": "123",
        "VERCEL_TOKEN": "offline", "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }.items():
        monkeypatch.setenv(key, value)
    return module


def test_advanced_main_cannot_publish(production, monkeypatch):
    monkeypatch.setattr(production, "github", lambda path: {"object": {"sha": OTHER}})
    provider = Mock()
    monkeypatch.setattr(production, "vercel", provider)
    with pytest.raises(SystemExit, match="advanced"):
        production.publish()
    provider.assert_not_called()


@pytest.mark.parametrize("retry", [False, True])
def test_production_publishes_tested_commit_and_reuses_partial_run(production, monkeypatch, retry):
    names = list(production.PROJECTS)
    creations = []
    polls = []
    monkeypatch.setattr(production, "github", lambda path: {"object": {"sha": SHA}})
    monkeypatch.setattr(production.time, "sleep", lambda seconds: None)

    def provider(path, payload=None, **query):
        if path == "v7/deployments":
            assert query["target"] == "production" and query["sha"] == SHA
            name = next(name for name in names if production.PROJECTS[name] == query["projectId"])
            previous = [{"uid": name, "readyState": "READY", "meta": {"vtxMathematicsSha": SHA}}]
            return {"deployments": previous if retry and name in names[:2] else []}
        if path == "v13/deployments":
            creations.append(payload)
            return {"id": payload["name"]}
        name = path.removeprefix("v13/deployments/")
        assert query["withGitRepoInfo"] == "true"
        polls.append(name)
        return {"projectId": production.PROJECTS[name], "gitSource": {"sha": SHA},
                "target": "production", "readyState": "READY", "aliasAssigned": True,
                "url": "example.invalid", "createdAt": 1234567890}

    monkeypatch.setattr(production, "vercel", provider)
    production.publish()
    assert len(polls) == 5
    assert len(creations) == (3 if retry else 5)
    for payload in creations:
        assert payload["target"] == "production"
        assert payload["gitSource"] == {"type": "github", "repoId": "123", "ref": "main", "sha": SHA}


def test_alias_failure_is_reported(production, monkeypatch):
    monkeypatch.setattr(production, "github", lambda path: {"object": {"sha": SHA}})
    monkeypatch.setattr(production, "production", lambda name, *args: name)
    name = next(iter(production.PROJECTS))
    monkeypatch.setattr(production, "vercel", lambda *args, **kwargs: {
        "projectId": production.PROJECTS[name], "gitSource": {"sha": SHA},
        "target": "production", "readyState": "READY", "aliasError": {"message": "failed"}})
    with pytest.raises(SystemExit, match="production domains"):
        production.publish()
