import unittest

from experiments.cneh_exp_05m import scales as s


def sample(mode=0,g=.5,correct=True,obs=15,full=15):
    return {"mode":mode,"g":g,"correct":correct,"band":.4<=g<=.6,
            "stale":not correct,"ambiguous":not correct,"observed":obs,"complete":full,
            "source_spike":False,"arrival":0}


class TestScales(unittest.TestCase):
    def test_cancellation_and_no_claim_of_regulation(self):
        _,m,_=s.window_metrics([sample(g=0.),sample(g=1.)])
        self.assertEqual(m["raw_mae_nS"],.5)
        self.assertEqual(m["smoothed_abs_error_nS"],0.)
        self.assertEqual(m["mean_g_in_band"],1)
        self.assertEqual(m["raw_band_fraction"],0.)

    def test_temporal_mismatch(self):
        rows=[sample(g=.2,correct=True)]*20+[sample(g=.5,correct=False)]*10
        _,m,_=s.window_metrics(rows)
        self.assertEqual((m["I20"],m["B10"],m["J10"],m["false_cooccurrence"]),(1,1,0,1))

    def test_mixed_has_no_positive_goal_or_persistent_set_claim(self):
        kind,m,_=s.window_metrics([sample(mode=0,obs=1,full=1),sample(mode=1,obs=2,full=2)])
        self.assertEqual(kind,"MIXED")
        self.assertEqual(m["mixed_empty_intersection"],1)
        self.assertNotIn("raw_band_fraction",m)
        self.assertNotIn("observed_singleton",m)

    def test_distinct_evidence_vs_repetition(self):
        _,m,_=s.window_metrics([sample(obs=3,full=1)]*4)
        self.assertEqual(m["distinct_eliminated"],2)
        self.assertEqual(m["evidence_redundancy"],6)
        self.assertEqual(m["erasure_candidate_gap"],1)

    def test_disconnection_not_regulation(self):
        kind,m,_=s.window_metrics([sample(mode=3,g=.5,obs=8,full=8)])
        self.assertEqual(kind,"PURE_DISCONNECTED")
        self.assertNotIn("raw_band_fraction",m)
        self.assertEqual(m["observed_singleton"],1)

    def test_age_bins(self):
        self.assertEqual(s.age_bin([1,2,100],100),"60_160")
        self.assertEqual(s.age_bin([0,2,100],100),"PRIOR_INVOLVED")
        with self.assertRaises(ValueError):
            s.age_bin([1,200,400],401)

    def test_coverage_tail_and_unavailable_width(self):
        out,c=s.segment_windows([("OOD_REACHABLE",[sample()]*11)],[])
        self.assertEqual(c["SEGMENT/OOD_REACHABLE/10/0"],{"eligible_samples":11,"used_samples":10,"skipped_prefix":0,"discarded_tail":1})
        self.assertEqual(c["SEGMENT/OOD_REACHABLE/10/5"]["used_samples"],0)
        self.assertNotIn("SEGMENT/OOD_REACHABLE/10/5",out)

    def test_pooled_reversal_and_missing_worlds(self):
        def r(seed,total,n):
            return {"seed":seed,"windows":{"key":{"metrics":{"m":[total,n]}}}}
        a=[r(1,9.,10),r(2,0.,100),{"seed":3,"windows":{}}]
        b=[r(1,0.,10),r(2,60.,100),r(3,1.,1)]
        q=s.paired_contrasts(a,b)["key"]["m"]
        self.assertEqual(q["paired_worlds"],2)
        self.assertEqual(q["missing_worlds"],1)
        self.assertTrue(q["sign_reversal"])
