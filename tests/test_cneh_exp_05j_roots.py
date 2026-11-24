"""Adversarial tests for independent dense root isolation and reset evidence."""
from fractions import Fraction as F
import unittest

from experiments.cneh_exp_05j import integrator as c
from experiments.cneh_exp_05j import verify as v


class TestRoot(unittest.TestCase):
    def test_hidden_crossing_equal_sign_endpoints(self):
        p=(F(-1,16),F(1),F(-1))
        l,u=c.first_upcross(p)
        self.assertLess(u,F(1,2))
        self.assertTrue(l<=v.verify_bracket(p,l,u)<=u)

    def test_earliest_of_multiple_upcrossings(self):
        p=(F(-3,32),F(11,16),F(-3,2),F(1))
        l,u=c.first_upcross(p)
        self.assertEqual((l,u),(F(1,4),F(1,4)))
        v.verify_bracket(p,l,u)
        with self.assertRaisesRegex(ValueError,"earlier root"):
            v.verify_bracket(p,F(3,4),F(3,4))

    def test_no_crossing(self):
        self.assertIsNone(c.first_upcross((F(-1),F(1),F(-1))))

    def test_grazing_fails_closed(self):
        with self.assertRaises(ValueError):
            c.first_upcross((F(-1,4),F(1),F(-1)))

    def test_odd_multiple_root_not_transverse(self):
        # (x-1/3)^3 changes sign, and both endpoints and midpoint
        # have strictly positive derivatives, but its root is grazing.
        p=(F(-1,27),F(1,3),F(-1),F(1))
        den=2**72
        l,u=F(den//3,den),F(den//3+1,den)
        with self.assertRaisesRegex(ValueError,"nontransverse"):
            v.verify_bracket(p,l,u)
        with self.assertRaises(ValueError):
            c.first_upcross(p)

    def test_exact_endpoint(self):
        p=(F(-1),F(1))
        self.assertEqual(c.first_upcross(p),(F(1),F(1)))
        self.assertEqual(v.verify_bracket(p,F(1),F(1)),F(1))

    def test_invalid_bracket(self):
        with self.assertRaises(ValueError):
            v.verify_bracket((F(-1),F(2)),F(0),F(1))
        with self.assertRaises(ValueError):
            v.verify_bracket((F(-1),F(2)),F(3,4),F(3,4))

    def test_impulse_left_limit(self):
        self.assertEqual(v.analytic_value(0.,[(1.,.5)],6.,1.),0.)
        self.assertGreater(v.analytic_value(0.,[(1.,.5)],6.,1.0001),0.49)


if __name__=="__main__":
    unittest.main()
