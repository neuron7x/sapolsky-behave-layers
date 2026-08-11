from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from experiments.real_transfer_01.contract import ContractError, Cohorts, cohort_digest
from experiments.real_transfer_01.evaluator import REQUIRED_POLICIES


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
_SOURCE_FAMILIES = {"AVeriTeC", "HybridQA"}
_COHORT_NAMES = ("CALIBRATION", "PRIMARY", "REPLICATION")


def _require_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ContractError(f"{field} must be lowercase 64-hex SHA-256")
    return value


def _canonical_json_sha256(value: Any, *, field: str) -> str:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{field} must be finite JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


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
            "record_hashes": list(values),
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
        "decoding_parameters_sha256",
        "calibration_procedure_sha256",
        "governor_parameters_sha256",
        "training_corpus_provenance",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise ContractError(f"model manifest missing: {missing}")
    if not isinstance(manifest["runner_version"], str) or not manifest["runner_version"].strip():
        raise ContractError("model manifest runner_version must be non-empty string")
    for key in (
        "weights_sha256",
        "tokenizer_sha256",
        "prompt_template_sha256",
        "decoding_parameters_sha256",
        "calibration_procedure_sha256",
        "governor_parameters_sha256",
    ):
        _require_sha256(manifest[key], field=f"model manifest {key}")
    if not isinstance(manifest["decoding_parameters"], Mapping):
        raise ContractError("model manifest decoding_parameters must be an object")
    observed_decoding_sha = _canonical_json_sha256(
        manifest["decoding_parameters"], field="decoding_parameters"
    )
    if observed_decoding_sha != manifest["decoding_parameters_sha256"]:
        raise ContractError("decoding_parameters_sha256 does not bind decoding_parameters")
    provenance = manifest["training_corpus_provenance"]
    if provenance in (None, ""):
        raise ContractError("training_corpus_provenance must be declared; use UNKNOWN if unavailable")
    _canonical_json_sha256(provenance, field="training_corpus_provenance")


def validate_comparators(policies: Sequence[str]) -> None:
    if tuple(policies) != REQUIRED_POLICIES:
        missing = sorted(set(REQUIRED_POLICIES) - set(policies))
        extra = sorted(set(policies) - set(REQUIRED_POLICIES))
        raise ContractError(f"comparator contract mismatch missing={missing} extra={extra}")


def authority_from_contamination(training_provenance: Any, collision_audit_complete: bool) -> str:
    if training_provenance in (None, "", "UNKNOWN") or not collision_audit_complete:
        return "TRANSFER_OBSERVED_CONTAMINATION_UNKNOWN"
    return "TRANSFER_OBSERVED_CONTAMINATION_AUDITED"


def validate_source_manifest(payload: Mapping[str, Any]) -> None:
    if payload.get("experiment") != "REAL-TRANSFER-01":
        raise ContractError("source manifest experiment mismatch")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ContractError("source manifest sources must be a non-empty list")
    seen_families: set[str] = set()
    for i, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise ContractError(f"source[{i}] must be an object")
        required = {
            "family", "canonical_url", "ref", "path", "byte_length", "sha256",
            "license", "acquired_at",
        }
        missing = sorted(required - set(source))
        if missing:
            raise ContractError(f"source[{i}] missing: {missing}")
        family = source["family"]
        if family not in _SOURCE_FAMILIES:
            raise ContractError(f"source[{i}] invalid family: {family!r}")
        seen_families.add(str(family))
        if not isinstance(source["canonical_url"], str) or not source["canonical_url"].startswith("https://"):
            raise ContractError(f"source[{i}] canonical_url must be https URL")
        for field in ("ref", "path", "license"):
            if not isinstance(source[field], str) or not source[field].strip():
                raise ContractError(f"source[{i}] {field} must be non-empty string")
        byte_length = source["byte_length"]
        if isinstance(byte_length, bool) or not isinstance(byte_length, int) or byte_length <= 0:
            raise ContractError(f"source[{i}] byte_length must be positive integer")
        _require_sha256(source["sha256"], field=f"source[{i}].sha256")
        upstream = source.get("upstream_commit_sha")
        if upstream not in (None, "") and (not isinstance(upstream, str) or not _GIT_SHA_RE.fullmatch(upstream)):
            raise ContractError(f"source[{i}] upstream_commit_sha must be 40/64-hex Git object id or null")
        if not _valid_utc_timestamp(source["acquired_at"]):
            raise ContractError(f"source[{i}] acquired_at must be ISO-8601 UTC Z timestamp")
    if seen_families != _SOURCE_FAMILIES:
        raise ContractError(f"source manifest must cover exactly both families; got={sorted(seen_families)}")

    cohorts = payload.get("cohorts")
    if not isinstance(cohorts, Mapping) or set(cohorts) != _SOURCE_FAMILIES:
        raise ContractError("source manifest cohorts must contain AVeriTeC and HybridQA")
    for family in sorted(_SOURCE_FAMILIES):
        family_groups = cohorts[family]
        if not isinstance(family_groups, Mapping) or tuple(family_groups.keys()) != _COHORT_NAMES:
            raise ContractError(f"{family} cohort keys must be CALIBRATION/PRIMARY/REPLICATION in order")
        seen_hashes: set[str] = set()
        for cohort_name in _COHORT_NAMES:
            info = family_groups[cohort_name]
            if not isinstance(info, Mapping):
                raise ContractError(f"{family}.{cohort_name} must be an object")
            hashes = info.get("record_hashes")
            if not isinstance(hashes, list):
                raise ContractError(f"{family}.{cohort_name}.record_hashes must be a list")
            if info.get("count") != len(hashes):
                raise ContractError(f"{family}.{cohort_name} count/hash mismatch")
            for h in hashes:
                _require_sha256(h, field=f"{family}.{cohort_name}.record_hash")
                if h in seen_hashes:
                    raise ContractError(f"{family} cohort overlap/duplicate for {h}")
                seen_hashes.add(h)
            expected = hashlib.sha256("\n".join(hashes).encode("utf-8")).hexdigest()
            if info.get("cohort_sha256") != expected:
                raise ContractError(f"{family}.{cohort_name} cohort_sha256 mismatch")

    collision = payload.get("collision_audit")
    if not isinstance(collision, Mapping):
        raise ContractError("source manifest collision_audit must be an object")
    repo_count = collision.get("repository_exact_collision_count")
    if isinstance(repo_count, bool) or not isinstance(repo_count, int) or repo_count < 0:
        raise ContractError("repository_exact_collision_count must be nonnegative integer")
    train_count = collision.get("training_exact_collision_count")
    if train_count is not None and (isinstance(train_count, bool) or not isinstance(train_count, int) or train_count < 0):
        raise ContractError("training_exact_collision_count must be nonnegative integer/null")
    complete = collision.get("training_collision_audit_complete")
    if not isinstance(complete, bool) or complete is not (train_count is not None):
        raise ContractError("training collision completion flag/count disagree")


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
    validate_source_manifest(payload)
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
