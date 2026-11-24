"""Independent contracts and negative controls for EXP-06F."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.cneh_exp_06c import algebra as a, fixtures
from experiments.cneh_exp_06f import channel, panel, run


class SensorChannelTests(unittest.TestCase):
    def test_quantizer_exact_ties(self):
        for value, expected in ((F(1, 8), F(0)), (F(3, 8), F(1, 2)),
                                (F(-1, 8), F(0)), (F(-3, 8), F(-1, 2))):
            self.assertEqual(panel.quantize(value, F(1, 4)), expected)

    def test_frozen_alias_certifies_both_truths(self):
        witness = panel.alias_witness()
        self.assertEqual(witness["minimum_width"], "1/12")
        self.assertEqual(witness["requested_width"], "1/16")
        self.assertEqual(witness["status"], "FAIL_WIDTH_IDENTIFIABILITY_COUNTEREXAMPLE")
        for pair in witness["worst_distances_pA"]:
            self.assertTrue(all(F(value) <= panel.EPS for value in pair))
        for name in ("left_outcomes", "right_outcomes"):
            self.assertTrue(witness[name]["WIDE_SYNTHETIC"]["truth_enclosed"])
            self.assertFalse(witness[name]["WIDE_SYNTHETIC"]["estimate"]
                             ["source_action_authorized"])

    def test_fixed_panel_contracts(self):
        scenarios = panel.scenarios()
        self.assertEqual(len(scenarios), 12)
        self.assertEqual(len(set(s.name for s in scenarios)), 12)
        self.assertEqual(len(set(panel.TRUTHS)), 16)
        self.assertEqual(len(panel.SIGNS), 2)
        self.assertEqual(sum(panel.channel_membership(s, "WIDE_SYNTHETIC")
                             for s in scenarios), 11)
        self.assertEqual(sum(panel.channel_membership(s, "IDEAL_QUANTIZED")
                             for s in scenarios), 1)
        for t in a.TIMES:
            self.assertGreater(channel.derivative_upper(t), 0)
            self.assertLess(channel.derivative_upper(t), F(7, 2))

    def test_nominal_composite_and_clipping_are_distinct(self):
        by_name = {s.name: s for s in panel.scenarios()}
        for name in ("NOMINAL", "COMPOSITE", "CLIP"):
            row = panel.panel_case(23, by_name[name], panel.SIGNS[0])
            self.assertEqual(row["bounded_wide"], name != "CLIP")
            self.assertEqual(row["bounded_ideal"], name == "NOMINAL")
            self.assertTrue(row["outcomes"]["UNVERIFIED"]["truth_enclosed"])
            if name != "CLIP":
                self.assertTrue(row["outcomes"]["WIDE_SYNTHETIC"]["truth_enclosed"])
            for outcome in row["outcomes"].values():
                self.assertIs(outcome["estimate"]["scientific_promotion_authorized"], False)

    def test_declared_negative_controls(self):
        controls = panel.negative_controls()
        self.assertEqual(len(controls), 18)
        self.assertEqual(sum(v == "REJECTED" for v in controls.values()), 12)
        self.assertEqual(sum(v == "OUTSIDE_DECLARED_HYPOTHESIS"
                             for v in controls.values()), 6)

    def test_clock_envelope_is_not_optional(self):
        truth = (F(0), F(1), F(0), F(0))
        profile = replace(channel.PROFILES["IDEAL_QUANTIZED"], jitter=F(1))
        observed = [panel.quantize(fixtures.current(F(t)+1, truth), panel.FINE)
                    for t in a.TIMES]
        with patch.dict(channel.PROFILES, {"ISOLATED_TEST": profile}):
            panel.certify_compatibility(truth, observed, "ISOLATED_TEST")
            with patch.object(channel, "derivative_upper", return_value=F(0)):
                with self.assertRaisesRegex(ValueError, "dewarped nominal current excluded"):
                    panel.certify_compatibility(truth, observed, "ISOLATED_TEST")

    def test_quantization_envelope_is_not_optional(self):
        truth = (F(0),)*4
        observed = [panel.quantize(fixtures.current(F(t), truth), panel.COARSE)
                    for t in a.TIMES]
        profile = replace(channel.PROFILES["IDEAL_QUANTIZED"], quantization=panel.COARSE)
        with patch.dict(channel.PROFILES, {"ISOLATED_TEST": profile}):
            panel.certify_compatibility(truth, observed, "ISOLATED_TEST")
        with patch.dict(channel.PROFILES, {"ISOLATED_TEST": replace(profile, quantization=F(0))}):
            with self.assertRaisesRegex(ValueError, "dewarped nominal current excluded"):
                panel.certify_compatibility(truth, observed, "ISOLATED_TEST")

    def test_gain_offset_and_drift_cannot_be_silently_removed(self):
        truth = (F(1, 2),)*4
        gain, offset, drift = F(9, 8), F(-16), F(1)
        observed = [panel.quantize(gain*fixtures.current(F(t), truth)+offset+
                                   drift*F(t, 120), panel.FINE) for t in a.TIMES]
        profile = replace(channel.PROFILES["IDEAL_QUANTIZED"],
                          gain=a.point(gain), offset=a.point(offset), drift=a.point(drift))
        with patch.dict(channel.PROFILES, {"ISOLATED_TEST": profile}):
            panel.certify_compatibility(truth, observed, "ISOLATED_TEST")
        for field, value in (("gain", a.point(1)), ("offset", a.point(0)),
                             ("drift", a.point(0))):
            with self.subTest(field=field):
                mutated = replace(profile, **{field: value})
                with patch.dict(channel.PROFILES, {"ISOLATED_TEST": mutated}):
                    with self.assertRaisesRegex(ValueError, "dewarped nominal current excluded"):
                        panel.certify_compatibility(truth, observed, "ISOLATED_TEST")

    def test_analog_noise_cannot_be_silently_removed(self):
        truth = (F(1, 2),)*4
        observed = [panel.quantize(fixtures.current(F(t), truth)+F(3, 4)*panel.EPS,
                                   panel.FINE) for t in a.TIMES]
        correct = channel.dewarp(observed, panel.EPS, "IDEAL_QUANTIZED")
        faulty = channel.dewarp(observed, F(0), "IDEAL_QUANTIZED")
        for t, good, bad in zip(a.TIMES, correct, faulty, strict=True):
            exact = a.current_interval(t, truth)
            self.assertTrue(panel.contains_interval(good, exact))
            self.assertFalse(panel.contains_interval(bad, exact))


class EvidenceTests(unittest.TestCase):
    def test_identity_and_recomputed_forgery(self):
        args = SimpleNamespace(head="a"*40, base=run.BASE, checkout="b"*40,
                               run_id="17", attempt="2")
        expected = run.canonical({"synthetic_unit_fixture": True})
        for name in ("valid", "wrong_attempt", "forged_all", "missing_replay",
                     "extra_file", "symlink"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                args.profiles = Path(directory)/"profiles"
                for arch in run.ARCHES:
                    for replica in ("primary", "replay"):
                        root = args.profiles/("cneh06f-"+arch)/replica
                        root.mkdir(parents=True)
                        raw = (run.canonical({"forged": True}) if name == "forged_all"
                               else expected)
                        receipt = run.metadata(args, arch, raw)
                        if name == "wrong_attempt" and arch == "x86_64" and replica == "replay":
                            receipt["run_attempt"] = "1"
                        (root/"payload.json").write_bytes(raw)
                        (root/"receipt.json").write_bytes(run.canonical(receipt))
                target = args.profiles/"cneh06f-x86_64"/"replay"
                if name == "missing_replay":
                    shutil.rmtree(target)
                elif name == "extra_file":
                    (target/"extra").touch()
                elif name == "symlink":
                    outside = Path(directory)/"outside.json"
                    (target/"payload.json").rename(outside)
                    (target/"payload.json").symlink_to(outside)
                if name == "valid":
                    self.assertEqual(len(run.verify_profiles(args, expected)), 2)
                else:
                    with self.assertRaises(ValueError):
                        run.verify_profiles(args, expected)

    def test_negative_evidence_cannot_be_reclassified(self):
        value = {"qualification": run.QUALIFIED, "failures": [], **panel.NEGATIVE}
        for key in ("scientific_promotion_authorized", "source_action_authorized",
                    "historical_noise_width", "calibration"):
            forged = deepcopy(value)
            forged[key] = True if type(value[key]) is bool else "PASS"
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "negative evidence"):
                run.validate_report(forged)
        failed = dict(value, failures=[{"error": "test"}])
        with self.assertRaisesRegex(ValueError, "not qualified"):
            run.validate_report(failed)


if __name__ == "__main__":
    unittest.main()
