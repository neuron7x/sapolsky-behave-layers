"""Closed-form control boundary and coordinate-equivariance tests."""
from __future__ import annotations
import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"experiments"/"cneh_exp_02"
SPEC=importlib.util.spec_from_file_location("cneh_linear_reference",ROOT/"linear_reference.py")
assert SPEC and SPEC.loader
m=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=m
SPEC.loader.exec_module(m)


class TestLinearReference(unittest.TestCase):
    def test_observability_complementarity_at_zero_coupling(self):
        a=((0.8,0.),(0.,0.85))
        b=m.EYE
        ca=((1.,0.),(0.,0.))
        cb=((0.,0.),(0.,1.))
        w=m.finite_gramians(a,b,ca,cb,horizon=6,observation_variance=1.)
        self.assertAlmostEqual(m.eig_sym(w["Wo_A"])[0],0.,places=10)
        self.assertAlmostEqual(m.eig_sym(w["Wo_B"])[0],0.,places=10)
        self.assertGreater(m.eig_sym(w["Wo_joint"])[0],0.)
        self.assertGreater(m.eig_sym(w["Wc"])[0],0.)

    def test_single_sensor_can_be_temporally_observable(self):
        a=((0.8,0.4),(-0.4,0.85))
        ca=((1.,0.),(0.,0.))
        w=m.finite_gramians(a,m.EYE,ca,m.ZERO,horizon=8,observation_variance=0.01)
        self.assertGreater(m.eig_sym(w["Wo_A"])[0],0.0)
        self.assertEqual(m.eig_sym(w["Wo_B"]),(0.0,0.0))

    def test_no_actuator_means_no_control_even_if_full_observation(self):
        a=((0.8,0.),(0.,0.85))
        w=m.finite_gramians(a,m.ZERO,m.EYE,m.ZERO,horizon=8,observation_variance=1.)
        self.assertEqual(m.hankel_singular_values(w["Wc"],w["Wo_joint"]),(0.,0.))
        self.assertGreater(m.eig_sym(w["Wo_joint"])[0],0.)

    def test_hankel_coordinates_are_similarity_invariant(self):
        a=((0.8,0.3),(-0.3,0.85))
        b=((0.4,0.),(0.,0.4))
        ca=((1.,0.),(0.,0.))
        cb=((0.,0.),(0.,1.))
        w=m.finite_gramians(a,b,ca,cb,horizon=16,observation_variance=0.01)
        expected=m.hankel_singular_values(w["Wc"],w["Wo_joint"])
        t=((2.,0.),(0.,0.5))
        inv=((0.5,0.),(0.,2.))
        new_a=m.mm(m.mm(t,a),inv)
        new_b=m.mm(t,b)
        new_ca=m.mm(ca,inv)
        new_cb=m.mm(cb,inv)
        wc=m.finite_gramians(new_a,new_b,new_ca,new_cb,horizon=16,observation_variance=0.01)
        got=m.hankel_singular_values(wc["Wc"],wc["Wo_joint"])
        for x,y in zip(expected,got):
            self.assertAlmostEqual(x,y,places=7)

    def test_parameter_information_is_not_observability(self):
        # Both state observability and controllability can be full-rank, while
        # a zero-state zero-input trajectory contains ZERO theta information.
        zero=m.theta_regression_information_open_loop(
            theta=0.2,a0=0.8,a1=0.85,actuator_gain=0.4,
            initial=(0.,0.),fixed_actions=[(0.,0.)]*20,
            observation_variance=0.01,
        )
        excited=m.theta_regression_information_open_loop(
            theta=0.2,a0=0.8,a1=0.85,actuator_gain=0.4,
            initial=(0.,0.),fixed_actions=[(0.2*math.sin(i),0.2*math.cos(i)) for i in range(20)],
            observation_variance=0.01,
        )
        self.assertEqual(zero,0.)
        self.assertGreater(excited,0.)

    def test_reference_report_is_finite_and_nonpromoting(self):
        p=json.loads((ROOT/"protocol.json").read_text())
        result=m.reference_report(p)
        self.assertEqual(len(result["variants"]),len(p["model"]["theta_ood"])+1)
        self.assertEqual(result["scientific_authority"],"EXPLORATORY_REFERENCE_LTI_ONLY")
        for d in result["variants"].values():
            for key,v in d.items():
                if isinstance(v,list):
                    self.assertTrue(all(math.isfinite(x) for x in v))
                else:
                    self.assertTrue(math.isfinite(v))


if __name__=="__main__":
    unittest.main()
