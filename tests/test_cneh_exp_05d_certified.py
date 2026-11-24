"""Falsifiers for binary64 rounding and the bounded exp certificate."""
from __future__ import annotations

from decimal import localcontext, ROUND_UP
from fractions import Fraction
import math
import random
import unittest

from experiments.cneh_exp_05d import certified as c


class TestCertifiedExp(unittest.TestCase):
    def test_halfway_rounding_is_even(self):
        one = 1 << 52
        self.assertEqual(c.rational_bits(2*one+1, 2*one), c.bits(1.))
        self.assertEqual(c.rational_bits(2*one+3, 2*one), c.bits(1.)+2)
        self.assertEqual(c.rational_bits(4*one-1, 2*one), c.bits(2.))

    def test_integer_rounding_against_independent_fraction(self):
        rng = random.Random(93003)
        for _ in range(2048):
            p, q = rng.getrandbits(120)+1, rng.getrandbits(120)+1
            self.assertEqual(c.rational_bits(p, q), c.bits(float(Fraction(p, q))))

    def test_independent_taylor_enclosure(self):
        rng = random.Random(93004)
        xs = [-32., -20., -1., -0., 0., math.nextafter(0., 1.),
              math.nextafter(0., -1.), .1, 1., 20., 32.]
        xs.extend(rng.uniform(-32., 32.) for _ in range(64))
        for x in xs:
            self.assertEqual(c.certificate(x)[0], c.independent_taylor(x)[0], x.hex())

    def test_ambient_decimal_context_cannot_change_output(self):
        xs = [-32., -2.3, .1, 19.98, 32.]
        expected = [c.certificate(x) for x in xs]
        c._certificate.cache_clear()
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.rounding = ROUND_UP
            self.assertEqual([c.certificate(x) for x in xs], expected)

    def test_invalid_domain_fails_closed(self):
        for x in (math.nan, math.inf, -math.inf, -33., 33., 1, True, "0.1"):
            with self.assertRaises(ValueError):
                c.certificate(x)

    def test_negative_zero(self):
        self.assertEqual(c.certified_exp(-0.), 1.)
        self.assertEqual(c.certified_exp(0.), 1.)


if __name__ == "__main__":
    unittest.main()
