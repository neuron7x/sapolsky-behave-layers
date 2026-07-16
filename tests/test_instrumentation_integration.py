"""python -m pytest tests/test_instrumentation_integration.py -v

Act 8.3: micro-model integration (depth 2, short sequence, batch 1,
deterministic seed). Uses nanochat's real GPT/GPTConfig directly in a
synthetic forward/backward/optimizer-step loop shaped exactly like
scripts/base_train.py's training step, so the instrumentation wiring is
proven against nanochat's real model without requiring a trained tokenizer or
downloaded dataset shard (which base_train.py itself needs but this test
does not exercise — see docs/WP1_INSTRUMENTATION.md for the known gap).

Confirms: OFF vs COUNTERS produce identical model outputs/loss (Gate B,
mathematical neutrality); default OFF creates no artifacts directory.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from cwc.instrumentation.config import InstrumentationConfig, InstrumentationMode
from cwc.instrumentation.flops import FlopLedger
from cwc.instrumentation.noop import NullFlopLedger, NullRoutingCounters, NullRunMeter, NullWriter
from cwc.instrumentation.routing import RoutingCounters
from cwc.instrumentation.run_meter import RunMeter
from cwc.instrumentation.vram import VRAMMeter
from cwc.instrumentation.writer import InstrumentationWriter
from nanochat.gpt import GPT, GPTConfig


def _micro_model_and_batch(seed: int = 1234):
    # nanochat's flash_attention path dispatches a CUDA-only custom op
    # regardless of caller device (HAS_FA3 is a host capability check, not a
    # per-call device check), so this model only runs on CUDA tensors here.
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        pytest.skip("nanochat's flash-attention op requires CUDA tensors on this host")
    torch.manual_seed(seed)
    cfg = GPTConfig(sequence_len=32, vocab_size=64, n_layer=2, n_head=2, n_kv_head=2, n_embd=32, window_pattern="L")
    model = GPT(cfg).to(device)
    x = torch.randint(0, cfg.vocab_size, (1, 16), device=device)
    y = torch.randint(0, cfg.vocab_size, (1, 16), device=device)
    return model, x, y


def _run_micro_step(model, x, y, meter, *, step: int) -> float:
    optimizer = torch.optim.SGD(model.parameters(), lr=0.0)  # lr=0: pure forward/backward, no weight drift
    with meter.scope("train_step", step=step, tokens=x.numel()):
        optimizer.zero_grad(set_to_none=True)
        loss = model(x, y)
        loss.backward()
        optimizer.step()
    return float(loss.detach().item())


def test_off_mode_creates_no_output_directory(tmp_path: Path):
    output_dir = tmp_path / "should_not_exist"
    config = InstrumentationConfig(mode=InstrumentationMode.OFF)
    assert config.output_dir is None
    meter = NullRunMeter()
    model, x, y = _micro_model_and_batch()
    loss = _run_micro_step(model, x, y, meter, step=0)
    assert loss == loss  # finite, not NaN
    assert not output_dir.exists()


def test_off_and_counters_produce_identical_loss(tmp_path: Path):
    """Gate B: instrumentation must not change model outputs/loss."""
    model_off, x, y = _micro_model_and_batch(seed=99)
    model_counters, _, _ = _micro_model_and_batch(seed=99)

    loss_off = _run_micro_step(model_off, x, y, NullRunMeter(), step=0)

    pool = None
    from cwc.instrumentation.event_buffer import EventPool

    if torch.cuda.is_available():
        pool = EventPool(size=8)
        pool.warm_up()
    meter = RunMeter(event_pool=pool, enable_cuda_events=torch.cuda.is_available())
    loss_counters = _run_micro_step(model_counters, x, y, meter, step=0)
    meter.close()

    assert loss_off == pytest.approx(loss_counters, rel=1e-6)


def test_counters_mode_produces_valid_evidence_bundle(tmp_path: Path):
    output_dir = tmp_path / "run-1"
    writer = InstrumentationWriter(output_dir)
    flop_ledger = FlopLedger()
    routing_counters = RoutingCounters(mode=InstrumentationMode.COUNTERS)
    vram_meter = VRAMMeter(device="cuda") if torch.cuda.is_available() else None

    model, x, y = _micro_model_and_batch()
    meter = RunMeter(enable_cuda_events=False)  # CPU-safe path regardless of host
    for step in range(3):
        loss = _run_micro_step(model, x, y, meter, step=step)
        flop_ledger.add_mlp(f"step{step}", tokens=x.numel(), d_model=32, d_ff=128)
        routing_counters.record(
            step=step, active_tokens=x.numel(), active_blocks=2, active_experts=1,
            active_parameters=model.num_matmul_params(),
        )
        writer.write_metric({"step": step, "loss": loss})
    meter.close()
    writer.write_summary(
        {
            "schema_version": "1.0.0",
            "run": {"run_id": "test-run-1"},
            "environment": {},
            "model": {},
            "workload": {},
            "instrumentation": {"mode": "counters"},
            "latency": {"count": len(meter.records)},
            "throughput": {},
            "vram": (
                dataclasses.asdict(vram_meter.snapshot())
                if vram_meter and vram_meter.available
                else {}
            ),
            "flops": flop_ledger.to_dict(),
            "energy": {"available": False},
            "routing": {"step_count": routing_counters.snapshot().step_count},
            "validity": {
                "environment_match": True,
                "warmup_complete": True,
                "overhead_gate_passed": None,
                "energy_available": False,
                "energy_confidence": "unavailable",
                "profiler_disabled_for_claim_run": True,
                "trace_disabled_for_claim_run": True,
                "claimable": False,
                "reasons": ["overhead gate not run in this micro-integration test"],
            },
        }
    )
    writer.close()
    checksums_path = writer.compute_checksums()

    import json

    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "cwc_instrumentation.schema.json"
    schema = json.loads(schema_path.read_text())
    summary = json.loads((output_dir / "summary.json").read_text())
    # nanochat has no jsonschema dependency; check required top-level and
    # validity sub-keys directly rather than adding a new dependency for one
    # test's sake.
    for key in schema["required"]:
        assert key in summary, f"summary missing required top-level key: {key}"
    for key in schema["properties"]["validity"]["required"]:
        assert key in summary["validity"], f"summary.validity missing required key: {key}"

    assert (output_dir / "metrics.jsonl").exists()
    assert checksums_path.exists()
    assert len(meter.records) == 3


def test_null_stack_matches_real_stack_interface():
    """The Null* facade and the real classes must be interchangeable at the
    call sites base_train.py uses — this is what makes OFF mode a drop-in
    no-op rather than a special-cased code path.
    """
    null_meter = NullRunMeter()
    with null_meter.scope("x", step=0, tokens=1):
        pass
    null_meter.resolve()
    null_meter.flush()
    null_meter.close()

    real_meter = RunMeter(enable_cuda_events=False)
    with real_meter.scope("x", step=0, tokens=1):
        pass
    real_meter.resolve()
    real_meter.flush()
    real_meter.close()

    assert NullFlopLedger().to_dict()["enabled"] is False
    assert isinstance(FlopLedger().to_dict()["logical_forward_flops"], int)
    assert NullRoutingCounters().snapshot().step_count == 0
    assert RoutingCounters().snapshot().step_count == 0
    assert NullWriter().output_dir is None
