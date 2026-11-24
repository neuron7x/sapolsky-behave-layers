"""Adversarial tests for finite selector; never native efficacy evidence."""
from __future__ import annotations

from dataclasses import replace
from itertools import product
import unittest

from experiments.cneh_exp_05s import selector as s


class TestFiniteSelector(unittest.TestCase):
    def fixture(self, name):
        return next(f for f in s.FIXTURES if f.name == name)

    def test_frozen_roster(self):
        report = s.report()
        self.assertFalse(report["scientific_promotion_authorized"])
        self.assertEqual(report["native_replay"], "NOT_TESTED")
        self.assertEqual(len(report["fixtures"]), 8)
        self.assertEqual(len(s.PLANS), 27)
        for result in report["fixtures"]:
            self.assertEqual(len(result["plans"]), 27)
            self.assertEqual(result["equivalence_pair_checks"], 27 * result["scenarios"] ** 2)
        selected = {r["fixture"]: tuple(r["selected"]) for r in report["fixtures"]}
        self.assertEqual(selected["INFORMATIVE"], (-1, -1, 0))
        self.assertEqual(selected["RECOVERY"], (-1, -1, 0))
        self.assertEqual(selected["ERASED"], (-1, -1, 0))
        for key in ("SILENT", "REVIVAL", "SINGLETON", "ALIAS_NO_BUDGET"):
            self.assertEqual(selected[key], s.WAIT)

    def test_adaptation_recovery(self):
        f = self.fixture("RECOVERY")
        scenario = s.roster(f)[0]
        early, early_w = s.observe(scenario, (0, -1, -1))
        late, late_w = s.observe(scenario, (-1, -1, 0))
        self.assertEqual([x[0] for x in early], [0, 0, 0])
        self.assertEqual([x[0] for x in late], [0, 0, 1])
        self.assertGreater(late_w[0], early_w[0])

    def test_final_switch_reopens_all_modes(self):
        f = self.fixture("REVIVAL")
        scenarios = s.roster(f)
        for plan in s.PLANS:
            self.assertTrue(all(v == s.ALL for v in s.supports(scenarios, plan)))

    def test_silent_and_aliased_support(self):
        for name in ("SILENT",):
            f = self.fixture(name)
            self.assertEqual(s.evaluate(f)["selected"], list(s.WAIT))
        f = s.fixture("ALIAS_SYNTHETIC_TEST", drives=((100, 100),))
        result = s.evaluate(f)
        self.assertEqual(result["selected"], list(s.WAIT))
        self.assertTrue(all(x["worst_paired_gain"] == 0 for x in result["plans"]))

    def test_observational_twins_no_latent_disambiguation(self):
        f = self.fixture("INFORMATIVE")
        scenarios = s.roster(f)
        obs = [s.observe(x, s.WAIT)[0] for x in scenarios]
        self.assertEqual(len(set(obs)), 1)
        self.assertEqual(s.supports(scenarios, s.WAIT), (s.ALL,) * len(scenarios))

    def test_order_and_incomplete_scenarios(self):
        f = self.fixture("ERASED")
        roster = s.roster(f)
        self.assertEqual(s.evaluate(f), s.evaluate(f, reversed(roster)))
        for invalid in (roster[:-1], roster[:-1] + roster[:1]):
            with self.assertRaisesRegex(ValueError, "roster"):
                s.evaluate(f, invalid)
        with self.assertRaises(ValueError):
            s.roster(replace(f, adaptation=()))

    def test_exact_rational_ranking_and_ties(self):
        a, b, c = (0, -1, -1), (-1, 0, -1), (-1, 0, 1)
        def rows(gains):
            return [(plan, gains.get(plan, 0), s.charge(plan)) for plan in s.PLANS]
        self.assertEqual(s.choose(rows({a: 3, c: 6}), 600), a)
        self.assertEqual(s.choose(rows({a: 3, b: 3}), 600), b)
        self.assertEqual(s.choose(rows({a: 2, c: 5}), 600), c)
        self.assertEqual(s.choose(rows({a: 2, c: 5}), 200), a)
        self.assertEqual(s.choose(rows({a: 2, c: 5}), 0), s.WAIT)

    def test_invalid_rank_inputs(self):
        rows = [(p, 0, s.charge(p)) for p in s.PLANS]
        for invalid in (rows[:-1], rows + rows[:1],
                        [(s.WAIT, 1, 0)] + rows[1:],
                        [(s.WAIT, 0, -1)] + rows[1:],
                        [(s.WAIT, False, 0)] + rows[1:],
                        [(s.WAIT, float("nan"), 0)] + rows[1:]):
            with self.assertRaises(ValueError):
                s.choose(invalid, 600)
        for bad in (-1, True, float("inf")):
            with self.assertRaises(ValueError):
                s.choose(rows, bad)

    def test_support_and_charge_validation(self):
        for n in range(1, 5):
            for support in product(s.ALL, repeat=n):
                if len(set(support)) == n:
                    self.assertEqual(s.ambiguity(support), n * (n - 1) // 2)
                else:
                    with self.assertRaises(ValueError):
                        s.ambiguity(support)
        for invalid in ((), (4,), (True,), (0, 0)):
            with self.assertRaises(ValueError):
                s.ambiguity(invalid)
        for bad in ((False, -1, -1), (2, -1, -1)):
            with self.assertRaises(ValueError):
                s.charge(bad)


if __name__ == "__main__":
    unittest.main()
