from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"research/registry/dgc_math_proof_ledger_v1.json"
ALLOWED={"COUNTEREXAMPLE_ANCHORED","PROVED_NARROW_EXECUTABLE","ENGINEERING_AUTHORITY_CONTRACT","EMPIRICAL_ANCHORED_FINITE_THEOREM","EXHAUSTIVE_FINITE_MODELCHECK","OPEN"}


def main():
    data=json.loads(LEDGER.read_text())
    if data.get("schema")!="DGC_MATH_PROOF_LEDGER_V1": raise AssertionError("wrong proof ledger schema")
    rows=data.get("entries",[]); ids=set()
    for row in rows:
        rid=row["id"]
        if rid in ids: raise AssertionError(f"duplicate proof id {rid}")
        ids.add(rid)
        if row["status"] not in ALLOWED: raise AssertionError(f"invalid status {rid}")
        if row.get("novelty_claim") is not False: raise AssertionError(f"novelty inflation {rid}")
        if row["status"]!="OPEN":
            if not row.get("assumptions"): raise AssertionError(f"missing assumptions {rid}")
            for field in ("implementation","test"):
                value=str(row.get(field,""))
                if not value or not (ROOT/value).exists(): raise AssertionError(f"missing {field} for {rid}: {value}")
            if not row.get("prior_art"): raise AssertionError(f"missing prior art {rid}")
    reviewed=sum(bool(r.get("independent_reviewed")) for r in rows)
    print(f"DGC-PROOF-LEDGER: PASS entries={len(rows)} independent_reviewed={reviewed} formal_complete=false")
    return 0

if __name__=="__main__": raise SystemExit(main())
