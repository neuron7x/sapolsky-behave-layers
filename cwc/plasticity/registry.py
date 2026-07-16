"""Parameter-group registry (spec §5, §6.1, Gate B): the deterministic partition.

WHAT
    Given a model, assign every trainable parameter to exactly one *structured* group
    keyed by (block index, role) — e.g. `3::attention.qkv`. Each group gets an id that
    is a content hash of its key, so the id depends only on the model's parameter
    *names*, never on Python object identity or construction order.

WHY (design argument)
    Two properties are load-bearing and both come from determinism:
      1. **Reproducibility.** The same model config yields the same registry on any
         machine and any run — a decision recorded as "group 0x1a2b froze" is stable
         evidence, not an artifact of a particular process. Object-`id()`-based grouping
         would silently change every run and make traces meaningless.
      2. **Interpretability.** Groups follow model *structure* (attention vs mlp, up vs
         down, which block), so a mask over groups reads as an anatomical statement
         about the network rather than an opaque index set.

INVARIANT (Gate B). Every `requires_grad` parameter lands in exactly one group; a
duplicate assignment is an assertion error, not a last-writer-wins overwrite.
"""
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
    """Map a parameter name to its structural *role* by suffix pattern (first match in
    `_GROUP_RULES` wins; unmatched -> "other"). The ordered rules are the operational
    definition of "role": anything not matched is deliberately pooled into "other"
    rather than guessed, so an unrecognized parameter is visible, not misfiled."""
    low = param_name.lower()
    for pat, gtype in _GROUP_RULES:
        if pat in low:
            return gtype
    return "other"


def _block_index(param_name: str) -> str:
    """Extract the transformer block key, e.g. `blocks.3.attn...` -> "3"; parameters
    with no block (embeddings, head, norms outside blocks) -> "global". This is what
    lets a group be block-local, so the governor can freeze a role in one depth while
    updating it in another."""
    parts = param_name.split(".")
    for i, p in enumerate(parts):
        if p in ("blocks", "h", "layers") and i + 1 < len(parts):
            return parts[i + 1]
    return "global"


def _group_key(param_name: str) -> str:
    """The full group key `"<block>::<role>"` — the human-readable identity of a group
    and the sole input to its id hash."""
    return f"{_block_index(param_name)}::{_group_type(param_name)}"


def _stable_id(key: str) -> int:
    """Content-derived 32-bit group id: first 8 hex of SHA-256(key). Deterministic and
    collision-resistant enough for the handful of groups in a model; depends only on
    the key string, which is the whole point (see module docstring)."""
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


class ParameterGroupRegistry:
    """The realized partition: the ordered list of `ParameterGroupSpec`s plus the
    parameter-name -> group-id map the optimizer indexes into. `group_ids` fixes the
    tensor order for every length-G `PlasticityDecision`, so index g means the same
    group everywhere."""

    def __init__(self, specs: list[ParameterGroupSpec], param_to_group: dict[str, int]):
        self.specs = specs
        self.param_to_group = param_to_group
        self.group_ids = [s.group_id for s in specs]

    @classmethod
    def from_model(cls, model: nn.Module, mutable_prefixes: tuple[str, ...] | None = None,
                   bytes_per_param: int = 4, optimizer_state_mult: int = 2) -> ParameterGroupRegistry:
        """Build the registry from a live model. Only `requires_grad` parameters are
        grouped. Groups are emitted in **sorted key order** (not discovery order) so the
        G-axis is deterministic. `mutable_prefixes` optionally restricts which groups
        may change (a group is mutable iff any of its parameters starts with a listed
        prefix; `None` = all mutable). `bytes_per_param`/`optimizer_state_mult`
        parameterize the byte-cost estimate (default: fp32 + 2 Adam state tensors).
        Raises on a duplicate parameter assignment — the Gate-B one-group invariant."""
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
        """Number of groups G (the length of every decision tensor)."""
        return len(self.specs)

    def coverage(self, model: nn.Module) -> tuple[int, int]:
        """`(covered, total)` trainable-parameter-tensor counts. The Gate-B invariant is
        `covered == total`: every trainable parameter is grouped. Returned as a pair (not
        a bool) so a caller can report the exact shortfall if the invariant ever breaks."""
        total = sum(1 for _, p in model.named_parameters() if p.requires_grad)
        covered = len(self.param_to_group)
        return covered, total

    def checksum(self) -> str:
        """Stable fingerprint of the whole partition (name:id:count per group, in spec
        order). Two runs producing the same checksum have provably the same grouping —
        the machine-checkable form of the reproducibility claim in the module docstring."""
        payload = ";".join(f"{s.name}:{s.group_id}:{s.parameter_count}" for s in self.specs)
        return hashlib.sha256(payload.encode()).hexdigest()
