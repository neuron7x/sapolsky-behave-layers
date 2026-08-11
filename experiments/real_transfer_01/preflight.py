from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.real_transfer_01.contract import ContractError, Cohorts, cohort_digest
from experiments.real_transfer_01.evaluator import REQUIRED_POLICIES


@dataclass(frozen=True, slots=True)
class FileDigest:
    path: str
    byte_length: int
    sha256: str


def digest_file(path: Path) -> FileDigest:
    data = path.read_bytes()
    return FileDigest(str(path), len(data), hashlib.sha256(data).hexdigest())


def canonical_record_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def exact_collision_count(needles: Iterable[str], corpus: Iterable[str]) -> int:
    corpus_set = set(corpus)
    return sum(needle in corpus_set for needle in needles)


def validate_cohorts(cohorts: Cohorts) -> dict[str, Any]:
    groups = cohorts.hashes()
    sets = {name: set(values) for name, values in groups.items()}
    if any(len(values) != len(sets[name]) for name, values in groups.items()):
        raise ContractError("duplicate record hash within cohort")
    names = tuple(groups)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = sets[a] & sets[b]
            if overlap:
                raise ContractError(f"cohort overlap {a}/{b}: {len(overlap)}")
    return {
        name: {
            "count": len(values),
            "cohort_sha256": cohort_digest(getattr(cohorts, name.lower())),
        }
        for name, values in groups.items()
    }


def validate_model_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "runner_version",
        "weights_sha256",
        "tokenizer_sha256",
        "prompt_template_sha256",
        "decoding_parameters",
        "calibration_procedure_sha256",
        "governor_parameters_sha256",
        "training_corpus_provenance",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise ContractError(f"model manifest missing: {missing}")
    for key in required - {"decoding_parameters", "training_corpus_provenance"}:
        value = manifest[key]
        if not isinstance(value, str) or not value.strip():
            raise ContractError(f"model manifest {key} must be non-empty string")


def validate_comparators(policies: Sequence[str]) -> None:
    if tuple(policies) != REQUIRED_POLICIES:
        missing = sorted(set(REQUIRED_POLICIES) - set(policies))
        extra = sorted(set(policies) - set(REQUIRED_POLICIES))
        raise ContractError(f"comparator contract mismatch missing={missing} extra={extra}")


def authority_from_contamination(training_provenance: Any, collision_audit_complete: bool) -> str:
    if training_provenance in (None, "", "UNKNOWN") or not collision_audit_complete:
        return "TRANSFER_OBSERVED_CONTAMINATION_UNKNOWN"
    return "TRANSFER_OBSERVED_CONTAMINATION_AUDITED"


def write_source_manifest(
    path: Path,
    *,
    sources: Sequence[Mapping[str, Any]],
    averitec_cohorts: Cohorts,
    hybridqa_cohorts: Cohorts,
    repo_collision_count: int,
    training_collision_count: int | None,
) -> None:
    payload = {
        "experiment": "REAL-TRANSFER-01",
        "sources": list(sources),
        "cohorts": {
            "AVeriTeC": validate_cohorts(averitec_cohorts),
            "HybridQA": validate_cohorts(hybridqa_cohorts),
        },
        "collision_audit": {
            "repository_exact_collision_count": repo_collision_count,
            "training_exact_collision_count": training_collision_count,
            "training_collision_audit_complete": training_collision_count is not None,
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


FORBIDDEN_AVERITEC_MODEL_FIELDS = {
    "label",
    "gold_label",
    "gold_action",
    "justification",
    "fact_checking_article",
    "original_claim_url",
    "cached_original_claim_url",
    "record_hash",
    "cohort",
}


def validate_averitec_model_input(payload: Mapping[str, Any]) -> None:
    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            overlap = FORBIDDEN_AVERITEC_MODEL_FIELDS.intersection(map(str, value.keys()))
            if overlap:
                raise ContractError(f"forbidden AVeriTeC model-input fields: {sorted(overlap)}")
            for child in value.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)
    walk(payload)


def validate_hybridqa_stage0(payload: Mapping[str, Any], initial_modality: str) -> None:
    has_table = "table" in payload
    has_text = "linked_text" in payload
    if initial_modality == "TABLE_ONLY":
        if not has_table or has_text:
            raise ContractError("TABLE_ONLY stage0 leaked/missed complementary modality")
    elif initial_modality == "TEXT_ONLY":
        if not has_text or has_table:
            raise ContractError("TEXT_ONLY stage0 leaked/missed complementary modality")
    else:
        raise ContractError(f"invalid initial modality: {initial_modality}")
    if "gold_answer" in payload or "answer-text" in payload:
        raise ContractError("HybridQA gold answer leaked into model input")


def validate_calibration_binding(metadata: Mapping[str, Any]) -> None:
    if metadata.get("threshold_fit_cohort") != "CALIBRATION":
        raise ContractError("thresholds must be fit on CALIBRATION only")
    observed = metadata.get("observed_cohorts_before_freeze", [])
    if not isinstance(observed, list):
        raise ContractError("observed_cohorts_before_freeze must be a list")
    prohibited = {"PRIMARY", "REPLICATION"}.intersection(map(str, observed))
    if prohibited:
        raise ContractError(f"post-calibration tuning leakage: {sorted(prohibited)}")
