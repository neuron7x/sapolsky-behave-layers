from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cwc.governance.terminal_harbor_adapter import execute_terminal_harbor_unit


def _env_path(name: str) -> Path:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return Path(value)


def main() -> int:
    request = json.load(sys.stdin)
    if not isinstance(request, dict):
        raise ValueError("DGC unit request must be a JSON object")
    response = execute_terminal_harbor_unit(
        request=request,
        repository_root=_env_path("DGC_REPOSITORY_ROOT"),
        materialization_root=_env_path("DGC_MATERIALIZATION_ROOT"),
        runtime_root=_env_path("DGC_BENCHMARK_RUNTIME_ROOT"),
        unit_runtime_root=_env_path("DGC_UNIT_RUNTIME_ROOT"),
    )
    sys.stdout.write(json.dumps(response, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
