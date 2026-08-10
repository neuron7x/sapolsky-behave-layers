from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.csca_02_ua.common import serialize_raw
from experiments.csca_02_ua.run import load_policy, run_cohort


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed-start", type=int, required=True)
    parser.add_argument("--seed-count", type=int, default=32)
    parser.add_argument("--label", choices=("PRIMARY", "INDEPENDENT_REPLICATION"), required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    policy, policy_sha = load_policy(args.policy)
    started = time.perf_counter()
    raw, score, passed, reasons = run_cohort(args.seed_start, args.seed_count, policy)
    payload = {
        "label": args.label,
        "seed_start": args.seed_start,
        "seed_count": args.seed_count,
        "policy_sha256": policy_sha,
        "pass": passed,
        "failure_reasons": reasons,
        "score": {k: v for k, v in score.items() if k != "decisions"},
        "decisions": score["decisions"],
        "raw_cases": [serialize_raw(r) for r in raw],
        "wall_seconds": time.perf_counter() - started,
    }
    (args.out / f"{args.label.lower()}_chunk.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k not in {"raw_cases", "decisions"}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
