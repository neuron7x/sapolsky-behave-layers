"""Synthetic engineering controls, not scientific evidence."""
import gzip
import io
import json
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch
import zipfile

from experiments.cwc_collision import audit as a


class CollisionTests(unittest.TestCase):
    def setUp(self):
        self.needles = {("AVeriTeC", "PRIMARY", "a"): "alpha beta",
                        ("HybridQA", "REPLICATION", "b"): "beta",
                        ("AVeriTeC", "CALIBRATION", "c"): 'caf\u00e9 "quote"'}
        self.matcher = a.ExactMatcher(self.needles)

    def test_exact_and_overlapping_needles(self):
        self.assertEqual(len(self.matcher.compare(b"prefix alpha beta suffix")), 2)
        self.assertEqual(self.matcher.compare(b"Alpha BETA"), set())
        self.assertEqual(len(self.matcher.compare(b"beta beta beta")), 1)

    def test_escaped_text(self):
        needle = self.needles[("AVeriTeC", "CALIBRATION", "c")]
        for ascii_mode in (True, False):
            self.assertEqual(len(self.matcher.compare(json.dumps(needle, ensure_ascii=ascii_mode).encode())), 1)
        self.assertEqual(len(self.matcher.compare(needle.encode())), 1)

    def test_independent_disagreement_rejected(self):
        self.matcher.reference.clear()
        with self.assertRaisesRegex(a.AuditError, "INDEPENDENT_MATCHER_DISAGREEMENT"):
            self.matcher.compare(b"beta")

    def test_nested_archive(self):
        tar = io.BytesIO()
        raw = b"alpha beta"
        with tarfile.open(fileobj=tar, mode="w") as handle:
            info = tarfile.TarInfo("fixture.txt")
            info.size = len(raw)
            handle.addfile(info, io.BytesIO(raw))
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, "w", compression=zipfile.ZIP_DEFLATED) as handle:
            handle.writestr("nested.tar.gz", gzip.compress(tar.getvalue()))
        payloads = list(a.payloads(zipped.getvalue(), "fixtures.zip", a.Budget()))
        self.assertEqual(payloads[-1][1], raw)
        self.assertEqual(len(self.matcher.compare(payloads[-1][1])), 2)

    def test_archive_error_and_budget(self):
        with self.assertRaises(zipfile.BadZipFile):
            list(a.payloads(b"broken", "fixture.zip", a.Budget()))
        with self.assertRaisesRegex(a.AuditError, "PAYLOAD_TOTAL_BUDGET"):
            list(a.payloads(b"abcd", "plain", a.Budget(max_total=3)))
        with self.assertRaisesRegex(a.AuditError, "PAYLOAD_UNIT_BUDGET"):
            list(a.payloads(b"x", "plain", a.Budget(), depth=a.MAX_DEPTH+1))

    def test_wrong_blob_rejected(self):
        with patch.object(a, "git", return_value=b"wrong"):
            with self.assertRaisesRegex(a.AuditError, "BLOB_IDENTITY_MISMATCH"):
                a.checked_blob(Path("."), "0"*40, 5)

    def test_missing_cohort_rejected(self):
        with self.assertRaisesRegex(a.AuditError, "COHORT_FAMILY_ROSTER"):
            a.bind_rosters({}, {})

    def test_cross_cohort_text_repeat_is_not_record_overlap(self):
        needles = dict(self.needles)
        needles[("AVeriTeC", "REPLICATION", "d")] = "alpha beta"
        result = a.repeated_text(needles)
        self.assertEqual(result["AVeriTeC"]["cross_cohort_groups"], 1)
        self.assertEqual(result["AVeriTeC"]["records_in_cross_cohort_groups"], 2)

    def test_missing_source_is_not_zero(self):
        with patch.object(a.intake, "analyze", return_value={"status": "NOT_TESTED"}):
            with self.assertRaisesRegex(a.AuditError, "PINNED_SOURCE_ADMISSION"):
                a.read_source_needles(Path("."))


if __name__ == "__main__":
    unittest.main()
