from __future__ import annotations

from experiments.dgc_05_triage_ood.run import unseen_known_combinations


def test_dgc05_has_exactly_21_unseen_known_combinations() -> None:
    combos = unseen_known_combinations()
    assert len(combos) == 21
    assert len(set(combos)) == 21
    assert all(len(combo) >= 2 for combo in combos)
