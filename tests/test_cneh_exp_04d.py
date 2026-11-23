"""Repeated-change, stale-evidence, and observation-boundary falsifiers."""
import unittest

from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04c import qualification as q


def obs(t,g,bits=(0,)*8):
    return d.Observation(t,(g,)*16,tuple(bits))


class TestRepeatedOOD(unittest.TestCase):
    def test_multiple_contradictions_reopen_previously_eliminated_modes(self):
        p=d.Policy("ACTIVE_REID")
        a=(1,0,0,0,0,0,0,0)
        b=(0,0,0,0,1,0,0,0)
        p.observe(obs(0,0.,a))
        p.observe(obs(1,0.,b))
        self.assertEqual(p.event,d.CONTRADICTION)
        self.assertEqual(p.candidates,(1,3))
        self.assertEqual(p.act(),(1,"ACTIVE_PROBE"))
        g=q.QUANTUM
        p.observe(obs(2,g,b))
        self.assertEqual(p.candidates,(1,))
        g*=q.DECAY
        p.observe(obs(3,g,a))
        self.assertEqual(p.event,d.CONTRADICTION)
        self.assertEqual(p.candidates,(0,3))
        g*=q.DECAY
        p.observe(obs(4,g,a))
        self.assertEqual(p.candidates,(3,))
        g=q.DECAY*g+q.QUANTUM
        p.observe(obs(5,g,b))
        self.assertEqual(p.event,d.CONTRADICTION)
        self.assertEqual(p.candidates,(0,2))
        p.observe(obs(6,q.DECAY*g))
        self.assertEqual(p.candidates,(0,))

    def test_silent_hidden_switch_is_not_instantly_identifiable(self):
        p=d.Policy("ACTIVE_REID")
        p.observe(obs(0,0.))
        p.observe(obs(1,0.))
        self.assertEqual(p.instant,d.ALL)
        self.assertEqual(p.candidates,(0,))
        self.assertEqual(p.event,"NONE")
        # The same observations could arise after M0 -> M3; the epoch
        # singleton is not a certificate of the actual new hidden mode.
        self.assertIn(3,p.instant)
        self.assertNotIn(3,p.candidates)

    def test_scheduled_renewal_is_not_contradiction(self):
        p=d.Policy("ACTIVE_REID")
        for t in range(401):
            p.observe(obs(t,0.,(None,)*8))
        self.assertEqual(p.event,d.RENEWAL)
        self.assertEqual(p.candidates,d.ALL)
        self.assertEqual(p.epoch,1)

    def test_no_change_with_bounded_noise_and_erasure(self):
        p=d.Policy("ACTIVE_REID")
        gaba=0.
        true_bits=(1,0,0,0,0,0,0,0)
        for t in range(800):
            e=q.EPS if t%2 else -q.EPS
            mask=(t%3==0,False,False,False,False,False,False,False)
            p.observe(d.public_observation(t,(gaba,)*16,true_bits,(e,)*16,mask))
            self.assertIn(0,p.instant)
            self.assertIn(0,p.candidates)
            self.assertNotEqual(p.event,d.CONTRADICTION)
            gaba=q.DECAY*gaba+q.QUANTUM

    def test_impossible_receiver_observation_fails_closed(self):
        p=d.Policy("ACTIVE_REID")
        p.observe(obs(0,0.))
        with self.assertRaisesRegex(ValueError,"MODEL_SET_VIOLATION"):
            p.observe(obs(1,1.))

    def test_ambiguous_and_disconnected_modes_do_not_track(self):
        for arm in ("ACTIVE_REID","PERIODIC_REID"):
            p=d.Policy(arm)
            p.previous=obs(101,0.)
            p.candidates=(3,)
            self.assertEqual(p.act(),(None,"DISCONNECTED_ABSTAIN"))
            p.candidates=(1,3)
            self.assertNotEqual(p.act()[1],"TRACK")
        self.assertEqual(d.known_action(3,obs(0,0.)),(0,"SENTINEL"))

    def test_actual_sensor_bound_and_erasure_are_not_clipped(self):
        x=d.public_observation(0,(0.,)*16,(1,)*8,(-.01,)*16,(True,)*8)
        self.assertEqual(x.gaba,(-.01,)*16)
        self.assertEqual(x.bits,(None,)*8)
        with self.assertRaises(ValueError):
            d.public_observation(0,(0.,)*16,(0,)*8,(.011,)*16,(False,)*8)

    def test_recovery_requires_consecutive_correct_observations(self):
        self.assertEqual(d.first_run([True,False,True,True,True],[11,12,13,14,15],3),15)
        self.assertIsNone(d.first_run([True,False,True],[11,12,13],2))
        with self.assertRaises(ValueError):
            d.first_run([True,True],[11,13],2)
        rows=[]
        for t in range(31):
            rows.append({"tick":t,"transition_mode":None if t==0 else 1,"next_mode":1,
                         "candidates":[1] if t>=6 else [0],"true_gaba":[(.5).hex()]*16,
                         "event":"NONE","kind":"TRACK","group":1})
        r=d.segment_metrics(rows,"ACTIVE_REID",0,30,1)
        self.assertEqual(r["identification_latency"],25)
        self.assertEqual(r["control_recovery_latency"],15)
        self.assertEqual(r["stale_fraction"],5/30)
        for row in rows:
            row["transition_mode"]=3
            row["next_mode"]=3
            row["candidates"]=[3]
            row["kind"]="DISCONNECTED_ABSTAIN"
            row["group"]=None
        r=d.segment_metrics(rows,"ACTIVE_REID",0,30,3)
        self.assertEqual(r["control_recovery_status"],"DISCONNECTED_NOT_APPLICABLE")
        self.assertIsNone(r["control_recovery_latency"])

    def test_world_switches_reconnect_and_sensor_tape_independent(self):
        for seed in d.SEEDS:
            w=d.world(seed)
            if seed<87101:
                modes=[0]+[mode for _,mode in w["schedule"]]
                self.assertEqual(len(w["schedule"]),3)
                self.assertIn(3,modes)
                self.assertNotEqual(modes[-1],3)
                self.assertTrue(all(x!=y for x,y in zip(modes,modes[1:])))
            else:
                self.assertEqual(w["schedule"],[])
        tape=d.sensor_tape(87001)
        self.assertEqual(tape,d.sensor_tape(87001))
        self.assertNotEqual(tape,d.sensor_tape(87002))
        self.assertTrue(all(all(tape[t][1]) for t in range(1000,1100)))

    def test_policy_tape_rejects_forged_decision_not_privileged_metadata(self):
        p=d.Policy("ACTIVE_REID")
        rows=[]
        for t in range(d.STEPS+1):
            o=obs(t,0.)
            p.observe(o)
            row={**d.obs_record(o),"instant":list(p.instant),"candidates":list(p.candidates),
                 "event":p.event,"epoch":p.epoch,"next_mode":3}
            if t<d.STEPS:
                row["group"],row["kind"]=p.act()
            rows.append(row)
        d.audit_policy_tape(rows,"ACTIVE_REID")
        rows[0]["next_mode"]=2
        d.audit_policy_tape(rows,"ACTIVE_REID")
        rows[0]["group"]=1
        with self.assertRaisesRegex(ValueError,"policy action"):
            d.audit_policy_tape(rows,"ACTIVE_REID")
