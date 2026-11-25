"""Read-only source intake regression checks. No external fixture masquerades as data."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from experiments.real_transfer_01 import source_intake as s


class IntakeTests(unittest.TestCase):
    def test_exact_blob_binding(self):
        raw = b'{"value":1}\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"source.json"
            path.write_bytes(raw)
            value, meta = s.exact_blob(path, 1024, s.git_blob(raw), s.digest(raw))
            self.assertEqual(value, {"value": 1})
            self.assertEqual(meta["byte_length"], len(raw))
            with self.assertRaises(s.IntakeError):
                s.exact_blob(path, 1024, "0"*40)
            with self.assertRaises(s.IntakeError):
                s.exact_blob(path, 1024, s.git_blob(raw), "0"*64)
            with self.assertRaises(s.IntakeError):
                s.exact_blob(path, 1, s.git_blob(raw))
            alias = Path(directory)/"alias.json"
            alias.symlink_to(path)
            with self.assertRaises(s.IntakeError):
                s.exact_blob(alias, 1024, s.git_blob(raw))

    def test_strict_source_json(self):
        for raw in (b'{"a":0,"a":1}', b'{"a":NaN}', b'{"a":1e999}',
                    b'{"a":"\xff"}', b'{"a":'):
            with self.subTest(raw=raw), self.assertRaises(s.IntakeError):
                s.parse(raw)

    def test_table_identity_and_link_resolution(self):
        table = {"uid": "example", "header": [["column", []]],
                 "data": [[["cell", ["/wiki/entry"]]]]}
        self.assertEqual(s.validate_modalities(table, {"/wiki/entry": "passage"}, "example"), 1)
        for bad in ({}, {"/wiki/entry": 1}):
            with self.assertRaises(s.IntakeError):
                s.validate_modalities(table, bad, "example")
        with self.assertRaises(s.IntakeError):
            s.validate_modalities(table, {"/wiki/entry": "passage"}, "other")
        for key in ("", "../other", ".", "a/b", "a\\b", "\x00", None):
            with self.subTest(key=key), self.assertRaises(s.IntakeError):
                s.table_key(key)

    def test_zip_exact_member_and_traversal(self):
        name = s.WIKI_PREFIX+"/tables_tok/example.json"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"fixture.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(name, '{"uid":"example"}')
            with zipfile.ZipFile(path) as z:
                index = s.archive_index(z)
                usage = [0]
                value, receipt = s.member(z, index, name, usage)
                self.assertEqual(value, {"uid": "example"})
                self.assertEqual(usage[0], receipt["byte_length"])
                with self.assertRaises(s.IntakeError):
                    s.member(z, index, name+"x", usage)
                with self.assertRaises(s.IntakeError):
                    s.member(z, index, name, [s.MAX_SELECTED])
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(s.WIKI_PREFIX+"/../escape", "invalid")
            with zipfile.ZipFile(path) as z, self.assertRaises(s.IntakeError):
                s.archive_index(z)

    def test_amended_averitec_cohort_contract(self):
        records = []
        for label, n in (("Refuted",305), ("Supported",122),
                         ("Not Enough Evidence",35), ("Conflicting Evidence/Cherrypicking",38)):
            records.extend({"claim": f"synthetic-fixture-{label}-{i}", "label": label,
                            "questions": [{"question": "fixture question",
                                           "answers": [{"answer":"fixture answer"}]}]}
                           for i in range(n))
        bound, _ = s.av_cohorts(records)
        self.assertEqual([bound[n]["count"] for n in ("CALIBRATION","PRIMARY","REPLICATION")],
                         [99,199,202])
        self.assertEqual(s.av_cohorts(list(reversed(records)))[0], bound)
        duplicate = list(records)
        duplicate[1] = duplicate[0]
        with self.assertRaises(ValueError):
            s.av_cohorts(duplicate)

    def test_missing_source_fails_without_scientific_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            report = s.analyze(Path(directory))
        self.assertEqual(report["status"], "NOT_TESTED")
        self.assertEqual(len(report["source_blockers"]), 3)
        self.assertEqual(report["sources"], [])
        self.assertEqual(report["cohorts"], {})
        self.assertIs(report["scientific_promotion_authorized"], False)
        self.assertEqual(report["real_model_execution"], "NOT_RUN")
        self.assertTrue(report["execution_blockers"])


if __name__ == "__main__":
    unittest.main()
