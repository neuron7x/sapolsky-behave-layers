"""Real evidence checker negative controls, not a positive promotion issuer."""
import tempfile
from pathlib import Path
import unittest

from scripts import cneh_evidence_admission as a
from scripts import cneh_evidence_ratchet as r


class EvidenceRatchetTests(unittest.TestCase):
    def test_all_seven_families(self):
        report=r.campaign(777)
        self.assertEqual(report["case_count"],168)
        self.assertTrue(report["all_attacks_pass"],[x for x in report["records"] if x["disposition"]!="REJECTED_EXPECTED"])
        self.assertEqual(report["family_counts"],{k:{"cases":24,"rejected":24} for k in r.FAMILIES})
        self.assertIs(report["scientific_promotion_authorized"],False)

    def test_strict_stream_rejects_duplicate_and_overflow(self):
        import gzip
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"test.gz"
            for text in (b'[{"a":1,"a":2}]',b'[{"a":1e400}]',b'[{"a":1},]',b'[{"a":1}]\n{}'):
                path.write_bytes(gzip.compress(text,mtime=0))
                with self.assertRaises(a.EvidenceViolation) as ctx:
                    list(a.strict_array(path))
                self.assertEqual(ctx.exception.code,"ENCODING")

    def test_replay_cannot_accept_resigned_data(self):
        contract,files=r.fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"bundle"
            r.write_fixture(root,files)
            before=a.snapshot(root,contract["names"])
            r.mutate(root,"REPLAY",["preregistration.md",0])
            with self.assertRaises(a.EvidenceViolation) as ctx:
                a.admit(root,contract,before)
            self.assertEqual(ctx.exception.code,"REPLAY")
