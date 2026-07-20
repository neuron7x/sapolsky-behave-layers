"""Falsification suite for the CWC coherence + efficiency audit.

Verifies that the real claim ladder is internally consistent (theory verdict ==
recorded status for every entry), that the auditor can DETECT an injected
inconsistency (a proof that could not fail is not a proof), and that the
identifiability predictor attains its information-theoretic complexity lower bound.
"""
import pytest

from experiments.common.coherence_audit import (
    POSITIVE,
    VETO_COMPUTATION,
    VETO_DOMINANCE,
    VETO_INFORMATION,
    audit_ladder,
    certificate,
    classify,
    complexity_is_optimal,
    falsify_coherence,
    predictor_op_count,
)


# ------------------------------- coherence --------------------------------- #
def test_real_claim_ladder_is_coherent():
    audit = audit_ladder()
    assert audit["coherent"] is True
    assert audit["contradictions"] == []
    assert audit["n"] >= 6  # all recorded regimes are audited


def test_every_row_matches_theory_and_record():
    for row in audit_ladder()["rows"]:
        assert row["coherent"] is True, row["claim_id"]


def test_auditor_detects_injected_incoherence():
    # a proof of coherence is worthless unless it can catch a violation
    result = falsify_coherence()
    assert result["real_ladder_coherent"] is True
    assert result["injected_fault_caught"] is True
    assert result["auditor_sound"] is True


def test_auditor_catches_faults_in_both_directions():
    # DESTRUCTION STAGE: the auditor must catch incoherence of every kind, not one.
    # reverse fault: a genuinely identifiable (G>0) problem tagged as a NEGATIVE status
    reverse = [{"claim_id": "REV", "status": "NOT_SUPPORTED",
                "utility": [[1.0, 0.0], [0.0, 1.0]], "route_cost": 0.0, "expect": POSITIVE}]
    assert audit_ladder(reverse)["coherent"] is False
    # wrong-veto-class fault: a dominance problem whose expected veto is mislabelled
    wrong_veto = [{"claim_id": "WV", "status": "NOT_SUPPORTED",
                   "utility": [[1.0, 1.0], [1.0, 1.0]], "route_cost": 0.0, "expect": VETO_COMPUTATION}]
    assert audit_ladder(wrong_veto)["coherent"] is False


# --------------------------- the three vetoes ------------------------------ #
def test_classify_selects_the_right_veto():
    assert classify(0.0, 5.0, 0.0) == VETO_DOMINANCE       # no oracle gap
    assert classify(0.5, 0.0, 0.0) == VETO_INFORMATION     # no signal information
    assert classify(0.5, 5.0, 0.5) == VETO_COMPUTATION     # cost >= binding ceiling
    assert classify(0.5, 5.0, 0.1) == POSITIVE             # all three clear


def test_certificate_is_min_of_ceilings_minus_cost():
    assert certificate(0.4, 0.9, 0.1) == pytest.approx(0.4 - 0.1)   # oracle gap binds
    assert certificate(0.9, 0.3, 0.1) == pytest.approx(0.3 - 0.1)   # information binds
    assert certificate(0.5, 0.5, 0.6) == pytest.approx(-0.1)        # net negative


def test_negative_route_cost_and_negative_gap_rejected():
    with pytest.raises(ValueError):
        certificate(0.5, 0.5, -0.1)
    with pytest.raises(ValueError):
        classify(-0.5, 0.5, 0.0)


# ------------------------------- efficiency -------------------------------- #
@pytest.mark.parametrize("n_c,n_a", [(2, 2), (3, 4), (10, 20), (100, 50), (7, 3)])
def test_predictor_attains_complexity_lower_bound(n_c, n_a):
    cx = complexity_is_optimal(n_c, n_a)
    assert cx["reads"] == n_c * n_a           # reads every entry exactly once
    assert cx["attains_lower_bound"] is True  # optimal: cannot do fewer reads
    assert cx["compares"] == n_c * (n_a - 1)
    assert cx["linear"] is True


def test_op_count_is_exactly_linear_in_size():
    # doubling |A| doubles the reads; the constant is exactly 1 read per entry
    a = predictor_op_count([[1.0, 2.0]], [0.0, 0.0], 0.5)
    b = predictor_op_count([[1.0, 2.0, 3.0, 4.0]], [0.0, 0.0, 0.0, 0.0], 0.5)
    assert a["reads"] == 2 and b["reads"] == 4
    assert b["reads"] == 2 * a["reads"]


def test_predictor_detects_identifiability():
    # argmax varies with context => identifiable
    varying = predictor_op_count([[1.0, 0.0], [0.0, 1.0]], [0.0, 0.0], 0.0)
    assert varying["identifiable"] == 1
    # one action dominates => not identifiable (constant argmax)
    constant = predictor_op_count([[1.0, 0.5], [1.0, 0.5]], [0.0, 0.0], 0.0)
    assert constant["identifiable"] == 0
