"""Falsification controls for the separate EXP03B gain intervention."""
from __future__ import annotations

import unittest

import numpy as np

from experiments.cneh_exp_03 import gain_intervention as g


class TestGainIntervention(unittest.TestCase):
    def test_gain_buffer_mismatch_is_rejected(self):
        u = np.array([300., 320.])
        g.check_current(u + 25., u, 1.5, 50., np)
        with self.assertRaisesRegex(ValueError, "gain intervention"):
            g.check_current(u, u, 1.5, 50., np)

    def test_conductance_oracle_rejects_ignored_arrival(self):
        expected = (np.array([1., 0.]), np.zeros(2), np.zeros(2))
        self.assertEqual(g.check_delivery(expected, expected, np, 1e-10, 1e-12), 0.)
        with self.assertRaisesRegex(ValueError, "independent oracle"):
            g.check_delivery((np.zeros(2), np.zeros(2), np.zeros(2)), expected, np, 1e-10, 1e-12)

    def test_conductance_nan_fails(self):
        expected = (np.zeros(2), np.zeros(2), np.zeros(2))
        with self.assertRaises(ValueError):
            g.check_delivery((np.array([float("nan"), 0.]), *expected[1:]), expected, np, 1e-10, 1e-12)

    def test_prospective_probe_is_mean_free_and_bounded(self):
        p = g.protocol()
        wave = g.probe(p)
        self.assertEqual(len(wave), 600)
        self.assertAlmostEqual(sum(wave), 0., places=8)
        self.assertTrue(all(0. <= 300. + v <= 500. for v in wave))
        self.assertAlmostEqual(sum(v*v for v in wave), 1920000., places=6)

    def test_new_cohort_disjoint_from_prior_exp03(self):
        p = g.protocol()
        self.assertFalse(set(p["seeds"]) & set(range(82001, 82009)))
        self.assertFalse(p["scientific_promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
