"""Exact independent oracle and bounded replay tests for K."""
import unittest

from experiments.cneh_exp_06k import kernel as k, panel as p


class CorrelatedReferenceTests(unittest.TestCase):
    def test_frozen_panel(self):
        result = p.report()
        self.assertEqual(result["qualification"], p.QUALIFIED, result["failures"])
        self.assertEqual(result["oracle"]["configurations"], 24480)
        self.assertEqual(result["oracle"]["failures"], [])
        self.assertEqual(set(result["negative_controls"].values()), {"REJECTED"})

    def test_empty_support_does_not_certify(self):
        def forbidden(_query):
            self.fail("must not query contradiction")
        result = k.execute("SHARED", 0, 3, 4, "ADAPTIVE", forbidden)
        self.assertEqual(result["reason"], "EMPTY_SUPPORT")
        self.assertIsNone(result["label"])
        self.assertEqual(result["spent"], 0)
        self.assertTrue(k.verify("SHARED", 0, 3, 4, "ADAPTIVE", [], result))

    def test_exact_cost_and_model_revision(self):
        self.assertEqual(k.optimum(k.initial("SHARED", 255, 3), 15)[0], 3)
        self.assertEqual(k.optimum(k.initial("INDEPENDENT", 255, 3), 15), (None, None))

    def test_strict_contract(self):
        for invalid in (True, -1, 5):
            with self.assertRaises(ValueError):
                k.execute("SHARED", 255, 3, invalid, "ADAPTIVE", lambda _: 0)


if __name__ == "__main__":
    unittest.main()
