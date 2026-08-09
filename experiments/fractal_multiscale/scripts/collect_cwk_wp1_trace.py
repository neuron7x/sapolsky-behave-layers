from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import torch
import yaml

ROOT = Path(__file__).resolve().parents[3]
LEGACY_ARCHIVE = ROOT / "legacy" / "cognitive-weave-kernel-archive.zip"


def _resolve_cwk_runtime(
    *,
    archive: Path,
    config: Path | None,
) -> tuple[Path, Path, tempfile.TemporaryDirectory[str] | None]:
    if config is not None:
        project = config.resolve().parents[1]
        return project, config.resolve(), None
    if not archive.is_file():
        raise SystemExit(f"legacy CWK archive missing: {archive}")
    temp = tempfile.TemporaryDirectory(prefix="cwc-cwk-runtime-")
    with zipfile.ZipFile(archive) as handle:
        handle.extractall(temp.name)
    candidates = sorted(Path(temp.name).glob("*/cognitive-weave-kernel"))
    if len(candidates) != 1:
        temp.cleanup()
        raise SystemExit(f"expected exactly one CWK project in archive, found {len(candidates)}")
    project = candidates[0]
    resolved_config = project / "configs" / "smoke.yaml"
    if not resolved_config.is_file():
        temp.cleanup()
        raise SystemExit("archived CWK smoke config missing")
    return project, resolved_config, temp


def _normalized_entropy(values: torch.Tensor) -> float:
    probs = values.detach().to(dtype=torch.float64, device="cpu")
    total = float(probs.sum().item())
    if total <= 0.0 or probs.numel() <= 1:
        return 0.0
    probs = probs / total
    entropy = float((-(probs * probs.clamp_min(1e-15).log()).sum()).item())
    return entropy / math.log(probs.numel())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-archive", type=Path, default=LEGACY_ARCHIVE)
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional explicit CWK config. When omitted, the in-repository legacy archive is used.",
    )
    parser.add_argument("--output", type=Path, default=Path("evidence/cwk_wp1_trace_64.jsonl"))
    parser.add_argument("--runs", type=int, default=64)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--fixed-shape", action="store_true")
    parser.add_argument(
        "--controller-mode",
        choices=("learned", "random", "inverted", "static"),
        default="learned",
    )
    args = parser.parse_args()

    if args.runs < 16:
        raise SystemExit("runs must be >= 16 for the frozen fractal protocol")

    project, config_path, temp = _resolve_cwk_runtime(
        archive=args.legacy_archive,
        config=args.config,
    )
    sys.path.insert(0, str(project / "src"))
    try:
        from cwk.core import CognitiveWeaveKernel
        from cwk.instrumentation import FlopLedger, InferenceLatencyBreakdown, RoutingTrace, RunMeter
        from cwk.types import ActivationBudget

        torch.set_num_threads(1)
        torch.manual_seed(args.seed)
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
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
                    # 12-shape deterministic cycle: 3 batch states x 4 sequence states.
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
                    controller_mode=args.controller_mode,
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
                active_tokens = int(output.graph.active_token_mask.sum().item())
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
                        "expert_utilization": [
                            float(value) for value in output.route.utilization.detach().cpu().tolist()
                        ],
                        "expert_utilization_entropy": _normalized_entropy(output.route.utilization),
                        "controller_active_token_fraction": float(
                            output.telemetry["controller_active_token_fraction"]
                        ),
                        "controller_depth_fraction": float(
                            output.telemetry["controller_depth_fraction"]
                        ),
                        "controller_memory_read_fraction": float(
                            output.telemetry["controller_memory_read_fraction"]
                        ),
                        "attention_density": float(output.telemetry["attention_density"]),
                        "topology_hash": str(output.telemetry["topology_hash"]),
                        "controller_mode": args.controller_mode,
                    },
                )
                attention_density = float(output.telemetry["attention_density"])
                ledger.add_attention(
                    "local-global-attention",
                    tokens=total_tokens,
                    d_model=d_model,
                    density=attention_density,
                )
                # This ledger is a semantic estimate and deliberately does not claim that controller
                # active/depth masks skipped expert execution. The execution-reality audit counts
                # actual expert inputs separately.
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
                        tpot_ms=summary["latency"]["end_to_end_ms"]["p50"]
                        / max(sequence_length, 1),
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
                final_summary["trace_seed"] = args.seed
                final_summary["controller_mode"] = args.controller_mode
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
    finally:
        if temp is not None:
            temp.cleanup()


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


def _forward_factory(
    *,
    model: Any,
    tokens: torch.Tensor,
    budget: Any,
    write_memory: bool,
    controller_mode: str,
    state: dict[str, Any],
) -> Callable[[], torch.Tensor]:
    def forward_once() -> torch.Tensor:
        with torch.no_grad():
            output = model(
                tokens,
                budget,
                read_memory=True,
                write_memory=write_memory,
                controller_mode=controller_mode,
            )
        state["output"] = output
        return output.logits

    return forward_once


if __name__ == "__main__":
    main()
