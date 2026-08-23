from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

ATTESTATION_SCHEMA = "DGC_INDEPENDENT_REPLICATION_ATTESTATION_V1"
NAMESPACE = "dgc-independent-replication-v1"
DECLARATION = (
    "I independently executed the frozen DGC replication package without author-controlled "
    "result selection or methodology changes, and I disclose the raw replication evidence."
)


class ReplicationAttestationError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ReplicationAttestationError(f"{name} must be lowercase SHA-256")
    return text


def _canonical_attestation_bytes(doc: dict[str, object]) -> bytes:
    return canonical_json_bytes(doc) + b"\n"


@dataclass(frozen=True, slots=True)
class ReplicationSignatureReceipt:
    attestation_sha256: str
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


def load_replication_attestation(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ReplicationAttestationError("replication attestation must be a regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReplicationAttestationError("invalid replication attestation JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != ATTESTATION_SCHEMA:
        raise ReplicationAttestationError("unexpected replication attestation schema")
    if raw != _canonical_attestation_bytes(doc):
        raise ReplicationAttestationError("replication attestation must use canonical JSON bytes")
    if doc.get("declaration") != DECLARATION:
        raise ReplicationAttestationError("replication independence declaration mismatch")
    if doc.get("methodology_unchanged") is not True:
        raise ReplicationAttestationError("replicator did not attest unchanged methodology")
    if doc.get("author_control_over_execution") is not False:
        raise ReplicationAttestationError("replicator did not attest execution independence")
    if doc.get("raw_results_disclosed") is not True:
        raise ReplicationAttestationError("replicator did not attest raw-result disclosure")
    principal = str(doc.get("replicator_principal", "")).strip()
    if not principal or "\n" in principal or "\r" in principal:
        raise ReplicationAttestationError("replicator_principal required")
    for field in (
        "replication_package_digest", "primary_p9_scientific_authority_digest",
        "primary_generalization_scientific_authority_digest", "replica_p9_scientific_authority_digest",
    ):
        _sha(field, doc.get(field))
    return doc


def verify_ssh_signed_replication_attestation(
    *,
    attestation_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    runner: Runner = subprocess.run,
    executable: str | None = None,
) -> tuple[dict[str, object], ReplicationSignatureReceipt]:
    doc = load_replication_attestation(Path(attestation_path))
    signature = Path(signature_path)
    allowed = Path(allowed_signers_path)
    for name, path in (("signature", signature), ("allowed signers", allowed)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise ReplicationAttestationError(f"{name} must be a non-empty regular file")
    ssh_keygen = executable or shutil.which("ssh-keygen")
    if not ssh_keygen:
        raise ReplicationAttestationError("ssh-keygen unavailable for signature verification")
    exe_path = Path(ssh_keygen).resolve()
    if not exe_path.is_file():
        raise ReplicationAttestationError("ssh-keygen executable path invalid")
    principal = str(doc["replicator_principal"])
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
        raise ReplicationAttestationError("ssh-keygen signature verifier execution failed") from exc
    stdout = bytes(result.stdout or b"")
    stderr = bytes(result.stderr or b"")
    verified = int(result.returncode) == 0
    receipt = ReplicationSignatureReceipt(
        attestation_sha256=sha256_file(Path(attestation_path)),
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
        raise ReplicationAttestationError("replication SSH signature verification failed")
    return doc, receipt
