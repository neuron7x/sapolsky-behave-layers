"""Fail-closed gate for the CWC Vertical Inference Ascension programme."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "docs/acts/CWC_VIA_01.md",
    "engineering/via_architecture_contract.json",
    "cwc/causal/__init__.py",
    "cwc/causal/potential_outcomes.py",
    "cwc/causal/interventions.py",
    "cwc/causal/cate.py",
    "cwc/causal/crossfit.py",
    "cwc/causal/opportunity.py",
    "experiments/via_v1_causal_surface/PREREGISTRATION.md",
    "experiments/via_v1_causal_surface/protocol.yaml",
    "experiments/via_v1_causal_surface/run.py",
    "experiments/via_v1_causal_surface/analyze.py",
    "experiments/via_v1_causal_surface/nulls.py",
    "docs/acts/CWC_VIA_02.md",
    "experiments/via_v1_attention_horizon_qualification/PREREGISTRATION.md",
    "experiments/via_v1_attention_horizon_qualification/protocol.yaml",
    "experiments/via_v1_attention_horizon_qualification/run.py",
    "experiments/via_v1_attention_horizon_qualification/analyze.py",
    "scripts/via_status.py",
    "artifacts/via-v1-causal-surface/verdict.json",
    "artifacts/via-v1-attention-horizon-qualification/verdict.json",
    "artifacts/via-v1-evidence-sufficiency/verdict.json",
]


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text())
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).is_file():
            errors.append(f"missing required VIA file: {rel}")

    if errors:
        return errors

    try:
        contract = _read_json(root / "engineering/via_architecture_contract.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"invalid VIA architecture contract: {exc}"]
    if contract.get("schema_version") != 1:
        errors.append("unsupported VIA architecture contract schema")
    if contract.get("current_authorized_scientific_level") != "VIA-V1":
        errors.append("current authorized scientific level must remain VIA-V1")

    try:
        wp18 = _read_json(root / contract["prior_kill_rule"]["source"])
        wp19 = _read_json(root / contract["prior_kill_rule"]["reinforced_by"])
    except (KeyError, OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"cannot resolve binding prior evidence: {exc}")
        return errors
    if wp18.get("verdict") != contract["prior_kill_rule"]["required_verdict"]:
        errors.append("WP18 binding kill verdict changed or missing")
    if wp19.get("verdict") != contract["prior_kill_rule"]["required_reinforcement"]:
        errors.append("WP19 binding robustness verdict changed or missing")

    try:
        via = _read_json(root / "artifacts/via-v1-causal-surface/verdict.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"invalid VIA-V1 verdict: {exc}")
        return errors
    if via.get("verdict") != "VIA_V1_METHOD_VALIDATED_ASCENSION_BLOCKED":
        errors.append(f"unexpected VIA-V1 verdict {via.get('verdict')!r}")
    if via.get("ascension_authorized") is not False:
        errors.append("retrospective VIA-V1 audit must not authorize ascension")
    if via.get("next_scientific_level_authorized") is not False:
        errors.append("VIA-V2 must remain unauthorized")
    checks = via.get("method_checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        errors.append("one or more VIA-V1 method checks failed")

    try:
        qualifier = _read_json(root / "artifacts/via-v1-attention-horizon-qualification/verdict.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"invalid attention-horizon qualification verdict: {exc}")
        return errors
    allowed_qualifier_verdicts = {
        "ATTENTION_HORIZON_MECHANISM_QUALIFIED_CONTROL_ONLY",
        "ATTENTION_HORIZON_MECHANISM_REJECTED",
    }
    if qualifier.get("verdict") not in allowed_qualifier_verdicts:
        errors.append(f"unexpected attention-horizon qualifier verdict {qualifier.get('verdict')!r}")
    if qualifier.get("scientific_pass") is not False:
        errors.append("controlled mechanism qualification must not claim scientific VIA-V1 PASS")
    if qualifier.get("ascension_authorized") is not False:
        errors.append("controlled mechanism qualification must not authorize ascension")
    if qualifier.get("via_v2_authorized") is not False:
        errors.append("attention-horizon qualification must not authorize VIA-V2")
    qchecks = qualifier.get("checks")
    if qualifier.get("verdict") == "ATTENTION_HORIZON_MECHANISM_QUALIFIED_CONTROL_ONLY":
        if not isinstance(qchecks, dict) or not qchecks or not all(value is True for value in qchecks.values()):
            errors.append("qualified attention-horizon candidate has a failed qualification check")

    try:
        sufficiency = _read_json(root / "artifacts/via-v1-evidence-sufficiency/verdict.json")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"invalid VIA-V1 evidence-sufficiency verdict: {exc}")
        return errors
    if sufficiency.get("verdict") != "VIA_V1_INSTANCE_OPPORTUNITY_UNIDENTIFIED_FROM_FROZEN_REAL_EVIDENCE":
        errors.append("frozen real evidence must not be represented as identifying G_instance")
    if sufficiency.get("real_instance_opportunity_identified") is not False:
        errors.append("real instance opportunity identification flag must remain false")
    if sufficiency.get("ascension_authorized") is not False:
        errors.append("evidence-sufficiency audit must not authorize ascension")
    future = sufficiency.get("required_future_artifact_contract")
    required_future = {
        "independent_unit_id", "immutable_unit_payload_hash", "same_unit_all_actions",
        "raw_quality_before_scalarization", "raw_compute_per_action", "action_execution_identity",
        "cluster_id_if_units_share_source", "no_preaggregation_before_evidence_seal",
    }
    if not isinstance(future, dict) or any(future.get(k) is not True for k in required_future):
        errors.append("future VIA-V1 artifact contract is incomplete")

    # Descendant fail-closed rule.  Any later verdict that claims authorization
    # while V1 is blocked is a hard programme violation.
    for level in range(2, 8):
        for path in (root / "artifacts").glob(f"via-v{level}*/verdict.json"):
            try:
                descendant = _read_json(path)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"invalid descendant verdict {path.relative_to(root)}: {exc}")
                continue
            if descendant.get("ascension_authorized") is True or descendant.get("scientific_pass") is True:
                errors.append(
                    f"{path.relative_to(root)} claims scientific authorization while VIA-V1 is blocked"
                )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"VIA-GATE-FAIL: {error}")
        return 1
    print(
        "VIA-GATE: PASS (engineering substrate coherent; scientific ascension remains "
        "BLOCKED_AT_VIA_V1 by binding prior evidence)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
