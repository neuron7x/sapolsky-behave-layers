"""Act-J pilot: a gradient-trained neural controller realises the analytic V*(R).

This is the empirical bridge for the whole information-market theory. The value-of-
information rate function `V*(R)` (`experiments/common/value_of_information_rate.py`)
is the *analytic* optimum of the rational-inattention objective

    maximise   E_c[ sum_a P(a|c) U[c,a] ]  -  beta * I(C;A) .

Here we train a real neural controller `context -> P(a|c)` by gradient descent on
exactly that objective and check that its converged `(I, V)` lands on `V*(R)` — i.e.
a trained network reaches the theoretical ceiling, and exhibits the phase transition
(regular: value linear in R; critical: value ~ sqrt R, Pinsker attained).

Two controllers are trained per problem:
  * `oracle`   — sees the clean context id (can represent any P(a|c)); its (I,V)
                 must match the analytic RI fixed point to tight tolerance.
  * `sensory`  — sees only a noisy embedding of the context (a fixed observation
                 channel); realistic, and bounded by V*(I_observed) <= V*(R_oracle).

Minimal, self-contained, runs on CPU or a single small GPU. No dataset, no I/O in the
core; the runner writes an evidence JSON.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

from experiments.common.value_of_information_rate import (
    optimal_value_at_rate_ri,
    oracle_gap_value,
    value_and_information,
)

_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


@dataclass
class ControllerResult:
    information_nats: float
    value: float           # E[U] - V_fixed  (the realised value of adaptivity)
    gross_value: float     # E[U]
    v_fixed: float


def _v_fixed(utility: list[list[float]], prior: list[float]) -> float:
    n_c, n_a = len(utility), len(utility[0])
    return max(sum(prior[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))


class _Controller(nn.Module):
    """context id -> action logits. `noise` > 0 corrupts the context embedding
    (a fixed sensory channel); noise = 0 is the clean-context oracle controller."""

    def __init__(
        self, n_contexts: int, n_actions: int, *, hidden: int = 64, embed: int = 16, noise: float = 0.0
    ) -> None:
        super().__init__()
        self.emb = nn.Embedding(n_contexts, embed)
        self.noise = noise
        self.net = nn.Sequential(
            nn.Linear(embed, hidden), nn.GELU(),
            nn.Linear(hidden, hidden), nn.GELU(),
            nn.Linear(hidden, n_actions),
        )

    def forward(self, ctx: torch.Tensor) -> torch.Tensor:
        h = self.emb(ctx)
        if self.noise > 0.0 and self.training:
            h = h + self.noise * torch.randn_like(h)
        return self.net(h)


def train_controller(
    utility: list[list[float]], prior: list[float], beta: float, *,
    steps: int = 4000, lr: float = 3e-3, noise: float = 0.0, seed: int = 0,
) -> ControllerResult:
    """Train `P(a|c)` by Adam on the rational-inattention objective and return (I, V).

    The objective is the exact Lagrangian ``E[U] - beta*I(C;A)`` computed in closed
    form over all contexts each step (no sampling needed — the categorical policy makes
    both terms differentiable), so the controller converges to the RI optimum at ``beta``.
    """
    torch.manual_seed(seed)
    n_c, n_a = len(utility), len(utility[0])
    U = torch.tensor(utility, dtype=torch.float32, device=_DEVICE)          # [K, A]
    p = torch.tensor(prior, dtype=torch.float32, device=_DEVICE)            # [K]
    ctx = torch.arange(n_c, device=_DEVICE)
    model = _Controller(n_c, n_a, noise=noise).to(_DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=lr)

    model.train()
    for _step in range(steps):
        logits = model(ctx)                                                # [K, A]
        logp = F.log_softmax(logits, dim=1)
        pa_given_c = logp.exp()                                            # P(a|c)
        gross = (p[:, None] * pa_given_c * U).sum()                        # E[U]
        p_a = (p[:, None] * pa_given_c).sum(0).clamp_min(1e-12)            # P(a)
        info = (p[:, None] * pa_given_c * (logp - p_a.log()[None, :])).sum()  # I(C;A) nats
        loss = -(gross - beta * info)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

    # evaluate deterministically (no embedding noise) at the converged policy
    model.eval()
    with torch.no_grad():
        logp = F.log_softmax(model(ctx), dim=1)
        pa_given_c = logp.exp()
        gross_v = float((p[:, None] * pa_given_c * U).sum())
        p_a = (p[:, None] * pa_given_c).sum(0).clamp_min(1e-12)
        info_v = float((p[:, None] * pa_given_c * (logp - p_a.log()[None, :])).sum())
    vfix = _v_fixed(utility, prior)
    return ControllerResult(information_nats=max(0.0, info_v), value=gross_v - vfix,
                            gross_value=gross_v, v_fixed=vfix)


def symmetric_confusion_channel(n_contexts: int, epsilon: float) -> list[list[float]]:
    """P(o|c): stay on the true context w.p. ``1-eps+eps/K``, else uniform (a noisy sensor)."""
    k = n_contexts
    return [[(1.0 - epsilon) + epsilon / k if o == c else epsilon / k for o in range(k)] for c in range(k)]


@dataclass
class SensoryResult:
    trained_value: float       # value realised by the trained controller on the sensor
    channel_value: float       # V(O): Bayes-optimal value of the observation channel
    channel_information: float  # I(C;O)
    v_star_at_channel_rate: float  # V*(I(C;O)): the rate-optimal value at the same MI
    inefficiency: float        # V*(I) - V(O): value lost by not shaping the sensor


def train_sensory_controller(
    utility: list[list[float]], prior: list[float], channel: list[list[float]], *,
    steps: int = 4000, lr: float = 3e-3, seed: int = 0,
) -> SensoryResult:
    """Train a controller that sees only a noisy observation ``O`` and learns ``P(a|O)``.

    The bottleneck is the sensor, not an explicit info penalty: the controller simply
    maximises expected reward over the joint ``(C, O)``. It converges to the Bayes value
    ``V(O)``, which the rate function bounds: ``V(O) ≤ V*(I(C;O))``. The symmetric
    confusion sensor is rate-optimal (``inefficiency = V*(I)−V(O) = 0``) **iff the problem
    is context-exchangeable** — invariant under the full permutation group on contexts (a
    fully symmetric problem, at any ``|C|``). Being merely *critical* (two tied actions)
    is NOT sufficient: a critical but non-exchangeable problem still leaves ``inefficiency
    > 0`` — the cost of a channel not shaped to the (asymmetric) decision.
    """
    torch.manual_seed(seed)
    n_c, n_a = len(utility), len(utility[0])
    n_o = len(channel[0])
    U = torch.tensor(utility, dtype=torch.float32, device=_DEVICE)          # [K, A]
    weight = torch.tensor([[prior[c] * channel[c][o] for o in range(n_o)] for c in range(n_c)],
                          dtype=torch.float32, device=_DEVICE)              # [K, O] = p(c)P(o|c)
    obs = torch.arange(n_o, device=_DEVICE)
    model = _Controller(n_o, n_a).to(_DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=lr)

    model.train()
    for _step in range(steps):
        p_a_given_o = F.softmax(model(obs), dim=1)                         # [O, A]
        util_per_co = p_a_given_o @ U.t()                                  # [O, K]  E[U|o] per context
        gross = (weight * util_per_co.t()).sum()                          # E_{c,o} sum_a P(a|o)U[c,a]
        loss = -gross
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        p_a_given_o = F.softmax(model(obs), dim=1)
        gross_v = float((weight * (p_a_given_o @ U.t()).t()).sum())
    vfix = _v_fixed(utility, prior)
    channel_v, channel_i = value_and_information(utility, channel, prior)
    v_star = optimal_value_at_rate_ri(utility, channel_i, prior) if channel_i > 1e-9 else 0.0
    return SensoryResult(
        trained_value=gross_v - vfix, channel_value=channel_v, channel_information=channel_i,
        v_star_at_channel_rate=v_star, inefficiency=v_star - channel_v,
    )


def compare_to_theory(
    utility: list[list[float]], prior: list[float], betas: list[float], *,
    steps: int = 4000, seed: int = 0,
) -> list[dict[str, float]]:
    """For each beta: train the oracle controller and compare its (I, V) to V*(I)."""
    rows: list[dict[str, float]] = []
    for beta in betas:
        res = train_controller(utility, prior, beta, steps=steps, seed=seed)
        v_star = optimal_value_at_rate_ri(utility, res.information_nats, prior) if res.information_nats > 1e-9 else 0.0
        rows.append({
            "beta": beta,
            "trained_information": res.information_nats,
            "trained_value": res.value,
            "theory_v_star": v_star,
            "gap_to_theory": res.value - v_star,
            "oracle_gap_G": oracle_gap_value(utility, prior),
        })
    return rows
