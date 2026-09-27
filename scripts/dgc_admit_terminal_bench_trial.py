from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.terminal_bench_admission import admit_terminal_bench_trial

ROOT = Path(__file__).resolve().parents[1]


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Admit one upstream Harbor Terminal-Bench trial into DGC evidence semantics."
    )
    parser.add_argument("--trial-root", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    admitted = admit_terminal_bench_trial(
        trial_root=_path(args.trial_root),
        expected_task_id=args.task_id,
    )
    payload = admitted.document
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"

    if args.output:
        output = _path(args.output)
        if output.exists():
            raise FileExistsError("admission output is immutable")
        output.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    print(json.dumps({
        "status": "PASS",
        "task_id": admitted.task_id,
        "quality": admitted.quality,
        "agent_metered_cost_usd": admitted.agent_metered_cost_usd,
        "evidence_digest": admitted.evidence_digest,
        "physical_cost_authority": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
