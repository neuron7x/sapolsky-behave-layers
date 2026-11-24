"""Exact arithmetic and synthetic contract falsifiers."""
from __future__ import annotations

from fractions import Fraction
import unittest

from experiments.cneh_exp_05k import boundary as k


class TestBoundary(unittest.TestCase):
    def test_interval_and_packing(self):
        lo,hi=k.duration_interval()
        self.assertLess(lo,hi)
        self.assertLess(hi-lo,Fraction(1,10**57))
        self.assertTrue(Fraction(2432790648,10**9)<lo<hi<Fraction(2432790650,10**9))
        for numerator in range(1,1025):
            t=Fraction(numerator,10)
            u=k.upper_occupancy(t)
            self.assertLessEqual(u,t)
            self.assertLessEqual(u,(t+hi)/2+(hi-lo)*(t/lo+1))
        self.assertEqual(k.upper_occupancy(Fraction(1,10)),Fraction(1,10))

    def test_finite_reachability(self):
        report=k.reachability()
        self.assertEqual(report["guaranteed_common_source_groups"],[])
        self.assertEqual(report["probability_simplex_cases"],5151)
        self.assertEqual(report["support_subsets"],15)
        self.assertEqual(report["asymptotic_upper_fraction"],{"numerator":1,"denominator":2})

    def test_fail_closed_contract(self):
        report=k.synthetic_contract_tests()
        self.assertEqual(report["status_assignments"],78125)
        self.assertEqual(len(report["attacks_rejected"]),17)
        self.assertTrue(all(report["attacks_rejected"].values()))
        self.assertEqual(report["synthetic_all_pass_production_admission"],"BLOCKED")
        self.assertFalse(k.admission({},[])["scientific_promotion_authorized"])

    def test_no_authority(self):
        report=k.report()
        self.assertEqual(report["real_trust_roots"],0)
        self.assertEqual(report["blind_cohort_admission"],"BLOCKED")
        self.assertFalse(report["scientific_promotion_authorized"])


if __name__=="__main__":
    unittest.main()
