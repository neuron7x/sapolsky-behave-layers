"""Independent admission and proof mutation contracts for EXP-06I."""
from copy import deepcopy
from fractions import Fraction as F
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as p, solver as s, run


class JointCompatibilityTests(unittest.TestCase):
    def test_shared_reference_counterexample(self):
        for b in (F(-8), F(8)):
            for direction in (-1, 1):
                with self.subTest(b=b, direction=direction):
                    result = p.marginal_conflict(b, direction)
                    self.assertEqual(result["H"]["status"], "CONDITIONAL_NARROW_ENCLOSURE")
                    self.assertEqual(result["I"]["status"], s.EXCLUDED)
                    proof = result["I"]["certificate"]
                    self.assertEqual(F(proof["lower"])-F(proof["upper"]), h.STEP)
                    self.assertIsNone(result["I"]["outer_bounds"])

    def test_witness_and_budget_are_distinct(self):
        record, _ = p.clean_record(F(-71), (F(1, 2),)*4, p.CLEAN_WORLDS[0])
        witness = s.solve(record, h.BOUNDED)
        unknown = s.solve(record, h.BOUNDED, 0)
        unverified = s.solve(record)
        self.assertEqual(witness["status"], s.WITNESS)
        self.assertEqual(unknown["status"], s.UNKNOWN)
        self.assertEqual(unverified["status"], s.UNCALIBRATED)
        self.assertTrue(s.verify(record, witness, h.BOUNDED))
        self.assertTrue(s.verify(record, unknown, h.BOUNDED, 0))
        self.assertTrue(s.verify(record, unverified))
        for result in (witness, unknown, unverified):
            self.assertIs(result["source_action_authorized"], False)
            self.assertIs(result["scientific_promotion_authorized"], False)
        self.assertTrue(witness["conditional_joint_witness_verified"])
        self.assertFalse(unknown["conditional_joint_witness_verified"])

    def test_gross_current_infeasibility(self):
        for time, code in ((0, F(900)), (60, F(-100))):
            row = p.current_conflict(time, code)
            self.assertEqual(row["I"]["status"], s.EXCLUDED)
            self.assertEqual(row["I"]["certificate"]["unresolved_leaves"], 0)
            forged = deepcopy(row["I"])
            forged["certificate"]["tree"]["reason"]["measurement"] = ["0/1", "0/1"]
            with self.assertRaises(ValueError):
                s.verify(row["record"], forged, h.BOUNDED)

    def test_root_cover_and_pruning_mutations(self):
        controls = p.negative_controls()
        self.assertEqual(len(controls["controls"]), 16)
        self.assertEqual(sum(v == "REJECTED" for v in controls["controls"].values()), 14)
        self.assertTrue(controls["three_node_frontier"])

    def test_clean_and_stress_cases(self):
        for i in (0, 15, 31):
            for j in range(2):
                self.assertEqual(p.clean_case(i, j)["I"]["status"], s.WITNESS)
                self.assertNotEqual(p.stress_case(i, j)["I"]["status"], s.EXCLUDED)


class ReceiptTests(unittest.TestCase):
    def test_same_attempt_and_exact_raw_reconstruction(self):
        args = SimpleNamespace(head="a"*40, base=run.BASE, checkout="b"*40,
                               run_id="17", attempt="2")
        expected = run.canonical({"unit_fixture": True})
        for attack in ("VALID", "WRONG_ATTEMPT", "WRONG_BASE", "WRONG_CHECKOUT",
                       "FORGED", "MISSING_REPLAY", "EXTRA_FILE", "SYMLINK"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as root:
                args.profiles = Path(root)/"profiles"
                for arch in run.ARCHES:
                    for replica in ("primary", "replay"):
                        if attack == "MISSING_REPLAY" and arch == "x86_64" and replica == "replay":
                            continue
                        folder = args.profiles/("cneh06i-"+arch)/replica
                        folder.mkdir(parents=True)
                        raw = run.canonical({"forged": True}) if attack == "FORGED" else expected
                        meta = run.metadata(args, arch, raw)
                        if arch == "x86_64" and replica == "replay":
                            if attack == "WRONG_ATTEMPT":
                                meta["run_attempt"] = "1"
                            if attack == "WRONG_BASE":
                                meta["base_sha"] = "c"*40
                            if attack == "WRONG_CHECKOUT":
                                meta["checkout_sha"] = "d"*40
                        (folder/"payload.json").write_bytes(raw)
                        (folder/"receipt.json").write_bytes(run.canonical(meta))
                target = args.profiles/"cneh06i-x86_64"/"primary"
                if attack == "EXTRA_FILE":
                    (target/"unexpected").touch()
                if attack == "SYMLINK":
                    outside = Path(root)/"outside"
                    (target/"payload.json").rename(outside)
                    (target/"payload.json").symlink_to(outside)
                if attack == "VALID":
                    self.assertEqual(len(run.verify_profiles(args, expected)), 2)
                else:
                    with self.assertRaises(ValueError):
                        run.verify_profiles(args, expected)


if __name__ == "__main__":
    unittest.main()
