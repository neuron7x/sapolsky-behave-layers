"""Exact mathematical and end-to-end falsifiers for EXP04."""
import itertools
import unittest

from experiments.cneh_exp_04 import run


class TestReidentification(unittest.TestCase):
    def test_all_ambiguous_subsets_separable(self):
        for size in (2,3,4):
            for c in itertools.combinations(range(4),size):
                u=run.active_probe(c)
                run.action_check(u)
                self.assertGreater(run.separation(c,u),2*run.EPS)
                for i in c:
                    for noise in (-.013,0.,.013):
                        self.assertEqual(run.compatible(c,run.dot(run.MODES[i],u)+noise,u),(i,))

    def test_sentinel_detects_each_change_at_noise_extremes(self):
        for i in (1,2,3):
            for noise in (-.013,0.,.013):
                self.assertEqual(run.compatible((0,),run.dot(run.MODES[i],(.25,0.))+noise,(.25,0.)),())
                self.assertEqual(run.compatible((0,),.2+noise,(.25,0.)),(0,))

    def test_no_oracle_input_to_controller_and_ambiguity(self):
        c=run.Controller(active=True)
        c.observe(0,0.)
        u,_=c.act(0)
        self.assertEqual(u,(.25,0.))
        c.observe(1,0.)
        self.assertEqual(c.candidates,(2,3))
        u,kind=c.act(1)
        self.assertEqual(kind,"ACTIVE_PROBE")
        c.observe(2,run.dot(run.MODES[2],u))
        self.assertEqual(c.candidates,(2,))
        self.assertEqual(c.identified,2)

    def test_impossible_residual_fails_closed(self):
        c=run.Controller(active=True)
        c.observe(0,0.)
        c.act(0)
        with self.assertRaisesRegex(ValueError,"MODEL_SET_VIOLATION"):
            c.observe(1,10.)

    def test_invalid_action_and_nonfinite_rejected(self):
        for u in ((.5,.5),(float("nan"),0.)):
            with self.assertRaises(ValueError):
                run.action_check(u)
        with self.assertRaises(ValueError):
            run.compatible((0,),float("nan"),(0.,0.))

    def test_no_change_and_hidden_change_with_emulator(self):
        for seed in (85001,85101):
            w=run.world(seed)
            eps=[run.execute(w,a) for a in run.ARMS]
            r=run.pair(w,eps)
            self.assertTrue(r["exact_emulator_equal"])
            if seed==85101:
                self.assertIsNone(r["active_detect_delay"])
            else:
                self.assertLessEqual(r["active_identify_delay"],9)
            eps[1]["trace"][1]["x"]="0x1.0p+0"
            with self.assertRaisesRegex(ValueError,"emulator mismatch"):
                run.pair(w,eps)

    def test_exhaustive_switch_ticks_and_modes_without_random_noise(self):
        for tau in range(20,40):
            for mode in (1,2,3):
                w={"seed":85001,"tau":tau,"mode":mode,"w":[0.]*80,"v":[0.]*81}
                e=run.execute(w,"ACTIVE_REID")
                self.assertLessEqual(e["detect_tick"]-tau,8)
                self.assertLessEqual(e["identify_tick"]-tau,9)
                self.assertEqual(e["final_candidates"],[mode])
