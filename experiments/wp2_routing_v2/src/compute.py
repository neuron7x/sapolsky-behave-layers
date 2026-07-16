"""Independent FLOP formulas (Act §15). Logical MAC*2 accounting."""
from __future__ import annotations

from experiments.wp2_routing_v2.src.contracts import VOCAB_SIZE
from experiments.wp2_routing_v2.src.task_semantic_route import SEQ_LEN
from experiments.wp2_routing_v2.src.typed_modules import D_MODEL, L_OUT

T = SEQ_LEN
d = D_MODEL


def _attn_flops():
    qkv = 2 * T * 3 * d * d
    core = 2 * 2 * T * T * d
    out = 2 * T * d * d
    return qkv + core + out


def _mlp_flops(hidden=128):
    return 2 * T * (d * hidden + hidden * d)


def direct_path_flops() -> int:
    heads = L_OUT * 2 * d * VOCAB_SIZE
    return _attn_flops() + _mlp_flops() + heads


def semantic_parser_flops() -> int:
    heads = 2 * d * (3 * VOCAB_SIZE + 2 + 1)
    return _attn_flops() + _mlp_flops() + heads


def semantic_renderer_flops() -> int:
    return L_OUT * 2 * (4 * d) * VOCAB_SIZE


def controller_flops() -> int:
    return 2 * d * 64 + 2 * 64 * 1


def semantic_path_cost() -> int:
    return semantic_parser_flops() + semantic_renderer_flops()


def per_sample_route_cost(semantic: bool) -> int:
    return semantic_path_cost() if semantic else direct_path_flops()


def total_batch_flops(batch_size: int, k_semantic: int) -> int:
    direct = (batch_size - k_semantic) * direct_path_flops()
    semantic = k_semantic * semantic_path_cost()
    ctrl = batch_size * controller_flops()
    return direct + semantic + ctrl


def parity_ratio(a: int, b: int) -> float:
    return abs(a - b) / max(a, b)
