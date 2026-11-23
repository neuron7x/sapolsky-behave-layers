"""Cross-verify CNEH-EXP-02 exact finite-horizon mathematics with CWC's own
local-identifiability primitive. This test runs against actual CWC code.
"""
from __future__ import annotations
import importlib.util
import math
import sys
import unittest
from pathlib import Path
import numpy as np

from cwc.causal.observability import local_first_order_identifiability

ROOT=Path(__file__).resolve().parents[1]/"experiments"/"cneh_exp_02"
SPEC=importlib.util.spec_from_file_location("cneh_reference_bridge",ROOT/"linear_reference.py")
assert SPEC and SPEC.loader
lin=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=lin
SPEC.loader.exec_module(lin)


def dynamic_jacobian(a: lin.Mat, axes: tuple[int,...], horizon: int) -> list[list[float]]:
    """Stack C_i A^k as rows: true dynamic observability, not just C_i rank."""
    ak=lin.EYE
    rows=[]
    for _ in range(horizon):
        for axis in axes:
            rows.append(list(ak[axis]))
        ak=lin.mm(ak,a)
    return rows


class TestCWCScientificBridge(unittest.TestCase):
    def test_cwc_fisher_matches_independent_discrete_gramian(self):
        a=((0.81,0.34),(-0.34,0.86))
        variance=0.055**2
        jac=dynamic_jacobian(a,(0,1),horizon=12)
        cert=local_first_order_identifiability(
            jac,covariance=np.eye(len(jac))*variance,
        )
        grams=lin.finite_gramians(
            a,lin.EYE,((1.,0.),(0.,0.)),((0.,0.),(0.,1.)),
            horizon=12,observation_variance=variance,
        )
        reference=lin.eig_sym(grams["Wo_joint"])[0]
        self.assertEqual(cert.numerical_rank,2)
        self.assertEqual(cert.state,"LOCAL_FIRST_ORDER_IDENTIFIABLE")
        self.assertAlmostEqual(cert.information_min_eigenvalue,reference,places=7)
        self.assertFalse(cert.causal_authority_granted)

    def test_full_rank_requires_joint_sensor_when_dynamics_uncoupled(self):
        a=((0.83,0.0),(0.0,0.86))
        for axis in (0,1):
            cert=local_first_order_identifiability(dynamic_jacobian(a,(axis,),8))
            self.assertEqual(cert.numerical_rank,1)
            self.assertFalse(cert.causal_authority_granted)
        both=local_first_order_identifiability(dynamic_jacobian(a,(0,1),8))
        self.assertEqual(both.numerical_rank,2)
        self.assertFalse(both.causal_authority_granted)

    def test_single_temporal_sensor_can_be_full_rank_at_nonzero_coupling(self):
        # The simplistic 'each agent blind' condition is NOT universal:
        # temporal observations can reveal both coordinates.
        a=((0.83,0.34),(-0.34,0.86))
        cert=local_first_order_identifiability(dynamic_jacobian(a,(0,),8))
        self.assertEqual(cert.numerical_rank,2)
        self.assertFalse(cert.causal_authority_granted)

    def test_parameter_identifiability_differs_from_state_observability(self):
        zero=lin.theta_regression_information_open_loop(
            theta=0.34,a0=0.83,a1=0.86,actuator_gain=0.43,
            initial=(0.,0.),fixed_actions=[(0.,0.)]*12,
            observation_variance=0.055**2,
        )
        active=lin.theta_regression_information_open_loop(
            theta=0.34,a0=0.83,a1=0.86,actuator_gain=0.43,
            initial=(0.,0.),fixed_actions=[
                (0.3*math.sin(i),0.3*math.cos(i)) for i in range(12)
            ],
            observation_variance=0.055**2,
        )
        self.assertEqual(zero,0.)
        self.assertGreater(active,0.)
        self.assertEqual(local_first_order_identifiability([[0.]]).numerical_rank,0)
        self.assertEqual(local_first_order_identifiability([[math.sqrt(active)]]).numerical_rank,1)


if __name__=="__main__":
    unittest.main()
