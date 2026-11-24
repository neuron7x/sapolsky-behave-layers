"""Structural envelope, predictor, decision and replay falsifiers."""
import copy
import unittest
from unittest.mock import patch

from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_05 import policy as p


class TestDualControl(unittest.TestCase):
    def test_certificate(self):
        self.assertEqual(p.certificate()["max_contiguous_samples"],25)
        self.assertEqual(p.upper_count(49),25)
        self.assertEqual(p.upper_count(50),26)
        self.assertEqual(p.upper_count(3200),1640)
        self.assertEqual(p.certify_band([True]*25+[False]*24+[True]*25),50)
        with self.assertRaisesRegex(ValueError,"continuous"):
            p.certify_band([True]*26)
        with self.assertRaisesRegex(ValueError,"inter-run"):
            p.certify_band([True]+[False]*23+[True])

    def test_all_plan_budgets(self):
        for plan in p.PLANS:
            seq=[p.action(plan,t) for t in range(p.BLOCK)]
            self.assertEqual(sum(x is not None for x in seq),160)
            self.assertEqual({x for x in seq if x is not None},{plan[0]})

    def test_spike_observation_override(self):
        c=(-70.,0.,0)
        self.assertEqual(p.shadow_step(c,0.,1),(-58.,80.,1))
        self.assertEqual(p.shadow_step(c,0.,None)[2],0)
        v,w,s=p.shadow_step((29.,0.,0),500.,0)
        self.assertLess(v,30.)
        self.assertEqual(s,0)
        self.assertLess(w,1.)

    def test_causal_previous_action_alignment(self):
        policy=p.Policy("DUAL")
        policy.observe(d.Observation(0,(0.,)*16,(0,)*8))
        policy.filter.last_action_tick=0
        policy.filter.last_action_group=1
        bits=(0,0,0,0,1,None,0,0)
        policy.observe(d.Observation(1,(0.,)*16,bits))
        self.assertEqual(policy.shadow[4],(-58.,80.,1))
        self.assertEqual(policy.shadow[5],p.shadow_step((-70.,0.,0),500.,None))
        self.assertEqual(policy.shadow[0],p.shadow_step((-70.,0.,0),0.,0))

    def test_objective_and_tie_break(self):
        rows=[{"plan":list(x),"control_cost":.9,"information_proxy":.1} for x in p.PLANS]
        rows[0].update(control_cost=.1,information_proxy=.1)
        rows[4].update(control_cost=.2,information_proxy=1.)
        self.assertEqual(p.choose("CONTROL_ONLY",0,rows),p.PLANS[0])
        self.assertEqual(p.choose("INFO_ONLY",0,rows),p.PLANS[4])
        self.assertEqual(p.choose("DUAL",0,rows),p.PLANS[4])
        self.assertEqual(p.choose("EXACT_EMULATOR",0,rows),p.PLANS[4])
        self.assertEqual(p.choose("FIXED_ALTERNATE",1,rows),(1,"EARLY"))
        for row in rows:
            row.update(control_cost=.5,information_proxy=.5)
        self.assertEqual(p.choose("DUAL",1,rows),(1,"EARLY"))

    def test_disconnection_and_all_mode_information(self):
        shadow=tuple((-70.,0.,0) for _ in range(8))
        a=p.score_plans(shadow,(3,),(0.,)*16)
        b=p.score_plans(shadow,(0,),(0.,)*16)
        self.assertTrue(all(x["control_cost"]==0 and not x["forecasts"] for x in a))
        self.assertEqual([x["information_proxy"] for x in a],[x["information_proxy"] for x in b])
        self.assertTrue(all(len(x["forecasts"])==2 for x in b))

    def test_observation_only_replay_rejects_forged_plan(self):
        scores=[{"plan":list(x),"control_cost":.5,"information_proxy":.5} for x in p.PLANS]
        with patch.object(p,"score_plans",return_value=scores):
            policy=p.Policy("DUAL")
            rows=[]
            for t in range(d.STEPS+1):
                obs=d.Observation(t,(0.,)*16,(None,)*8)
                policy.observe(obs)
                row={**d.obs_record(obs),"policy":policy.snapshot(),"privileged_mode":3}
                if t<d.STEPS:
                    row["group"],row["decision"]=policy.act()
                rows.append(row)
            p.audit_tape(rows,"DUAL")
            rows[0]["privileged_mode"]=1
            p.audit_tape(rows,"DUAL")
            bad=copy.deepcopy(rows)
            bad[0]["decision"]["selected"]=[1,"SPLIT"]
            with self.assertRaisesRegex(ValueError,"action mismatch"):
                p.audit_tape(bad,"DUAL")
