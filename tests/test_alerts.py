"""Tests for the alert issues logic, with the GitHub API mocked out."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "collectors"))

import alerts  # noqa: E402

STATUS = """| Dataset | Rows | Latest data | Updates | Status |
|---|---:|---|---|---|
| `weather.csv` | 26 | 2026-10-05 | daily | ✅ OK |
| `dengue.csv` | 962 | 2026-08-01 | weekly | ⚠️ Stale (66 days old) |
| `cbsl_rates.csv` | 1 | 2026-10-06 | weekdays | ❌ New data rejected by validation |
"""


class FakeGitHub:
    def __init__(self, open_titles=()):
        self.calls = []
        self.open = [{"number": n, "title": t} for n, t in enumerate(open_titles, 1)]

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET":
            return self.open
        if path == "/issues":
            return {"number": 99}
        return None

    def opened(self):
        return [b["title"] for m, p, b in self.calls if (m, p) == ("POST", "/issues")]

    def closed(self):
        return [p for m, p, b in self.calls if m == "PATCH"]


class AlertsTest(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("GITHUB_REPOSITORY", "owner/repo")

    def run_sync(self, steps, status="", open_titles=()):
        gh = alerts.api = FakeGitHub(open_titles)
        problems, healthy = alerts.from_steps(steps)
        more, more_healthy = alerts.from_status(status)
        problems.update(more)
        alerts.sync(problems, (healthy | more_healthy) - set(problems))
        return gh

    def test_failures_open_one_issue_each(self):
        gh = self.run_sync({"dengue": {"outcome": "failure"}, "solar": {"outcome": "success"}}, STATUS)
        self.assertEqual(sorted(gh.opened()), [
            "Data alert: cbsl_rates.csv rejected by validation",
            "Data alert: dengue collector failed",
            "Data alert: dengue.csv is stale"])

    def test_known_problem_is_not_reported_again(self):
        gh = self.run_sync({"dengue": {"outcome": "failure"}},
                           open_titles=["Data alert: dengue collector failed"])
        self.assertEqual(gh.opened(), [])
        self.assertEqual(gh.closed(), [])

    def test_recovery_closes_the_issue(self):
        gh = self.run_sync({"dengue": {"outcome": "success"}},
                           open_titles=["Data alert: dengue collector failed"])
        self.assertEqual(gh.closed(), ["/issues/1"])

    def test_skipped_step_leaves_issue_alone(self):
        gh = self.run_sync({"dengue": {"outcome": "skipped"}},
                           open_titles=["Data alert: dengue collector failed"])
        self.assertEqual(gh.closed(), [])

    def test_status_recovery(self):
        healthy_status = STATUS.replace("⚠️ Stale (66 days old)", "✅ OK")
        gh = self.run_sync({}, healthy_status, open_titles=["Data alert: dengue.csv is stale"])
        self.assertEqual(gh.closed(), ["/issues/1"])


if __name__ == "__main__":
    unittest.main()
