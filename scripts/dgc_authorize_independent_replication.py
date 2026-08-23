from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.independent_replication_authority_v2 import (
    build_independent_replication_authority_v2,
)


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recompute a fresh externally signed replication and derive INDEPENDENT_REPLICATION authority."
    )
    parser.add_argument("--primary-p9-scientific", required=True)
    parser.add_argument("--primary-dual-p9", required=True)
    parser.add_argument("--primary-ccf-audit", required=True)
    parser.add_argument("--primary-generalization-scientific", required=True)
    parser.add_argument("--replica-p9-scientific", required=True)
    parser.add_argument("--replica-dual-p9", required=True)
    parser.add_argument("--replica-ccf-audit", required=True)
    parser.add_argument("--replica-execution-authority", required=True)
    parser.add_argument("--replica-execution-bundle-root", required=True)
    parser.add_argument("--replica-physical-cost-bundle-root", required=True)
    parser.add_argument("--replica-confirmatory-root-authority", required=True)
    parser.add_argument("--harness-freeze", required=True)
    parser.add_argument("--execution-manifest-freeze", required=True)
    parser.add_argument("--materialization-reference", required=True)
    parser.add_argument("--source-registry", required=True)
    parser.add_argument("--ccf-spec-authority", required=True)
    parser.add_argument("--replica-ccf-evidence-bundle-root", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--signature", required=True)
    parser.add_argument("--allowed-signers", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_independent_replication_authority_v2(
        primary_p9_scientific_authority_path=Path(args.primary_p9_scientific),
        primary_dual_p9_authority_path=Path(args.primary_dual_p9),
        primary_ccf_oracle_audit_authority_path=Path(args.primary_ccf_audit),
        primary_generalization_scientific_authority_path=Path(args.primary_generalization_scientific),
        replica_p9_scientific_authority_path=Path(args.replica_p9_scientific),
        replica_dual_p9_authority_path=Path(args.replica_dual_p9),
        replica_ccf_oracle_audit_authority_path=Path(args.replica_ccf_audit),
        replica_execution_authority_path=Path(args.replica_execution_authority),
        replica_execution_bundle_root=Path(args.replica_execution_bundle_root),
        replica_physical_cost_bundle_root=Path(args.replica_physical_cost_bundle_root),
        replica_confirmatory_root_authority_path=Path(args.replica_confirmatory_root_authority),
        harness_freeze_path=Path(args.harness_freeze),
        execution_manifest_freeze_path=Path(args.execution_manifest_freeze),
        materialization_reference_path=Path(args.materialization_reference),
        source_registry_path=Path(args.source_registry),
        ccf_spec_authority_path=Path(args.ccf_spec_authority),
        replica_ccf_evidence_bundle_root=Path(args.replica_ccf_evidence_bundle_root),
        repository_root=Path(args.repository_root),
        attestation_path=Path(args.attestation),
        signature_path=Path(args.signature),
        allowed_signers_path=Path(args.allowed_signers),
    )
    output = Path(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps({
        "status": "PASS" if authority.independent_replication_supported else "FAIL_INDEPENDENT_REPLICATION",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "replication_package_digest": authority.replication_package_digest,
        "fresh_execution_verified": authority.fresh_execution_verified,
        "replica_p9_supported_under_frozen_assumptions": (
            authority.replica_p9_supported_under_frozen_assumptions
        ),
        "signed_independence_attested": authority.signed_independence_attested,
        "social_independence_machine_proven": authority.social_independence_machine_proven,
        "independent_replication_supported": authority.independent_replication_supported,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if authority.independent_replication_supported else 40


if __name__ == "__main__":
    raise SystemExit(main())
