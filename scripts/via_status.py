"""Machine-readable status resolver for the CWC-VIA dependency DAG."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "engineering/via_architecture_contract.json"
V1_VERDICT = ROOT / "artifacts/via-v1-causal-surface/verdict.json"


def resolve(root: Path = ROOT) -> dict[str, Any]:
    contract = json.loads((root / "engineering/via_architecture_contract.json").read_text())
    prior = contract["prior_kill_rule"]
    wp18 = json.loads((root / prior["source"]).read_text())
    kill_active = wp18.get("verdict") == prior["required_verdict"]

    v1_path = root / "artifacts/via-v1-causal-surface/verdict.json"
    v1 = json.loads(v1_path.read_text()) if v1_path.is_file() else None
    v1_scientific_pass = bool(v1 and v1.get("scientific_pass") is True)
    v1_method_validated = bool(
        v1 and v1.get("verdict") == "VIA_V1_METHOD_VALIDATED_ASCENSION_BLOCKED"
    )

    qpath = root / "artifacts/via-v1-attention-horizon-qualification/verdict.json"
    qualifier = json.loads(qpath.read_text()) if qpath.is_file() else None
    candidate_status = (
        qualifier.get("verdict") if isinstance(qualifier, dict) else "NOT_EXECUTED"
    )

    levels: list[dict[str, Any]] = []
    for level in contract["levels"]:
        lid = level["id"]
        if lid == "VIA-V1":
            if v1_scientific_pass:
                status = "PASS"
                reason = "scientific VIA-V1 pass artifact present"
            elif v1_method_validated:
                status = "BLOCKED"
                if candidate_status == "ATTENTION_HORIZON_MECHANISM_QUALIFIED_CONTROL_ONLY":
                    reason = (
                        "retrospective method validated; attention-horizon mechanism qualified only "
                        "for a future prospective real VIA-V1 pilot; binding scientific gate remains closed"
                    )
                else:
                    reason = "method validated retrospectively; binding WP18 kill rule remains active"
            else:
                status = "PENDING" if not kill_active else "BLOCKED"
                reason = "no admissible new VIA-V1 scientific evidence"
        else:
            parent = levels[-1]
            if parent["status"] == "PASS":
                status = "PENDING"
                reason = f"ancestor {parent['id']} passed; this level has no pass artifact yet"
            else:
                status = "BLOCKED_BY_ANCESTOR"
                reason = f"ancestor {parent['id']} status={parent['status']}"
        levels.append({"id": lid, "name": level["name"], "status": status, "reason": reason})

    return {
        "programme": "CWC-VIA",
        "prior_kill_rule_active": kill_active,
        "candidate_qualification": candidate_status,
        "current_scientific_frontier": next(
            (item["id"] for item in levels if item["status"] != "PASS"), "COMPLETE"
        ),
        "levels": levels,
    }


def main() -> int:
    status = resolve()
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
