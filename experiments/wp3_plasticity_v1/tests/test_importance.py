"""python -m pytest experiments/wp3_plasticity_v1/tests/test_importance.py -q

Behavioural + determinism checks for the three parameter-importance estimators
in :mod:`cwc.plasticity.importance`.

Toy task (CPU, tiny, fully seeded): a linearly-separable 3-class problem whose
inputs are *already* good features. The model is ``l2 · relu(l1 · x)`` with no
biases and equal in/hidden/out width. Layer ``l1`` is initialised to the
identity, so it starts as an (optimal) pass-through and barely has to move;
layer ``l2`` is initialised randomly and must learn the entire feature->class
readout. Layer ``l2`` is therefore the *essential* layer — it does the real
work — and we assert that SI and MAS rank it above the near-frozen ``l1``.
"""
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from torch import Tensor, nn  # noqa: E402

from cwc.plasticity.importance import (  # noqa: E402
    aggregate_to_groups,
    ewc_importance,
    mas_importance,
    si_accumulate,
    si_finalize,
    si_zero_accumulator,
)

SEED = 1234
DEVICE = torch.device("cpu")
DIM = 6
N_CLASSES = 3
N_SAMPLES = 90


class TwoLayer(nn.Module):
    """l1 (identity-init, near-frozen) -> ReLU -> l2 (random-init, essential)."""

    def __init__(self) -> None:
        super().__init__()
        self.l1 = nn.Linear(DIM, DIM, bias=False)
        self.l2 = nn.Linear(DIM, N_CLASSES, bias=False)
        with torch.no_grad():
            self.l1.weight.copy_(torch.eye(DIM))

    def forward(self, x: Tensor) -> Tensor:
        return self.l2(torch.relu(self.l1(x)))


def _make_data() -> tuple[Tensor, Tensor]:
    """Linearly-separable clusters: class c lives around prototype 2*e_c."""
    g = torch.Generator().manual_seed(SEED)
    labels = torch.arange(N_SAMPLES) % N_CLASSES
    protos = torch.zeros(N_CLASSES, DIM)
    for c in range(N_CLASSES):
        protos[c, c] = 2.0
    x = protos[labels] + 0.1 * torch.randn(N_SAMPLES, DIM, generator=g)
    return x, labels


def _batches(x: Tensor, y: Tensor, batch_size: int = 30) -> list[tuple[Tensor, Tensor]]:
    return [
        (x[i : i + batch_size], y[i : i + batch_size])
        for i in range(0, x.shape[0], batch_size)
    ]


def _build_and_train() -> tuple[
    TwoLayer, list[tuple[Tensor, Tensor]], dict[str, Tensor], dict[str, Tensor]
]:
    """Deterministically build, train briefly; return (model, batches, w_SI, ref)."""
    torch.manual_seed(SEED)
    model = TwoLayer()
    x, y = _make_data()
    batches = _batches(x, y)

    ref_params = {n: p.detach().clone() for n, p in model.named_parameters()}
    w = si_zero_accumulator(model)
    opt = torch.optim.SGD(model.parameters(), lr=0.1)

    # Brief consolidation-style training: importance is measured right after an
    # experience, not after massive over-training. SI scores contribution *per
    # unit displacement*, so letting the essential readout drift arbitrarily far
    # would make SI discount it (large Δθ^2 denominator) — the realistic CL
    # setting keeps displacements modest, where SI, EWC and MAS all agree.
    model.train()
    for _ in range(2):
        for bx, by in batches:
            prev = {n: p.detach().clone() for n, p in model.named_parameters()}
            opt.zero_grad()
            loss = nn.functional.cross_entropy(model(bx), by)
            loss.backward()
            opt.step()
            # p.grad still holds the pre-step gradient here (Zenke-correct point).
            si_accumulate(w, prev, model)

    return model, batches, w, ref_params


def _mean(t: Tensor) -> float:
    return float(t.detach().mean().item())


def test_estimators_rank_essential_layer_and_are_deterministic() -> None:
    model, batches, w, ref_params = _build_and_train()
    cur_params = {n: p.detach().clone() for n, p in model.named_parameters()}

    # --- SI ---
    si = si_finalize(w, cur_params, ref_params)
    si_l1, si_l2 = _mean(si["l1.weight"]), _mean(si["l2.weight"])

    # --- EWC (empirical Fisher, uses labels) ---
    ewc = ewc_importance(model, batches, n_batches=len(batches), device=DEVICE)
    ewc_l1, ewc_l2 = _mean(ewc["l1.weight"]), _mean(ewc["l2.weight"])

    # --- MAS (unlabelled: feed bare input tensors) ---
    inputs_only = [bx for bx, _ in batches]
    mas = mas_importance(model, inputs_only, n_batches=len(inputs_only), device=DEVICE)
    mas_l1, mas_l2 = _mean(mas["l1.weight"]), _mean(mas["l2.weight"])

    # (a) essential layer (l2) ranks higher for at least SI and MAS.
    assert si_l2 > si_l1, f"SI failed to rank l2>l1: l1={si_l1:.6g} l2={si_l2:.6g}"
    assert mas_l2 > mas_l1, f"MAS failed to rank l2>l1: l1={mas_l1:.6g} l2={mas_l2:.6g}"
    # EWC agrees here too (bonus; not part of the "at least SI and MAS" contract).
    assert ewc_l2 > ewc_l1, f"EWC failed to rank l2>l1: l1={ewc_l1:.6g} l2={ewc_l2:.6g}"

    # (b) determinism: recompute from scratch and require exact equality.
    model2, batches2, w2, ref2 = _build_and_train()
    cur2 = {n: p.detach().clone() for n, p in model2.named_parameters()}

    si2 = si_finalize(w2, cur2, ref2)
    ewc2 = ewc_importance(model2, batches2, n_batches=len(batches2), device=DEVICE)
    mas2 = mas_importance(
        model2, [bx for bx, _ in batches2], n_batches=len(batches2), device=DEVICE
    )
    for a, b in ((si, si2), (ewc, ewc2), (mas, mas2)):
        for name in a:
            assert torch.equal(a[name], b[name]), f"non-deterministic: {name}"

    # (c) aggregate_to_groups returns exactly one scalar per group.
    group_map = {"layer1": ["l1.weight"], "layer2": ["l2.weight"]}
    for imp in (si, ewc, mas):
        groups = aggregate_to_groups(imp, group_map)
        assert set(groups) == {"layer1", "layer2"}
        assert all(isinstance(v, float) for v in groups.values())
        # l2 is the essential layer -> normalised to 1.0, l1 to 0.0 (2 params).
        assert groups["layer2"] >= groups["layer1"]
