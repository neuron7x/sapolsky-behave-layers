"""Evidence-derived readiness where blockers dominate any numeric score."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReadinessFacts:
    architecture_contract: bool
    inference_integrity: bool
    hermetic_reproduction: bool
    supply_chain_inventory: bool
    adversarial_gate: bool
    claim_artifacts_complete: bool
    negative_results_preserved: bool
    documentation_traceable: bool
    supported_claims: int
    independently_replicated_supported_claims: int
    real_workload_supported_claims: int
    restricted_data_present: bool


WEIGHTS = {
    "architecture": 10,
    "inference_integrity": 15,
    "reproducibility": 15,
    "supply_chain": 10,
    "adversarial_testing": 15,
    "claim_evidence": 15,
    "negative_results": 10,
    "documentation": 10,
}


def assess_readiness(facts: ReadinessFacts) -> dict[str, Any]:
    counts = (
        facts.supported_claims,
        facts.independently_replicated_supported_claims,
        facts.real_workload_supported_claims,
    )
    if any(count < 0 for count in counts):
        raise ValueError("claim counts must be non-negative")
    if facts.independently_replicated_supported_claims > facts.supported_claims:
        raise ValueError("replicated supported claims cannot exceed supported claims")
    if facts.real_workload_supported_claims > facts.supported_claims:
        raise ValueError("real-workload supported claims cannot exceed supported claims")

    subscores = {
        "architecture": WEIGHTS["architecture"] if facts.architecture_contract else 0,
        "inference_integrity": WEIGHTS["inference_integrity"] if facts.inference_integrity else 0,
        "reproducibility": WEIGHTS["reproducibility"] if facts.hermetic_reproduction else 0,
        "supply_chain": WEIGHTS["supply_chain"] if facts.supply_chain_inventory else 0,
        "adversarial_testing": WEIGHTS["adversarial_testing"] if facts.adversarial_gate else 0,
        "claim_evidence": WEIGHTS["claim_evidence"] if facts.claim_artifacts_complete else 0,
        "negative_results": WEIGHTS["negative_results"] if facts.negative_results_preserved else 0,
        "documentation": WEIGHTS["documentation"] if facts.documentation_traceable else 0,
    }
    score = sum(subscores.values())
    blockers = []
    if not facts.claim_artifacts_complete:
        blockers.append("one or more registered claim artifacts are missing")
    if facts.supported_claims and (
        facts.independently_replicated_supported_claims < facts.supported_claims
    ):
        blockers.append("supported claims are not all independently replicated")
    if facts.real_workload_supported_claims == 0:
        blockers.append("no supported real-workload claim")
    if facts.restricted_data_present:
        blockers.append("restricted corpus exists and remains quarantined")
    missing_controls = [
        name
        for name, present in (
            ("architecture contract", facts.architecture_contract),
            ("inference integrity", facts.inference_integrity),
            ("hermetic reproduction", facts.hermetic_reproduction),
            ("supply-chain inventory", facts.supply_chain_inventory),
            ("adversarial gate", facts.adversarial_gate),
            ("claim artifacts", facts.claim_artifacts_complete),
            ("negative-results register", facts.negative_results_preserved),
            ("documentation traceability", facts.documentation_traceable),
        )
        if not present
    ]
    if missing_controls:
        blockers.append("missing engineering controls: " + ", ".join(missing_controls))

    if score < 70:
        status = "NOT_READY"
    elif blockers or score < 100:
        status = "LOCALLY_VERIFIED_RESEARCH_ENGINEERING"
    else:
        status = "EXTERNALLY_VALIDATED_RESEARCH_SYSTEM"
    return {
        "schema_version": 1,
        "status": status,
        "technical_score": score,
        "score_ceiling": 100,
        "blocking_facts": blockers,
        "subscores": subscores,
        "facts": asdict(facts),
        "interpretation": (
            "The score summarizes implemented controls. Blocking facts determine "
            "the status and cannot be overridden by the score."
        ),
    }


def _artifact_exists(root: Path, value: str) -> bool:
    path = root / value
    if value.endswith("/"):
        return path.is_dir() and any(path.iterdir())
    return path.exists()


def collect_facts(root: Path) -> ReadinessFacts:
    registry = json.loads((root / "claim_registry.json").read_text(encoding="utf-8"))
    data_baseline = json.loads(
        (root / "engineering/data_corpus_baseline.json").read_text(encoding="utf-8")
    )
    claims = registry["claims"]
    supported = [
        claim for claim in claims
        if str(claim.get("status", "")).startswith("SUPPORTED")
    ]
    artifacts_complete = all(
        _artifact_exists(root, artifact)
        for claim in claims
        for artifact in claim.get("required_artifacts", [])
    )
    real_workload = sum(
        1 for claim in supported
        if any(
            "real" in str(value).casefold()
            for value in claim.get("scope", {}).get("tasks", [])
        )
    )
    return ReadinessFacts(
        architecture_contract=(root / "engineering/architecture_contract.json").is_file(),
        inference_integrity=(root / "engineering/inference_integrity_contract.json").is_file(),
        hermetic_reproduction=(root / "engineering/hermeticity_contract.json").is_file(),
        supply_chain_inventory=(root / "docs/security/SBOM.cdx.json").is_file(),
        adversarial_gate=(root / "scripts/assurance_attack.py").is_file(),
        claim_artifacts_complete=artifacts_complete,
        negative_results_preserved=(root / "docs/methodology/NEGATIVE_RESULTS_REGISTER.json").is_file(),
        documentation_traceable=(root / "docs/vnv/REQUIREMENTS_TRACEABILITY_MATRIX.csv").is_file(),
        supported_claims=len(supported),
        independently_replicated_supported_claims=sum(
            bool(claim.get("independent_replication")) for claim in supported
        ),
        real_workload_supported_claims=real_workload,
        restricted_data_present=data_baseline["category_file_count"].get("restricted", 0) > 0,
    )
