from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_research_ops_gate_runs_from_clean_external_cwd(tmp_path: Path) -> None:
    """ACT-R&D-03 P0: a clean copied tree must not depend on PYTHONPATH or cwd."""
    copied = tmp_path / "repo"
    shutil.copytree(
        ROOT,
        copied,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache",
            ".ruff_cache", ".coverage", "assurance-build", "release-build",
        ),
    )
    external = tmp_path / "external-cwd"
    external.mkdir()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, str(copied / "scripts/research_ops_gate.py")],
        cwd=external,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "RESEARCH-OPS-GATE: PASS" in proc.stdout
