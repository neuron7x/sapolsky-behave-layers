#!/usr/bin/env python3
"""Fail closed unless the 100-task ledger and DONE evidence agree."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW = re.compile(r"^\| (TQ-\d{3}) \| (DONE|OPEN) \|")


def verify(root: Path = ROOT) -> list[str]:
    evidence_path = root / "engineering/technical_quality_evidence.json"
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    ledger_path = root / payload["ledger"]
    rows = [
        match.groups()
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if (match := ROW.match(line))
    ]
    errors: list[str] = []
    expected = [f"TQ-{number:03d}" for number in range(1, 101)]
    observed = [task_id for task_id, _ in rows]
    if observed != expected:
        errors.append("ledger IDs must be exactly TQ-001..TQ-100 in order")

    done = {task_id for task_id, state in rows if state == "DONE"}
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return [*errors, "evidence must be an object"]
    evidenced = set(evidence)
    if done != evidenced:
        errors.append(
            f"DONE/evidence mismatch: missing={sorted(done - evidenced)}, "
            f"unexpected={sorted(evidenced - done)}"
        )
    for task_id, paths in evidence.items():
        if not isinstance(paths, list) or not paths:
            errors.append(f"{task_id} must have at least one evidence path")
            continue
        for relative in paths:
            if not isinstance(relative, str) or not (root / relative).is_file():
                errors.append(f"{task_id} evidence is missing: {relative!r}")
    return errors


def main() -> int:
    errors = verify()
    if errors:
        for error in errors:
            print(f"TECHNICAL-QUALITY-GATE: FAIL: {error}")
        return 1
    print("TECHNICAL-QUALITY-GATE: PASS (100 stable tasks; every DONE task evidenced)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
