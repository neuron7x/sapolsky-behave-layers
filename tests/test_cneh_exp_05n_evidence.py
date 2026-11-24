"""Pure falsifiers for finite native checkpoint evidence boundaries."""
from __future__ import annotations

import copy
import unittest

from experiments.cneh_exp_05n import run as n


class TestNativeEvidence(unittest.TestCase):
    def test_checkpoint_anchor_is_external(self):
        data = {"tick": 128, "rng": {"state": 17}, "mode": 0}
        cp = n.seal(data)
        self.assertEqual(n.authenticated(cp, cp["sha256"], 128), data)
        altered = copy.deepcopy(cp)
        altered["data"]["rng"]["state"] = 18
        with self.assertRaisesRegex(ValueError, "anchor"):
            n.authenticated(altered, cp["sha256"], 128)
        forged = n.seal(altered["data"])
        with self.assertRaisesRegex(ValueError, "anchor"):
            n.authenticated(forged, cp["sha256"], 128)
        with self.assertRaisesRegex(ValueError, "stale"):
            n.authenticated(cp, cp["sha256"], 129)

    def test_exact_float_encoding(self):
        for x in (0., -0., 1., -1e-300, 1e300, 0.1):
            self.assertEqual(n.parse_float(n.hex_float(x)).hex(), x.hex())
        for bad in ("nan", "inf", "0x1p+0", 1.):
            with self.assertRaises(ValueError):
                n.parse_float(bad)

    def test_fixed_action_roster(self):
        self.assertEqual(n.CHECKPOINTS, (0, 128, 256, 384, 480))
        for t in range(n.STEPS):
            self.assertIsNone(n.action("WAIT", t))
            self.assertEqual(n.action("G0", t), 0)
            self.assertEqual(n.action("G1", t), 1)
            self.assertEqual(n.action("ALTERNATE", t), (t // 64) % 2)
        for t in (-1, n.STEPS, True):
            with self.assertRaises(ValueError):
                n.action("WAIT", t)

    def test_first_difference_is_not_rounded(self):
        row = {"tick": 7, "parts": {"w": "a"}, "state_sha256": "a"}
        a = [{"seed": 92001, "arm": "WAIT", "trace": [row]}]
        b = copy.deepcopy(a)
        self.assertIsNone(n.difference(a, b))
        b[0]["trace"][0]["parts"]["w"] = "b"
        b[0]["trace"][0]["state_sha256"] = "b"
        self.assertEqual(n.difference(a, b),
                         {"seed": 92001, "arm": "WAIT", "tick": 7,
                          "fields": ["parts", "state_sha256"], "parts": ["w"]})

    def test_missing_profile_blocks_aggregate(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "artifact roster"):
                n.aggregate(Path(tmp))


if __name__ == "__main__":
    unittest.main()
