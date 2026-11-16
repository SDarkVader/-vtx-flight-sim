"""Wait for the open PR's integration run as well as the successful push job."""

import json
import os
import subprocess
import time
from urllib.parse import quote, urlencode


def github(path, **query):
    endpoint = f"repos/{os.environ['GITHUB_REPOSITORY']}/{path}"
    if query:
        endpoint += "?" + urlencode(query)
    return json.loads(subprocess.check_output(["gh", "api", endpoint]))


def can_publish(branch, sha):
    ref = github("git/ref/heads/" + quote(branch, safe="/"))
    if ref["object"]["sha"] != sha:
        print("Branch has advanced. A newer push owns the preview.")
        return False

    owner = os.environ["GITHUB_REPOSITORY_OWNER"]
    pulls = github("pulls", state="open", head=f"{owner}:{branch}", per_page=100)
    if not pulls:
        return True
    if any(pr["head"]["sha"] != sha for pr in pulls):
        return False

    runs = github("actions/workflows/physics-regression.yml/runs",
                  event="pull_request", head_sha=sha, per_page=100)["workflow_runs"]
    for pr in pulls:
        matches = [
            run for run in runs
            if any(link["number"] == pr["number"] and link["base"]["sha"] == pr["base"]["sha"]
                   for link in run["pull_requests"])
        ]
        if not matches:
            return None
        latest = max(matches, key=lambda r: (r["id"], r["run_attempt"]))
        if latest["status"] != "completed":
            return None
        if latest["conclusion"] != "success":
            raise SystemExit(f"PR #{pr['number']} Mathematics ended with {latest['conclusion']}.")
        jobs = github(f"actions/runs/{latest['id']}/attempts/{latest['run_attempt']}/jobs")["jobs"]
        math_job = next((job for job in jobs if job["name"] == "mathematics"), None)
        if not math_job or math_job["conclusion"] != "success":
            raise SystemExit(f"PR #{pr['number']} has no successful Mathematics job.")
        print(f"PR #{pr['number']} passed Mathematics for {sha}.")
    return True


if __name__ == "__main__":
    while True:
        publish = can_publish(os.environ["GITHUB_REF_NAME"], os.environ["GITHUB_SHA"])
        if publish is not None:
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                print(f"publish={str(publish).lower()}", file=output)
            break
        print("Waiting for Mathematics on the open pull request.", flush=True)
        time.sleep(15)
