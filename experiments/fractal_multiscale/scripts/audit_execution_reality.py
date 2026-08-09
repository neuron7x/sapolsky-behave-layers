from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
import time
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import torch
import yaml

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "legacy" / "cognitive-weave-kernel-archive.zip"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _runtime(archive: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory(prefix="cwc-execution-reality-")
    with zipfile.ZipFile(archive) as handle:
        handle.extractall(temp.name)
    candidates = sorted(Path(temp.name).glob("*/cognitive-weave-kernel"))
    if len(candidates) != 1:
        temp.cleanup()
        raise RuntimeError(f"expected one archived CWK project, found {len(candidates)}")
    return temp, candidates[0]


class WorkCounter:
    def __init__(self, model: Any) -> None:
        self.shared_rows = 0
        self.routed_rows = [0 for _ in model.experts.routed]
        self.attention_calls = 0
        self.attention_q_tokens = 0
        self.output_rows = 0
        self._handles: list[Any] = []
        self._handles.append(model.experts.shared.register_forward_pre_hook(self._shared_hook))
        for expert_id, expert in enumerate(model.experts.routed):
            self._handles.append(
                expert.register_forward_pre_hook(self._routed_hook_factory(expert_id))
            )
        self._handles.append(model.attention.attention.register_forward_pre_hook(self._attention_hook))
        self._handles.append(model.output.register_forward_pre_hook(self._output_hook))

    def close(self) -> None:
        for handle in self._handles:
            handle.remove()

    def _shared_hook(self, _module: Any, inputs: tuple[Any, ...]) -> None:
        x = inputs[0]
        self.shared_rows += int(x.numel() // x.shape[-1])

    def _routed_hook_factory(self, expert_id: int):
        def hook(_module: Any, inputs: tuple[Any, ...]) -> None:
            x = inputs[0]
            self.routed_rows[expert_id] += int(x.numel() // x.shape[-1])

        return hook

    def _attention_hook(self, _module: Any, inputs: tuple[Any, ...]) -> None:
        q = inputs[0]
        self.attention_calls += 1
        self.attention_q_tokens += int(q.shape[0] * q.shape[1])

    def _output_hook(self, _module: Any, inputs: tuple[Any, ...]) -> None:
        x = inputs[0]
        self.output_rows += int(x.numel() // x.shape[-1])

    def payload(self) -> dict[str, Any]:
        return {
            "shared_expert_rows": self.shared_rows,
            "routed_expert_rows_by_id": self.routed_rows,
            "routed_expert_rows_total": sum(self.routed_rows),
            "attention_calls": self.attention_calls,
            "attention_q_tokens": self.attention_q_tokens,
            "output_rows": self.output_rows,
        }


def _benchmark(fn: Any, *, warmup: int = 15, steps: int = 80) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    values: list[float] = []
    for _ in range(steps):
        start = time.perf_counter_ns()
        fn()
        values.append((time.perf_counter_ns() - start) / 1e6)
    values.sort()
    return {
        "median_ms": statistics.median(values),
        "p95_ms": values[min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)],
    }


def _same_route(left: Any, right: Any) -> bool:
    return bool(torch.equal(left.route.indices, right.route.indices)) and bool(
        torch.allclose(left.route.weights, right.route.weights, atol=0.0, rtol=0.0)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260810)
    args = parser.parse_args()

    temp, project = _runtime(args.archive)
    sys.path.insert(0, str(project / "src"))
    try:
        from cwk.core import CognitiveWeaveKernel
        from cwk.types import ActivationBudget

        torch.set_num_threads(1)
        torch.manual_seed(args.seed)
        cfg = yaml.safe_load((project / "configs" / "smoke.yaml").read_text(encoding="utf-8"))
        model = CognitiveWeaveKernel(**cfg["model"])
        model.eval()
        baseline_budget = ActivationBudget(**cfg["budget"])
        batch_size = int(cfg["training"]["batch_size"])
        sequence_length = int(cfg["training"]["sequence_length"])
        vocab_size = int(cfg["model"]["vocab_size"])
        total_tokens = batch_size * sequence_length
        tokens = (
            torch.arange(total_tokens, dtype=torch.long).reshape(batch_size, sequence_length) * 5 + 7
        ) % vocab_size

        interventions: list[dict[str, Any]] = []
        reference_output: Any | None = None
        reference_counts: dict[str, Any] | None = None

        budget_cases = [
            ("depth2_active_all", replace(baseline_budget, max_depth=2, max_active_tokens=None), "learned"),
            ("depth1_active_all", replace(baseline_budget, max_depth=1, max_active_tokens=None), "learned"),
            ("depth1_active24", replace(baseline_budget, max_depth=1, max_active_tokens=24), "learned"),
            ("depth1_active12", replace(baseline_budget, max_depth=1, max_active_tokens=12), "learned"),
            ("static_active12", replace(baseline_budget, max_depth=1, max_active_tokens=12), "static"),
            ("inverted_active12", replace(baseline_budget, max_depth=1, max_active_tokens=12), "inverted"),
        ]
        for name, budget, mode in budget_cases:
            counter = WorkCounter(model)
            with torch.no_grad():
                output = model(tokens, budget, read_memory=False, write_memory=False, controller_mode=mode)
            counts = counter.payload()
            counter.close()
            if reference_output is None:
                reference_output = output
                reference_counts = counts
            timing = _benchmark(
                lambda: model(tokens, budget, read_memory=False, write_memory=False, controller_mode=mode)
            )
            interventions.append(
                {
                    "name": name,
                    "controller_mode": mode,
                    "budget": {
                        "max_active_experts": budget.max_active_experts,
                        "max_attention_density": budget.max_attention_density,
                        "max_memory_reads": budget.max_memory_reads,
                        "max_depth": budget.max_depth,
                        "max_active_tokens": budget.max_active_tokens,
                    },
                    "telemetry": {
                        "controller_active_token_fraction": output.telemetry[
                            "controller_active_token_fraction"
                        ],
                        "controller_depth_fraction": output.telemetry["controller_depth_fraction"],
                        "controller_memory_read_fraction": output.telemetry[
                            "controller_memory_read_fraction"
                        ],
                        "attention_density": output.telemetry["attention_density"],
                    },
                    "work_counts": counts,
                    "same_route_as_reference": _same_route(reference_output, output),
                    "same_expert_row_counts_as_reference": counts["shared_expert_rows"]
                    == reference_counts["shared_expert_rows"]
                    and counts["routed_expert_rows_total"]
                    == reference_counts["routed_expert_rows_total"],
                    "timing_diagnostic": timing,
                }
            )

        # Router's max_active_experts parameter is a lower-bound check above top_k, not an active
        # compute budget. Test the legal values 2 and 4 on identical inputs.
        route_budget_2 = replace(baseline_budget, max_active_experts=2)
        route_budget_4 = replace(baseline_budget, max_active_experts=4)
        with torch.no_grad():
            route2 = model(tokens, route_budget_2, read_memory=False, write_memory=False)
            route4 = model(tokens, route_budget_4, read_memory=False, write_memory=False)
        max_active_experts_effective = not _same_route(route2, route4)

        # Attention density budget is checked only after attention executes. Count the attention call
        # under a deliberately failing budget to distinguish guard semantics from a compute governor.
        failing_attention_budget = replace(baseline_budget, max_attention_density=0.30)
        fail_counter = WorkCounter(model)
        attention_error = None
        try:
            with torch.no_grad():
                model(tokens, failing_attention_budget, read_memory=False, write_memory=False)
        except RuntimeError as exc:
            attention_error = str(exc)
        failing_counts = fail_counter.payload()
        fail_counter.close()

        gate_changed = any(
            item["telemetry"]["controller_depth_fraction"]
            != interventions[0]["telemetry"]["controller_depth_fraction"]
            or item["telemetry"]["controller_active_token_fraction"]
            != interventions[0]["telemetry"]["controller_active_token_fraction"]
            for item in interventions[1:]
        )
        expert_rows_invariant = all(
            item["same_expert_row_counts_as_reference"] for item in interventions
        )
        semantic_gate_only = gate_changed and expert_rows_invariant
        attention_guard_after_execution = (
            attention_error is not None
            and failing_counts["attention_calls"] == 1
            and failing_counts["attention_q_tokens"] == total_tokens
        )

        verdict = {
            "controller_active_depth_physical_skip": (
                "NOT_SUPPORTED_SEMANTIC_GATE_ONLY" if semantic_gate_only else "UNRESOLVED"
            ),
            "max_active_experts_governor": (
                "HAS_ROUTE_EFFECT" if max_active_experts_effective else "NO_EFFECT_ABOVE_TOP_K"
            ),
            "attention_budget": (
                "POST_EXECUTION_GUARD_NOT_GOVERNOR"
                if attention_guard_after_execution
                else "UNRESOLVED"
            ),
            "attention_sparse_physical_execution": "NOT_ESTABLISHED_DENSE_MHA_REFERENCE_PATH",
            "overall": (
                "LEGACY_CWK_CONDITIONAL_EXECUTION_NOT_PHYSICALLY_ESTABLISHED"
                if semantic_gate_only and attention_guard_after_execution and not max_active_experts_effective
                else "EXECUTION_REALITY_PARTIALLY_UNRESOLVED"
            ),
        }
        payload = {
            "schema_version": "cwc.execution_reality_audit.v1",
            "archive": str(args.archive),
            "archive_sha256": _sha256(args.archive),
            "seed": args.seed,
            "environment": {
                "torch": torch.__version__,
                "device": "cpu",
                "threads": torch.get_num_threads(),
            },
            "input_shape": {
                "batch_size": batch_size,
                "sequence_length": sequence_length,
                "total_tokens": total_tokens,
            },
            "interventions": interventions,
            "max_active_experts_comparison": {
                "same_route_for_budget_2_and_4": not max_active_experts_effective,
                "top_k": int(cfg["model"]["top_k"]),
            },
            "failing_attention_budget_probe": {
                "max_attention_density": 0.30,
                "runtime_error": attention_error,
                "work_counts_before_error": failing_counts,
                "attention_executed_before_guard": attention_guard_after_execution,
            },
            "verdict": verdict,
            "claim_boundary": (
                "This audit concerns the archived CWK reference implementation on CPU. It does not "
                "establish GPU behavior, useful adaptive-compute value, or the current nanochat VIA runtime."
            ),
            "via_authority": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
    finally:
        temp.cleanup()


if __name__ == "__main__":
    main()
