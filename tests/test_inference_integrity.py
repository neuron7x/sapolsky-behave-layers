from __future__ import annotations

import copy
from pathlib import Path
from typing import ClassVar

import pytest
import torch

from nanochat.checkpoint_manager import load_checkpoint, save_checkpoint
from nanochat.engine import Engine, KVCache, sample_next_token
from nanochat.inference_contracts import MAX_SEED, validate_generation_request
from nanochat.model_integrity import build_state_manifest, verify_state_manifest


class _Config:
    n_kv_head = 1
    n_head = 1
    n_embd = 4
    n_layer = 1
    sequence_len = 8
    vocab_size = 7


class _Model:
    config = _Config()
    vocab_size = 7

    def get_device(self) -> torch.device:
        return torch.device("cpu")

    def forward(self, ids: torch.Tensor, kv_cache: KVCache | None = None) -> torch.Tensor:
        if kv_cache is not None:
            kv_cache.advance(ids.shape[1])
        basis = torch.arange(self.vocab_size, dtype=torch.float32)
        return basis.expand(ids.shape[0], ids.shape[1], -1)


class _Tokenizer:
    _special: ClassVar[dict[str, int]] = {
        "<|python_start|>": 1,
        "<|python_end|>": 2,
        "<|output_start|>": 3,
        "<|output_end|>": 4,
        "<|assistant_end|>": 5,
    }

    def encode_special(self, value: str) -> int:
        return self._special[value]

    def get_bos_token_id(self) -> int:
        return 6

    def encode(self, value: str) -> list[int]:
        return [0] * len(value)

    def decode(self, tokens: list[int]) -> str:
        return "".join(str(token) for token in tokens)


@pytest.mark.parametrize(
    ("override", "error"),
    [
        ({"tokens": []}, ValueError),
        ({"tokens": [True]}, TypeError),
        ({"tokens": [-1]}, ValueError),
        ({"tokens": [7]}, ValueError),
        ({"num_samples": 0}, ValueError),
        ({"max_tokens": -1}, ValueError),
        ({"max_tokens": 7}, ValueError),
        ({"temperature": float("nan")}, ValueError),
        ({"temperature": float("inf")}, ValueError),
        ({"temperature": -0.1}, ValueError),
        ({"top_k": -1}, ValueError),
        ({"seed": MAX_SEED + 1}, ValueError),
    ],
)
def test_generation_contract_fails_closed(override: dict[str, object], error: type[Exception]) -> None:
    request: dict[str, object] = {
        "tokens": [1, 2],
        "num_samples": 1,
        "max_tokens": 2,
        "temperature": 1.0,
        "top_k": None,
        "seed": 42,
        "sequence_len": 8,
        "vocab_size": 7,
    }
    request.update(override)
    with pytest.raises(error):
        validate_generation_request(**request)


def test_kv_cache_rejects_divergence_overflow_and_bad_layer() -> None:
    cache = KVCache(2, 1, 4, 2, 1, "cpu", torch.float32)
    cache.cache_seqlens[:] = torch.tensor([1, 2], dtype=torch.int32)
    with pytest.raises(RuntimeError, match="divergent"):
        cache.get_pos()
    cache.cache_seqlens.fill_(3)
    with pytest.raises(OverflowError, match="capacity"):
        cache.advance(2)
    with pytest.raises(IndexError):
        cache.get_layer_cache(1)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_sampler_rejects_nonfinite_logits(bad: float) -> None:
    logits = torch.tensor([[0.0, bad]])
    with pytest.raises(FloatingPointError):
        sample_next_token(logits, torch.Generator().manual_seed(1))


def test_greedy_generation_is_invariant_to_seed_and_batch_replication() -> None:
    engine = Engine(_Model(), _Tokenizer())
    single, _ = engine.generate_batch([1, 2], num_samples=1, max_tokens=3, temperature=0, seed=1)
    batch, _ = engine.generate_batch([1, 2], num_samples=4, max_tokens=3, temperature=0, seed=999)
    assert batch == single * 4


def test_weight_manifest_is_order_invariant_and_content_sensitive() -> None:
    state = {
        "b": torch.tensor([1.0, 2.0]),
        "a": torch.arange(6, dtype=torch.int64).reshape(2, 3),
    }
    reordered = {"a": state["a"], "b": state["b"]}
    expected = build_state_manifest(state)
    assert build_state_manifest(reordered) == expected
    assert verify_state_manifest(reordered, expected) == []

    tampered = copy.deepcopy(state)
    tampered["a"][0, 0] += 1
    errors = verify_state_manifest(tampered, expected)
    assert any("state_sha256" in error for error in errors)
    assert any("tensor inventory" in error for error in errors)


def test_weight_manifest_rejects_nonfinite_or_missing_weights() -> None:
    with pytest.raises(FloatingPointError):
        build_state_manifest({"weight": torch.tensor([float("nan")])})
    expected = build_state_manifest({"weight": torch.ones(2), "bias": torch.zeros(1)})
    errors = verify_state_manifest({"weight": torch.ones(2)}, expected)
    assert errors


def test_checkpoint_roundtrip_verifies_weight_content(tmp_path: Path) -> None:
    checkpoint_dir = str(tmp_path)
    state = {"weight": torch.arange(4, dtype=torch.float32)}
    save_checkpoint(checkpoint_dir, 3, state, None, {"model_config": {}}, rank=0)
    loaded, optimizer, meta = load_checkpoint(checkpoint_dir, 3, torch.device("cpu"))
    assert torch.equal(loaded["weight"], state["weight"])
    assert optimizer is None
    assert meta["model_integrity"]["state_sha256"] == build_state_manifest(state)["state_sha256"]

    model_path = tmp_path / "model_000003.pt"
    corrupted = torch.load(model_path, weights_only=True)
    corrupted["weight"][0] += 1
    torch.save(corrupted, model_path)
    with pytest.raises(RuntimeError, match="weight integrity verification failed"):
        load_checkpoint(checkpoint_dir, 3, torch.device("cpu"))
