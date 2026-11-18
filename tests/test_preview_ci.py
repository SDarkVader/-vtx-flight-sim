"""Preview CI contracts with offline provider responses and isolated summaries."""
import importlib.util
import json
import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHA, OTHER, BASE = "a" * 40, "b" * 40, "c" * 40
BRANCH = "codex/verified-preview"


@pytest.fixture
def scripts(monkeypatch, tmp_path):
    modules = []
    for name in ("preview_gate", "vercel_previews"):
        spec = importlib.util.spec_from_file_location(name, ROOT / ".github/scripts" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    gate, previews = modules
    def forbidden(*args, **kwargs):
        raise AssertionError("Provider calls and waits must be mocked")
    monkeypatch.setattr(gate.subprocess, "check_output", forbidden)
    monkeypatch.setattr(previews, "urlopen", forbidden)
    monkeypatch.setattr(previews.time, "sleep", forbidden)
    for key, value in {"GITHUB_REPOSITORY_OWNER": "owner", "GITHUB_REPOSITORY_ID": "123",
                       "GITHUB_REF_NAME": BRANCH, "GITHUB_SHA": SHA,
                       "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    return gate, previews


def gate_provider(monkeypatch, gate, *, branch_sha=SHA, pulls=None, runs=None, jobs=None):
    pr = {"number": 58, "head": {"sha": SHA}, "base": {"sha": BASE}}
    latest = {"id": 12, "run_attempt": 2, "status": "completed", "conclusion": "success",
              "pull_requests": [pr]}
    replies = iter([{"object": {"sha": branch_sha}}, [pr] if pulls is None else pulls,
                    {"workflow_runs": [latest] if runs is None else runs}])
    if jobs is None:
        jobs = [{"name": "mathematics", "conclusion": "success"}]
    provider = Mock(side_effect=lambda path, **query:
                    {"jobs": jobs} if path.endswith("/jobs") else next(replies))
    monkeypatch.setattr(gate, "github", provider)
    return provider, pr, latest


@pytest.mark.parametrize("case,expected", [
    ("normal-branch", True), ("success", True), ("advanced-branch", False),
    ("wrong-head", False), ("pending", None), ("missing-run", None),
    ("wrong-pr", None), ("old-base", None),
])
def test_gate_requires_current_push_and_matching_pr_mathematics(scripts, monkeypatch, case, expected):
    gate, _ = scripts
    provider, pr, latest = gate_provider(monkeypatch, gate)
    if case == "normal-branch":
        provider, _, _ = gate_provider(monkeypatch, gate, pulls=[])
    elif case == "advanced-branch":
        provider, _, _ = gate_provider(monkeypatch, gate, branch_sha=OTHER)
    elif case == "wrong-head":
        pr["head"]["sha"] = OTHER
    elif case in {"wrong-pr", "old-base"}:
        latest["pull_requests"] = [{"number": 99 if case == "wrong-pr" else 58,
                                     "base": {"sha": OTHER if case == "old-base" else BASE}}]
    elif case == "missing-run":
        provider, _, _ = gate_provider(monkeypatch, gate, runs=[])
    elif case == "pending":
        old = dict(latest, run_attempt=1)
        latest["status"], latest["conclusion"] = "in_progress", None
        provider, _, _ = gate_provider(monkeypatch, gate, runs=[latest, old])
    assert gate.can_publish(BRANCH, SHA) is expected
    if case == "success":
        assert provider.call_args_list[2].kwargs["head_sha"] == SHA
        assert provider.call_args.args == ("actions/runs/12/attempts/2/jobs",)
    if case == "normal-branch":
        assert provider.call_count == 2


@pytest.mark.parametrize("case", ["failed-run", "failed-job", "skipped-job", "missing-job"])
def test_failed_or_missing_math_never_publishes(scripts, monkeypatch, case):
    gate, _ = scripts
    _, _, latest = gate_provider(monkeypatch, gate)
    if case == "failed-run":
        latest["conclusion"] = "failure"
    else:
        jobs = [] if case == "missing-job" else [{
            "name": "mathematics", "conclusion": "failure" if case == "failed-job" else "skipped"}]
        gate_provider(monkeypatch, gate, jobs=jobs)
    with pytest.raises(SystemExit, match="Mathematics"):
        gate.can_publish(BRANCH, SHA)


@pytest.mark.parametrize("retry", [False, True])
def test_five_exact_sha_previews_and_partial_retry(scripts, monkeypatch, tmp_path, retry):
    _, previews = scripts
    monkeypatch.setenv("VERCEL_TOKEN", "offline-test-token")
    names = list(previews.PROJECTS)
    assert len(names) == len(set(previews.PROJECTS.values())) == 5
    created, polled, sleeps = [], [], []
    def provider(path, payload=None, **query):
        if path == "v7/deployments":
            assert query["sha"] == SHA and query["branch"] == BRANCH and query["target"] == "preview"
            name = next(name for name in names if previews.PROJECTS[name] == query["projectId"])
            existing = [{"uid": name, "readyState": "ERROR" if name == names[3] else "READY",
                         "meta": {"vtxMathematicsSha": OTHER if name == names[4] else SHA}}]
            return {"deployments": existing if retry else []}
        if path == "v13/deployments":
            created.append(payload)
            return {"id": payload["name"]}
        assert query == {"withGitRepoInfo": "true"}
        name = path.removeprefix("v13/deployments/")
        pending = name == names[0] and name not in polled
        polled.append(name)
        return {"projectId": previews.PROJECTS[name], "gitSource": {"sha": SHA}, "target": None,
                "readyState": "BUILDING" if pending else "READY", "url": name + ".example.invalid",
                "createdAt": 1234567890}
    monkeypatch.setattr(previews, "vercel", provider)
    monkeypatch.setattr(previews.time, "sleep", sleeps.append)
    previews.publish()
    assert [item["name"] for item in created] == (names[3:] if retry else names)
    for item in created:
        assert item["project"] == previews.PROJECTS[item["name"]]
        assert item["gitSource"] == {"type": "github", "repoId": "123", "ref": BRANCH, "sha": SHA}
        assert item["meta"]["vtxMathematicsSha"] == SHA and "target" not in item
    assert polled == names + [names[0]] and sleeps == [10]
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert len(summary.splitlines()) == 5
    assert all(summary.count("- " + name + " · " + SHA[:12]) == 1 for name in names)


def test_wrong_source_sha_cannot_be_reported_as_ready(scripts, monkeypatch):
    _, previews = scripts
    monkeypatch.setenv("VERCEL_TOKEN", "offline-test-token")
    monkeypatch.setattr(previews, "preview", lambda name, *args: name)
    monkeypatch.setattr(previews, "vercel", lambda path, **query: {
        "projectId": next(iter(previews.PROJECTS.values())),
        "gitSource": {"sha": OTHER}, "target": None, "readyState": "READY"})
    with pytest.raises(SystemExit, match="Unexpected project, source or target"):
        previews.publish()


def test_missing_optional_secret_fails_before_any_request(scripts, monkeypatch):
    _, previews = scripts
    provider = Mock(side_effect=AssertionError("No request without a token"))
    monkeypatch.setattr(previews, "vercel", provider)
    with pytest.raises(SystemExit, match="VERCEL_TOKEN"):
        previews.publish()
    provider.assert_not_called()


def test_native_git_previews_do_not_bypass_ci():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["git"]["deploymentEnabled"] is False


def test_deployed_selector_can_read_the_same_public_tree_as_the_cdn():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    module = project["tool"]["vercel"]["entrypoint"].split(":")[0]
    entrypoint = module.replace(".", "/") + ".py"
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    included = {p for p in ROOT.glob(config["functions"][entrypoint]["includeFiles"]) if p.is_file()}
    public_files = {p for p in (ROOT / "public").rglob("*") if p.is_file()}
    assert public_files and public_files <= included
