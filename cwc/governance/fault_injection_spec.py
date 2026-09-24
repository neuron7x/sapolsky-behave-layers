from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.generalization_registry import verify_generalization_registry_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SPEC_SCHEMA = "DGC_FAULT_INJECTION_SPEC_V1"
AUTHORITY_SCHEMA = "DGC_FAULT_INJECTION_SPEC_AUTHORITY_V1"

REQUIRED_FAULT_CLASSES = frozenset({
    "PROVIDER_TIMEOUT", "PROVIDER_RATE_LIMIT", "MALFORMED_MODEL_OUTPUT",
    "TOOL_TIMEOUT", "TOOL_NONZERO_EXIT", "SCORER_UNAVAILABLE",
    "BUDGET_EXHAUSTION", "WORKER_CRASH_AFTER_LEASE", "STALE_LEASE_REPLAY",
    "DUPLICATE_RESULT_COMMIT", "EVIDENCE_DIGEST_CORRUPTION", "PARTIAL_EXECUTION_POPULATION",
})
REQUIRED_GLOBAL_INVARIANTS = frozenset({
    "NO_UNAUTHORIZED_PROMOTION", "NO_BUDGET_LIMIT_BYPASS", "AUDIT_CHAIN_CONTIGUOUS",
    "NO_DUPLICATE_SIDE_EFFECT_COMMIT", "NO_UNVERIFIED_OUTPUT_PROMOTION", "SAFE_TERMINAL_OR_RECOVERED",
})
ALLOWED_TERMINAL_ACTIONS = frozenset({
    "SAFE_ABSTAIN", "SAFE_FALLBACK", "SAFE_STOP", "RECOVERED", "REJECT", "IDEMPOTENT_NOOP",
})


class FaultInjectionSpecError(RuntimeError):
    pass


def _safe_repo_file(root: Path, value: Path) -> tuple[Path, str]:
    candidate = value if value.is_absolute() else root / value
    if candidate.is_symlink():
        raise FaultInjectionSpecError("fault spec symlink rejected")
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise FaultInjectionSpecError("fault spec path escapes repository") from exc
    if not resolved.is_file():
        raise FaultInjectionSpecError("fault spec must be a regular file")
    return resolved, rel.as_posix()


def load_fault_spec(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise FaultInjectionSpecError("fault spec must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FaultInjectionSpecError("invalid fault spec JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SPEC_SCHEMA:
        raise FaultInjectionSpecError("unexpected fault spec schema")
    if doc.get("outcomes_observed") is not False or doc.get("policy_retuning_allowed") is not False:
        raise FaultInjectionSpecError("fault spec must be frozen pre-outcome with no retuning")
    cases = doc.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FaultInjectionSpecError("fault spec requires cases")
    case_ids: set[str] = set()
    classes: set[str] = set()
    for row in cases:
        if not isinstance(row, Mapping):
            raise FaultInjectionSpecError("malformed fault case")
        case_id = str(row.get("case_id", "")).strip()
        fault_class = str(row.get("fault_class", "")).strip()
        injection_point = str(row.get("injection_point", "")).strip()
        terminals = row.get("expected_terminal_actions")
        if not case_id or case_id in case_ids or not fault_class or not injection_point:
            raise FaultInjectionSpecError("fault case identity must be unique and complete")
        if not isinstance(terminals, list) or not terminals:
            raise FaultInjectionSpecError("fault case requires expected terminal actions")
        terminal_set = {str(value) for value in terminals}
        if not terminal_set <= ALLOWED_TERMINAL_ACTIONS:
            raise FaultInjectionSpecError("fault case contains unknown terminal action")
        case_ids.add(case_id)
        classes.add(fault_class)
    if classes != REQUIRED_FAULT_CLASSES:
        raise FaultInjectionSpecError("fault spec must contain exact required fault-class population")
    invariants = doc.get("global_invariants")
    if not isinstance(invariants, list) or set(str(value) for value in invariants) != REQUIRED_GLOBAL_INVARIANTS:
        raise FaultInjectionSpecError("fault spec global invariant population mismatch")
    return doc


def semantic_fault_spec_digest(doc: Mapping[str, object]) -> str:
    payload = {
        "cases": doc["cases"],
        "global_invariants": doc["global_invariants"],
        "policy_retuning_allowed": doc["policy_retuning_allowed"],
        "outcomes_observed": doc["outcomes_observed"],
    }
    return sha256_bytes(canonical_json_bytes(payload))


@dataclass(frozen=True, slots=True)
class FaultInjectionSpecAuthority:
    family_id: str
    repository_commit: str
    repository_tree: str
    execution_manifest_freeze_digest: str
    generalization_registry_digest: str
    fault_spec_path: str
    fault_spec_sha256: str
    fault_spec_semantic_digest: str
    case_count: int
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": AUTHORITY_SCHEMA,
            **asdict(self),
            "outcomes_observed": False,
            "fault_execution_authorized": True,
            "product_promotion_authorized": False,
        }


def build_fault_injection_spec_authority(
    *,
    repository_root: Path,
    fault_spec_path: Path,
    execution_manifest_freeze_path: Path,
    generalization_registry_path: Path,
) -> FaultInjectionSpecAuthority:
    root = Path(repository_root).resolve()
    spec_path, rel = _safe_repo_file(root, Path(fault_spec_path))
    spec = load_fault_spec(spec_path)
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    generalization = verify_generalization_registry_document(Path(generalization_registry_path))
    if execution.get("family_id") != generalization.get("family_id"):
        raise FaultInjectionSpecError("fault preregistration upstream family mismatch")
    if generalization.get("execution_manifest_freeze_digest") != execution.get("freeze_digest"):
        raise FaultInjectionSpecError("fault preregistration lost execution/generalization lineage")
    payload = {
        "family_id": str(execution["family_id"]),
        "repository_commit": str(execution["repository_commit"]),
        "repository_tree": str(execution["repository_tree"]),
        "execution_manifest_freeze_digest": str(execution["freeze_digest"]),
        "generalization_registry_digest": str(generalization["registry_digest"]),
        "fault_spec_path": rel,
        "fault_spec_sha256": sha256_file(spec_path),
        "fault_spec_semantic_digest": semantic_fault_spec_digest(spec),
        "case_count": len(spec["cases"]),
    }
    return FaultInjectionSpecAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_fault_injection_spec_authority_document(
    path: Path,
    *,
    repository_root: Path | None = None,
) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise FaultInjectionSpecError("fault spec authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FaultInjectionSpecError("invalid fault spec authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != AUTHORITY_SCHEMA:
        raise FaultInjectionSpecError("unexpected fault spec authority schema")
    if doc.get("outcomes_observed") is not False or doc.get("fault_execution_authorized") is not True:
        raise FaultInjectionSpecError("fault spec authority temporal boundary malformed")
    if doc.get("product_promotion_authorized") is not False:
        raise FaultInjectionSpecError("fault spec authority cannot promote product")
    keys = (
        "family_id", "repository_commit", "repository_tree", "execution_manifest_freeze_digest",
        "generalization_registry_digest", "fault_spec_path", "fault_spec_sha256",
        "fault_spec_semantic_digest", "case_count",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise FaultInjectionSpecError("fault spec authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != str(doc.get("authority_digest", "")):
        raise FaultInjectionSpecError("fault spec authority digest mismatch")
    if int(doc.get("case_count", 0)) != len(REQUIRED_FAULT_CLASSES):
        raise FaultInjectionSpecError("fault spec authority case count mismatch")
    if repository_root is not None:
        root = Path(repository_root).resolve()
        spec_path, rel = _safe_repo_file(root, Path(str(doc["fault_spec_path"])))
        if rel != doc.get("fault_spec_path") or sha256_file(spec_path) != doc.get("fault_spec_sha256"):
            raise FaultInjectionSpecError("fault spec bytes changed after freeze")
        spec = load_fault_spec(spec_path)
        if semantic_fault_spec_digest(spec) != doc.get("fault_spec_semantic_digest"):
            raise FaultInjectionSpecError("fault spec semantics changed after freeze")
    return doc
