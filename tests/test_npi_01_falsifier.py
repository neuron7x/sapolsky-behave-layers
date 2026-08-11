from fractions import Fraction

from scripts.npi_01_falsifier import (
    FROZEN_RADII,
    VERDICT,
    build_report,
    certificate,
    evaluate_radius,
    frozen_counterexample_results,
    mutation_results,
)


def test_frozen_counterexample_reverses_inside_every_radius() -> None:
    results = frozen_counterexample_results()
    assert [r.radius for r in results] == list(FROZEN_RADII)
    assert all(r.passed for r in results)
    assert all(r.distance < r.radius for r in results)


def test_local_certificate_is_exactly_first_order_safe_looking() -> None:
    cert = certificate()
    assert cert.margin == 1
    assert cert.jacobian == ((Fraction(1), Fraction(0)),)
    assert cert.nullspace_basis == ((Fraction(0), Fraction(1)),)
    assert cert.gradient == (Fraction(0), Fraction(0))
    assert cert.score_squared == 0


def test_exact_counterexample_value_is_minus_one() -> None:
    for r in FROZEN_RADII:
        result = evaluate_radius(r)
        # K=8/r^2 and v=r/2 => 1 - K v^2 = -1 exactly.
        assert result.reversed_action
        assert result.k * result.test_point[1] * result.test_point[1] == 2


def test_all_preregistered_mutations_are_killed() -> None:
    attacks = mutation_results()
    assert len(attacks) == 6
    assert all(attacks.values())


def test_report_binds_negative_verdict() -> None:
    report = build_report()
    assert report["verdict"] == VERDICT
    assert report["certificate_identity"] is True
    assert report["counterexample_all_radii"] is True
    assert report["mutation_kill_count"] == 6
    assert report["mutation_total"] == 6
