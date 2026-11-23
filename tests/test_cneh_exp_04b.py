"""Analytic discrimination, observation-only replay, and abstention falsifiers."""
import itertools
import unittest

from experiments.cneh_exp_04b import run


def obs(tick, g, n0=0, n1=0):
    return run.Observation(tick, (g,) * 16, (1,) * n0 + (0,) * (4-n0) + (1,) * n1 + (0,) * (4-n1))


class TestNeuralReidentification(unittest.TestCase):
    def test_all_modes_identifiable_after_both_groups_fire(self):
        for mode in range(4):
            c = tuple(range(4))
            a = obs(0, 0., 1, 0)
            b = obs(1, run.prediction(mode, (1, 0)), 0, 1)
            c = run.compatible(c, a, b)
            d = obs(2, run.DECAY * b.gaba[0] + run.prediction(mode, (0, 1)))
            self.assertEqual(run.compatible(c, b, d), (mode,))

    def test_silence_is_not_identification(self):
        a, b = obs(0, 1.), obs(1, run.DECAY)
        self.assertEqual(run.compatible(tuple(range(4)), a, b), tuple(range(4)))

    def test_hidden_cut_detects_then_probe_resolves_disconnect(self):
        p = run.Policy("ACTIVE_REID")
        p.observe(obs(0, 0., 1, 0))
        p.observe(obs(1, 0., 0, 1))
        self.assertEqual(p.candidates, (1, 3))
        self.assertEqual(p.act(), (1, "ACTIVE_PROBE"))
        p.observe(obs(2, 0.))
        self.assertEqual(p.candidates, (3,))
        self.assertEqual(p.identified, 2)
        self.assertEqual(run.known_action(3, obs(101, 0.)), (None, "DISCONNECTED_ABSTAIN"))

    def test_nominal_never_detects_exact_nominal_tape(self):
        p = run.Policy("ACTIVE_REID")
        g = 0.
        for tick in range(20):
            p.observe(obs(tick, g, 1, 0))
            g = run.DECAY * (g + run.WEIGHT)
        self.assertIsNone(p.detected)

    def test_maximin_group_really_partitions_candidates(self):
        for n in (2, 3, 4):
            for c in itertools.combinations(range(4), n):
                g = run.distinguishing_group(c)
                self.assertGreater(len({run.MODES[i][g] for i in c}), 1)

    def test_falsifies_single_receiver_corruption_and_nan(self):
        a = obs(0, 0., 1, 0)
        b = run.Observation(1, (0.,) * 15 + (1.,), (0,) * 8)
        self.assertEqual(run.compatible(tuple(range(4)), a, b), ())
        with self.assertRaises(ValueError):
            obs(0, float("nan"))

    def test_tape_action_forgery_and_privileged_metadata_do_not_drive_policy(self):
        a = obs(0, 0., 1, 0)
        row = {**run.obs_record(a), "candidates": [0], "detected": None, "identified": None,
               "group": 0, "kind": "SENTINEL", "evaluator_mode": 3}
        run.audit_policy_tape([row], "ACTIVE_REID")
        row["evaluator_mode"] = 1
        run.audit_policy_tape([row], "ACTIVE_REID")
        row["group"] = 1
        with self.assertRaisesRegex(ValueError, "action differs"):
            run.audit_policy_tape([row], "ACTIVE_REID")
