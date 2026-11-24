"""Falsify the historical provenance inventory on synthetic sealed ZIPs."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

from experiments.cneh_exp_05q import inventory as q


class TestInventory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "archive.zip"
        self.digest = "a" * 64
        self.lock = "numpy==2.4.1 \\\n    --hash=sha256:" + self.digest + "\n"
        self.report = {
            "environment": {"python_full_version": "3.12.16", "platform_machine": "x86_64"},
            "install": [{
                "metadata": {"name": "NumPy", "version": "2.4.1"},
                "download_info": {
                    "url": "https://example.org/numpy-2.4.1-cp312-cp312-manylinux.whl",
                    "archive_info": {"hashes": {"sha256": self.digest}},
                },
            }],
        }

    def seal(self, report=None, *, omit=None, extra=None, raw=None):
        if report is None:
            report = self.report
        with zipfile.ZipFile(self.path, "w") as archive:
            for name in sorted(q.ROSTER - ({omit} if omit else set())):
                data = (raw if raw is not None else json.dumps(report)) if name == "cneh05-install.json" else "fixture"
                archive.writestr(name, data)
            if extra is not None:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(extra, "duplicate or unexpected")
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_exact_inventory_is_not_replay_authority(self):
        sha = self.seal()
        result = q.inventory(self.path, sha, self.lock)
        self.assertEqual(result, q.inventory(self.path, sha, self.lock))
        self.assertEqual(result["historical_domain"], "HISTORICAL_DOMAIN_UNRESOLVED")
        self.assertEqual(result["historical_native_replay"], "FAIL_PRESERVED")
        self.assertFalse(result["replay_rerun_authorized"])
        self.assertFalse(result["scientific_promotion_authorized"])
        self.assertEqual(result["locked_wheel_roster"]["numpy"]["sha256"], self.digest)
        self.assertIn("original_libm_libc_blas_binary_identity", result["unestablished_execution_domain_fields"])
        self.assertIn("platform_release", result["missing_report_environment_fields"])

    def test_tampered_archive(self):
        sha = self.seal()
        with self.path.open("ab") as out:
            out.write(b"tamper")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            q.inventory(self.path, sha, self.lock)

    def test_duplicate_or_missing_or_extra_members(self):
        for kwargs in ({"extra": "cneh05-install.json"}, {"omit": "cneh05/implementation.json"},
                       {"extra": "../escape"}):
            with self.subTest(kwargs=kwargs):
                sha = self.seal(**kwargs)
                with self.assertRaisesRegex(ValueError, "roster"):
                    q.inventory(self.path, sha, self.lock)

    def test_wrong_wheel_version_and_hash(self):
        for field in ("version", "hash"):
            report = copy.deepcopy(self.report)
            if field == "version":
                report["install"][0]["metadata"]["version"] = "2.4.2"
            else:
                report["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"] = "b" * 64
            with self.subTest(field=field):
                sha = self.seal(report)
                with self.assertRaisesRegex(ValueError, "unlocked wheel"):
                    q.inventory(self.path, sha, self.lock)

    def test_incomplete_and_duplicate_installs(self):
        for installs in ([], self.report["install"] * 2):
            report = copy.deepcopy(self.report)
            report["install"] = installs
            sha = self.seal(report)
            with self.assertRaisesRegex(ValueError, "roster"):
                q.inventory(self.path, sha, self.lock)

    def test_duplicate_json_key(self):
        sha = self.seal(raw='{"install":[],"install":[]}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            q.inventory(self.path, sha, self.lock)

    def test_reported_platform_cannot_self_authorize(self):
        report = copy.deepcopy(self.report)
        report["historical_domain"] = "RECOVERABLE"
        report["scientific_promotion_authorized"] = True
        report["environment"].update({key: "claimed" for key in q.UNESTABLISHED})
        sha = self.seal(report)
        result = q.inventory(self.path, sha, self.lock)
        self.assertEqual(result["historical_domain"], "HISTORICAL_DOMAIN_UNRESOLVED")
        self.assertFalse(result["replay_rerun_authorized"])
        self.assertFalse(result["scientific_promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
