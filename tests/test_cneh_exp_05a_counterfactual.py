"""Calibration and archive decoder falsifiers."""
import io
import unittest

from experiments.cneh_exp_05a import audit as a,counterfactual as c
from experiments.cneh_exp_05 import policy as p


class TestCounterfactual(unittest.TestCase):
    def test_complete_bits_information(self):
        bits=[(1,0,0,0,0,0,0,0),(0,0,0,0,1,0,0,0)]
        h=c.arrival_histories(bits)
        i=c.information(h,bits)
        self.assertEqual(i["full_directed_elimination"],1.)
        self.assertEqual(i["observed_directed_elimination"],1.)
        self.assertEqual(i["observed_singleton_modes"],4)
        erased=c.information(h,[(None,)*8]*2)
        self.assertLess(erased["observed_directed_elimination"],1.)
        self.assertEqual(erased["observed_singleton_modes"],0)

    def test_rank_inversion_and_ties(self):
        x=list(range(8))
        y=list(reversed(x))
        self.assertEqual(c.rank_stats(x,y),{"strict_pairs":28,"inversions":28,"tie_disagreements":0})
        self.assertEqual(c.rank_stats(x,[0]*8)["tie_disagreements"],28)

    def test_shadow_independent_reproduction(self):
        cells=tuple((-70.,0.,0) for _ in range(8))
        for plan in p.PLANS:
            history=c.shadow_history(cells,plan)
            state=cells
            for t,row in enumerate(history):
                self.assertEqual(row,tuple(s for _,_,s in state))
                state=p.advance(state,p.action(plan,t))

    def test_stream_array(self):
        self.assertEqual(list(a.stream_array(io.StringIO(' [ {"x":1}, {"x":2} ] \n'))),[{"x":1},{"x":2}])
        self.assertEqual(list(a.stream_array(io.StringIO("[]"))),[])
        with self.assertRaises(ValueError):
            list(a.stream_array(io.StringIO('[{"x":1},]')))
        with self.assertRaises(ValueError):
            list(a.stream_array(io.StringIO('[{"x":1}] {}')))

    def test_first_episode_difference_never_masks_mismatch(self):
        left={"valid":True,"trace":[{"tick":0,"state_sha256":"a","rng_sha256":"r"},
                                    {"tick":1,"state_sha256":"b","rng_sha256":"s"}]}
        right={"valid":True,"trace":[dict(x) for x in left["trace"]]}
        self.assertTrue(a.first_episode_difference(left,right)["exact_match"])
        right["trace"][1]["state_sha256"]="changed"
        report=a.first_episode_difference(left,right)
        self.assertFalse(report["exact_match"])
        self.assertEqual(report["first_different_tick"],1)
        self.assertEqual(report["first_different_fields"],["state_sha256"])
        self.assertEqual(report["digest_or_action_difference"]["state_sha256"]["archive"],"b")
