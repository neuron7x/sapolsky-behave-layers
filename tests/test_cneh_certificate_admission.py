"""Regression tests for type-confusion and bounded certificate admission."""
from copy import deepcopy
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_06f.run import canonical
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as p, solver as i
from experiments.cneh_exp_06j import kernel as j
from scripts import cneh_certificate_admission as admission


class CertificateAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record, _ = p.clean_record(F(-71), (F(1, 2),)*4, p.CLEAN_WORLDS[0])
        cls.valid = i.solve(cls.record, h.BOUNDED)
        if cls.valid["status"] != i.WITNESS:
            raise ValueError("frozen witness fixture failed")
        cls.zero = i.solve(cls.record, h.BOUNDED, 0)
        cls.gross = deepcopy(cls.record)
        cls.gross["samples"][0]["current_pA"] = "900/1"
        cls.excluded = i.solve(cls.gross, h.BOUNDED)
        cls.contradiction = p.marginal_conflict(F(8), 1)

    def admit(self, record, proof, budget=i.MAX_NODES, profile=h.BOUNDED):
        return admission.verify_i(canonical(record), canonical(proof),
                                  profile=profile, budget=budget)

    def test_positive_certificate_roster(self):
        for record, proof, budget, profile in (
            (self.record, self.valid, i.MAX_NODES, h.BOUNDED),
            (self.record, self.zero, 0, h.BOUNDED),
            (self.gross, self.excluded, i.MAX_NODES, h.BOUNDED),
            (self.contradiction["record"], self.contradiction["I"], i.MAX_NODES, h.BOUNDED),
            (self.record, i.solve(self.record), i.MAX_NODES, "UNVERIFIED"),
        ):
            self.assertTrue(self.admit(record, proof, budget, profile))

    def test_legacy_type_confusion_witness(self):
        forged = deepcopy(self.valid)
        forged["certificate"]["witness"]["samples"][0]["t_ms"] = False
        self.assertNotEqual(canonical(self.valid), canonical(forged))
        # The frozen legacy comparison accepts this exact wrong wire type.
        self.assertIs(i.verify(self.record, forged, h.BOUNDED), True)
        with self.assertRaises(admission.CertificateError):
            self.admit(self.record, forged)

    def test_legacy_type_confusion_exclusion(self):
        self.assertEqual(self.excluded["status"], i.EXCLUDED)
        forged = deepcopy(self.excluded)
        reason = forged["certificate"]["tree"]["reason"]
        self.assertEqual(reason["t_ms"], 0)
        reason["t_ms"] = False
        self.assertIs(i.verify(self.gross, forged, h.BOUNDED), True)
        with self.assertRaises(admission.CertificateError):
            self.admit(self.gross, forged)

    def test_legacy_type_confusion_frontier(self):
        self.assertEqual(self.zero["status"], i.UNKNOWN)
        forged = deepcopy(self.zero)
        self.assertEqual(forged["certificate"]["unresolved_leaves"], 1)
        forged["certificate"]["unresolved_leaves"] = True
        self.assertIs(i.verify(self.record, forged, h.BOUNDED, 0), True)
        with self.assertRaises(admission.CertificateError):
            self.admit(self.record, forged, 0)

    def test_semantically_incompatible_proof_mutations(self):
        for attack in ("coordinate", "reference", "current", "missing_world",
                       "extra_field", "wrong_identity", "false_status", "authority"):
            with self.subTest(attack=attack):
                forged = deepcopy(self.valid)
                witness = forged["certificate"]["witness"]
                if attack == "coordinate":
                    witness["world"][7] = "2/1"
                elif attack == "reference":
                    witness["reference_errors"]["gamma"] = "1/1"
                elif attack == "current":
                    witness["samples"][1]["clean_outer_pA"] = ["0/1", "0/1"]
                elif attack == "missing_world":
                    witness["world"].pop()
                elif attack == "extra_field":
                    witness["extra"] = "unknown"
                elif attack == "wrong_identity":
                    forged["record_sha256"] = "0"*64
                elif attack == "false_status":
                    forged["status"] = i.EXCLUDED
                else:
                    forged["scientific_promotion_authorized"] = True
                with self.assertRaises(admission.CertificateError):
                    self.admit(self.record, forged)

    def test_bounded_canonical_wire_rejects(self):
        values = (
            b'{"x":0,"x":1}\n', b'{"x":1.0}\n', b'{"x":NaN}\n',
            b'{"x":1e0}\n', b'{"x":2147483648}\n', b'{"x":0}',
            b'{"x": 0}\n', b'[]\n', b'{"x":"\xff"}\n',
            b'{"x":'+b'['*33+b'0'+b']'*33+b'}\n',
            canonical({"x": "s"*(admission.MAX_STRING+1)}),
            canonical({"x": [0]*admission.MAX_ITEMS}),
            b' '* (admission.MAX_BYTES+1),
        )
        for index, raw in enumerate(values):
            with self.subTest(index=index), self.assertRaises(admission.CertificateError):
                admission.verify_i(canonical(self.record), raw, profile=h.BOUNDED)

    def test_j_replay_and_cross_boundary(self):
        for mode in ("ADAPTIVE", "PASSIVE", j.FIXED[0]):
            receipt = j.execute(self.record, self.valid, h.BOUNDED, 2, mode, lambda _: 1)
            self.assertTrue(admission.verify_j(canonical(self.record), canonical(self.valid),
                            canonical(receipt), profile=h.BOUNDED, budget=2, mode=mode))
            wrong = deepcopy(receipt)
            wrong["spent"] = -1
            with self.assertRaises(admission.CertificateError):
                admission.verify_j(canonical(self.record), canonical(self.valid),
                                   canonical(wrong), profile=h.BOUNDED, budget=2, mode=mode)
        forged = deepcopy(self.valid)
        forged["certificate"]["witness"]["samples"][0]["t_ms"] = False
        receipt = j.execute(self.record, forged, h.BOUNDED, 0, "PASSIVE", lambda _: 1)
        self.assertTrue(j.verify(self.record, forged, h.BOUNDED, 0, "PASSIVE", receipt))
        with self.assertRaises(admission.CertificateError):
            admission.verify_j(canonical(self.record), canonical(forged), canonical(receipt),
                               profile=h.BOUNDED, budget=0, mode="PASSIVE")

    def test_j_policy_type_confusion(self):
        mode = (2, True, 3)
        receipt = j.execute(self.record, self.valid, h.BOUNDED, 0, mode, lambda _: 1)
        self.assertTrue(j.verify(self.record, self.valid, h.BOUNDED, 0, mode, receipt))
        with self.assertRaises(admission.CertificateError):
            admission.verify_j(canonical(self.record), canonical(self.valid), canonical(receipt),
                               profile=h.BOUNDED, budget=0, mode=mode)


if __name__ == "__main__":
    unittest.main()
