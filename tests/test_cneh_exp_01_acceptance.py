"""Adversarial acceptance regressions; no network or scientific claims."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

from experiments.cneh_exp_01 import acceptance as gate

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "artifacts/cneh-exp-01-a2/acceptance-auditor.py"


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cneh-acceptance-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.final_sha = "a" * 40

    def args(self, out=None, **extra):
        return argparse.Namespace(repo=str(self.repo), final_sha=self.final_sha,
                                  out=str(out or self.base / "out"), **extra)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo,
                                       stderr=subprocess.PIPE).decode().strip()

    def git_fixture(self):
        self.git("init", "-q", "--initial-branch=" + gate.BRANCH)
        source = self.repo / gate.AUDITOR_PATH
        source.parent.mkdir(parents=True)
        source.write_bytes(Path(gate.__file__).read_bytes())
        self.git("add", ".")
        self.git("-c", "user.name=CNEH fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "isolated fixture")
        self.final_sha = self.git("rev-parse", "HEAD")

    def forge(self, out, auditor):
        out.mkdir()
        (out / "checkout").mkdir()
        (out / "final-source-manifest.json").write_bytes(gate.canonical({"commit": "0" * 40, "files": {}}))
        (out / "local-replay-receipt.json").write_bytes(gate.canonical({
            "final_sha": self.final_sha, "auditor_sha256": gate.sha(Path(auditor.__file__).read_bytes()),
            "G3": {"status": "PASS"},
            "G4": {"status": "PASS", "scientific_promotion_authorized": True}}))

    def test_original_false_pass_remains_reproducible(self):
        self.git_fixture()
        self.assertEqual(gate.sha(OLD.read_bytes()), "fabdb74ac9572086a847c0486da10039f00ae4a89e46c08d9eeeff9bd26862d1")
        before = {str(p.relative_to(OLD.parent)): gate.sha(p.read_bytes())
                  for p in OLD.parent.rglob("*") if p.is_file()}
        original = types.ModuleType("historical_acceptance")
        original.__file__ = str(OLD)
        # Loading frozen evidence must not create a bytecode sidecar in its bundle.
        exec(compile(OLD.read_bytes(), str(OLD), "exec"), original.__dict__)
        after = {str(p.relative_to(OLD.parent)): gate.sha(p.read_bytes())
                 for p in OLD.parent.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        out = self.base / "forged-old"
        self.forge(out, original)
        audit = original.Audit(self.args(out, refresh=True))
        # Only the two live GitHub boundaries are assumed; the vulnerable path executes.
        audit.g1 = Mock(return_value={"status": "PASS", "fixture": "isolated G1"})
        audit.g2 = Mock(return_value={"status": "PASS", "fixture": "isolated G2"})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(audit.run(), 0)
        receipt = original.read(next(out.glob("acceptance-*.json")))
        self.assertTrue(receipt["ENGINEERING_QUALIFIED"])
        self.assertTrue(receipt["gates"]["G4"]["scientific_promotion_authorized"])
        self.assertEqual(list((out / "checkout").rglob("*")), [])
        self.assertFalse(any("replay" in r["label"] for r in audit.records))

    def test_replacement_rejects_same_self_authored_receipt_without_writes(self):
        out = self.base / "forged-new"
        self.forge(out, gate)
        before = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()}
        with self.assertRaises(FileExistsError):
            gate.Audit(self.args(out, refresh=True))
        after = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_existing_empty_directory_is_rejected(self):
        out = self.base / "empty"
        out.mkdir()
        with self.assertRaises(FileExistsError):
            gate.Audit(self.args(out))
        self.assertEqual(list(out.iterdir()), [])

    def test_existing_file_and_dangling_or_resolved_symlink_are_rejected(self):
        target = self.base / "target"
        for kind in ("file", "dangling", "resolved"):
            with self.subTest(kind=kind):
                out = self.base / kind
                if kind == "file":
                    out.write_text("preserve")
                else:
                    if kind == "resolved":
                        target.mkdir()
                    out.symlink_to(target, target_is_directory=True)
                with self.assertRaises(FileExistsError):
                    gate.Audit(self.args(out))
                if kind == "file":
                    self.assertEqual(out.read_text(), "preserve")
                else:
                    self.assertTrue(out.is_symlink())
                    self.assertEqual(target.exists(), kind == "resolved")

    def test_output_inside_repository_is_rejected_before_writes(self):
        out = self.repo / "new-evidence"
        with self.assertRaisesRegex(ValueError, "outside"):
            gate.Audit(self.args(out))
        self.assertFalse(out.exists())

    def test_concurrent_and_second_writer_cannot_share_output(self):
        barrier = threading.Barrier(2)
        def reserve():
            barrier.wait()
            try:
                return gate.Audit(self.args())
            except FileExistsError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reserve) for _ in range(2)]
            results = [f.result() for f in futures]
        self.assertEqual(sum(x is not None for x in results), 1)
        with self.assertRaises(FileExistsError):
            gate.Audit(self.args())

    def test_refresh_cli_is_removed_and_does_not_create_output(self):
        command = [sys.executable, "-B", gate.__file__, "--repo", str(self.repo),
                   "--final-sha", self.final_sha, "--out", str(self.base / "out"), "--refresh"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --refresh", result.stderr)
        self.assertFalse((self.base / "out").exists())

    def test_existing_output_cli_failure_preserves_original(self):
        out = self.base / "forged"
        self.forge(out, gate)
        before = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, "-B", gate.__file__, "--repo", str(self.repo),
                                 "--final-sha", self.final_sha, "--out", str(out)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ENGINEERING_QUALIFIED"])
        self.assertEqual(before, {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()})

    def test_forged_cache_injected_after_reservation_cannot_bypass_fresh_g3(self):
        self.git_fixture()
        audit = gate.Audit(self.args(refresh=True))
        (audit.out / "checkout").mkdir()
        (audit.out / "final-source-manifest.json").write_bytes(gate.canonical({"commit": "0" * 40, "files": {}}))
        (audit.out / "local-replay-receipt.json").write_bytes(gate.canonical({"final_sha": self.final_sha,
            "auditor_sha256": audit.auditor_sha256, "G3": {"status": "PASS"}, "G4": {"status": "PASS"}}))
        audit.g1 = Mock(return_value={"status": "PASS"})
        audit.g2 = Mock(return_value={"status": "PASS"})
        with patch.object(audit, "g3", wraps=audit.g3) as actual_replay:
            with self.assertRaisesRegex(FileExistsError, "fresh"):
                audit.run()
            actual_replay.assert_called_once_with()
        audit.g1.assert_not_called()
        self.assertEqual(list(audit.out.glob("acceptance-*.json")), [])

    def test_fresh_incomplete_source_executes_reconstruction_then_fails_closed(self):
        self.git_fixture()
        audit = gate.Audit(self.args())
        audit.g1 = Mock(return_value={"status": "PASS"})
        audit.g2 = Mock(return_value={"status": "PASS"})
        with patch.object(audit, "g3", wraps=audit.g3) as actual_replay:
            with self.assertRaises(RuntimeError):
                audit.run()
            actual_replay.assert_called_once_with()
        labels = [row["label"] for row in audit.records]
        self.assertIn("fresh-detached-worktree", labels)
        self.assertIn("auditor-source-binding", labels)
        self.assertEqual(self.git("worktree", "list", "--porcelain").count("worktree "), 1)
        self.assertEqual(list(audit.out.glob("acceptance-*.json")), [])

    def test_executing_auditor_must_equal_final_sha_blob(self):
        self.git_fixture()
        (self.repo / gate.AUDITOR_PATH).write_bytes(Path(gate.__file__).read_bytes() + b"\n# different final source\n")
        self.git("add", ".")
        self.git("-c", "user.name=CNEH fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "other bytes")
        self.final_sha = self.git("rev-parse", "HEAD")
        audit = gate.Audit(self.args())
        with self.assertRaisesRegex(ValueError, "differs from final SHA"):
            audit.verify_auditor_binding()

    def test_canonical_remote_excludes_wrong_owner_and_host(self):
        self.assertTrue(gate.canonical_remote("https://github.com/neuron7x/sapolsky-behave-layers.git"))
        for url in ("https://github.com/neuron7xLab/sapolsky-behave-layers.git",
                    "https://example.invalid/neuron7x/sapolsky-behave-layers.git",
                    "https://github.com/neuron7x/sapolsky-behave-layers.git/extra"):
            with self.subTest(url=url):
                self.assertFalse(gate.canonical_remote(url))

    def test_g1_rejects_wrong_branch_upstream_or_stale_pr_head(self):
        self.git_fixture()
        self.git("remote", "add", "origin", "https://github.com/" + gate.REPOSITORY + ".git")
        self.git("update-ref", "refs/remotes/origin/" + gate.BRANCH, self.final_sha)
        self.git("config", "branch." + gate.BRANCH + ".remote", "origin")
        self.git("config", "branch." + gate.BRANCH + ".merge", "refs/heads/" + gate.BRANCH)
        audit = gate.Audit(self.args())
        pr = {"head": {"sha": self.final_sha, "ref": gate.BRANCH, "repo": {"full_name": gate.REPOSITORY}},
              "base": {"ref": "main", "sha": self.final_sha, "repo": {"full_name": gate.REPOSITORY}},
              "merge_commit_sha": self.final_sha, "mergeable": True, "mergeable_state": "clean"}
        merge_tree = {"sha": self.git("rev-parse", "HEAD^{tree}")}
        def api(label, endpoint):
            return {"pr-merge-commit": {"tree": merge_tree}, "github-actor": {"login": "neuron7x"}, "canonical-repository": {"full_name": gate.REPOSITORY},
                    "pr-head": pr, "remote-branch": {"object": {"sha": self.final_sha}}}[label]
        original_command = audit.command
        def command(label, args, **kwargs):
            if label == "origin-ls-remote":
                return (self.final_sha + "\trefs/heads/" + gate.BRANCH + "\n").encode()
            if label == "canonical-fetch":
                return b""
            if label == "fetched-head":
                return self.final_sha.encode()
            return original_command(label, args, **kwargs)
        with patch.object(audit, "api", side_effect=api), patch.object(audit, "command", side_effect=command), patch.object(audit, "collect_provenance", return_value={"status": "PASS", "scope": "network collector isolation"}):
            self.assertEqual(audit.g1()["status"], "PASS")
            pr.update(mergeable=False, mergeable_state="dirty")
            self.assertEqual(audit.g1()["status"], "FAIL")
            pr.update(mergeable=None, mergeable_state="unknown")
            self.assertEqual(audit.g1()["status"], "UNKNOWN")
            pr.update(mergeable=True, mergeable_state="clean")
            pr["head"]["sha"] = "f" * 40
            self.assertEqual(audit.g1()["status"], "FAIL")
            pr["head"]["sha"] = self.final_sha
            pr["base"]["ref"] = "other"
            self.assertEqual(audit.g1()["status"], "FAIL")
            pr["base"]["ref"] = "main"
            original_tree = merge_tree["sha"]
            merge_tree["sha"] = "0" * 40
            self.assertEqual(audit.g1()["status"], "FAIL")
            merge_tree["sha"] = original_tree
            pr["merge_commit_sha"] = None
            self.assertEqual(audit.g1()["status"], "UNKNOWN")
            pr["merge_commit_sha"] = self.final_sha
            self.git("switch", "-qc", "wrong-branch")
            self.git("config", "branch.wrong-branch.remote", "origin")
            self.git("config", "branch.wrong-branch.merge", "refs/heads/" + gate.BRANCH)
            self.assertEqual(audit.g1()["status"], "FAIL")

    def test_historical_ledger_deletion_rewrite_or_unchecked_extension_rejected(self):
        frozen = [json.loads(line) for line in (ROOT / gate.LEDGER_PATH).read_text().splitlines() if line.strip()]
        self.assertEqual(len(gate.preserved_ledger_inventory(frozen, frozen)), 3)
        for mode in ("delete", "rewrite", "unchecked", "promote"):
            changed = copy.deepcopy(frozen)
            if mode == "delete":
                changed.pop()
            elif mode == "rewrite":
                changed[0]["verdict"] = "changed"
            elif mode == "unchecked":
                row = copy.deepcopy(next(r for r in frozen if not r["has_checksums"]))
                row["run_id"] = "new-unchecked"
                changed.append(row)
            else:
                row = copy.deepcopy(next(r for r in frozen if r["experiment"] == "CNEH-EXP-01"))
                row.update(run_id="new-promotion", verdict="SUPPORTED_NARROW")
                changed.append(row)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                gate.preserved_ledger_inventory(changed, frozen)

    def test_a3_mutation_false_kills_errors_skips_and_forged_identity_rejected(self):
        rows = []
        for name in ["baseline", *sorted(gate.A3_MUTANT_NAMES)]:
            baseline = name == "baseline"
            rows.append({"name": name, "exit_code": 0 if baseline else 1,
                         "classification": "PASS" if baseline else "KILLED_ASSERTION",
                         "counts": {"tests": 20, "failures": 0 if baseline else 1, "errors": 0,
                                    "skips": 0, "expected_failures": 0, "unexpected_successes": 0}})
        report = {"status": "PASS", "source_commit": self.final_sha,
                  "driver_sha256": gate.A3_MUTATION_DRIVER_SHA, "source_unchanged": True,
                  "killed": 4, "total_mutants": 4, "results": rows}
        self.assertEqual(gate.validate_a3_mutations(report, self.final_sha)["killed"], 4)
        for defect in ("errors", "skips", "expected_failures", "empty", "survivor", "baseline", "duplicate", "source", "commit", "driver"):
            changed = copy.deepcopy(report)
            if defect in ("errors", "skips", "expected_failures"):
                changed["results"][1]["counts"][defect] = 1
            elif defect == "empty":
                changed["results"][1]["counts"]["tests"] = 0
            elif defect == "survivor":
                changed["results"][1].update(exit_code=0, classification="SURVIVED_OR_INVALID")
            elif defect == "baseline":
                changed["results"][0]["counts"]["failures"] = 1
            elif defect == "duplicate":
                changed["results"][1]["name"] = changed["results"][2]["name"]
            elif defect == "source":
                changed["source_unchanged"] = False
            elif defect == "commit":
                changed["source_commit"] = "b" * 40
            else:
                changed["driver_sha256"] = "0" * 64
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                gate.validate_a3_mutations(changed, self.final_sha)

    def checks(self):
        return [{"id": i, "name": name, "head_sha": self.final_sha, "status": "completed", "conclusion": "success"}
                for i, name in enumerate(sorted(gate.REQUIRED_CHECKS), 1)]

    def test_empty_missing_pending_neutral_skipped_or_failed_ci_cannot_pass(self):
        self.assertEqual(gate.classify_ci([], [])["status"], "FAIL")
        self.assertEqual(gate.classify_ci(self.checks()[:-1], [])["status"], "FAIL")
        for conclusion in ("failure", "neutral", "skipped", "cancelled", "timed_out", None):
            checks = self.checks()
            checks[0]["conclusion"] = conclusion
            with self.subTest(conclusion=conclusion):
                self.assertEqual(gate.classify_ci(checks, [])["status"], "FAIL")
        checks = self.checks()
        checks[0].update(status="in_progress", conclusion=None)
        self.assertEqual(gate.classify_ci(checks, [])["status"], "UNKNOWN")
        self.assertEqual(gate.classify_ci(self.checks(), [{"state": "pending"}])["status"], "UNKNOWN")
        self.assertEqual(gate.classify_ci(self.checks(), [{"state": "failure"}])["status"], "FAIL")
        self.assertEqual(gate.classify_ci(self.checks(), [])["status"], "PASS")

    def provenance_fixture(self):
        manifest = gate.read(ROOT / gate.CHECKS_PATH)
        checks, runs = [], []
        for i, row in enumerate(manifest["required_contexts"], 1):
            checks.append({"id": i, "name": row["name"], "head_sha": self.final_sha,
                "app": {"id": row["app_id"], "slug": row["app_slug"]}, "check_suite": {"id": 100+i},
                "details_url": f"https://github.com/{gate.REPOSITORY}/actions/runs/{200+i}/job/{i}"})
            if row["workflow_path"] is not None:
                runs.append({"id": 200+i, "check_suite_id": 100+i, "head_sha": self.final_sha,
                             "path": row["workflow_path"], "event": row["event"], "status": "completed", "conclusion": "success"})
        return checks, runs, manifest

    def test_ci_name_cannot_substitute_for_app_workflow_event_or_sha(self):
        checks, runs, manifest = self.provenance_fixture()
        self.assertEqual(gate.ci_provenance(checks, runs, manifest, self.final_sha)["status"], "PASS")
        for field, value in (("app", {"id": 1, "slug": "untrusted"}),
                             ("head_sha", "b"*40), ("details_url", "https://example.invalid/job/1")):
            changed = copy.deepcopy(checks)
            changed[0][field] = value
            with self.subTest(field=field):
                self.assertEqual(gate.ci_provenance(changed, runs, manifest, self.final_sha)["status"], "FAIL")
        for field, value in (("event", "push"), ("path", ".github/workflows/other.yml"), ("head_sha", "c"*40)):
            changed = copy.deepcopy(runs)
            changed[0][field] = value
            with self.subTest(field=field):
                self.assertEqual(gate.ci_provenance(checks, changed, manifest, self.final_sha)["status"], "FAIL")

    def test_green_checks_do_not_mask_unfinished_or_failed_workflow_runs(self):
        checks, runs, manifest = self.provenance_fixture()
        for status, conclusion, expected in (("in_progress", None, "UNKNOWN"),
                ("completed", "failure", "FAIL"), ("completed", "neutral", "FAIL"),
                ("completed", "skipped", "FAIL")):
            changed = copy.deepcopy(runs)
            changed[0].update(status=status, conclusion=conclusion)
            with self.subTest(status=status, conclusion=conclusion):
                self.assertEqual(gate.ci_provenance(checks, changed, manifest, self.final_sha)["status"], expected)

    def test_duplicate_documentation_name_does_not_cover_both_events(self):
        checks, runs, manifest = self.provenance_fixture()
        for run in runs:
            if run["path"] == ".github/workflows/cwc-doc-gates.yml":
                run["event"] = "pull_request"
        result = gate.ci_provenance(checks, runs, manifest, self.final_sha)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(row["event"] == "push" for row in result["missing_required_contexts"]))

    def test_codeql_upload_job_does_not_replace_analysis_result(self):
        checks, runs, manifest = self.provenance_fixture()
        checks = [row for row in checks if row["name"] != "CodeQL"]
        self.assertEqual(gate.ci_provenance(checks, runs, manifest, self.final_sha)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
