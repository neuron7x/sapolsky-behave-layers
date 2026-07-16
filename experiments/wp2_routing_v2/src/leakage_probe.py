"""Surface-leakage audit (G3 / defect #4). Trains simple probes that see ONLY
surface features and try to predict the task kind (EASY vs HARD). If a surface
probe achieves high AUROC, the benchmark leaks format and a router could
classify surface, not mechanism need -> BENCHMARK_INVALID_SURFACE_LEAKAGE.
"""
from __future__ import annotations

import torch

from experiments.common.metrics import auroc
from experiments.wp2_routing_v2.src.contracts import TaskKind, VOCAB_SIZE
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch


def _features(tokens: torch.Tensor) -> dict[str, torch.Tensor]:
    """Surface-only features per sequence."""
    pad = 0
    nonpad = (tokens != pad)
    length = nonpad.sum(dim=1).float()                      # sequence length
    first = tokens[:, 0].float()                            # first token
    hist = torch.stack([(tokens == v).sum(dim=1).float() for v in range(VOCAB_SIZE)], dim=1)  # token histogram
    return {"length": length, "first_token": first, "histogram": hist}


def _logistic_auroc(x: torch.Tensor, y: torch.Tensor, steps: int = 300) -> float:
    """Fit a tiny logistic regression on feature x -> label y, return AUROC."""
    if x.dim() == 1:
        x = x.unsqueeze(1)
    x = (x - x.mean(0)) / (x.std(0) + 1e-6)
    w = torch.zeros(x.shape[1], requires_grad=True)
    b = torch.zeros(1, requires_grad=True)
    opt = torch.optim.Adam([w, b], lr=0.1)
    yf = y.float()
    for _ in range(steps):
        logit = x @ w + b
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logit, yf)
        opt.zero_grad()
        loss.backward()
        opt.step()
    with torch.no_grad():
        return auroc(x @ w + b, y)


def audit(n: int = 4000, seed: int = 0) -> dict:
    g = torch.Generator().manual_seed(seed)
    tokens, _st, _canon, kind = generate_batch(n, g, "train", 0.5, "cpu")
    y = (kind == int(TaskKind.HARD_SEMANTIC)).long()
    feats = _features(tokens)
    return {name: _logistic_auroc(f, y) for name, f in feats.items()}
