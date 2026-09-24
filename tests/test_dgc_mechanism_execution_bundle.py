from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

import cwc.governance.mechanism_execution_bundle as bundle_module
from cwc.governance.cost_accounting import ProviderRateCard
from cwc.governance.distributed_eval_control import DistributedEvalCoordinator, DistributedEvalSpec
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.mechanism_execution_bundle import (
    AUDIT_SCHEMA,
    BUNDLE_SCHEMA,
    EVIDENCE_SCHEMA,
    RESULT_SCHEMA,
    MechanismExecutionBundleError,
    canonical_mechanism_result_digest,
    verify_mechanism_execution_bundle,
)
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


def h(char: str) -> str:
    return char * 64


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifests = repo / "manifests"
    manifests.mkdir()
    card = ProviderRateCard(
        provider="provider",
        model="model",
        input_usd_per_million=1.0,
        cached_input_usd_per_million=0.1,
        cache_write_usd_per_million=1.25,
        long_cache_write_usd_per_million=1.25,
        output_usd_per_million=2.0,
        source_uri="https://example.invalid/pricing",
        retrieved_at="2026-09-24T00:00:00Z",
    )
    pricing = manifests / "pricing.json"
    pricing_doc = {
        "schema": "DGC_PRICING_SNAPSHOT_V1",
        "captured_at": "2026-09-24T00:00:00Z",
        "entries": [{
            "provider": "provider",
            "model_id": "model",
            "model_version": "v1",
            "currency": "USD",
            "source_uri": "https://example.invalid/pricing",
            "input_per_million": 1.0,
            "cached_input_per_million": 0.1,
            "cache_write_per_million": 1.25,
            "long_cache_write_per_million": 1.25,
            "output_per_million": 2.0,
        }],
    }
    _write(pricing, pricing_doc)
    execution = {
        "freeze_digest": h("1"),
        "components": [{
            "component": "pricing_snapshot",
            "path": "manifests/pricing.json",
            "sha256": sha256_file(pricing),
        }],
    }
    spec = DistributedEvalSpec(
        experiment_id="mechanism-fixture",
        task_ids=("task-a",),
        policy_ids=("DGC",),
        replicates=1,
        max_attempts_per_unit=1,
        lease_ttl_ticks=4,
        max_cost_per_unit_usd=2.0,
        global_budget_usd=2.0,
        harness_digest=h("2"),
        statistical_plan_digest=h("3"),
    )
    authority = {
        "family_id": "TERMINAL_BENCH_2_1",
        "authority_digest": h("4"),
        "execution_manifest_freeze_digest": h("1"),
        "distributed_spec": {
            "experiment_id": spec.experiment_id,
            "task_ids": list(spec.task_ids),
            "policy_ids": list(spec.policy_ids),
            "replicates": spec.replicates,
            "max_attempts_per_unit": spec.max_attempts_per_unit,
            "lease_ttl_ticks": spec.lease_ttl_ticks,
            "max_cost_per_unit_usd": spec.max_cost_per_unit_usd,
            "global_budget_usd": spec.global_budget_usd,
            "harness_digest": spec.harness_digest,
            "statistical_plan_digest": spec.statistical_plan_digest,
        },
        "distributed_spec_digest": spec.digest,
    }
    monkeypatch.setattr(
        bundle_module,
        "verify_mechanism_execution_authority_document",
        lambda _: authority,
    )
    monkeypatch.setattr(
        bundle_module,
        "verify_execution_manifest_freeze_document",
        lambda _: execution,
    )
    return repo, card, spec, authority


def _build_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    inject_risk: bool = False,
    null_call_id: bool = False,
):
    repo, card, spec, authority = _fixture(tmp_path, monkeypatch)
    root = tmp_path / "bundle"
    root.mkdir()

    unit = spec.units()[0]
    trace = ProviderUsageTrace(
        trace_id="trace-1",
        decision_id=unit.stable_id,
        policy_id=unit.policy_id,
        authority=TraceAuthority.PROVIDER_LIVE,
        provider="provider",
        model="model",
        rate_card_digest=card.digest,
        input_tokens=1_000_000,
        cached_input_tokens=0,
        cache_write_tokens=0,
        long_cache_write_tokens=0,
        output_tokens=0,
        provider_call_id="resp-1",
        provider_call_id_kind=ProviderCallIdKind.PROVIDER_RESPONSE_ID,
    )
    model_cost = trace.meter(card).model_token_usd
    population_digest = sha256_bytes(canonical_json_bytes([(trace.digest, "v1")]))
    raw_trace = {
        "trace_id": trace.trace_id,
        "decision_id": trace.decision_id,
        "policy_id": trace.policy_id,
        "authority": trace.authority.value,
        "provider": trace.provider,
        "model": trace.model,
        "model_version": "v1",
        "rate_card_digest": trace.rate_card_digest,
        "input_tokens": trace.input_tokens,
        "cached_input_tokens": trace.cached_input_tokens,
        "cache_write_tokens": trace.cache_write_tokens,
        "long_cache_write_tokens": trace.long_cache_write_tokens,
        "output_tokens": trace.output_tokens,
        "provider_call_id": None if null_call_id else trace.provider_call_id,
        "provider_call_id_kind": (
            None if null_call_id else trace.provider_call_id_kind.value
        ),
    }
    response = {
        "schema": "DGC_UNIT_EXECUTION_RESPONSE_V1",
        "unit": asdict(unit),
        "attempt": 1,
        "quality": 0.8,
        "provider_usage_traces": [raw_trace],
        "trace": {"upstream_trial_digest": h("5")},
    }
    if inject_risk:
        response["catastrophic_regret"] = 0.0

    derived_trace = {
        "trace_digest": trace.digest,
        "trace_id": trace.trace_id,
        "decision_id": trace.decision_id,
        "policy_id": trace.policy_id,
        "authority": trace.authority.value,
        "provider_call_id": trace.provider_call_id,
        "provider_call_id_kind": trace.provider_call_id_kind.value,
        "provider": trace.provider,
        "model": trace.model,
        "model_version": "v1",
        "rate_card_digest": trace.rate_card_digest,
        "input_tokens": trace.input_tokens,
        "cached_input_tokens": trace.cached_input_tokens,
        "cache_write_tokens": trace.cache_write_tokens,
        "long_cache_write_tokens": trace.long_cache_write_tokens,
        "output_tokens": trace.output_tokens,
        "model_token_usd": model_cost,
    }
    card_doc = {
        "rate_card_digest": card.digest,
        "provider": card.provider,
        "model": card.model,
        "model_version": "v1",
        "input_usd_per_million": card.input_usd_per_million,
        "cached_input_usd_per_million": card.cached_input_usd_per_million,
        "cache_write_usd_per_million": card.cache_write_usd_per_million,
        "long_cache_write_usd_per_million": card.long_cache_write_usd_per_million,
        "output_usd_per_million": card.output_usd_per_million,
        "source_uri": card.source_uri,
        "retrieved_at": card.retrieved_at,
    }
    evidence_rows = {}
    for component in PRODUCT_COST_COMPONENTS:
        if component == "model_usd":
            evidence_rows[component] = CostComponentEvidence(
                component,
                model_cost,
                CostAuthority.PROVIDER_METER,
                population_digest,
            )
        else:
            evidence_rows[component] = CostComponentEvidence(
                component,
                0.0,
                CostAuthority.ZERO_BY_CONTRACT,
                h("a"),
            )
    certificate = certify_physical_trial_cost(
        trial_id=f"{unit.stable_id}::1",
        evidence=evidence_rows,
    )
    certificate_doc = {
        "trial_id": certificate.trial_id,
        "digest": certificate.digest,
        "components": [
            {
                "component": row.component,
                "value_usd": row.value_usd,
                "authority": row.authority.value,
                "source_digest": row.source_digest,
            }
            for row in certificate.component_evidence
        ],
        "total_operational_usd": certificate.cost.total_operational_usd,
    }
    adapter_digest = sha256_bytes(canonical_json_bytes(response))
    trace_digest = sha256_bytes(canonical_json_bytes(response["trace"]))
    evidence_doc = {
        "schema": EVIDENCE_SCHEMA,
        "response": response,
        "adapter_response_digest": adapter_digest,
        "trace_digest": trace_digest,
        "pricing_snapshot_manifest_sha256": sha256_file(repo / "manifests" / "pricing.json"),
        "provider_rate_cards": [card_doc],
        "provider_usage_traces": [derived_trace],
        "provider_trace_population_digest": population_digest,
        "physical_cost_certificate": certificate_doc,
    }
    evidence_path = _write(root / "evidence" / "00000000.json", evidence_doc)
    evidence_digest = sha256_file(evidence_path)

    result_payload = {
        "quality": 0.8,
        "adapter_response_digest": adapter_digest,
        "trace_digest": trace_digest,
        "pricing_snapshot_manifest_sha256": sha256_file(repo / "manifests" / "pricing.json"),
        "provider_trace_population_digest": population_digest,
        "physical_cost_certificate_digest": certificate.digest,
    }
    coordinator = DistributedEvalCoordinator(spec)
    lease = coordinator.claim("worker-1", tick=0)
    assert lease is not None
    record = coordinator.commit(
        lease,
        tick=1,
        result_payload=result_payload,
        evidence_digest=evidence_digest,
        actual_cost_usd=certificate.cost.total_operational_usd,
    )
    result_record_payload = {
        "authority_digest": authority["authority_digest"],
        "distributed_spec_digest": spec.digest,
        "unit": asdict(record.unit),
        "attempt": record.attempt,
        "worker_id": record.worker_id,
        "committed_tick": record.committed_tick,
        "result_payload": result_payload,
        "result_digest": canonical_mechanism_result_digest(result_payload),
        "actual_cost_usd": record.actual_cost_usd,
        "evidence_path": evidence_path.relative_to(root).as_posix(),
        "evidence_sha256": evidence_digest,
    }
    result_doc = {
        "schema": RESULT_SCHEMA,
        **result_record_payload,
        "record_digest": sha256_bytes(canonical_json_bytes(result_record_payload)),
    }
    result_path = _write(root / "records" / "00000000.json", result_doc)

    events = [asdict(event) for event in coordinator.audit_events()]
    audit_root = events[-1]["event_digest"]
    audit_payload = {
        "spec_digest": spec.digest,
        "events": events,
        "audit_root_digest": audit_root,
    }
    _write(root / "AUDIT_LOG.json", {
        "schema": AUDIT_SCHEMA,
        **audit_payload,
        "audit_log_digest": sha256_bytes(canonical_json_bytes(audit_payload)),
    })
    completion = coordinator.completion_certificate(tick=1)
    payload_rows = file_manifest(
        root,
        excluded_names=frozenset({"MECHANISM_EXECUTION_BUNDLE.json"}),
    )
    payload_digest = sha256_bytes(canonical_json_bytes(payload_rows))
    manifest_payload = {
        "family_id": authority["family_id"],
        "authority_digest": authority["authority_digest"],
        "distributed_spec_digest": spec.digest,
        "payload_manifest_sha256": payload_digest,
        "audit_log_path": "AUDIT_LOG.json",
        "result_paths": [result_path.relative_to(root).as_posix()],
        "expected_units": completion.expected_units,
        "committed_units": completion.committed_units,
        "audit_root_digest": completion.audit_root_digest,
        "result_population_digest": completion.result_population_digest,
        "total_cost_usd": completion.total_cost_usd,
        "risk_qualification_authorized": False,
        "product_promotion_authorized": False,
        "commercial_claim_authorized": False,
    }
    _write(root / "MECHANISM_EXECUTION_BUNDLE.json", {
        "schema": BUNDLE_SCHEMA,
        **manifest_payload,
        "bundle_digest": sha256_bytes(canonical_json_bytes(manifest_payload)),
    })
    return root, repo


def test_mechanism_bundle_replays_full_cost_quality_population(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, repo = _build_bundle(tmp_path, monkeypatch)
    verified = verify_mechanism_execution_bundle(
        root,
        mechanism_authority_path=tmp_path / "authority.json",
        execution_manifest_freeze_path=tmp_path / "execution.json",
        repository_root=repo,
    )
    assert verified.completion.complete is True
    assert verified.completion.expected_units == 1
    assert verified.completion.committed_units == 1
    assert verified.results[0].quality == pytest.approx(0.8)
    assert verified.results[0].actual_cost_usd == pytest.approx(1.0)
    assert verified.total_cost_usd == pytest.approx(1.0)


def test_risk_field_leakage_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, repo = _build_bundle(tmp_path, monkeypatch, inject_risk=True)
    with pytest.raises(MechanismExecutionBundleError, match="forbidden risk field"):
        verify_mechanism_execution_bundle(
            root,
            mechanism_authority_path=tmp_path / "authority.json",
            execution_manifest_freeze_path=tmp_path / "execution.json",
            repository_root=repo,
        )


def test_null_provider_call_id_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, repo = _build_bundle(tmp_path, monkeypatch, null_call_id=True)
    with pytest.raises(MechanismExecutionBundleError, match="real provider_call_id"):
        verify_mechanism_execution_bundle(
            root,
            mechanism_authority_path=tmp_path / "authority.json",
            execution_manifest_freeze_path=tmp_path / "execution.json",
            repository_root=repo,
        )


def test_product_promotion_flag_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, repo = _build_bundle(tmp_path, monkeypatch)
    manifest = root / "MECHANISM_EXECUTION_BUNDLE.json"
    doc = json.loads(manifest.read_text())
    doc["product_promotion_authorized"] = True
    _write(manifest, doc)
    with pytest.raises(MechanismExecutionBundleError, match="illegally grants"):
        verify_mechanism_execution_bundle(
            root,
            mechanism_authority_path=tmp_path / "authority.json",
            execution_manifest_freeze_path=tmp_path / "execution.json",
            repository_root=repo,
        )


def test_result_population_loss_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, repo = _build_bundle(tmp_path, monkeypatch)
    result = root / "records" / "00000000.json"
    result.unlink()
    with pytest.raises(MechanismExecutionBundleError, match="payload manifest mismatch|file missing"):
        verify_mechanism_execution_bundle(
            root,
            mechanism_authority_path=tmp_path / "authority.json",
            execution_manifest_freeze_path=tmp_path / "execution.json",
            repository_root=repo,
        )
