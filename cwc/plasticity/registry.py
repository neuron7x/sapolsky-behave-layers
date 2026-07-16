"""Parameter-group registry (spec §5, §6.1, Gate B). Assigns every trainable
parameter to exactly one structured group with a DETERMINISTIC id independent
of Python object identity, so the same model config yields the same registry."""
from __future__ import annotations

import hashlib

import torch.nn as nn

from cwc.plasticity.contracts import ParameterGroupSpec

# structured group types by parameter-name suffix pattern (spec §5.1)
_GROUP_RULES: tuple[tuple[str, str], ...] = (
    ("attn.qkv", "attention.qkv"),
    ("attn.proj", "attention.output"),
    ("attn.out", "attention.output"),
    ("mlp.fc", "mlp.up"),
    ("mlp.up", "mlp.up"),
    ("mlp.proj", "mlp.down"),
    ("mlp.down", "mlp.down"),
    ("norm", "normalization"),
    ("adapter", "adapter"),
    ("embed", "token_embedding"),
    ("pos", "position_embedding"),
    ("head", "language_head"),
)


def _group_type(param_name: str) -> str:
    low = param_name.lower()
    for pat, gtype in _GROUP_RULES:
        if pat in low:
            return gtype
    return "other"


def _block_index(param_name: str) -> str:
    # extract a stable block key, e.g. "blocks.3" -> "3"; global params -> "global"
    parts = param_name.split(".")
    for i, p in enumerate(parts):
        if p in ("blocks", "h", "layers") and i + 1 < len(parts):
            return parts[i + 1]
    return "global"


def _group_key(param_name: str) -> str:
    return f"{_block_index(param_name)}::{_group_type(param_name)}"


def _stable_id(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


class ParameterGroupRegistry:
    def __init__(self, specs: list[ParameterGroupSpec], param_to_group: dict[str, int]):
        self.specs = specs
        self.param_to_group = param_to_group
        self.group_ids = [s.group_id for s in specs]

    @classmethod
    def from_model(cls, model: nn.Module, mutable_prefixes: tuple[str, ...] | None = None,
                   bytes_per_param: int = 4, optimizer_state_mult: int = 2) -> ParameterGroupRegistry:
        by_key: dict[str, list[tuple[str, int]]] = {}
        module_path: dict[str, str] = {}
        for name, p in model.named_parameters():
            if not p.requires_grad:
                continue
            key = _group_key(name)
            by_key.setdefault(key, []).append((name, p.numel()))
            module_path.setdefault(key, name.rsplit(".", 1)[0])
        specs: list[ParameterGroupSpec] = []
        param_to_group: dict[str, int] = {}
        for key in sorted(by_key):  # sorted -> deterministic order
            members = by_key[key]
            gid = _stable_id(key)
            names = tuple(sorted(n for n, _ in members))
            count = sum(n for _, n in members)
            mutable = True if mutable_prefixes is None else any(
                any(nm.startswith(pre) for pre in mutable_prefixes) for nm in names)
            specs.append(ParameterGroupSpec(
                group_id=gid, name=key, module_path=module_path[key],
                parameter_names=names, group_type=key.split("::")[1],
                parameter_count=count,
                estimated_update_flops=2 * count,   # 1 mul + 1 add per param
                estimated_optimizer_bytes=count * bytes_per_param * optimizer_state_mult,
                mutable=mutable))
            for nm in names:
                assert nm not in param_to_group, f"duplicate assignment: {nm}"
                param_to_group[nm] = gid
        return cls(specs, param_to_group)

    def n_groups(self) -> int:
        return len(self.specs)

    def coverage(self, model: nn.Module) -> tuple[int, int]:
        total = sum(1 for _, p in model.named_parameters() if p.requires_grad)
        covered = len(self.param_to_group)
        return covered, total

    def checksum(self) -> str:
        payload = ";".join(f"{s.name}:{s.group_id}:{s.parameter_count}" for s in self.specs)
        return hashlib.sha256(payload.encode()).hexdigest()
