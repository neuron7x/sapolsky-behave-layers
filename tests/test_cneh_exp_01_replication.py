"""Commitment consistency is not independent execution or authenticated chronology."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from experiments.cneh_exp_01 import replication as rep


class CNEHReplicationTests(unittest.TestCase):
    def setUp(self):
        self.seeds = list(range(61001, 61129))
        self.commitment, self.reveal = rep.create_commitment(
            self.seeds, code_sha="a" * 40, operator_id="external-operator",
            nonce=bytes(range(32)),
        )

    def test_roundtrip_has_no_independence_authority(self):
        result = rep.verify_reveal(self.commitment, self.reveal)
        self.assertEqual(result["consistency"], "PASS")
        self.assertFalse(result["independent_blind_replication"])
        self.assertEqual(result["authority"], "EXTERNAL_ATTESTATION_REQUIRED")
        self.assertEqual(result["chronology"], "NOT_AUTHENTICATED")

    def test_public_commitment_never_contains_seeds_or_nonce(self):
        public = rep.canonical(self.commitment).decode()
        self.assertNotIn("nonce", public)
        self.assertNotIn("61001", public)
        self.assertNotIn("seeds", self.commitment)

    def test_nonce_hides_identical_seed_cohort(self):
        other, _ = rep.create_commitment(self.seeds, code_sha="a" * 40,
                                         operator_id="external-operator", nonce=b"x" * 32)
        self.assertNotEqual(other["commitment_sha256"], self.commitment["commitment_sha256"])

    def test_seed_nonce_identity_code_and_protocol_tamper_rejected(self):
        edits = {"nonce": "ff" * 32, "operator_id": "another-operator",
                 "code_sha": "b" * 40, "protocol_sha256": "c" * 64,
                 "experiment": "OTHER", "cohort": "PRIMARY", "n_world_seeds": 127}
        for key, value in edits.items():
            with self.subTest(key=key):
                forged = copy.deepcopy(self.reveal)
                forged[key] = value
                with self.assertRaises(ValueError):
                    rep.verify_reveal(self.commitment, forged)
        forged = copy.deepcopy(self.reveal)
        forged["seeds"][0] = 71001
        with self.assertRaises(ValueError):
            rep.verify_reveal(self.commitment, forged)

    def test_known_and_duplicate_seeds_rejected(self):
        for replacement in (3001, 3004, 51001, 51128, 73001, 73002, self.seeds[1], True, -1, 2**64):
            with self.subTest(seed=replacement):
                seeds = self.seeds.copy()
                seeds[0] = replacement
                with self.assertRaises(ValueError):
                    rep.create_commitment(seeds, code_sha="a" * 40, operator_id="operator")

    def test_missing_wrong_count_short_nonce_invalid_binding_rejected(self):
        for seeds in ([], self.seeds[:-1]):
            with self.assertRaises(ValueError):
                rep.create_commitment(seeds, code_sha="a" * 40, operator_id="operator")
        for nonce in (b"x" * 31, b"", "x" * 32):
            with self.assertRaises(ValueError):
                rep.create_commitment(self.seeds, code_sha="a" * 40, operator_id="operator", nonce=nonce)
        for code, operator in (("main", "operator"), ("A" * 40, "operator"), ("a" * 40, "")):
            with self.assertRaises(ValueError):
                rep.create_commitment(self.seeds, code_sha=code, operator_id=operator)

    def test_self_attested_independence_is_rejected(self):
        for document in ("public", "private"):
            with self.subTest(document=document):
                public, private = copy.deepcopy((self.commitment, self.reveal))
                (public if document == "public" else private)["independent_blind_replication"] = True
                with self.assertRaisesRegex(ValueError, "fields"):
                    rep.verify_reveal(public, private)

    def test_duplicate_keys_nonfinite_and_extra_fields_fail_closed(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}', '{"a":1e999}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                rep.loads_strict(text)
        forged = copy.deepcopy(self.commitment)
        del forged["code_sha"]
        with self.assertRaises(ValueError):
            rep.verify_reveal(forged, self.reveal)

    def test_output_seal_binds_commitment_and_raw_bytes_without_time_authority(self):
        with tempfile.TemporaryDirectory() as root:
            raw = Path(root) / "result.csv"
            raw.write_bytes(b"seed,outcome\n61001,0\n")
            seal = rep.seal_outputs(self.commitment, raw)
            result = rep.verify_reveal(self.commitment, self.reveal, output_seal=seal,
                                       outputs=raw)
            self.assertEqual(result["output_seal"], "PASS")
            self.assertEqual(result["chronology"], "NOT_AUTHENTICATED")
            raw.write_bytes(b"seed,outcome\n61001,1\n")
            with self.assertRaisesRegex(ValueError, "output"):
                rep.verify_reveal(self.commitment, self.reveal, output_seal=seal, outputs=raw)

    def test_output_seal_missing_pair_or_swapped_commitment_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            raw = Path(root) / "result.csv"
            raw.write_bytes(b"raw")
            seal = rep.seal_outputs(self.commitment, raw)
            with self.assertRaises(ValueError):
                rep.verify_reveal(self.commitment, self.reveal, output_seal=seal)
            seal["commitment_sha256"] = "b" * 64
            with self.assertRaises(ValueError):
                rep.verify_reveal(self.commitment, self.reveal, output_seal=seal, outputs=raw)

    def test_cli_keeps_private_reveal_private_and_requires_external_authority(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            seeds = base / "seeds.json"
            seeds.write_text(json.dumps(self.seeds))
            bundle = base / "prepared"
            command = [sys.executable, str(Path(rep.__file__)), "prepare", "--seeds", str(seeds),
                       "--code-sha", "a" * 40, "--operator-id", "operator", "--out", str(bundle)]
            created = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertEqual((bundle / "commitment.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((bundle / "private" / "reveal.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((bundle / "private").stat().st_mode & 0o777, 0o700)
            verified = subprocess.run([sys.executable, str(Path(rep.__file__)), "verify",
                                      "--commitment", str(bundle / "commitment.json"),
                                      "--reveal", str(bundle / "private" / "reveal.json"),
                                      "--require-independent"], capture_output=True, text=True)
            self.assertEqual(verified.returncode, 2, verified.stderr)
            self.assertFalse(json.loads(verified.stdout)["independent_blind_replication"])
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)


if __name__ == "__main__":
    unittest.main()
