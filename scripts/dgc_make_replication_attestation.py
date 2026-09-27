from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.replication_attestation import ATTESTATION_SCHEMA, DECLARATION, NAMESPACE
from cwc.governance.materialization_transaction import canonical_json_bytes


def _sha(name: str, value: str) -> str:
    value = value.strip().lower()
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Create canonical bytes for an externally signed DGC replication attestation.")
    parser.add_argument("--replicator-principal", required=True)
    parser.add_argument("--replication-package-digest", required=True)
    parser.add_argument("--primary-p9-authority-digest", required=True)
    parser.add_argument("--primary-generalization-authority-digest", required=True)
    parser.add_argument("--replica-p9-authority-digest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    principal = args.replicator_principal.strip()
    if not principal or "\n" in principal or "\r" in principal:
        raise ValueError("replicator principal required")
    doc = {
        "schema": ATTESTATION_SCHEMA,
        "replicator_principal": principal,
        "replication_package_digest": _sha("replication_package_digest", args.replication_package_digest),
        "primary_p9_scientific_authority_digest": _sha(
            "primary_p9_scientific_authority_digest", args.primary_p9_authority_digest
        ),
        "primary_generalization_scientific_authority_digest": _sha(
            "primary_generalization_scientific_authority_digest", args.primary_generalization_authority_digest
        ),
        "replica_p9_scientific_authority_digest": _sha(
            "replica_p9_scientific_authority_digest", args.replica_p9_authority_digest
        ),
        "methodology_unchanged": True,
        "author_control_over_execution": False,
        "raw_results_disclosed": True,
        "declaration": DECLARATION,
    }
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("attestation output is immutable")
    output.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json_bytes(doc) + b"\n"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    print(json.dumps({
        "status": "PASS",
        "attestation": str(output),
        "namespace": NAMESPACE,
        "next_action": "sign these exact bytes with ssh-keygen -Y sign using namespace dgc-independent-replication-v1",
        "social_independence_machine_proven": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
