"""Known-answer counterexamples for post-primary temporal diagnostics."""
from __future__ import annotations

import math
import unittest

from experiments.cneh_exp_03 import post_primary_audit as audit


class TestTemporalAudit(unittest.TestCase):
    def test_equal_totals_can_hide_temporal_interaction(self):
        d = {
            "SHAM_BASE": [1, 0, 0],
            "SHAM_PROBE_A": [0, 1, 0],
            "CUT_AB_BASE": [1, 0, 0],
            "CUT_AB_PROBE_A": [1, 0, 0],
        }
        x = audit.temporal_contrast(d)
        self.assertTrue(x["all_arm_totals_equal"])
        self.assertEqual(x["terminal_factorial_count"], 0)
        self.assertEqual(x["instantaneous_factorial_counts"], [-1, 1, 0])
        self.assertEqual(x["max_abs_cumulative_factorial_count"], 1)
        self.assertTrue(x["endpoint_null_hides_temporal_interaction"])

    def test_exact_temporal_null_is_not_promoted(self):
        x = audit.temporal_contrast({arm: [0, 1, 0] for arm in audit.ARMS})
        self.assertEqual(x["sum_abs_instantaneous_factorial_counts"], 0)
        self.assertFalse(x["nonzero_temporal_interaction"])

    def test_missing_arms_and_invalid_counts_rejected(self):
        with self.assertRaises(ValueError):
            audit.temporal_contrast({"SHAM_BASE": [0]})
        for value in (-1, True, 0.5):
            d = {arm: [0] for arm in audit.ARMS}
            d["SHAM_BASE"] = [value]
            with self.assertRaises(ValueError):
                audit.temporal_contrast(d)

    def test_nonintegral_probe_window_has_dc_and_balanced_reference(self):
        original = [80. * math.sin(2 * math.pi * t / 80) for t in range(600)]
        result = audit.probe_diagnostics(original, 300., 500., 0.1)
        self.assertGreater(result["original_mean_offset_pA"], 0.)
        self.assertAlmostEqual(result["future_reference_mean_offset_pA"], 0., places=10)
        self.assertAlmostEqual(
            result["original_probe_l2_pA2_ticks"],
            result["future_reference_probe_l2_pA2_ticks"],
            places=7,
        )
        self.assertFalse(result["reference_used_in_primary"])
        self.assertFalse(result["physical_energy_qualified"])

    def test_degenerate_or_nonfinite_probe_fails_closed(self):
        for values in ([1., 1.], [float("nan")], []):
            with self.assertRaises(ValueError):
                audit.mean_free_reference(values)
        self.assertEqual(audit.mean_free_reference([0., 0.]), [0., 0.])

    def test_reference_cannot_bypass_current_bounds(self):
        with self.assertRaisesRegex(ValueError, "input envelope"):
            audit.probe_diagnostics([200., 0., -200.], 300., 350., 0.1)


if __name__ == "__main__":
    unittest.main()
