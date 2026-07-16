"""Analytical FLOP ledger (Act 4.8). Convention: 1 MAC = 2 FLOPs.

Reports logical_forward_flops (architecture-derived, always available) and
executed_estimate_forward_flops (accounts for e.g. sliding-window truncation
that a real kernel would skip) as separate numbers — never conflated.
profiler_observed_flops is populated only by the AUDIT path (audit.py), never
here, and flop_model_error_percent is only meaningful once both are present.

MoE is not implemented in WP-1. record_expert_assignments exists only as a
measurement-ready interface for WP-3; F_MoE = dense_flops * active_experts is
explicitly the wrong formula (it double-counts the shared/router paths and
ignores per-expert capacity) and is not offered anywhere in this module.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .types import FlopRecord


def dense_linear_flops(*, tokens: int, d_in: int, d_out: int) -> int:
    """1 MAC = 2 FLOPs convention: a (tokens, d_in) @ (d_in, d_out) matmul."""
    return 2 * tokens * d_in * d_out


def full_noncausal_pairs(seq_len: int) -> int:
    return seq_len * seq_len


def full_causal_pairs(seq_len: int) -> int:
    return seq_len * (seq_len + 1) // 2


def sliding_causal_pairs(seq_len: int, window: int) -> int:
    """Sum of actual valid key positions per query under a causal sliding
    window of size `window` (query i attends to keys in
    [max(0, i - window + 1), i]).
    """
    if window <= 0:
        raise ValueError("window must be positive")
    total = 0
    for i in range(seq_len):
        left = max(0, i - window + 1)
        total += i - left + 1
    return total


def attention_projection_flops(
    *, batch: int, seq_len: int, d_model: int, n_head: int, n_kv_head: int, head_dim: int
) -> dict[str, int]:
    d_q = n_head * head_dim
    d_kv = n_kv_head * head_dim
    tokens = batch * seq_len
    return {
        "q_proj": dense_linear_flops(tokens=tokens, d_in=d_model, d_out=d_q),
        "k_proj": dense_linear_flops(tokens=tokens, d_in=d_model, d_out=d_kv),
        "v_proj": dense_linear_flops(tokens=tokens, d_in=d_model, d_out=d_kv),
        "o_proj": dense_linear_flops(tokens=tokens, d_in=d_q, d_out=d_model),
    }


def attention_core_flops(*, batch: int, d_model: int, valid_attention_pairs: int) -> int:
    """QK + AV logical FLOPs, per the Act's normative convention:
    4 * B * valid_attention_pairs * d_model.
    """
    return 4 * batch * valid_attention_pairs * d_model


def mlp_flops(*, tokens: int, d_model: int, d_ff: int) -> int:
    return 2 * tokens * d_model * d_ff + 2 * tokens * d_ff * d_model


def lm_head_flops(*, tokens: int, d_model: int, vocab_size: int) -> int:
    return dense_linear_flops(tokens=tokens, d_in=d_model, d_out=vocab_size)


@dataclass
class FlopLedger:
    entries: list[FlopRecord] = field(default_factory=list)
    _expert_assignment_calls: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        name: str,
        kind: str,
        logical_flops: int,
        *,
        executed_estimate_flops: int | None = None,
        **metadata: Any,
    ) -> FlopRecord:
        if logical_flops < 0:
            raise ValueError("logical_flops cannot be negative")
        executed = logical_flops if executed_estimate_flops is None else executed_estimate_flops
        if executed < 0:
            raise ValueError("executed_estimate_flops cannot be negative")
        record = FlopRecord(
            name=name,
            kind=kind,
            logical_flops=int(logical_flops),
            executed_estimate_flops=int(executed),
            metadata=dict(metadata),
        )
        self.entries.append(record)
        return record

    def add_dense_linear(self, name: str, *, tokens: int, d_in: int, d_out: int) -> FlopRecord:
        return self.add(
            name, "dense_linear", dense_linear_flops(tokens=tokens, d_in=d_in, d_out=d_out),
            tokens=tokens, d_in=d_in, d_out=d_out,
        )

    def add_attention(
        self,
        name: str,
        *,
        batch: int,
        seq_len: int,
        d_model: int,
        n_head: int,
        n_kv_head: int,
        head_dim: int,
        causal: bool = True,
        window: int | None = None,
    ) -> FlopRecord:
        projections = attention_projection_flops(
            batch=batch, seq_len=seq_len, d_model=d_model, n_head=n_head, n_kv_head=n_kv_head, head_dim=head_dim
        )
        if window is not None:
            pairs = sliding_causal_pairs(seq_len, window)
        elif causal:
            pairs = full_causal_pairs(seq_len)
        else:
            pairs = full_noncausal_pairs(seq_len)
        core = attention_core_flops(batch=batch, d_model=d_model, valid_attention_pairs=pairs)
        logical_total = sum(projections.values()) + core
        return self.add(
            name,
            "attention",
            logical_total,
            batch=batch,
            seq_len=seq_len,
            d_model=d_model,
            n_head=n_head,
            n_kv_head=n_kv_head,
            head_dim=head_dim,
            causal=causal,
            window=window,
            valid_attention_pairs=pairs,
            **projections,
        )

    def add_mlp(self, name: str, *, tokens: int, d_model: int, d_ff: int) -> FlopRecord:
        return self.add(
            name, "mlp", mlp_flops(tokens=tokens, d_model=d_model, d_ff=d_ff),
            tokens=tokens, d_model=d_model, d_ff=d_ff,
        )

    def add_lm_head(self, name: str, *, tokens: int, d_model: int, vocab_size: int) -> FlopRecord:
        return self.add(
            name, "lm_head", lm_head_flops(tokens=tokens, d_model=d_model, vocab_size=vocab_size),
            tokens=tokens, d_model=d_model, vocab_size=vocab_size,
        )

    def add_embedding_lookup(self, name: str, *, tokens: int, d_model: int) -> FlopRecord:
        # A lookup is not a matmul: explicitly zero dense FLOPs, per Act 4.8.
        return self.add(name, "embedding_lookup", 0, tokens=tokens, d_model=d_model)

    def record_expert_assignments(
        self,
        *,
        expert_token_counts: Mapping[int, int],
        top_k: int,
        shared_expert_token_count: int,
        dropped_token_count: int,
        padded_token_count: int,
    ) -> None:
        """Measurement-ready API only (Act 4.8): WP-1 implements no router, so
        this only validates and records the shape of a future call; it computes
        no FLOP total. F_MoE = Sum_e F_expert(n_e) + F_shared + F_router is a
        WP-3 formula, not implemented here, and dense_flops * active_experts is
        explicitly rejected as a shortcut.
        """
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if any(count < 0 for count in expert_token_counts.values()):
            raise ValueError("expert_token_counts cannot be negative")
        if shared_expert_token_count < 0 or dropped_token_count < 0 or padded_token_count < 0:
            raise ValueError("token counts cannot be negative")
        self._expert_assignment_calls.append(
            {
                "expert_token_counts": dict(expert_token_counts),
                "top_k": top_k,
                "shared_expert_token_count": shared_expert_token_count,
                "dropped_token_count": dropped_token_count,
                "padded_token_count": padded_token_count,
            }
        )

    @property
    def total_logical_flops(self) -> int:
        return sum(entry.logical_flops for entry in self.entries)

    @property
    def total_executed_estimate_flops(self) -> int:
        return sum(entry.executed_estimate_flops for entry in self.entries)

    @property
    def flop_model_error_percent(self) -> float | None:
        logical = self.total_logical_flops
        executed = self.total_executed_estimate_flops
        if logical == 0:
            return None
        return 100.0 * (executed - logical) / logical

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_forward_flops": self.total_logical_flops,
            "executed_estimate_forward_flops": self.total_executed_estimate_flops,
            "flop_model_error_percent": self.flop_model_error_percent,
            "controller_forward_flops": 0,
            "profiler_observed_flops": None,
            "expert_assignment_calls_recorded": len(self._expert_assignment_calls),
            "entry_count": len(self.entries),
            "entries": [
                {
                    "name": e.name,
                    "kind": e.kind,
                    "logical_flops": e.logical_flops,
                    "executed_estimate_flops": e.executed_estimate_flops,
                    "metadata": e.metadata,
                }
                for e in self.entries
            ],
        }
