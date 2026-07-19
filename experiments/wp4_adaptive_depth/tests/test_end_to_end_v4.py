import torch

from experiments.wp4_adaptive_depth.src.analyze_end_to_end_v4 import MINIMUM_MEANINGFUL_EFFECT
from experiments.wp4_adaptive_depth.src.runner_end_to_end_v4 import run_paid_probe


def test_v4_mde_matches_frozen_protocol():
    assert MINIMUM_MEANINGFUL_EFFECT == 0.02


def test_paid_probe_charges_terminal_observation_once():
    table = torch.tensor([[1, 1], [1, 1]])
    start = torch.tensor([0, 1])
    result = run_paid_probe(table, start, 3, torch.Generator().manual_seed(1))
    assert result["moves_per_item"] == [1, 0]
    assert result["billed_lookups"] == 3
    assert result["terminal_probes"] == 2
    assert result["unfinished_items"] == 0


def test_paid_probe_budget_exhaustion_has_no_hidden_lookup():
    table = torch.tensor([[1, 2, 2], [1, 1, 1]])
    start = torch.tensor([0, 0])
    result = run_paid_probe(table, start, 1, torch.Generator().manual_seed(7))
    assert sum(result["moves_per_item"]) == 1
    assert result["billed_lookups"] == 1
    assert result["terminal_probes"] == 0
    assert result["unfinished_items"] == 2


def test_paid_probe_rejects_negative_budget():
    try:
        run_paid_probe(torch.ones((1, 1), dtype=torch.long), torch.zeros(1, dtype=torch.long), -1, torch.Generator())
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("negative lookup budget accepted")
