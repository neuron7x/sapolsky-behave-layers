from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.dgc_01.analysis import summarize
from experiments.dgc_01.baselines import POLICIES
from experiments.dgc_01.oracle import oracle_should_compute
from experiments.dgc_01.workloads import generate_workload

ROOT = Path(__file__).resolve().parents[2]


def run(per_regime: int, seed_offset: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    tasks = generate_workload(per_regime, seed_offset=seed_offset)
    rows: list[dict[str, object]] = []
    for task in tasks:
        for policy in POLICIES:
            decision = policy(task)
            if decision.buy_diagnostic:
                decision_loss = 0.0
                compute_cost = task.diagnostic_cost
            else:
                decision_loss = task.realized_loss(task.baseline_action)
                compute_cost = 0.0
            rows.append(
                {
                    "task_id": task.task_id,
                    "regime": task.regime,
                    "policy": decision.policy,
                    "buy_diagnostic": decision.buy_diagnostic,
                    "oracle_should_compute": oracle_should_compute(task),
                    "score": decision.score,
                    "decision_loss": decision_loss,
                    "compute_cost": compute_cost,
                    "uncertainty_bits": task.uncertainty_bits,
                    "p_world_b": task.p_world_b,
                    "diagnostic_cost": task.diagnostic_cost,
                    "expected_baseline_regret": task.expected_baseline_regret,
                    "true_world": task.true_world,
                }
            )
    return rows, summarize(rows)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-regime", type=int, default=20_000)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/dgc-01-dev")
    parser.add_argument("--keep-raw", action="store_true", help="retain the regenerable raw JSONL instead of compact digest-only evidence")
    args = parser.parse_args()
    rows, summary = run(args.per_regime, args.seed_offset)
    args.output.mkdir(parents=True, exist_ok=True)
    raw = args.output / "raw_results.jsonl"
    with raw.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    verdict = {
        "schema": "dgc-01-development/1",
        "status": "DEVELOPMENT_ONLY_NOT_CONFIRMATORY",
        "per_regime": args.per_regime,
        "seed_offset": args.seed_offset,
        "summary": summary,
        "claim_promotion": "PROHIBITED",
        "reason": "Development execution is not the untouched preregistered confirmatory cohort.",
    }
    verdict_path = args.output / "verdict.json"
    verdict_path.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw_descriptor = {
        "file": "raw_results.jsonl",
        "sha256": _sha256(raw),
        "bytes": raw.stat().st_size,
        "line_count": len(rows),
        "regeneration": f"python -m experiments.dgc_01.run --per-regime {args.per_regime} --seed-offset {args.seed_offset} --keep-raw",
        "derived_regenerable": True,
    }
    raw_descriptor_path = args.output / "raw_results_digest.json"
    raw_descriptor_path.write_text(json.dumps(raw_descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.keep_raw:
        raw.unlink()
    manifest = {
        "raw_results_digest.json": _sha256(raw_descriptor_path),
        "verdict.json": _sha256(verdict_path),
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(manifest.items())), encoding="utf-8"
    )
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
