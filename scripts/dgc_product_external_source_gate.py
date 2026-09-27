from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cwc.governance.external_source_authority import ExternalSourceAuthority, ExternalSourceStage

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "artifacts/dgc-product-v1/external_source_authority.json"


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main() -> int:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if data.get("schema") != "DGC_EXTERNAL_SOURCE_AUTHORITY_REGISTRY_V1":
        raise AssertionError("wrong external source authority schema")
    families = data.get("families", [])
    if {row.get("family_id") for row in families} != {"SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"}:
        raise AssertionError("registry must contain exactly both frozen external families")

    for row in families:
        if row.get("stage") != "SOURCE_VERIFIED":
            raise AssertionError(f"unexpected source stage for {row.get('family_id')}")
        if row.get("materialized_tree_sha256") is not None:
            raise AssertionError("source verification must not imply materialized tree")
        if row.get("materialized_task_manifest_sha256") is not None:
            raise AssertionError("source verification must not imply materialized task manifest")
        if row.get("execution_population_digest") is not None:
            raise AssertionError("source verification must not imply execution")
        verification = row["verification"]
        if verification.get("materialized") is not False:
            raise AssertionError("metadata/Git verification is not local materialization")
        if _digest(row["identity"]) != row["upstream_identity_digest"]:
            raise AssertionError(f"identity digest mismatch for {row['family_id']}")
        if _digest(verification) != row["source_verification_evidence_digest"]:
            raise AssertionError(f"verification evidence digest mismatch for {row['family_id']}")
        authority = ExternalSourceAuthority(
            family_id=row["family_id"],
            stage=ExternalSourceStage.SOURCE_VERIFIED,
            upstream_revision=row["upstream_revision"],
            upstream_identity_digest=row["upstream_identity_digest"],
            source_verification_method=verification["verification_method"],
            source_verification_evidence_digest=row["source_verification_evidence_digest"],
        )
        if authority.digest != row["authority_digest"]:
            raise AssertionError(f"authority digest mismatch for {row['family_id']}")

    if data.get("product_promotion_authorized") is not False:
        raise AssertionError("source authority alone cannot authorize product promotion")
    print("DGC-EXTERNAL-SOURCE-GATE: PASS — 2/2 source identities verified; materialized=0; executed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
