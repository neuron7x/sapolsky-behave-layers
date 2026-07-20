"""Tests for the Act-J identifiability pilot decision instrument.

These assert the preregistered decision rule and — critically — that the pilot CAN
fail: the negative controls must be refused and the certificate must actually debias.
A pilot whose controls could not fail would be worthless.
"""
from __future__ import annotations

import math

from experiments.act_j_pilot_decision.src import runner


def _result():
    return runner.run()


def test_verdict_is_go_and_deterministic():
    r1 = _result()
    r2 = _result()
    assert r1 == r2, "pilot must be deterministic on frozen real data"
    assert r1["verdict"] == "PILOT_GO_L4_CONFIRMATORY"


def test_certificate_actually_debiases_and_stays_positive():
    p = _result()["primary"]
    # The debiased lower bound must be strictly below the (upward-biased) plug-in
    # estimate, and still strictly positive to certify identifiability.
    assert p["gap_lower_bound"] < p["gap_hat"]
    assert p["gap_lower_bound"] > 0.0
    # Documented plasticity-revival gap ~0.19 (see identifiability_theory.py note).
    assert math.isclose(p["gap_hat"], 0.1906, abs_tol=5e-3)


def test_negative_controls_are_refused():
    c = _result()["controls"]
    assert c["negative_A"]["identifiable"] is False  # weak interaction (lambda=0)
    assert c["negative_B"]["identifiable"] is False  # quality dominance (routing)


def test_positive_control_is_certified_at_pilot_noise():
    c = _result()["controls"]
    assert c["positive"]["identifiable"] is True
    # positive control must be evaluated at the primary pilot's own noise level
    assert math.isclose(c["positive"]["std_error"], _result()["primary"]["std_error"], rel_tol=1e-9)


def test_certificate_self_falsification_holds():
    f = _result()["certificate_self_falsification"]
    assert f["all_ok"] is True
    assert f["calibration_valid"] is True
    assert f["naive_rule_fails"] is True


def test_bonferroni_and_headroom_bookkeeping():
    r = _result()
    assert math.isclose(r["delta_eff_bonferroni_over_lambda_grid"], 0.05 / 4)
    assert r["c_route"] == 0.0
    assert math.isclose(r["route_cost_headroom"], r["primary"]["gap_lower_bound"])


def test_go_requires_all_controls_ok():
    # If any control were violated the verdict would be VOID, not GO. Encoded here so a
    # future regression that silently breaks a control cannot masquerade as a GO.
    r = _result()
    assert r["controls"]["controls_ok"] is True
    assert r["verdict"] == "PILOT_GO_L4_CONFIRMATORY"
