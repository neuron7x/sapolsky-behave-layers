"""Executable download and fail-closed audit regressions; no network required."""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import cwc_dependency_audit as audit


class DependencyAuditTests(unittest.TestCase):
    def test_lock_drift_and_unhashed_transitive_dependency_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements").mkdir()
            line = f"example==1.0 --hash=sha256:{'a' * 64}\n"
            (root / "requirements/cwc-dev.lock").write_text(line)
            (root / "requirements/pip-audit.lock").write_text(line)
            (root / "cwc-requirements-dev.txt").write_text("example==1.0\n")
            (root / "uv.lock").write_text('[[package]]\nname = "example"\nversion = "1.0"\n')
            audit.validate_controls(root)
            for defect in ("direct", "runtime", "missing-hash"):
                with self.subTest(defect=defect):
                    if defect == "direct":
                        (root / "cwc-requirements-dev.txt").write_text("example==2.0\n")
                    elif defect == "runtime":
                        (root / "uv.lock").write_text('[[package]]\nname = "example"\nversion = "2.0"\n')
                    else:
                        (root / "requirements/cwc-dev.lock").write_text(line + "transitive==1.0\n")
                    with self.assertRaises(ValueError):
                        audit.validate_controls(root)
                    (root / "cwc-requirements-dev.txt").write_text("example==1.0\n")
                    (root / "uv.lock").write_text('[[package]]\nname = "example"\nversion = "1.0"\n')

    def test_hash_locked_installer_rejects_wrong_wheel_and_accepts_exact_wheel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "cwc_hash_fixture-1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("cwc_hash_fixture.py", "VALUE = 43\n")
                archive.writestr("cwc_hash_fixture-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: cwc-hash-fixture\nVersion: 1.0\n")
                archive.writestr("cwc_hash_fixture-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                archive.writestr("cwc_hash_fixture-1.0.dist-info/RECORD", "")
            lock = root / "requirements.lock"
            lock.write_text(f"cwc-hash-fixture @ {wheel.as_uri()} --hash=sha256:{'0' * 64}\n")
            with self.assertRaises(subprocess.CalledProcessError):
                audit.install_tool(root / "rejected", lock)
            result = subprocess.run([str(root / "rejected/bin/python"), "-c", "import cwc_hash_fixture"], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            lock.write_text(f"cwc-hash-fixture @ {wheel.as_uri()} --hash=sha256:{hashlib.sha256(wheel.read_bytes()).hexdigest()}\n")
            python = audit.install_tool(root / "accepted", lock)
            subprocess.run([str(python), "-c", "import cwc_hash_fixture; assert cwc_hash_fixture.VALUE == 43"], check=True)

    def test_nonzero_vulnerability_or_collection_failure_propagates(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "dependencies.txt"
            target.write_text("example==1.0\n")
            for code in (1, 2):
                with self.subTest(code=code), patch.object(audit.subprocess, "run") as run:
                    run.side_effect = [subprocess.CompletedProcess([], 0), subprocess.CalledProcessError(code, "pip-audit")]
                    with self.assertRaises(subprocess.CalledProcessError) as raised:
                        audit.audit_targets(Path("python"), [target])
                    self.assertEqual(raised.exception.returncode, code)

    def test_installer_rejects_an_omitted_transitive_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dependency = root / "cwc_dependency-1.0-py3-none-any.whl"
            parent = root / "cwc_parent-1.0-py3-none-any.whl"
            for name, wheel, requires in (
                ("cwc_dependency", dependency, ""),
                ("cwc_parent", parent, f"Requires-Dist: cwc-dependency @ {dependency.as_uri()}\n"),
            ):
                with zipfile.ZipFile(wheel, "w") as archive:
                    archive.writestr(name + ".py", "VALUE = 43\n")
                    archive.writestr(f"{name}-1.0.dist-info/METADATA", f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n{requires}")
                    archive.writestr(f"{name}-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                    archive.writestr(f"{name}-1.0.dist-info/RECORD", "")
            lock = root / "requirements.lock"
            lock.write_text(f"cwc-parent @ {parent.as_uri()} --hash=sha256:{hashlib.sha256(parent.read_bytes()).hexdigest()}\n")
            with self.assertRaises(subprocess.CalledProcessError):
                audit.install_tool(root / "rejected", lock)
            lock.write_text(lock.read_text() + f"cwc-dependency @ {dependency.as_uri()} --hash=sha256:{hashlib.sha256(dependency.read_bytes()).hexdigest()}\n")
            python = audit.install_tool(root / "accepted", lock)
            subprocess.run([str(python), "-c", "import cwc_parent, cwc_dependency"], check=True)

    def test_public_entrypoint_preserves_failure_exit_code(self):
        for code in (1, 7):
            with (
                self.subTest(code=code),
                patch.object(audit, "validate_controls"),
                patch.object(audit.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)),
                patch.object(audit, "prepare_targets", side_effect=subprocess.CalledProcessError(code, "uv export")),
            ):
                self.assertEqual(audit.main(), code)

    def test_missing_or_empty_target_prevents_any_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "dependencies.txt"
            for contents in (None, "", "# empty export\n"):
                if contents is not None:
                    target.write_text(contents)
                with self.subTest(contents=contents), patch.object(audit.subprocess, "run") as run:
                    with self.assertRaisesRegex(ValueError, "missing or empty"):
                        audit.audit_targets(Path("python"), [target])
                    run.assert_not_called()
            with self.assertRaisesRegex(ValueError, "roster is empty"):
                audit.audit_targets(Path("python"), [])

    def test_failed_export_cannot_fall_through_to_install_or_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements").mkdir()
            for name in ("uv.lock", "pyproject.toml", "requirements/cwc-dev.lock", "requirements/pip-audit.lock"):
                (root / name).write_text("fixture==1.0\n")
            with (
                patch.object(audit.subprocess, "run", side_effect=subprocess.CalledProcessError(7, "uv export")),
                self.assertRaises(subprocess.CalledProcessError),
            ):
                audit.prepare_targets(root, root)


if __name__ == "__main__":
    unittest.main()
