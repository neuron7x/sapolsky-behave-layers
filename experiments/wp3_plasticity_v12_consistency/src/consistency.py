"""L4j sub-line consistency audit.

Cross-checks that every CWC-L4* claim's registry status matches its artifact verdict polarity,
and that no L4 evidence bundle is orphaned from the registry. A governance check the existing
gates do not perform. See PREREGISTRATION.md. Deterministic, read-only over committed state.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/wp3-plasticity-v12-consistency"

POS_TOKENS = ("CONFIRMED", "SUPPORTED", "MAPPED", "GENERALIZES", "ROBUST", "_GO", "GO_")
NEG_TOKENS = ("VIOLATED", "INCOMPLETE", "NOT_SUPPORTED", "NOT_MAPPED", "NOT_CONFIRMED", "VOID")


def _verdict_polarity(v: str) -> str:
    up = v.upper()
    if any(t in up for t in NEG_TOKENS):
        return "negative"
    if any(t in up for t in POS_TOKENS):
        return "positive"
    return "unknown"


def _status_polarity(status: str) -> str:
    if status in ("SUPPORTED", "SUPPORTED_NARROWED"):
        return "positive"
    if status == "NOT_SUPPORTED":
        return "negative"
    return "untested"


def _find_verdict(required: list[str]) -> dict[str, Any] | None:
    for art in required:
        p = ROOT / art.rstrip("/") / "verdict.json"
        if p.is_file():
            return json.loads(p.read_text())
    return None


def analyze() -> dict[str, Any]:
    reg = json.loads((ROOT / "claim_registry.json").read_text())
    l4_claims = [c for c in reg["claims"] if c["claim_id"].startswith("CWC-L4")]

    checks = []
    mismatches = 0
    for c in l4_claims:
        vj = _find_verdict(c.get("required_artifacts", []))
        if vj is None:
            checks.append({"claim": c["claim_id"], "status": c["status"], "verdict": None,
                           "match": None, "note": "no artifact verdict.json"})
            continue
        vstr = str(vj.get("verdict") or vj.get("status") or "")
        vp = _verdict_polarity(vstr)
        sp = _status_polarity(c["status"])
        match = (vp == sp) or (sp == "positive" and vp == "positive")
        if not match:
            mismatches += 1
        checks.append({"claim": c["claim_id"], "status": c["status"], "status_polarity": sp,
                       "verdict": vstr, "verdict_polarity": vp, "match": match})

    # orphan evidence: any wp3-plasticity-v* bundle with a verdict.json not referenced by a claim
    referenced = {a.rstrip("/") for c in reg["claims"] for a in c.get("required_artifacts", [])}
    orphans = []
    for d in sorted(glob.glob(str(ROOT / "artifacts/wp3-plasticity-v*"))):
        rel = str(Path(d).relative_to(ROOT))
        if (Path(d) / "verdict.json").is_file() and rel not in referenced:
            orphans.append(rel)

    consistent = mismatches == 0 and len(orphans) == 0
    verdict = "L4J_CONSISTENT" if consistent else "L4J_INCONSISTENT"
    return {
        "experiment": "wp3_plasticity_v12_consistency",
        "verdict": verdict,
        "tier": "PROCESS — governance consistency of the L4 sub-line",
        "n_l4_claims": len(l4_claims),
        "checks": checks,
        "polarity_mismatches": mismatches,
        "orphan_evidence": orphans,
        "consistent": consistent,
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4j CONSISTENCY VERDICT: {r['verdict']}")
    print(f"  L4 claims checked: {r['n_l4_claims']}  mismatches: {r['polarity_mismatches']}  "
          f"orphans: {len(r['orphan_evidence'])}")
    for ch in r["checks"]:
        if ch["match"] is False:
            print(f"  MISMATCH {ch['claim']}: status={ch['status']} verdict={ch['verdict']}")


if __name__ == "__main__":
    main()
