from nanochat.engine import Engine
from nanochat.gpt import GPT, GPTConfig


class _PilotTokenizer:
    _special = {
        "<|python_start|>": 258,
        "<|python_end|>": 259,
        "<|output_start|>": 260,
        "<|output_end|>": 261,
        "<|assistant_end|>": 262,
    }

    def encode_special(self, name):
        return self._special[name]

    def get_bos_token_id(self):
        return 263

    def decode(self, ids):
        return bytes(int(i) % 256 for i in ids).decode("latin1")

    def encode(self, text):
        return list(text.encode("latin1", errors="ignore"))


def test_engine_accepts_vocab_size_declared_on_config_only():
    cfg = GPTConfig(sequence_len=16, vocab_size=264, n_layer=1, n_head=2, n_kv_head=2, n_embd=32, window_pattern="L")
    model = GPT(cfg, pad_vocab_size_to=8)
    model.init_weights()
    model.eval()
    assert not hasattr(model, "vocab_size")
    engine = Engine(model, _PilotTokenizer())
    result, masks = engine.generate_batch([65, 66], max_tokens=2, temperature=0.0, top_k=1, seed=7)
    assert len(result) == 1
    assert result[0][:2] == [65, 66]
    assert len(masks[0]) == len(result[0])
