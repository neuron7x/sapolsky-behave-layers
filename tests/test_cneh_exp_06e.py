"""Independent regression assertions for the frozen observation quotient."""
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_06e import quotient as q


class QuotientTests(unittest.TestCase):
    def test_full_continuous_families(self):
        for anchor in q.ANCHORS:
            for lo, hi in q.family_certificate(anchor):
                self.assertLessEqual(F(0), lo)
                self.assertLessEqual(lo, hi)
                self.assertLessEqual(hi, F(1))

    def test_active_gain_alias_exact(self):
        left = q.decimal_lift(q.ANCHORS[0], F(1), F(0), F(100))
        right = q.decimal_lift(q.ANCHORS[0], F(2), F(0), F(100))
        self.assertEqual(left, (F(1, 2), F(1, 4), F(1, 4), F(1, 4)))
        self.assertEqual(right, (F(1, 2), F(1, 4), F(1, 8), F(1, 4)))
        self.assertEqual(left[2], 2*right[2])

    def test_silent_rate_and_active_rate(self):
        for anchor, same in zip(q.ANCHORS, (False, True), strict=True):
            self.assertEqual(q.quotient_key(q.VOLTAGE, anchor, F(100)) ==
                             q.quotient_key(q.VOLTAGE, anchor, F(120)), same)

    def test_domain_and_key_controls(self):
        controls = q.negative_controls()
        self.assertEqual(len(controls), 14)
        self.assertEqual(sum(v == "REJECTED" for v in controls.values()), 7)
        self.assertEqual(controls["SILENT_TAU_CHANGED"], "EQUIVALENT")

    def test_graph_future_unobservability(self):
        report = q.graph_support()
        self.assertEqual(len(report["pairs"]), 16)
        self.assertEqual(set((r["past_mode"], r["future_mode"]) for r in report["pairs"]),
                         {(i, j) for i in range(4) for j in range(4)})
        self.assertEqual(report["future_support_by_past_mode"],
                         {str(i): [0, 1, 2, 3] for i in range(4)})

    def test_complete_panel_and_scope(self):
        report = q.report()
        self.assertEqual(len(report["cases"]), 54)
        self.assertEqual(sum(c["decimal_samples_checked"] for c in report["cases"]), 270)
        self.assertEqual(sorted(x["cases"] for x in report["fibers"]), [9, 9, 9, 27])
        self.assertEqual(len(report["negative_controls"]), 14)
        for flag in ("scientific_promotion_authorized", "source_action_authorized",
                     "closed_loop_authorized"):
            self.assertIs(report[flag], False)
        for name in ("historical_count_observability", "historical_nominal_ood",
                     "historical_noise_width", "historical_2ms_reachability"):
            self.assertEqual(report[name], "FAIL_PRESERVED")
        self.assertEqual(report["closed_loop_efficacy"], "BLOCKED")
        self.assertEqual(report["calibration"], "NOT_TESTED")


if __name__ == "__main__":
    unittest.main()
