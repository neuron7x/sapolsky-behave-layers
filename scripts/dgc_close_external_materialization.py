from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from cwc.governance.evidence_closure import EvidenceClosureLedger
from cwc.governance.materialization_closure import (
    close_materialized_verified,
    close_source_verified,
)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle" / "dgc-evidence-closure"
GENERATION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def _generation_id(value: str) -> str:
    if not GENERATION_ID_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "generation-id must be 1-128 characters: letters, digits, dot, underscore or hyphen; no path separators"
        )
    return value


def _capture(*args: str) -> str:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _repo_identity() -> tuple[str, str]:
    commit = _capture("git", "rev-parse", "HEAD")
    tree = _capture("git", "rev-parse", "HEAD^{tree}")
    dirty = _capture("git", "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise RuntimeError("repository must be clean before evidence closure")
    return commit, tree


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Close DGC SOURCE_VERIFIED and MATERIALIZED_VERIFIED stages against one verified external generation."
    )
    parser.add_argument("--generation-id", required=True, type=_generation_id)
    parser.add_argument("--generation-root", required=True)
    args = parser.parse_args()

    commit, tree = _repo_identity()
    runtime = RUNTIME_ROOT / args.generation_id
    ledger = EvidenceClosureLedger(
        repository_root=ROOT,
        ledger_path=runtime / "closure-ledger.json",
        generation_id=args.generation_id,
        repo_commit=commit,
        repo_tree=tree,
    )

    transitions: list[dict[str, object]] = []
    if ledger.next_stage() == "SOURCE_VERIFIED":
        receipt = close_source_verified(ledger)
        transitions.append({"stage": "SOURCE_VERIFIED", "receipt_digest": receipt["receipt_digest"]})
    if ledger.next_stage() == "MATERIALIZED_VERIFIED":
        receipt = close_materialized_verified(
            ledger,
            generation_root=Path(args.generation_root),
            reference_path=runtime / "materialization-reference.json",
        )
        transitions.append({"stage": "MATERIALIZED_VERIFIED", "receipt_digest": receipt["receipt_digest"]})

    state = ledger.load()
    print(
        json.dumps(
            {
                "status": "PASS",
                "generation_id": args.generation_id,
                "repo_commit": commit,
                "repo_tree": tree,
                "completed_stages": state["completed_stages"],
                "next_stage": ledger.next_stage(),
                "transitions": transitions,
                "product_qualified": state["product_qualified"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
