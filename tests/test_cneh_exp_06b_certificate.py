"""Pure-rational tests of the finite-horizon observability counterexamples."""
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_06b import certificate as c


class TestObservabilityCertificate(unittest.TestCase):
    def test_quiet_first_exit_bounds(self):
        q=c.quiet_certificate()
        self.assertEqual(q["dV_bounds"],[[-79,75],[107,25]])
        self.assertEqual(q["dw_bounds"],[[-13,50],[1,8]])
        self.assertEqual(q["reachable_V"],[[-5708,75],[-1486,25]])
        self.assertEqual(q["reachable_w"],[[-13,25],[97,4]])
        self.assertEqual(q["action_strings"],3486784401)
        self.assertEqual(q["public_count_sequence"],[[0,0]]*20)
        self.assertEqual(q["sensitivity_gramian_rank"],0)
        self.assertEqual(q["continuous_state_nullity"],160)

    def test_active_edge_certificate(self):
        a=c.active_certificate()
        lo,hi=(F(*x) for x in a["source_event_time_bounds_ms"])
        self.assertGreater(lo,F(1,10**9))
        self.assertLess(hi,F(1,40))
        self.assertEqual(a["connected_GABA_strict_lower_nS"],[59,120])
        self.assertEqual(a["disconnected_GABA_nS"],[0,1])
        self.assertEqual(a["exact_source_spike_count"],1)
        self.assertEqual(a["receiver_spike_count"],0)

    def test_forged_rank_is_rejected(self):
        value=c.certificate()
        value["quiet"]["sensitivity_gramian_rank"]=160
        with self.assertRaisesRegex(ValueError,"forged"):
            c.certify_result(value)

    def test_wrong_horizon_cannot_be_certified(self):
        dv,dw=c.interval_rhs(c.QUIET,(F(0),F(500)))
        self.assertFalse(c.strict_interior(c.reachable(c.INITIAL[0],dv,F(3)),c.QUIET[0]))
        self.assertTrue(c.strict_interior(c.reachable(c.INITIAL[1],dw,F(2)),c.QUIET[1]))


if __name__=="__main__":
    unittest.main()
