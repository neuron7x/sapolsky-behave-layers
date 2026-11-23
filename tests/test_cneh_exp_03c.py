"""Known-answer falsifiers for exact receiver state comparison."""
import copy
import unittest

from experiments.cneh_exp_03c import run


def state():
    return {**{k: [(0.).hex()] * 16 for k in run.FIELDS[:-1]}, "spikes": [0] * 16}


class TestExactIsolation(unittest.TestCase):
    def test_identical_complete_state(self):
        self.assertEqual(run.compare_states(state(), state())["differences"], 0)

    def test_one_ulp_and_signed_zero_not_hidden(self):
        a, b = state(), state()
        b["g_nmda"][3] = (-0.).hex()
        b["V_mV"][2] = (5e-324).hex()
        q = run.compare_states(a, b)
        self.assertEqual(q["differences"], 2)
        self.assertEqual(q["first"]["field"], "V_mV")

    def test_spike_change_cannot_cancel_across_neurons(self):
        a, b = state(), state()
        a["spikes"][0], b["spikes"][1] = 1, 1
        self.assertEqual(sum(a["spikes"]), sum(b["spikes"]))
        self.assertEqual(run.compare_states(a, b)["differences"], 2)

    def test_missing_field_and_nonfinite_are_rejected(self):
        a = state()
        b = copy.deepcopy(a)
        del b["w_pA"]
        with self.assertRaises(ValueError):
            run.compare_states(a, b)
        b = copy.deepcopy(a)
        b["g_ampa"][0] = "nan"
        with self.assertRaises(ValueError):
            run.compare_states(a, b)
