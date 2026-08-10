from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import FrozenSet, Mapping

import torch
import torch.nn.functional as F

PLAYERS = ("A_RECENT", "B_PREV", "C_MIDDLE", "D_EARLY")
NEUTRAL_BYTE = 32


@dataclass(frozen=True, slots=True)
class PromptInterventionSpec:
    prompt_tokens: tuple[int, ...]
    context: str
    spans: dict[str, tuple[int, int]]

    @property
    def prompt_hash(self) -> str:
        raw = ",".join(map(str, self.prompt_tokens)).encode()
        return hashlib.sha256(raw).hexdigest()


def candidate_spans(prompt_len: int) -> dict[str, tuple[int, int]]:
    if prompt_len < 41:
        raise ValueError("prompt must contain context marker + at least 40 content bytes")
    middle_start = 1 + (40 - 4) // 2
    return {
        "D_EARLY": (1, 5),
        "C_MIDDLE": (middle_start, middle_start + 4),
        "B_PREV": (prompt_len - 12, prompt_len - 8),
        "A_RECENT": (prompt_len - 4, prompt_len),
    }


def intervene_prompt(spec: PromptInterventionSpec, keep: FrozenSet[str]) -> list[int]:
    out = list(spec.prompt_tokens)
    for player, (start, end) in spec.spans.items():
        if player not in keep:
            out[start:end] = [NEUTRAL_BYTE] * (end - start)
    return out


@torch.inference_mode()
def next_token_log_probs(model, prompt_tokens: list[int]) -> torch.Tensor:
    ids = torch.tensor([prompt_tokens], dtype=torch.long, device=model.get_device())
    logits = model(ids)[:, -1, :]
    return F.log_softmax(logits, dim=-1)[0].cpu()


class DirectModelCoalitionOracle:
    def __init__(self, model, spec: PromptInterventionSpec):
        self.model = model
        self.spec = spec
        factual_lp = next_token_log_probs(model, list(spec.prompt_tokens))
        self.factual_top_token = int(torch.argmax(factual_lp).item())
        self.factual_log_prob = float(factual_lp[self.factual_top_token].item())
        self.forward_calls = 1

    def __call__(self, keep: FrozenSet[str]) -> float:
        prompt = intervene_prompt(self.spec, keep)
        lp = next_token_log_probs(self.model, prompt)
        self.forward_calls += 1
        return float(lp[self.factual_top_token].item())

    def single_ablation_effects(self) -> dict[str, float]:
        full = frozenset(PLAYERS)
        factual = self.factual_log_prob
        effects: dict[str, float] = {}
        for player in PLAYERS:
            value = self(full - {player})
            effects[player] = factual - value
        return effects


def top_gap(credits: Mapping[str, float]) -> float:
    values = sorted((abs(float(v)) for v in credits.values()), reverse=True)
    return values[0] - values[1] if len(values) > 1 else values[0]


def l1_error(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    return float(sum(abs(float(a[k]) - float(b[k])) for k in a) / len(a))
