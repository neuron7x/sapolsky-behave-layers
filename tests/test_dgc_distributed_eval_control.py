import random
import pytest
from cwc.governance.distributed_eval_control import DistributedEvalCoordinator, DistributedEvalSpec


def spec(**overrides):
    base = dict(
        experiment_id="exp-v1",
        task_ids=("t2", "t1"),
        policy_ids=("dgc", "b0"),
        replicates=2,
        max_attempts_per_unit=2,
        lease_ttl_ticks=5,
        max_cost_per_unit_usd=1.0,
        global_budget_usd=8.0,
        harness_digest="a" * 64,
        statistical_plan_digest="b" * 64,
    )
    base.update(overrides)
    return DistributedEvalSpec(**base)


def commit_all(coordinator):
    tick = 0
    while True:
        lease = coordinator.claim("w", tick=tick)
        if lease is None:
            break
        coordinator.commit(
            lease,
            tick=tick + 1,
            result_payload={"unit": lease.unit.stable_id, "ok": True},
            evidence_digest="c" * 64,
            actual_cost_usd=0.25,
        )
        tick += 1
    return coordinator.completion_certificate(tick=tick + 10)


def test_spec_canonical_and_underbudget_rejected():
    frozen = spec()
    assert frozen.task_ids == ("t1", "t2")
    assert frozen.policy_ids == ("b0", "dgc")
    with pytest.raises(ValueError, match="worst-case"):
        spec(global_budget_usd=7.99)


def test_semantic_pseudo_digests_rejected():
    with pytest.raises(ValueError, match="SHA-256"):
        spec(harness_digest="model-v1")
    with pytest.raises(ValueError, match="SHA-256"):
        spec(statistical_plan_digest="s" * 64)


def test_deterministic_claim_order_and_full_coverage():
    coordinator = DistributedEvalCoordinator(spec())
    cert = commit_all(coordinator)
    assert cert.complete
    assert cert.expected_units == 8 == cert.committed_units
    assert cert.total_cost_usd == 2.0
    assert coordinator.verify_audit_chain()
    leased = [e.unit_id for e in coordinator.audit_events() if e.kind == "LEASE_GRANTED"]
    assert leased == sorted(leased)


def test_expired_lease_requeues_then_quarantines():
    coordinator = DistributedEvalCoordinator(
        spec(task_ids=("t1",), policy_ids=("dgc",), replicates=1, global_budget_usd=1.0)
    )
    assert coordinator.claim("w1", tick=0)
    second = coordinator.claim("w2", tick=5)
    assert second and second.attempt == 2
    assert coordinator.claim("w3", tick=10) is None
    assert coordinator.snapshot(tick=10)["counts"]["QUARANTINED"] == 1
    with pytest.raises(ValueError, match="quarantined"):
        coordinator.completion_certificate(tick=10)


def test_idempotent_same_result_conflict_quarantines():
    coordinator = DistributedEvalCoordinator(
        spec(task_ids=("t1",), policy_ids=("dgc",), replicates=1, global_budget_usd=1.0)
    )
    lease = coordinator.claim("w", tick=0)
    first = coordinator.commit(
        lease, tick=1, result_payload={"x": 1}, evidence_digest="c" * 64, actual_cost_usd=0.2
    )
    assert coordinator.commit(
        lease, tick=2, result_payload={"x": 1}, evidence_digest="c" * 64, actual_cost_usd=0.2
    ) == first
    with pytest.raises(ValueError, match="conflicting duplicate"):
        coordinator.commit(
            lease, tick=2, result_payload={"x": 2}, evidence_digest="c" * 64, actual_cost_usd=0.2
        )
    assert coordinator.snapshot(tick=2)["counts"]["QUARANTINED"] == 1


def test_stale_worker_cannot_commit_after_reassignment():
    coordinator = DistributedEvalCoordinator(
        spec(task_ids=("t1",), policy_ids=("dgc",), replicates=1, global_budget_usd=1.0)
    )
    old = coordinator.claim("slow", tick=0)
    new = coordinator.claim("retry", tick=5)
    with pytest.raises(ValueError, match="stale or forged lease"):
        coordinator.commit(
            old, tick=6, result_payload={"late": 1}, evidence_digest="c" * 64, actual_cost_usd=0.1
        )
    coordinator.commit(
        new, tick=6, result_payload={"ok": 1}, evidence_digest="c" * 64, actual_cost_usd=0.1
    )
    assert coordinator.completion_certificate(tick=7).complete


def test_cost_cap_and_evidence_digest_hard():
    coordinator = DistributedEvalCoordinator(
        spec(task_ids=("t1",), policy_ids=("dgc",), replicates=1, global_budget_usd=1.0)
    )
    lease = coordinator.claim("w", tick=0)
    with pytest.raises(ValueError, match="per-unit cap"):
        coordinator.commit(
            lease, tick=1, result_payload={"x": 1}, evidence_digest="c" * 64, actual_cost_usd=1.01
        )
    with pytest.raises(ValueError, match="SHA-256"):
        coordinator.commit(
            lease, tick=1, result_payload={"x": 1}, evidence_digest="semantic-evidence", actual_cost_usd=0.1
        )


def test_completion_refuses_partial_population():
    coordinator = DistributedEvalCoordinator(spec())
    lease = coordinator.claim("w", tick=0)
    coordinator.commit(
        lease, tick=1, result_payload={"ok": 1}, evidence_digest="c" * 64, actual_cost_usd=0.1
    )
    with pytest.raises(ValueError, match="full preregistered coverage"):
        coordinator.completion_certificate(tick=2)


def test_random_worker_schedule_preserves_population_and_audit():
    for seed in range(50):
        rng = random.Random(seed)
        coordinator = DistributedEvalCoordinator(spec())
        tick = 0
        while True:
            lease = coordinator.claim(f"w{rng.randrange(5)}", tick=tick)
            if lease is None:
                break
            coordinator.commit(
                lease,
                tick=tick + rng.randrange(1, 5),
                result_payload={"u": lease.unit.stable_id},
                evidence_digest=("a" if seed % 2 else "b") * 64,
                actual_cost_usd=rng.random() * 0.5,
            )
            tick += 5
        cert = coordinator.completion_certificate(tick=tick + 1)
        assert cert.expected_units == 8 and cert.committed_units == 8
        assert coordinator.verify_audit_chain()
