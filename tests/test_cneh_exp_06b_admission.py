"""Typed mathematical domain and public decision-boundary falsification."""
import copy
from dataclasses import dataclass,replace
import itertools
import unittest

from experiments.cneh_exp_06b import admission as a,certificate as c


@dataclass(frozen=True)
class Frame:
    tick:int=0
    mode:int=0
    switches:tuple=()
    external:tuple=((),)*32


def initial():
    return [[x.hex()]*32 for x in (-71.,12.,.0625,.0625,.25)]


def history(actions,active):
    rows=[{"tick":0,"receiver_spikes":0,"population_spikes":0,"last_action":None}]
    for k,act in enumerate(actions,1):
        rows.append({"tick":k,"receiver_spikes":0,"population_spikes":int(active),"last_action":act})
    return rows


class TestQuietAdmission(unittest.TestCase):
    def test_exact_typed_certificate(self):
        for field,bad in (("sensitivity_gramian_rank",False),("sensitivity_gramian_rank",0.),
                          ("continuous_state_nullity",160.),("first_exit_excluded",1)):
            value=c.certificate()
            value["quiet"][field]=bad
            with self.assertRaisesRegex(ValueError,"forged"):
                c.certify_result(value)

    def test_prefix_and_switch_grammar(self):
        frame=Frame(switches=((.025.hex(),2),(.075.hex(),3)))
        self.assertEqual(c.certify_quiet_prefix(initial(),[frame],["WAIT"])["frames"],1)
        frames=[Frame(k) for k in range(20)]
        self.assertEqual(c.certify_silent_inputs(initial(),frames,["WAIT"]*20)["frames"],20)
        with self.assertRaisesRegex(ValueError,"horizon"):
            c.certify_silent_inputs(initial(),[frame],["WAIT"])

    def test_initial_types(self):
        for bad in ("-71","-0X1.1C00000000000P+6","nan","inf",False,71):
            x=initial();x[0][0]=bad
            with self.assertRaises(ValueError):
                c.certify_quiet_prefix(x,[Frame()],["WAIT"])
        x=initial();x[2][0]=.125.hex()
        with self.assertRaisesRegex(ValueError,"outside certified"):
            c.certify_quiet_prefix(x,[Frame()],["WAIT"])

    def test_malformed_frame_rejection(self):
        frames=(
            Frame(tick=False),Frame(tick=0.),Frame(mode=True),
            Frame(external=()),Frame(external=((),)*31),Frame(external=([],)+((),)*31),
            Frame(external=((.01.hex(),),)+((),)*31),
            Frame(switches=(((0.).hex(),1),)),Frame(switches=((.1.hex(),1),)),
            Frame(switches=((.05.hex(),0),)),Frame(switches=((.07.hex(),1),(.06.hex(),2))),
            Frame(switches=((.05.hex(),True),)),Frame(switches=((.05.hex(),1),(.05.hex(),2))),
            Frame(switches=[(.05.hex(),1)]),
        )
        for frame in frames:
            with self.assertRaises(ValueError):
                c.certify_quiet_prefix(initial(),[frame],["WAIT"])


class TestPublicAdmission(unittest.TestCase):
    def test_all_nonempty_mode_subsets(self):
        n=0
        for mask in range(1,16):
            support=tuple(i for i in range(4) if mask&(1<<i))
            expected=tuple(sorted(set.intersection(*(set(j for j,b in enumerate(a.MODES[i]) if b) for i in support))))
            self.assertEqual(a.common_groups(support),expected)
            n+=1
        self.assertEqual(n,15)

    def test_all_short_public_histories(self):
        n=0
        for actions in itertools.product(a.ACTIONS,repeat=3):
            for active in (False,True):
                obs=history(actions,active)
                for action in a.ACTIONS:
                    result=a.admit(obs,action)
                    self.assertEqual(result["mode_support"],[0,1,2,3])
                    self.assertEqual(result["guaranteed_common_source_groups"],[])
                    self.assertFalse(result["source_action_authorized"])
                    self.assertFalse(result["closed_loop_authorized"])
                    self.assertIs(result["scientific_promotion_authorized"],False)
                    self.assertEqual(result["disposition"],"NO_SOURCE_REQUEST" if action=="WAIT" else "ABSTAIN_UNIDENTIFIED")
                    n+=1
        self.assertEqual(n,162)

    def test_malformed_observation_and_action(self):
        good=history(("G0",),False)
        for change in ({"tick":True},{"tick":2},{"receiver_spikes":-1},
                       {"population_spikes":False},{"population_spikes":0.},
                       {"receiver_spikes":1},{"last_action":"OTHER"},
                       {"mode_support":[0]},{"V":-70.},{"scientific_promotion_authorized":False}):
            bad=copy.deepcopy(good);bad[1].update(change)
            with self.assertRaises(ValueError):
                a.admit(bad,"G0")
        for bad in ("ALTERNATE","",True,0,None):
            with self.assertRaises(ValueError):
                a.admit(good,bad)
        for support in ((),(True,),(0,0),(1,0),[0],(4,)):
            with self.assertRaises(ValueError):
                a.common_groups(support)


if __name__=="__main__":
    unittest.main()
