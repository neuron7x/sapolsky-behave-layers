from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

ATTESTATION_SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_ATTESTATION_V1"
NAMESPACE = "dgc-p19-external-verification-v1"
VERIFICATION_PROTOCOL = "DGC_P19_CANONICAL_SEMANTIC_REPLAY_V1"
DECLARATION = (
    "I independently executed the canonical DGC family P19 semantic verification/replay "
    "against the disclosed evidence subjects and obtained PASS. This signature attests "
    "that verification execution; it does not replace the raw evidence or prove the social "
    "fact of verifier independence by itself."
)


class P19VerificationAttestationError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerificationAttestationError(f"{name} must be lowercase SHA-256")
    return text


def _oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerificationAttestationError(f"{name} must be lowercase 40-hex Git object id")
    return text


def canonical_attestation_bytes(doc: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(dict(doc)) + b"\n"


@dataclass(frozen=True, slots=True)
class P19VerificationSignatureReceipt:
    attestation_sha256: str
    verification_report_sha256: str
    signature_sha256: str
    allowed_signers_sha256: str
    principal: str
    namespace: str
    ssh_keygen_path: str
    ssh_keygen_sha256: str
    stdout_sha256: str
    stderr_sha256: str
    signature_verified: bool

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json_bytes(asdict(self)))


def make_p19_verification_attestation(
    *,
    family_p19: Mapping[str, object],
    verifier_principal: str,
    verification_report_sha256: str,
) -> dict[str, object]:
    principal = str(verifier_principal).strip()
    if not principal or "\n" in principal or "\r" in principal:
        raise P19VerificationAttestationError("verifier_principal required")
    if family_p19.get("family_evidence_complete") is not True:
        raise P19VerificationAttestationError("cannot attest an incomplete family P19")
    return {
        "schema": ATTESTATION_SCHEMA,
        "verification_protocol": VERIFICATION_PROTOCOL,
        "family_id": str(family_p19.get("family_id", "")),
        "p19_digest": _sha("p19_digest", family_p19.get("p19_digest")),
        "repository_commit": _oid("repository_commit", family_p19.get("repository_commit")),
        "repository_tree": _oid("repository_tree", family_p19.get("repository_tree")),
        "statistical_plan_digest": _sha("statistical_plan_digest", family_p19.get("statistical_plan_digest")),
        "theorem_identity_digest": _sha("theorem_identity_digest", family_p19.get("theorem_identity_digest")),
        "methodology_anchor_digest": _sha("methodology_anchor_digest", family_p19.get("methodology_anchor_digest")),
        "stage_evidence_manifest_digest": _sha(
            "stage_evidence_manifest_digest", family_p19.get("stage_evidence_manifest_digest")
        ),
        "subject_root_manifest_digest": _sha(
            "subject_root_manifest_digest", family_p19.get("subject_root_manifest_digest")
        ),
        "verification_report_sha256": _sha("verification_report_sha256", verification_report_sha256),
        "semantic_replay_passed": True,
        "raw_evidence_disclosed": True,
        "author_control_over_verification": False,
        "social_independence_machine_proven": False,
        "verifier_principal": principal,
        "declaration": DECLARATION,
    }


def load_p19_verification_attestation(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P19VerificationAttestationError("P19 verification attestation must be a regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19VerificationAttestationError("invalid P19 verification attestation JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != ATTESTATION_SCHEMA:
        raise P19VerificationAttestationError("unexpected P19 verification attestation schema")
    if raw != canonical_attestation_bytes(doc):
        raise P19VerificationAttestationError("P19 verification attestation must use canonical JSON bytes")
    if doc.get("verification_protocol") != VERIFICATION_PROTOCOL or doc.get("declaration") != DECLARATION:
        raise P19VerificationAttestationError("P19 verification protocol/declaration mismatch")
    if doc.get("semantic_replay_passed") is not True or doc.get("raw_evidence_disclosed") is not True:
        raise P19VerificationAttestationError("P19 verifier did not attest semantic replay/raw disclosure")
    if doc.get("author_control_over_verification") is not False:
        raise P19VerificationAttestationError("P19 verifier did not attest execution independence")
    if doc.get("social_independence_machine_proven") is not False:
        raise P19VerificationAttestationError("P19 attestation cannot claim machine-proven social independence")
    principal = str(doc.get("verifier_principal", "")).strip()
    family = str(doc.get("family_id", "")).strip()
    if not principal or "\n" in principal or "\r" in principal or not family:
        raise P19VerificationAttestationError("P19 verifier/family identity required")
    for field in (
        "p19_digest", "statistical_plan_digest", "theorem_identity_digest", "methodology_anchor_digest",
        "stage_evidence_manifest_digest", "subject_root_manifest_digest", "verification_report_sha256",
    ):
        _sha(field, doc.get(field))
    _oid("repository_commit", doc.get("repository_commit"))
    _oid("repository_tree", doc.get("repository_tree"))
    return doc


def verify_ssh_signed_p19_verification_attestation(
    *,
    attestation_path: Path,
    verification_report_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    runner: Runner = subprocess.run,
    executable: str | None = None,
) -> tuple[dict[str, object], P19VerificationSignatureReceipt]:
    doc = load_p19_verification_attestation(Path(attestation_path))
    report = Path(verification_report_path)
    signature = Path(signature_path)
    allowed = Path(allowed_signers_path)
    for name, path in (("verification report", report), ("signature", signature), ("allowed signers", allowed)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise P19VerificationAttestationError(f"{name} must be a non-empty regular file")
    report_sha = sha256_file(report)
    if report_sha != doc.get("verification_report_sha256"):
        raise P19VerificationAttestationError("P19 verification report differs from signed attestation")

    ssh_keygen = executable or shutil.which("ssh-keygen")
    if not ssh_keygen:
        raise P19VerificationAttestationError("ssh-keygen unavailable for P19 signature verification")
    exe_path = Path(ssh_keygen).resolve()
    if not exe_path.is_file():
        raise P19VerificationAttestationError("ssh-keygen executable path invalid")
    principal = str(doc["verifier_principal"])
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
        raise P19VerificationAttestationError("P19 SSH signature verifier execution failed") from exc
    stdout = bytes(result.stdout or b"")
    stderr = bytes(result.stderr or b"")
    verified = int(result.returncode) == 0
    receipt = P19VerificationSignatureReceipt(
        attestation_sha256=sha256_file(Path(attestation_path)),
        verification_report_sha256=report_sha,
        signature_sha256=sha256_file(signature),
        allowed_signers_sha256=sha256_file(allowed),
        principal=principal,
        namespace=NAMESPACE,
        ssh_keygen_path=str(exe_path),
        ssh_keygen_sha256=sha256_file(exe_path),
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        signature_verified=verified,
    )
    if not verified:
        raise P19VerificationAttestationError("P19 external verification SSH signature failed")
    return doc, receipt


def bind_attestation_to_p19(attestation: Mapping[str, object], p19: Mapping[str, object]) -> None:
    pairs = {
        "family_id": str(p19.get("family_id", "")),
        "p19_digest": str(p19.get("p19_digest", "")),
        "repository_commit": str(p19.get("repository_commit", "")),
        "repository_tree": str(p19.get("repository_tree", "")),
        "statistical_plan_digest": str(p19.get("statistical_plan_digest", "")),
        "theorem_identity_digest": str(p19.get("theorem_identity_digest", "")),
        "methodology_anchor_digest": str(p19.get("methodology_anchor_digest", "")),
        "stage_evidence_manifest_digest": str(p19.get("stage_evidence_manifest_digest", "")),
        "subject_root_manifest_digest": str(p19.get("subject_root_manifest_digest", "")),
    }
    for field, expected in pairs.items():
        if str(attestation.get(field, "")) != expected:
            raise P19VerificationAttestationError(f"P19 external verification attestation mismatch: {field}")
