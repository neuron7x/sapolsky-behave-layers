"""Independent finite oracle and receipt attacks for J."""
import unittest

from experiments.cneh_exp_06j import kernel as k, panel as p


class AcquisitionTests(unittest.TestCase):
    def test_complete_finite_oracle(self):
        self.assertEqual(p.exact_panel(), {"DP_cases": 2040,
                                           "cube_adaptive_cost": 2,
                                           "cube_best_fixed_cost": 3})

    def test_query_relevance(self):
        support = ((0, 0, 0), (0, 1, 0), (0, 0, 1), (0, 1, 1))
        self.assertEqual(k.optimum(support, k.QUERIES), (1, 1))
        self.assertEqual(k.optimum(support, (3,)), (None, None))
        self.assertEqual(k.optimum(((0, 0, 0), (1, 1, 0)), k.QUERIES), (0, None))

    def test_all_proof_mutations(self):
        self.assertEqual(set(p.controls().values()), {"REJECTED"})


if __name__ == "__main__":
    unittest.main()
