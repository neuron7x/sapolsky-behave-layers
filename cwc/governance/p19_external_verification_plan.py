from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verification_contract import (
    CHECK_METHOD_IDS,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_external_verifier_activation import (
    verify_p19_external_verifier_activation_authority_document,
)
from cwc.governance.p19_external_verifier_regression import current_runtime_digest, current_test_manifest_digest
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS

SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_PLAN_V4"
PLAN_GENERATION = "PRE_OUTCOME_EXTERNAL_VERIFICATION_PLAN_V4_DUAL_SIGNED_REGRESSION_ACTIVATION"
CANONICAL_PLAN_PATH = "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V4.json"
ENTRYPOINT = VERIFIER_ENTRYPOINT
REQUIRED_IMPLEMENTATION_DEPENDENCIES = VERIFIER_RUNTIME_DEPENDENCIES


class P19ExternalVerificationPlanError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerificationPlanError(f"{name} must be lowercase SHA-256")
    return text


def _git_oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerificationPlanError(f"{name} must be lowercase 40-hex Git OID")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if (
        not text
        or text != text.strip()
        or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\"))
        or "//" in text
    ):
        raise P19ExternalVerificationPlanError(f"{label} must be canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts) or rel.as_posix() != text:
        raise P19ExternalVerificationPlanError(f"{label} must be canonical repository-relative POSIX path")
    return text


def _required_regular_file(root: Path, rel: str, *, label: str) -> Path:
    normalized = _safe_rel(rel, label=label)
    path = root / normalized
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
        raise P19ExternalVerificationPlanError(f"{label} missing/invalid")
    resolved = path.resolve()
    try:
        observed_rel = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise P19ExternalVerificationPlanError(f"{label} escapes repository") from exc
    if observed_rel != normalized:
        raise P19ExternalVerificationPlanError(f"{label} resolves through a non-canonical alias/symlink")
    return resolved


def _repo_rel(root: Path, value: Path, *, label: str) -> tuple[Path, str]:
    source = Path(value)
    if source.is_absolute():
        resolved = source.resolve()
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise P19ExternalVerificationPlanError(f"{label} escapes repository") from exc
        rel = _safe_rel(rel, label=label)
    else:
        rel = _safe_rel(source.as_posix(), label=label)
        resolved = _required_regular_file(root, rel, label=label)
    if resolved.is_symlink() or not resolved.is_file() or resolved.stat().st_size <= 0:
        raise P19ExternalVerificationPlanError(f"{label} missing/invalid")
    return resolved, rel


def _runtime_bindings(root: Path) -> tuple[Path, list[dict[str, object]], str]:
    entry = _required_regular_file(root, ENTRYPOINT, label="external verification entrypoint")
    dependencies: list[dict[str, object]] = []
    for rel in REQUIRED_IMPLEMENTATION_DEPENDENCIES:
        path = _required_regular_file(root, rel, label=f"external verifier dependency {rel}")
        dependencies.append({
            "path": rel,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
    dependency_digest = sha256_bytes(canonical_json_bytes(dependencies))
    return entry, dependencies, dependency_digest


def _contracts() -> list[dict[str, object]]:
    return [
        {
            "check_id": check_id,
            "method_id": CHECK_METHOD_IDS[check_id],
            "command_template": [
                "python", ENTRYPOINT, "--check-id", check_id,
                "--p19", "{P19_PATH}", "--evidence-output", "{EVIDENCE_PATH}",
            ],
            "implementation_status": "IMPLEMENTED",
        }
        for check_id in sorted(REQUIRED_CHECKS)
    ]


def _activation_payload(root: Path, activation_authority_path: Path) -> dict[str, object]:
    authority_file, authority_rel = _repo_rel(root, activation_authority_path, label="verifier activation authority")
    try:
        authority = verify_p19_external_verifier_activation_authority_document(
            authority_file,
            repository_root=root,
        )
    except RuntimeError as exc:
        raise P19ExternalVerificationPlanError("active Plan V4 activation-authority replay failed") from exc
    if authority.get("activation_authorized") is not True or authority.get("all_signatures_verified") is not True:
        raise P19ExternalVerificationPlanError("verifier activation authority is not supported")
    principals = authority.get("verifier_principals")
    key_digests = authority.get("signer_key_digests")
    if not isinstance(principals, list) or not isinstance(key_digests, list) or len(principals) < 2 or len(key_digests) < 2:
        raise P19ExternalVerificationPlanError("verifier activation authority lacks dual independent signers")
    if len(set(map(str, principals))) != len(principals) or len(set(map(str, key_digests))) != len(key_digests):
        raise P19ExternalVerificationPlanError("verifier activation authority signer population is not distinct")
    if authority.get("runtime_manifest_digest") != current_runtime_digest(root):
        raise P19ExternalVerificationPlanError("activation authority runtime no longer matches current verifier")
    if authority.get("test_manifest_digest") != current_test_manifest_digest(root):
        raise P19ExternalVerificationPlanError("activation authority tests no longer match current canonical suite")
    return {
        "activation_authority_path": authority_rel,
        "activation_authority_sha256": sha256_file(authority_file),
        "activation_authority_digest": _sha("activation authority digest", authority.get("authority_digest")),
        "activation_trust_policy_path": _safe_rel(authority.get("trust_policy_path"), label="activation trust policy"),
        "activation_trust_policy_digest": _sha("activation trust policy digest", authority.get("trust_policy_digest")),
        "activation_verifier_principals": [str(value) for value in principals],
        "activation_signer_key_digests": [_sha("activation signer key digest", value) for value in key_digests],
        "activation_regression_receipt_path": _safe_rel(authority.get("regression_receipt_path"), label="activation regression receipt"),
        "activation_regression_receipt_sha256": _sha("activation regression receipt sha256", authority.get("regression_receipt_sha256")),
        "activation_regression_receipt_digest": _sha("activation regression receipt digest", authority.get("regression_receipt_digest")),
        "activation_regression_source_commit": _git_oid("activation regression source commit", authority.get("source_commit")),
        "activation_regression_source_tree": _git_oid("activation regression source tree", authority.get("source_tree")),
        "activation_regression_test_manifest_digest": _sha("activation regression test manifest digest", authority.get("test_manifest_digest")),
    }


def _empty_activation() -> dict[str, object]:
    return {
        "activation_authority_path": None,
        "activation_authority_sha256": None,
        "activation_authority_digest": None,
        "activation_trust_policy_path": None,
        "activation_trust_policy_digest": None,
        "activation_verifier_principals": [],
        "activation_signer_key_digests": [],
        "activation_regression_receipt_path": None,
        "activation_regression_receipt_sha256": None,
        "activation_regression_receipt_digest": None,
        "activation_regression_source_commit": None,
        "activation_regression_source_tree": None,
        "activation_regression_test_manifest_digest": None,
    }


def _build_plan_document(
    *,
    repository_root: Path,
    active: bool,
    activation_authority_path: Path | None,
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    entry, dependencies, dependency_digest = _runtime_bindings(root)
    activation = _empty_activation()
    if active:
        if activation_authority_path is None:
            raise P19ExternalVerificationPlanError("active Plan V4 requires dual-signed activation authority")
        activation = _activation_payload(root, activation_authority_path)
    elif activation_authority_path is not None:
        raise P19ExternalVerificationPlanError("inactive Plan V4 cannot carry activation authority")

    payload = {
        "plan_generation": PLAN_GENERATION,
        "frozen_pre_outcome": True,
        "activation_authorized": active,
        "activation_evidence_requirement": "DUAL_EXTERNAL_SSH_SIGNED_GIT_BOUND_CANONICAL_REGRESSION_V1",
        "verifier_entrypoint_path": ENTRYPOINT,
        "verifier_entrypoint_sha256": sha256_file(entry),
        "verifier_dependency_manifest_digest": dependency_digest,
        "verifier_dependencies": dependencies,
        "check_contracts": _contracts(),
        "all_check_implementations_complete": True,
        **activation,
        "product_qualification_authorized": False,
    }
    return {
        "schema": SCHEMA,
        **payload,
        "plan_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def build_inactive_p19_external_verification_plan_document(
    *,
    repository_root: Path,
    implemented_check_ids: Sequence[str],
) -> dict[str, object]:
    declared = tuple(str(value) for value in implemented_check_ids)
    if len(declared) != len(set(declared)) or set(declared) != REQUIRED_CHECKS:
        raise P19ExternalVerificationPlanError(
            "inactive Plan V4 builder requires exact unique implemented check population"
        )
    return _build_plan_document(repository_root=repository_root, active=False, activation_authority_path=None)


def build_activated_p19_external_verification_plan_document(
    *,
    repository_root: Path,
    activation_authority_path: Path,
) -> dict[str, object]:
    return _build_plan_document(
        repository_root=repository_root,
        active=True,
        activation_authority_path=activation_authority_path,
    )


@dataclass(frozen=True, slots=True)
class P19ExternalVerificationPlan:
    plan_generation: str
    frozen_pre_outcome: bool
    activation_authorized: bool
    activation_evidence_requirement: str
    verifier_entrypoint_path: str
    verifier_entrypoint_sha256: str
    verifier_dependency_manifest_digest: str
    verifier_dependencies: tuple[dict[str, object], ...]
    check_contracts: tuple[dict[str, object], ...]
    all_check_implementations_complete: bool
    activation_authority_path: str | None
    activation_authority_sha256: str | None
    activation_authority_digest: str | None
    activation_trust_policy_path: str | None
    activation_trust_policy_digest: str | None
    activation_verifier_principals: tuple[str, ...]
    activation_signer_key_digests: tuple[str, ...]
    activation_regression_receipt_path: str | None
    activation_regression_receipt_sha256: str | None
    activation_regression_receipt_digest: str | None
    activation_regression_source_commit: str | None
    activation_regression_source_tree: str | None
    activation_regression_test_manifest_digest: str | None
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
        path = _required_regular_file(root, rel, label="external verifier dependency")
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
    resolved_source = source.resolve()
    try:
        resolved_source.relative_to(root)
    except ValueError as exc:
        raise P19ExternalVerificationPlanError("external verification plan escapes repository") from exc
    try:
        raw = resolved_source.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19ExternalVerificationPlanError("invalid external verification plan JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19ExternalVerificationPlanError("unexpected external verification plan schema")
    if raw != canonical_json_bytes(doc) + b"\n":
        raise P19ExternalVerificationPlanError("external verification plan must use canonical JSON bytes")

    payload_keys = (
        "plan_generation", "frozen_pre_outcome", "activation_authorized", "activation_evidence_requirement",
        "verifier_entrypoint_path", "verifier_entrypoint_sha256",
        "verifier_dependency_manifest_digest", "verifier_dependencies", "check_contracts",
        "all_check_implementations_complete", "activation_authority_path", "activation_authority_sha256",
        "activation_authority_digest", "activation_trust_policy_path", "activation_trust_policy_digest",
        "activation_verifier_principals", "activation_signer_key_digests",
        "activation_regression_receipt_path", "activation_regression_receipt_sha256",
        "activation_regression_receipt_digest", "activation_regression_source_commit",
        "activation_regression_source_tree", "activation_regression_test_manifest_digest",
        "product_qualification_authorized",
    )
    try:
        payload = {key: doc[key] for key in payload_keys}
    except KeyError as exc:
        raise P19ExternalVerificationPlanError("external verification plan payload incomplete") from exc
    digest = _sha("plan_digest", doc.get("plan_digest"))
    if sha256_bytes(canonical_json_bytes(payload)) != digest:
        raise P19ExternalVerificationPlanError("external verification plan digest mismatch")
    if doc.get("plan_generation") != PLAN_GENERATION:
        raise P19ExternalVerificationPlanError("external verification plan generation mismatch")
    if doc.get("activation_evidence_requirement") != "DUAL_EXTERNAL_SSH_SIGNED_GIT_BOUND_CANONICAL_REGRESSION_V1":
        raise P19ExternalVerificationPlanError("external verification activation evidence requirement mismatch")
    if doc.get("frozen_pre_outcome") is not True:
        raise P19ExternalVerificationPlanError("external verification plan must be frozen pre-outcome")
    if doc.get("product_qualification_authorized") is not False:
        raise P19ExternalVerificationPlanError("verification plan cannot itself authorize product qualification")

    entry_rel = _safe_rel(doc.get("verifier_entrypoint_path"), label="verifier entrypoint")
    if entry_rel != ENTRYPOINT:
        raise P19ExternalVerificationPlanError("external verification entrypoint differs from canonical path")
    entry = _required_regular_file(root, entry_rel, label="external verification entrypoint")
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
        if method_id != CHECK_METHOD_IDS[check_id]:
            raise P19ExternalVerificationPlanError(f"external verification method identity mismatch: {check_id}")
        if template != expected_template:
            raise P19ExternalVerificationPlanError(f"external verification command template mismatch: {check_id}")
        if status != "IMPLEMENTED":
            raise P19ExternalVerificationPlanError(f"external verification implementation incomplete: {check_id}")
        normalized.append({
            "check_id": check_id,
            "method_id": method_id,
            "command_template": list(template),
            "implementation_status": status,
        })
    normalized.sort(key=lambda row: str(row["check_id"]))
    if seen != REQUIRED_CHECKS or rows != normalized:
        raise P19ExternalVerificationPlanError("external verification contract population/order differs from canonical SSOT")
    complete = True
    if doc.get("all_check_implementations_complete") is not True:
        raise P19ExternalVerificationPlanError("external verification implementation-completeness flag mismatch")

    active = doc.get("activation_authorized") is True
    activation_fields = tuple(_empty_activation().keys())
    if active:
        authority_rel = _safe_rel(doc.get("activation_authority_path"), label="activation authority")
        authority_path = _required_regular_file(root, authority_rel, label="activation authority")
        if sha256_file(authority_path) != _sha("activation authority sha256", doc.get("activation_authority_sha256")):
            raise P19ExternalVerificationPlanError("activation authority bytes differ from plan")
        try:
            authority = verify_p19_external_verifier_activation_authority_document(authority_path, repository_root=root)
        except RuntimeError as exc:
            raise P19ExternalVerificationPlanError("activation authority signature replay failed") from exc
        expected = _activation_payload(root, authority_path)
        for field, value in expected.items():
            if doc.get(field) != value:
                raise P19ExternalVerificationPlanError(f"activation authority lineage differs from plan: {field}")
    else:
        empty = _empty_activation()
        for field in activation_fields:
            if doc.get(field) != empty[field]:
                raise P19ExternalVerificationPlanError("inactive verification plan cannot carry activation evidence")
    if require_active and not active:
        raise P19ExternalVerificationPlanError("external verification plan is not activated")

    return P19ExternalVerificationPlan(
        plan_generation=PLAN_GENERATION,
        frozen_pre_outcome=True,
        activation_authorized=active,
        activation_evidence_requirement=str(doc["activation_evidence_requirement"]),
        verifier_entrypoint_path=entry_rel,
        verifier_entrypoint_sha256=entry_sha,
        verifier_dependency_manifest_digest=dependency_digest,
        verifier_dependencies=dependencies,
        check_contracts=tuple(normalized),
        all_check_implementations_complete=complete,
        activation_authority_path=(str(doc["activation_authority_path"]) if active else None),
        activation_authority_sha256=(str(doc["activation_authority_sha256"]) if active else None),
        activation_authority_digest=(str(doc["activation_authority_digest"]) if active else None),
        activation_trust_policy_path=(str(doc["activation_trust_policy_path"]) if active else None),
        activation_trust_policy_digest=(str(doc["activation_trust_policy_digest"]) if active else None),
        activation_verifier_principals=(tuple(str(v) for v in doc["activation_verifier_principals"]) if active else ()),
        activation_signer_key_digests=(tuple(str(v) for v in doc["activation_signer_key_digests"]) if active else ()),
        activation_regression_receipt_path=(str(doc["activation_regression_receipt_path"]) if active else None),
        activation_regression_receipt_sha256=(str(doc["activation_regression_receipt_sha256"]) if active else None),
        activation_regression_receipt_digest=(str(doc["activation_regression_receipt_digest"]) if active else None),
        activation_regression_source_commit=(str(doc["activation_regression_source_commit"]) if active else None),
        activation_regression_source_tree=(str(doc["activation_regression_source_tree"]) if active else None),
        activation_regression_test_manifest_digest=(str(doc["activation_regression_test_manifest_digest"]) if active else None),
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
