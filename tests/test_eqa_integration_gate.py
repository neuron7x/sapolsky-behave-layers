from __future__ import annotations

import unittest

from scripts.eqa_integration_gate import REQUIRED_JOBS, identity_errors, roster_errors


class IntegrationGateTests(unittest.TestCase):
    def test_exact_successful_roster(self) -> None:
        jobs = {job: {"result": "success"} for job in REQUIRED_JOBS}
        self.assertEqual(roster_errors(jobs), [])
        for job in REQUIRED_JOBS:
            with self.subTest(job=job):
                self.assertTrue(roster_errors({k: v for k, v in jobs.items() if k != job}))
        self.assertTrue(roster_errors({**jobs, "unknown": {"result": "success"}}))

    def test_each_non_success_state_is_rejected(self) -> None:
        for state in ("failure", "cancelled", "skipped", "timed_out", "neutral", None):
            for job in REQUIRED_JOBS:
                with self.subTest(state=state, job=job):
                    jobs = {name: {"result": "success"} for name in REQUIRED_JOBS}
                    jobs[job] = {"result": state}
                    self.assertEqual(len(roster_errors(jobs)), 1)

    def test_candidate_identity(self) -> None:
        head, base, merge = "a" * 40, "b" * 40, "c" * 40
        info = {
            "event": "pull_request", "checkout": merge, "expected_checkout": merge,
            "parents": [base, head], "head": head, "base": base,
        }
        self.assertEqual(identity_errors(**info), [])
        for key, value in (("checkout", head), ("head", base), ("parents", [head, base]), ("event", "push")):
            with self.subTest(key=key):
                self.assertTrue(identity_errors(**{**info, key: value}))
