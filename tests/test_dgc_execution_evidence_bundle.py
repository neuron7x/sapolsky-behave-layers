from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

import cwc.governance.execution_evidence_bundle as bundle_module
from cwc.governance.distributed_eval_control import DistributedEvalCoordinator, DistributedEvalSpec
from cwc.governance.execution_evidence_bundle import ExecutionEvidenceError, verify_execution_bundle
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.physical_cost_evidence import (
    PRODUCT_COST_COMPONENTS,
    CostAuthority,
    CostComponentEvidence,
    certify_physical_trial_cost,
)


def h(char: str) -> str:
    return char * 64


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def root_authority(spec: DistributedEvalSpec) -> dict:
    return {
        "family_id": "FAM",
        "authority_digest": h("a"),
        "distributed_spec_digest": spec.digest,
        "distributed_spec": asdict(spec),
        "root": {"root_digest": h("b")},
    }


def audit_document(coordinator: DistributedEvalCoordinator, spec: DistributedEvalSpec) -> dict:
    events = [asdict(event) for event in coordinator.audit_events()]
    root = events[-1]["event_digest"]
    payload = {"spec_digest": spec.digest, "events": events, "audit_root_digest": root}
    return {
        "schema": "DGC_DISTRIBUTED_AUDIT_LOG_V1",
        **payload,
        "audit_log_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def result_document(*, authority: dict, spec: DistributedEvalSpec, result, result_payload: dict, evidence_rel: str, evidence_sha: str) -> dict:
    payload = {
        "root_authority_digest": authority["authority_digest"],
        "root_digest": authority["root"]["root_digest"],
        "distributed_spec_digest": spec.digest,
        "unit": asdict(result.unit),
        "attempt": result.attempt,
        "worker_id": result.worker_id,
        "committed_tick": result.committed_tick,
        "result_payload": result_payload,
        "result_digest": result.result_digest,
        "actual_cost_usd": result.actual_cost_usd,
        "evidence_path": evidence_rel,
        "evidence_sha256": evidence_sha,
    }
    return {
        "schema": "DGC_CONFIRMATORY_RESULT_V1",
        **payload,
        "record_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def seal_manifest(root: Path, *, authority: dict, spec: DistributedEvalSpec, result_paths: list[str], coordinator: DistributedEvalCoordinator) -> None:
    completion = coordinator.completion_certificate(tick=100)
    rows = file_manifest(root, excluded_names=frozenset({"EXECUTION_BUNDLE.json"}))
    payload_digest = sha256_bytes(canonical_json_bytes(rows))
    payload = {
        "family_id": authority["family_id"],
        "root_authority_digest": authority["authority_digest"],
        "root_digest": authority["root"]["root_digest"],
        "distributed_spec_digest": spec.digest,
        "payload_manifest_sha256": payload_digest,
        "audit_log_path": "AUDIT_LOG.json",
        "result_paths": result_paths,
        "expected_units": completion.expected_units,
        "committed_units": completion.committed_units,
        "audit_root_digest": completion.audit_root_digest,
        "result_population_digest": completion.result_population_digest,
        "total_cost_usd": completion.total_cost_usd,
        "product_promotion_authorized": False,
    }
    write_json(root / "EXECUTION_BUNDLE.json", {
        "schema": "DGC_CONFIRMATORY_EXECUTION_BUNDLE_V1",
        **payload,
        "bundle_digest": sha256_bytes(canonical_json_bytes(payload)),
    })


def make_bundle(tmp_path: Path):
    spec = DistributedEvalSpec(
        experiment_id="exp-1",
        task_ids=("t1",),
        policy_ids=("B0", "DGC"),
        replicates=1,
        max_attempts_per_unit=2,
        lease_ttl_ticks=10,
        max_cost_per_unit_usd=1.0,
        global_budget_usd=2.0,
        harness_digest=h("1"),
        statistical_plan_digest=h("2"),
    )
    authority = root_authority(spec)
    coordinator = DistributedEvalCoordinator(spec)
    root = tmp_path / "bundle"
    results_dir = root / "records"
    evidence_dir = root / "evidence"
    result_paths: list[str] = []
    tick = 0
    for index, policy in enumerate(("B0", "DGC")):
        lease = coordinator.claim(f"worker-{policy}", tick=tick)
        assert lease is not None
        tick += 1
        actual_cost = 0.6 - 0.2 * index
        adapter_response = {
            "schema": "DGC_UNIT_EXECUTION_RESPONSE_V1",
            "unit": asdict(lease.unit),
            "attempt": lease.attempt,
            "quality": 0.8 + 0.1 * index,
            "actual_cost_usd": actual_cost,
            "trace": {"provider_request_id": f"req-{policy}"},
        }
        adapter_digest = sha256_bytes(canonical_json_bytes(adapter_response))
        trace_digest = sha256_bytes(canonical_json_bytes(adapter_response["trace"]))
        risk_response = {
            "schema": "DGC_RISK_ENDPOINT_RESPONSE_V1",
            "catastrophic_regret": 0.1 - 0.05 * index,
            "evidence": {"source": "fixture", "policy": policy},
        }
        risk_digest = sha256_bytes(canonical_json_bytes(risk_response))
        cost_evidence = {}
        for component in PRODUCT_COST_COMPONENTS:
            cost_evidence[component] = CostComponentEvidence(
                component=component,
                value_usd=actual_cost if component == "model_usd" else 0.0,
                authority=(
                    CostAuthority.PROVIDER_METER
                    if component == "model_usd"
                    else CostAuthority.ZERO_BY_CONTRACT
                ),
                source_digest=h("c"),
            )
        cost_certificate = certify_physical_trial_cost(
            trial_id=f"{lease.unit.stable_id}::{lease.attempt}",
            evidence=cost_evidence,
        )
        result_payload = {
            "quality": adapter_response["quality"],
            "catastrophic_regret": risk_response["catastrophic_regret"],
            "adapter_response_digest": adapter_digest,
            "trace_digest": trace_digest,
            "risk_endpoint_response_digest": risk_digest,
            "physical_cost_certificate_digest": cost_certificate.digest,
        }
        evidence = evidence_dir / f"{policy}.json"
        write_json(evidence, {
            "schema": "DGC_UNIT_EXECUTION_EVIDENCE_V1",
            "response": adapter_response,
            "adapter_response_digest": adapter_digest,
            "trace_digest": trace_digest,
            "risk_endpoint_response": risk_response,
            "risk_endpoint_response_digest": risk_digest,
            "physical_cost_certificate": {
                "trial_id": cost_certificate.trial_id,
                "digest": cost_certificate.digest,
                "components": [
                    {
                        "component": row.component,
                        "value_usd": row.value_usd,
                        "authority": row.authority.value,
                        "source_digest": row.source_digest,
                    }
                    for row in cost_certificate.component_evidence
                ],
                "total_operational_usd": cost_certificate.cost.total_operational_usd,
            },
        })
        evidence_sha = sha256_file(evidence)
        result = coordinator.commit(
            lease,
            tick=tick,
            result_payload=result_payload,
            evidence_digest=evidence_sha,
            actual_cost_usd=actual_cost,
        )
        tick += 1
        rel = f"records/{policy}.json"
        write_json(
            root / rel,
            result_document(
                authority=authority,
                spec=spec,
                result=result,
                result_payload=result_payload,
                evidence_rel=f"evidence/{policy}.json",
                evidence_sha=evidence_sha,
            ),
        )
        result_paths.append(rel)
    write_json(root / "AUDIT_LOG.json", audit_document(coordinator, spec))
    seal_manifest(root, authority=authority, spec=spec, result_paths=result_paths, coordinator=coordinator)
    return root, authority, spec, coordinator


def patch_root(monkeypatch: pytest.MonkeyPatch, authority: dict) -> None:
    monkeypatch.setattr(bundle_module, "verify_confirmatory_root_authority_document", lambda _: authority)


def test_complete_execution_bundle_replays_exact_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, authority, spec, coordinator = make_bundle(tmp_path)
    patch_root(monkeypatch, authority)
    verified = verify_execution_bundle(root, confirmatory_root_authority_path=tmp_path / "root.json")
    expected = coordinator.completion_certificate(tick=100)
    assert verified.completion == expected
    assert verified.distributed_spec_digest == spec.digest
    assert len(verified.results) == 2


def test_missing_frozen_unit_cannot_be_hidden_by_self_consistent_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, authority, spec, coordinator = make_bundle(tmp_path)
    patch_root(monkeypatch, authority)
    (root / "records" / "B0.json").unlink()
    # Re-seal the reduced payload and result path list: cryptographic self-consistency is not enough.
    seal_manifest(root, authority=authority, spec=spec, result_paths=["records/DGC.json"], coordinator=coordinator)
    with pytest.raises(ExecutionEvidenceError, match="full frozen work population"):
        verify_execution_bundle(root, confirmatory_root_authority_path=tmp_path / "root.json")


def test_result_record_cannot_disagree_with_coordinator_commit_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, authority, spec, coordinator = make_bundle(tmp_path)
    patch_root(monkeypatch, authority)
    path = root / "records" / "DGC.json"
    doc = json.loads(path.read_text())
    doc["committed_tick"] += 1
    payload = {key: value for key, value in doc.items() if key not in {"schema", "record_digest"}}
    doc["record_digest"] = sha256_bytes(canonical_json_bytes(payload))
    write_json(path, doc)
    seal_manifest(root, authority=authority, spec=spec, result_paths=["records/B0.json", "records/DGC.json"], coordinator=coordinator)
    with pytest.raises(ExecutionEvidenceError, match="coordinator commit audit event"):
        verify_execution_bundle(root, confirmatory_root_authority_path=tmp_path / "root.json")


def test_evidence_tamper_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, authority, _, _ = make_bundle(tmp_path)
    patch_root(monkeypatch, authority)
    write_json(root / "evidence" / "DGC.json", {"provider_trace": "tampered"})
    with pytest.raises(ExecutionEvidenceError, match="payload manifest mismatch"):
        verify_execution_bundle(root, confirmatory_root_authority_path=tmp_path / "root.json")


def test_risk_semantic_tamper_is_rejected_even_after_rehash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, authority, spec, coordinator = make_bundle(tmp_path)
    patch_root(monkeypatch, authority)
    evidence_path = root / "evidence" / "DGC.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["risk_endpoint_response"]["catastrophic_regret"] = 0.9
    evidence["risk_endpoint_response_digest"] = sha256_bytes(
        canonical_json_bytes(evidence["risk_endpoint_response"])
    )
    write_json(evidence_path, evidence)
    evidence_sha = sha256_file(evidence_path)
    result_path = root / "records" / "DGC.json"
    result = json.loads(result_path.read_text())
    result["evidence_sha256"] = evidence_sha
    payload = {key: value for key, value in result.items() if key not in {"schema", "record_digest"}}
    result["record_digest"] = sha256_bytes(canonical_json_bytes(payload))
    write_json(result_path, result)
    seal_manifest(
        root,
        authority=authority,
        spec=spec,
        result_paths=["records/B0.json", "records/DGC.json"],
        coordinator=coordinator,
    )
    with pytest.raises(ExecutionEvidenceError, match="result is not bound to frozen risk response"):
        verify_execution_bundle(root, confirmatory_root_authority_path=tmp_path / "root.json")


def test_physical_cost_semantic_tamper_is_rejected_even_after_rehash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root, authority, spec, coordinator = make_bundle(tmp_path)
    patch_root(monkeypatch, authority)
    evidence_path = root / "evidence" / "DGC.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["physical_cost_certificate"]["components"][0]["value_usd"] += 0.1
    write_json(evidence_path, evidence)
    evidence_sha = sha256_file(evidence_path)
    result_path = root / "records" / "DGC.json"
    result = json.loads(result_path.read_text())
    result["evidence_sha256"] = evidence_sha
    payload = {key: value for key, value in result.items() if key not in {"schema", "record_digest"}}
    result["record_digest"] = sha256_bytes(canonical_json_bytes(payload))
    write_json(result_path, result)
    seal_manifest(
        root,
        authority=authority,
        spec=spec,
        result_paths=["records/B0.json", "records/DGC.json"],
        coordinator=coordinator,
    )
    with pytest.raises(ExecutionEvidenceError, match="physical cost certificate digest mismatch"):
        verify_execution_bundle(root, confirmatory_root_authority_path=tmp_path / "root.json")


def test_parent_symlink_alias_for_evidence_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root, authority, spec, coordinator = make_bundle(tmp_path)
    patch_root(monkeypatch, authority)
    evidence = root / "evidence"
    real = root / "evidence-real"
    evidence.rename(real)
    evidence.symlink_to(real, target_is_directory=True)
    seal_manifest(
        root,
        authority=authority,
        spec=spec,
        result_paths=["records/B0.json", "records/DGC.json"],
        coordinator=coordinator,
    )
    with pytest.raises(ExecutionEvidenceError, match="execution evidence symlink rejected"):
        verify_execution_bundle(root, confirmatory_root_authority_path=tmp_path / "root.json")
