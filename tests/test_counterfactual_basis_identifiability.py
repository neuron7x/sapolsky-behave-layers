from __future__ import annotations

from scripts.counterfactual_basis_identifiability_gate import FAMILIES, factorial_rows, run_gate
from cwc.counterfactual.identifiability import (
    audit_counterfactual_basis_orthogonality,
    certify_counterfactual_basis,
)


def test_full_factorial_identifies_all_declared_counterfactual_bases():
    rows = factorial_rows()
    for family in FAMILIES:
        result = certify_counterfactual_basis(family, rows)
        assert result.certificate.state == "LOCAL_FIRST_ORDER_IDENTIFIABLE"
        assert result.certificate.numerical_rank == len(result.term_names)
        assert result.certificate.causal_authority_granted is False


def test_c_equals_a_factual_slice_exposes_rank_loss():
    rows = [row for row in factorial_rows() if row["C"] == row["A"]]
    expected_rank = {"LINEAR": 5, "CONTEXT": 8, "NONLINEAR": 11}
    expected_terms = {"LINEAR": 6, "CONTEXT": 10, "NONLINEAR": 16}
    for family in FAMILIES:
        result = certify_counterfactual_basis(family, rows)
        assert result.certificate.state == "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE"
        assert result.certificate.numerical_rank == expected_rank[family]
        assert len(result.term_names) == expected_terms[family]
        assert len(result.certificate.nullspace_basis) == expected_terms[family] - expected_rank[family]


def test_constant_context_breaks_context_dependent_bases():
    rows = [row for row in factorial_rows() if row["context"] == 1.0]
    assert certify_counterfactual_basis("CONTEXT", rows).certificate.state == "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE"
    assert certify_counterfactual_basis("NONLINEAR", rows).certificate.state == "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE"


def test_gate_distinguishes_interventional_design_from_confounded_observation():
    result = run_gate()
    assert result["state"] == "PASS"
    assert result["full_factorial_rows"] == 32
    assert result["confounded_rows"] == 16


def test_full_factorial_basis_is_exactly_orthogonal_and_unit_conditioned_up_to_scale():
    rows = factorial_rows()
    for family in FAMILIES:
        audit = audit_counterfactual_basis_orthogonality(family, rows)
        assert audit.orthogonal_equal_norm is True
        assert audit.expected_diagonal == 32.0
        assert audit.minimum_diagonal == 32.0
        assert audit.maximum_diagonal == 32.0
        assert audit.maximum_absolute_off_diagonal == 0.0
        assert abs(audit.gram_condition_number - 1.0) < 1e-12


def test_confounded_slice_breaks_exact_orthogonality():
    rows = [row for row in factorial_rows() if row["C"] == row["A"]]
    for family in FAMILIES:
        audit = audit_counterfactual_basis_orthogonality(family, rows)
        assert audit.orthogonal_equal_norm is False
        assert audit.gram_condition_number > 1e12
