from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import FrozenSet

import numpy as np
import torch
import torch.nn.functional as F

from cwc.credit.ablation_shapley import exact_ablation_shapley, ranked_by_absolute_credit
from experiments.csca_05_shadow_pilot.direct_credit import PLAYERS, PromptInterventionSpec, candidate_spans
from experiments.csca_05_shadow_pilot.runtime_model import CODE_MARKER, PROSE_MARKER, load_checkpoint
from experiments.csca_05_shadow_pilot.run import ROOT, ART, CONTEXT_FILES, _checkpoint_path


def _fresh_specs(context: str, n: int = 16) -> list[PromptInterventionSpec]:
    raw = b"\n".join(path.read_bytes() for path in CONTEXT_FILES[context]["primary"])
    content = 40
    marker = PROSE_MARKER if context == "PROSE" else CODE_MARKER
    specs = []
    used = set()
    for i in range(n):
        digest = hashlib.sha256(f"CSCA05-DIAGNOSTIC:{context}:{i}".encode()).digest()
        offset = int.from_bytes(digest[:8], "big") % (len(raw) - content)
        while offset in used:
            offset = (offset + 1) % (len(raw) - content)
        used.add(offset)
        tokens = (marker, *raw[offset: offset + content])
        specs.append(PromptInterventionSpec(tuple(int(x) for x in tokens), context, candidate_spans(len(tokens))))
    return specs


@torch.inference_mode()
def _log_probs(model, prompt):
    ids = torch.tensor([prompt], dtype=torch.long, device=model.get_device())
    return F.log_softmax(model(ids)[:, -1, :], dim=-1)[0].cpu()


class _PerturbationOracle:
    def __init__(self, model, spec: PromptInterventionSpec, mode: str):
        self.model = model
        self.spec = spec
        self.mode = mode
        factual = _log_probs(model, list(spec.prompt_tokens))
        self.target = int(torch.argmax(factual))

    def __call__(self, keep: FrozenSet[str]) -> float:
        prompt = list(self.spec.prompt_tokens)
        for player, (start, end) in self.spec.spans.items():
            if player in keep:
                continue
            original = prompt[start:end]
            if self.mode == "SPACE":
                replacement = [32] * (end - start)
            elif self.mode == "ZERO":
                replacement = [0] * (end - start)
            elif self.mode == "FF":
                replacement = [255] * (end - start)
            elif self.mode == "REVERSE":
                replacement = list(reversed(original))
            else:
                raise ValueError(self.mode)
            prompt[start:end] = replacement
        return float(_log_probs(self.model, prompt)[self.target])


def main():
    model = load_checkpoint(_checkpoint_path("primary"))
    modes = ("SPACE", "ZERO", "FF", "REVERSE")
    rows = []
    for context in ("PROSE", "CODE"):
        for idx, spec in enumerate(_fresh_specs(context)):
            tops = {}
            signs = {}
            credits = {}
            for mode in modes:
                exact = exact_ablation_shapley(PLAYERS, _PerturbationOracle(model, spec, mode))
                top = ranked_by_absolute_credit(exact.credits)[0]
                tops[mode] = top
                value = float(exact.credits[top])
                signs[mode] = 0 if value == 0 else (1 if value > 0 else -1)
                credits[mode] = exact.credits
            rows.append({
                "context": context,
                "index": idx,
                "prompt_hash": spec.prompt_hash,
                "tops": tops,
                "signs": signs,
                "all_top_same": len(set(tops.values())) == 1,
                "all_sign_same": len(set(signs.values())) == 1,
                "credits": credits,
            })
    payload = {
        "diagnostic_only": True,
        "n": len(rows),
        "modes": list(modes),
        "all_top_same_fraction": float(np.mean([r["all_top_same"] for r in rows])),
        "all_sign_same_fraction": float(np.mean([r["all_sign_same"] for r in rows])),
        "space_top_A_RECENT_fraction": float(np.mean([r["tops"]["SPACE"] == "A_RECENT" for r in rows])),
        "mode_top_A_RECENT_fraction": {
            mode: float(np.mean([r["tops"][mode] == "A_RECENT" for r in rows])) for mode in modes
        },
        "interpretation": "Intervention sensitivity is a boundary diagnostic. It cannot upgrade CSCA-05 and does not redefine the preregistered SPACE intervention estimand."
    }
    out = ART / "diagnostics/intervention_semantics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    (out / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
