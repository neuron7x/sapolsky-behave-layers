from __future__ import annotations

import numpy as np
import pytest

from experiments.cwc_flagship_route_01 import core
from experiments.cwc_flagship_route_01.semantic_gate import self_test


def test_frozen_data_hashes() -> None:
    assert core.verify_data_hashes() == core.EXPECTED_SHA256


def test_seed_contract() -> None:
    core.validate_seed_contract()


def test_window_membership_deterministic_and_disjoint() -> None:
    sets = {}
    for fam in ("PROSE", "CODE"):
        for cohort in ("CALIBRATION", "PRIMARY", "REPLICATION"):
            ids1 = [x.case_id for x in core.window_cases(fam, cohort)]
            ids2 = [x.case_id for x in core.window_cases(fam, cohort)]
            assert ids1 == ids2
            sets[(fam, cohort)] = set(ids1)
        assert sets[(fam, "CALIBRATION")].isdisjoint(sets[(fam, "PRIMARY")])
        assert sets[(fam, "CALIBRATION")].isdisjoint(sets[(fam, "REPLICATION")])
        assert sets[(fam, "PRIMARY")].isdisjoint(sets[(fam, "REPLICATION")])


def test_case_counts() -> None:
    assert len(core.window_cases("PROSE", "CALIBRATION")) == 128
    assert len(core.window_cases("PROSE", "PRIMARY")) == 128
    assert len(core.window_cases("PROSE", "REPLICATION")) == 64
    assert len(core.window_cases("CODE", "CALIBRATION")) == 128
    assert len(core.window_cases("CODE", "PRIMARY")) == 128
    assert len(core.window_cases("CODE", "REPLICATION")) == 64


def test_flop_contract_orders_depths_and_charges_router() -> None:
    f = core.flop_contract()
    assert f.block > 0 and f.head > 0 and f.route > 0
    assert f.fixed_depth1 < f.fixed_depth2
    assert core.dynamic_compute(0, 100) > f.fixed_depth1
    assert core.dynamic_compute(100, 100) > f.fixed_depth2


def test_fixed_frontier_uses_budget_not_forced_spend() -> None:
    f = core.flop_contract()
    mid = (f.fixed_depth1 + f.fixed_depth2) / 2
    assert core.fixed_frontier_loss(1.0, 2.0, mid) == 1.0
    assert core.fixed_frontier_loss(2.0, 1.0, mid) == pytest.approx(1.5)
    with pytest.raises(core.ProtocolViolation):
        core.fixed_frontier_loss(2.0, 1.0, f.fixed_depth2 + 1)


def test_ridge_calibration_only_and_predicts_shape() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(size=(30, 65)); y = x[:, 0] * 2 - x[:, 1]
    m = core.fit_ridge(x, y, cohort="CALIBRATION")
    assert m.predict(x).shape == (30,)
    with pytest.raises(core.ProtocolViolation):
        core.fit_ridge(x, y, cohort="PRIMARY")


def test_selector_matches_count() -> None:
    score = np.arange(10, dtype=float)
    ids = [f"id{i}" for i in range(10)]
    assert int(core._select_top(score, 3, ids).sum()) == 3
    assert int(core._random_matched(ids, 3).sum()) == 3


def test_primary_failure_cannot_be_rescued() -> None:
    assert core.final_verdict({"passed": False}, {"passed": True}) == "CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED"


def test_semantic_mutations_all_die() -> None:
    r = self_test()
    assert r["passed"] is True
    assert r["killed"] == r["total"] == 14
