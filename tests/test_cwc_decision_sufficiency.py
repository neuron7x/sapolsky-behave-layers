"""Executable falsifiers for the frozen finite decision-sufficiency contract."""
from copy import deepcopy
from fractions import Fraction as F
import unittest

from experiments.cwc_decision_sufficiency import oracle as o


class DecisionLawTests(unittest.TestCase):
    def test_loss_regret_and_uniform_decisions_are_different(self):
        m = ((0, 10), (100, 99))
        self.assertEqual(o.regret(m), ((0, 10), (1, 0)))
        self.assertEqual(o.decisions(m, 0), ())
        self.assertEqual(o.decisions(m, 1), (0,))
        self.assertEqual(o.decisions(((0, 0), (0, 0))), (0, 1))
        self.assertEqual(o.regret(m), o.regret(((0, 10), (0, -1))))

    def test_pairwise_agreement_does_not_imply_global(self):
        m = ((0, 0, 1), (1, 0, 0), (0, 1, 0))
        for i in range(3):
            self.assertTrue(o.decisions(tuple(row for j, row in enumerate(m) if i != j)))
        self.assertEqual(o.minimal_obstructions(m), ((0, 1, 2),))

    def test_input_and_empty_world_fail_closed(self):
        for call in (
            lambda: o.decisions(()),
            lambda: o.decisions(((0, 1), (0,))),
            lambda: o.decisions(((False, 1),)),
            lambda: o.decisions(((0.0, 1),)),
            lambda: o.decisions(((0, 1),), -1),
            lambda: o.optimal(((0, 1),), (("t", 0, (0,)),)),
            lambda: o.optimal(((0, 1),), (("t", 1, (True,)),)),
            lambda: o.optimal(((0, 1),), (("t", 1, (0,)), ("t", 1, (1,)))),
            lambda: o.optimal(((0, 1),)*9, ()),
            lambda: o.budget_disposition(((0, 1),), (), -1),
        ):
            with self.assertRaises(ValueError):
                call()

    def test_cost_and_abstention(self):
        m, tests = o.binary_family("XOR")
        self.assertEqual(o.optimal(m, tests)[0], F(2))
        self.assertEqual(o.greedy(m, tests), F(5))
        self.assertEqual(o.optimal(m, tests, full_id=True)[0], F(3))
        self.assertEqual(o.budget_disposition(m, tests, 0), "ABSTAIN")
        self.assertEqual(o.budget_disposition(m, tests, 1), "ABSTAIN")
        self.assertEqual(o.budget_disposition(m, tests, 2), "CONDITIONAL_PLAN_AVAILABLE")

    def test_proof_corruption(self):
        m, tests = o.binary_family("SELECTOR")
        cost, tree = o.optimal(m, tests)
        self.assertEqual(cost, F(2))
        self.assertEqual(o.static_analysis(m, tests)[0], F(3))
        self.assertTrue(o.replay(m, tests, cost, tree))
        for kind in ("missing", "impossible", "wrong_action", "repeated", "wrong_cost"):
            with self.subTest(kind=kind):
                bad, price = deepcopy(tree), cost
                if kind == "missing":
                    bad["branches"].pop()
                elif kind == "impossible":
                    bad["branches"][0]["outcome"] = 9
                elif kind == "wrong_action":
                    leaf = bad["branches"][0]["node"]["branches"][0]["node"]
                    leaf["action"] = 1-leaf["action"]
                elif kind == "repeated":
                    bad["branches"][0]["node"]["test"] = bad["test"]
                else:
                    price += 1
                with self.assertRaises(ValueError):
                    o.replay(m, tests, price, bad)

    def test_obstruction_cover_for_overlapping_regions(self):
        m = ((0, 0, 1), (1, 0, 0), (0, 1, 0))
        tests = (("distinguish_first", 2, (1, 0, 0)),
                 ("constant", 1, (0, 0, 0)))
        cost, policy = o.optimal(m, tests)
        self.assertEqual(cost, F(2))
        self.assertEqual(o.static_analysis(m, tests)[0], cost)
        self.assertTrue(o.replay(m, tests, cost, policy))


if __name__ == "__main__":
    unittest.main()
