#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cwc.counterfactual.falsifiability import information_budget_certificate

SOURCE = ROOT / "research/results/CSCA-06A-R1/verdict.json"
OUT = ROOT / "artifacts/csca-06a-information-converse"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    verdict = json.loads(SOURCE.read_text())
    if verdict.get("verdict") != "GLOBAL_CHECKPOINT_FALSIFIABILITY_QUALIFIED_NARROWED":
        raise RuntimeError("R1 source verdict is not the sealed qualified object")
    alpha = float(verdict["alpha"])
    target_power = 0.95  # inherited from the frozen parent/R1 structural gate
    max_cost = float(verdict["max_cost"])
    families = {}
    for family in ("E0_SINGLE_ACTION_EQUIVALENCE", "S1_MISSING_TRUE_EDGE", "S2_MISSING_TRUE_EDGE_NEGATIVE", "S3_SPURIOUS_CANDIDATE_EDGE", "W1_WEAK_EDGE_BUDGET_STRESS"):
        rate = float(verdict["primary_summary"][family]["separation_rate_per_cost"])
        cert = information_budget_certificate(
            alpha=alpha,
            target_power=target_power,
            separation_rate_per_cost=rate,
            available_cost=max_cost,
        )
        row = asdict(cert)
        if row['necessary_cost_lower_bound'] == float('inf'):
            row['necessary_cost_lower_bound'] = None
            row['necessary_cost_is_infinite'] = True
        else:
            row['necessary_cost_is_infinite'] = False
        families[family] = row
    payload = {
        "artifact_id": "CSCA-06A-INFORMATION-CONVERSE",
        "status": "MATHEMATICAL_POSTCONFIRMATORY_DIAGNOSTIC",
        "source_verdict": str(SOURCE.relative_to(ROOT)),
        "source_verdict_sha256": sha256(SOURCE),
        "theorem": "For a level-alpha rejection event with power >=p under P*, data processing requires inf_Q KL(P*||Q) >= kl(p||alpha). For a fixed design with separation rate R nat/cost, Cost >= kl(p||alpha)/R is necessary, not sufficient.",
        "families": families,
        "authority": {
            "graph_truth": False,
            "nuisance_decomposition": False,
            "shadow_promotion": False,
            "active_control": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = OUT / "certificate.json"
    cert_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = sha256(cert_path)
    (OUT / "SHA256SUMS").write_text(f"{digest}  certificate.json\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
