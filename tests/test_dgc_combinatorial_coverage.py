import pytest
from cwc.governance.combinatorial_coverage import (
    CoverageCase,
    Factor,
    FactorSchema,
    certify_t_way_coverage,
    require_coverage,
)


def schema():
    return FactorSchema((
        Factor("drift", ("none", "mean")),
        Factor("provider", ("a", "b")),
        Factor("fault", ("none", "timeout")),
    ))


def case(i, drift, provider, fault):
    return CoverageCase(str(i), (("drift", drift), ("provider", provider), ("fault", fault)))


def test_full_factorial_has_complete_pairwise_and_three_way():
    cases = tuple(
        case(i, drift, provider, fault)
        for i, (drift, provider, fault) in enumerate(
            (d, p, f)
            for d in ("none", "mean")
            for p in ("a", "b")
            for f in ("none", "timeout")
        )
    )
    pair = certify_t_way_coverage(schema(), cases, strength=2)
    triple = certify_t_way_coverage(schema(), cases, strength=3)
    assert pair.complete and pair.coverage_fraction == 1
    assert triple.complete and triple.interaction_universe == 8


def test_pairwise_can_be_complete_without_three_way_complete():
    cases = (
        case(1, "none", "a", "none"),
        case(2, "none", "b", "timeout"),
        case(3, "mean", "a", "timeout"),
        case(4, "mean", "b", "none"),
    )
    assert certify_t_way_coverage(schema(), cases, strength=2).complete
    triple = certify_t_way_coverage(schema(), cases, strength=3)
    assert not triple.complete and triple.coverage_fraction == 0.5


def test_missing_interaction_digest_deterministic_under_case_shuffle():
    cases = [case(1, "none", "a", "none"), case(2, "mean", "b", "timeout")]
    a = certify_t_way_coverage(schema(), tuple(cases), strength=2)
    b = certify_t_way_coverage(schema(), tuple(reversed(cases)), strength=2)
    assert a.missing_interactions_digest == b.missing_interactions_digest
    assert a.case_population_digest == b.case_population_digest


def test_unknown_or_partial_assignments_fail_closed():
    with pytest.raises(ValueError, match="every and only"):
        certify_t_way_coverage(schema(), (CoverageCase("x", (("drift", "none"),)),), strength=2)
    with pytest.raises(ValueError, match="outside frozen"):
        certify_t_way_coverage(schema(), (case(1, "alien", "a", "none"),), strength=2)


def test_duplicate_case_id_rejected():
    cases = (case("same", "none", "a", "none"), case("same", "mean", "b", "timeout"))
    with pytest.raises(ValueError, match="case_id"):
        certify_t_way_coverage(schema(), cases, strength=2)


def test_require_coverage_enforces_threshold_and_complete():
    cases = (case(1, "none", "a", "none"), case(2, "mean", "b", "timeout"))
    cert = certify_t_way_coverage(schema(), cases, strength=2)
    with pytest.raises(ValueError, match="below threshold"):
        require_coverage(cert, min_fraction=0.9)
    with pytest.raises(ValueError, match="complete"):
        require_coverage(cert, min_fraction=0.1, require_complete=True)
