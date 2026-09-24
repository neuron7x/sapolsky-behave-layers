from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cwc.governance.ccf_oracle_audit_authority import verify_ccf_oracle_audit_authority_document
from cwc.governance.executed_p9_authority import verify_executed_p9_authority_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

SCHEMA = "DGC_P9_SCIENTIFIC_AUTHORITY_V1"


class P9ScientificAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P9ScientificAuthorityError(f"{name} must be lowercase SHA-256")
    return text


@dataclass(frozen=True, slots=True)
class P9ScientificAuthority:
    family_id: str
    executed_p9_authority_digest: str
    ccf_oracle_audit_authority_digest: str
    execution_authority_digest: str
    execution_population_digest: str
    execution_bundle_digest: str
    physical_cost_bundle_digest: str
    physical_cost_population_digest: str
    harness_freeze_digest: str
    confirmatory_task_manifest_digest: str
    p9_certificate_digest: str
    p9_supported: bool
    physical_cost_accounting_verified: bool
    net_cost_superiority_supported: bool
    ccf_headroom_audit_complete: bool
    ccf_total_value_regret_units: int
    ccf_total_avoidable_cost_units: int
    ccf_max_value_regret_units: int
    ccf_max_avoidable_cost_units: int
    generalization_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "family_id": self.family_id,
            "executed_p9_authority_digest": self.executed_p9_authority_digest,
            "ccf_oracle_audit_authority_digest": self.ccf_oracle_audit_authority_digest,
            "execution_authority_digest": self.execution_authority_digest,
            "execution_population_digest": self.execution_population_digest,
            "execution_bundle_digest": self.execution_bundle_digest,
            "physical_cost_bundle_digest": self.physical_cost_bundle_digest,
            "physical_cost_population_digest": self.physical_cost_population_digest,
            "harness_freeze_digest": self.harness_freeze_digest,
            "confirmatory_task_manifest_digest": self.confirmatory_task_manifest_digest,
            "p9_certificate_digest": self.p9_certificate_digest,
            "p9_supported": self.p9_supported,
            "physical_cost_accounting_verified": self.physical_cost_accounting_verified,
            "net_cost_superiority_supported": self.net_cost_superiority_supported,
            "ccf_headroom_audit_complete": self.ccf_headroom_audit_complete,
            "ccf_total_value_regret_units": self.ccf_total_value_regret_units,
            "ccf_total_avoidable_cost_units": self.ccf_total_avoidable_cost_units,
            "ccf_max_value_regret_units": self.ccf_max_value_regret_units,
            "ccf_max_avoidable_cost_units": self.ccf_max_avoidable_cost_units,
            "generalization_authorized": self.generalization_authorized,
            "authority_digest": self.authority_digest,
            "product_promotion_authorized": False,
        }


def build_p9_scientific_authority(
    *,
    executed_p9_authority_path: Path,
    ccf_oracle_audit_authority_path: Path,
) -> P9ScientificAuthority:
    p9 = verify_executed_p9_authority_document(Path(executed_p9_authority_path))
    ccf = verify_ccf_oracle_audit_authority_document(Path(ccf_oracle_audit_authority_path))
    if p9.get("family_id") != ccf.get("family_id"):
        raise P9ScientificAuthorityError("P9 and CCF family lineage mismatch")
    for field in (
        "execution_authority_digest", "execution_population_digest", "execution_bundle_digest",
        "physical_cost_bundle_digest", "physical_cost_population_digest", "harness_freeze_digest",
        "confirmatory_task_manifest_digest",
    ):
        if p9.get(field) != ccf.get(field):
            raise P9ScientificAuthorityError(f"P9 and CCF lineage mismatch for {field}")
    p9_supported = bool(p9.get("p9_supported"))
    physical = p9.get("physical_cost_accounting_verified") is True
    net_cost = p9.get("net_cost_superiority_supported") is True
    ccf_complete = ccf.get("headroom_audit_complete") is True
    generalization = p9_supported and physical and net_cost and ccf_complete
    payload = {
        "family_id": str(p9["family_id"]),
        "executed_p9_authority_digest": _sha("executed P9 authority_digest", p9.get("authority_digest")),
        "ccf_oracle_audit_authority_digest": _sha("CCF authority_digest", ccf.get("authority_digest")),
        "execution_authority_digest": _sha("execution_authority_digest", p9.get("execution_authority_digest")),
        "execution_population_digest": _sha("execution_population_digest", p9.get("execution_population_digest")),
        "execution_bundle_digest": _sha("execution_bundle_digest", p9.get("execution_bundle_digest")),
        "physical_cost_bundle_digest": _sha("physical_cost_bundle_digest", p9.get("physical_cost_bundle_digest")),
        "physical_cost_population_digest": _sha("physical_cost_population_digest", p9.get("physical_cost_population_digest")),
        "harness_freeze_digest": _sha("harness_freeze_digest", p9.get("harness_freeze_digest")),
        "confirmatory_task_manifest_digest": _sha(
            "confirmatory_task_manifest_digest", p9.get("confirmatory_task_manifest_digest")
        ),
        "p9_certificate_digest": _sha("p9_certificate_digest", p9.get("p9_certificate_digest")),
        "p9_supported": p9_supported,
        "physical_cost_accounting_verified": physical,
        "net_cost_superiority_supported": net_cost,
        "ccf_headroom_audit_complete": ccf_complete,
        "ccf_total_value_regret_units": int(ccf["total_value_regret_units"]),
        "ccf_total_avoidable_cost_units": int(ccf["total_avoidable_cost_units"]),
        "ccf_max_value_regret_units": int(ccf["max_value_regret_units"]),
        "ccf_max_avoidable_cost_units": int(ccf["max_avoidable_cost_units"]),
        "generalization_authorized": generalization,
    }
    return P9ScientificAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_p9_scientific_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P9ScientificAuthorityError("P9 scientific authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P9ScientificAuthorityError("invalid P9 scientific authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P9ScientificAuthorityError("unexpected P9 scientific authority schema")
    if doc.get("product_promotion_authorized") is not False:
        raise P9ScientificAuthorityError("P9 scientific authority cannot authorize product promotion")
    keys = (
        "family_id", "executed_p9_authority_digest", "ccf_oracle_audit_authority_digest",
        "execution_authority_digest", "execution_population_digest", "execution_bundle_digest",
        "physical_cost_bundle_digest", "physical_cost_population_digest", "harness_freeze_digest",
        "confirmatory_task_manifest_digest", "p9_certificate_digest", "p9_supported",
        "physical_cost_accounting_verified", "net_cost_superiority_supported",
        "ccf_headroom_audit_complete", "ccf_total_value_regret_units",
        "ccf_total_avoidable_cost_units", "ccf_max_value_regret_units",
        "ccf_max_avoidable_cost_units", "generalization_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise P9ScientificAuthorityError("P9 scientific authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise P9ScientificAuthorityError("P9 scientific authority digest mismatch")
    derived = (
        doc.get("p9_supported") is True
        and doc.get("physical_cost_accounting_verified") is True
        and doc.get("net_cost_superiority_supported") is True
        and doc.get("ccf_headroom_audit_complete") is True
    )
    if doc.get("generalization_authorized") is not derived:
        raise P9ScientificAuthorityError("generalization authority is not derivable from P9+physical-cost+CCF evidence")
    return doc
