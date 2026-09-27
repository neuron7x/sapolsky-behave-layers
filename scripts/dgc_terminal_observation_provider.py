from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cwc.governance.terminal_task_observations import (
    OBSERVATION_FIELDS,
    extract_terminal_task_observations,
)

REQUEST_SCHEMA = "DGC_PREOUTCOME_OBSERVATION_REQUEST_V1"
RESPONSE_SCHEMA = "DGC_PREOUTCOME_OBSERVATION_RESPONSE_V1"
FAMILY = "TERMINAL_BENCH_2_1"


def main() -> int:
    raw = json.load(sys.stdin)
    if not isinstance(raw, dict) or raw.get("schema") != REQUEST_SCHEMA:
        raise ValueError("unexpected observation request schema")
    if raw.get("family_id") != FAMILY:
        raise ValueError("Terminal observation provider family mismatch")
    task_id = str(raw.get("task_id", "")).strip()
    if not task_id:
        raise ValueError("task_id required")

    materialization_root = Path(os.environ["DGC_MATERIALIZATION_ROOT"]).resolve()
    task_root = (
        materialization_root
        / FAMILY
        / "repo"
        / "tasks"
        / task_id
    )
    observed = extract_terminal_task_observations(
        task_root=task_root,
        task_id=task_id,
        budget_remaining=raw.get("budget_remaining"),
        step_index=raw.get("step_index"),
    )
    response = {
        "schema": RESPONSE_SCHEMA,
        "family_id": FAMILY,
        "task_id": task_id,
        "observations": observed.observations,
        "output_fields": list(OBSERVATION_FIELDS),
        "source_manifest_digest": observed.source_manifest_digest,
        "confirmatory_label_access": False,
        "post_outcome_access": False,
    }
    sys.stdout.write(json.dumps(response, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
