from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path
import random
from typing import Iterable

import torch

from nanochat.gpt import GPT, GPTConfig

PROSE_MARKER = 256
CODE_MARKER = 257
PYTHON_START = 258
PYTHON_END = 259
OUTPUT_START = 260
OUTPUT_END = 261
ASSISTANT_END = 262
BOS = 263
VOCAB_SIZE = 264


class BytePilotTokenizer:
    special = {
        "<|python_start|>": PYTHON_START,
        "<|python_end|>": PYTHON_END,
        "<|output_start|>": OUTPUT_START,
        "<|output_end|>": OUTPUT_END,
        "<|assistant_end|>": ASSISTANT_END,
    }

    def encode_special(self, name: str) -> int:
        return self.special[name]

    def get_bos_token_id(self) -> int:
        return BOS

    def decode(self, ids: Iterable[int]) -> str:
        return bytes(int(i) % 256 for i in ids if 0 <= int(i) < 256).decode("latin1", errors="ignore")

    def encode(self, text: str) -> list[int]:
        return list(text.encode("latin1", errors="ignore"))


def model_config() -> GPTConfig:
    return GPTConfig(
        sequence_len=48,
        vocab_size=VOCAB_SIZE,
        n_layer=2,
        n_head=4,
        n_kv_head=4,
        n_embd=64,
        window_pattern="L",
    )


def state_dict_sha256(model: GPT) -> str:
    h = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        t = tensor.detach().cpu().contiguous()
        h.update(name.encode())
        h.update(str(t.dtype).encode())
        h.update(str(tuple(t.shape)).encode())
        h.update(t.view(torch.uint8).numpy().tobytes())
    return h.hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _training_batch(
    prose: bytes,
    code: bytes,
    *,
    rng: random.Random,
    batch_size: int,
    sequence_len: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    xs: list[list[int]] = []
    ys: list[list[int]] = []
    for _ in range(batch_size):
        context_is_code = rng.random() < 0.5
        raw = code if context_is_code else prose
        marker = CODE_MARKER if context_is_code else PROSE_MARKER
        need = sequence_len
        offset = rng.randrange(0, len(raw) - need - 1)
        seq = [marker] + list(raw[offset : offset + need])
        xs.append(seq[:sequence_len])
        ys.append(seq[1 : sequence_len + 1])
    return torch.tensor(xs, dtype=torch.long), torch.tensor(ys, dtype=torch.long)


def train_checkpoint(
    *,
    seed: int,
    prose_train: Path,
    code_train: Path,
    steps: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    checkpoint_path: Path,
) -> dict:
    torch.manual_seed(seed)
    random.seed(seed)
    rng = random.Random(seed)
    torch.use_deterministic_algorithms(True)
    model = GPT(model_config(), pad_vocab_size_to=8)
    model.init_weights()
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    prose = prose_train.read_bytes()
    code = code_train.read_bytes()
    losses: list[float] = []
    for _ in range(steps):
        x, y = _training_batch(
            prose,
            code,
            rng=rng,
            batch_size=batch_size,
            sequence_len=model.config.sequence_len,
        )
        optimizer.zero_grad(set_to_none=True)
        loss = model(x, y)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    model.eval()
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seed": seed,
        "config": asdict(model.config),
        "state_dict": model.state_dict(),
        "training": {
            "steps": steps,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "initial_loss": losses[0],
            "final_loss": losses[-1],
            "mean_last_50_loss": sum(losses[-50:]) / min(50, len(losses)),
        },
        "data_hashes": {
            "prose": file_sha256(prose_train),
            "code": file_sha256(code_train),
        },
    }
    torch.save(payload, checkpoint_path)
    return {
        "seed": seed,
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": file_sha256(checkpoint_path),
        "state_dict_sha256": state_dict_sha256(model),
        **payload["training"],
        "data_hashes": payload["data_hashes"],
    }


def load_checkpoint(path: Path) -> GPT:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    model = GPT(GPTConfig(**payload["config"]), pad_vocab_size_to=8)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model
