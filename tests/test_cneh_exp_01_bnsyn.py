"""Hermetic adapter boundary tests; real pinned neural run is a separate command."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "experiments" / "cneh_exp_01"
SPEC = importlib.util.spec_from_file_location("cneh_bnsyn_adapter", ROOT / "bnsyn_adapter.py")
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class NeuralAdapterBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / "bnsyn_integration_contract.json").read_text())

    def test_observation_boundary_rejects_nonfinite_boolean_and_wrong_dimension(self):
        for obs in ((math.nan, -55.0), (math.inf, -55.0), (-55.0,),
                    (True, -55.0), (-55.0, -55.0, -55.0)):
            with self.subTest(obs=obs), self.assertRaises(ValueError):
                mod.bounded_action(obs, self.contract)

    def test_actions_bounded_and_partition_permutation_equivariant(self):
        for a in (-1e100, -100.0, -55.0, 0.0, 1e100):
            for b in (-100.0, -55.0, 1e100):
                action = mod.bounded_action((a, b), self.contract)
                self.assertTrue(all(0 <= x <= 500.0 for x in action))
                self.assertEqual(action, mod.bounded_action((b, a), self.contract)[::-1])

    def test_exact_trace_encoding_detects_sub_rounding_change(self):
        class Array:
            def __init__(self, value):
                self.value = value

            def ravel(self):
                return [self.value]

        a, b = 1.0, math.nextafter(1.0, 2.0)
        self.assertEqual(round(a, 12), round(b, 12))
        self.assertNotEqual(mod._hex_array(Array(a)), mod._hex_array(Array(b)))
        with self.assertRaises(ValueError):
            mod._hex_array(Array(math.nan))

    def test_source_tamper_and_extra_importable_file_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "module.py").write_text("x=1\n")
            (root / "LICENSE").write_text("license\n")
            (root / "pyproject.toml").write_text("[project]\n")
            manifest = mod.source_manifest(root)
            contract = {"source": {"file_count": len(manifest),
                                   "files_sha256": mod.sha(mod.canonical(manifest))}}
            self.assertEqual(mod.validate_source(root, contract), manifest)
            (root / "src" / "module.py").write_text("x=2\n")
            with self.assertRaisesRegex(ValueError, "digest"):
                mod.validate_source(root, contract)
            (root / "src" / "module.py").write_text("x=1\n")
            (root / "src" / "shadow.py").write_text("x=3\n")
            with self.assertRaisesRegex(ValueError, "digest"):
                mod.validate_source(root, contract)

    def test_source_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "LICENSE").write_text("license\n")
            (root / "pyproject.toml").write_text("[project]\n")
            (root / "src" / "external.py").symlink_to(root / "LICENSE")
            with self.assertRaisesRegex(ValueError, "symlink"):
                mod.source_manifest(root)

    def test_missing_and_substitute_source_fail_without_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                mod.validate_source(root / "absent", self.contract)
            (root / "src").mkdir()
            (root / "LICENSE").write_text("substitute")
            (root / "pyproject.toml").write_text("[project]\n")
            with self.assertRaisesRegex(ValueError, "digest"):
                mod.validate_source(root, self.contract)

    def _episodes(self):
        rows = []
        for seed in self.contract["smoke"]["seeds"]:
            for arm in self.contract["smoke"]["arms"]:
                payload = {"response": 0 if arm == "ZERO_ACTION" else 1}
                rows.append({"seed": seed, "arm": arm, "payload": payload,
                             "trace_sha256": mod.sha(mod.canonical(payload)),
                             "response_sha256": mod.sha(mod.canonical(payload)),
                             "total_spikes": 2, "voltage_range_mV": 1.0})
        return rows

    def test_negative_controls_reject_parity_failure_inactivity_and_missing_arm(self):
        cases = []
        rows = self._episodes()
        rows[1]["payload"] = {"response": 2}
        rows[1]["trace_sha256"] = mod.sha(mod.canonical(rows[1]["payload"]))
        cases.append(rows)
        rows = self._episodes()
        rows[0]["total_spikes"] = 0
        cases.append(rows)
        cases.append(self._episodes()[:-1])
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                mod.check_episodes(rows, self.contract)

    def test_action_labels_cannot_fake_neural_responsiveness(self):
        rows = self._episodes()
        rows[2]["response_sha256"] = rows[0]["response_sha256"]
        self.assertNotEqual(rows[2]["trace_sha256"], rows[0]["trace_sha256"])
        with self.assertRaisesRegex(ValueError, "responsiveness"):
            mod.check_episodes(rows, self.contract)

    def test_neural_evidence_immutable_and_manifest_tamper_rejected_before_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "bundle"
            mod.write_bundle(out, {"authority": "fixture"}, [])
            with self.assertRaises(FileExistsError):
                mod.write_bundle(out, {}, [])
            (out / "report.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "manifest"):
                mod.verify_bundle(out, Path(temporary) / "nonexistent")

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'):
            with self.assertRaises(ValueError):
                mod.strict_json(raw)

    def test_authority_and_seed_isolation(self):
        self.assertIs(self.contract["scientific_promotion_authorized"], False)
        self.assertEqual(self.contract["authority"], "INTEGRATION_SMOKE_ONLY")
        seeds = set(self.contract["smoke"]["seeds"])
        self.assertEqual(len(seeds), len(self.contract["smoke"]["seeds"]))
        self.assertFalse(seeds & set(range(51001, 51129)))
        self.assertFalse(seeds & {3001, 3002, 3003, 3004})


if __name__ == "__main__":
    unittest.main()
