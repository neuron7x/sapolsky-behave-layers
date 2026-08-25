from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Protocol, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verifier_activation import (
    AUTHORITY_SCHEMA as V1_AUTHORITY_SCHEMA,
    NAMESPACE,
    P19ExternalVerifierActivationAuthority,
    build_p19_external_verifier_activation_authority,
)
from cwc.governance.p19_verifier_policy import CANONICAL_POLICY_PATH

SCHEMA = "DGC_P19_EXTERNAL_VERIFIER_ACTIVATION_AUTHORITY_V2"
SIGNATURE_SEMANTICS = "SSH_SIGNATURE_INPUT_SEMANTICS_ENVIRONMENT_INDEPENDENT_V1"


class P19ExternalVerifierActivationV2Error(RuntimeError):
    pass


class V1Builder(Protocol):
    def __call__(
        self,
        *,
        repository_root: Path,
        regression_receipt_path: Path,
        trust_policy_path: Path,
        attestation_paths: Sequence[Path],
        signature_paths: Sequence[Path],
        **kwargs: object,
    ) -> P19ExternalVerifierActivationAuthority: ...


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerifierActivationV2Error(f"{name} must be lowercase SHA-256")
    return text


def _oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerifierActivationV2Error(f"{name} must be lowercase 40-hex Git OID")
    return text


def _safe_rel(root: Path, value: Path | str, *, label: str) -> tuple[Path, str]:
    source = Path(value)
    if source.is_absolute():
        resolved = source.resolve()
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise P19ExternalVerifierActivationV2Error(f"{label} escapes repository") from exc
    else:
        text = source.as_posix()
        if (
            not text
            or text != text.strip()
            or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\"))
            or "//" in text
        ):
            raise P19ExternalVerifierActivationV2Error(f"{label} path is non-canonical")
        rel_path = PurePosixPath(text)
        if rel_path.is_absolute() or any(part in ("", ".", "..") for part in rel_path.parts):
            raise P19ExternalVerifierActivationV2Error(f"{label} path is non-canonical")
        rel = rel_path.as_posix()
        resolved = (root / rel).resolve()
    candidate = root / rel
    if candidate.is_symlink() or not resolved.is_file() or resolved.stat().st_size <= 0:
        raise P19ExternalVerifierActivationV2Error(f"{label} must be a non-empty regular non-symlink file")
    try:
        observed = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise P19ExternalVerifierActivationV2Error(f"{label} escapes repository") from exc
    if observed != rel:
        raise P19ExternalVerifierActivationV2Error(f"{label} resolves through non-canonical alias")
    return resolved, rel


@dataclass(frozen=True, slots=True)
class StableRegressionSignatureRecord:
    verifier_principal: str
    signer_key_digest: str
    attestation_path: str
    attestation_sha256: str
    signature_path: str
    signature_sha256: str
    allowed_signers_sha256: str
    namespace: str
    signature_verified: bool
    record_digest: str


@dataclass(frozen=True, slots=True)
class P19ExternalVerifierActivationAuthorityV2:
    regression_receipt_path: str
    regression_receipt_sha256: str
    regression_receipt_digest: str
    source_commit: str
    source_tree: str
    runtime_manifest_digest: str
    test_manifest_digest: str
    method_map_digest: str
    trust_policy_path: str
    trust_policy_digest: str
    allowed_signers_sha256: str
    stable_signature_records: tuple[StableRegressionSignatureRecord, ...]
    verifier_principals: tuple[str, ...]
    signer_key_digests: tuple[str, ...]
    minimum_distinct_verifiers_satisfied: bool
    minimum_distinct_signer_keys_satisfied: bool
    all_signatures_verified: bool
    signature_semantics: str
    signature_tool_execution_provenance_authoritative: bool
    activation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "v1_raw_signature_validation_required": True,
            "v1_environment_specific_authority_is_activation_identity": False,
            "product_qualification_authorized": False,
        }


def _stable_records(
    *,
    root: Path,
    v1: P19ExternalVerifierActivationAuthority,
) -> tuple[StableRegressionSignatureRecord, ...]:
    rows: list[StableRegressionSignatureRecord] = []
    if not (
        len(v1.attestation_paths)
        == len(v1.signature_paths)
        == len(v1.verifier_principals)
        == len(v1.signer_key_digests)
    ):
        raise P19ExternalVerifierActivationV2Error("V1 activation signature population is inconsistent")
    for principal, key_digest, att_rel, sig_rel in zip(
        v1.verifier_principals,
        v1.signer_key_digests,
        v1.attestation_paths,
        v1.signature_paths,
        strict=True,
    ):
        attestation, normalized_att = _safe_rel(root, att_rel, label="regression attestation")
        signature, normalized_sig = _safe_rel(root, sig_rel, label="regression signature")
        payload = {
            "verifier_principal": str(principal),
            "signer_key_digest": _sha("signer_key_digest", key_digest),
            "attestation_path": normalized_att,
            "attestation_sha256": sha256_file(attestation),
            "signature_path": normalized_sig,
            "signature_sha256": sha256_file(signature),
            "allowed_signers_sha256": _sha("allowed_signers_sha256", v1.allowed_signers_sha256),
            "namespace": NAMESPACE,
            "signature_verified": True,
        }
        rows.append(StableRegressionSignatureRecord(
            **payload,
            record_digest=sha256_bytes(canonical_json_bytes(payload)),
        ))
    ordered = tuple(sorted(rows, key=lambda row: row.verifier_principal))
    if len({row.verifier_principal for row in ordered}) != len(ordered):
        raise P19ExternalVerifierActivationV2Error("portable activation verifier principals must be unique")
    if len({row.signer_key_digest for row in ordered}) != len(ordered):
        raise P19ExternalVerifierActivationV2Error("portable activation signer keys must be unique")
    return ordered


def build_p19_external_verifier_activation_authority_v2(
    *,
    repository_root: Path,
    regression_receipt_path: Path,
    attestation_paths: Sequence[Path],
    signature_paths: Sequence[Path],
    v1_builder: V1Builder = build_p19_external_verifier_activation_authority,
    v1_builder_kwargs: Mapping[str, object] | None = None,
) -> P19ExternalVerifierActivationAuthorityV2:
    root = Path(repository_root).resolve()
    canonical_policy = root / CANONICAL_POLICY_PATH
    kwargs = dict(v1_builder_kwargs or {})
    try:
        v1 = v1_builder(
            repository_root=root,
            regression_receipt_path=Path(regression_receipt_path),
            trust_policy_path=canonical_policy,
            attestation_paths=list(attestation_paths),
            signature_paths=list(signature_paths),
            **kwargs,
        )
    except RuntimeError as exc:
        raise P19ExternalVerifierActivationV2Error("V1 raw signature validation failed") from exc
    if not v1.activation_authorized or not v1.all_signatures_verified:
        raise P19ExternalVerifierActivationV2Error("V1 raw signature validation did not authorize activation")
    if v1.trust_policy_path != CANONICAL_POLICY_PATH:
        raise P19ExternalVerifierActivationV2Error("V1 activation did not use canonical trust policy path")

    records = _stable_records(root=root, v1=v1)
    principals = tuple(row.verifier_principal for row in records)
    key_digests = tuple(row.signer_key_digest for row in records)
    if len(principals) < 2 or len(key_digests) < 2:
        raise P19ExternalVerifierActivationV2Error("portable activation requires at least two external verifiers/keys")

    payload = {
        "regression_receipt_path": str(v1.regression_receipt_path),
        "regression_receipt_sha256": _sha("regression_receipt_sha256", v1.regression_receipt_sha256),
        "regression_receipt_digest": _sha("regression_receipt_digest", v1.regression_receipt_digest),
        "source_commit": _oid("source_commit", v1.source_commit),
        "source_tree": _oid("source_tree", v1.source_tree),
        "runtime_manifest_digest": _sha("runtime_manifest_digest", v1.runtime_manifest_digest),
        "test_manifest_digest": _sha("test_manifest_digest", v1.test_manifest_digest),
        "method_map_digest": _sha("method_map_digest", v1.method_map_digest),
        "trust_policy_path": CANONICAL_POLICY_PATH,
        "trust_policy_digest": _sha("trust_policy_digest", v1.trust_policy_digest),
        "allowed_signers_sha256": _sha("allowed_signers_sha256", v1.allowed_signers_sha256),
        "stable_signature_records": [asdict(row) for row in records],
        "verifier_principals": list(principals),
        "signer_key_digests": list(key_digests),
        "minimum_distinct_verifiers_satisfied": True,
        "minimum_distinct_signer_keys_satisfied": True,
        "all_signatures_verified": True,
        "signature_semantics": SIGNATURE_SEMANTICS,
        "signature_tool_execution_provenance_authoritative": False,
        "activation_authorized": True,
    }
    return P19ExternalVerifierActivationAuthorityV2(
        regression_receipt_path=str(payload["regression_receipt_path"]),
        regression_receipt_sha256=str(payload["regression_receipt_sha256"]),
        regression_receipt_digest=str(payload["regression_receipt_digest"]),
        source_commit=str(payload["source_commit"]),
        source_tree=str(payload["source_tree"]),
        runtime_manifest_digest=str(payload["runtime_manifest_digest"]),
        test_manifest_digest=str(payload["test_manifest_digest"]),
        method_map_digest=str(payload["method_map_digest"]),
        trust_policy_path=CANONICAL_POLICY_PATH,
        trust_policy_digest=str(payload["trust_policy_digest"]),
        allowed_signers_sha256=str(payload["allowed_signers_sha256"]),
        stable_signature_records=records,
        verifier_principals=principals,
        signer_key_digests=key_digests,
        minimum_distinct_verifiers_satisfied=True,
        minimum_distinct_signer_keys_satisfied=True,
        all_signatures_verified=True,
        signature_semantics=SIGNATURE_SEMANTICS,
        signature_tool_execution_provenance_authoritative=False,
        activation_authorized=True,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_p19_external_verifier_activation_authority_v2_document(
    path: Path,
    *,
    repository_root: Path,
    v1_builder: V1Builder = build_p19_external_verifier_activation_authority,
    v1_builder_kwargs: Mapping[str, object] | None = None,
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    source, _ = _safe_rel(root, path, label="portable verifier activation authority")
    try:
        raw = source.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19ExternalVerifierActivationV2Error("invalid portable activation authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19ExternalVerifierActivationV2Error("unexpected portable activation authority schema")
    if raw != canonical_json_bytes(doc) + b"\n":
        raise P19ExternalVerifierActivationV2Error("portable activation authority must use canonical JSON bytes")
    if doc.get("signature_semantics") != SIGNATURE_SEMANTICS:
        raise P19ExternalVerifierActivationV2Error("portable activation signature semantics mismatch")
    if doc.get("signature_tool_execution_provenance_authoritative") is not False:
        raise P19ExternalVerifierActivationV2Error("machine-local signature-tool provenance leaked into activation truth")
    if doc.get("v1_raw_signature_validation_required") is not True:
        raise P19ExternalVerifierActivationV2Error("portable activation omitted raw V1 signature validation requirement")
    if doc.get("v1_environment_specific_authority_is_activation_identity") is not False:
        raise P19ExternalVerifierActivationV2Error("environment-specific V1 authority leaked into portable activation identity")
    if doc.get("product_qualification_authorized") is not False:
        raise P19ExternalVerifierActivationV2Error("activation authority cannot authorize product qualification")
    if not all(doc.get(field) is True for field in (
        "minimum_distinct_verifiers_satisfied",
        "minimum_distinct_signer_keys_satisfied",
        "all_signatures_verified",
        "activation_authorized",
    )):
        raise P19ExternalVerifierActivationV2Error("portable activation support flags incomplete")
    if doc.get("trust_policy_path") != CANONICAL_POLICY_PATH:
        raise P19ExternalVerifierActivationV2Error("portable activation does not bind canonical trust policy path")

    attestation_paths = []
    signature_paths = []
    records = doc.get("stable_signature_records")
    if not isinstance(records, list) or len(records) < 2:
        raise P19ExternalVerifierActivationV2Error("portable activation stable signature population malformed")
    for row in records:
        if not isinstance(row, Mapping):
            raise P19ExternalVerifierActivationV2Error("portable activation stable signature row malformed")
        attestation_paths.append(Path(str(row.get("attestation_path", ""))))
        signature_paths.append(Path(str(row.get("signature_path", ""))))

    rebuilt = build_p19_external_verifier_activation_authority_v2(
        repository_root=root,
        regression_receipt_path=Path(str(doc.get("regression_receipt_path", ""))),
        attestation_paths=attestation_paths,
        signature_paths=signature_paths,
        v1_builder=v1_builder,
        v1_builder_kwargs=v1_builder_kwargs,
    )
    if rebuilt.authority_digest != _sha("authority_digest", doc.get("authority_digest")):
        raise P19ExternalVerifierActivationV2Error("portable activation authority differs from raw signature replay")
    if rebuilt.document != doc:
        raise P19ExternalVerifierActivationV2Error("portable activation document differs from recomputation")
    return doc
