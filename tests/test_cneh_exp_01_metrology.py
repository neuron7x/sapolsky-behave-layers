"""Actual small measurements plus falsifiers; no hardware/causal superiority claim."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from experiments.cneh_exp_01 import metrology as mod


class MetrologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = mod.measure()  # One bounded measurement for the entire class.
        cls.contract = json.loads(mod.CONTRACT.read_text())

    @staticmethod
    def resign_worker_bytes(report):
        for worker in report["workers"]:
            worker["stdout_bytes"] = len(mod.run.canonical({key: value for key, value in worker.items()
                if key not in {"parent_start_ns", "parent_end_ns", "stdout_bytes", "repeat", "position"}}))

    def test_actual_resource_vector_has_complete_paired_blocks(self):
        report = mod.validate_report(self.report)
        self.assertEqual(report["admission"], "PASS")
        self.assertEqual(len(report["workers"]), 20)
        self.assertEqual(len(report["inherited_timing"]["raw"]), 200)
        self.assertEqual(sum(len(row["samples"]) for row in report["workers"]), 80)
        self.assertFalse(report["resource_parity_verified"])
        for row in report["workers"]:
            self.assertGreaterEqual(row["peak_rss_bytes"], row["baseline_peak_rss_bytes"])
            self.assertGreater(row["peak_rss_bytes"], 0)
            self.assertEqual(row["profile"]["payload_bytes"], row["profile"]["result"]["message_bytes"])

    def test_gpu_inventory_excludes_display_connectors(self):
        original_glob = Path.glob
        with tempfile.TemporaryDirectory() as directory:
            devices = []
            for name in ("card0", "card0-DP-1", "card12", "card12-eDP-1"):
                entry = Path(directory) / name
                (entry / "device").mkdir(parents=True)
                (entry / "device/vendor").write_text("0x8086\n")
                devices.append(entry)

            def glob(path, pattern):
                return iter(devices) if path == Path("/sys/class/drm") else original_glob(path, pattern)

            with patch.object(Path, "glob", glob):
                inventory = mod.host_identity()["gpu_devices"]
            self.assertEqual([entry["name"] for entry in inventory], ["card0", "card12"])

    def test_every_frozen_measured_ceiling_has_a_rejection_witness(self):
        for limit, bound in self.contract["limits"].items():
            report = copy.deepcopy(self.report)
            row, sample = report["workers"][0], report["workers"][0]["samples"][0]
            if limit == "worker_timeout_seconds":
                row["parent_end_ns"] = row["parent_start_ns"] + int((bound + 1) * 1e9)
            elif limit == "parent_process_wall_ns_max":
                row["parent_end_ns"] = row["parent_start_ns"] + bound + 1
            elif limit == "worker_stdout_bytes_max":
                row["stdout_bytes"] = bound + 1
            elif limit == "worker_peak_rss_bytes_max":
                row["peak_rss_bytes"] = bound + 1
            elif limit in ("wall_ns_per_call_max", "cpu_ns_per_call_max"):
                clock = limit.split("_")[0]
                sample[clock + "_end_ns"] = sample[clock + "_start_ns"] + (bound + 1) * sample["calls"]
            elif limit == "verification_wall_ns_max":
                v = report["verification"][0]
                v["wall_end_ns"] = v["wall_start_ns"] + bound + 1
            else:
                key = {"profile_episode_wall_ns_max": "profile_episode_wall_ns",
                       "controller_profile_ns_max": "controller_ns",
                       "serialization_ns_max": "serialization_ns",
                       "payload_bytes_per_episode_max": "payload_bytes",
                       "training_steps_max": "training_steps"}[limit]
                row["profile"][key] = bound + 1
            with self.subTest(limit=limit):
                failures = mod.measured_failures(report, self.contract)
                self.assertTrue(any(item.endswith(":" + limit) for item in failures))

    def test_ceiling_failure_cannot_be_serialized_as_pass(self):
        report = copy.deepcopy(self.report)
        report["workers"][0]["peak_rss_bytes"] = self.contract["limits"]["worker_peak_rss_bytes_max"] + 1
        report["summary"] = mod._summary(report["workers"])
        self.resign_worker_bytes(report)
        with self.assertRaisesRegex(ValueError, "admission mismatch"):
            mod.validate_report(report)
        report["limit_failures"] = mod.measured_failures(report, self.contract)
        report["admission"] = "FAIL"
        mod.validate_report(report, require_admissible=False)
        with self.assertRaisesRegex(ValueError, "ceiling exceeded"):
            mod.validate_report(report)

    def test_missing_duplicate_samples_and_wrong_sources_fail(self):
        for mutation in ("worker", "seed", "source", "runtime", "interval", "nonfinite"):
            report = copy.deepcopy(self.report)
            if mutation == "worker":
                report["workers"].pop()
            elif mutation == "seed":
                report["workers"][0]["samples"][1] = report["workers"][0]["samples"][0]
            elif mutation == "source":
                report["workers"][0]["source_sha256"]["run.py"] = "0" * 64
            elif mutation == "runtime":
                report["runtime"]["python"] = "unqualified runtime"
            elif mutation == "interval":
                report["workers"][0]["samples"][0]["wall_end_ns"] = 0
            else:
                report["workers"][0]["peak_rss_bytes"] = float("nan")
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                mod.validate_report(report)

    def test_requested_physical_authority_is_never_inferred(self):
        for key in ("resource_parity_verified", "scientific_promotion_authorized"):
            report = copy.deepcopy(self.report)
            report[key] = True
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "overclaim"):
                mod.validate_report(report)
        report = copy.deepcopy(self.report)
        report["instruments"]["electrical_joules"] = "QUALIFIED"
        with self.assertRaisesRegex(ValueError, "overclaim"):
            mod.validate_report(report)

    def test_resigned_nested_claims_and_escaped_intervals_are_rejected(self):
        for attack in ("summary", "source", "ram", "host", "interval", "extra", "limitations", "stdout"):
            report = copy.deepcopy(self.report)
            timing = report["inherited_timing"]
            if attack == "summary":
                timing["summary"]["COUPLED"]["median_wall_ns_per_call"] = 0
            elif attack == "source":
                timing["source_sha256"] = {"run.py": "0" * 64}
            elif attack == "ram":
                timing["physical_vector"]["attributable_peak_ram_bytes"] = 7
            elif attack == "host":
                report["host"] = {}
            elif attack == "interval":
                report["workers"][0]["samples"][0].update(wall_start_ns=0, wall_end_ns=10)
                report["summary"] = mod._summary(report["workers"])
            elif attack == "extra":
                timing["hardware"]["physical_energy_qualified"] = True
            elif attack == "stdout":
                report["workers"][0]["stdout_bytes"] = 1
            else:
                timing["limitations"] = []
            if attack != "stdout":
                self.resign_worker_bytes(report)
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                mod.validate_report(report)

    def test_sequential_measurement_intervals_cannot_overlap(self):
        for attack in ("worker_samples", "parent_blocks", "inherited", "verification"):
            report = copy.deepcopy(self.report)
            if attack == "worker_samples":
                rows = report["workers"][0]["samples"]
            elif attack == "inherited":
                rows = report["inherited_timing"]["raw"]
            elif attack == "verification":
                rows = report["verification"]
            else:
                rows = report["workers"]
                rows[1]["parent_start_ns"] = rows[0]["parent_end_ns"] - 1
            if attack != "parent_blocks":
                for clock in ("wall", "cpu"):
                    for bound in ("start", "end"):
                        key = clock + "_" + bound + "_ns"
                        rows[1][key] = rows[0][key]
                    if attack == "inherited":
                        rows[1][clock + "_ns_per_call"] = mod._interval(rows[1], clock) / rows[1]["batch_calls"]
            report["summary"] = mod._summary(report["workers"])
            self.resign_worker_bytes(report)
            with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, "overlapping"):
                mod.validate_report(report)

    def test_worker_nonzero_timeout_and_forged_identity_fail(self):
        args = ("COUPLED", self.contract, mod.source_hashes(), mod.runtime_identity())
        with patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 30)):
            with self.assertRaises(subprocess.TimeoutExpired):
                mod.launch_worker(*args)
        with patch.object(mod.subprocess, "run", return_value=subprocess.CompletedProcess([], 7, b"", b"failure")):
            with self.assertRaisesRegex(RuntimeError, "exit 7"):
                mod.launch_worker(*args)
        with patch.object(mod.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"{}", b"")):
            with self.assertRaisesRegex(ValueError, "unbound"):
                mod.launch_worker(*args)

    def test_worker_source_mismatch_fails_before_simulation(self):
        with patch.object(mod.run, "simulate") as simulation:
            with self.assertRaisesRegex(ValueError, "source or runtime mismatch"):
                mod.worker("COUPLED", {}, mod.runtime_identity())
            simulation.assert_not_called()

    def test_transient_worker_trace_corruption_is_not_overwritten(self):
        original = mod.run.simulate
        calls = 0

        def corrupted(*args):
            nonlocal calls
            calls += 1
            result = original(*args)
            if calls == 3:
                result["trace_sha256"] = "0" * 64
            return result

        with patch.object(mod.run, "simulate", side_effect=corrupted):
            with self.assertRaisesRegex(ValueError, "repeated trajectory"):
                mod.worker("COUPLED", mod.source_hashes(), mod.runtime_identity())

    def test_resigned_trace_lie_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "bundle"
            mod.write_bundle(out, self.report)
            report = json.loads((out / "report.json").read_text())
            report["workers"][0]["samples"][0]["result"]["success"] ^= 1
            (out / "report.json").write_bytes(mod.run.canonical(report))
            (out / "SHA256SUMS").write_text("".join(f"{mod.sha((out / name).read_bytes())}  {name}\n"
                                                     for name in ("contract.json", "report.json")))
            with self.assertRaisesRegex(ValueError, "replay mismatch"):
                mod.verify_bundle(out)

    def test_output_reservation_rejects_concurrent_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "bundle"
            with ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(mod.write_bundle, out, self.report) for _ in range(2)]
                errors = [future.exception() for future in futures]
            self.assertEqual(sum(error is None for error in errors), 1)
            self.assertEqual(sum(isinstance(error, FileExistsError) for error in errors), 1)
            self.assertEqual(mod.verify_bundle(out)["admission"], "PASS")

    def test_profile_restores_controller_on_failed_episode(self):
        original = mod.run.Controller.act
        with patch.object(mod.run, "simulate", side_effect=ValueError("injected")):
            with self.assertRaisesRegex(ValueError, "injected"):
                mod._profile("COUPLED", 3001, {})
        self.assertIs(mod.run.Controller.act, original)


if __name__ == "__main__":
    unittest.main()
