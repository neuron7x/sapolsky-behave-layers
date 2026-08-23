from __future__ import annotations

import itertools

from cwc.governance.distributed_eval_control import DistributedEvalCoordinator, DistributedEvalSpec


def _spec() -> DistributedEvalSpec:
    return DistributedEvalSpec(
        experiment_id="finite-modelcheck",
        task_ids=("task",),
        policy_ids=("dgc",),
        replicates=1,
        max_attempts_per_unit=2,
        lease_ttl_ticks=2,
        max_cost_per_unit_usd=1.0,
        global_budget_usd=1.0,
        harness_digest="a" * 64,
        statistical_plan_digest="b" * 64,
    )


def main() -> int:
    schedules = 0
    completed = 0
    quarantined = 0
    stale_rejections = 0

    for first_delay, retry_delay, retry_worker in itertools.product(
        range(4), range(4), ("w1", "w2")
    ):
        schedules += 1
        coordinator = DistributedEvalCoordinator(_spec())
        first = coordinator.claim("w0", tick=0)
        assert first is not None
        first_tick = first_delay
        first_committed = False

        if first_delay < 2:
            coordinator.commit(
                first,
                tick=first_tick,
                result_payload={"attempt": 1, "delay": first_delay},
                evidence_digest="c" * 64,
                actual_cost_usd=0.25,
            )
            first_committed = True
        else:
            coordinator.snapshot(tick=first_tick)

        if not first_committed:
            retry = coordinator.claim(retry_worker, tick=first_tick)
            if retry is not None:
                try:
                    coordinator.commit(
                        first,
                        tick=first_tick,
                        result_payload={"stale": True},
                        evidence_digest="c" * 64,
                        actual_cost_usd=0.1,
                    )
                except ValueError:
                    stale_rejections += 1
                else:
                    raise AssertionError("stale lease committed after reassignment")

                retry_tick = first_tick + retry_delay
                if retry_delay < 2:
                    coordinator.commit(
                        retry,
                        tick=retry_tick,
                        result_payload={"attempt": 2, "delay": retry_delay},
                        evidence_digest="d" * 64,
                        actual_cost_usd=0.25,
                    )
                else:
                    coordinator.snapshot(tick=retry_tick)

        horizon = max(first_tick, first_tick + retry_delay) + 1
        snapshot = coordinator.snapshot(tick=horizon)
        if snapshot["spent_usd"] < -1e-12 or snapshot["reserved_usd"] < -1e-12:
            raise AssertionError("negative accounting state")
        if snapshot["spent_usd"] + snapshot["reserved_usd"] > 1.0 + 1e-12:
            raise AssertionError("global budget invariant violated")
        if not coordinator.verify_audit_chain():
            raise AssertionError("audit chain invalid")

        try:
            cert = coordinator.completion_certificate(tick=horizon + 1)
        except ValueError:
            quarantined += 1
        else:
            if not cert.complete or cert.expected_units != 1 or cert.committed_units != 1:
                raise AssertionError("invalid completion certificate")
            completed += 1

    if schedules != 32:
        raise AssertionError(f"unexpected schedule count {schedules}")
    if completed == 0 or quarantined == 0 or stale_rejections == 0:
        raise AssertionError("modelcheck did not exercise success/failure/reassignment classes")
    print(
        "DGC-DISTRIBUTED-MODELCHECK: PASS "
        f"schedules={schedules} completed={completed} quarantined={quarantined} "
        f"stale_rejections={stale_rejections}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
