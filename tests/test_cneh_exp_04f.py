"""Prospective policy falsifiers independent of the BN-Syn runtime."""
import copy
import unittest

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04f import policy as f


def obs(t,g=0.,bits=(0,)*8):
    return d.Observation(t,(g,)*16,tuple(bits))


def step(p,t,g=0.,bits=(0,)*8):
    p.observe(obs(t,g,bits))
    return p.act() if t<d.STEPS else None


class TestResponsePolicy(unittest.TestCase):
    def test_exact_matched_budget_all_prefixes_and_fixed_packets(self):
        for arm in f.ARMS:
            p=f.Policy(arm)
            used=0
            groups=[]
            for t in range(d.STEPS):
                group,kind,_=step(p,t,bits=(None,)*8)
                used+=group is not None
                self.assertEqual(group is not None,f.is_on(t))
                self.assertEqual(used,160*(t//320)+min(t%320+1,160))
                if t%320==0:
                    groups.append(group)
                elif group is not None:
                    self.assertEqual(group,groups[-1])
                else:
                    self.assertEqual(kind,"REST")
            self.assertEqual(used,1600)
            step(p,d.STEPS)

    def test_response_weight_and_overdue_discrimination(self):
        p=f.Policy("RESPONSE_ROLLING")
        p.previous=obs(640)
        p.candidates=d.ALL
        p.ones=[1,9]
        p.seen=[10,10]
        p.last_packet=[0,1]
        choice=p.choose_packet(2)
        self.assertEqual(choice["group"],1)
        self.assertEqual(choice["reason"],"RESPONSE_WEIGHTED")
        self.assertEqual(p.choose_packet(3)["group"],0)
        p.candidates=(0,2)
        p.last_packet=[-3,2]
        self.assertEqual(p.choose_packet(4)["group"],1)

    def test_only_observed_bits_credit_response(self):
        p=f.Policy("RESPONSE_ROLLING")
        group,_,_=step(p,0)
        self.assertEqual(group,0)
        step(p,1,bits=(1,None,0,None,1,1,1,1))
        self.assertEqual(p.ones,[1,0])
        self.assertEqual(p.seen,[2,0])

    def test_rolling_retains_recent_exclusion_at_epoch_boundary(self):
        rolling,reset=f.Policy("RESPONSE_ROLLING"),f.Policy("RESPONSE_RESET")
        gaba=0.
        previous_bits=(0,)*8
        for t in range(401):
            gaba=q.DECAY*gaba+q.QUANTUM*sum(previous_bits[:4])
            bits=(1,0,0,0,1,0,0,0) if t==398 else (0,)*8
            for p in (rolling,reset):
                step(p,t,gaba,bits)
            previous_bits=bits
        self.assertEqual(rolling.candidates,(0,1))
        self.assertEqual(reset.candidates,d.ALL)
        self.assertEqual(rolling.exclusion,[None,None,399,399])

    def test_silent_expiry_not_detection(self):
        p=f.Policy("RESPONSE_ROLLING")
        for t in range(401):
            step(p,t,bits=(None,)*8)
        self.assertEqual(p.candidates,d.ALL)
        self.assertEqual(p.expired,(1,2,3))
        self.assertEqual(p.event,f.EXPIRY)

    def test_contradiction_reopens_modes(self):
        p=f.Policy("RESPONSE_ROLLING")
        step(p,0,bits=(1,0,0,0,0,0,0,0))
        step(p,1)
        self.assertEqual(p.candidates,(1,3))
        self.assertEqual(p.event,d.CONTRADICTION)

    def test_tracking_requires_conditional_connection(self):
        for modes in (d.ALL,(3,)):
            p=f.Policy("RESPONSE_ROLLING")
            p.candidates=modes
            p.previous=obs(320)
            group,kind,_=p.act()
            self.assertIsNotNone(group)
            self.assertEqual(kind,"PROBE")
        p=f.Policy("RESPONSE_ROLLING")
        p.previous=obs(320)
        p.candidates=(0,)
        self.assertEqual(p.act()[1],"TRACK")
        p.previous=obs(321)
        p.candidates=(1,3)
        self.assertEqual(p.act()[1],"PACKET_CONTINUATION")

    def test_reset_exact_parent_filter(self):
        p=f.Policy("ALTERNATE_RESET")
        ref=d.Policy("ACTIVE_REID")
        g=0.
        previous=(0,)*8
        for t in range(801):
            mode=0 if t<=250 else 1
            g=q.DECAY*g+q.QUANTUM*sum(previous[4*mode:4*mode+4])
            bits=(1,0,0,0,0,1,0,0) if t%47==0 else (0,)*8
            o=obs(t,g,bits)
            p.observe(o);ref.observe(o)
            self.assertEqual((p.instant,p.candidates,p.event,p.epoch),
                             (ref.instant,ref.candidates,ref.event,ref.epoch))
            p.act()
            previous=bits

    def test_observation_only_replay_rejects_tampering(self):
        p=f.Policy("RESPONSE_ROLLING")
        rows=[]
        for t in range(d.STEPS+1):
            o=obs(t)
            p.observe(o)
            row={**d.obs_record(o),"policy":p.snapshot(),"true_mode":3}
            if t<d.STEPS:
                row["group"],row["kind"],row["packet_decision"]=p.act()
            rows.append(row)
        f.audit_tape(rows,f.ARMS[0])
        rows[0]["true_mode"]=2
        f.audit_tape(rows,f.ARMS[0])
        bad=copy.deepcopy(rows)
        bad[0]["packet_decision"]["reason"]="FORGED"
        with self.assertRaisesRegex(ValueError,"action mismatch"):
            f.audit_tape(bad,f.ARMS[0])
