"""Regression checks for exact dual proofs, not optimizer self-attestation."""
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_06h import reference as h
from experiments.cneh_joint_lp import kernel as k,panel as p,search as s


class JointLPTests(unittest.TestCase):
    def test_exact_vertex_oracle(self):
        rows=p.toy_panel()
        self.assertEqual(len(rows),64)
        self.assertTrue(any(x["disposition"]=="CERTIFIED_INFEASIBLE" for x in rows))
        self.assertTrue(any(x["disposition"]=="EXACT_BOUND" for x in rows))

    def test_independent_normalized_lift(self):
        for stress in (False,True):
            item=p.compatible(0,0,stress)
            self.assertEqual(item["proof"]["status"],k.OUTER)
            self.assertGreaterEqual(F(item["minimum_row_slack"]),0)
            self.assertIs(item["proof"]["joint_existence_established"],False)

    def test_farkas_and_tolerance_boundary(self):
        rows=p.toy_rows(F(0),F(-1))
        proof,_=s.dual(rows,(F(0),F(0)),farkas=True)
        self.assertTrue(k.check_infeasible(rows,proof))
        self.assertLess(F(proof["bound"]),0)
        degenerate=p.toy_rows(F(0),F(0))
        cert,_=s.dual(degenerate,k.unit(2,0))
        self.assertEqual(k.check(degenerate,k.unit(2,0),cert),0)

    def test_checker_accepts_external_exact_proof_without_proposer(self):
        rows=p.toy_rows(F(1),F(1))
        # x+y <= 1 directly certifies the target; no solver execution required.
        weights=k.unit(len(rows),4)
        certificate=k.certificate(rows,(F(1),F(1)),weights)
        self.assertEqual(k.check(rows,(F(1),F(1)),certificate),1)
        with self.assertRaises(ValueError):
            k.check(rows,(F(1),F(0)),certificate)

    def test_fail_closed_controls(self):
        result=p.controls()
        self.assertEqual(len(result),23)
        self.assertEqual(sum(x=="REJECTED" for x in result.values()),18)
        self.assertEqual(result["PIVOT_EXHAUSTION"],"UNKNOWN")
        self.assertEqual(result["UNVERIFIED"],"FULL_PRIOR")
        self.assertEqual(result["EMPTY_SCALAR_STRIP"],"CERTIFIED_INFEASIBLE")

    def test_lift_and_affine_loss_contract(self):
        world=(F(1,2),F(0),F(1),F(1,4),
               F(7,8),F(-16),F(1),F(1),F(0),F(100))
        z=k.lift(world)
        self.assertEqual(z[:4],world[:4])
        self.assertEqual(z[4:],(world[5]/world[4],world[6]/world[4],1/world[4]))
        self.assertGreaterEqual(z[6],1/h.GAIN[1])
        self.assertLessEqual(z[6],1/h.GAIN[0])


if __name__=="__main__":
    unittest.main()
