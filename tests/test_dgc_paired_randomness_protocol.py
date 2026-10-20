from __future__ import annotations

import pytest

from cwc.governance.distributed_eval_control import CompletionCertificate, WorkUnitId
from cwc.governance.execution_evidence_bundle import VerifiedExecutionBundle, VerifiedExecutionResult
from cwc.governance.paired_randomness_protocol import (
    PROTOCOL,
    RandomnessProtocolError,
    paired_seed,
    verify_paired_randomness_protocol,
)

# No producer in the repository writes randomness_protocol/replicate_seed into a
# confirmatory result payload, so these falsifiers exercise the verifier directly
# on constructed verified-bundle objects.

ROOT_DIGEST = "b" * 64


def _result(
    policy: str,
    *,
    live_source_ids: tuple[str, ...],
    payload_extra: dict[str, object] | None = None,
) -> VerifiedExecutionResult:
    unit = WorkUnitId(task_id="t1", policy_id=policy, replicate=0)
    payload: dict[str, object] = {
        "randomness_protocol": PROTOCOL,
        "replicate_seed": paired_seed(root_digest=ROOT_DIGEST, task_id="t1", replicate=0),
        **(payload_extra or {}),
    }
    return VerifiedExecutionResult(
        unit=unit,
        attempt=1,
        worker_id=f"worker-{policy}",
        committed_tick=1,
        result_payload=payload,
        result_digest="c" * 64,
        quality=0.5,
        catastrophic_regret=0.0,
        actual_cost_usd=0.1,
        evidence_path=f"evidence/{policy}.json",
        evidence_digest="d" * 64,
        record_digest="e" * 64,
        commit_event_sequence=1,
        live_source_ids=live_source_ids,
    )


def _bundle(*results: VerifiedExecutionResult) -> VerifiedExecutionBundle:
    return VerifiedExecutionBundle(
        family_id="FAM",
        root_authority_digest="a" * 64,
        root_digest=ROOT_DIGEST,
        distributed_spec_digest="1" * 64,
        payload_manifest_sha256="2" * 64,
        audit_root_digest="3" * 64,
        result_population_digest="4" * 64,
        total_cost_usd=0.1 * len(results),
        results=results,
        completion=CompletionCertificate(
            experiment_id="exp",
            spec_digest="1" * 64,
            expected_units=len(results),
            committed_units=len(results),
            total_cost_usd=0.1 * len(results),
            audit_root_digest="3" * 64,
            result_population_digest="4" * 64,
            complete=True,
        ),
        bundle_digest="5" * 64,
    )


def test_randomness_counts_verified_live_source_population_not_payload_field():
    # No provider_request_id in the payload at all; the verified population carries
    # three calls (one unit made two provider calls).
    authority = verify_paired_randomness_protocol(
        _bundle(
            _result("B0", live_source_ids=("provider:req-1", "provider:req-2")),
            _result("DGC", live_source_ids=("provider:req-3",)),
        ),
        root_digest=ROOT_DIGEST,
    )
    assert authority.task_replicate_pairs == 1
    assert authority.provider_requests == 3


def test_verified_source_reuse_is_rejected_even_when_payload_ids_differ():
    with pytest.raises(
        RandomnessProtocolError, match="live usage source identity reused across execution units"
    ):
        verify_paired_randomness_protocol(
            _bundle(
                _result(
                    "B0",
                    live_source_ids=("provider:req-shared",),
                    payload_extra={"provider_request_id": "claimed-1"},
                ),
                _result(
                    "DGC",
                    live_source_ids=("provider:req-shared",),
                    payload_extra={"provider_request_id": "claimed-2"},
                ),
            ),
            root_digest=ROOT_DIGEST,
        )


def test_payload_request_id_cannot_stand_in_for_missing_verified_population():
    with pytest.raises(
        RandomnessProtocolError, match="verified live source population required"
    ):
        verify_paired_randomness_protocol(
            _bundle(
                _result("B0", live_source_ids=(), payload_extra={"provider_request_id": "claimed-1"}),
                _result("DGC", live_source_ids=("provider:req-2",)),
            ),
            root_digest=ROOT_DIGEST,
        )
