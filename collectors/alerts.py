"""Open a GitHub issue when a data source breaks; close it when it recovers.

    alerts.py collect                       # in the data workflow (after commit)
    alerts.py job --name forecast --status success|failure

`collect` reads the workflow's step outcomes from $STEPS (toJSON(steps)) and
STATUS.md: a failed collector, a file rejected by validation, a stale dataset
or a failed push each get one open issue labelled `data-alert`. While the
problem persists nothing more is posted, so GitHub only emails you once; when
the source works again the issue is closed with a link to the healthy run.
Steps that were skipped this run leave their issues untouched.

Uses the GitHub REST API with $GITHUB_TOKEN (standard library only). Pass
--dry-run to print what would happen instead.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

from common import REPO_ROOT, log

LABEL = "data-alert"
API = os.environ.get("GITHUB_API_URL", "https://api.github.com")


def run_url():
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server}/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"


def api(method, path, body=None):
    req = urllib.request.Request(
        f"{API}/repos/{os.environ['GITHUB_REPOSITORY']}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read()
            return json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        if method == "POST" and path == "/labels" and e.code == 422:
            return None  # label already exists
        raise


def title_for(key):
    kind, name = key.split(":", 1)
    return {
        "step": f"Data alert: {name} failed",
        "stale": f"Data alert: {name} is stale",
        "rejected": f"Data alert: {name} rejected by validation",
    }[kind]


STEP_NAMES = {"validate": "validation step", "commit": "pushing new data"}


def from_steps(steps):
    """{key: reason} for failed steps and the set of keys that succeeded."""
    problems, healthy = {}, set()
    for step_id, info in steps.items():
        key = f"step:{STEP_NAMES.get(step_id, f'{step_id} collector')}"
        if info.get("outcome") == "failure":
            problems[key] = f"The `{step_id}` step failed."
        elif info.get("outcome") == "success":
            healthy.add(key)
    return problems, healthy


def from_status(text):
    """Problems listed in STATUS.md (stale or rejected datasets)."""
    problems, healthy = {}, set()
    for name, status in re.findall(r"^\| `([^`]+)` \|.*\| ([^|]+) \|$", text, re.M):
        stale, rejected = f"stale:{name}", f"rejected:{name}"
        if "Stale" in status:
            problems[stale] = f"STATUS.md reports `{name}` as {status.strip()}."
        else:
            healthy.add(stale)
        if "rejected" in status:
            problems[rejected] = f"New rows for `{name}` failed validation and were not committed."
        else:
            healthy.add(rejected)
    return problems, healthy


def sync(problems, healthy, dry_run=False):
    """Open issues for new problems and close issues whose problem is gone."""
    if dry_run:
        for key, reason in sorted(problems.items()):
            log(f"would ensure open: {title_for(key)} ({reason})")
        return
    api("POST", "/labels", {"name": LABEL, "color": "d73a4a",
                            "description": "Opened automatically when a data source breaks"})
    open_issues = {i["title"]: i for i in api("GET", f"/issues?labels={LABEL}&state=open&per_page=100")}
    for key, reason in sorted(problems.items()):
        title = title_for(key)
        if title in open_issues:
            continue  # already reported; stay quiet until it recovers
        body = (f"{reason}\n\nFirst seen in [this workflow run]({run_url()}). Open the run "
                "for the full log; [STATUS.md](../blob/main/STATUS.md) shows every dataset's "
                "health.\n\nThis issue closes itself when the problem is gone.")
        issue = api("POST", "/issues", {"title": title, "body": body, "labels": [LABEL]})
        log(f"Opened #{issue['number']}: {title}")
    for key in sorted(healthy):
        issue = open_issues.get(title_for(key))
        if issue:
            api("POST", f"/issues/{issue['number']}/comments",
                {"body": f"Recovered in [this workflow run]({run_url()}). Closing."})
            api("PATCH", f"/issues/{issue['number']}", {"state": "closed", "state_reason": "completed"})
            log(f"Closed #{issue['number']}: {issue['title']}")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("mode", choices=["collect", "job"])
    p.add_argument("--name", help="job mode: workflow name for the issue title")
    p.add_argument("--status", help="job mode: success or failure")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.mode == "job":
        key = f"step:{args.name} workflow"
        failed = args.status == "failure"
        problems = {key: f"The {args.name} workflow failed."} if failed else {}
        healthy = set() if failed else {key}
    else:
        problems, healthy = from_steps(json.loads(os.environ.get("STEPS", "{}")))
        status_path = os.path.join(REPO_ROOT, "STATUS.md")
        if os.path.exists(status_path):
            with open(status_path, encoding="utf-8") as f:
                more, more_healthy = from_status(f.read())
            problems.update(more)
            healthy |= more_healthy
    sync(problems, healthy - set(problems), args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
