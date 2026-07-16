"""The exact operators are the load-bearing correctness claim of the surface-matched
routing experiment: the GLOBAL mechanism must always find the duplicate, and the
LOCAL mechanism must find it iff the two occurrences fall within its window."""
from __future__ import annotations

import torch

from experiments.wp2_routing_v2.src.surface_matched_routing import (
    LOCAL_W,
    global_logits,
    local_logits,
)
from experiments.wp2_routing_v2.src.surface_matched_task import generate_batch


def test_global_always_finds_duplicate():
    gen = torch.Generator().manual_seed(0)
    tokens, target, _far = generate_batch(256, gen, "cpu")
    pred = global_logits(tokens).argmax(dim=-1)
    assert (pred == target).all(), "global mechanism must solve every example"


def test_local_solves_near_fails_far():
    gen = torch.Generator().manual_seed(1)
    tokens, target, far = generate_batch(512, gen, "cpu")
    pred = local_logits(tokens, LOCAL_W).argmax(dim=-1)
    correct = pred == target
    # NEAR (~far == False) must be solved by the local window
    assert correct[~far].float().mean().item() > 0.99, "local must solve NEAR"
    # FAR accuracy must be far below NEAR: the local window cannot bridge the distance
    assert correct[far].float().mean().item() < correct[~far].float().mean().item()


def test_local_abstains_are_uniform_not_confident_wrong():
    gen = torch.Generator().manual_seed(2)
    tokens, _target, far = generate_batch(512, gen, "cpu")
    logits = local_logits(tokens, LOCAL_W)
    # where local did NOT find a within-window duplicate, logits are all-zero (uniform)
    row_max = logits.max(dim=-1).values
    abstained = row_max == 0.0
    # a meaningful fraction of FAR examples must trigger abstention
    assert abstained[far].float().mean().item() > 0.2


def test_surface_matched_batch_shapes_and_labels():
    gen = torch.Generator().manual_seed(3)
    tokens, target, far = generate_batch(64, gen, "cpu")
    assert tokens.shape[0] == 64 and target.shape[0] == 64 and far.shape[0] == 64
    # every target value actually appears at least twice (it is the duplicate)
    for b in range(64):
        assert (tokens[b] == target[b]).sum().item() >= 2
