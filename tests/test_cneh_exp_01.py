"""CNEH-EXP-01 synthetic preflight regression tests; NOT blind replication."""
import importlib.util
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/"experiments"/"cneh_exp_01"
SPEC=importlib.util.spec_from_file_location("cneh_pilot", ROOT/"run.py")
assert SPEC and SPEC.loader
import sys
mod=importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name]=mod
SPEC.loader.exec_module(mod)


class CNEHPreflightTests(unittest.TestCase):
    def setUp(self):
        self.protocol=json.loads((ROOT/"protocol.json").read_text())

    def test_common_mode_action_bound_violation_rejected_at_plant_boundary(self):
        with patch.object(mod.Controller, "act", return_value=(0.81, 0.0)):
            with self.assertRaisesRegex(ValueError, "physical interface bound"):
                mod.simulate(3001, "COUPLED", self.protocol)

    def test_concurrent_writers_cannot_overwrite_sealed_bundle(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        original = mod.evaluate
        rendezvous = threading.Barrier(2)

        def synchronized(*args):
            result = original(*args)
            rendezvous.wait(timeout=5)
            return result

        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "bundle"
            with patch.object(mod, "evaluate", side_effect=synchronized), ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(mod.write_bundle, out, "SMOKE", [seed], self.protocol)
                           for seed in (3001, 3002)]
                outcomes = [future.exception() for future in futures]
            self.assertEqual(sum(error is None for error in outcomes), 1)
            self.assertEqual(sum(isinstance(error, FileExistsError) for error in outcomes), 1)
            self.assertEqual(mod.verify_bundle(out, require_valid=True)["verdict"], "REPLICATION_NOT_TESTED")

    @staticmethod
    def resign(out):
        files = sorted(p for p in out.iterdir() if p.name != "SHA256SUMS")
        (out / "SHA256SUMS").write_text(
            "".join(f"{mod.digest(p.read_bytes())}  {p.name}\n" for p in files),
            encoding="ascii",
        )

    def test_faithful_centralized_emulator_parity(self):
        for seed in (3001,3002,3003,51001,51128):
            a=mod.simulate(seed,"COUPLED",self.protocol)
            b=mod.simulate(seed,"CENTRAL_EMULATOR",self.protocol)
            self.assertEqual(a["trace_sha256"],b["trace_sha256"])
            self.assertEqual(a["success"],b["success"])
            self.assertLessEqual(b["message_bytes"],a["message_bytes"])

    def test_exact_replay(self):
        for arm in mod.ARMS:
            self.assertEqual(mod.simulate(3001,arm,self.protocol),
                             mod.simulate(3001,arm,self.protocol))

    def test_trace_hash_detects_one_ulp_and_signed_zero(self):
        # A 12-decimal hash cannot distinguish these, despite different binary64.
        next_float = math.nextafter(1.0, math.inf)
        self.assertEqual(round(1.0, 12), round(next_float, 12))
        self.assertNotEqual(mod.trace_digest([[1.0]]), mod.trace_digest([[next_float]]))
        self.assertNotEqual(mod.trace_digest([[0.0]]), mod.trace_digest([[-0.0]]))

    def test_subdecimal_emulator_divergence_is_detected(self):
        original = mod.Controller.act

        def faulty(controller, t, sensed, goal, arm, plant, **kwargs):
            action = original(controller, t, sensed, goal, arm, plant, **kwargs)
            if arm == "CENTRAL_EMULATOR":
                return math.nextafter(action[0], 0.0), action[1]
            return action

        with patch.object(mod.Controller, "act", faulty):
            _, metrics = mod.evaluate([3001, 3002], self.protocol)
        self.assertFalse(metrics["emulator_trace_parity"])

    def test_initial_state_safety_is_part_of_whole_path(self):
        protocol = copy.deepcopy(self.protocol)
        protocol["model"].update({
            "initial_state_abs_bound": 10.0, "safety_abs_bound": 1.0,
            "A_base_diagonal": [0.0, 0.0], "cross_coupling_nominal": 0.0,
            "step_horizon": 1, "goal_abs_bound": 0.0,
            "process_noise_sd": 0.0, "observation_noise_sd": 0.0,
        })
        row = mod.simulate(3001, "COUPLED", protocol)
        self.assertEqual(row["safe"], 0)
        self.assertEqual(row["success"], 0)

    def test_budget_and_scrambled_traffic(self):
        rows,m=mod.evaluate([3001,3002],self.protocol)
        self.assertTrue(m["all_budget_envelopes_pass"])
        self.assertTrue(m["scrambled_traffic_envelope_parity"])
        self.assertEqual(len(rows),20)

    def test_memory_proxy_envelope_is_enforced(self):
        for limit, expected in ((255, 0), (256, 1)):
            with self.subTest(limit=limit):
                protocol = copy.deepcopy(self.protocol)
                protocol["resource_envelope"]["controller_memory_proxy_bytes_max"] = limit
                row = mod.simulate(3001, "COUPLED", protocol)
                self.assertEqual(row["budget_ok"], expected)
                if not expected:
                    self.assertEqual(row["success"], 0)

    def test_no_colliding_arms_or_world_seeds(self):
        with self.assertRaises(ValueError):
            mod.evaluate([3001,3001],self.protocol)
        with self.assertRaises(ValueError):
            mod.simulate(3001,"NOT_A_POLICY",self.protocol)

    def test_invalid_world_seed_values_are_rejected(self):
        for seeds in ([], [True], [3001.0], ["3001"], [-3001], [[3001]], (3001,)):
            with self.subTest(seeds=seeds), self.assertRaises(ValueError):
                mod.evaluate(seeds, self.protocol)

    def test_nonfinite_controller_action_is_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), patch.object(mod.Controller, "act", return_value=(value, 0.0)):
                with self.assertRaisesRegex(ValueError, "nonfinite"):
                    mod.simulate(3001, "COUPLED", self.protocol)

    def test_invalid_cohort_or_protocol_leaves_no_bundle(self):
        altered = copy.deepcopy(self.protocol)
        altered["material_effect"] = 0.0
        cases = (("REPLICATION", [3001], self.protocol),
                 ("PRIMARY", [51001], self.protocol),
                 ("SMOKE", [], self.protocol),
                 ("SMOKE", [True], self.protocol),
                 ("SMOKE", [3001], altered))
        with tempfile.TemporaryDirectory() as root:
            for i, (phase, seeds, protocol) in enumerate(cases):
                out = Path(root) / str(i)
                with self.subTest(phase=phase, seeds=seeds), self.assertRaises(ValueError):
                    mod.write_bundle(out, phase, seeds, protocol)
                self.assertFalse(out.exists())

    def test_hash_integrity_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/"bundle"
            mod.write_bundle(out,"SMOKE",[3001,3002],self.protocol)
            mod.verify_bundle(out)
            with (out/"verdict.json").open("a") as f:
                f.write(" ")
            with self.assertRaises(ValueError):
                mod.verify_bundle(out)

    def test_resigned_raw_result_lie_is_rejected(self):
        """A freshly rehashed forged non-primary CSV row must still fail."""
        import csv
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "bundle"
            mod.write_bundle(out, "SMOKE", [3001, 3002], self.protocol)
            csv_path = out / "pilot.csv"
            with csv_path.open(encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                fields, rows = list(reader.fieldnames), list(reader)
            target = next(row for row in rows if row["arm"] == "A_ONLY")
            target["success"] = str(1 - int(target["success"]))
            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            manifest = sorted(p for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS")
            (out / "SHA256SUMS").write_text(
                "".join(f"{mod.digest(p.read_bytes())}  {p.name}\n" for p in manifest),
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "raw trajectory"):
                mod.verify_bundle(out)

    def test_resigned_protocol_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "bundle"
            mod.write_bundle(out, "SMOKE", [3001, 3002], self.protocol)
            protocol = json.loads((out / "protocol.json").read_text())
            protocol["material_effect"] = 0.0  # hostile threshold override
            (out / "protocol.json").write_bytes(mod.canonical(protocol))
            manifest = sorted(p for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS")
            (out / "SHA256SUMS").write_text(
                "".join(f"{mod.digest(p.read_bytes())}  {p.name}\n" for p in manifest),
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "resigned protocol"):
                mod.verify_bundle(out)

    def test_resigned_derived_claims_are_rejected(self):
        cases = (
            ("budget.json", "observed_max_control_energy_proxy", 0.0),
            ("budget.json", "observed_max_controller_compute_proxy_ops", 0),
            ("budget.json", "observed_max_message_bytes", 0),
            ("budget.json", "observed_max_controller_memory_proxy_bytes", 0),
            ("budget.json", "observed_max_latency_steps", 0),
            ("budget.json", "external_training_budget_verified", True),
            ("budget.json", "hardware_flops_verified", 0),
            ("safety.json", "chance_constraint_verified", True),
            ("safety.json", "gate", "PHYSICALLY_SAFE"),
            ("negative_controls.json", "outcome", "SUPPORTED"),
            ("verdict.json", "limitations", []),
            ("verdict.json", "policy_boundary", "UNRESTRICTED_ADVANTAGE"),
            ("verdict.json", "scientific_promotion_authorized", True),
            ("seeds.json", "source", "independent external operator"),
            ("seeds.json", "n_world_seeds", 2.0),
            ("implementation.json", "runner_sha256", "0" * 64),
            ("implementation.json", "evidence_format_version", 1),
        )
        for name, key, value in cases:
            with self.subTest(file=name, key=key), tempfile.TemporaryDirectory() as root:
                out = Path(root) / "bundle"
                mod.write_bundle(out, "SMOKE", [3001, 3002], self.protocol)
                obj = json.loads((out / name).read_text())
                obj[key] = value
                (out / name).write_bytes(mod.canonical(obj))
                self.resign(out)
                with self.assertRaisesRegex(ValueError, "derived evidence"):
                    mod.verify_bundle(out)

    def test_missing_or_additional_derived_fields_are_rejected(self):
        for operation in ("delete", "add"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as root:
                out = Path(root) / "bundle"
                mod.write_bundle(out, "SMOKE", [3001, 3002], self.protocol)
                obj = json.loads((out / "verdict.json").read_text())
                if operation == "delete":
                    del obj["limitations"]
                else:
                    obj["unsupported_authority"] = "SUPPORTED_NARROW"
                (out / "verdict.json").write_bytes(mod.canonical(obj))
                self.resign(out)
                with self.assertRaisesRegex(ValueError, "derived evidence"):
                    mod.verify_bundle(out)

    def test_ambiguous_json_is_rejected_even_when_resigned(self):
        for extra in ('"chance_constraint_verified":false', '"extra":NaN',
                      '"extra":Infinity', '"extra":1e400'):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as root:
                out = Path(root) / "bundle"
                mod.write_bundle(out, "SMOKE", [3001, 3002], self.protocol)
                original = (out / "safety.json").read_text().strip()
                (out / "safety.json").write_text(original[:-1] + "," + extra + "}\n")
                self.resign(out)
                with self.assertRaisesRegex(ValueError, "duplicate JSON|nonfinite JSON"):
                    mod.verify_bundle(out)

    def test_authentic_negative_is_retained_but_cannot_qualify(self):
        # Deterministic injected fault in both execution and replay. The file
        # integrity checker must retain this negative without calling it valid.
        original = mod.Controller.act

        def faulty(controller, t, sensed, goal, arm, plant, **kwargs):
            action = original(controller, t, sensed, goal, arm, plant, **kwargs)
            if arm == "CENTRAL_EMULATOR":
                return math.nextafter(action[0], 0.0), action[1]
            return action

        with tempfile.TemporaryDirectory() as root, patch.object(mod.Controller, "act", faulty):
            out = Path(root) / "bundle"
            mod.write_bundle(out, "SMOKE", [3001, 3002], self.protocol)
            verdict = mod.verify_bundle(out)
            self.assertEqual(verdict["verdict"], "INVALID")
            self.assertFalse(verdict["scientific_promotion_authorized"])
            with self.assertRaisesRegex(ValueError, "authentic negative evidence"):
                mod.verify_bundle(out, require_valid=True)
            self.assertTrue((out / "SHA256SUMS").is_file())

    def test_extra_bundle_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "bundle"
            mod.write_bundle(out, "SMOKE", [3001, 3002], self.protocol)
            (out / "UNREGISTERED.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "membership"):
                mod.verify_bundle(out)

    def test_unsupported_replication_claim_forbidden(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/"bundle"
            mod.write_bundle(out,"SMOKE",[3001,3002],self.protocol)
            x=json.loads((out/"verdict.json").read_text())
            self.assertFalse(x["independent_blind_replication"])
            self.assertFalse(x["scientific_promotion_authorized"])
            self.assertEqual(x["verdict"],"REPLICATION_NOT_TESTED")


if __name__=="__main__":
    unittest.main()
