from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.global_product_qualification_v4 import FamilyP19VerificationInputV4
from cwc.governance.global_product_qualification_v5 import build_global_product_qualification_authority_v5
from cwc.governance.p19_verifier_policy import CANONICAL_POLICY_PATH


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _verification_input(args, suffix: str) -> FamilyP19VerificationInputV4:
    return FamilyP19VerificationInputV4(
        attestation_path=Path(getattr(args, f"attestation_{suffix}")),
        verification_report_path=Path(getattr(args, f"report_{suffix}")),
        signature_path=Path(getattr(args, f"signature_{suffix}")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the portable terminal two-family DGC Global V5 product qualification authority. "
            "V5 replays V4 validation but excludes environment-specific ssh-keygen execution provenance "
            "from the portable product authority identity."
        )
    )
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--source-registry", required=True)
    parser.add_argument("--p19-a", required=True)
    parser.add_argument("--attestation-a", required=True)
    parser.add_argument("--report-a", required=True)
    parser.add_argument("--signature-a", required=True)
    parser.add_argument("--p19-b", required=True)
    parser.add_argument("--attestation-b", required=True)
    parser.add_argument("--report-b", required=True)
    parser.add_argument("--signature-b", required=True)
    parser.add_argument("--verifier-policy", default=CANONICAL_POLICY_PATH)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.repository_root).resolve()
    authority = build_global_product_qualification_authority_v5(
        repository_root=root,
        source_registry_path=Path(args.source_registry),
        family_p19_paths=(Path(args.p19_a), Path(args.p19_b)),
        family_p19_verification_inputs=(
            _verification_input(args, "a"),
            _verification_input(args, "b"),
        ),
        p19_verifier_policy_path=Path(args.verifier_policy),
    )
    output = Path(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n",
    )
    print(json.dumps({
        "status": "PASS_PRODUCT_QUALIFIED_RESEARCH_EVIDENCE_PORTABLE_V5",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "canonical_family_ids": list(authority.canonical_family_ids),
        "verifier_principals": list(authority.verifier_principals),
        "verifier_trust_policy_digest": authority.verifier_trust_policy_digest,
        "signature_semantics": authority.signature_semantics,
        "signature_tool_execution_provenance_authoritative": authority.signature_tool_execution_provenance_authoritative,
        "product_qualified": authority.product_qualified,
        "production_control_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
