"""WP10 de-circularized coherence audit.

The audit found coherence 'Theorem C' circular: it checks a hand-encoded table of utility matrices
against hand-encoded expected verdicts. This replaces that with a NON-circular check: recompute each
claim's certificate G_lo from its OWN committed raw artifact and verify the recorded registry status
agrees with the certificate SIGN -- in BOTH directions (a SUPPORTED positive must have G_lo>0; a
NOT_SUPPORTED certificate claim must have G_lo<=0). Nothing is hand-encoded; every number comes from
committed evidence. See PREREGISTRATION.md. Deterministic.
"""
from __future__ import annotations

import glob
import json
import math
import statistics
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import gap_lower_confidence_bound, plugin_gap

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/wp10-coherence"
DELTA = 0.05


def _cert(mats, n_c, n_a) -> float:
    n = len(mats)
    uhat, se = [], 0.0
    for ci in range(n_c):
        row = []
        for ai in range(n_a):
            vals = [mats[s][ci][ai] for s in range(n)]
            row.append(sum(vals) / n)
            v = statistics.pvariance(vals) * n / (n - 1) if n > 1 else 0.0
            se = max(se, math.sqrt(v) / math.sqrt(n))
        uhat.append(row)
    return gap_lower_confidence_bound(plugin_gap(uhat), se, n_c, n_a, DELTA)


def _l4():
    rp = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "artifacts/wp3-plasticity-v2-confirmatory/raw_runs/seed*.json")))]
    G, T = ["attn", "mlp", "head", "embed"], ["lexical", "relational"]
    c = {a: rp[0]["tasks"][T[0]][a]["cost_params"] for a in G}
    km = max(c.values())
    return _cert([[[x["tasks"][t][a]["new_acc"] - c[a] / km for a in G] for t in T] for x in rp], 2, 4)


def _ac1():
    rc = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs/seed*.json")))]
    dep, ks = [str(d) for d in rc[0]["depths"]], [str(k) for k in rc[0]["k_choices"]]
    return _cert([[[x["acc"][d][k] for k in ks] for d in dep] for x in rc], 3, 3)


def _real_lm():
    rr = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "artifacts/wp6-real-lm/raw_runs/seed*.json")))]
    bk, ks = rr[0]["buckets"], [str(k) for k in rr[0]["k_choices"]]
    return _cert([[[-r["loss"][b][k] for k in ks] for b in bk] for r in rr], 3, 3)   # utility = -loss


def analyze() -> dict[str, Any]:
    reg = {c["claim_id"]: c for c in json.loads((ROOT / "claim_registry.json").read_text())["claims"]}
    # (recorded status, computed G_lo from real artifact); status sign must agree with G_lo sign
    cases = [
        ("CWC-L4-plasticity", reg["CWC-L4-plasticity"]["status"], _l4(), "positive"),
        ("CWC-AC1-compute-identifiability", reg["CWC-AC1-compute-identifiability"]["status"], _ac1(), "positive"),
        ("CWC-RD1-real-lm-boundary", reg["CWC-RD1-real-lm-boundary"]["status"], _real_lm(), "negative"),
    ]
    checks = []
    contradictions = 0
    for cid, status, glo, expected_sign in cases:
        status_positive = status in ("SUPPORTED", "SUPPORTED_NARROWED")
        cert_positive = glo > 0.0
        agrees = (status_positive == cert_positive)
        if not agrees:
            contradictions += 1
        checks.append({"claim": cid, "status": status, "status_positive": status_positive,
                       "g_lo_from_real_artifact": glo, "cert_positive": cert_positive,
                       "expected_sign": expected_sign, "agrees": agrees})

    verdict = "COHERENCE_DECIRCULARIZED_0_CONTRADICTIONS" if contradictions == 0 else "COHERENCE_CONTRADICTION"
    return {
        "experiment": "wp10_coherence",
        "verdict": verdict,
        "tier": "META — de-circularized coherence: recorded status vs certificate sign from real artifacts",
        "delta": DELTA,
        "checks": checks,
        "contradictions": contradictions,
        "note": "Non-circular: every G_lo is recomputed from committed raw seeds (not a hand-encoded "
                "matrix). Both directions: SUPPORTED<->G_lo>0 and NOT_SUPPORTED<->G_lo<=0 (RD1 real-LM).",
        "prohibited_extrapolations": ["independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP10 COHERENCE VERDICT: {r['verdict']}  (contradictions={r['contradictions']})")
    for c in r["checks"]:
        print(f"  {c['claim']:34s} status={c['status']:18s} G_lo={c['g_lo_from_real_artifact']:+.4f}  agrees={c['agrees']}")


if __name__ == "__main__":
    main()
