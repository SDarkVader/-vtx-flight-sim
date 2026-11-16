"""Create or reuse one preview of the tested Git SHA in each linked VTX project."""

import json
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TEAM = "team_kAdjEQ2ZsYsulcnNwv06efa4"
PROJECTS = {
    "-vtx-flight-sim": "prj_mkvyI93HIHmp9ShQBbnGpYt5FTty",
    "vercel-sandbox-default-project": "prj_8E4Oa2l15Y6j9efnddni1AXNs9np",
    "vtx-flight-sim": "prj_aRV0abzKp64EBd6FsaQLYZwWzRB7",
    "vtx-flight-sim-2l27": "prj_perJnEgWh5VbI28HLUCYFgg0JP4V",
    "vtx-flight-sim-nqbd": "prj_iBrrY5y99pxHbq9Unw0le5VsP9sa",
}


def vercel(path, payload=None, **query):
    url = "https://api.vercel.com/" + path + "?" + urlencode({"teamId": TEAM, **query})
    request = Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Authorization": "Bearer " + os.environ["VERCEL_TOKEN"],
                               "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise SystemExit(f"Vercel {request.get_method()} "
                         f"{path} failed ({error.code}): {error.read().decode()[:500]}") from error


def preview(name, project, branch, sha):
    # Rerunning a partly completed job reuses successful and in-flight previews.
    existing = vercel("v7/deployments", projectId=project, branch=branch, sha=sha,
                      target="preview", limit=100)["deployments"]
    for deployment in existing:
        if ((deployment.get("meta") or {}).get("vtxMathematicsSha") == sha and
                deployment["readyState"] in {"INITIALIZING", "QUEUED", "BUILDING", "READY"}):
            return deployment["uid"]
    deployment = vercel("v13/deployments", {
        "name": name, "project": project,
        "gitSource": {"type": "github", "repoId": os.environ["GITHUB_REPOSITORY_ID"],
                      "ref": branch, "sha": sha},
        "meta": {"vtxMathematicsSha": sha},
    })  # Omitting target explicitly selects Vercel's preview environment.
    return deployment["id"]


def publish():
    if not os.environ.get("VERCEL_TOKEN"):
        raise SystemExit("Set the VERCEL_TOKEN Actions secret for the linked Vercel team.")
    sha, branch = os.environ["GITHUB_SHA"], os.environ["GITHUB_REF_NAME"]
    pending = {name: preview(name, project, branch, sha) for name, project in PROJECTS.items()}
    while pending:
        for name, deployment_id in list(pending.items()):
            deployment = vercel("v13/deployments/" + deployment_id, withGitRepoInfo="true")
            source = deployment.get("gitSource") or {}
            if (deployment["projectId"] != PROJECTS[name] or source.get("sha") != sha or
                    deployment.get("target") not in (None, "preview")):
                raise SystemExit(f"Unexpected project, source or target on {name} {deployment_id}.")
            state = deployment["readyState"]
            if state == "READY":
                created = datetime.fromtimestamp(deployment["createdAt"] / 1000, timezone.utc)
                line = f"- {name} · {sha[:12]} · https://{deployment['url']} · created {created.isoformat()}"
                print(line, flush=True)
                with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                    print(line, file=summary)
                del pending[name]
            elif state not in {"INITIALIZING", "QUEUED", "BUILDING"}:
                raise SystemExit(f"{name} {deployment_id} ended with {state}.")
        if pending:
            time.sleep(10)


if __name__ == "__main__":
    publish()
