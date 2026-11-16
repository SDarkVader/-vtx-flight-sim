"""Publish the tested default-branch commit to the five VTX projects."""

import os
import time
from datetime import datetime, timezone

from preview_gate import github
from vercel_previews import PROJECTS, vercel


def require_current_commit(branch, sha):
    ref = github("git/ref/heads/" + branch)
    if ref["object"]["sha"] != sha:
        raise SystemExit("The default branch advanced; its newer run owns production.")


def production(name, project, branch, sha):
    existing = vercel("v7/deployments", projectId=project, branch=branch, sha=sha,
                      target="production", limit=100)["deployments"]
    for deployment in existing:
        if ((deployment.get("meta") or {}).get("vtxMathematicsSha") == sha
                and deployment["readyState"] in {"INITIALIZING", "QUEUED", "BUILDING", "READY"}):
            return deployment["uid"]
    require_current_commit(branch, sha)
    deployment = vercel("v13/deployments", {
        "name": name, "project": project, "target": "production",
        "gitSource": {"type": "github", "repoId": os.environ["GITHUB_REPOSITORY_ID"],
                      "ref": branch, "sha": sha},
        "meta": {"vtxMathematicsSha": sha},
    })
    return deployment["id"]


def publish():
    if not os.environ.get("VERCEL_TOKEN"):
        raise SystemExit("Missing VERCEL_TOKEN. Set the VTX Actions secret for the linked Vercel team.")
    sha, branch = os.environ["GITHUB_SHA"], os.environ["GITHUB_REF_NAME"]
    require_current_commit(branch, sha)
    pending = {name: production(name, project, branch, sha) for name, project in PROJECTS.items()}
    while pending:
        require_current_commit(branch, sha)
        for name, deployment_id in list(pending.items()):
            deployment = vercel("v13/deployments/" + deployment_id, withGitRepoInfo="true")
            source = deployment.get("gitSource") or {}
            if (deployment["projectId"] != PROJECTS[name] or source.get("sha") != sha
                    or deployment.get("target") != "production"):
                raise SystemExit(f"Unexpected project, source or target on {name} {deployment_id}.")
            state = deployment["readyState"]
            if deployment.get("aliasError"):
                raise SystemExit(f"{name} {deployment_id} failed to assign its production domains.")
            if state == "READY" and deployment.get("aliasAssigned"):
                created = datetime.fromtimestamp(deployment["createdAt"] / 1000, timezone.utc)
                line = f"- {name} · {sha[:12]} · https://{deployment['url']} · created {created.isoformat()}"
                print(line, flush=True)
                with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                    print(line, file=summary)
                del pending[name]
            elif state not in {"INITIALIZING", "QUEUED", "BUILDING", "READY"}:
                raise SystemExit(f"{name} {deployment_id} ended with {state}.")
        if pending:
            time.sleep(10)


if __name__ == "__main__":
    publish()
