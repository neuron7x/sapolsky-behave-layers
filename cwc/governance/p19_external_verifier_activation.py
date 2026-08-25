from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verification_contract import CANONICAL_REGRESSION_COMMAND
from cwc.governance.p19_external_verifier_regression import verify_p19_external_verifier_regression_receipt
from cwc.governance.p19_verifier_policy import (
    P19VerifierTrustPolicy,
    load_p19_verifier_trust_policy,
    resolve_allowed_signers,
    signer_key_digest_map,
)

ATTESTATION_SCHEMA = "DGC_P19_EXTERNAL_VERIFIER_REGRESSION_ATTESTATION_V1"
AUTHORITY_SCHEMA = "DGC_P19_EXTERNAL_VERIFIER_ACTIVATION_AUTHORITY_V1"
NAMESPACE = "dgc-p19-external-verifier-regression-v1"
DECLARATION = (
    "I independently observed execution of the canonical DGC external-P19 verifier regression "
    "against the exact Git-bound runtime/test surface identified by this receipt and observed "
    "exit_code=0. This signature attests execution provenance; it does not itself prove the "
    "scientific correctness of DGC or machine-prove social independence."
)


class P19ExternalVerifierActivationError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerifierActivationError(f"{name} must be lowercase SHA-256")
    return text


def _oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19ExternalVerifierActivationError(f"{name} must be lowercase 40-hex Git OID")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if (
        not text
        or text != text.strip()
        or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\"))
        or "//" in text
    ):
        raise P19ExternalVerifierActivationError(f"{label} must be canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise P19ExternalVerifierActivationError(f"{label} must be canonical repository-relative POSIX path")
    return rel.as_posix()


def _repo_file(root: Path, value: Path | str, *, label: str, allow_empty: bool = False) -> tuple[Path, str]:
    source = Path(value)
    if source.is_absolute():
        resolved = source.resolve()
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise P19ExternalVerifierActivationError(f"{label} escapes repository") from exc
        rel = _safe_rel(rel, label=label)
    else:
        rel = _safe_rel(source.as_posix(), label=label)
        resolved = (root / rel).resolve()
    if (root / rel).is_symlink() or not resolved.is_file():
        raise P19ExternalVerifierActivationError(f"{label} must be a regular non-symlink file")
    if not allow_empty and resolved.stat().st_size <= 0:
        raise P19ExternalVerifierActivationError(f"{label} must be non-empty")
    return resolved, rel


def canonical_regression_attestation_bytes(doc: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(dict(doc)) + b"\n"


def make_regression_attestation(
    *,
    regression_receipt: Mapping[str, object],
    regression_receipt_sha256: str,
    verifier_principal: str,
) -> dict[str, object]:
    principal = str(verifier_principal).strip()
    if not principal or "\n" in principal or "\r" in principal:
        raise P19ExternalVerifierActivationError("verifier principal required")
    if regression_receipt.get("exit_code") != 0 or regression_receipt.get("all_regression_tests_passed") is not True:
        raise P19ExternalVerifierActivationError("cannot attest a non-passing regression receipt")
    command = regression_receipt.get("canonical_command_argv")
    if not isinstance(command, list) or tuple(command) != CANONICAL_REGRESSION_COMMAND:
        raise P19ExternalVerifierActivationError("regression receipt command is not canonical")
    return {
        "schema": ATTESTATION_SCHEMA,
        "namespace": NAMESPACE,
        "regression_receipt_sha256": _sha("regression_receipt_sha256", regression_receipt_sha256),
        "regression_receipt_digest": _sha("regression_receipt_digest", regression_receipt.get("receipt_digest")),
        "source_commit": _oid("source_commit", regression_receipt.get("source_commit")),
        "source_tree": _oid("source_tree", regression_receipt.get("source_tree")),
        "runtime_manifest_digest": _sha("runtime_manifest_digest", regression_receipt.get("runtime_manifest_digest")),
        "test_manifest_digest": _sha("test_manifest_digest", regression_receipt.get("test_manifest_digest")),
        "method_map_digest": _sha("method_map_digest", regression_receipt.get("method_map_digest")),
        "canonical_command_digest": sha256_bytes(canonical_json_bytes(list(CANONICAL_REGRESSION_COMMAND))),
        "exit_code": 0,
        "all_regression_tests_passed": True,
        "execution_observed": True,
        "remote_runner_machine_proven": False,
        "social_independence_machine_proven": False,
        "verifier_principal": principal,
        "declaration": DECLARATION,
    }


def load_regression_attestation(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_size <= 0:
        raise P19ExternalVerifierActivationError("regression attestation must be a non-empty regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19ExternalVerifierActivationError("invalid regression attestation JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != ATTESTATION_SCHEMA:
        raise P19ExternalVerifierActivationError("unexpected regression attestation schema")
    if raw != canonical_regression_attestation_bytes(doc):
        raise P19ExternalVerifierActivationError("regression attestation must use canonical JSON bytes")
    if doc.get("namespace") != NAMESPACE or doc.get("declaration") != DECLARATION:
        raise P19ExternalVerifierActivationError("regression attestation protocol mismatch")
    if doc.get("exit_code") != 0 or doc.get("all_regression_tests_passed") is not True or doc.get("execution_observed") is not True:
        raise P19ExternalVerifierActivationError("regression attestation does not attest passing execution")
    if doc.get("remote_runner_machine_proven") is not False or doc.get("social_independence_machine_proven") is not False:
        raise P19ExternalVerifierActivationError("regression attestation overclaims machine proof")
    principal = str(doc.get("verifier_principal", "")).strip()
    if not principal or "\n" in principal or "\r" in principal:
        raise P19ExternalVerifierActivationError("regression attestation verifier principal required")
    for field in (
        "regression_receipt_sha256", "regression_receipt_digest", "runtime_manifest_digest",
        "test_manifest_digest", "method_map_digest", "canonical_command_digest",
    ):
        _sha(field, doc.get(field))
    _oid("source_commit", doc.get("source_commit"))
    _oid("source_tree", doc.get("source_tree"))
    return doc


def _bind_attestation_to_receipt(attestation: Mapping[str, object], receipt: Mapping[str, object], receipt_sha: str) -> None:
    expected = {
        "regression_receipt_sha256": receipt_sha,
        "regression_receipt_digest": str(receipt.get("receipt_digest", "")),
        "source_commit": str(receipt.get("source_commit", "")),
        "source_tree": str(receipt.get("source_tree", "")),
        "runtime_manifest_digest": str(receipt.get("runtime_manifest_digest", "")),
        "test_manifest_digest": str(receipt.get("test_manifest_digest", "")),
        "method_map_digest": str(receipt.get("method_map_digest", "")),
        "canonical_command_digest": sha256_bytes(canonical_json_bytes(list(CANONICAL_REGRESSION_COMMAND))),
    }
    for field, value in expected.items():
        if str(attestation.get(field, "")) != value:
            raise P19ExternalVerifierActivationError(f"regression attestation/receipt mismatch: {field}")


@dataclass(frozen=True, slots=True)
class RegressionSignatureReceipt:
    attestation_sha256: str
    signature_sha256: str
    allowed_signers_sha256: str
    principal: str
    signer_key_digest: str
    namespace: str
    ssh_keygen_path: str
    ssh_keygen_sha256: str
    stdout_sha256: str
    stderr_sha256: str
    signature_verified: bool

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json_bytes(asdict(self)))


def _verify_signature(
    *,
    attestation_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    signer_key_digests: Mapping[str, str],
    runner: Runner,
    executable: str | None,
) -> tuple[dict[str, object], RegressionSignatureReceipt]:
    attestation = load_regression_attestation(attestation_path)
    signature = Path(signature_path)
    allowed = Path(allowed_signers_path)
    if signature.is_symlink() or not signature.is_file() or signature.stat().st_size <= 0:
        raise P19ExternalVerifierActivationError("regression signature must be a non-empty regular file")
    if allowed.is_symlink() or not allowed.is_file() or allowed.stat().st_size <= 0:
        raise P19ExternalVerifierActivationError("regression allowed-signers must be a non-empty regular file")
    principal = str(attestation["verifier_principal"])
    if principal not in signer_key_digests:
        raise P19ExternalVerifierActivationError("regression verifier principal is absent from frozen trust store")
    ssh_keygen = executable or shutil.which("ssh-keygen")
    if not ssh_keygen:
        raise P19ExternalVerifierActivationError("ssh-keygen unavailable for regression attestation verification")
    exe_path = Path(ssh_keygen).resolve()
    if not exe_path.is_file():
        raise P19ExternalVerifierActivationError("ssh-keygen executable path invalid")
    argv: Sequence[str] = (
        str(exe_path), "-Y", "verify", "-f", str(allowed.resolve()),
        "-I", principal, "-n", NAMESPACE, "-s", str(signature.resolve()),
    )
    try:
        result = runner(
            list(argv),
            input=Path(attestation_path).read_bytes(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except (OSError, TypeError) as exc:
        raise P19ExternalVerifierActivationError("regression SSH signature verifier execution failed") from exc
    stdout = bytes(result.stdout or b"")
    stderr = bytes(result.stderr or b"")
    if int(result.returncode) != 0:
        raise P19ExternalVerifierActivationError("external verifier regression SSH signature failed")
    receipt = RegressionSignatureReceipt(
        attestation_sha256=sha256_file(Path(attestation_path)),
        signature_sha256=sha256_file(signature),
        allowed_signers_sha256=sha256_file(allowed),
        principal=principal,
        signer_key_digest=signer_key_digests[principal],
        namespace=NAMESPACE,
        ssh_keygen_path=str(exe_path),
        ssh_keygen_sha256=sha256_file(exe_path),
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        signature_verified=True,
    )
    return attestation, receipt


@dataclass(frozen=True, slots=True)
class P19ExternalVerifierActivationAuthority:
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
    attestation_paths: tuple[str, ...]
    signature_paths: tuple[str, ...]
    verifier_principals: tuple[str, ...]
    signer_key_digests: tuple[str, ...]
    signature_receipt_digests: tuple[str, ...]
    minimum_distinct_verifiers_satisfied: bool
    minimum_distinct_signer_keys_satisfied: bool
    all_signatures_verified: bool
    activation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {"schema": AUTHORITY_SCHEMA, **asdict(self), "product_qualification_authorized": False}


def build_p19_external_verifier_activation_authority(
    *,
    repository_root: Path,
    regression_receipt_path: Path,
    trust_policy_path: Path,
    attestation_paths: Sequence[Path],
    signature_paths: Sequence[Path],
    runner: Runner = subprocess.run,
    executable: str | None = None,
) -> P19ExternalVerifierActivationAuthority:
    root = Path(repository_root).resolve()
    receipt_file, receipt_rel = _repo_file(root, regression_receipt_path, label="regression receipt")
    receipt = verify_p19_external_verifier_regression_receipt(receipt_file, repository_root=root)
    receipt_sha = sha256_file(receipt_file)

    policy_file, policy_rel = _repo_file(root, trust_policy_path, label="verifier trust policy")
    policy: P19VerifierTrustPolicy = load_p19_verifier_trust_policy(policy_file)
    allowed = resolve_allowed_signers(policy, repository_root=root)
    signer_map = signer_key_digest_map(policy, allowed_signers_path=allowed)

    if len(attestation_paths) != policy.minimum_distinct_verifiers or len(signature_paths) != policy.minimum_distinct_verifiers:
        raise P19ExternalVerifierActivationError("regression activation requires exact frozen verifier signature population")

    attestation_rels: list[str] = []
    signature_rels: list[str] = []
    principals: list[str] = []
    key_digests: list[str] = []
    signature_receipts: list[str] = []
    for attestation_value, signature_value in zip(attestation_paths, signature_paths, strict=True):
        attestation_file, attestation_rel = _repo_file(root, attestation_value, label="regression attestation")
        signature_file, signature_rel = _repo_file(root, signature_value, label="regression signature")
        attestation, sig_receipt = _verify_signature(
            attestation_path=attestation_file,
            signature_path=signature_file,
            allowed_signers_path=allowed,
            signer_key_digests=signer_map,
            runner=runner,
            executable=executable,
        )
        _bind_attestation_to_receipt(attestation, receipt, receipt_sha)
        attestation_rels.append(attestation_rel)
        signature_rels.append(signature_rel)
        principals.append(sig_receipt.principal)
        key_digests.append(sig_receipt.signer_key_digest)
        signature_receipts.append(sig_receipt.digest)

    if len(set(principals)) < policy.minimum_distinct_verifiers:
        raise P19ExternalVerifierActivationError("regression activation verifier principals are not sufficiently distinct")
    if len(set(key_digests)) < policy.minimum_distinct_signer_keys:
        raise P19ExternalVerifierActivationError("regression activation signer keys are not sufficiently distinct")

    ordered = sorted(zip(principals, key_digests, attestation_rels, signature_rels, signature_receipts), key=lambda row: row[0])
    principals_t = tuple(row[0] for row in ordered)
    keys_t = tuple(row[1] for row in ordered)
    attest_t = tuple(row[2] for row in ordered)
    sig_t = tuple(row[3] for row in ordered)
    sig_receipts_t = tuple(row[4] for row in ordered)
    payload = {
        "regression_receipt_path": receipt_rel,
        "regression_receipt_sha256": receipt_sha,
        "regression_receipt_digest": _sha("regression receipt digest", receipt.get("receipt_digest")),
        "source_commit": _oid("source_commit", receipt.get("source_commit")),
        "source_tree": _oid("source_tree", receipt.get("source_tree")),
        "runtime_manifest_digest": _sha("runtime manifest digest", receipt.get("runtime_manifest_digest")),
        "test_manifest_digest": _sha("test manifest digest", receipt.get("test_manifest_digest")),
        "method_map_digest": _sha("method map digest", receipt.get("method_map_digest")),
        "trust_policy_path": policy_rel,
        "trust_policy_digest": policy.policy_digest,
        "allowed_signers_sha256": policy.allowed_signers_sha256,
        "attestation_paths": list(attest_t),
        "signature_paths": list(sig_t),
        "verifier_principals": list(principals_t),
        "signer_key_digests": list(keys_t),
        "signature_receipt_digests": list(sig_receipts_t),
        "minimum_distinct_verifiers_satisfied": True,
        "minimum_distinct_signer_keys_satisfied": True,
        "all_signatures_verified": True,
        "activation_authorized": True,
    }
    return P19ExternalVerifierActivationAuthority(
        regression_receipt_path=receipt_rel,
        regression_receipt_sha256=receipt_sha,
        regression_receipt_digest=str(payload["regression_receipt_digest"]),
        source_commit=str(payload["source_commit"]),
        source_tree=str(payload["source_tree"]),
        runtime_manifest_digest=str(payload["runtime_manifest_digest"]),
        test_manifest_digest=str(payload["test_manifest_digest"]),
        method_map_digest=str(payload["method_map_digest"]),
        trust_policy_path=policy_rel,
        trust_policy_digest=policy.policy_digest,
        allowed_signers_sha256=policy.allowed_signers_sha256,
        attestation_paths=attest_t,
        signature_paths=sig_t,
        verifier_principals=principals_t,
        signer_key_digests=keys_t,
        signature_receipt_digests=sig_receipts_t,
        minimum_distinct_verifiers_satisfied=True,
        minimum_distinct_signer_keys_satisfied=True,
        all_signatures_verified=True,
        activation_authorized=True,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_p19_external_verifier_activation_authority_document(
    path: Path,
    *,
    repository_root: Path,
    runner: Runner = subprocess.run,
    executable: str | None = None,
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    source, _ = _repo_file(root, path, label="verifier activation authority")
    try:
        raw = source.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19ExternalVerifierActivationError("invalid verifier activation authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != AUTHORITY_SCHEMA:
        raise P19ExternalVerifierActivationError("unexpected verifier activation authority schema")
    if raw != canonical_json_bytes(doc) + b"\n":
        raise P19ExternalVerifierActivationError("verifier activation authority must use canonical JSON bytes")
    if doc.get("product_qualification_authorized") is not False:
        raise P19ExternalVerifierActivationError("verifier activation authority cannot authorize product qualification")
    required_true = (
        "minimum_distinct_verifiers_satisfied", "minimum_distinct_signer_keys_satisfied",
        "all_signatures_verified", "activation_authorized",
    )
    if not all(doc.get(field) is True for field in required_true):
        raise P19ExternalVerifierActivationError("verifier activation authority support flags incomplete")

    attestation_paths = doc.get("attestation_paths")
    signature_paths = doc.get("signature_paths")
    if not isinstance(attestation_paths, list) or not isinstance(signature_paths, list):
        raise P19ExternalVerifierActivationError("verifier activation authority signature population malformed")
    rebuilt = build_p19_external_verifier_activation_authority(
        repository_root=root,
        regression_receipt_path=Path(str(doc.get("regression_receipt_path", ""))),
        trust_policy_path=Path(str(doc.get("trust_policy_path", ""))),
        attestation_paths=[Path(str(value)) for value in attestation_paths],
        signature_paths=[Path(str(value)) for value in signature_paths],
        runner=runner,
        executable=executable,
    )
    if rebuilt.authority_digest != _sha("authority_digest", doc.get("authority_digest")):
        raise P19ExternalVerifierActivationError("verifier activation authority differs from raw signature replay")
    if rebuilt.document != doc:
        raise P19ExternalVerifierActivationError("verifier activation authority document differs from recomputation")
    return doc
