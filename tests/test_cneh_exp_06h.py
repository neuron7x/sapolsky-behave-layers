"""Independent numerical, ablation and admission contracts for EXP-06H."""
from copy import deepcopy
from fractions import Fraction as F
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.cneh_exp_06c import fixtures
from experiments.cneh_exp_06h import panel as p, reference as h, run


class ReferenceAssuranceTests(unittest.TestCase):
    def test_continuous_tau_cover_and_width_bound(self):
        cert = h.diameter_certificate()
        self.assertEqual(len(cert["full_tau_cover"]), 19)
        for i, cell in enumerate(cert["full_tau_cover"], 100):
            self.assertEqual(list(map(F, cell["tau_ms"])), [i, i+2])
            self.assertLess(F(cell["eta_upper"]), 1)
        self.assertGreater(F(cert["margin_lower"]), 0)
        self.assertLessEqual(F(cert["max_diameter_upper"]), F(1, 16))
        self.assertEqual(F(cert["target"])-F(cert["max_diameter_upper"]),
                         F(cert["margin_lower"]))
        self.assertFalse(cert["real_calibration_verified"])

    def test_exact_inverse_and_reference_boundaries(self):
        for truth in (0, 15, 16):
            for nuisance in (p.worlds()[0], p.worlds()[-2], p.worlds()[-1]):
                for sign in p.SIGNS:
                    row = p.panel_case(truth, nuisance, sign)
                    self.assertTrue(p.contains(row["estimate"], tuple(map(F, row["truth"]))))
                    self.assertLessEqual(F(row["estimate"]["max_width"]), F(1, 16))
                    self.assertEqual(row["unverified"]["status"], "CALIBRATION_UNVERIFIED")

    def test_frozen_alias_is_not_erased(self):
        witness = p.gamma_ablation()
        self.assertEqual(witness["separation"], "1/2")
        for sample in witness["samples"]:
            self.assertTrue(all(F(x) <= h.E for x in sample["worst_errors_pA"]))
        self.assertGreater(abs(F(witness["gamma_reference_codes"][0])-
                               F(witness["gamma_reference_codes"][1])), 2*h.R)
        recovered = p.g_witness_recovery()["reference_assisted_recovery"]
        self.assertEqual(len(recovered), 2)
        for row in recovered:
            self.assertTrue(row["other_truth_excluded"])
            self.assertFalse(row["estimate"]["scientific_promotion_authorized"])

    def test_negative_controls(self):
        controls = p.negative_controls()
        self.assertEqual(len(controls), 21)
        self.assertEqual(sum(v == "REJECTED" for v in controls.values()), 13)
        self.assertEqual(sum(v == "INCONSISTENT_REFERENCE" for v in controls.values()), 6)

    def test_failed_panel_preserves_failure_and_blocks_admission(self):
        with patch.object(p, "panel_case", side_effect=ValueError("injected failure")):
            result = p.report()
        self.assertEqual(result["qualification"], "FAIL_ENGINEERING_GATE")
        self.assertEqual(sum(x["stage"] == "panel" for x in result["failures"]), 272)
        self.assertIn("gamma_ablation", result)
        with self.assertRaisesRegex(ValueError, "admission failed"):
            run.validate(result)

    def test_authority_requires_neither_self_attestation_nor_narrowness(self):
        v, x = fixtures.truth(16)
        record, _, _ = p.make_record(v, x, F(1), F(3, 2), F(1, 2), F(110),
                                    F(0), F(0), 1)
        for profile in ("UNVERIFIED", h.BOUNDED):
            result = h.estimate(record, profile)
            for flag in ("scientific_promotion_authorized", "source_action_authorized",
                         "real_calibration_verified", "closed_loop_authorized",
                         "joint_feasibility_proven"):
                self.assertIs(result[flag], False)
        forged = deepcopy(record)
        forged["scientific_promotion_authorized"] = True
        with self.assertRaises(ValueError):
            h.estimate(forged, h.BOUNDED)


class ReceiptTests(unittest.TestCase):
    def test_same_attempt_exact_identity_and_payload(self):
        args = SimpleNamespace(head="a"*40, base=run.BASE, checkout="b"*40,
                               run_id="17", attempt="2")
        expected = run.canonical({"unit_fixture": True})
        for attack in ("VALID", "WRONG_ATTEMPT", "WRONG_HEAD", "WRONG_CHECKOUT",
                       "FORGED", "MISSING_REPLAY", "EXTRA_FILE", "SYMLINK"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as root:
                args.profiles = Path(root)/"profiles"
                for arch in run.ARCHES:
                    for replica in ("primary", "replay"):
                        if attack == "MISSING_REPLAY" and arch == "x86_64" and replica == "replay":
                            continue
                        target = args.profiles/("cneh06h-"+arch)/replica
                        target.mkdir(parents=True)
                        raw = run.canonical({"forged": True}) if attack == "FORGED" else expected
                        meta = run.metadata(args, arch, raw)
                        if arch == "x86_64" and replica == "replay":
                            if attack == "WRONG_ATTEMPT":
                                meta["run_attempt"] = "1"
                            if attack == "WRONG_HEAD":
                                meta["head_sha"] = "c"*40
                            if attack == "WRONG_CHECKOUT":
                                meta["checkout_sha"] = "d"*40
                        (target/"payload.json").write_bytes(raw)
                        (target/"receipt.json").write_bytes(run.canonical(meta))
                target = args.profiles/"cneh06h-x86_64"/"primary"
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

    def test_negative_scientific_evidence_cannot_be_promoted(self):
        value = {"qualification": p.QUALIFIED, "failures": [], "scope": h.SCOPE, **h.NEGATIVE}
        for field in ("scientific_promotion_authorized", "historical_joint_gauge",
                      "calibration", "joint_feasibility_proven"):
            forged = dict(value)
            forged[field] = True if type(value[field]) is bool else "PASS"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "negative evidence"):
                run.validate(forged)


if __name__ == "__main__":
    unittest.main()
