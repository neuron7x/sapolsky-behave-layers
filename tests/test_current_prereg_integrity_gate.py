from __future__ import annotations

from scripts import current_prereg_integrity_gate as gate


def test_current_tree_temporal_integrity_is_fail_closed_clean() -> None:
    result = gate.analyze()
    assert result["verdict"] == "PASS"
    assert result["failure_count"] == 0
    assert result["hypothesis_count"] == 70


def test_cog_info_02_uses_true_preconfirmatory_research_preregistration() -> None:
    result = gate.analyze()
    check = next(x for x in result["checks"] if x["hypothesis_id"] == "H-COG-INFO-02")
    assert check["classification"] == "STRICT_ANCESTOR"
    assert check["preregistration_paths"] == [
        "research/preregistration/COG_INFO_02_DECISION_RELEVANT.md"
    ]


def test_same_commit_without_disclosure_is_rejected() -> None:
    ok, _ = gate._decision("SAME_COMMIT_RETROSPECTIVE", disclosed=False, status="SUPPORTED")
    assert ok is False


def test_historical_negative_without_prereg_cannot_authorize_positive_claim() -> None:
    negative_ok, _ = gate._decision(
        "NO_INDEPENDENT_PREREG", disclosed=True, status="NOT_SUPPORTED"
    )
    positive_ok, _ = gate._decision(
        "NO_INDEPENDENT_PREREG", disclosed=True, status="SUPPORTED"
    )
    assert negative_ok is True
    assert positive_ok is False
