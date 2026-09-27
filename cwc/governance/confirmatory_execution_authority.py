from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.confirmatory_generation import certify_confirmatory_completion
from cwc.governance.confirmatory_root_authority import (
    REFERENCE_SCHEMA,
    REGISTRY_SCHEMA,
    _json as _root_json,
    _materialized_authority,
    verify_confirmatory_root_authority_document,
)
from cwc.governance.execution_authority_binding import promote_executed_from_confirmatory
from cwc.governance.execution_evidence_bundle import VerifiedExecutionBundle, verify_execution_bundle
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

SCHEMA = "DGC_CONFIRMATORY_EXECUTION_AUTHORITY_V1"


class ConfirmatoryExecutionAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ConfirmatoryExecutionAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _finite_nonnegative(name: str, value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfirmatoryExecutionAuthorityError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or result < 0:
        raise ConfirmatoryExecutionAuthorityError(f"{name} must be finite and >= 0")
    return result


@dataclass(frozen=True, slots=True)
class _RootAdapter:
    family_id: str
    source_authority_digest: str
    root_digest: str
    distributed_spec_digest: str
    expected_work_units: int


@dataclass(frozen=True, slots=True)
class ConfirmatoryExecutionAuthority:
    family_id: str
    root_authority_digest: str
    root_digest: str
    distributed_spec_digest: str
    execution_bundle_digest: str
    execution_bundle_payload_manifest_sha256: str
    materialized_source_authority_digest: str
    executed_source_authority_digest: str
    execution_population_digest: str
    result_population_digest: str
    audit_root_digest: str
    unit_evidence_population_digest: str
    metric_population_digest: str
    expected_work_units: int
    committed_work_units: int
    total_cost_usd: float
    completion_certificate: dict[str, object]
    confirmatory_completion_certificate: dict[str, object]
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "family_id": self.family_id,
            "root_authority_digest": self.root_authority_digest,
            "root_digest": self.root_digest,
            "distributed_spec_digest": self.distributed_spec_digest,
            "execution_bundle_digest": self.execution_bundle_digest,
            "execution_bundle_payload_manifest_sha256": self.execution_bundle_payload_manifest_sha256,
            "materialized_source_authority_digest": self.materialized_source_authority_digest,
            "executed_source_authority_digest": self.executed_source_authority_digest,
            "execution_population_digest": self.execution_population_digest,
            "result_population_digest": self.result_population_digest,
            "audit_root_digest": self.audit_root_digest,
            "unit_evidence_population_digest": self.unit_evidence_population_digest,
            "metric_population_digest": self.metric_population_digest,
            "expected_work_units": self.expected_work_units,
            "committed_work_units": self.committed_work_units,
            "total_cost_usd": self.total_cost_usd,
            "completion_certificate": self.completion_certificate,
            "confirmatory_completion_certificate": self.confirmatory_completion_certificate,
            "authority_digest": self.authority_digest,
            "confirmatory_executed": True,
            "p9_evaluation_authorized": True,
            "product_promotion_authorized": False,
        }


def _root_adapter(root_authority: Mapping[str, object]) -> _RootAdapter:
    root = root_authority.get("root")
    if not isinstance(root, Mapping):
        raise ConfirmatoryExecutionAuthorityError("confirmatory root payload missing")
    try:
        expected = int(root["expected_work_units"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfirmatoryExecutionAuthorityError("invalid expected_work_units in confirmatory root") from exc
    if expected <= 0:
        raise ConfirmatoryExecutionAuthorityError("confirmatory root expected_work_units must be > 0")
    return _RootAdapter(
        family_id=str(root_authority.get("family_id", "")),
        source_authority_digest=_sha("root source_authority_digest", root.get("source_authority_digest")),
        root_digest=_sha("root_digest", root.get("root_digest")),
        distributed_spec_digest=_sha(
            "distributed_spec_digest", root_authority.get("distributed_spec_digest")
        ),
        expected_work_units=expected,
    )


def _population_digests(bundle: VerifiedExecutionBundle) -> tuple[str, str]:
    evidence_rows = [
        (row.unit.stable_id, row.evidence_digest, row.record_digest)
        for row in sorted(bundle.results, key=lambda item: item.unit)
    ]
    metric_rows = [
        (
            row.unit.stable_id,
            row.quality,
            row.catastrophic_regret,
            row.actual_cost_usd,
        )
        for row in sorted(bundle.results, key=lambda item: item.unit)
    ]
    return (
        sha256_bytes(canonical_json_bytes(evidence_rows)),
        sha256_bytes(canonical_json_bytes(metric_rows)),
    )


def build_confirmatory_execution_authority(
    *,
    execution_bundle_root: Path,
    confirmatory_root_authority_path: Path,
    materialization_reference_path: Path,
    source_registry_path: Path,
) -> ConfirmatoryExecutionAuthority:
    root_authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    root = _root_adapter(root_authority)
    bundle = verify_execution_bundle(
        Path(execution_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
    )
    root_authority_digest = _sha("root authority_digest", root_authority.get("authority_digest"))
    if bundle.root_authority_digest != root_authority_digest:
        raise ConfirmatoryExecutionAuthorityError("execution bundle root authority mismatch")
    if bundle.root_digest != root.root_digest or bundle.distributed_spec_digest != root.distributed_spec_digest:
        raise ConfirmatoryExecutionAuthorityError("execution bundle root/spec lineage mismatch")
    if bundle.family_id != root.family_id:
        raise ConfirmatoryExecutionAuthorityError("execution bundle family differs from root")

    reference = _root_json(Path(materialization_reference_path), REFERENCE_SCHEMA)
    registry = _root_json(Path(source_registry_path), REGISTRY_SCHEMA)
    materialized = _materialized_authority(
        reference=reference,
        registry=registry,
        family_id=root.family_id,
    )
    materialized_digest = materialized.digest
    if materialized_digest != _sha(
        "root materialized_source_authority_digest",
        root_authority.get("materialized_source_authority_digest"),
    ):
        raise ConfirmatoryExecutionAuthorityError("materialized authority differs from frozen root lineage")
    if materialized_digest != root.source_authority_digest:
        raise ConfirmatoryExecutionAuthorityError("confirmatory root source authority is not the reconstructed materialized authority")

    try:
        completion = certify_confirmatory_completion(root, bundle.completion)
        executed = promote_executed_from_confirmatory(
            materialized,
            root=root,
            completion=completion,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise ConfirmatoryExecutionAuthorityError("confirmatory completion cannot promote source authority to EXECUTED") from exc

    evidence_population_digest, metric_population_digest = _population_digests(bundle)
    completion_doc = asdict(bundle.completion)
    confirmatory_doc = asdict(completion)
    payload = {
        "family_id": root.family_id,
        "root_authority_digest": root_authority_digest,
        "root_digest": root.root_digest,
        "distributed_spec_digest": root.distributed_spec_digest,
        "execution_bundle_digest": bundle.bundle_digest,
        "execution_bundle_payload_manifest_sha256": bundle.payload_manifest_sha256,
        "materialized_source_authority_digest": materialized_digest,
        "executed_source_authority_digest": executed.digest,
        "execution_population_digest": completion.execution_population_digest,
        "result_population_digest": completion.result_population_digest,
        "audit_root_digest": completion.audit_root_digest,
        "unit_evidence_population_digest": evidence_population_digest,
        "metric_population_digest": metric_population_digest,
        "expected_work_units": completion.expected_work_units,
        "committed_work_units": completion.committed_work_units,
        "total_cost_usd": completion.total_cost_usd,
        "completion_certificate": completion_doc,
        "confirmatory_completion_certificate": confirmatory_doc,
    }
    return ConfirmatoryExecutionAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_confirmatory_execution_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ConfirmatoryExecutionAuthorityError("confirmatory execution authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfirmatoryExecutionAuthorityError("invalid confirmatory execution authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ConfirmatoryExecutionAuthorityError("unexpected confirmatory execution authority schema")
    if doc.get("confirmatory_executed") is not True or doc.get("p9_evaluation_authorized") is not True:
        raise ConfirmatoryExecutionAuthorityError("execution authority must explicitly authorize only P9 evaluation")
    if doc.get("product_promotion_authorized") is not False:
        raise ConfirmatoryExecutionAuthorityError("execution authority cannot authorize product promotion")

    payload_keys = (
        "family_id", "root_authority_digest", "root_digest", "distributed_spec_digest",
        "execution_bundle_digest", "execution_bundle_payload_manifest_sha256",
        "materialized_source_authority_digest", "executed_source_authority_digest",
        "execution_population_digest", "result_population_digest", "audit_root_digest",
        "unit_evidence_population_digest", "metric_population_digest", "expected_work_units",
        "committed_work_units", "total_cost_usd", "completion_certificate",
        "confirmatory_completion_certificate",
    )
    try:
        payload = {key: doc[key] for key in payload_keys}
    except KeyError as exc:
        raise ConfirmatoryExecutionAuthorityError("execution authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise ConfirmatoryExecutionAuthorityError("confirmatory execution authority digest mismatch")

    for name in (
        "root_authority_digest", "root_digest", "distributed_spec_digest", "execution_bundle_digest",
        "execution_bundle_payload_manifest_sha256", "materialized_source_authority_digest",
        "executed_source_authority_digest", "execution_population_digest", "result_population_digest",
        "audit_root_digest", "unit_evidence_population_digest", "metric_population_digest",
    ):
        _sha(name, doc.get(name))
    try:
        expected = int(doc["expected_work_units"])
        committed = int(doc["committed_work_units"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfirmatoryExecutionAuthorityError("execution authority work-unit counts malformed") from exc
    if expected <= 0 or committed != expected:
        raise ConfirmatoryExecutionAuthorityError("execution authority requires complete frozen work population")
    total_cost = _finite_nonnegative("total_cost_usd", doc.get("total_cost_usd"))

    raw = doc.get("completion_certificate")
    confirmatory = doc.get("confirmatory_completion_certificate")
    if not isinstance(raw, Mapping) or not isinstance(confirmatory, Mapping):
        raise ConfirmatoryExecutionAuthorityError("completion certificates missing")
    if raw.get("complete") is not True or confirmatory.get("complete") is not True:
        raise ConfirmatoryExecutionAuthorityError("completion certificates must be complete")
    for key in ("expected_units", "committed_units"):
        expected_value = expected if key == "expected_units" else committed
        if int(raw.get(key, -1)) != expected_value:
            raise ConfirmatoryExecutionAuthorityError("raw completion work-unit count mismatch")
    if confirmatory.get("expected_work_units") != expected or confirmatory.get("committed_work_units") != committed:
        raise ConfirmatoryExecutionAuthorityError("confirmatory completion work-unit count mismatch")
    if confirmatory.get("generation_root_digest") != doc.get("root_digest"):
        raise ConfirmatoryExecutionAuthorityError("confirmatory completion root mismatch")
    if confirmatory.get("distributed_spec_digest") != doc.get("distributed_spec_digest"):
        raise ConfirmatoryExecutionAuthorityError("confirmatory completion distributed spec mismatch")
    if confirmatory.get("result_population_digest") != doc.get("result_population_digest"):
        raise ConfirmatoryExecutionAuthorityError("confirmatory completion result population mismatch")
    if confirmatory.get("audit_root_digest") != doc.get("audit_root_digest"):
        raise ConfirmatoryExecutionAuthorityError("confirmatory completion audit root mismatch")
    if not math.isclose(float(confirmatory.get("total_cost_usd", -1)), total_cost, rel_tol=0.0, abs_tol=1e-12):
        raise ConfirmatoryExecutionAuthorityError("confirmatory completion total cost mismatch")

    recomputed_execution_population = sha256_bytes(canonical_json_bytes({
        "generation_root_digest": doc["root_digest"],
        "result_population_digest": doc["result_population_digest"],
        "audit_root_digest": doc["audit_root_digest"],
        "expected_work_units": expected,
        "committed_work_units": committed,
        "total_cost_usd": total_cost,
    }))
    if recomputed_execution_population != doc.get("execution_population_digest"):
        raise ConfirmatoryExecutionAuthorityError("execution population digest cannot be reconstructed")
    if confirmatory.get("execution_population_digest") != doc.get("execution_population_digest"):
        raise ConfirmatoryExecutionAuthorityError("confirmatory completion execution population mismatch")
    if doc.get("executed_source_authority_digest") == doc.get("materialized_source_authority_digest"):
        raise ConfirmatoryExecutionAuthorityError("EXECUTED authority must differ from MATERIALIZED_VERIFIED authority")
    return doc
