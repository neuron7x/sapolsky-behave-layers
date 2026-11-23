"""Engineering acceptance never promotes the impossible frozen scientific contrast."""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.cneh_exp_01 import qualification as gate
from experiments.cneh_exp_01 import run


class CNEHQualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bundle = Path(self.temp.name) / "bundle"
        protocol = json.loads((run.HERE / "protocol.json").read_text())
        run.write_bundle(self.bundle, "SMOKE", [3001, 3002], protocol)

    def test_verified_engineering_bundle_does_not_unlock_science(self):
        report = gate.assess(self.bundle)
        self.assertEqual(report["engineering_validation"], "PASS")
        self.assertEqual(report["scientific_readiness"], "BLOCKED")
        self.assertFalse(report["scientific_promotion_authorized"])
        self.assertEqual(report["gates"]["current_lineage"],
                         "STRUCTURALLY_UNTESTABLE_UNDER_SIMULATION_DOMINANCE")
        self.assertEqual(report["gates"]["cost"], "COST_INSTRUMENT_INVALID")
        self.assertEqual(report["gates"]["replication"], "REPLICATION_NOT_TESTED")
        self.assertEqual(report["gates"]["substrate"], "SUBSTRATE_TOO_SIMPLE")
        self.assertEqual(report["gates"]["estimators"], "ESTIMATORS_UNQUALIFIED")
        self.assertLess(report["central_emulator_lcb_at_frozen_primary_n"], 0)
        self.assertFalse(report["same_lineage_supported_narrow_reachable"])
        self.assertEqual(report["integration_smoke"], "NOT_RUN_BY_THIS_GATE")

    def test_source_and_bundle_digest_are_bound(self):
        report = gate.assess(self.bundle)
        self.assertEqual(report["bundle_manifest_sha256"], run.digest((self.bundle / "SHA256SUMS").read_bytes()))
        self.assertEqual(report["source_sha256"]["protocol.json"], run.digest((run.HERE / "protocol.json").read_bytes()))
        self.assertEqual(report["source_sha256"]["qualification.py"], run.digest(Path(gate.__file__).read_bytes()))

    def test_tampered_science_status_cannot_be_engineering_pass(self):
        verdict = self.bundle / "verdict.json"
        data = json.loads(verdict.read_text())
        data["scientific_promotion_authorized"] = True
        verdict.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            gate.assess(self.bundle)

    def test_authentic_negative_evidence_cannot_pass_engineering_gate(self):
        original = run.Controller.act

        def faulty(controller, t, sensed, goal, arm, plant, **kwargs):
            action = original(controller, t, sensed, goal, arm, plant, **kwargs)
            return ((math.nextafter(action[0], 0.0), action[1])
                    if arm == "CENTRAL_EMULATOR" else action)

        negative = Path(self.temp.name) / "negative"
        protocol = json.loads((run.HERE / "protocol.json").read_text())
        with patch.object(run.Controller, "act", faulty):
            run.write_bundle(negative, "SMOKE", [3001, 3002], protocol)
            self.assertEqual(run.verify_bundle(negative)["verdict"], "INVALID")
            with self.assertRaisesRegex(ValueError, "authentic negative"):
                gate.assess(negative)

    def test_missing_bundle_rejected(self):
        with self.assertRaises(ValueError):
            gate.assess(Path(self.temp.name) / "absent")

    def test_cli_readiness_has_distinct_nonzero_exit(self):
        command = [sys.executable, str(Path(gate.__file__)), "--bundle", str(self.bundle)]
        checked = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        blocked = subprocess.run(command + ["--require-scientific-readiness"], capture_output=True, text=True)
        self.assertEqual(blocked.returncode, 2, blocked.stderr)
        self.assertEqual(json.loads(blocked.stdout)["scientific_readiness"], "BLOCKED")
        (self.bundle / "verdict.json").unlink()
        invalid = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 1, invalid.stderr)


if __name__ == "__main__":
    unittest.main()
