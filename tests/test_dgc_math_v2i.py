from __future__ import annotations

from cwc.governance.causal_transport import find_minimal_s_admissible_adjustments


def test_search_finds_minimal_transport_adjustment_without_manual_oracle():
    result=find_minimal_s_admissible_adjustments(causal_nodes=("z","x","y"),causal_edges=(("z","x"),("z","y"),("x","y")),selection_edges=(("S","z"),),treatment=("x",),outcome=("y",),source_interventional_available=True,target_adjustment_distribution_available=True)
    assert result.complete_for_declared_candidate_family
    assert result.candidate_count == 2
    assert result.minimal_adjustments == (("z",),)


def test_search_returns_no_certificate_when_selection_directly_changes_outcome():
    result=find_minimal_s_admissible_adjustments(causal_nodes=("z","x","y"),causal_edges=(("z","x"),("z","y"),("x","y")),selection_edges=(("S","y"),),treatment=("x",),outcome=("y",),source_interventional_available=True,target_adjustment_distribution_available=True)
    assert result.transportable_count == 0
    assert result.minimal_adjustments == ()


def test_search_excludes_post_treatment_descendants_from_candidate_family():
    result=find_minimal_s_admissible_adjustments(causal_nodes=("x","m","z","y"),causal_edges=(("x","m"),("m","y"),("z","y")),selection_edges=(("S","z"),),treatment=("x",),outcome=("y",),source_interventional_available=True,target_adjustment_distribution_available=True)
    # m is a descendant of treatment and is excluded; only z is a legal candidate.
    assert result.candidate_count == 2
    assert all("m" not in cert.adjustment for cert in result.certificates)
