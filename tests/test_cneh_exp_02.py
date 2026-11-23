"""Adversarial engineering tests for the exploratory CNEH-EXP-02 pilot."""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "experiments" / "cneh_exp_02"
SPEC = importlib.util.spec_from_file_location("cneh_cortices", ROOT / "run.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class CNEHTwoCortexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = json.loads((ROOT / "protocol.json").read_text())
        cls.seeds = cls.p["cohorts"]["smoke"]

    def test_01_two_separate_local_observers(self):
        a = mod.Cortex(0, self.p)
        b = mod.Cortex(1, self.p)
        pa = mod.Packet.from_bytes(a.observe(0.1, 0))
        pb = mod.Packet.from_bytes(b.observe(-0.2, 0))
        self.assertEqual((pa.origin, pb.origin), (0, 1))
        self.assertEqual((pa.tick, pb.tick), (0, 0))
        self.assertNotEqual(pa.state, pb.state)
        self.assertEqual(len(pa.to_bytes()), self.p["agent"]["packet_bytes_per_direction"])

    def test_02_invalid_or_replayed_packet_is_rejected(self):
        cortex = mod.Cortex(0, self.p)
        cortex.observe(0.0, 0)
        bad = mod.Packet(1, 1, 0.0, 0.0, 0.0, 0.0).to_bytes()
        with self.assertRaisesRegex(ValueError, "contemporaneous"):
            cortex.act(0, bad, (0.0, 0.0), "COUPLED")
        bad_source = mod.Packet(0, 0, 0.0, 0.0, 0.0, 0.0).to_bytes()
        with self.assertRaisesRegex(ValueError, "identity"):
            cortex.act(0, bad_source, (0.0, 0.0), "COUPLED")
        with self.assertRaises(ValueError):
            mod.Packet.from_bytes(b"too short")

    def test_03_randomness_and_trace_are_replay_deterministic(self):
        for seed in self.seeds[:4]:
            for arm in ("COUPLED", "CENTRAL_EMULATOR", "STATIC_FUSION"):
                left, pa = mod.evaluate_world(seed, arm, self.p)
                right, pb = mod.evaluate_world(seed, arm, self.p)
                self.assertEqual(left, right)
                self.assertEqual(pa, pb)

    def test_04_unrestricted_monolith_is_exact_emulator(self):
        rows, metrics = mod.evaluate(self.seeds, self.p)
        self.assertTrue(metrics["emulator_exact_trace_parity"])
        by = {(r["seed"], r["arm"]): r for r in rows}
        for seed in self.seeds:
            self.assertEqual(by[seed, "COUPLED"]["trace_sha256"],
                             by[seed, "CENTRAL_EMULATOR"]["trace_sha256"])
            self.assertEqual(by[seed, "COUPLED"]["success"],
                             by[seed, "CENTRAL_EMULATOR"]["success"])
            self.assertEqual(by[seed, "COUPLED"]["operation_proxy"],
                             by[seed, "CENTRAL_EMULATOR"]["operation_proxy"])

    def test_05_time_stratified_content_swap_is_genuine_permutation(self):
        rows, metrics = mod.evaluate(self.seeds, self.p)
        self.assertEqual(len(rows), len(self.seeds) * len(mod.ARMS))
        self.assertTrue(metrics["scramble_donor_message_marginals_exact"])
        self.assertTrue(metrics["scramble_current_tick_envelope_parity"])
        self.assertTrue(metrics["all_world_budget_envelopes_pass"])
        mapping = mod.donor_rotation(self.seeds, self.p["model"])
        self.assertTrue(all(src != target for target, src in mapping.items()))
        self.assertTrue(all(
            src % len(self.p["model"]["theta_ood"]) ==
            target % len(self.p["model"]["theta_ood"])
            for target, src in mapping.items()
        ))

    def test_06_message_and_probe_ablations_are_not_aliases(self):
        rows, _ = mod.evaluate(self.seeds, self.p)
        by = {(r["seed"], r["arm"]): r for r in rows}
        self.assertTrue(any(
            by[s, "COUPLED"]["trace_sha256"] != by[s, "NO_PROBE"]["trace_sha256"]
            for s in self.seeds
        ))
        self.assertTrue(any(
            by[s, "COUPLED"]["trace_sha256"] != by[s, "SCRAMBLED_CONTENT"]["trace_sha256"]
            for s in self.seeds
        ))
        self.assertTrue(any(
            by[s, "COUPLED"]["trace_sha256"] != by[s, "DISCONNECTED"]["trace_sha256"]
            for s in self.seeds
        ))

    def test_07_no_cross_stratum_or_self_donors(self):
        with self.assertRaisesRegex(ValueError, "two world seeds per OOD stratum"):
            mod.evaluate(self.seeds[:4], self.p)
        with self.assertRaisesRegex(ValueError, "independent"):
            mod.evaluate(self.seeds + [self.seeds[0]], self.p)

    def test_08_smoke_evidence_is_replay_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "proof"
            mod.write_bundle(folder, self.seeds, "SMOKE", self.p)
            mod.verify_bundle(folder, self.p)
            self.assertEqual(
                json.loads((folder / "verdict.json").read_text())["verdict"],
                "EXPLORATORY_INTERNAL_ONLY",
            )
            self.assertFalse(json.loads(
                (folder / "verdict.json").read_text())["scientific_promotion_authorized"])

    def test_09_rehashed_forged_weak_control_is_rejected(self):
        """A perfect SHA256 re-signing of altered evidence is not sufficient."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "proof"
            mod.write_bundle(folder, self.seeds, "SMOKE", self.p)
            csv_path = folder / "episodes.csv"
            with csv_path.open(newline="", encoding="utf-8") as fh:
                rdr = csv.DictReader(fh)
                fields, rows = list(rdr.fieldnames), list(rdr)
            changed = next(r for r in rows if r["arm"] == "HOMOGENEOUS_VIEW")
            changed["success"] = str(1 - int(changed["success"]))
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            sealed = sorted(
                p for p in folder.iterdir() if p.is_file() and p.name != "SHA256SUMS"
            )
            (folder / "SHA256SUMS").write_text(
                "".join(f"{mod.sha(p.read_bytes())}  {p.name}\n" for p in sealed),
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "re-signed"):
                mod.verify_bundle(folder, self.p)

    def test_10_unregistered_artifact_blocks_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "proof"
            mod.write_bundle(folder, self.seeds, "SMOKE", self.p)
            (folder / "forged_extra.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                mod.verify_bundle(folder, self.p)

    def test_11_truth_available_only_to_explicit_oracle(self):
        agent_a = mod.Cortex(0, self.p)
        agent_b = mod.Cortex(0, self.p)
        packet = mod.Packet(0, 1, 0.01, 0.03, 0.0, 0.0).to_bytes()
        agent_a.observe(0.3, 0)
        agent_b.observe(0.3, 0)
        action_with_trap = agent_a.act(
            0, packet, (0.1, 0.2), "COUPLED", truth=(999.,999.), true_theta=999.
        )
        action_without_truth = agent_b.act(
            0, packet, (0.1, 0.2), "COUPLED"
        )
        self.assertEqual(action_with_trap, action_without_truth)

    def test_12_preregistration_contract_is_frozen(self):
        self.assertEqual(
            self.p["hypothesis_status"], "FORMALIZED / EMPIRICAL VALIDATION PENDING"
        )
        self.assertFalse(self.p["scientific_promotion_allowed"])
        self.assertFalse(self.p["independent_replication"])
        self.assertEqual(
            mod.sha(
                (ROOT.parent / "cneh_exp_01" / "CNEH-04-DC_Formal_Specification.md").read_bytes()
            ),
            self.p["source_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
