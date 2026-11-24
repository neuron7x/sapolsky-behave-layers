"""Source qualification budget, oracle and clamp falsifiers."""
import unittest
from types import SimpleNamespace

from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04f import policy as f
from experiments.cneh_exp_04g import run as g


class TestSourceQualification(unittest.TestCase):
    def test_all_geometries_exact_group_budget(self):
        for w in g.WIDTHS:
            counts=[0,0]
            for t in range(d.STEPS):
                group=g.geometry(t,w)
                if group is not None:
                    counts[group]+=1
                self.assertEqual(sum(counts),w*(t//(2*w))+min(t%(2*w)+1,w))
            self.assertEqual(counts,[800,800])

    def test_route_oracle_current_not_future(self):
        self.assertEqual(g.route_action(0,1,None),(1,1))
        self.assertEqual(g.route_action(1,0,1),(1,1))
        self.assertEqual(g.route_action(160,0,1),(None,1))
        self.assertEqual(g.route_action(320,0,1),(0,0))
        self.assertEqual(g.route_action(320,3,0),(1,1))

    def test_model_oracle_preserves_inferred_state(self):
        p=f.Policy(f.ARMS[0])
        p.previous=d.Observation(320,(0.,)*16,(0,)*8)
        p.candidates=(0,2)
        result=g.model_oracle_act(p,1)
        self.assertEqual(result[:2],(1,"TRACK"))
        self.assertEqual(p.candidates,(0,2))
        self.assertEqual(p.last_action_group,1)

    def test_native_policy_does_not_accept_mode(self):
        p=f.Policy(f.ARMS[0])
        p.observe(d.Observation(0,(0.,)*16,(0,)*8))
        with self.assertRaises(TypeError):
            p.act(1)

    def test_clamp_scope(self):
        import numpy as np
        net=SimpleNamespace(state=SimpleNamespace(V_mV=np.arange(32,dtype=float),
            w_pA=np.arange(32,dtype=float),spiked=np.zeros(32,dtype=bool)),
            g_ampa=np.arange(32,dtype=float),g_nmda=np.arange(32,dtype=float),
            g_gabaa=np.arange(32,dtype=float),gain=1.)
        before=net.state.w_pA.copy()
        native=g.clamp_source(net,np,False)
        self.assertEqual(native[0],native[1])
        a,b=g.clamp_source(net,np,True)
        self.assertEqual(a,g.hx(before[24:]))
        self.assertEqual(b,["0x0.0p+0"]*8)
        self.assertTrue(np.array_equal(net.state.w_pA[:24],before[:24]))
        self.assertTrue(np.array_equal(net.state.V_mV,np.arange(32,dtype=float)))

    def test_fresh_cohorts_and_switches(self):
        from experiments.cneh_exp_04f import run as prior
        self.assertFalse(set(g.B_SEEDS)&set(g.C_SEEDS))
        self.assertFalse(set(prior.SEEDS)&(set(g.B_SEEDS)|set(g.C_SEEDS)))
        for seed in g.C_SEEDS:
            w=g.c_world(seed)
            self.assertEqual(len(w["schedule"]),3 if seed<89301 else 0)
            if seed<89301:
                self.assertIn(3,[mode for _,mode in w["schedule"]])

    def test_physical_endpoint_independent_of_model(self):
        rows=[{"next_mode":0,"transition_mode":0,"true_gaba":[(.5).hex()]*16,
               "true_bits":[0]*8,"group":None,"policy":{"candidates":[1]}} for _ in range(22)]
        r=g.physical(rows,1,21,0,160,True)
        self.assertTrue(r["B10"])
        self.assertFalse(r["I20"])
        self.assertFalse(r["J10"])
