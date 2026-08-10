from __future__ import annotations

import json
import os
import resource
from dataclasses import asdict
import subprocess
import time
from pathlib import Path
from typing import Sequence

from .models import RunTelemetry
from .provenance import sha256_file


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def run_with_telemetry(
    *,
    root: Path,
    run_id: str,
    command: Sequence[str],
    dataset_hash: str,
    seed: int | str,
    artifact_paths: Sequence[Path] = (),
    env: dict[str, str] | None = None,
) -> tuple[RunTelemetry, subprocess.CompletedProcess[str]]:
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    started = time.perf_counter()
    proc = subprocess.run(
        list(command),
        cwd=root,
        env={**os.environ, **(env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    wall = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # ru_maxrss is KiB on Linux. Child maximum is coarse but measured, not estimated.
    peak_ram = max(before, after) * 1024
    hashes = {str(path.relative_to(root)): sha256_file(path) for path in artifact_paths if path.is_file()}
    telemetry = RunTelemetry(
        run_id=run_id,
        git_commit=git_head(root),
        dataset_hash=dataset_hash,
        seed=seed,
        device="CPU",
        wall_seconds=wall,
        gpu_seconds=None,
        peak_vram_bytes=None,
        peak_ram_bytes=peak_ram,
        exit_code=proc.returncode,
        metric_output={},
        artifact_hashes=hashes,
    )
    return telemetry, proc


def append_telemetry(path: Path, telemetry: RunTelemetry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(telemetry), sort_keys=True) + "\n")
