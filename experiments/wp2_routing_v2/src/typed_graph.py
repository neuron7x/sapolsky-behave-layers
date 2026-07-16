"""TypedCognitiveGraph (Act §6). Public forward returns its RoutingTrace
directly — no mutable hidden diagnostics (`_last_mask` is banned)."""
from __future__ import annotations

import torch
import torch.nn as nn

from experiments.wp2_routing_v2.src.contracts import RoutingTrace, SemanticState
from experiments.wp2_routing_v2.src.controller import NeedController, topk_mask
from experiments.wp2_routing_v2.src.typed_modules import DirectPath, SemanticPath

LESIONS = ("none", "semantic_parser_off", "semantic_state_permuted",
           "polarity_corrupted", "subject_object_swapped", "renderer_off", "channel_zeroed")


def _apply_lesion(state: SemanticState, lesion: str, gen: torch.Generator | None) -> SemanticState:
    if lesion in ("none", "renderer_off"):
        return state
    if lesion == "semantic_parser_off" or lesion == "channel_zeroed":
        z = torch.zeros_like(state.subject)
        return SemanticState(z, z, z, torch.zeros_like(state.polarity), state.confidence)
    if lesion == "semantic_state_permuted":
        n = state.subject.shape[0]
        dev = state.subject.device
        perm = torch.randperm(n, generator=gen, device=dev) if gen else torch.randperm(n, device=dev)
        return SemanticState(state.subject[perm], state.relation[perm], state.object[perm],
                             state.polarity[perm], state.confidence)
    if lesion == "polarity_corrupted":
        return SemanticState(state.subject, state.relation, state.object,
                             1 - state.polarity, state.confidence)
    if lesion == "subject_object_swapped":
        return SemanticState(state.object, state.relation, state.subject,
                             state.polarity, state.confidence)
    return state


class TypedCognitiveGraph(nn.Module):
    def __init__(self):
        super().__init__()
        self.direct = DirectPath()
        self.semantic = SemanticPath()
        self.controller = NeedController()

    def forward(self, tokens, *, capacity, forced_mask=None, lesion=None, gen=None):
        B = tokens.shape[0]
        lesion = lesion or "none"
        need = self.controller.need_score(tokens)
        route_logits = self.controller.route_logits(need)
        semantic_mask = forced_mask if forced_mask is not None else topk_mask(need, capacity)

        # semantic path
        sem_logits_full, state = self.semantic(tokens)
        state = _apply_lesion(state, lesion, gen)
        if lesion in ("semantic_parser_off", "semantic_state_permuted", "polarity_corrupted",
                      "subject_object_swapped", "channel_zeroed"):
            sem_logits_full = self.semantic.renderer(state)
        if lesion == "renderer_off":
            sem_logits_full = torch.zeros_like(sem_logits_full)

        direct_logits = self.direct(tokens)
        m = semantic_mask.view(B, 1, 1)
        out = torch.where(m, sem_logits_full, direct_logits)

        active_cost = semantic_mask.long()
        trace = RoutingTrace(need_score=need.detach(), semantic_mask=semantic_mask.detach(),
                             route_logits=route_logits.detach(), active_cost=active_cost.detach(),
                             capacity=capacity)
        out_state = state if semantic_mask.any() else None
        return out, out_state, trace
