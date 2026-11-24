"""Independent boundary, witness and admission tests for EXP-06G."""
from copy import deepcopy
from fractions import Fraction as F
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f import panel as f
from experiments.cneh_exp_06g import experiment as e, gauge as g, run


class JointGaugeTests(unittest.TestCase):
    def test_exact_diameter_dominates_each_coordinate(self):
        result = g.sharp_certificate()
        lo, hi = map(F, result["diameter_outer"])
        self.assertGreater(lo, F(11, 18))
        self.assertLess(hi, F(5, 8))
        self.assertLessEqual(hi-lo, F(1, 2**32))
        for name, bounds in result["coordinate_upper_bounds"].items():
            if name != "NMDA":
                self.assertGreater(lo, F(bounds[1]))
        self.assertEqual(result["noisy_upper_bound"], "NOT_ESTABLISHED")

    def test_exact_common_grid_witnesses(self):
        for name in ("ZERO_DELAY", "SHARP_DELAY"):
            with self.subTest(name=name):
                witness = g.finite_witness(name)
                left, right = witness["left"], witness["right"]
                self.assertEqual(max(abs(F(x)-F(y)) for x, y in
                                     zip(left["x"], right["x"], strict=True)),
                                 F(witness["separation"]))
                self.assertGreater(F(witness["separation"]), F(1, 16))
                for sample in witness["samples"]:
                    for side, world in (("left", left), ("right", right)):
                        exact = g.interval_current(sample["time_ms"], tuple(map(F, world["x"])),
                                                   F(world["gain"]), F(world["gamma"]),
                                                   F(world["delay_ms"]), F(witness["tau_ms"]),
                                                   F(world["offset_pA"]))
                        self.assertEqual(a.encode(exact), sample[side+"_outer_pA"])
                        code = F(sample["code_pA"])
                        self.assertLessEqual(max(abs(code-q) for q in exact), f.EPS)
                        self.assertEqual((code/F(witness["step_pA"])).denominator, 1)

    def test_complete_independent_lift_panel(self):
        rows = g.panel()
        self.assertEqual(len(rows), 48)
        self.assertEqual(sum(len(x["absolute_errors_pA"]) for x in rows), 336)
        self.assertEqual(len({tuple(x["key"]) for x in rows}), 4)

    def test_minimal_samples_scope_and_numerical_witnesses(self):
        theorem = e.theorem()
        self.assertEqual(theorem["fixed_tau_minimal_distinct_samples"], 6)
        self.assertEqual(theorem["unknown_active_tau_minimal_distinct_samples"], 7)
        self.assertEqual(theorem["noisy_or_jittered_minimal_count"], "NOT_ESTABLISHED")
        for unknown in (False, True):
            result = e.sample_witness(unknown)
            self.assertEqual(len(result["matched_times_ms"]), 6 if unknown else 5)
            self.assertGreater(F(result["extra_absolute_residual_pA"]), F(1, 10**12))
            self.assertTrue(all(F(x) <= F(1, 10**90)
                                for x in result["matched_absolute_residuals_pA"]))

    def test_negative_controls(self):
        result = e.negative_controls()
        self.assertEqual(len(result), 17)
        self.assertEqual(sum(v == "REJECTED" for v in result.values()), 12)
        self.assertEqual(result["SILENT_TAU_EQUIVALENT"], "EQUIVALENT")

    def test_full_report_fails_closed(self):
        result = e.report()
        run.validate(result)
        for field in ("scientific_promotion_authorized", "real_calibration_verified",
                      "source_action_authorized", "historical_noise_width"):
            forged = deepcopy(result)
            forged[field] = True if type(result[field]) is bool else "PASS"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "negative evidence"):
                run.validate(forged)
        forged = deepcopy(result)
        forged["minimal_samples"]["noisy_or_jittered_minimal_count"] = 7
        with self.assertRaisesRegex(ValueError, "theorem scope"):
            run.validate(forged)

    def test_faults_are_not_silently_discarded(self):
        with patch.object(g, "panel", side_effect=ValueError("intentional diagnostic failure")):
            report = e.report()
        self.assertEqual(report["qualification"], "FAIL_ENGINEERING_GATE")
        self.assertEqual(report["failures"][0]["stage"], "panel")
        self.assertIn("finite_witnesses", report)
        with self.assertRaises(ValueError):
            run.validate(report)


class ReceiptTests(unittest.TestCase):
    def test_same_attempt_or_reject(self):
        args = SimpleNamespace(head="a"*40, base=run.BASE, checkout="b"*40,
                               run_id="17", attempt="2")
        expected = run.canonical({"unit_fixture": True})
        for attack in ("VALID", "WRONG_ATTEMPT", "WRONG_CHECKOUT", "FORGED", "MISSING_REPLAY"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as root:
                args.profiles = Path(root)
                for arch in run.ARCHES:
                    for replica in ("primary", "replay"):
                        if attack == "MISSING_REPLAY" and arch == "x86_64" and replica == "replay":
                            continue
                        target = args.profiles/("cneh06g-"+arch)/replica
                        target.mkdir(parents=True)
                        raw = run.canonical({"forged": True}) if attack == "FORGED" else expected
                        metadata = run.metadata(args, arch, raw)
                        if attack == "WRONG_ATTEMPT":
                            metadata["run_attempt"] = "1"
                        if attack == "WRONG_CHECKOUT":
                            metadata["checkout_sha"] = "c"*40
                        (target/"payload.json").write_bytes(raw)
                        (target/"receipt.json").write_bytes(run.canonical(metadata))
                if attack == "VALID":
                    self.assertEqual(len(run.verify_profiles(args, expected)), 2)
                else:
                    with self.assertRaises(ValueError):
                        run.verify_profiles(args, expected)


if __name__ == "__main__":
    unittest.main()
