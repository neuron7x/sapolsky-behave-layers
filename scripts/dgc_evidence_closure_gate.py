from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.governance.evidence_closure import ClosureError, EvidenceClosureLedger


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a fail-closed DGC evidence-closure ledger.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--repo-commit", required=True)
    parser.add_argument("--repo-tree", required=True)
    args = parser.parse_args()

    try:
        ledger = EvidenceClosureLedger(
            repository_root=args.root,
            ledger_path=args.ledger,
            generation_id=args.generation_id,
            repo_commit=args.repo_commit,
            repo_tree=args.repo_tree,
        )
        state = ledger.load()
        result = {
            "status": "PASS",
            "next_stage": ledger.next_stage(),
            "product_qualified": state["product_qualified"],
            "completed_stages": state["completed_stages"],
        }
    except (ClosureError, OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"status": "FAIL", "reason": str(exc)}
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
