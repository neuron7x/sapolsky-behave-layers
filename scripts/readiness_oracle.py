"""Emit an evidence-derived, blocking-facts-first system readiness verdict."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.assurance.readiness import assess_readiness, collect_facts

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("assurance-build/READINESS.json"))
    args = parser.parse_args()
    result = assess_readiness(collect_facts(ROOT))
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"READINESS: {result['status']} score={result['technical_score']}/100")
    for blocker in result["blocking_facts"]:
        print(f"READINESS-BLOCKER: {blocker}")
    return 0 if result["status"] != "NOT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
