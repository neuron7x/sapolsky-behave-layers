"""Falsify the transport boundary independently of GitHub network access."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import cneh_artifact_transport as t


class TestTransport(unittest.TestCase):
    def run_case(self,spec="y",upstream="true",failure=False,missing=False,extra=False):
        with TemporaryDirectory() as d:
            root=Path(d)/"profiles"
            groups=dict(t.expected(spec))
            def download(cmd):
                pattern=cmd[cmd.index("--pattern")+1]
                for name in sorted(groups[pattern]):
                    if not (missing and name.endswith("pair-0")):
                        (root/name).mkdir()
                if extra and pattern.endswith("pair-*"):
                    (root/"unexpected").mkdir()
                return 1 if failure and pattern.endswith("pair-*") else 0
            return t.fetch(spec,"123","neuron7x/sapolsky-behave-layers","a"*40,root,upstream,download)

    def test_complete_rosters(self):
        for spec in ("x","y"):
            self.assertEqual(self.run_case(spec=spec)["status"],"PASS")

    def test_nonzero_even_if_all_files_exist(self):
        r=self.run_case(failure=True)
        self.assertEqual(r["missing"],[])
        self.assertEqual(r["status"],"BLOCKED")

    def test_upstream_failure_even_if_all_files_exist(self):
        self.assertEqual(self.run_case(upstream="false")["status"],"BLOCKED")

    def test_missing_and_unexpected_rosters(self):
        for mode in ("missing","extra"):
            self.assertEqual(self.run_case(**{mode:True})["status"],"BLOCKED")

    def test_invalid_run_identity(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                t.fetch("y","bad","neuron7x/sapolsky-behave-layers","a"*40,Path(d)/"p","true",lambda x:0)


if __name__=="__main__":
    unittest.main()
