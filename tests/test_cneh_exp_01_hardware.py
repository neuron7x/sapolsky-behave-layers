"""Timing design checks do not qualify physical energy/FLOP instruments."""
import unittest
from unittest.mock import patch

from experiments.cneh_exp_01 import hardware


class HardwareTimingTests(unittest.TestCase):
    def test_complete_balanced_blocks_and_raw_interval_arithmetic(self):
        report = hardware.measure()
        plan = report["plan"]
        self.assertEqual(len(report["raw"]), plan["repeats"] * len(plan["seeds"]) * len(hardware.run.ARMS))
        for repeat in range(plan["repeats"]):
            for seed in plan["seeds"]:
                rows = [r for r in report["raw"] if r["repeat"] == repeat and r["seed"] == seed]
                self.assertEqual({r["arm"] for r in rows}, set(hardware.run.ARMS))
                self.assertEqual([r["position"] for r in rows], list(range(len(hardware.run.ARMS))))
                for row in rows:
                    self.assertEqual(row["wall_ns_per_call"], (row["wall_end_ns"] - row["wall_start_ns"]) / plan["batch_calls"])
                    self.assertGreater(row["cpu_ns_per_call"], 0)
        self.assertEqual(report["cost_status"], "COST_INSTRUMENT_INVALID")
        self.assertFalse(report["scientific_promotion_authorized"])
        self.assertIsNone(report["physical_vector"]["flops"])
        self.assertIsNone(report["physical_vector"]["joules"])

    def test_broken_timer_fails(self):
        with patch.object(hardware.time, "perf_counter_ns", return_value=1):
            with self.assertRaisesRegex(RuntimeError, "nonpositive"):
                hardware.measure()

    def test_emulator_fault_fails_even_when_timers_work(self):
        original = hardware.run.simulate

        def corrupted(seed, arm, protocol):
            result = original(seed, arm, protocol)
            if arm == "CENTRAL_EMULATOR":
                result["trace_sha256"] = "0" * 64
            return result

        with patch.object(hardware.run, "simulate", side_effect=corrupted):
            with self.assertRaisesRegex(RuntimeError, "parity"):
                hardware.measure()

    def test_transient_corruption_in_early_batch_is_not_overwritten(self):
        original = hardware.run.simulate
        for corrupt_call in (3, 10):  # after two warmups: first and last call of first batch
            calls = 0

            def corrupted(seed, arm, protocol):
                nonlocal calls
                result = original(seed, arm, protocol)
                if arm == "CENTRAL_EMULATOR":
                    calls += 1
                    if calls == corrupt_call:
                        result["trace_sha256"] = "0" * 64
                return result

            with self.subTest(call=corrupt_call):
                with patch.object(hardware.run, "simulate", side_effect=corrupted):
                    with self.assertRaisesRegex(RuntimeError, "parity"):
                        hardware.measure()


if __name__ == "__main__":
    unittest.main()
