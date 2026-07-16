from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import torch
import yaml
from cwk.core import CognitiveWeaveKernel
from cwk.instrumentation import FlopLedger, InferenceLatencyBreakdown, RoutingTrace, RunMeter
from cwk.types import ActivationBudget


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(
            "/home/neuro7/Desktop/Системи в системах /sapolsky-behave-layers/"
            "cognitive-weave-kernel-v0.1.0/cognitive-weave-kernel/configs/smoke.yaml"
        ),
    )
    parser.add_argument("--output", type=Path, default=Path("evidence/cwk_wp1_trace_32.jsonl"))
    parser.add_argument("--runs", type=int, default=32)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--fixed-shape", action="store_true")
    args = parser.parse_args()

    if args.runs < 16:
        raise SystemExit("runs must be >= 16 for the frozen fractal protocol")

    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    model_cfg = config["model"]
    train_cfg = config["training"]
    budget = ActivationBudget(**config["budget"])
    model = CognitiveWeaveKernel(**model_cfg)
    model.eval()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()

    vocab_size = int(model_cfg["vocab_size"])
    base_batch_size = int(train_cfg["batch_size"])
    base_sequence_length = int(train_cfg["sequence_length"])
    d_model = int(model_cfg["d_model"])
    hidden_dim = int(model_cfg["hidden_dim"])
    num_experts = int(model_cfg["num_experts"])
    top_k = int(model_cfg["top_k"])

    with args.output.open("a", encoding="utf-8") as handle:
        for run_index in range(args.runs):
            if args.fixed_shape:
                batch_size = base_batch_size
                sequence_length = base_sequence_length
            else:
                batch_size = max(1, base_batch_size + ((run_index % 3) - 1))
                sequence_length = base_sequence_length + 4 * (run_index % 4)
            tokens = _deterministic_tokens(
                run_index=run_index,
                batch_size=batch_size,
                sequence_length=sequence_length,
                vocab_size=vocab_size,
            )
            trace = RoutingTrace()
            ledger = FlopLedger()
            meter = RunMeter(warmup_steps=1)
            state: dict[str, Any] = {}

            forward_once = _forward_factory(
                model=model,
                tokens=tokens,
                budget=budget,
                write_memory=run_index == 0,
                state=state,
            )

            summary = meter.benchmark(
                forward_once,
                steps=1,
                routing_trace=trace,
                flop_ledger=ledger,
            )
            output = state["output"]
            total_tokens = batch_size * sequence_length
            active_tokens = _active_tokens_from_entropy(output.route.entropy)
            active_experts = int((output.route.utilization > 0).sum().item())
            trace.record(
                "cwk-forward-route",
                active_tokens=active_tokens,
                total_tokens=total_tokens,
                active_experts=active_experts,
                total_experts=num_experts,
                metadata={
                    "route_entropy_mean": float(output.route.entropy.mean().item()),
                    "route_overflow_count": output.route.overflow_count,
                },
            )
            attention_density = float(output.telemetry["attention_density"])
            ledger.add_attention(
                "local-global-attention",
                tokens=total_tokens,
                d_model=d_model,
                density=attention_density,
            )
            ledger.add_routed_ffn(
                "routed-expert-ffn",
                active_tokens=total_tokens * top_k,
                d_model=d_model,
                hidden_dim=hidden_dim,
                active_experts=1,
            )
            ledger.add_dense_linear(
                "shared-output-projection",
                tokens=total_tokens,
                d_in=d_model,
                d_out=vocab_size,
            )
            ledger.add_memory_bytes(
                "activation-read-write-estimate",
                total_tokens * d_model * 4 * 4,
            )
            ledger.add_communication_bytes(
                "routing-index-estimate",
                total_tokens * top_k * 8,
            )
            meter.record_inference_breakdown(
                InferenceLatencyBreakdown(
                    ttft_ms=summary["latency"]["end_to_end_ms"]["p50"],
                    tpot_ms=summary["latency"]["end_to_end_ms"]["p50"] / max(sequence_length, 1),
                    ttlt_ms=summary["latency"]["end_to_end_ms"]["p95"],
                    prompt_tokens=sequence_length,
                    output_tokens=1,
                )
            )
            final_summary = meter.summary(
                routing_trace=trace,
                flop_ledger=ledger,
                vram=summary["vram"],
                energy=summary["energy"],
            )
            final_summary["run_index"] = run_index
            final_summary["config"] = {
                "batch_size": batch_size,
                "sequence_length": sequence_length,
                "vocab_size": vocab_size,
                "d_model": d_model,
                "num_experts": num_experts,
                "top_k": top_k,
            }
            handle.write(json.dumps(final_summary, sort_keys=True) + "\n")

    print(args.output)


def _deterministic_tokens(
    *,
    run_index: int,
    batch_size: int,
    sequence_length: int,
    vocab_size: int,
) -> torch.Tensor:
    base = torch.arange(batch_size * sequence_length, dtype=torch.long).reshape(
        batch_size,
        sequence_length,
    )
    pattern = (base * (run_index % 7 + 1) + run_index * 13) % vocab_size
    if run_index % 3 == 0:
        pattern = torch.flip(pattern, dims=(1,))
    return pattern


def _active_tokens_from_entropy(entropy: torch.Tensor) -> int:
    threshold = float(entropy.mean().item())
    return int((entropy >= threshold).sum().item())


def _forward_factory(
    *,
    model: CognitiveWeaveKernel,
    tokens: torch.Tensor,
    budget: ActivationBudget,
    write_memory: bool,
    state: dict[str, Any],
) -> Callable[[], torch.Tensor]:
    def forward_once() -> torch.Tensor:
        with torch.no_grad():
            output = model(tokens, budget, read_memory=True, write_memory=write_memory)
        state["output"] = output
        return output.logits

    return forward_once


if __name__ == "__main__":
    main()
