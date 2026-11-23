"""CNEH-EXP-01 synthetic preflight regression tests; NOT blind replication."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

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

    def test_budget_and_scrambled_traffic(self):
        rows,m=mod.evaluate([3001,3002],self.protocol)
        self.assertTrue(m["all_budget_envelopes_pass"])
        self.assertTrue(m["scrambled_traffic_envelope_parity"])
        self.assertEqual(len(rows),20)

    def test_no_colliding_arms_or_world_seeds(self):
        with self.assertRaises(ValueError):
            mod.evaluate([3001,3001],self.protocol)
        with self.assertRaises(ValueError):
            mod.simulate(3001,"NOT_A_POLICY",self.protocol)

    def test_hash_integrity_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            out=Path(root)/"bundle"
            mod.write_bundle(out,"SMOKE",[3001,3002],self.protocol)
            mod.verify_bundle(out)
            with (out/"verdict.json").open("a") as f:
                f.write(" ")
            with self.assertRaises(ValueError):
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
