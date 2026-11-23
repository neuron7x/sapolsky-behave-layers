"""Counterexamples and complete finite support qualification."""
import unittest

from experiments.cneh_exp_04c import qualification as q


class TestBoundedSupport(unittest.TestCase):
    def test_exhaustive_containment(self):
        result = q.qualification()
        self.assertEqual(result["cases"], 14700)
        self.assertEqual(result["false_exclusions"], 0)
        self.assertGreater(result["ambiguous_cases"], 0)
        self.assertGreater(result["singleton_cases"], 0)

    def test_complete_patterns_discriminate(self):
        c = (0, 1, 2, 3)
        for mode in c:
            m = q.MODES[mode]
            a = q.support(c, (1,0,0,0,0,0,0,0), (q.QUANTUM*m[0],)*16)
            b = q.support(a, (0,0,0,0,1,0,0,0), (q.QUANTUM*m[1],)*16)
            self.assertEqual(b, (mode,))

    def test_all_erased_silence_remains_ambiguous(self):
        self.assertEqual(q.support((0,1,2,3), (None,)*8, (0.,)*16), (0,1,2,3))

    def test_discrete_band_gap_defeats_convex_hull(self):
        bits = (None,0,0,0,0,0,0,0)
        r = (q.QUANTUM/2,)*16
        # Both endpoints bracket r, yet neither discrete band admits it.
        self.assertTrue(0 < r[0] < q.QUANTUM)
        self.assertEqual(q.support((0,), bits, r), ())

    def test_one_common_count_defeats_receiverwise_completion(self):
        bits = (None,0,0,0,0,0,0,0)
        self.assertEqual(q.support((0,), bits, (0.,)*16), (0,))
        self.assertEqual(q.support((0,), bits, (q.QUANTUM,)*16), (0,))
        self.assertEqual(q.support((0,), bits, (0.,)*8+(q.QUANTUM,)*8), ())

    def test_invalid_sensor_source_and_modes_fail(self):
        for bits in ((True,)*8, (2,)*8, (None,)*7):
            with self.assertRaises(ValueError):
                q.support((0,), bits, (0.,)*16)
        with self.assertRaises(ValueError):
            q.support((0,), (None,)*8, (float("nan"),)*16)
        with self.assertRaises(ValueError):
            q.support((0,0), (None,)*8, (0.,)*16)
        with self.assertRaises(ValueError):
            q.support((4,), (None,)*8, (0.,)*16)
        with self.assertRaisesRegex(ValueError, "MODEL_SET_VIOLATION"):
            q.update((0,1,2,3), (0,)*8, (0.,)*16, (1.,)*16)

    def test_observation_residual_bound_and_fail_closed(self):
        previous = (2. - q.EPS,)*16
        current = (2.*q.DECAY + q.QUANTUM + q.EPS,)*16
        self.assertEqual(q.update((0,1,2,3), (1,0,0,0,0,0,0,0), previous, current), (0,2))
        with self.assertRaises(ValueError):
            q.observed_residual((0.,)*15, (0.,)*16)
