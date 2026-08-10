from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from cwc.research_ops.compute_governor import ComputeGovernor, ComputeRequest
from cwc.research_ops.governance import HumanDecision, validate_human_decision
from cwc.research_ops.provenance import sha256_file

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "research/registry"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_dataclass(cls, payload):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in payload.items() if k in names})


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    required = [
        ROOT / "docs/acts/ACT_RD_02.md",
        REG / "rd02_sources.json",
        REG / "rd02_claims.json",
        REG / "rd02_hypotheses.json",
        REG / "rd02_compute_requests.json",
        REG / "rd02_pipeline_state.json",
        ROOT / "experiments/csca_01/PREREGISTRATION.md",
    ]
    for path in required:
        check(path.exists(), f"missing required RD02 artifact: {path.relative_to(ROOT)}", errors)
    if errors:
        print("RESEARCH-OPS-GATE: FAIL")
        for err in errors:
            print(" -", err)
        return 1

    sources = load(REG / "rd02_sources.json")
    for source in sources:
        raw = Path(source["raw_path"])
        check(raw.is_file(), f"frozen source missing: {raw}", errors)
        if raw.is_file():
            check(sha256_file(raw) == source["content_sha256"], f"source hash mismatch: {source['source_id']}", errors)
        if not source["primary_source_bytes"]:
            check(source["gate_status"] != "SOURCE_VERIFIED", "snapshot-only source may not be SOURCE_VERIFIED", errors)

    claims = load(REG / "rd02_claims.json")
    for claim in claims:
        span = claim.get("source_span", {})
        check(bool(span.get("source_path")), f"claim {claim.get('claim_id')} missing source path", errors)
        check(int(span.get("start_line", 0)) >= 1, f"claim {claim.get('claim_id')} missing source line", errors)
        check(claim.get("status") == "UNVERIFIED_EXTRACTION", f"machine extraction self-promoted: {claim.get('claim_id')}", errors)

    requests = load(REG / "rd02_compute_requests.json")
    for entry in requests:
        req = build_dataclass(ComputeRequest, entry["request"])
        actual = entry["decision"]
        expected = ComputeGovernor.evaluate(req)
        check(actual["approved"] == expected.approved and actual["reason"] == expected.reason, f"compute decision drift: {req.compute_request_id}", errors)

    for path in sorted((ROOT / "research/governance").glob("*.json")):
        payload = load(path)
        try:
            validate_human_decision(build_dataclass(HumanDecision, payload))
        except Exception as exc:  # fail-closed gate
            errors.append(f"invalid human decision {path.name}: {exc}")
        if payload.get("architecture_authority"):
            check(payload.get("reviewer") not in {"UNASSIGNED_HUMAN_REVIEWER", "MODEL", "LLM"}, f"non-human architecture authority: {path.name}", errors)

    state = load(REG / "rd02_pipeline_state.json")
    check(not state.get("architecture_promotion_authority"), "RD02 may not self-grant architecture promotion", errors)

    verdict_path = ROOT / "research/results/CSCA-01/verdict.json"
    if verdict_path.exists():
        verdict = load(verdict_path)
        check(verdict["preregistration_sha256"] == sha256_file(ROOT / "experiments/csca_01/PREREGISTRATION.md"), "CSCA preregistration hash drift", errors)
        check(verdict["implementation_sha256"] == sha256_file(ROOT / "experiments/csca_01/run.py"), "CSCA implementation hash drift", errors)
        check(not verdict.get("paper_reproduction_authority"), "snapshot-only run may not claim paper reproduction", errors)
        check(not verdict.get("architecture_promotion_authority"), "CSCA result may not self-promote architecture", errors)
        telemetry = ROOT / "research/results/CSCA-01/run_telemetry.jsonl"
        check(telemetry.exists(), "CSCA verdict exists without run telemetry", errors)
        if telemetry.exists():
            check(verdict.get("telemetry_sha256") == sha256_file(telemetry), "CSCA telemetry hash drift", errors)

    if errors:
        print("RESEARCH-OPS-GATE: FAIL")
        for err in errors:
            print(" -", err)
        return 1
    print(f"RESEARCH-OPS-GATE: PASS sources={len(sources)} claims={len(claims)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
