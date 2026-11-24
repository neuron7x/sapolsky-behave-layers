import unittest
from experiments.cneh_exp_05r import run as r


class TestNumericalDiagnostic(unittest.TestCase):
    def test_first_component_difference(self):
        a=[{"parts":{"V":"a","w":"b"},"state_sha256":"x","rng_sha256":"r","public_policy_sha256":"p"} for _ in range(3)]
        b=[{**x,"parts":dict(x["parts"])} for x in a]
        self.assertTrue(r.compare_states(a,b)["exact"])
        b[1]["parts"]["V"]="different"
        b[1]["state_sha256"]="z"
        b[2]["parts"]["w"]="different"
        result=r.compare_states(a,b)
        self.assertFalse(result["exact"])
        self.assertEqual(result["first_difference"],{"tick":1,"fields":["V","state_sha256"]})
        self.assertEqual(result["differing_samples_by_field"]["w"],1)

    def test_archive_discrepancy_not_a_tolerance_pass(self):
        a={"trace":[{"tick":0,"source_V":[(1.).hex()],"state_sha256":"a"}]}
        b={"trace":[{"tick":0,"source_V":[(1.0000000000000002).hex()],"state_sha256":"b"}]}
        result=r.archive_difference(a,b)
        self.assertFalse(result["exact"])
        self.assertEqual(result["first_tick"],0)
        self.assertGreater(result["known_array_max_abs_delta"]["source_V"],0.)
