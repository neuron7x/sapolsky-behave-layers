"""Real-Git negative controls for the immutable evidence contour; offline only."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_experiment_ledger as builder
from scripts import cneh_history_guard as guard


class HistoryGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cneh-history-test-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "History guard fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.scientific = "scientific/protocol.json"
        self.write(self.scientific, b'{"threshold":0.5}\n')
        self.write(".gitignore", b"__pycache__/\n")
        self.payload = "artifacts/base/raw.json"
        self.write(self.payload, b'{"observed":1}\n')
        self.resign("artifacts/base")
        self.ledger = "docs/ledger.jsonl"
        self.ledger_bytes = b'{"run_id":"first","verdict":"NOT_TESTED"}\n{"run_id":"second","verdict":"NOT_TESTED"}\n'
        self.write(self.ledger, self.ledger_bytes)
        self.original = self.commit("original source and global evidence")
        for name in ("a1", "a2", "a2-ci"):
            self.write(f"artifacts/{name}/data.json", b'{"result":"negative"}\n')
            self.resign(f"artifacts/{name}")
        self.delivery = self.commit("historical deliveries")
        self.anchors = (
            guard.Anchor(self.original, self.scientific),
            guard.Anchor(self.original, "artifacts", tree=True),
            *(guard.Anchor(self.delivery, "artifacts/" + name, tree=True, exact_roster=True)
              for name in ("a1", "a2", "a2-ci")),
        )

    def git(self, *args, data=None):
        result = subprocess.run(["git", "-C", str(self.repo), *args], input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError(result.stderr.decode())
        return result.stdout.decode().strip()

    def write(self, relative, data):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def resign(self, relative):
        root = self.repo / relative
        files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
        (root / "SHA256SUMS").write_text("".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n" for path in files
        ))

    def verify(self, **overrides):
        arguments = {"anchors": self.anchors, "ledger_commit": self.delivery, "ledger_path": self.ledger}
        arguments.update(overrides)
        return guard.verify_history(self.repo, **arguments)

    def test_valid_history_future_bundle_and_append_only_ledger_pass(self):
        initial_status = self.git("status", "--porcelain")
        result = self.verify()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["ledger"]["historical_rows"], 2)
        self.assertEqual(initial_status, self.git("status", "--porcelain"))
        self.write("artifacts/future/new.json", b'{"status":"pending"}\n')
        self.write(self.ledger, self.ledger_bytes + b'{"run_id":"future","verdict":"NOT_TESTED"}\n')
        result = self.verify()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["ledger"]["appended_rows"], 1)
        self.assertFalse(result["scientific_promotion_authorized"])

    def test_real_ledger_regenerator_can_insert_new_sorted_bundle(self):
        for name in ("a-generated", "z-generated"):
            self.write(f"artifacts/{name}/verdict.json", b'{"status":"NOT_TESTED"}\n')
            self.resign("artifacts/" + name)
        self.commit("two historical generated bundles")
        def regenerate():
            with patch.object(builder, "ROOT", self.repo), patch.object(builder, "ART", self.repo / "artifacts"), patch.object(builder, "OUT", self.repo / self.ledger), contextlib.redirect_stdout(io.StringIO()):
                builder.main()
        regenerate()
        ledger_commit = self.commit("canonical historical ledger")
        self.verify(ledger_commit=ledger_commit)
        self.write("artifacts/m-generated/verdict.json", b'{"status":"NOT_TESTED"}\n')
        self.resign("artifacts/m-generated")
        self.commit("new future bundle")
        regenerate()
        records = [json.loads(line) for line in (self.repo / self.ledger).read_text().splitlines()]
        self.assertEqual([row["run_id"] for row in records],
                         ["artifacts:a-generated", "artifacts:m-generated", "artifacts:z-generated"])
        result = self.verify(ledger_commit=ledger_commit)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["ledger"]["appended_rows"], 1)

    def test_fully_resigned_bundle_passes_checksum_but_fails_git_history(self):
        self.write(self.payload, b'{"observed":999}\n')
        self.resign("artifacts/base")
        checksum = subprocess.run(["sha256sum", "-c", "SHA256SUMS"],
                                  cwd=self.repo / "artifacts/base", capture_output=True, text=True)
        self.assertEqual(checksum.returncode, 0, checksum.stderr)
        with self.assertRaisesRegex(guard.HistoryViolation, "byte mismatch"):
            self.verify()

    def test_frozen_scientific_byte_change_is_rejected(self):
        self.write(self.scientific, b'{"threshold":0.9}\n')
        with self.assertRaisesRegex(guard.HistoryViolation, "byte mismatch"):
            self.verify()

    def test_missing_historical_file_is_rejected(self):
        (self.repo / self.payload).unlink()
        with self.assertRaises((guard.HistoryViolation, FileNotFoundError)):
            self.verify()

    def test_same_bytes_symlink_leaf_is_rejected(self):
        original = self.repo / self.payload
        target = Path(self.temporary.name) / "same-bytes.json"
        target.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(target)
        with self.assertRaisesRegex(guard.HistoryViolation, "regular file"):
            self.verify()

    def test_same_contents_symlink_parent_is_rejected(self):
        original = self.repo / "artifacts/a1"
        target = Path(self.temporary.name) / "same-tree"
        original.rename(target)
        original.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(guard.HistoryViolation, "real directory"):
            self.verify()

    def test_extra_ignored_file_in_each_dedicated_root_is_rejected(self):
        for root in ("a1", "a2", "a2-ci"):
            path = self.write(f"artifacts/{root}/__pycache__/extra.pyc", b"unrecorded runtime bytes")
            with self.subTest(root=root), self.assertRaisesRegex(guard.HistoryViolation, "roster changed"):
                self.verify()
            path.unlink()

    def test_existing_file_replaced_by_directory_is_rejected(self):
        path = self.repo / self.payload
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(guard.HistoryViolation, "regular file"):
            self.verify()

    def test_missing_anchor_and_empty_roster_or_root_fail_closed(self):
        cases = (
            (),
            (guard.Anchor("0" * 40, self.scientific),),
            (guard.Anchor(self.original, "artifacts/missing", tree=True),),
        )
        for anchors in cases:
            with self.subTest(anchors=anchors), self.assertRaises(guard.HistoryViolation):
                self.verify(anchors=anchors)

    def test_existing_anchor_outside_head_ancestry_is_rejected(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        unrelated = self.git("commit-tree", tree, "-m", "unrelated root with identical files")
        with self.assertRaisesRegex(guard.HistoryViolation, "merge-base"):
            self.verify(anchors=(guard.Anchor(unrelated, self.scientific),))

    def test_deleted_rewritten_reordered_and_duplicated_ledger_rows_are_rejected(self):
        lines = self.ledger_bytes.splitlines(keepends=True)
        cases = (lines[0], b'{"run_id":"first","verdict":"SUPPORTED"}\n' + lines[1],
                 lines[1] + lines[0], self.ledger_bytes + lines[0],
                 self.ledger_bytes.replace(b'"verdict":', b'"verdict": '))
        for raw in cases:
            self.write(self.ledger, raw)
            with self.subTest(raw=raw), self.assertRaises(guard.HistoryViolation):
                self.verify()

    def test_malformed_or_nonfinite_appended_ledger_cannot_pass(self):
        for row in (b'{"run_id":"new","run_id":"first"}\n',
                    b'{"run_id":"new","value":NaN}\n',
                    b'{"run_id":"new","value":1e999}\n', b'[]\n', b'{"run_id":null}\n'):
            self.write(self.ledger, self.ledger_bytes + row)
            with self.subTest(row=row), self.assertRaises(guard.HistoryViolation):
                self.verify()

    def test_git_replacement_cannot_reauthenticate_modified_history(self):
        self.write(self.payload, b'{"observed":999}\n')
        self.resign("artifacts/base")
        replacement = self.commit("forged replacement history")
        self.git("replace", self.original, replacement)
        with self.assertRaisesRegex(guard.HistoryViolation, "byte mismatch"):
            self.verify()

    def test_shallow_history_is_rejected_even_when_anchor_files_exist(self):
        clone = Path(self.temporary.name) / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth=1", self.repo.as_uri(), str(clone)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with self.assertRaisesRegex(guard.HistoryViolation, "complete Git history"):
            guard.verify_history(clone, anchors=self.anchors, ledger_commit=self.delivery, ledger_path=self.ledger)

    def test_cli_cannot_select_weaker_anchors_and_reports_nonzero_failure(self):
        command = [sys.executable, "-B", str(Path(guard.__file__)), "--repo", str(self.repo)]
        before = self.git("status", "--porcelain")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        value = json.loads(result.stdout)
        self.assertEqual(value["status"], "FAIL")
        self.assertFalse(value["scientific_promotion_authorized"])
        self.assertEqual(before, self.git("status", "--porcelain"))
        result = subprocess.run(command + ["--anchor", self.delivery], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    os.umask(0o022)
    unittest.main()
