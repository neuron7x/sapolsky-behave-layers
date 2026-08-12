"""Parameter-importance estimators for the CWC Adaptive Metaplasticity Governor.

Three *independent* estimators of per-parameter importance Ω_i, each answering
"how much does parameter θ_i matter for what the network has already learned?".
They are the standard continual-learning regularisers, implemented here as
self-contained functions over a plain ``nn.Module`` plus a data iterator — this
module imports nothing from the rest of the WP-3 stack.

1. Synaptic Intelligence (Zenke, Poole & Ganguli, ICML 2017). An *online*
   path-integral estimate accumulated during training: the contribution of a
   parameter is the running sum of ``-g_i · Δθ_i`` (gradient times the update it
   drove), normalised at the end of the experience by the squared total
   displacement. Split into :func:`si_accumulate` (call each optimiser step) and
   :func:`si_finalize` (call once, at the end of the experience).

2. Elastic Weight Consolidation — diagonal Fisher (Kirkpatrick et al., PNAS
   2017). The empirical Fisher information ``Ω_i = E[(∂ log p(y|x,θ)/∂θ_i)^2]``,
   estimated as the mean of squared cross-entropy log-likelihood gradients over
   sampled labelled batches. Requires labels.

3. Memory Aware Synapses (Aljundi et al., ECCV 2018). The sensitivity of the
   *output magnitude* to each parameter,
   ``Ω_i = E_x[ |∂ ||f(x;θ)||_2^2 / ∂θ_i| ]``. Uses no labels, so it can run on
   unlabelled data.

All three are deterministic given a fixed seed and a fixed data ordering: none
of them draw random numbers internally (EWC uses the *empirical* Fisher with the
data's own labels, not model-sampled labels), so reproducibility is inherited
entirely from the caller's seeding of model init and data iteration.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import torch
import torch.nn.functional as F
from torch import Tensor, nn

# A mapping from fully-qualified parameter name (as produced by
# ``model.named_parameters()``) to a tensor shaped exactly like that parameter.
ImportanceDict = dict[str, Tensor]


def _trainable_named_params(model: nn.Module) -> list[tuple[str, Tensor]]:
    """Parameters that carry gradient, in ``named_parameters`` order (stable)."""
    return [(name, p) for name, p in model.named_parameters() if p.requires_grad]


# --------------------------------------------------------------------------- #
# 1. Synaptic Intelligence (Zenke et al. 2017)
# --------------------------------------------------------------------------- #
def si_zero_accumulator(model: nn.Module) -> ImportanceDict:
    """A fresh, zero-initialised path-integral accumulator ``w`` for ``model``.

    Call once at the start of an experience; feed the returned dict to every
    :func:`si_accumulate` call and finally to :func:`si_finalize`.
    """
    return {name: torch.zeros_like(p) for name, p in _trainable_named_params(model)}


def si_accumulate(
    w: ImportanceDict,
    prev_params: Mapping[str, Tensor],
    model: nn.Module,
    loss: Tensor | None = None,
    *,
    grads: Mapping[str, Tensor] | None = None,
    retain_graph: bool = False,
) -> None:
    """Accumulate one optimiser step into the SI path integral ``w`` in place.

    Implements the Zenke et al. (2017) per-step contribution
    ``w_i -= g_i · Δθ_i``, where ``g_i`` is the gradient that drove the step and
    ``Δθ_i = θ_i(after) - θ_i(before)`` is the resulting parameter displacement.
    Because the loss decreases along the update direction, ``g_i · Δθ_i`` is
    typically negative, so the subtraction makes ``w_i`` accumulate a positive
    importance.

    Intended call order, once per optimiser step::

        prev = {n: p.detach().clone() for n, p in model.named_parameters()}
        optimizer.zero_grad()
        loss = loss_fn(model(x), y)
        loss.backward()          # populates p.grad at θ(before)
        optimizer.step()         # θ(before) -> θ(after)
        si_accumulate(w, prev, model)   # reads p.grad and θ(after)

    The gradient ``g_i`` is taken (in priority order) from an explicit ``grads``
    mapping, else computed from ``loss`` via autograd, else read from ``p.grad``.
    ``p.grad`` is the theoretically correct source in the flow above: it was
    filled at θ(before) and is *not* cleared by ``optimizer.step()``. Deriving
    ``g_i`` from ``loss`` here would evaluate it at θ(after) — the wrong point —
    so pass ``loss`` only when you have not yet stepped, or supply ``grads``.

    Args:
        w: The accumulator to update in place (see :func:`si_zero_accumulator`).
        prev_params: θ(before) snapshot for this step, keyed by parameter name.
        model: The model, now holding θ(after).
        loss: Optional scalar loss used to derive gradients if ``grads`` is None
            and no ``p.grad`` is present.
        grads: Optional explicit ``{name: gradient}`` mapping; highest priority.
        retain_graph: Forwarded to autograd when gradients are derived from
            ``loss``.
    """
    named = _trainable_named_params(model)

    resolved: dict[str, Tensor | None]
    if grads is not None:
        resolved = {name: grads.get(name) for name, _ in named}
    elif loss is not None:
        params = [p for _, p in named]
        computed = torch.autograd.grad(loss, params, retain_graph=retain_graph, allow_unused=True)
        resolved = {name: g for (name, _), g in zip(named, computed, strict=True)}
    else:
        resolved = {name: p.grad for name, p in named}

    for name, p in named:
        g = resolved.get(name)
        if g is None:
            continue
        prev = prev_params[name]
        delta = p.detach() - prev
        w[name] -= g.detach() * delta


def si_finalize(
    w: Mapping[str, Tensor],
    params: Mapping[str, Tensor],
    ref_params: Mapping[str, Tensor],
    xi: float = 1e-3,
) -> ImportanceDict:
    """Finalise the SI importance for one experience.

    Returns ``Ω_i^SI = w_i / ((θ_i - θ_i*)^2 + ξ)`` (Zenke et al. 2017, Eq. 5),
    where ``θ_i`` are the current parameters, ``θ_i*`` (``ref_params``) are the
    parameters at the *start* of the experience, and ``ξ`` (``xi``) is the damping
    term that bounds importance when the displacement is tiny.

    Args:
        w: The accumulated path integral from :func:`si_accumulate`.
        params: Current parameters θ_i.
        ref_params: Reference parameters θ_i* at the start of the experience.
        xi: Damping constant ξ > 0.

    Returns:
        Per-parameter SI importance, same shapes as ``w``.
    """
    omega: ImportanceDict = {}
    for name, w_i in w.items():
        delta = params[name] - ref_params[name]
        omega[name] = w_i / (delta.pow(2) + xi)
    return omega


# --------------------------------------------------------------------------- #
# 2. EWC — diagonal empirical Fisher (Kirkpatrick et al. 2017)
# --------------------------------------------------------------------------- #
def _split_batch(batch: Any) -> tuple[Tensor, Tensor | None]:
    """Split a data-iterator item into (inputs, optional targets)."""
    if isinstance(batch, (tuple, list)):
        x = batch[0]
        y = batch[1] if len(batch) > 1 else None
        return x, y
    return batch, None


def ewc_importance(
    model: nn.Module,
    data_iter: Iterable[Any],
    n_batches: int,
    device: torch.device | str,
) -> ImportanceDict:
    """Diagonal EWC Fisher importance ``Ω_i = E[(∂ log p(y|x,θ)/∂θ_i)^2]``.

    Estimates the *empirical* diagonal Fisher: for each of up to ``n_batches``
    labelled batches it back-propagates the cross-entropy log-likelihood (the
    log-likelihood gradient is minus the cross-entropy gradient; the square is
    sign-invariant), squares the resulting per-parameter gradient, and averages
    over batches. This is the standard EWC per-batch-gradient estimator.

    ``data_iter`` must yield ``(inputs, targets)``; ``model(inputs)`` must return
    logits of shape ``(batch, num_classes)``. Model parameters are left with
    zeroed gradients on return; the model's ``training`` flag is preserved.

    Args:
        model: The model to measure.
        data_iter: Iterable of labelled batches.
        n_batches: Maximum number of batches to consume.
        device: Device to move batches onto.

    Returns:
        Per-parameter mean squared log-likelihood gradient.
    """
    was_training = model.training
    model.eval()

    named = _trainable_named_params(model)
    fisher: ImportanceDict = {name: torch.zeros_like(p) for name, p in named}

    seen = 0
    for batch in data_iter:
        if seen >= n_batches:
            break
        x, y = _split_batch(batch)
        if y is None:
            raise ValueError("ewc_importance requires labelled batches (inputs, targets)")
        x = x.to(device)
        y = y.to(device)

        model.zero_grad(set_to_none=True)
        logits = model(x)
        # log p(y|x) = -CE(logits, y); grad of squared is sign-invariant.
        nll = F.cross_entropy(logits, y)
        nll.backward()

        for name, p in named:
            if p.grad is not None:
                fisher[name] += p.grad.detach().pow(2)
        seen += 1

    model.zero_grad(set_to_none=True)
    if was_training:
        model.train()

    if seen == 0:
        raise ValueError("ewc_importance consumed no batches (empty data_iter or n_batches<=0)")

    for name in fisher:
        fisher[name] /= seen
    return fisher


# --------------------------------------------------------------------------- #
# 3. MAS — Memory Aware Synapses (Aljundi et al. 2018)
# --------------------------------------------------------------------------- #
def mas_importance(
    model: nn.Module,
    data_iter: Iterable[Any],
    n_batches: int,
    device: torch.device | str,
) -> ImportanceDict:
    """MAS importance ``Ω_i = E_x[ |∂ ||f(x;θ)||_2^2 / ∂θ_i| ]``.

    For each of up to ``n_batches`` batches it computes the mean (over the batch)
    squared L2 norm of the model output, back-propagates it, takes the absolute
    value of each parameter gradient, and averages over batches. Uses **no
    labels** — batches may be bare input tensors, or ``(inputs, ...)`` tuples
    whose remaining elements are ignored.

    Model parameters are left with zeroed gradients on return; the model's
    ``training`` flag is preserved.

    Args:
        model: The model to measure.
        data_iter: Iterable of inputs (or tuples whose first element is inputs).
        n_batches: Maximum number of batches to consume.
        device: Device to move batches onto.

    Returns:
        Per-parameter mean absolute output-sensitivity gradient.
    """
    was_training = model.training
    model.eval()

    named = _trainable_named_params(model)
    importance: ImportanceDict = {name: torch.zeros_like(p) for name, p in named}

    seen = 0
    for batch in data_iter:
        if seen >= n_batches:
            break
        x, _ = _split_batch(batch)
        x = x.to(device)

        model.zero_grad(set_to_none=True)
        out = model(x)
        # Squared L2 norm of the output per example, averaged over the batch:
        # E_x[ ||f(x)||_2^2 ]. Flatten any non-batch dims before summing.
        flat = out.reshape(out.shape[0], -1)
        objective = flat.pow(2).sum(dim=1).mean()
        objective.backward()

        for name, p in named:
            if p.grad is not None:
                importance[name] += p.grad.detach().abs()
        seen += 1

    model.zero_grad(set_to_none=True)
    if was_training:
        model.train()

    if seen == 0:
        raise ValueError("mas_importance consumed no batches (empty data_iter or n_batches<=0)")

    for name in importance:
        importance[name] /= seen
    return importance


# --------------------------------------------------------------------------- #
# Group aggregation
# --------------------------------------------------------------------------- #
def aggregate_to_groups(
    importance_dict: Mapping[str, Tensor],
    group_map: Mapping[str, list[str]],
) -> dict[str, float]:
    """Aggregate per-parameter importance into one scalar per group.

    Each parameter's tensor is first reduced to a scalar (its mean). Those
    per-parameter scalars are then **min-max normalised** across *all* parameters
    present in ``importance_dict`` into ``[0, 1]`` — chosen over z-scoring so the
    result is non-negative and directly comparable as a fraction of the most
    important parameter, which suits a plasticity governor. If every parameter
    has the same scalar (zero spread) all normalised values are ``0.0``. Finally,
    each group's score is the mean of the normalised scalars of its member
    parameters.

    Args:
        importance_dict: Per-parameter importance tensors.
        group_map: ``group_id -> [parameter names]``. Names absent from
            ``importance_dict`` are ignored; a group with no present members
            scores ``0.0``.

    Returns:
        ``group_id -> float`` aggregate importance in ``[0, 1]``.
    """
    per_param: dict[str, float] = {name: float(t.detach().mean().item()) for name, t in importance_dict.items()}
    if per_param:
        lo = min(per_param.values())
        hi = max(per_param.values())
        spread = hi - lo
        normalised = {name: (v - lo) / spread if spread > 0.0 else 0.0 for name, v in per_param.items()}
    else:
        normalised = {}

    result: dict[str, float] = {}
    for group_id, names in group_map.items():
        vals = [normalised[name] for name in names if name in normalised]
        result[group_id] = sum(vals) / len(vals) if vals else 0.0
    return result
