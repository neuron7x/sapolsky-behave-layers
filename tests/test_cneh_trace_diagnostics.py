"""Controls for the real trace admission boundary and its CLI failure receipt."""
from contextlib import redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import cneh_evidence_admission as a


def fixture():
    key = ("", 7)
    contract = {
        "native": True, "steps": 3, "stim_ticks": 0, "source_effort": 0,
        "worlds": {key: {"schedule": []}},
    }
    rows = [{
        "tick": tick, "state_sha256": "a" * 64, "rng_sha256": "b" * 64,
        "true_gaba": ["0x0.0p+0"] * 16, "true_bits": [0] * 8,
        "transition_mode": None if not tick else 0, "next_mode": 0,
        "noise": [0.0], "erasures": [False],
    } for tick in range(4)]
    for row in rows[:-1]:
        row.update(group=None, source_inputs_pA=[0.0, 0.0], direct_B_pA=300.0, applied_gain=1.0)
    return {"trace": rows, "source_current_l1_pA_ticks": 0}, key, contract


class TraceDiagnosticsTests(unittest.TestCase):
    def test_good_trace_retains_signature_and_numeric_representation(self):
        episode, key, contract = fixture()
        expected = hashlib.sha256(a.canonical(
            ["a" * 64, [("b" * 64, [0.0], [False])] * 4])).hexdigest()
        self.assertEqual(a.validate_trace(episode, key, contract), expected)
        episode["trace"][2].update(direct_B_pA=300, applied_gain=1)
        self.assertEqual(a.validate_trace(episode, key, contract), expected)

    def test_boolean_transition_and_gain_rejected(self):
        for tick, field, value in ((1, "transition_mode", False), (2, "applied_gain", True)):
            with self.subTest(field=field):
                episode, key, contract = fixture()
                episode["trace"][tick][field] = value
                with self.assertRaises(a.EvidenceViolation) as error:
                    a.validate_trace(episode, key, contract)
                self.assertEqual((error.exception.code, error.exception.trace_tick), ("TRACE", tick))

    def test_first_invalid_position_and_bad_conductance(self):
        for field, value in (("tick", 99), ("true_gaba", ["invalid"] * 16)):
            with self.subTest(field=field):
                episode, key, contract = fixture()
                episode["trace"][1][field] = value
                episode["trace"][2]["applied_gain"] = False
                with self.assertRaises(a.EvidenceViolation) as error:
                    a.validate_trace(episode, key, contract)
                self.assertEqual((error.exception.code, error.exception.trace_tick), ("TRACE", 1))

    def test_envelope_failure_has_no_tick(self):
        episode, key, contract = fixture()
        episode["trace"].pop()
        with self.assertRaises(a.EvidenceViolation) as error:
            a.validate_trace(episode, key, contract)
        self.assertEqual(error.exception.code, "TRACE")
        self.assertIsNone(error.exception.trace_tick)

    def test_cli_failure_contains_first_tick_and_writes_no_success_receipt(self):
        episode, key, contract = fixture()
        episode["trace"][1]["tick"] = 900
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "receipt.json"
            argv = ["admission", "archive", "--experiment", "CNEH-EXP-05",
                    "--input", str(Path(directory) / "archive.zip"), "--out", str(out)]
            buf = StringIO()
            with (patch("sys.argv", argv), patch.object(a, "trusted_contract", return_value=contract),
                  patch.object(a, "admit_archive", side_effect=lambda *_: a.validate_trace(
                      episode, key, contract)), redirect_stderr(buf)):
                self.assertEqual(a.main(), 2)
            self.assertFalse(out.exists())
            receipt = json.loads(buf.getvalue())
            self.assertEqual(receipt["failure_code"], "TRACE")
            self.assertEqual(receipt["trace_tick"], 1)
            self.assertEqual(receipt["engineering_evidence"], "BLOCKED")
            self.assertIs(receipt[a.FLAG], False)
