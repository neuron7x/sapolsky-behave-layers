"""Analytic fixtures and independent identities, not neural estimator validation."""
import math
import random
import unittest

from experiments.cneh_exp_01.estimators import gaussian_mean_fisher, observability_gramian, pid_imin, qualify


class EstimatorQualificationTests(unittest.TestCase):
    def test_frozen_known_answers(self):
        report = qualify()
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["causal_attribution_qualified"])
        self.assertFalse(report["neural_estimators_qualified"])
        self.assertGreaterEqual(len(report["checks"]), 25)

    def test_fisher_quadratic_score_identity_and_reparametrization(self):
        rng = random.Random(22)
        for _ in range(30):
            j = [[rng.uniform(-2, 2) for _ in range(3)] for _ in range(5)]
            v = [rng.uniform(-2, 2) for _ in range(3)]
            fisher = gaussian_mean_fisher(j, 0.7)
            left = sum(v[a] * fisher[a][b] * v[b] for a in range(3) for b in range(3))
            right = sum(sum(row[a] * v[a] for a in range(3)) ** 2 for row in j) / 0.7
            self.assertAlmostEqual(left, right, places=11)
            self.assertGreaterEqual(left, -1e-12)
            rescaled = gaussian_mean_fisher([[2 * x for x in row] for row in j], 0.7)
            self.assertAlmostEqual(rescaled[0][1], 4 * fisher[0][1], places=11)

    def test_gramian_matches_independent_trajectory_energy(self):
        rng = random.Random(23)
        for _ in range(30):
            a = [[rng.uniform(-0.5, 0.5) for _ in range(3)] for _ in range(3)]
            c = [[rng.uniform(-1, 1) for _ in range(3)] for _ in range(2)]
            x = [rng.uniform(-1, 1) for _ in range(3)]
            w = observability_gramian(a, c, 8)
            expected = sum(x[i] * w[i][j] * x[j] for i in range(3) for j in range(3))
            actual = 0
            for _ in range(8):
                actual += sum(sum(row[j] * x[j] for j in range(3)) ** 2 for row in c)
                x = [sum(row[j] * x[j] for j in range(3)) for row in a]
            self.assertAlmostEqual(actual, expected, places=11)

    def test_invalid_inputs_never_become_information(self):
        for bad in (float("nan"), float("inf"), True, "1"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    gaussian_mean_fisher([[bad]], 1)
                with self.assertRaises(ValueError):
                    gaussian_mean_fisher([[1]], bad)
                with self.assertRaises(ValueError):
                    observability_gramian([[bad]], [[1]], 2)
                with self.assertRaises(ValueError):
                    pid_imin({(0, 0, 0): bad})
        for variance in (0, -1):
            with self.assertRaises(ValueError):
                gaussian_mean_fisher([[1]], variance)
        for matrix in ([], [[]], [[1], [1, 2]]):
            with self.assertRaises(ValueError):
                gaussian_mean_fisher(matrix, 1)
        for horizon in (0, -1, True, 1.5, 10001):
            with self.assertRaises(ValueError):
                observability_gramian([[1]], [[1]], horizon)
        with self.assertRaises(ValueError):
            observability_gramian([[1, 0]], [[1]], 2)
        with self.assertRaises(ValueError):
            observability_gramian([[1]], [[1, 0]], 2)

    def test_pid_rejects_invalid_mass_and_reconstructs_nonuniform(self):
        for pmf in ({}, {(0, 0, 0): 0.9}, {(0, 0, 0): 1.1, (1, 1, 1): -0.1}, {(True, 0, 0): 1}):
            with self.assertRaises(ValueError):
                pid_imin(pmf)
        p = pid_imin({(0, 0, 0): 0.25, (1, 1, 1): 0.75})
        entropy = -0.25 * math.log2(0.25) - 0.75 * math.log2(0.75)
        self.assertAlmostEqual(p["redundancy_bits"], entropy)
        self.assertAlmostEqual(p["synergy_bits"], 0)

    def test_finite_inputs_overflow_rejected(self):
        with self.assertRaises((ValueError, OverflowError)):
            gaussian_mean_fisher([[1e308]], 1)
        with self.assertRaises((ValueError, OverflowError)):
            observability_gramian([[1e308]], [[1]], 4)


if __name__ == "__main__":
    unittest.main()
