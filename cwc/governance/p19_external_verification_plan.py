from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS

SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_PLAN_V2"
CANONICAL_PLAN_PATH = "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V2.json"
ENTRYPOINT = "scripts/dgc_external_p19_verifier.py"
REQUIRED_IMPLEMENTATION_DEPENDENCIES = (
    "cwc/governance/p19_external_replay.py",
)


class P19ExternalVerificationPlanError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerificationPlanError(f"{name} must be lowercase SHA-256")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if not text or text != text.strip() or text.startswith("/") or ".." in Path(text).parts or "\\" in text:
        raise P19ExternalVerificationPlanError(f"{label} must be canonical repository-relative path")
    return text


@dataclass(frozen=True, slots=True)
class P19ExternalVerificationPlan:
    plan_generation: str
    frozen_pre_outcome: bool
    activation_authorized: bool
    verifier_entrypoint_path: str
    verifier_entrypoint_sha256: str
    verifier_dependency_manifest_digest: str
    verifier_dependencies: tuple[dict[str, object], ...]
    check_contracts: tuple[dict[str, object], ...]
    all_check_implementations_complete: bool
    product_qualification_authorized: bool
    plan_digest: str

    def contract(self, check_id: str) -> Mapping[str, object]:
        matches = [row for row in self.check_contracts if row.get("check_id") == check_id]
        if len(matches) != 1:
            raise P19ExternalVerificationPlanError(f"missing/duplicate verification contract: {check_id}")
        return matches[0]


def _verify_dependencies(root: Path, rows: object) -> tuple[dict[str, object], ...]:
    if not isinstance(rows, list) or len(rows) != len(REQUIRED_IMPLEMENTATION_DEPENDENCIES):
        raise P19ExternalVerificationPlanError("external verifier dependency population incomplete")
    normalized: list[dict[str, object]] = []
    for expected, row in zip(REQUIRED_IMPLEMENTATION_DEPENDENCIES, rows, strict=True):
        if not isinstance(row, Mapping):
            raise P19ExternalVerificationPlanError("external verifier dependency row malformed")
        rel = _safe_rel(row.get("path"), label="verifier dependency")
        if rel != expected:
            raise P19ExternalVerificationPlanError("external verifier dependency path differs from canonical manifest")
        path = root / rel
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise P19ExternalVerificationPlanError("external verifier dependency missing/invalid")
        digest = _sha("verifier dependency sha256", row.get("sha256"))
        size = int(row.get("bytes", -1))
        if size <= 0 or path.stat().st_size != size or sha256_file(path) != digest:
            raise P19ExternalVerificationPlanError("external verifier dependency bytes differ from frozen plan")
        normalized.append({"path": rel, "sha256": digest, "bytes": size})
    return tuple(normalized)


def load_p19_external_verification_plan(
    path: Path,
    *,
    repository_root: Path,
    require_active: bool = True,
) -> P19ExternalVerificationPlan:
    root = Path(repository_root).resolve()
    source = Path(path)
    if not source.is_absolute():
        source = root / source
    if source.is_symlink() or not source.is_file():
        raise P19ExternalVerificationPlanError("external verification plan must be a regular non-symlink file")
    try:
        raw = source.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19ExternalVerificationPlanError("invalid external verification plan JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19ExternalVerificationPlanError("unexpected external verification plan schema")
    if raw != canonical_json_bytes(doc) + b"\n":
        raise P19ExternalVerificationPlanError("external verification plan must use canonical JSON bytes")

    payload_keys = (
        "plan_generation", "frozen_pre_outcome", "activation_authorized",
        "verifier_entrypoint_path", "verifier_entrypoint_sha256",
        "verifier_dependency_manifest_digest", "verifier_dependencies", "check_contracts",
        "all_check_implementations_complete", "product_qualification_authorized",
    )
    try:
        payload = {key: doc[key] for key in payload_keys}
    except KeyError as exc:
        raise P19ExternalVerificationPlanError("external verification plan payload incomplete") from exc
    digest = _sha("plan_digest", doc.get("plan_digest"))
    if sha256_bytes(canonical_json_bytes(payload)) != digest:
        raise P19ExternalVerificationPlanError("external verification plan digest mismatch")
    if doc.get("frozen_pre_outcome") is not True:
        raise P19ExternalVerificationPlanError("external verification plan must be frozen pre-outcome")
    if doc.get("product_qualification_authorized") is not False:
        raise P19ExternalVerificationPlanError("verification plan cannot itself authorize product qualification")

    entry_rel = _safe_rel(doc.get("verifier_entrypoint_path"), label="verifier entrypoint")
    if entry_rel != ENTRYPOINT:
        raise P19ExternalVerificationPlanError("external verification entrypoint differs from canonical path")
    entry = root / entry_rel
    if entry.is_symlink() or not entry.is_file() or entry.stat().st_size <= 0:
        raise P19ExternalVerificationPlanError("external verification entrypoint missing/invalid")
    entry_sha = _sha("verifier_entrypoint_sha256", doc.get("verifier_entrypoint_sha256"))
    if sha256_file(entry) != entry_sha:
        raise P19ExternalVerificationPlanError("external verification entrypoint bytes differ from frozen plan")

    dependencies = _verify_dependencies(root, doc.get("verifier_dependencies"))
    dependency_digest = _sha("verifier_dependency_manifest_digest", doc.get("verifier_dependency_manifest_digest"))
    if sha256_bytes(canonical_json_bytes(list(dependencies))) != dependency_digest:
        raise P19ExternalVerificationPlanError("external verifier dependency manifest digest mismatch")

    rows = doc.get("check_contracts")
    if not isinstance(rows, list) or len(rows) != len(REQUIRED_CHECKS):
        raise P19ExternalVerificationPlanError("external verification contract population incomplete")
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise P19ExternalVerificationPlanError("external verification contract row malformed")
        check_id = str(row.get("check_id", "")).strip()
        if check_id not in REQUIRED_CHECKS or check_id in seen:
            raise P19ExternalVerificationPlanError("external verification contract check population invalid")
        seen.add(check_id)
        method_id = str(row.get("method_id", "")).strip()
        template = row.get("command_template")
        status = str(row.get("implementation_status", "")).strip()
        expected_template = [
            "python", ENTRYPOINT, "--check-id", check_id,
            "--p19", "{P19_PATH}", "--evidence-output", "{EVIDENCE_PATH}",
        ]
        if not method_id or template != expected_template:
            raise P19ExternalVerificationPlanError(f"external verification command template mismatch: {check_id}")
        if status not in {"IMPLEMENTED", "NOT_IMPLEMENTED"}:
            raise P19ExternalVerificationPlanError(f"external verification implementation status invalid: {check_id}")
        normalized.append({
            "check_id": check_id,
            "method_id": method_id,
            "command_template": list(template),
            "implementation_status": status,
        })
    if seen != REQUIRED_CHECKS:
        raise P19ExternalVerificationPlanError("external verification contract set differs from required checks")
    normalized.sort(key=lambda row: str(row["check_id"]))
    if rows != normalized:
        raise P19ExternalVerificationPlanError("external verification contracts must be canonically ordered")

    complete = all(row["implementation_status"] == "IMPLEMENTED" for row in normalized)
    if bool(doc.get("all_check_implementations_complete")) != complete:
        raise P19ExternalVerificationPlanError("external verification implementation-completeness flag mismatch")
    active = doc.get("activation_authorized") is True
    if active and not complete:
        raise P19ExternalVerificationPlanError("external verification plan cannot activate with incomplete checks")
    if require_active and not active:
        raise P19ExternalVerificationPlanError("external verification plan is not activated")

    return P19ExternalVerificationPlan(
        plan_generation=str(doc.get("plan_generation", "")),
        frozen_pre_outcome=True,
        activation_authorized=active,
        verifier_entrypoint_path=entry_rel,
        verifier_entrypoint_sha256=entry_sha,
        verifier_dependency_manifest_digest=dependency_digest,
        verifier_dependencies=dependencies,
        check_contracts=tuple(normalized),
        all_check_implementations_complete=complete,
        product_qualification_authorized=False,
        plan_digest=digest,
    )


def expected_command_argv(
    plan: P19ExternalVerificationPlan,
    *,
    check_id: str,
    p19_path: str,
    evidence_path: str,
) -> tuple[str, ...]:
    row = plan.contract(check_id)
    if row.get("implementation_status") != "IMPLEMENTED":
        raise P19ExternalVerificationPlanError(f"external verification check not implemented: {check_id}")
    return (
        "python", plan.verifier_entrypoint_path, "--check-id", check_id,
        "--p19", _safe_rel(p19_path, label="P19 path"),
        "--evidence-output", _safe_rel(evidence_path, label="verification evidence path"),
    )


def verify_command_against_plan(
    plan: P19ExternalVerificationPlan,
    *,
    check_id: str,
    command_argv: Sequence[str],
    p19_path: str,
    evidence_path: str,
) -> None:
    expected = expected_command_argv(
        plan,
        check_id=check_id,
        p19_path=p19_path,
        evidence_path=evidence_path,
    )
    if tuple(command_argv) != expected:
        raise P19ExternalVerificationPlanError(f"verification command differs from frozen plan: {check_id}")
