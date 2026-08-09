from __future__ import annotations

import pytest

from cwc.causal.crossfit import fold_assignment, grouped_kfold


def test_grouped_kfold_never_leaks_group() -> None:
    groups = ["doc1", "doc1", "doc2", "doc2", "doc3", "doc3", "doc4", "doc4"]
    folds = grouped_kfold(groups, n_splits=4, seed=23)
    seen_test = set()
    for train, test in folds:
        train_groups = {groups[i] for i in train}
        test_groups = {groups[i] for i in test}
        assert not (train_groups & test_groups)
        seen_test.update(test)
    assert seen_test == set(range(len(groups)))


def test_fold_assignment_is_deterministic_at_group_level() -> None:
    groups = ["a", "a", "b", "c", "c", "d"]
    a = fold_assignment(groups, n_splits=3, seed=9)
    b = fold_assignment(groups, n_splits=3, seed=9)
    assert a == b
    assert set(a) == {"a", "b", "c", "d"}


def test_invalid_number_of_folds_fails_closed() -> None:
    with pytest.raises(ValueError):
        grouped_kfold(["a", "a", "b"], n_splits=3, seed=1)
