"""Endpoint decomposition falsifiers."""
import unittest
from experiments.cneh_exp_04f_audit import audit as a


class TestFailureDecomposition(unittest.TestCase):
    def test_all_partitions(self):
        t=[True]*10
        n=[False]*10
        cases=[(t,t,"JOINT"),(n,t,"IDENTIFICATION_LIMITED"),(t,n,"CONTROL_LIMITED"),
               (n,n,"BOTH_LIMITED"),(t+n,n+t,"TEMPORAL_MISMATCH")]
        for i,b,want in cases:
            self.assertEqual(a.classify(i,b),want)

    def test_joint_does_not_imply_twenty_tick_identification(self):
        self.assertEqual(a.classify([True]*10,[True]*10),"JOINT")
        self.assertEqual(a.e.longest([True]*10),10)

    def test_nonaligned_vectors_rejected(self):
        with self.assertRaises(ValueError):
            a.classify([True],[])
