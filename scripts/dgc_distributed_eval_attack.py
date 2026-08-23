from cwc.governance.distributed_eval_control import DistributedEvalCoordinator, DistributedEvalSpec


def main():
    spec = DistributedEvalSpec(
        experiment_id="attack",
        task_ids=("t",),
        policy_ids=("dgc",),
        replicates=1,
        max_attempts_per_unit=2,
        lease_ttl_ticks=2,
        max_cost_per_unit_usd=1.0,
        global_budget_usd=1.0,
        harness_digest="h" * 64,
        statistical_plan_digest="s" * 64,
    )
    killed = 0

    coordinator = DistributedEvalCoordinator(spec)
    stale = coordinator.claim("w1", tick=0)
    try:
        coordinator.completion_certificate(tick=0)
    except ValueError:
        killed += 1
    coordinator.claim("w2", tick=2)
    try:
        coordinator.commit(
            stale,
            tick=3,
            result_payload={"stale": 1},
            evidence_digest="e" * 64,
            actual_cost_usd=0.1,
        )
    except ValueError:
        killed += 1

    duplicate = DistributedEvalCoordinator(spec)
    lease = duplicate.claim("w", tick=0)
    duplicate.commit(
        lease,
        tick=1,
        result_payload={"x": 1},
        evidence_digest="e" * 64,
        actual_cost_usd=0.1,
    )
    try:
        duplicate.commit(
            lease,
            tick=1,
            result_payload={"x": 2},
            evidence_digest="e" * 64,
            actual_cost_usd=0.1,
        )
    except ValueError:
        killed += 1

    try:
        DistributedEvalSpec(
            experiment_id="underbudgeted",
            task_ids=("a", "b"),
            policy_ids=("dgc",),
            replicates=1,
            max_attempts_per_unit=1,
            lease_ttl_ticks=2,
            max_cost_per_unit_usd=1.0,
            global_budget_usd=1.9,
            harness_digest="h" * 64,
            statistical_plan_digest="s" * 64,
        )
    except ValueError:
        killed += 1

    if killed != 4:
        raise AssertionError(f"expected 4/4 attacks killed, got {killed}")
    print("DGC-DISTRIBUTED-EVAL-ATTACK: PASS killed=4/4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
