"""Independent finite contract checks for EXP06C."""
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_06c import algebra as a,estimator as e,fixtures as f


class TestConditionalMeasurement(unittest.TestCase):
    def test_outward_exp(self):
        for x in (F(-48),F(-1,3),F(0),F(93,25),F(1,2)):
            lo,hi=a.exponential(x)
            self.assertLessEqual(lo,hi)
            self.assertGreater(lo,0)
        self.assertEqual(a.exponential(F(0)),(F(1),F(1)))

    def test_matrix_and_decimal(self):
        value=a.matrix_certificate()
        lo,hi=map(a.decode,value["determinant_interval"])
        self.assertGreater(lo,0)
        self.assertLessEqual(lo,hi)
        self.assertEqual(value["conditional_cell_rank"],5)
        self.assertEqual(value["conditional_32_cell_rank"],160)
        self.assertLess(a.decode(value["inverse_perturbation_upper"]),1)
        self.assertEqual(f.independent_coefficients(),25)

    def test_sensor_contract_and_ood_aliases(self):
        self.assertEqual(len(f.negative_controls()),14)
        result=f.aliases()
        self.assertEqual(result["ood_model_qualification"],"FAIL_COUNTEREXAMPLE")
        self.assertTrue(result["unknown_nmda_gain"]["same_quantized_record"])
        self.assertTrue(result["unknown_clock_origin"]["nominal_origin_truth_excluded"])

    def test_single_nominal_corner(self):
        v,x=f.truth(0)
        rec=f.record(v,tuple(f.current(t,x) for t in a.TIMES),F(1,1024),(1,)*5)
        out=e.estimate(rec)
        self.assertTrue(f.contains(out,v,x))
        self.assertFalse(out["source_action_authorized"])

    def test_action_time_limit(self):
        rows,summary=f.graph_panel()
        self.assertEqual(len(rows),128)
        self.assertEqual(summary["profiles"][0]["fixed_epoch_singletons"],64)
        self.assertEqual(summary["future_action_time_support"],[0,1,2,3])
        self.assertEqual(summary["profiles"][0]["action_time_singletons"],0)
        reach=a.reachability()
        self.assertLess(a.decode(reach["max_terminal_GABA_nS"][1]),F(2,5))
        self.assertEqual(reach["max_incremental_source_charge_pC"],"4/1")


if __name__=="__main__":
    unittest.main()
