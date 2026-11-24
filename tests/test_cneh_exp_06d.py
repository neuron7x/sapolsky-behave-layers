"""Exact counterexample and conservative interval contraction tests."""
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_06c import algebra as a,fixtures as f
from experiments.cneh_exp_06d import audit,robust as r


class TestRobustModelSet(unittest.TestCase):
    def test_noise_indistinguishability(self):
        out=audit.prove_noise_alias()
        self.assertGreater(a.decode(out["max_normalized_state_separation"]),F(1,16))
        self.assertTrue(all(a.decode(v)<=F(1,64) for v in out["certified_distances_to_shared_record_pA"]))

    def test_cover(self):
        self.assertEqual(audit.model_cover_check()["boxes"],8)

    def test_alias_recovery(self):
        self.assertEqual(len(audit.recover_aliases()),3)

    def test_unverified_calibration(self):
        v,x=f.truth(16)
        record=f.record(v,tuple(f.current(t,x) for t in a.TIMES),F(1,1024),(1,)*5)
        out=r.estimate(record)
        self.assertEqual(out["status"],"CALIBRATION_UNVERIFIED")
        self.assertEqual(out["normalized_bounds"],[["0/1","1/1"]]*4)
        self.assertFalse(out["closed_loop_authorized"])

    def test_negative_controls(self):
        self.assertEqual(len(audit.negatives()),7)


if __name__=="__main__":
    unittest.main()
