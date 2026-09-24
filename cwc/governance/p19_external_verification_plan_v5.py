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
from cwc.governance.p19_external_verification_plan import (
    build_inactive_p19_external_verification_plan_document as build_v4_inactive_plan,
)
from cwc.governance.p19_external_verifier_activation_v2 import (
    SIGNATURE_SEMANTICS,
    verify_p19_external_verifier_activation_authority_v2_document,
)
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS

SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_PLAN_V5"
PLAN_GENERATION = "PRE_OUTCOME_EXTERNAL_VERIFICATION_PLAN_V5_PORTABLE_ACTIVATION_V2"
CANONICAL_PLAN_PATH = "artifacts/dgc-product-v1/P19_EXTERNAL_VERIFICATION_PLAN_V5.json"
ENTRYPOINT = VERIFIER_ENTRYPOINT
REQUIRED_IMPLEMENTATION_DEPENDENCIES = VERIFIER_RUNTIME_DEPENDENCIES
ACTIVATION_EVIDENCE_REQUIREMENT = "PORTABLE_DUAL_EXTERNAL_SSH_SIGNED_GIT_BOUND_CANONICAL_REGRESSION_V2"


class P19ExternalVerificationPlanV5Error(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerificationPlanV5Error(f"{name} must be lowercase SHA-256")
    return text


def _oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerificationPlanV5Error(f"{name} must be lowercase 40-hex Git OID")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if (
        not text
        or text != text.strip()
        or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\"))
        or "//" in text
    ):
        raise P19ExternalVerificationPlanV5Error(f"{label} must be canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts) or rel.as_posix() != text:
        raise P19ExternalVerificationPlanV5Error(f"{label} must be canonical repository-relative POSIX path")
    return text


def _repo_file(root: Path, value: Path | str, *, label: str) -> tuple[Path, str]:
    source = Path(value)
    if source.is_absolute():
        resolved = source.resolve()
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise P19ExternalVerificationPlanV5Error(f"{label} escapes repository") from exc
        rel = _safe_rel(rel, label=label)
    else:
        rel = _safe_rel(source.as_posix(), label=label)
        resolved = (root / rel).resolve()
    candidate = root / rel
    if candidate.is_symlink() or not resolved.is_file() or resolved.stat().st_size <= 0:
        raise P19ExternalVerificationPlanV5Error(f"{label} must be a non-empty regular non-symlink file")
    try:
        observed = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise P19ExternalVerificationPlanV5Error(f"{label} escapes repository") from exc
    if observed != rel:
        raise P19ExternalVerificationPlanV5Error(f"{label} resolves through a non-canonical alias")
    return resolved, rel


def _empty_activation() -> dict[str, object]:
    return {
        "activation_authority_path": None,
        "activation_authority_sha256": None,
        "activation_authority_digest": None,
        "activation_trust_policy_path": None,
        "activation_trust_policy_digest": None,
        "activation_allowed_signers_sha256": None,
        "activation_verifier_principals": [],
        "activation_signer_key_digests": [],
        "activation_regression_receipt_path": None,
        "activation_regression_receipt_sha256": None,
        "activation_regression_receipt_digest": None,
        "activation_regression_source_commit": None,
        "activation_regression_source_tree": None,
        "activation_regression_test_manifest_digest": None,
        "activation_signature_semantics": None,
        "activation_signature_tool_execution_provenance_authoritative": False,
    }


def _current_core(root: Path) -> dict[str, object]:
    v4 = build_v4_inactive_plan(
        repository_root=root,
        implemented_check_ids=tuple(sorted(REQUIRED_CHECKS)),
    )
    return {
        "verifier_entrypoint_path": str(v4["verifier_entrypoint_path"]),
        "verifier_entrypoint_sha256": _sha("verifier_entrypoint_sha256", v4["verifier_entrypoint_sha256"]),
        "verifier_dependency_manifest_digest": _sha(
            "verifier_dependency_manifest_digest", v4["verifier_dependency_manifest_digest"]
        ),
        "verifier_dependencies": list(v4["verifier_dependencies"]),
        "check_contracts": list(v4["check_contracts"]),
        "all_check_implementations_complete": True,
    }


def _activation_payload(root: Path, authority_value: Path) -> dict[str, object]:
    authority_file, authority_rel = _repo_file(root, authority_value, label="portable verifier activation authority V2")
    try:
        authority = verify_p19_external_verifier_activation_authority_v2_document(
            authority_file,
            repository_root=root,
        )
    except RuntimeError as exc:
        raise P19ExternalVerificationPlanV5Error("portable activation V2 replay failed") from exc
    if authority.get("activation_authorized") is not True or authority.get("all_signatures_verified") is not True:
        raise P19ExternalVerificationPlanV5Error("portable activation V2 is unsupported")
    if authority.get("signature_semantics") != SIGNATURE_SEMANTICS:
        raise P19ExternalVerificationPlanV5Error("portable activation signature semantics mismatch")
    if authority.get("signature_tool_execution_provenance_authoritative") is not False:
        raise P19ExternalVerificationPlanV5Error("machine-local signature-tool provenance cannot define Plan V5 activation")
    principals = authority.get("verifier_principals")
    key_digests = authority.get("signer_key_digests")
    if not isinstance(principals, list) or not isinstance(key_digests, list) or len(principals) < 2 or len(key_digests) < 2:
        raise P19ExternalVerificationPlanV5Error("portable activation lacks distinct verifier/key population")
    if len(set(map(str, principals))) != len(principals) or len(set(map(str, key_digests))) != len(key_digests):
        raise P19ExternalVerificationPlanV5Error("portable activation verifier/key population is not unique")
    return {
        "activation_authority_path": authority_rel,
        "activation_authority_sha256": sha256_file(authority_file),
        "activation_authority_digest": _sha("activation_authority_digest", authority.get("authority_digest")),
        "activation_trust_policy_path": _safe_rel(authority.get("trust_policy_path"), label="activation trust policy"),
        "activation_trust_policy_digest": _sha("activation_trust_policy_digest", authority.get("trust_policy_digest")),
        "activation_allowed_signers_sha256": _sha("activation_allowed_signers_sha256", authority.get("allowed_signers_sha256")),
        "activation_verifier_principals": [str(value) for value in principals],
        "activation_signer_key_digests": [_sha("activation signer key digest", value) for value in key_digests],
        "activation_regression_receipt_path": _safe_rel(authority.get("regression_receipt_path"), label="activation regression receipt"),
        "activation_regression_receipt_sha256": _sha("activation regression receipt sha256", authority.get("regression_receipt_sha256")),
        "activation_regression_receipt_digest": _sha("activation regression receipt digest", authority.get("regression_receipt_digest")),
        "activation_regression_source_commit": _oid("activation regression source commit", authority.get("source_commit")),
        "activation_regression_source_tree": _oid("activation regression source tree", authority.get("source_tree")),
        "activation_regression_test_manifest_digest": _sha(
            "activation regression test manifest digest", authority.get("test_manifest_digest")
        ),
        "activation_signature_semantics": SIGNATURE_SEMANTICS,
        "activation_signature_tool_execution_provenance_authoritative": False,
    }


def _build_document(*, repository_root: Path, active: bool, activation_authority_path: Path | None) -> dict[str, object]:
    root = Path(repository_root).resolve()
    core = _current_core(root)
    if core["verifier_entrypoint_path"] != ENTRYPOINT:
        raise P19ExternalVerificationPlanV5Error("current verifier entrypoint differs from Plan V5 contract")
    contracts = core["check_contracts"]
    if not isinstance(contracts, list) or {str(row.get("check_id")) for row in contracts if isinstance(row, Mapping)} != REQUIRED_CHECKS:
        raise P19ExternalVerificationPlanV5Error("current check population differs from Plan V5 contract")
    activation = _empty_activation()
    if active:
        if activation_authority_path is None:
            raise P19ExternalVerificationPlanV5Error("active Plan V5 requires portable Activation V2 authority")
        activation = _activation_payload(root, activation_authority_path)
    elif activation_authority_path is not None:
        raise P19ExternalVerificationPlanV5Error("inactive Plan V5 cannot carry activation authority")
    payload = {
        "plan_generation": PLAN_GENERATION,
        "frozen_pre_outcome": True,
        "activation_authorized": bool(active),
        "activation_evidence_requirement": ACTIVATION_EVIDENCE_REQUIREMENT,
        **core,
        **activation,
        "product_qualification_authorized": False,
    }
    return {"schema": SCHEMA, **payload, "plan_digest": sha256_bytes(canonical_json_bytes(payload))}


def build_inactive_p19_external_verification_plan_v5_document(*, repository_root: Path) -> dict[str, object]:
    return _build_document(repository_root=repository_root, active=False, activation_authority_path=None)


def build_activated_p19_external_verification_plan_v5_document(
    *, repository_root: Path, activation_authority_path: Path
) -> dict[str, object]:
    return _build_document(
        repository_root=repository_root,
        active=True,
        activation_authority_path=activation_authority_path,
    )


@dataclass(frozen=True, slots=True)
class P19ExternalVerificationPlanV5:
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
    activation_allowed_signers_sha256: str | None
    activation_verifier_principals: tuple[str, ...]
    activation_signer_key_digests: tuple[str, ...]
    activation_regression_receipt_path: str | None
    activation_regression_receipt_sha256: str | None
    activation_regression_receipt_digest: str | None
    activation_regression_source_commit: str | None
    activation_regression_source_tree: str | None
    activation_regression_test_manifest_digest: str | None
    activation_signature_semantics: str | None
    activation_signature_tool_execution_provenance_authoritative: bool
    product_qualification_authorized: bool
    plan_digest: str

    def contract(self, check_id: str) -> Mapping[str, object]:
        matches = [row for row in self.check_contracts if row.get("check_id") == check_id]
        if len(matches) != 1:
            raise P19ExternalVerificationPlanV5Error(f"missing/duplicate verification contract: {check_id}")
        return matches[0]


def load_p19_external_verification_plan_v5(
    path: Path,
    *,
    repository_root: Path,
    require_active: bool = True,
) -> P19ExternalVerificationPlanV5:
    root = Path(repository_root).resolve()
    source, _ = _repo_file(root, path, label="Plan V5")
    try:
        raw = source.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19ExternalVerificationPlanV5Error("invalid Plan V5 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19ExternalVerificationPlanV5Error("unexpected Plan V5 schema")
    if raw != canonical_json_bytes(doc) + b"\n":
        raise P19ExternalVerificationPlanV5Error("Plan V5 must use canonical JSON bytes")
    active = doc.get("activation_authorized") is True
    expected = _build_document(
        repository_root=root,
        active=active,
        activation_authority_path=(Path(str(doc.get("activation_authority_path"))) if active else None),
    )
    if doc != expected:
        raise P19ExternalVerificationPlanV5Error("Plan V5 document differs from current portable composition replay")
    if require_active and not active:
        raise P19ExternalVerificationPlanV5Error("Plan V5 is not activated")
    activation = _activation_payload(root, Path(str(doc["activation_authority_path"]))) if active else _empty_activation()
    return P19ExternalVerificationPlanV5(
        plan_generation=PLAN_GENERATION,
        frozen_pre_outcome=True,
        activation_authorized=active,
        activation_evidence_requirement=ACTIVATION_EVIDENCE_REQUIREMENT,
        verifier_entrypoint_path=str(doc["verifier_entrypoint_path"]),
        verifier_entrypoint_sha256=str(doc["verifier_entrypoint_sha256"]),
        verifier_dependency_manifest_digest=str(doc["verifier_dependency_manifest_digest"]),
        verifier_dependencies=tuple(dict(row) for row in doc["verifier_dependencies"]),
        check_contracts=tuple(dict(row) for row in doc["check_contracts"]),
        all_check_implementations_complete=True,
        activation_authority_path=(str(activation["activation_authority_path"]) if active else None),
        activation_authority_sha256=(str(activation["activation_authority_sha256"]) if active else None),
        activation_authority_digest=(str(activation["activation_authority_digest"]) if active else None),
        activation_trust_policy_path=(str(activation["activation_trust_policy_path"]) if active else None),
        activation_trust_policy_digest=(str(activation["activation_trust_policy_digest"]) if active else None),
        activation_allowed_signers_sha256=(str(activation["activation_allowed_signers_sha256"]) if active else None),
        activation_verifier_principals=(tuple(str(v) for v in activation["activation_verifier_principals"]) if active else ()),
        activation_signer_key_digests=(tuple(str(v) for v in activation["activation_signer_key_digests"]) if active else ()),
        activation_regression_receipt_path=(str(activation["activation_regression_receipt_path"]) if active else None),
        activation_regression_receipt_sha256=(str(activation["activation_regression_receipt_sha256"]) if active else None),
        activation_regression_receipt_digest=(str(activation["activation_regression_receipt_digest"]) if active else None),
        activation_regression_source_commit=(str(activation["activation_regression_source_commit"]) if active else None),
        activation_regression_source_tree=(str(activation["activation_regression_source_tree"]) if active else None),
        activation_regression_test_manifest_digest=(str(activation["activation_regression_test_manifest_digest"]) if active else None),
        activation_signature_semantics=(SIGNATURE_SEMANTICS if active else None),
        activation_signature_tool_execution_provenance_authoritative=False,
        product_qualification_authorized=False,
        plan_digest=str(doc["plan_digest"]),
    )


def expected_command_argv_v5(
    plan: P19ExternalVerificationPlanV5,
    *,
    check_id: str,
    p19_path: str,
    evidence_path: str,
) -> tuple[str, ...]:
    row = plan.contract(check_id)
    if row.get("method_id") != CHECK_METHOD_IDS.get(check_id) or row.get("implementation_status") != "IMPLEMENTED":
        raise P19ExternalVerificationPlanV5Error(f"Plan V5 check contract invalid: {check_id}")
    return (
        "python", ENTRYPOINT, "--check-id", check_id,
        "--p19", _safe_rel(p19_path, label="P19 path"),
        "--evidence-output", _safe_rel(evidence_path, label="verification evidence path"),
    )


def verify_command_against_plan_v5(
    plan: P19ExternalVerificationPlanV5,
    *,
    check_id: str,
    command_argv: Sequence[str],
    p19_path: str,
    evidence_path: str,
) -> None:
    expected = expected_command_argv_v5(
        plan,
        check_id=check_id,
        p19_path=p19_path,
        evidence_path=evidence_path,
    )
    if tuple(command_argv) != expected:
        raise P19ExternalVerificationPlanV5Error(f"verification command differs from Plan V5: {check_id}")
