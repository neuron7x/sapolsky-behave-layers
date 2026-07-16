"""A0 — provenance closure. Captures a machine-readable run manifest so every
result is reconstructable from one commit + one environment record.
Date.now()-free: timestamps come from the OS via subprocess at call time
(scripts, not workflow — allowed here).
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
from pathlib import Path


def _sh(cmd: str) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()
    except Exception as exc:  # pragma: no cover
        return f"ERR:{exc}"


def _sha256(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        return "MISSING"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_manifest(extra: dict | None = None) -> dict:
    import torch

    man = {
        "git_commit": _sh("git rev-parse HEAD"),
        "git_tree_status": _sh("git status --porcelain"),
        "repository_remote": _sh("git remote -v | head -1"),
        "dependency_lock_checksum": _sha256("uv.lock"),
        "hardware_model": _sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"),
        "driver_version": _sh("nvidia-smi --query-gpu=driver_version --format=csv,noheader"),
        "cuda_version": torch.version.cuda,
        "pytorch_version": torch.__version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "precision": "fp32",
        "compile_state": "eager",
        "start_timestamp_utc": _sh("date -u +%Y-%m-%dT%H:%M:%SZ"),
    }
    if extra:
        man.update(extra)
    return man
