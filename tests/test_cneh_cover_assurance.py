"""Targeted falsifiers for the bounded mathematical cover, not all-world sampling."""
from copy import deepcopy
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as ip, solver as old
from experiments.cneh_cover_assurance import cover as c, panel as p, verifier as v


class CoverAssuranceTests(unittest.TestCase):
    def test_independent_alternating_decay_contains_frozen_taylor(self):
        for u in (F(0), F(1, 2), F(5, 2), F(93, 25), F(40), F(99), F(100)):
            with self.subTest(u=u):
                lo, hi = c.decay(u)
                lower, upper = a.exponential(-u)
                self.assertLessEqual(lo, lower)
                self.assertLessEqual(upper, hi)

    def test_exact_quantizer_parity_and_closed_noise_relaxation(self):
        self.assertEqual(len(p.quantizer_panel()), 54)

    def test_extreme_noise_and_full_budget_nested_cover(self):
        row = p.extreme_case(0, 0, -1)
        self.assertEqual([q["node_budget"] for q in row["proofs"]], [0, 1, 7, 63])
        for proof in row["proofs"]:
            self.assertEqual(proof["status"], c.OUTER)
            self.assertIs(proof["joint_existence_established"], False)
            self.assertLessEqual(proof["nodes"], proof["node_budget"])

    def test_subtle_infeasibility_requires_contraction(self):
        for sign in (-1, 1):
            with self.subTest(sign=sign):
                row = p.subtle_case(sign)
                self.assertEqual(row["legacy"]["status"], old.UNKNOWN)
                self.assertEqual(row["proof"]["status"], c.EXCLUDED)
                self.assertEqual(row["proof"]["nodes"], 1)

    def test_reference_contradiction_valid_even_at_zero_search_budget(self):
        record = ip.marginal_conflict(F(8), 1)["record"]
        proof = c.solve(record, h.BOUNDED, 0)
        self.assertTrue(v.verify(record, proof, h.BOUNDED, 0))
        self.assertEqual(proof["status"], c.EXCLUDED)
        self.assertEqual(proof["tree"]["kind"], "REFERENCE_EMPTY")
        self.assertIsNone(proof["physical_hull"])

    def test_arbitrary_preconditioner_does_not_need_invertibility(self):
        record, _ = ip.clean_record(F(-71), (F(1, 2),)*4, ip.CLEAN_WORLDS[0])
        _, observed, refs = h.parse(record)
        root, contradiction = old.root_box(refs)
        self.assertIsNone(contradiction)
        rows = c.affine_rows(root[4:])
        zero = ((F(0),)*4,)*4
        tree, frontier, count = c.search(root[:4], rows, zero, observed, 1)
        proof = c.result(record, h.BOUNDED, 1, c.OUTER, root, rows,
                         zero, tree, frontier, count)
        self.assertTrue(v.verify(record, proof, h.BOUNDED, 1))
        self.assertEqual(proof["max_width"], "1/1")
        self.assertTrue(any(p.contains(box, (F(1, 2),)*4) for box in proof["frontier"]))
        bad = deepcopy(proof)
        bad["status"] = c.EXCLUDED
        with self.assertRaises(ValueError):
            v.verify(record, bad, h.BOUNDED, 1)

    def test_all_fixed_proof_mutations(self):
        controls = p.controls()
        self.assertEqual(len(controls["mutations"]), 22)
        self.assertEqual(set(controls["mutations"].values()), {"REJECTED"})
        self.assertEqual(controls["zero"]["nodes"], 0)
        self.assertEqual(controls["unverified"]["status"], c.UNCALIBRATED)


if __name__ == "__main__":
    unittest.main()
