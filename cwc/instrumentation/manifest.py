"""Provenance manifest (Act 4.12). Deliberately excludes secrets, API keys,
or a full environment dump — only the explicit, named fields below.
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import socket
from pathlib import Path
from typing import Any


def _run_git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return None


def _hostname_hash() -> str:
    hostname = socket.gethostname()
    return hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:16]


def git_provenance(repo_root: Path) -> dict[str, Any]:
    commit = _run_git(repo_root, "rev-parse", "HEAD")
    branch = _run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    status = _run_git(repo_root, "status", "--short")
    return {
        "git_commit": commit,
        "git_branch": branch,
        "git_dirty": bool(status),
    }


def device_manifest() -> dict[str, Any]:
    try:
        import torch
    except ImportError:
        return {
            "cuda_available": False,
            "device_name": None,
            "cuda_runtime_version": None,
            "driver_version": None,
            "total_vram_bytes": 0,
        }
    cuda_available = bool(torch.cuda.is_available())
    device_name = None
    total_vram_bytes = 0
    driver_version = None
    if cuda_available:
        device_name = torch.cuda.get_device_name(0)
        total_vram_bytes = int(torch.cuda.get_device_properties(0).total_memory)
        try:
            driver_version = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                check=True, capture_output=True, text=True, timeout=5,
            ).stdout.strip().splitlines()[0]
        except Exception:
            driver_version = None
    return {
        "cuda_available": cuda_available,
        "device_name": device_name,
        "cuda_runtime_version": torch.version.cuda if cuda_available else None,
        "driver_version": driver_version,
        "total_vram_bytes": total_vram_bytes,
    }


def environment_manifest(*, expected_torch_version: str = "2.9.1") -> dict[str, Any]:
    try:
        import torch
        torch_version = torch.__version__
    except ImportError:
        torch_version = "unavailable"
    environment_match = torch_version == expected_torch_version
    return {
        "python_version": platform.python_version(),
        "torch_version": torch_version,
        "expected_torch_version": expected_torch_version,
        "environment_match": environment_match,
        "os_name": platform.system(),
        "hostname_hash": _hostname_hash(),
        "ddp_world_size": int(os.environ.get("WORLD_SIZE", "1")),
        "ddp_rank": int(os.environ.get("RANK", "0")),
    }


def build_manifest(
    *,
    run_id: str,
    created_at_utc: str,
    repo_root: Path,
    command_line: list[str],
    resolved_config: dict[str, Any],
    model_config: dict[str, Any] | None = None,
    checkpoint_identity: str | None = None,
    tokenizer_identity: str | None = None,
    seed: int | None = None,
    dataset_identity: str | None = None,
    compile_state: str = "unknown",
    attention_backend: str = "unknown",
    expected_torch_version: str = "2.9.1",
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at_utc": created_at_utc,
        "command_line": command_line,
        "git": git_provenance(repo_root),
        "device": device_manifest(),
        "environment": environment_manifest(expected_torch_version=expected_torch_version),
        "instrumentation_config": resolved_config,
        "model_config": model_config or {},
        "checkpoint_identity": checkpoint_identity,
        "tokenizer_identity": tokenizer_identity,
        "seed": seed,
        "dataset_identity": dataset_identity,
        "compile_state": compile_state,
        "attention_backend": attention_backend,
    }
