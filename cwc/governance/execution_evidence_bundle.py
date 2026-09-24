from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.cost_accounting import ProviderRateCard
from cwc.governance.distributed_eval_control import CompletionCertificate, DistributedEvalSpec, WorkUnitId
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.physical_cost_evidence import (
    PRODUCT_COST_COMPONENTS,
    CostAuthority,
    CostComponentEvidence,
    certify_physical_trial_cost,
)
from cwc.governance.provider_trace import (
    ProviderCallIdKind,
    ProviderUsageTrace,
    TraceAuthority,
)

BUNDLE_SCHEMA = "DGC_CONFIRMATORY_EXECUTION_BUNDLE_V1"
RESULT_SCHEMA = "DGC_CONFIRMATORY_RESULT_V1"
AUDIT_SCHEMA = "DGC_DISTRIBUTED_AUDIT_LOG_V1"
EVIDENCE_SCHEMA = "DGC_UNIT_EXECUTION_EVIDENCE_V1"
RISK_RESPONSE_SCHEMA = "DGC_RISK_ENDPOINT_RESPONSE_V1"


class ExecutionEvidenceError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ExecutionEvidenceError(f"{name} must be lowercase SHA-256")
    return text


def _req(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise ExecutionEvidenceError(f"{name} required")
    return text


def _nonnegative_int(name: str, value: object) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ExecutionEvidenceError(f"{name} must be an integer") from exc
    if result < 0:
        raise ExecutionEvidenceError(f"{name} must be >= 0")
    return result


def _finite(name: str, value: object, *, lower: float | None = None, upper: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ExecutionEvidenceError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ExecutionEvidenceError(f"{name} must be finite")
    if lower is not None and result < lower:
        raise ExecutionEvidenceError(f"{name} below lower bound")
    if upper is not None and result > upper:
        raise ExecutionEvidenceError(f"{name} above upper bound")
    return result


def _safe_relative(root: Path, value: object, *, require_file: bool = True) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise ExecutionEvidenceError("execution evidence path must be relative and non-traversing")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ExecutionEvidenceError(f"execution evidence symlink rejected: {rel.as_posix()}")
    path = root / rel
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ExecutionEvidenceError("execution evidence path escapes bundle root") from exc
    if require_file and not resolved.is_file():
        raise ExecutionEvidenceError(f"execution evidence file missing: {rel.as_posix()}")
    return resolved, rel.as_posix()


def _json(path: Path, *, schema: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ExecutionEvidenceError(f"missing regular JSON evidence: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionEvidenceError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise ExecutionEvidenceError(f"unexpected schema for {path}")
    return doc


def _unit_from_mapping(value: object) -> WorkUnitId:
    if not isinstance(value, Mapping):
        raise ExecutionEvidenceError("result unit must be an object")
    try:
        return WorkUnitId(
            task_id=str(value["task_id"]),
            policy_id=str(value["policy_id"]),
            replicate=int(value["replicate"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionEvidenceError("invalid result work unit") from exc


def canonical_result_payload_digest(payload: Mapping[str, object]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(payload)))


@dataclass(frozen=True, slots=True)
class VerifiedExecutionResult:
    unit: WorkUnitId
    attempt: int
    worker_id: str
    committed_tick: int
    result_payload: dict[str, object]
    result_digest: str
    quality: float
    catastrophic_regret: float
    actual_cost_usd: float
    evidence_path: str
    evidence_digest: str
    record_digest: str
    commit_event_sequence: int
    provider_call_identities: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class VerifiedExecutionBundle:
    family_id: str
    root_authority_digest: str
    root_digest: str
    distributed_spec_digest: str
    payload_manifest_sha256: str
    audit_root_digest: str
    result_population_digest: str
    total_cost_usd: float
    results: tuple[VerifiedExecutionResult, ...]
    completion: CompletionCertificate
    bundle_digest: str


def _safe_repository_subject(root: Path, value: object) -> Path:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise ExecutionEvidenceError("frozen component path must be repository-relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ExecutionEvidenceError("frozen component path contains symlink")
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ExecutionEvidenceError("frozen component path escapes repository root") from exc
    if not path.is_file():
        raise ExecutionEvidenceError("frozen component file missing from repository")
    return path


def _strict_execution_lineage(
    *,
    root_authority: Mapping[str, object],
    execution_manifest_freeze_path: Path | None,
    repository_root: Path | None,
) -> tuple[str | None, str | None, dict[tuple[str, str, str], ProviderRateCard] | None]:
    if execution_manifest_freeze_path is None:
        return None, None, None
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    freeze_digest = _sha("execution freeze_digest", execution.get("freeze_digest"))
    if freeze_digest != _sha(
        "root execution_manifest_freeze_digest",
        root_authority.get("execution_manifest_freeze_digest"),
    ):
        raise ExecutionEvidenceError("execution bundle replay uses a different execution freeze")
    rows = execution.get("components")
    if not isinstance(rows, list):
        raise ExecutionEvidenceError("execution freeze component population missing")
    by_name = {
        str(row.get("component")): row
        for row in rows
        if isinstance(row, Mapping)
    }
    if "pricing_snapshot" not in by_name or "risk_endpoint_manifest" not in by_name:
        raise ExecutionEvidenceError("execution freeze lacks pricing/risk components")
    pricing_sha = _sha("frozen pricing component sha256", by_name["pricing_snapshot"].get("sha256"))
    risk_sha = _sha("frozen risk component sha256", by_name["risk_endpoint_manifest"].get("sha256"))
    if repository_root is None:
        return pricing_sha, risk_sha, None

    repo_root = Path(repository_root).resolve()
    pricing_path = _safe_repository_subject(repo_root, by_name["pricing_snapshot"].get("path"))
    if sha256_file(pricing_path) != pricing_sha:
        raise ExecutionEvidenceError("repository pricing bytes differ from execution freeze")
    risk_path = _safe_repository_subject(repo_root, by_name["risk_endpoint_manifest"].get("path"))
    if sha256_file(risk_path) != risk_sha:
        raise ExecutionEvidenceError("repository risk endpoint bytes differ from execution freeze")
    pricing_doc = _json(pricing_path, schema="DGC_PRICING_SNAPSHOT_V1")
    captured_at = _req("pricing captured_at", pricing_doc.get("captured_at"))
    entries = pricing_doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ExecutionEvidenceError("frozen pricing entries missing")
    expected: dict[tuple[str, str, str], ProviderRateCard] = {}
    try:
        for row in entries:
            if not isinstance(row, Mapping):
                raise ExecutionEvidenceError("invalid frozen pricing row")
            identity = (
                _req("pricing provider", row.get("provider")),
                _req("pricing model_id", row.get("model_id")),
                _req("pricing model_version", row.get("model_version")),
            )
            if identity in expected:
                raise ExecutionEvidenceError("duplicate frozen pricing identity")
            if str(row.get("currency", "")) != "USD":
                raise ExecutionEvidenceError("frozen pricing currency is not USD")
            expected[identity] = ProviderRateCard(
                provider=identity[0],
                model=identity[1],
                input_usd_per_million=float(row["input_per_million"]),
                cached_input_usd_per_million=float(row["cached_input_per_million"]),
                cache_write_usd_per_million=float(row["cache_write_per_million"]),
                long_cache_write_usd_per_million=float(row["long_cache_write_per_million"]),
                output_usd_per_million=float(row["output_per_million"]),
                source_uri=str(row["source_uri"]),
                retrieved_at=captured_at,
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionEvidenceError("invalid frozen pricing manifest") from exc
    return pricing_sha, risk_sha, expected


def _verify_unit_evidence(
    path: Path,
    *,
    result_payload: Mapping[str, object],
    actual_cost_usd: float,
    unit: WorkUnitId,
    expected_pricing_sha: str | None = None,
    expected_risk_sha: str | None = None,
    expected_rate_cards: Mapping[tuple[str, str, str], ProviderRateCard] | None = None,
) -> tuple[tuple[str, str], ...]:
    doc = _json(path, schema=EVIDENCE_SCHEMA)

    response = doc.get("response")
    if not isinstance(response, Mapping):
        raise ExecutionEvidenceError("execution evidence missing adapter response")
    adapter_digest = sha256_bytes(canonical_json_bytes(dict(response)))
    if _sha("adapter_response_digest", doc.get("adapter_response_digest")) != adapter_digest:
        raise ExecutionEvidenceError("adapter response digest mismatch")
    if _sha(
        "result adapter_response_digest", result_payload.get("adapter_response_digest")
    ) != adapter_digest:
        raise ExecutionEvidenceError("result is not bound to adapter response")

    trace = response.get("trace")
    if not isinstance(trace, Mapping) or not trace:
        raise ExecutionEvidenceError("execution evidence missing raw trace metadata")
    trace_digest = sha256_bytes(canonical_json_bytes(dict(trace)))
    if _sha("trace_digest", doc.get("trace_digest")) != trace_digest:
        raise ExecutionEvidenceError("raw trace digest mismatch")
    if _sha("result trace_digest", result_payload.get("trace_digest")) != trace_digest:
        raise ExecutionEvidenceError("result is not bound to raw trace")

    risk = doc.get("risk_endpoint_response")
    if not isinstance(risk, Mapping) or risk.get("schema") != RISK_RESPONSE_SCHEMA:
        raise ExecutionEvidenceError("execution evidence missing frozen risk response")
    evidence = risk.get("evidence")
    if not isinstance(evidence, Mapping) or not evidence:
        raise ExecutionEvidenceError("risk response requires non-empty evidence")
    risk_digest = sha256_bytes(canonical_json_bytes(dict(risk)))
    if _sha("risk_endpoint_response_digest", doc.get("risk_endpoint_response_digest")) != risk_digest:
        raise ExecutionEvidenceError("risk response digest mismatch")
    if _sha(
        "result risk_endpoint_response_digest", result_payload.get("risk_endpoint_response_digest")
    ) != risk_digest:
        raise ExecutionEvidenceError("result is not bound to frozen risk response")
    risk_value = _finite(
        "risk response catastrophic_regret",
        risk.get("catastrophic_regret"),
        lower=0.0,
        upper=1.0,
    )
    result_risk = _finite(
        "result catastrophic_regret",
        result_payload.get("catastrophic_regret"),
        lower=0.0,
        upper=1.0,
    )
    if not math.isclose(risk_value, result_risk, rel_tol=0.0, abs_tol=1e-12):
        raise ExecutionEvidenceError("result catastrophic_regret differs from frozen risk response")

    pricing_sha = _sha(
        "pricing_snapshot_manifest_sha256", doc.get("pricing_snapshot_manifest_sha256")
    )
    if expected_pricing_sha is not None and pricing_sha != expected_pricing_sha:
        raise ExecutionEvidenceError("evidence pricing snapshot differs from execution freeze")
    if _sha(
        "result pricing_snapshot_manifest_sha256",
        result_payload.get("pricing_snapshot_manifest_sha256"),
    ) != pricing_sha:
        raise ExecutionEvidenceError("result is not bound to frozen pricing snapshot")
    risk_manifest_sha = _sha(
        "risk_endpoint_manifest_sha256", doc.get("risk_endpoint_manifest_sha256")
    )
    if expected_risk_sha is not None and risk_manifest_sha != expected_risk_sha:
        raise ExecutionEvidenceError("evidence risk endpoint differs from execution freeze")
    if _sha(
        "result risk_endpoint_manifest_sha256",
        result_payload.get("risk_endpoint_manifest_sha256"),
    ) != risk_manifest_sha:
        raise ExecutionEvidenceError("result is not bound to frozen risk endpoint manifest")

    rate_rows = doc.get("provider_rate_cards")
    if not isinstance(rate_rows, list) or not rate_rows:
        raise ExecutionEvidenceError("execution evidence requires provider rate cards")
    rate_cards: dict[tuple[str, str, str], ProviderRateCard] = {}
    try:
        for row in rate_rows:
            if not isinstance(row, Mapping):
                raise ExecutionEvidenceError("invalid provider rate card row")
            identity = (
                _req("rate-card provider", row.get("provider")),
                _req("rate-card model", row.get("model")),
                _req("rate-card model_version", row.get("model_version")),
            )
            if identity in rate_cards:
                raise ExecutionEvidenceError("duplicate provider rate-card identity")
            card = ProviderRateCard(
                provider=identity[0],
                model=identity[1],
                input_usd_per_million=float(row["input_usd_per_million"]),
                cached_input_usd_per_million=float(row["cached_input_usd_per_million"]),
                cache_write_usd_per_million=float(row["cache_write_usd_per_million"]),
                long_cache_write_usd_per_million=float(row["long_cache_write_usd_per_million"]),
                output_usd_per_million=float(row["output_usd_per_million"]),
                source_uri=str(row["source_uri"]),
                retrieved_at=str(row["retrieved_at"]),
            )
            if _sha("rate_card_digest", row.get("rate_card_digest")) != card.digest:
                raise ExecutionEvidenceError("provider rate-card digest mismatch")
            if expected_rate_cards is not None:
                expected_card = expected_rate_cards.get(identity)
                if expected_card is None or expected_card.digest != card.digest:
                    raise ExecutionEvidenceError("embedded provider rate card differs from frozen pricing")
            rate_cards[identity] = card
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionEvidenceError("invalid provider rate-card evidence") from exc

    raw_provider_rows = response.get("provider_usage_traces")
    evidence_provider_rows = doc.get("provider_usage_traces")
    if (
        not isinstance(raw_provider_rows, list)
        or not raw_provider_rows
        or not isinstance(evidence_provider_rows, list)
        or len(raw_provider_rows) != len(evidence_provider_rows)
    ):
        raise ExecutionEvidenceError("provider usage population missing or inconsistent")
    expected_trace_docs: list[dict[str, object]] = []
    metered_rows: list[tuple[str, str]] = []
    call_ids: set[tuple[str, str]] = set()
    model_usd_rows: list[float] = []
    for raw in raw_provider_rows:
        if not isinstance(raw, Mapping):
            raise ExecutionEvidenceError("invalid raw provider usage trace")
        model_version = _req("provider trace model_version", raw.get("model_version"))
        identity = (
            _req("provider trace provider", raw.get("provider")),
            _req("provider trace model", raw.get("model")),
            model_version,
        )
        card = rate_cards.get(identity)
        if card is None:
            raise ExecutionEvidenceError("provider trace has no embedded frozen rate card")
        try:
            provider_trace = ProviderUsageTrace(
                trace_id=str(raw["trace_id"]),
                decision_id=str(raw["decision_id"]),
                policy_id=str(raw["policy_id"]),
                authority=TraceAuthority(str(raw["authority"])),
                provider=identity[0],
                model=identity[1],
                rate_card_digest=str(raw["rate_card_digest"]),
                input_tokens=int(raw["input_tokens"]),
                cached_input_tokens=int(raw.get("cached_input_tokens", 0)),
                cache_write_tokens=int(raw.get("cache_write_tokens", 0)),
                long_cache_write_tokens=int(raw.get("long_cache_write_tokens", 0)),
                output_tokens=int(raw["output_tokens"]),
                provider_call_id=str(raw["provider_call_id"]),
                provider_call_id_kind=ProviderCallIdKind(str(raw["provider_call_id_kind"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionEvidenceError("malformed provider usage trace") from exc
        if provider_trace.authority is not TraceAuthority.PROVIDER_LIVE:
            raise ExecutionEvidenceError("confirmatory provider trace is not PROVIDER_LIVE")
        if provider_trace.decision_id != unit.stable_id or provider_trace.policy_id != unit.policy_id:
            raise ExecutionEvidenceError("provider trace decision/policy identity mismatch")
        if provider_trace.rate_card_digest != card.digest:
            raise ExecutionEvidenceError("provider trace rate-card digest mismatch")
        call_identity = (
            provider_trace.provider_call_id_kind.value,
            str(provider_trace.provider_call_id),
        )
        if call_identity in call_ids:
            raise ExecutionEvidenceError("duplicate provider call id")
        call_ids.add(call_identity)
        metered = provider_trace.meter(card)
        model_usd_rows.append(metered.model_token_usd)
        expected_trace_docs.append({
            "trace_digest": provider_trace.digest,
            "trace_id": provider_trace.trace_id,
            "decision_id": provider_trace.decision_id,
            "policy_id": provider_trace.policy_id,
            "authority": provider_trace.authority.value,
            "provider_call_id": provider_trace.provider_call_id,
            "provider_call_id_kind": provider_trace.provider_call_id_kind.value,
            "provider": provider_trace.provider,
            "model": provider_trace.model,
            "model_version": model_version,
            "rate_card_digest": provider_trace.rate_card_digest,
            "input_tokens": provider_trace.input_tokens,
            "cached_input_tokens": provider_trace.cached_input_tokens,
            "cache_write_tokens": provider_trace.cache_write_tokens,
            "long_cache_write_tokens": provider_trace.long_cache_write_tokens,
            "output_tokens": provider_trace.output_tokens,
            "model_token_usd": metered.model_token_usd,
        })
        metered_rows.append((provider_trace.digest, model_version))
    if evidence_provider_rows != expected_trace_docs:
        raise ExecutionEvidenceError("derived provider trace evidence differs from raw provider usage")
    provider_population_digest = sha256_bytes(canonical_json_bytes(sorted(metered_rows)))
    if _sha(
        "provider_trace_population_digest", doc.get("provider_trace_population_digest")
    ) != provider_population_digest:
        raise ExecutionEvidenceError("provider trace population digest mismatch")
    if _sha(
        "result provider_trace_population_digest",
        result_payload.get("provider_trace_population_digest"),
    ) != provider_population_digest:
        raise ExecutionEvidenceError("result is not bound to provider trace population")
    metered_model_usd = math.fsum(model_usd_rows)

    certificate = doc.get("physical_cost_certificate")
    if not isinstance(certificate, Mapping):
        raise ExecutionEvidenceError("execution evidence missing physical cost certificate")
    rows = certificate.get("components")
    if not isinstance(rows, list) or len(rows) != len(PRODUCT_COST_COMPONENTS):
        raise ExecutionEvidenceError("physical cost certificate component population mismatch")
    cost_evidence: dict[str, CostComponentEvidence] = {}
    try:
        for row in rows:
            if not isinstance(row, Mapping):
                raise ExecutionEvidenceError("invalid physical cost certificate row")
            component = str(row.get("component", ""))
            if component in cost_evidence or component not in PRODUCT_COST_COMPONENTS:
                raise ExecutionEvidenceError("physical cost certificate component identity mismatch")
            cost_evidence[component] = CostComponentEvidence(
                component=component,
                value_usd=float(row.get("value_usd")),
                authority=CostAuthority(str(row.get("authority"))),
                source_digest=_sha(
                    f"physical cost source digest {component}", row.get("source_digest")
                ),
            )
        rebuilt = certify_physical_trial_cost(
            trial_id=_req("physical cost trial_id", certificate.get("trial_id")),
            evidence=cost_evidence,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise ExecutionEvidenceError("invalid physical cost certificate") from exc
    model_component = cost_evidence.get("model_usd")
    if model_component is None:
        raise ExecutionEvidenceError("physical cost certificate missing model_usd")
    if model_component.authority is not CostAuthority.PROVIDER_METER:
        raise ExecutionEvidenceError("model_usd must use PROVIDER_METER authority")
    if model_component.source_digest != provider_population_digest:
        raise ExecutionEvidenceError("model_usd source is not provider trace population")
    if not math.isclose(
        model_component.value_usd,
        metered_model_usd,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ExecutionEvidenceError("model_usd differs from replayed provider token cost")

    if _sha("physical cost certificate digest", certificate.get("digest")) != rebuilt.digest:
        raise ExecutionEvidenceError("physical cost certificate digest mismatch")
    if _sha(
        "result physical cost certificate digest",
        result_payload.get("physical_cost_certificate_digest"),
    ) != rebuilt.digest:
        raise ExecutionEvidenceError("result is not bound to physical cost certificate")
    declared_total = _finite(
        "physical cost certificate total",
        certificate.get("total_operational_usd"),
        lower=0.0,
    )
    if not math.isclose(
        declared_total,
        rebuilt.cost.total_operational_usd,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ExecutionEvidenceError("physical cost certificate total mismatch")
    if not math.isclose(
        rebuilt.cost.total_operational_usd,
        actual_cost_usd,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ExecutionEvidenceError("result actual cost differs from physical cost certificate")
    return tuple(sorted(call_ids))


def _verify_audit_log(path: Path, *, spec_digest: str) -> tuple[list[dict[str, object]], str]:
    doc = _json(path, schema=AUDIT_SCHEMA)
    if _sha("audit spec_digest", doc.get("spec_digest")) != spec_digest:
        raise ExecutionEvidenceError("audit log belongs to a different distributed spec")
    events = doc.get("events")
    if not isinstance(events, list) or not events:
        raise ExecutionEvidenceError("non-empty distributed audit event list required")
    previous = "GENESIS"
    normalized: list[dict[str, object]] = []
    for expected_sequence, row in enumerate(events):
        if not isinstance(row, Mapping):
            raise ExecutionEvidenceError("invalid audit event")
        try:
            sequence = int(row["sequence"])
            kind = _req("audit kind", row["kind"])
            unit_id_raw = row.get("unit_id")
            unit_id = None if unit_id_raw is None else _req("audit unit_id", unit_id_raw)
            payload_digest = _sha("audit payload_digest", row["payload_digest"])
            observed_previous = str(row["previous_digest"])
            event_digest = _sha("audit event_digest", row["event_digest"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionEvidenceError("malformed audit event") from exc
        if sequence != expected_sequence or observed_previous != previous:
            raise ExecutionEvidenceError("audit sequence/chain discontinuity")
        expected_digest = sha256_bytes(canonical_json_bytes({
            "sequence": sequence,
            "kind": kind,
            "unit_id": unit_id,
            "payload_digest": payload_digest,
            "previous_digest": previous,
        }))
        if event_digest != expected_digest:
            raise ExecutionEvidenceError("audit event digest mismatch")
        if kind == "QUARANTINE":
            raise ExecutionEvidenceError("confirmatory execution contains a quarantined work unit")
        normalized.append({
            "sequence": sequence,
            "kind": kind,
            "unit_id": unit_id,
            "payload_digest": payload_digest,
            "previous_digest": previous,
            "event_digest": event_digest,
        })
        previous = event_digest
    declared_root = _sha("audit_root_digest", doc.get("audit_root_digest"))
    if declared_root != previous:
        raise ExecutionEvidenceError("declared audit root does not equal replayed chain root")
    payload = {
        "spec_digest": spec_digest,
        "events": normalized,
        "audit_root_digest": previous,
    }
    if _sha("audit_log_digest", doc.get("audit_log_digest")) != sha256_bytes(canonical_json_bytes(payload)):
        raise ExecutionEvidenceError("audit log digest mismatch")
    return normalized, previous


def _verify_result(
    path: Path,
    *,
    bundle_root: Path,
    root_authority_digest: str,
    root_digest: str,
    spec: DistributedEvalSpec,
    audit_events: list[dict[str, object]],
    expected_pricing_sha: str | None = None,
    expected_risk_sha: str | None = None,
    expected_rate_cards: Mapping[tuple[str, str, str], ProviderRateCard] | None = None,
) -> VerifiedExecutionResult:
    doc = _json(path, schema=RESULT_SCHEMA)
    if _sha("result root_authority_digest", doc.get("root_authority_digest")) != root_authority_digest:
        raise ExecutionEvidenceError("result belongs to a different confirmatory root authority")
    if _sha("result root_digest", doc.get("root_digest")) != root_digest:
        raise ExecutionEvidenceError("result belongs to a different confirmatory generation root")
    if _sha("result spec_digest", doc.get("distributed_spec_digest")) != spec.digest:
        raise ExecutionEvidenceError("result belongs to a different distributed spec")
    unit = _unit_from_mapping(doc.get("unit"))
    if unit not in set(spec.units()):
        raise ExecutionEvidenceError("result unit is outside frozen execution population")
    attempt = _nonnegative_int("attempt", doc.get("attempt"))
    if attempt < 1 or attempt > spec.max_attempts_per_unit:
        raise ExecutionEvidenceError("result attempt outside frozen attempt budget")
    worker_id = _req("worker_id", doc.get("worker_id"))
    committed_tick = _nonnegative_int("committed_tick", doc.get("committed_tick"))
    result_payload = doc.get("result_payload")
    if not isinstance(result_payload, Mapping):
        raise ExecutionEvidenceError("result_payload must be an object")
    result_payload = dict(result_payload)
    quality = _finite("quality", result_payload.get("quality"), lower=0.0, upper=1.0)
    catastrophic = _finite(
        "catastrophic_regret", result_payload.get("catastrophic_regret"), lower=0.0, upper=1.0
    )
    result_digest = canonical_result_payload_digest(result_payload)
    if _sha("result_digest", doc.get("result_digest")) != result_digest:
        raise ExecutionEvidenceError("result payload digest mismatch")
    cost = _finite(
        "actual_cost_usd", doc.get("actual_cost_usd"), lower=0.0, upper=spec.max_cost_per_unit_usd
    )
    evidence_path, evidence_rel = _safe_relative(bundle_root, doc.get("evidence_path"))
    evidence_digest = sha256_file(evidence_path)
    if evidence_path.stat().st_size <= 0:
        raise ExecutionEvidenceError("empty execution evidence artifact is not accepted")
    if _sha("evidence_sha256", doc.get("evidence_sha256")) != evidence_digest:
        raise ExecutionEvidenceError("execution evidence digest mismatch")
    provider_call_identities = _verify_unit_evidence(
        evidence_path,
        result_payload=result_payload,
        actual_cost_usd=cost,
        unit=unit,
        expected_pricing_sha=expected_pricing_sha,
        expected_risk_sha=expected_risk_sha,
        expected_rate_cards=expected_rate_cards,
    )

    record_payload = {
        "root_authority_digest": root_authority_digest,
        "root_digest": root_digest,
        "distributed_spec_digest": spec.digest,
        "unit": asdict(unit),
        "attempt": attempt,
        "worker_id": worker_id,
        "committed_tick": committed_tick,
        "result_payload": result_payload,
        "result_digest": result_digest,
        "actual_cost_usd": cost,
        "evidence_path": evidence_rel,
        "evidence_sha256": evidence_digest,
    }
    record_digest = sha256_bytes(canonical_json_bytes(record_payload))
    if _sha("record_digest", doc.get("record_digest")) != record_digest:
        raise ExecutionEvidenceError("execution result record digest mismatch")

    expected_commit_payload_digest = sha256_bytes(canonical_json_bytes({
        "attempt": attempt,
        "worker_id": worker_id,
        "result_digest": result_digest,
        "evidence_digest": evidence_digest,
        "actual_cost_usd": cost,
        "committed_tick": committed_tick,
    }))
    commit_matches = [
        event for event in audit_events
        if event["kind"] == "RESULT_COMMITTED"
        and event["unit_id"] == unit.stable_id
        and event["payload_digest"] == expected_commit_payload_digest
    ]
    if len(commit_matches) != 1:
        raise ExecutionEvidenceError("result cannot be bound to exactly one coordinator commit audit event")
    commit_sequence = int(commit_matches[0]["sequence"])
    lease_before_commit = any(
        event["kind"] == "LEASE_GRANTED"
        and event["unit_id"] == unit.stable_id
        and int(event["sequence"]) < commit_sequence
        for event in audit_events
    )
    if not lease_before_commit:
        raise ExecutionEvidenceError("result commit has no preceding lease audit event")

    return VerifiedExecutionResult(
        unit=unit,
        attempt=attempt,
        worker_id=worker_id,
        committed_tick=committed_tick,
        result_payload=result_payload,
        result_digest=result_digest,
        quality=quality,
        catastrophic_regret=catastrophic,
        actual_cost_usd=cost,
        evidence_path=evidence_rel,
        evidence_digest=evidence_digest,
        record_digest=record_digest,
        commit_event_sequence=commit_sequence,
        provider_call_identities=provider_call_identities,
    )


def verify_execution_bundle(
    bundle_root: Path,
    *,
    confirmatory_root_authority_path: Path,
    execution_manifest_freeze_path: Path | None = None,
    repository_root: Path | None = None,
) -> VerifiedExecutionBundle:
    supplied = Path(bundle_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise ExecutionEvidenceError("execution bundle root must be a real directory")
    root = supplied.resolve()
    manifest_path = root / "EXECUTION_BUNDLE.json"
    manifest = _json(manifest_path, schema=BUNDLE_SCHEMA)
    root_authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    expected_pricing_sha, expected_risk_sha, expected_rate_cards = _strict_execution_lineage(
        root_authority=root_authority,
        execution_manifest_freeze_path=execution_manifest_freeze_path,
        repository_root=repository_root,
    )
    root_authority_digest = _sha("root authority_digest", root_authority.get("authority_digest"))
    root_doc = root_authority.get("root")
    spec_doc = root_authority.get("distributed_spec")
    if not isinstance(root_doc, Mapping) or not isinstance(spec_doc, Mapping):
        raise ExecutionEvidenceError("confirmatory root/spec payload missing")
    root_digest = _sha("root_digest", root_doc.get("root_digest"))
    try:
        spec = DistributedEvalSpec(**dict(spec_doc))
    except (TypeError, ValueError) as exc:
        raise ExecutionEvidenceError("distributed spec cannot be reconstructed") from exc
    if spec.digest != _sha("distributed_spec_digest", root_authority.get("distributed_spec_digest")):
        raise ExecutionEvidenceError("distributed spec digest mismatch")

    if _sha("bundle root_authority_digest", manifest.get("root_authority_digest")) != root_authority_digest:
        raise ExecutionEvidenceError("execution bundle belongs to a different root authority")
    if _sha("bundle root_digest", manifest.get("root_digest")) != root_digest:
        raise ExecutionEvidenceError("execution bundle belongs to a different root")
    if _sha("bundle distributed_spec_digest", manifest.get("distributed_spec_digest")) != spec.digest:
        raise ExecutionEvidenceError("execution bundle belongs to a different distributed spec")
    if str(manifest.get("family_id", "")) != str(root_authority.get("family_id", "")):
        raise ExecutionEvidenceError("execution bundle family mismatch")
    if manifest.get("product_promotion_authorized") is not False:
        raise ExecutionEvidenceError("execution bundle cannot authorize product promotion")

    observed_rows = file_manifest(root, excluded_names=frozenset({"EXECUTION_BUNDLE.json"}))
    observed_payload_digest = sha256_bytes(canonical_json_bytes(observed_rows))
    if _sha("payload_manifest_sha256", manifest.get("payload_manifest_sha256")) != observed_payload_digest:
        raise ExecutionEvidenceError("execution bundle payload manifest mismatch")

    audit_path, audit_rel = _safe_relative(root, manifest.get("audit_log_path"))
    audit_events, audit_root = _verify_audit_log(audit_path, spec_digest=spec.digest)
    if audit_rel == "EXECUTION_BUNDLE.json":
        raise ExecutionEvidenceError("bundle manifest cannot be its own audit log")

    raw_result_paths = manifest.get("result_paths")
    if not isinstance(raw_result_paths, list) or not raw_result_paths:
        raise ExecutionEvidenceError("execution bundle requires result_paths")
    result_paths: list[tuple[Path, str]] = []
    seen_paths: set[str] = set()
    for value in raw_result_paths:
        path, rel = _safe_relative(root, value)
        if rel in seen_paths:
            raise ExecutionEvidenceError("duplicate result path")
        seen_paths.add(rel)
        result_paths.append((path, rel))

    results = tuple(
        _verify_result(
            path,
            bundle_root=root,
            root_authority_digest=root_authority_digest,
            root_digest=root_digest,
            spec=spec,
            audit_events=audit_events,
            expected_pricing_sha=expected_pricing_sha,
            expected_risk_sha=expected_risk_sha,
            expected_rate_cards=expected_rate_cards,
        )
        for path, _ in result_paths
    )
    expected_units = set(spec.units())
    observed_units = [row.unit for row in results]
    if len(observed_units) != len(set(observed_units)):
        raise ExecutionEvidenceError("duplicate work-unit results")
    if set(observed_units) != expected_units:
        missing = sorted(unit.stable_id for unit in expected_units - set(observed_units))
        extra = sorted(unit.stable_id for unit in set(observed_units) - expected_units)
        raise ExecutionEvidenceError(
            f"full frozen work population required; missing={missing[:5]}; extra={extra[:5]}"
        )
    commit_events = [event for event in audit_events if event["kind"] == "RESULT_COMMITTED"]
    if len(commit_events) != len(results):
        raise ExecutionEvidenceError("audit RESULT_COMMITTED population differs from result population")

    seen_provider_calls: set[tuple[str, str]] = set()
    for result in results:
        for identity in result.provider_call_identities:
            if identity in seen_provider_calls:
                raise ExecutionEvidenceError("provider call identity reused across work units")
            seen_provider_calls.add(identity)

    # Reproduce coordinator completion ordering: spend accumulates in commit-event order;
    # result_population_digest is sorted by WorkUnitId.
    by_commit = sorted(results, key=lambda row: row.commit_event_sequence)
    spent = 0.0
    for row in by_commit:
        spent += row.actual_cost_usd
    if spent > spec.global_budget_usd + 1e-12:
        raise ExecutionEvidenceError("replayed execution cost exceeds frozen global budget")
    by_unit = sorted(results, key=lambda row: row.unit)
    population_rows = [
        (
            row.unit.stable_id,
            row.attempt,
            row.worker_id,
            row.result_digest,
            row.evidence_digest,
            row.actual_cost_usd,
        )
        for row in by_unit
    ]
    population_digest = sha256_bytes(canonical_json_bytes(population_rows))
    completion = CompletionCertificate(
        experiment_id=spec.experiment_id,
        spec_digest=spec.digest,
        expected_units=len(expected_units),
        committed_units=len(results),
        total_cost_usd=spent,
        audit_root_digest=audit_root,
        result_population_digest=population_digest,
        complete=True,
    )

    manifest_payload = {
        "family_id": str(root_authority["family_id"]),
        "root_authority_digest": root_authority_digest,
        "root_digest": root_digest,
        "distributed_spec_digest": spec.digest,
        "payload_manifest_sha256": observed_payload_digest,
        "audit_log_path": audit_rel,
        "result_paths": [rel for _, rel in result_paths],
        "expected_units": len(expected_units),
        "committed_units": len(results),
        "audit_root_digest": audit_root,
        "result_population_digest": population_digest,
        "total_cost_usd": spent,
        "product_promotion_authorized": False,
    }
    bundle_digest = sha256_bytes(canonical_json_bytes(manifest_payload))
    if _sha("bundle_digest", manifest.get("bundle_digest")) != bundle_digest:
        raise ExecutionEvidenceError("execution bundle digest mismatch")
    for key in ("expected_units", "committed_units"):
        if int(manifest.get(key, -1)) != int(manifest_payload[key]):
            raise ExecutionEvidenceError(f"execution bundle {key} mismatch")
    for key in ("audit_root_digest", "result_population_digest"):
        if manifest.get(key) != manifest_payload[key]:
            raise ExecutionEvidenceError(f"execution bundle {key} mismatch")
    declared_cost = _finite("bundle total_cost_usd", manifest.get("total_cost_usd"), lower=0.0)
    if not math.isclose(declared_cost, spent, rel_tol=0.0, abs_tol=1e-12):
        raise ExecutionEvidenceError("execution bundle total cost mismatch")

    return VerifiedExecutionBundle(
        family_id=str(root_authority["family_id"]),
        root_authority_digest=root_authority_digest,
        root_digest=root_digest,
        distributed_spec_digest=spec.digest,
        payload_manifest_sha256=observed_payload_digest,
        audit_root_digest=audit_root,
        result_population_digest=population_digest,
        total_cost_usd=spent,
        results=results,
        completion=completion,
        bundle_digest=bundle_digest,
    )
