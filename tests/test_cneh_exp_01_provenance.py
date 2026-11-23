"""Provenance boundary regressions; controlled fixtures, no network or credentials."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import importlib.util
import importlib.metadata
import base64
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import warnings
import zipfile

from experiments.cneh_exp_01 import provenance as p


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cneh-provenance-test-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "--initial-branch=" + p.BRANCH)
        (self.repo / "fixture.txt").write_text("known source\n")
        self.git("add", ".")
        self.git("-c", "user.name=CNEH test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "known source")
        self.head = self.git("rev-parse", "HEAD")
        self.git("remote", "add", "origin", "https://github.com/" + p.REPO + ".git")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo,
                                       stderr=subprocess.PIPE).decode().strip()

    def args(self, out=None):
        return argparse.Namespace(repo=str(self.repo), final_sha=self.head,
                                  out=str(out or self.base / "out"), mode="ci-artifacts",
                                  inputs=str(self.base / "inputs"))

    def collector(self, out=None):
        return p.Collector(self.args(out))

    @staticmethod
    def blob(files):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name, data in files:
                archive.writestr(name, data)
        return stream.getvalue()

    def good_blob(self):
        value = b"finite raw output\n"
        return self.blob([("raw.txt", value), ("SHA256SUMS", f"{p.sha(value)}  raw.txt\n")])

    def start_without_network(self, collector):
        original = collector.command
        def command(label, argv, **kwargs):
            if label == "actor-scope-names":
                return 0, b'HTTP/2 200\nX-Oauth-Scopes: repo\n\n{"login":"neuron7x"}'
            return original(label, argv, **kwargs)
        with patch.object(collector, "command", side_effect=command):
            collector.start()

    def test_wrong_remote_is_rejected_before_network_or_collection(self):
        self.git("remote", "set-url", "origin", "https://github.com/unrelated/example.git")
        with self.assertRaisesRegex(ValueError, "remote|repository"):
            self.start_without_network(self.collector())

    def test_dirty_tree_and_other_head_reject(self):
        (self.repo / "untracked.txt").write_text("not committed")
        with self.assertRaisesRegex(ValueError, "dirty|HEAD"):
            self.start_without_network(self.collector())
        (self.repo / "untracked.txt").unlink()
        args = self.args(self.base / "other-head")
        args.final_sha = "a" * 40
        with self.assertRaisesRegex(ValueError, "HEAD"):
            self.start_without_network(p.Collector(args))

    def test_existing_output_and_symlink_parents_cannot_receive_writes(self):
        out = self.base / "existing"
        out.mkdir()
        (out / "receipt.json").write_text("preserve")
        with self.assertRaises(FileExistsError):
            self.collector(out)
        self.assertEqual((out / "receipt.json").read_text(), "preserve")
        target = self.base / "target"
        target.mkdir()
        link = self.base / "alias"
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaises((ValueError, FileExistsError)):
            self.collector(link / "new")
        self.assertEqual(list(target.iterdir()), [])

    def test_concurrent_output_has_exactly_one_writer(self):
        barrier = threading.Barrier(2)
        def reserve():
            barrier.wait()
            try:
                self.collector()
                return True
            except FileExistsError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(reserve) for _ in range(2)]
            self.assertEqual(sum(item.result() for item in results), 1)

    def test_output_inside_repository_is_rejected_before_creation(self):
        destination = self.repo / "generated"
        with self.assertRaisesRegex(ValueError, "outside"):
            self.collector(destination)
        self.assertFalse(destination.exists())

    def test_strict_json_and_paths_reject_ambiguous_inputs(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                p.strict_json(raw)
        for name in ("../escape", "/absolute", "dir/../escape", "dir\\escape", ".", "x\x01"):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                p.safe_relative(name)

    def test_zip_traversal_duplicate_and_special_member_rejected(self):
        bad = self.blob([("../escape", b"bad")])
        with self.assertRaises(ValueError):
            p.extract_zip(bad, self.base / "traversal")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            duplicate = self.blob([("same", b"a"), ("same", b"b")])
        with self.assertRaises(ValueError):
            p.extract_zip(duplicate, self.base / "duplicate")
        for kind in (stat.S_IFLNK, stat.S_IFSOCK, stat.S_IFIFO):
            entry = zipfile.ZipInfo("special")
            entry.external_attr = (kind | 0o600) << 16
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr(entry, b"irrelevant")
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                p.extract_zip(stream.getvalue(), self.base / str(kind))

    def test_zip_file_directory_conflict_is_rejected_before_output(self):
        data = self.blob([("collision", b"file"), ("collision/child", b"child")])
        destination = self.base / "collision"
        with self.assertRaises((ValueError, OSError)):
            p.extract_zip(data, destination)
        self.assertFalse(destination.exists())

    def test_zip_declared_size_bound_is_checked_before_decompression(self):
        info = zipfile.ZipInfo("too-large")
        info.file_size = 2**30
        fake = Mock()
        fake.__enter__ = Mock(return_value=fake)
        fake.__exit__ = Mock(return_value=False)
        fake.infolist.return_value = [info]
        with patch.object(p.zipfile, "ZipFile", return_value=fake):
            with self.assertRaisesRegex(ValueError, "size"):
                p.extract_zip(b"placeholder", self.base / "oversize")
        fake.read.assert_not_called()

    def test_manifest_validates_bytes_and_classifies_upload_extras(self):
        destination = self.base / "bundle"
        p.extract_zip(self.good_blob(), destination)
        (destination / "extra.json").write_text('{"note":"separate uploaded file"}')
        report = p.manifests(destination)
        self.assertFalse(report["manifests"][0]["roster_exact_within_manifest_directory"])
        self.assertEqual([row["path"] for row in report["archive_files_outside_manifests"]], ["extra.json"])
        (destination / "raw.txt").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            p.manifests(destination)

    def test_manifest_rejects_unlisted_symlink_before_reading_target(self):
        destination = self.base / "bundle"
        p.extract_zip(self.good_blob(), destination)
        outside = self.base / "outside"
        outside.write_bytes(b"controlled fixture, never a credential")
        (destination / "unlisted").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink|regular"):
            p.manifests(destination)

    def test_pagination_rejects_moving_totals_duplicate_ids_and_truncation(self):
        cases = [
            [{"total_count": 2, "rows": [{"id": 1}]}, {"total_count": 3, "rows": [{"id": 2}]}],
            [{"total_count": 2, "rows": [{"id": 1}]}, {"total_count": 2, "rows": [{"id": 1}]}],
            [{"total_count": 2, "rows": [{"id": 1}]}, {"total_count": 2, "rows": []}],
        ]
        for number, values in enumerate(cases):
            collector = self.collector(self.base / f"pages-{number}")
            collector.api = Mock(side_effect=values)
            with self.subTest(number=number), self.assertRaises(ValueError):
                collector.paginated("pages", "example", "rows")

    def ci_fixture(self, counts, stale=False):
        collector = self.collector()
        collector.start = Mock()
        collector.actor = {"actor": "neuron7x"}
        collector.finish = Mock()
        names = sorted(p.EXPECTED_ARTIFACTS)
        data = self.good_blob()
        runs = [{"id": i + 1, "path": ".github/workflows/cneh-exp-01.yml", "event": "pull_request",
                 "head_sha": self.head, "status": "completed", "conclusion": "success",
                 "run_attempt": 1, "html_url": "https://github.com/" + p.REPO + f"/actions/runs/{i + 1}"}
                for i in range(len(counts))]
        groups = []
        for i, count in enumerate(counts):
            selected = names[:count]
            groups.append([{"id": (i + 1) * 100 + j, "name": name, "expired": False,
                            "size_in_bytes": len(data), "digest": "sha256:" + p.sha(data),
                            "workflow_run": {"id": i + 1, "head_sha": "b" * 40 if stale else self.head,
                                             "head_branch": p.BRANCH}}
                           for j, name in enumerate(selected)])
        collector.paginated = Mock(side_effect=[runs, *groups])
        collector.command = Mock(return_value=(0, data))
        return collector

    def test_every_run_must_have_complete_artifact_roster(self):
        collector = self.ci_fixture([0, len(p.EXPECTED_ARTIFACTS)])
        with self.assertRaisesRegex(ValueError, "missing|roster"):
            collector.ci_artifacts()
        collector.finish.assert_not_called()

    def test_stale_artifact_rejected_before_download(self):
        collector = self.ci_fixture([len(p.EXPECTED_ARTIFACTS)], stale=True)
        with self.assertRaisesRegex(ValueError, "identity"):
            collector.ci_artifacts()
        collector.command.assert_not_called()

    def test_complete_artifacts_remain_nonqualifying_provenance(self):
        collector = self.ci_fixture([len(p.EXPECTED_ARTIFACTS)])
        collector.ci_artifacts()
        report = collector.finish.call_args.args[0]
        self.assertEqual(report["artifact_integrity"], "PASS")
        self.assertEqual(len(report["artifacts"]), len(p.EXPECTED_ARTIFACTS))
        self.assertNotIn("ENGINEERING_QUALIFIED", report)
        self.assertTrue(all(row["semantic_replay"] == "NOT_RUN_BY_THIS_COLLECTOR" for row in report["artifacts"]))

    def test_installed_record_rejects_changed_bytes_versions_and_escape(self):
        prefix = self.base / "environment"
        prefix.mkdir()
        payload = prefix / "package.py"
        original = b"result = 7\n"
        payload.write_bytes(original)
        encoded = base64.urlsafe_b64encode(hashlib.sha256(original).digest()).rstrip(b"=").decode()
        distribution = Mock()
        distribution.version = "1"
        distribution.read_text.return_value = f"package.py,sha256={encoded},{len(original)}\n"
        distribution.locate_file.side_effect = lambda name: prefix / name
        with patch.object(p.sys, "prefix", str(prefix)), patch.object(importlib.metadata, "distribution", return_value=distribution):
            result = p.verify_installed_records([{"name": "fixture", "version": "1"}])
            self.assertEqual(result["hashed_files_verified"], 1)
            self.assertEqual(result["authority"], "CONSISTENCY_WITH_INSTALLED_DISTRIBUTION_RECORD_ONLY")
            payload.write_bytes(b"changed\n")
            with self.assertRaisesRegex(ValueError, "byte/hash/size"):
                p.verify_installed_records([{"name": "fixture", "version": "1"}])
            with self.assertRaisesRegex(ValueError, "version"):
                p.verify_installed_records([{"name": "fixture", "version": "2"}])
            outside = self.base / "outside-record-target"
            outside.write_bytes(original)
            distribution.locate_file.side_effect = lambda name: outside
            with self.assertRaisesRegex(ValueError, "escapes"):
                p.verify_installed_records([{"name": "fixture", "version": "1"}])

    def test_collector_source_change_cannot_be_bound_to_new_bytes_at_finish(self):
        copied = self.base / "collector.py"
        copied.write_bytes(Path(p.__file__).read_bytes())
        spec = importlib.util.spec_from_file_location("changing_collector", copied)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        collector = module.Collector(self.args())
        copied.write_bytes(copied.read_bytes() + b"\n# changed during execution\n")
        with self.assertRaisesRegex(ValueError, "implementation changed"):
            collector.finish({"inventory_integrity": "PASS"}, "provenance.json")
        self.assertFalse((collector.out / "provenance.json").exists())

    def test_actor_headers_collect_only_names_and_classify_absence(self):
        raw = b'HTTP/2 200\r\nX-Oauth-Scopes: repo, read:org\r\nLocation: https://temporary.invalid/signed\r\n\r\n{"login":"neuron7x","unrelated":"excluded"}'
        result = p.actor_scope_headers(raw)
        self.assertEqual(result["oauth_scope_names"], ["read:org", "repo"])
        self.assertNotIn("signed", json.dumps(result))
        self.assertNotIn("excluded", json.dumps(result))
        absent = p.actor_scope_headers(b'HTTP/2 200\n\n{"login":"neuron7x"}')
        self.assertEqual(absent["scope_metadata"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
