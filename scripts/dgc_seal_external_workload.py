from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from cwc.governance.workload_seal import seal_materialized_workload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-id", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--task-ids", required=True, help="JSON file containing a list of task IDs")
    parser.add_argument("--expected-count", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    task_ids = json.loads(Path(args.task_ids).read_text(encoding="utf-8"))
    if not isinstance(task_ids, list):
        raise ValueError("task-ids JSON must contain a list")
    seal = seal_materialized_workload(
        family_id=args.family_id,
        root=Path(args.root),
        task_ids=task_ids,
        expected_task_count=args.expected_count,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(seal), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(asdict(seal), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
