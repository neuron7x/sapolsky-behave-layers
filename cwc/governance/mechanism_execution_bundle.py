from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.cost_accounting import ProviderRateCard
from cwc.governance.distributed_eval_control import CompletionCertificate, DistributedEvalSpec, WorkUnitId
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.mechanism_execution_authority import verify_mechanism_execution_authority_document
from cwc.governance.physical_cost_evidence import (
    PRODUCT_COST_COMPONENTS,
    CostAuthority,
    CostComponentEvidence,
    certify_physical_trial_cost,
)
from cwc.governance.provider_trace import ProviderUsageTrace, TraceAuthority

BUNDLE_SCHEMA = "DGC_MECHANISM_EXECUTION_BUNDLE_V1"
RESULT_SCHEMA = "DGC_MECHANISM_RESULT_V1"
EVIDENCE_SCHEMA = "DGC_MECHANISM_UNIT_EVIDENCE_V1"
AUDIT_SCHEMA = "DGC_DISTRIBUTED_AUDIT_LOG_V1"

_FORBIDDEN_RISK_FIELDS = frozenset({
    "catastrophic_regret",
    "risk_endpoint_response",
    "risk_endpoint_response_digest",
    "risk_endpoint_manifest_sha256",
})


class MechanismExecutionBundleError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise MechanismExecutionBundleError(f"{name} must be lowercase SHA-256")
    return text


def _req(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise MechanismExecutionBundleError(f"{name} required")
    return text


def _finite(
    name: str,
    value: object,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise MechanismExecutionBundleError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise MechanismExecutionBundleError(f"{name} must be finite")
    if lower is not None and result < lower:
        raise MechanismExecutionBundleError(f"{name} below lower bound")
    if upper is not None and result > upper:
        raise MechanismExecutionBundleError(f"{name} above upper bound")
    return result


def _json(path: Path, *, schema: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise MechanismExecutionBundleError(f"missing regular JSON evidence: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MechanismExecutionBundleError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise MechanismExecutionBundleError(f"unexpected schema for {path}")
    return doc


def _safe_relative(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise MechanismExecutionBundleError("mechanism evidence path must be relative and non-traversing")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise MechanismExecutionBundleError(
                f"mechanism evidence symlink rejected: {rel.as_posix()}"
            )
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise MechanismExecutionBundleError("mechanism evidence path escapes bundle root") from exc
    if not resolved.is_file():
        raise MechanismExecutionBundleError(f"mechanism evidence file missing: {rel.as_posix()}")
    return resolved, rel.as_posix()


def _safe_repository_file(root: Path, value: object) -> Path:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise MechanismExecutionBundleError("frozen repository subject path must be relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise MechanismExecutionBundleError("frozen repository subject contains symlink")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise MechanismExecutionBundleError("frozen repository subject escapes root") from exc
    if not resolved.is_file():
        raise MechanismExecutionBundleError("frozen repository subject missing")
    return resolved


def _unit(value: object) -> WorkUnitId:
    if not isinstance(value, Mapping):
        raise MechanismExecutionBundleError("result unit must be an object")
    try:
        return WorkUnitId(
            task_id=str(value["task_id"]),
            policy_id=str(value["policy_id"]),
            replicate=int(value["replicate"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MechanismExecutionBundleError("invalid mechanism work unit") from exc


def canonical_mechanism_result_digest(payload: Mapping[str, object]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(payload)))


@dataclass(frozen=True, slots=True)
class VerifiedMechanismResult:
    unit: WorkUnitId
    attempt: int
    worker_id: str
    committed_tick: int
    result_payload: dict[str, object]
    result_digest: str
    quality: float
    actual_cost_usd: float
    evidence_path: str
    evidence_digest: str
    record_digest: str
    commit_event_sequence: int


@dataclass(frozen=True, slots=True)
class VerifiedMechanismBundle:
    family_id: str
    authority_digest: str
    distributed_spec_digest: str
    payload_manifest_sha256: str
    audit_root_digest: str
    result_population_digest: str
    total_cost_usd: float
    results: tuple[VerifiedMechanismResult, ...]
    completion: CompletionCertificate
    bundle_digest: str


def _distributed_spec(authority: Mapping[str, object]) -> DistributedEvalSpec:
    raw = authority.get("distributed_spec")
    if not isinstance(raw, Mapping):
        raise MechanismExecutionBundleError("mechanism distributed spec missing")
    try:
        spec = DistributedEvalSpec(
            experiment_id=str(raw["experiment_id"]),
            task_ids=tuple(str(x) for x in raw["task_ids"]),
            policy_ids=tuple(str(x) for x in raw["policy_ids"]),
            replicates=int(raw["replicates"]),
            max_attempts_per_unit=int(raw["max_attempts_per_unit"]),
            lease_ttl_ticks=int(raw["lease_ttl_ticks"]),
            max_cost_per_unit_usd=float(raw["max_cost_per_unit_usd"]),
            global_budget_usd=float(raw["global_budget_usd"]),
            harness_digest=str(raw["harness_digest"]),
            statistical_plan_digest=str(raw["statistical_plan_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MechanismExecutionBundleError("mechanism distributed spec cannot be replayed") from exc
    if spec.digest != _sha("distributed_spec_digest", authority.get("distributed_spec_digest")):
        raise MechanismExecutionBundleError("mechanism distributed spec digest mismatch")
    return spec


def _pricing_lineage(
    *,
    authority: Mapping[str, object],
    execution_manifest_freeze_path: Path,
    repository_root: Path,
) -> tuple[str, dict[tuple[str, str, str], ProviderRateCard]]:
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    if _sha("execution freeze_digest", execution.get("freeze_digest")) != _sha(
        "authority execution_manifest_freeze_digest",
        authority.get("execution_manifest_freeze_digest"),
    ):
        raise MechanismExecutionBundleError("mechanism replay uses a different execution freeze")
    rows = execution.get("components")
    if not isinstance(rows, list):
        raise MechanismExecutionBundleError("execution freeze component population missing")
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("component") == "pricing_snapshot"
    ]
    if len(matches) != 1:
        raise MechanismExecutionBundleError("exactly one frozen pricing component required")
    row = matches[0]
    pricing_sha = _sha("frozen pricing sha256", row.get("sha256"))
    path = _safe_repository_file(Path(repository_root).resolve(), row.get("path"))
    if sha256_file(path) != pricing_sha:
        raise MechanismExecutionBundleError("repository pricing bytes differ from execution freeze")
    doc = _json(path, schema="DGC_PRICING_SNAPSHOT_V1")
    captured_at = _req("pricing captured_at", doc.get("captured_at"))
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise MechanismExecutionBundleError("frozen pricing entries missing")
    cards: dict[tuple[str, str, str], ProviderRateCard] = {}
    try:
        for raw in entries:
            if not isinstance(raw, Mapping):
                raise MechanismExecutionBundleError("invalid frozen pricing row")
            identity = (
                _req("pricing provider", raw.get("provider")),
                _req("pricing model_id", raw.get("model_id")),
                _req("pricing model_version", raw.get("model_version")),
            )
            if identity in cards:
                raise MechanismExecutionBundleError("duplicate frozen pricing identity")
            if raw.get("currency") != "USD":
                raise MechanismExecutionBundleError("pricing currency must be USD")
            cards[identity] = ProviderRateCard(
                provider=identity[0],
                model=identity[1],
                input_usd_per_million=float(raw["input_per_million"]),
                cached_input_usd_per_million=float(raw["cached_input_per_million"]),
                cache_write_usd_per_million=float(raw["cache_write_per_million"]),
                long_cache_write_usd_per_million=float(raw["long_cache_write_per_million"]),
                output_usd_per_million=float(raw["output_per_million"]),
                source_uri=str(raw["source_uri"]),
                retrieved_at=captured_at,
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise MechanismExecutionBundleError("invalid frozen pricing manifest") from exc
    return pricing_sha, cards


def _verify_cost_evidence(
    doc: Mapping[str, object],
    *,
    result_payload: Mapping[str, object],
    actual_cost_usd: float,
    unit: WorkUnitId,
    expected_pricing_sha: str,
    expected_rate_cards: Mapping[tuple[str, str, str], ProviderRateCard],
) -> None:
    response = doc.get("response")
    if not isinstance(response, Mapping):
        raise MechanismExecutionBundleError("mechanism evidence missing adapter response")
    if any(field in response for field in _FORBIDDEN_RISK_FIELDS):
        raise MechanismExecutionBundleError("mechanism adapter response contains forbidden risk field")
    adapter_digest = sha256_bytes(canonical_json_bytes(dict(response)))
    if _sha("adapter_response_digest", doc.get("adapter_response_digest")) != adapter_digest:
        raise MechanismExecutionBundleError("adapter response digest mismatch")
    if _sha(
        "result adapter_response_digest", result_payload.get("adapter_response_digest")
    ) != adapter_digest:
        raise MechanismExecutionBundleError("mechanism result is not bound to adapter response")

    trace = response.get("trace")
    if not isinstance(trace, Mapping) or not trace:
        raise MechanismExecutionBundleError("mechanism evidence missing raw trace metadata")
    trace_digest = sha256_bytes(canonical_json_bytes(dict(trace)))
    if _sha("trace_digest", doc.get("trace_digest")) != trace_digest:
        raise MechanismExecutionBundleError("raw trace digest mismatch")
    if _sha("result trace_digest", result_payload.get("trace_digest")) != trace_digest:
        raise MechanismExecutionBundleError("mechanism result is not bound to raw trace")

    pricing_sha = _sha(
        "pricing_snapshot_manifest_sha256", doc.get("pricing_snapshot_manifest_sha256")
    )
    if pricing_sha != expected_pricing_sha:
        raise MechanismExecutionBundleError("mechanism evidence pricing differs from freeze")
    if _sha(
        "result pricing_snapshot_manifest_sha256",
        result_payload.get("pricing_snapshot_manifest_sha256"),
    ) != pricing_sha:
        raise MechanismExecutionBundleError("mechanism result is not bound to pricing snapshot")

    rate_rows = doc.get("provider_rate_cards")
    if not isinstance(rate_rows, list) or not rate_rows:
        raise MechanismExecutionBundleError("mechanism evidence requires provider rate cards")
    cards: dict[tuple[str, str, str], ProviderRateCard] = {}
    try:
        for raw in rate_rows:
            if not isinstance(raw, Mapping):
                raise MechanismExecutionBundleError("invalid embedded rate card")
            identity = (
                _req("rate-card provider", raw.get("provider")),
                _req("rate-card model", raw.get("model")),
                _req("rate-card model_version", raw.get("model_version")),
            )
            if identity in cards:
                raise MechanismExecutionBundleError("duplicate embedded rate-card identity")
            card = ProviderRateCard(
                provider=identity[0],
                model=identity[1],
                input_usd_per_million=float(raw["input_usd_per_million"]),
                cached_input_usd_per_million=float(raw["cached_input_usd_per_million"]),
                cache_write_usd_per_million=float(raw["cache_write_usd_per_million"]),
                long_cache_write_usd_per_million=float(raw["long_cache_write_usd_per_million"]),
                output_usd_per_million=float(raw["output_usd_per_million"]),
                source_uri=str(raw["source_uri"]),
                retrieved_at=str(raw["retrieved_at"]),
            )
            if _sha("embedded rate_card_digest", raw.get("rate_card_digest")) != card.digest:
                raise MechanismExecutionBundleError("embedded rate-card digest mismatch")
            expected = expected_rate_cards.get(identity)
            if expected is None or expected.digest != card.digest:
                raise MechanismExecutionBundleError("embedded rate card differs from frozen pricing")
            cards[identity] = card
    except (KeyError, TypeError, ValueError) as exc:
        raise MechanismExecutionBundleError("invalid embedded provider pricing") from exc

    raw_traces = response.get("provider_usage_traces")
    evidence_traces = doc.get("provider_usage_traces")
    if (
        not isinstance(raw_traces, list)
        or not raw_traces
        or not isinstance(evidence_traces, list)
        or len(raw_traces) != len(evidence_traces)
    ):
        raise MechanismExecutionBundleError("provider usage population missing or inconsistent")

    derived: list[dict[str, object]] = []
    meter_population: list[tuple[str, str]] = []
    model_costs: list[float] = []
    request_ids: set[str] = set()
    for raw in raw_traces:
        if not isinstance(raw, Mapping):
            raise MechanismExecutionBundleError("invalid raw provider usage trace")
        version = _req("provider model_version", raw.get("model_version"))
        identity = (
            _req("provider", raw.get("provider")),
            _req("model", raw.get("model")),
            version,
        )
        card = cards.get(identity)
        if card is None:
            raise MechanismExecutionBundleError("provider trace lacks frozen rate card")
        request_id_raw = raw.get("provider_request_id")
        if not isinstance(request_id_raw, str) or not request_id_raw.strip():
            raise MechanismExecutionBundleError("live provider trace requires real provider_request_id")
        try:
            trace_obj = ProviderUsageTrace(
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
                provider_request_id=request_id_raw.strip(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MechanismExecutionBundleError("malformed provider usage trace") from exc
        if trace_obj.authority is not TraceAuthority.PROVIDER_LIVE:
            raise MechanismExecutionBundleError(
                "real-workload mechanism provider trace must be PROVIDER_LIVE"
            )
        if trace_obj.decision_id != unit.stable_id or trace_obj.policy_id != unit.policy_id:
            raise MechanismExecutionBundleError("provider trace decision/policy identity mismatch")
        request_id = str(trace_obj.provider_request_id)
        if request_id in request_ids:
            raise MechanismExecutionBundleError("duplicate provider_request_id")
        request_ids.add(request_id)
        if trace_obj.rate_card_digest != card.digest:
            raise MechanismExecutionBundleError("provider trace rate-card digest mismatch")
        metered = trace_obj.meter(card)
        model_costs.append(metered.model_token_usd)
        derived.append({
            "trace_digest": trace_obj.digest,
            "trace_id": trace_obj.trace_id,
            "decision_id": trace_obj.decision_id,
            "policy_id": trace_obj.policy_id,
            "authority": trace_obj.authority.value,
            "provider_request_id": trace_obj.provider_request_id,
            "provider": trace_obj.provider,
            "model": trace_obj.model,
            "model_version": version,
            "rate_card_digest": trace_obj.rate_card_digest,
            "input_tokens": trace_obj.input_tokens,
            "cached_input_tokens": trace_obj.cached_input_tokens,
            "cache_write_tokens": trace_obj.cache_write_tokens,
            "long_cache_write_tokens": trace_obj.long_cache_write_tokens,
            "output_tokens": trace_obj.output_tokens,
            "model_token_usd": metered.model_token_usd,
        })
        meter_population.append((trace_obj.digest, version))
    if evidence_traces != derived:
        raise MechanismExecutionBundleError("derived provider evidence differs from raw traces")
    trace_population_digest = sha256_bytes(canonical_json_bytes(sorted(meter_population)))
    if _sha(
        "provider_trace_population_digest", doc.get("provider_trace_population_digest")
    ) != trace_population_digest:
        raise MechanismExecutionBundleError("provider trace population digest mismatch")
    if _sha(
        "result provider_trace_population_digest",
        result_payload.get("provider_trace_population_digest"),
    ) != trace_population_digest:
        raise MechanismExecutionBundleError("result is not bound to provider trace population")

    certificate = doc.get("physical_cost_certificate")
    if not isinstance(certificate, Mapping):
        raise MechanismExecutionBundleError("mechanism evidence missing physical cost certificate")
    rows = certificate.get("components")
    if not isinstance(rows, list) or len(rows) != len(PRODUCT_COST_COMPONENTS):
        raise MechanismExecutionBundleError("physical cost component population mismatch")
    evidence: dict[str, CostComponentEvidence] = {}
    try:
        for raw in rows:
            if not isinstance(raw, Mapping):
                raise MechanismExecutionBundleError("invalid physical cost row")
            component = str(raw.get("component", ""))
            if component in evidence or component not in PRODUCT_COST_COMPONENTS:
                raise MechanismExecutionBundleError("physical cost component identity mismatch")
            evidence[component] = CostComponentEvidence(
                component=component,
                value_usd=float(raw.get("value_usd")),
                authority=CostAuthority(str(raw.get("authority"))),
                source_digest=_sha(
                    f"physical cost source digest {component}",
                    raw.get("source_digest"),
                ),
            )
        rebuilt = certify_physical_trial_cost(
            trial_id=_req("physical cost trial_id", certificate.get("trial_id")),
            evidence=evidence,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise MechanismExecutionBundleError("invalid physical cost certificate") from exc

    model_component = evidence.get("model_usd")
    if model_component is None or model_component.authority is not CostAuthority.PROVIDER_METER:
        raise MechanismExecutionBundleError("model_usd must use PROVIDER_METER")
    if model_component.source_digest != trace_population_digest:
        raise MechanismExecutionBundleError("model_usd source is not provider trace population")
    if not math.isclose(
        model_component.value_usd,
        math.fsum(model_costs),
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise MechanismExecutionBundleError("model_usd differs from replayed provider token cost")
    if _sha("physical cost digest", certificate.get("digest")) != rebuilt.digest:
        raise MechanismExecutionBundleError("physical cost certificate digest mismatch")
    if _sha(
        "result physical cost digest",
        result_payload.get("physical_cost_certificate_digest"),
    ) != rebuilt.digest:
        raise MechanismExecutionBundleError("result is not bound to physical cost certificate")
    declared_total = _finite(
        "physical cost total",
        certificate.get("total_operational_usd"),
        lower=0.0,
    )
    if not math.isclose(
        declared_total,
        rebuilt.cost.total_operational_usd,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise MechanismExecutionBundleError("physical cost total mismatch")
    if not math.isclose(
        rebuilt.cost.total_operational_usd,
        actual_cost_usd,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise MechanismExecutionBundleError("actual cost differs from physical cost certificate")


def _verify_audit(path: Path, *, spec_digest: str) -> tuple[list[dict[str, object]], str]:
    doc = _json(path, schema=AUDIT_SCHEMA)
    if _sha("audit spec_digest", doc.get("spec_digest")) != spec_digest:
        raise MechanismExecutionBundleError("audit spec digest mismatch")
    events = doc.get("events")
    if not isinstance(events, list) or not events:
        raise MechanismExecutionBundleError("mechanism audit log is empty")
    previous = "GENESIS"
    verified: list[dict[str, object]] = []
    for index, raw in enumerate(events):
        if not isinstance(raw, Mapping):
            raise MechanismExecutionBundleError("invalid mechanism audit row")
        event = dict(raw)
        if int(event.get("sequence", -1)) != index:
            raise MechanismExecutionBundleError("mechanism audit sequence gap")
        if event.get("previous_digest") != previous:
            raise MechanismExecutionBundleError("mechanism audit chain broken")
        payload = {
            "sequence": index,
            "kind": event.get("kind"),
            "unit_id": event.get("unit_id"),
            "payload_digest": event.get("payload_digest"),
            "previous_digest": previous,
        }
        expected = sha256_bytes(canonical_json_bytes(payload))
        if _sha("audit event_digest", event.get("event_digest")) != expected:
            raise MechanismExecutionBundleError("mechanism audit event digest mismatch")
        previous = expected
        verified.append(event)
    if _sha("audit_root_digest", doc.get("audit_root_digest")) != previous:
        raise MechanismExecutionBundleError("mechanism audit root mismatch")
    audit_payload = {
        "spec_digest": spec_digest,
        "events": verified,
        "audit_root_digest": previous,
    }
    if _sha("audit_log_digest", doc.get("audit_log_digest")) != sha256_bytes(
        canonical_json_bytes(audit_payload)
    ):
        raise MechanismExecutionBundleError("mechanism audit document digest mismatch")
    return verified, previous


def _verify_result(
    path: Path,
    *,
    bundle_root: Path,
    authority_digest: str,
    spec: DistributedEvalSpec,
    audit_events: list[dict[str, object]],
    expected_pricing_sha: str,
    expected_rate_cards: Mapping[tuple[str, str, str], ProviderRateCard],
) -> VerifiedMechanismResult:
    doc = _json(path, schema=RESULT_SCHEMA)
    if any(field in doc for field in _FORBIDDEN_RISK_FIELDS):
        raise MechanismExecutionBundleError("mechanism result record contains forbidden risk field")
    if _sha("result authority_digest", doc.get("authority_digest")) != authority_digest:
        raise MechanismExecutionBundleError("mechanism result belongs to different authority")
    if _sha("result distributed_spec_digest", doc.get("distributed_spec_digest")) != spec.digest:
        raise MechanismExecutionBundleError("mechanism result belongs to different distributed spec")

    unit = _unit(doc.get("unit"))
    if unit not in set(spec.units()):
        raise MechanismExecutionBundleError("result unit outside frozen mechanism population")
    try:
        attempt = int(doc.get("attempt"))
        committed_tick = int(doc.get("committed_tick"))
    except (TypeError, ValueError) as exc:
        raise MechanismExecutionBundleError("invalid mechanism result integer field") from exc
    if attempt <= 0 or committed_tick < 0:
        raise MechanismExecutionBundleError("invalid mechanism attempt/commit tick")
    worker = _req("worker_id", doc.get("worker_id"))

    payload = doc.get("result_payload")
    if not isinstance(payload, Mapping):
        raise MechanismExecutionBundleError("mechanism result_payload missing")
    result_payload = dict(payload)
    if any(field in result_payload for field in _FORBIDDEN_RISK_FIELDS):
        raise MechanismExecutionBundleError("mechanism result_payload contains forbidden risk field")
    quality = _finite("quality", result_payload.get("quality"), lower=0.0, upper=1.0)
    digest = canonical_mechanism_result_digest(result_payload)
    if _sha("result_digest", doc.get("result_digest")) != digest:
        raise MechanismExecutionBundleError("mechanism result payload digest mismatch")
    cost = _finite(
        "actual_cost_usd",
        doc.get("actual_cost_usd"),
        lower=0.0,
        upper=spec.max_cost_per_unit_usd,
    )
    evidence_path, evidence_rel = _safe_relative(bundle_root, doc.get("evidence_path"))
    evidence_digest = sha256_file(evidence_path)
    if evidence_path.stat().st_size <= 0:
        raise MechanismExecutionBundleError("empty mechanism evidence is not accepted")
    if _sha("evidence_sha256", doc.get("evidence_sha256")) != evidence_digest:
        raise MechanismExecutionBundleError("mechanism evidence digest mismatch")
    evidence_doc = _json(evidence_path, schema=EVIDENCE_SCHEMA)
    if any(field in evidence_doc for field in _FORBIDDEN_RISK_FIELDS):
        raise MechanismExecutionBundleError("mechanism evidence contains forbidden risk field")
    _verify_cost_evidence(
        evidence_doc,
        result_payload=result_payload,
        actual_cost_usd=cost,
        unit=unit,
        expected_pricing_sha=expected_pricing_sha,
        expected_rate_cards=expected_rate_cards,
    )

    record_payload = {
        "authority_digest": authority_digest,
        "distributed_spec_digest": spec.digest,
        "unit": asdict(unit),
        "attempt": attempt,
        "worker_id": worker,
        "committed_tick": committed_tick,
        "result_payload": result_payload,
        "result_digest": digest,
        "actual_cost_usd": cost,
        "evidence_path": evidence_rel,
        "evidence_sha256": evidence_digest,
    }
    record_digest = sha256_bytes(canonical_json_bytes(record_payload))
    if _sha("record_digest", doc.get("record_digest")) != record_digest:
        raise MechanismExecutionBundleError("mechanism result record digest mismatch")

    commit_payload = sha256_bytes(canonical_json_bytes({
        "attempt": attempt,
        "worker_id": worker,
        "result_digest": digest,
        "evidence_digest": evidence_digest,
        "actual_cost_usd": cost,
        "committed_tick": committed_tick,
    }))
    matches = [
        event for event in audit_events
        if event.get("kind") == "RESULT_COMMITTED"
        and event.get("unit_id") == unit.stable_id
        and event.get("payload_digest") == commit_payload
    ]
    if len(matches) != 1:
        raise MechanismExecutionBundleError(
            "mechanism result cannot bind exactly one coordinator commit"
        )
    commit_sequence = int(matches[0]["sequence"])
    if not any(
        event.get("kind") == "LEASE_GRANTED"
        and event.get("unit_id") == unit.stable_id
        and int(event.get("sequence", -1)) < commit_sequence
        for event in audit_events
    ):
        raise MechanismExecutionBundleError("mechanism result lacks preceding lease")

    return VerifiedMechanismResult(
        unit=unit,
        attempt=attempt,
        worker_id=worker,
        committed_tick=committed_tick,
        result_payload=result_payload,
        result_digest=digest,
        quality=quality,
        actual_cost_usd=cost,
        evidence_path=evidence_rel,
        evidence_digest=evidence_digest,
        record_digest=record_digest,
        commit_event_sequence=commit_sequence,
    )


def verify_mechanism_execution_bundle(
    bundle_root: Path,
    *,
    mechanism_authority_path: Path,
    execution_manifest_freeze_path: Path,
    repository_root: Path,
) -> VerifiedMechanismBundle:
    supplied = Path(bundle_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise MechanismExecutionBundleError("mechanism bundle root must be a real directory")
    root = supplied.resolve()
    manifest = _json(root / "MECHANISM_EXECUTION_BUNDLE.json", schema=BUNDLE_SCHEMA)
    authority = verify_mechanism_execution_authority_document(
        Path(mechanism_authority_path)
    )
    authority_digest = _sha("authority_digest", authority.get("authority_digest"))
    spec = _distributed_spec(authority)
    pricing_sha, rate_cards = _pricing_lineage(
        authority=authority,
        execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
        repository_root=Path(repository_root),
    )

    if _sha("bundle authority_digest", manifest.get("authority_digest")) != authority_digest:
        raise MechanismExecutionBundleError("mechanism bundle belongs to different authority")
    if _sha("bundle distributed_spec_digest", manifest.get("distributed_spec_digest")) != spec.digest:
        raise MechanismExecutionBundleError("mechanism bundle uses different distributed spec")
    if str(manifest.get("family_id", "")) != str(authority.get("family_id", "")):
        raise MechanismExecutionBundleError("mechanism bundle family mismatch")
    if (
        manifest.get("risk_qualification_authorized") is not False
        or manifest.get("product_promotion_authorized") is not False
        or manifest.get("commercial_claim_authorized") is not False
    ):
        raise MechanismExecutionBundleError("mechanism bundle illegally grants downstream authority")

    observed_rows = file_manifest(
        root,
        excluded_names=frozenset({"MECHANISM_EXECUTION_BUNDLE.json"}),
    )
    payload_digest = sha256_bytes(canonical_json_bytes(observed_rows))
    if _sha("payload_manifest_sha256", manifest.get("payload_manifest_sha256")) != payload_digest:
        raise MechanismExecutionBundleError("mechanism bundle payload manifest mismatch")

    audit_path, audit_rel = _safe_relative(root, manifest.get("audit_log_path"))
    events, audit_root = _verify_audit(audit_path, spec_digest=spec.digest)

    raw_paths = manifest.get("result_paths")
    if not isinstance(raw_paths, list) or not raw_paths:
        raise MechanismExecutionBundleError("mechanism bundle requires result_paths")
    paths: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for value in raw_paths:
        path, rel = _safe_relative(root, value)
        if rel in seen:
            raise MechanismExecutionBundleError("duplicate mechanism result path")
        seen.add(rel)
        paths.append((path, rel))

    results = tuple(
        _verify_result(
            path,
            bundle_root=root,
            authority_digest=authority_digest,
            spec=spec,
            audit_events=events,
            expected_pricing_sha=pricing_sha,
            expected_rate_cards=rate_cards,
        )
        for path, _ in paths
    )
    expected_units = set(spec.units())
    observed_units = [row.unit for row in results]
    if len(observed_units) != len(set(observed_units)):
        raise MechanismExecutionBundleError("duplicate mechanism work-unit results")
    if set(observed_units) != expected_units:
        missing = sorted(unit.stable_id for unit in expected_units - set(observed_units))
        extra = sorted(unit.stable_id for unit in set(observed_units) - expected_units)
        raise MechanismExecutionBundleError(
            f"full mechanism work population required; missing={missing[:5]}; extra={extra[:5]}"
        )
    commit_events = [event for event in events if event.get("kind") == "RESULT_COMMITTED"]
    if len(commit_events) != len(results):
        raise MechanismExecutionBundleError(
            "mechanism commit audit population differs from result population"
        )

    by_commit = sorted(results, key=lambda row: row.commit_event_sequence)
    spent = math.fsum(row.actual_cost_usd for row in by_commit)
    if spent > spec.global_budget_usd + 1e-12:
        raise MechanismExecutionBundleError("mechanism replay exceeds frozen budget")
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
        "family_id": str(authority["family_id"]),
        "authority_digest": authority_digest,
        "distributed_spec_digest": spec.digest,
        "payload_manifest_sha256": payload_digest,
        "audit_log_path": audit_rel,
        "result_paths": [rel for _, rel in paths],
        "expected_units": len(expected_units),
        "committed_units": len(results),
        "audit_root_digest": audit_root,
        "result_population_digest": population_digest,
        "total_cost_usd": spent,
        "risk_qualification_authorized": False,
        "product_promotion_authorized": False,
        "commercial_claim_authorized": False,
    }
    bundle_digest = sha256_bytes(canonical_json_bytes(manifest_payload))
    if _sha("bundle_digest", manifest.get("bundle_digest")) != bundle_digest:
        raise MechanismExecutionBundleError("mechanism bundle digest mismatch")
    for key in ("expected_units", "committed_units"):
        if int(manifest.get(key, -1)) != int(manifest_payload[key]):
            raise MechanismExecutionBundleError(f"mechanism bundle {key} mismatch")
    for key in ("audit_root_digest", "result_population_digest"):
        if manifest.get(key) != manifest_payload[key]:
            raise MechanismExecutionBundleError(f"mechanism bundle {key} mismatch")
    if not math.isclose(
        _finite("bundle total_cost_usd", manifest.get("total_cost_usd"), lower=0.0),
        spent,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise MechanismExecutionBundleError("mechanism bundle total cost mismatch")

    return VerifiedMechanismBundle(
        family_id=str(authority["family_id"]),
        authority_digest=authority_digest,
        distributed_spec_digest=spec.digest,
        payload_manifest_sha256=payload_digest,
        audit_root_digest=audit_root,
        result_population_digest=population_digest,
        total_cost_usd=spent,
        results=results,
        completion=completion,
        bundle_digest=bundle_digest,
    )
