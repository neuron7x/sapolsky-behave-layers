"""Exact electronic support and conditional-decision regression contracts."""
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_06h import reference as h
from experiments.cneh_cover_assurance import correlated_decision as d
from experiments.cneh_cover_assurance import correlated_panel as p


class CorrelatedDecisionTests(unittest.TestCase):
    def test_support_and_independent_vertices(self):
        panel = p.support_panel()
        self.assertEqual(len(panel["comparisons"]), 450)
        self.assertGreater(panel["strict_improvements"], 0)
        self.assertEqual(panel["analytic_width_ratio"], "23/8")
        self.assertTrue(panel["empty_polytope"])
        self.assertEqual(panel["degenerate_checks"], 15)

    def test_opposing_witnesses_are_not_a_common_decision(self):
        row = p.pair_witness()
        proof = row["decision"]
        self.assertEqual(proof["witness_count"], 2)
        self.assertEqual(proof["status"], "NO_EPSILON_ACTION")
        self.assertEqual(proof["excluded_actions"], [0, 1])
        self.assertEqual([F(x[0]) for x in proof["bounds"]], [F(1, 2**19)]*2)
        self.assertIs(proof["source_action_authorized"], False)

    def test_revocation_and_admission_controls(self):
        result = p.controls()["dispositions"]
        self.assertEqual(result["NO_WITNESS"], "UNKNOWN")
        self.assertEqual(result["ZERO_BUDGET"], "UNKNOWN")
        self.assertEqual(result["UNVERIFIED"], "UNKNOWN")
        self.assertEqual(result["TIE"], "MULTIPLE_CERTIFIED")
        self.assertEqual(sum(v == "REJECTED" for v in result.values()), 18)

    def test_affine_endpoint_and_corner_oracles(self):
        for coeff in ((1, -2, 3, 0, -1), (-1, 2, -3, 4, 0)):
            row = tuple(map(F, coeff))
            box = ((F(0), F(1)), (F(1, 4), F(3, 4)),
                   (F(1, 2), F(1, 2)), (F(0), F(3, 4)))
            self.assertEqual(d.affine_max(row, box), d.corner_max(row, box))

    def test_full_joint_support_tightening(self):
        codes = F(0), F(128), F(0)
        current = F(120), F(120)
        self.assertEqual(d.support(codes, current, 0), (120-h.R, 120+h.R))
        self.assertEqual(d.vertex_support(codes, current, 0), d.support(codes, current, 0))


if __name__ == "__main__":
    unittest.main()
