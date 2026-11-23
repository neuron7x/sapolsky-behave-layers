"""Structural intervention falsifiers, independent of favorable neural outcomes."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from experiments.cneh_exp_03 import run


class TestCNEHStructuralOOD(unittest.TestCase):
    def test_factorial_contrast_and_null(self):
        self.assertEqual(run.interaction(dict(zip(run.ARMS, [1., 4., 2., 3.]))), 2.)
        self.assertEqual(run.interaction(dict.fromkeys(run.ARMS, 1.)), 0.)
        with self.assertRaises(ValueError):
            run.interaction({"SHAM_BASE": 0.})
        with self.assertRaises(ValueError):
            run.interaction(dict.fromkeys(run.ARMS, float("nan")))

    def test_probe_leaves_receiver_unchanged_and_has_no_early_leak(self):
        p = run.read_protocol()
        t = p["network"]["intervention_tick"]
        for arm in p["arms"]:
            self.assertEqual(run.direct_currents(t - 1, arm, p), (300., 300.))
            for tick in range(t, p["network"]["steps"]):
                self.assertEqual(run.direct_currents(tick, arm, p)[1], 300.)
        self.assertNotEqual(
            run.direct_currents(t + 20, p["arms"][1], p)[0],
            run.direct_currents(t + 20, p["arms"][0], p)[0],
        )

    def test_directional_mask_both_presynaptic_cell_types(self):
        import numpy as np

        e = np.arange(1., 9.).reshape(4, 2)
        i = np.arange(11., 19.).reshape(4, 2)
        # A contains E0 and I0; B contains E1 and I1.
        a, b = [0, 2], [1, 3]
        expected_e, expected_i = e.copy(), i.copy()
        expected_e[b, 0] = 0
        expected_i[b, 0] = 0
        got_e, got_i, witness = run.cut_weights(e, i, a, b, 2, np, cut=True)
        np.testing.assert_array_equal(got_e, expected_e)
        np.testing.assert_array_equal(got_i, expected_i)
        self.assertEqual(witness["removed_AB_edges"], 4)
        self.assertTrue(np.all(e != 0) and np.all(i != 0))
        sham_e, sham_i, sham = run.cut_weights(e, i, a, b, 2, np, cut=False)
        self.assertEqual(sham_e.tobytes(), e.tobytes())
        self.assertEqual(sham_i.tobytes(), i.tobytes())
        self.assertEqual(sham["removed_AB_edges"], 0)

    def test_zero_or_malformed_structural_intervention_rejected(self):
        import numpy as np

        z = np.zeros((4, 2))
        with self.assertRaisesRegex(ValueError, "no A-to-B"):
            run.cut_weights(z, z, [0, 2], [1, 3], 2, np, cut=True)
        with self.assertRaises(ValueError):
            run.cut_weights(z.T, z, [0, 2], [1, 3], 2, np, cut=True)
        z[0, 0] = float("inf")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            run.cut_weights(z, z, [0, 2], [1, 3], 2, np, cut=True)

    def fixture(self):
        p = copy.deepcopy(run.read_protocol())
        p["network"]["steps"] = 4
        p["network"]["intervention_tick"] = 2
        episodes = []
        for arm in p["arms"]:
            rows = []
            for tick in range(4):
                a, b = run.direct_currents(tick, arm, p)
                rows.append({"tick": tick, "u_A_pA": a.hex(), "u_B_pA": b.hex(),
                             "spikes_A": 1, "spikes_B": 1,
                             "mean_voltage_B_mV": (-60.).hex(),
                             "state_sha256": "state", "rng_sha256": str(tick)})
            episodes.append({
                "seed": 82001, "arm": arm["name"],
                "initial_state_sha256": "state", "initial_matrix_sha256": "matrix",
                "pre_spikes_A": 2, "pre_spikes_B": 2,
                "structure": {"cut": arm["cut"], "off_target_unchanged": True,
                              "available_AB_edges": 3,
                              "removed_AB_edges": 3 if arm["cut"] else 0},
                run.ENDPOINTS[0]: 2 / 16, run.ENDPOINTS[1]: -60.,
                "trace": rows, "trace_sha256": run.pinned.sha(run.pinned.canonical(rows)),
            })
        return p, episodes

    def test_valid_null_world_is_not_rejected(self):
        p, rows = self.fixture()
        self.assertTrue(run.verify_world(rows, p)["pre_spiking_qualified"])
        self.assertEqual(run.verify_world(rows, p)["contrasts"][run.ENDPOINTS[0]], 0.)

    def test_reject_preintervention_state_leak(self):
        p, rows = self.fixture()
        rows[1]["trace"][0]["state_sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "pre-intervention"):
            run.verify_world(rows, p)

    def test_reject_rng_and_direct_receiver_confound(self):
        for field, value, message in [
            ("rng_sha256", "changed", "random tape"),
            ("u_B_pA", (301.).hex(), "receiver input"),
        ]:
            p, rows = self.fixture()
            rows[1]["trace"][3][field] = value
            with self.assertRaisesRegex(ValueError, message):
                run.verify_world(rows, p)

    def test_reject_outcome_fabrication_and_wrong_mask_count(self):
        p, rows = self.fixture()
        rows[1][run.ENDPOINTS[0]] += 1
        with self.assertRaisesRegex(ValueError, "derived endpoint"):
            run.verify_world(rows, p)
        p, rows = self.fixture()
        rows[2]["structure"]["removed_AB_edges"] = 2
        with self.assertRaisesRegex(ValueError, "wrong number"):
            run.verify_world(rows, p)

    def test_rehashed_bundle_does_not_authenticate_altered_result(self):
        expected = {"verdict.json": b'{"scientific_promotion_authorized":false}\n',
                    "raw.csv": b"seed,result\n1,0\n"}
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "bundle"
            run.write_bundle(out, expected)
            run.verify_payload(out, expected)
            changed = dict(expected, **{"raw.csv": b"seed,result\n1,1\n"})
            (out / "raw.csv").write_bytes(changed["raw.csv"])
            (out / "SHA256SUMS").write_bytes(run.manifest(changed))
            with self.assertRaisesRegex(ValueError, "deterministic replay"):
                run.verify_payload(out, expected)
            with self.assertRaises(FileExistsError):
                run.write_bundle(out, expected)


if __name__ == "__main__":
    unittest.main()
