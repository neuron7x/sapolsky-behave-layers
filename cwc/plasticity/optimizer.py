"""Plasticity-aware optimizer wrapper (spec §9, Gate F). Before the wrapped
optimizer steps, each parameter's gradient is scaled by its group's mask and
LR multiplier, given a consolidation pull toward the reference, and norm-bounded
per group. requires_grad is NEVER toggled per step (spec §9)."""
from __future__ import annotations

import torch

from cwc.plasticity.contracts import PlasticityDecision
from cwc.plasticity.registry import ParameterGroupRegistry


class PlasticityOptimizer:
    def __init__(self, optimizer: torch.optim.Optimizer, registry: ParameterGroupRegistry,
                 named_params: dict[str, torch.nn.Parameter]):
        self.opt = optimizer
        self.registry = registry
        self.named_params = named_params
        self._gid_to_idx = {gid: i for i, gid in enumerate(registry.group_ids)}

    def _idx(self, name: str) -> int | None:
        gid = self.registry.param_to_group.get(name)
        return self._gid_to_idx.get(gid) if gid is not None else None

    def apply_and_step(self, decision: PlasticityDecision,
                       reference: dict[str, torch.Tensor],
                       importance: dict[str, torch.Tensor] | None = None) -> None:
        """Modify .grad per group policy, then step. importance[name] optional
        per-parameter Ω for the consolidation term (defaults to 1)."""
        with torch.no_grad():
            self._apply_and_step(decision, reference, importance)

    def _apply_and_step(self, decision: PlasticityDecision,
                        reference: dict[str, torch.Tensor],
                        importance: dict[str, torch.Tensor] | None) -> None:
        if not decision.budget_ok():
            raise ValueError(f"budget violation: {int(decision.group_mask.sum())} > {decision.budget}")
        # snapshot every inactive/unregistered param so the wrapped optimizer's
        # weight decay / momentum cannot move it — inactive groups are guaranteed
        # byte-identical regardless of the base optimizer's settings.
        frozen: dict[str, torch.Tensor] = {}
        for name, p in self.named_params.items():
            gi = self._idx(name)
            active = gi is not None and bool(decision.group_mask[gi].item())
            if not active:
                frozen[name] = p.detach().clone()
        for name, p in self.named_params.items():
            gi = self._idx(name)
            if gi is None or p.grad is None:
                continue
            active = bool(decision.group_mask[gi].item())
            if not active:
                continue
            lr_mult = float(decision.lr_multiplier[gi].item())
            lam = float(decision.consolidation[gi].item())
            g = p.grad
            g.mul_(lr_mult)
            if lam > 0 and name in reference:
                omega = importance[name] if importance and name in importance else 1.0
                g.add_(lam * omega * (p.data - reference[name]))
            max_norm = float(decision.max_update_norm[gi].item())
            if max_norm > 0:
                gn = g.norm()
                if gn > max_norm:
                    g.mul_(max_norm / (gn + 1e-12))
        self.opt.step()
        # restore inactive params (guarantee: masked groups do not move)
        for name, saved in frozen.items():
            self.named_params[name].data.copy_(saved)

    def zero_grad(self, set_to_none: bool = True) -> None:
        self.opt.zero_grad(set_to_none=set_to_none)
