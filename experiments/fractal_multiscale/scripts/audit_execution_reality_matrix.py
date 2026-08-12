from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import types
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import torch
import yaml

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "legacy" / "cognitive-weave-kernel-archive.zip"
SEEDS = (101, 211, 307)
SHAPES = ((1, 8), (2, 12), (4, 12), (5, 24))
MODES = ("learned", "random", "inverted", "static")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime(archive: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory(prefix="cwc-exec-matrix-")
    with zipfile.ZipFile(archive) as handle:
        handle.extractall(temp.name)
    candidates = sorted(Path(temp.name).glob("*/cognitive-weave-kernel"))
    if len(candidates) != 1:
        temp.cleanup()
        raise RuntimeError(f"expected one archived CWK project, found {len(candidates)}")
    return temp, candidates[0]


class Counter:
    def __init__(self, model: Any) -> None:
        self.shared = 0
        self.routed = 0
        self.attention_calls = 0
        self.attention_q_tokens = 0
        self.output = 0
        self.handles = [model.experts.shared.register_forward_pre_hook(self._shared)]
        self.handles += [
            expert.register_forward_pre_hook(self._routed) for expert in model.experts.routed
        ]
        self.handles += [model.attention.attention.register_forward_pre_hook(self._attention)]
        self.handles += [model.output.register_forward_pre_hook(self._output)]

    def _shared(self, _m: Any, inputs: tuple[Any, ...]) -> None:
        x = inputs[0]
        self.shared += int(x.numel() // x.shape[-1])

    def _routed(self, _m: Any, inputs: tuple[Any, ...]) -> None:
        x = inputs[0]
        self.routed += int(x.numel() // x.shape[-1])

    def _attention(self, _m: Any, inputs: tuple[Any, ...]) -> None:
        q = inputs[0]
        self.attention_calls += 1
        self.attention_q_tokens += int(q.shape[0] * q.shape[1])

    def _output(self, _m: Any, inputs: tuple[Any, ...]) -> None:
        x = inputs[0]
        self.output += int(x.numel() // x.shape[-1])

    def close(self) -> None:
        for h in self.handles:
            h.remove()

    def as_dict(self) -> dict[str, int]:
        return {
            "shared_expert_rows": self.shared,
            "routed_expert_rows_total": self.routed,
            "attention_calls": self.attention_calls,
            "attention_q_tokens": self.attention_q_tokens,
            "output_rows": self.output,
        }


def tokens_for(batch: int, seq: int, vocab: int) -> torch.Tensor:
    return (torch.arange(batch * seq, dtype=torch.long).reshape(batch, seq) * 7 + 11) % vocab


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    temp, project = runtime(args.archive)
    sys.path.insert(0, str(project / "src"))
    try:
        from cwk.core import CognitiveWeaveKernel
        from cwk.types import ActivationBudget

        torch.set_num_threads(1)
        cfg = yaml.safe_load((project / "configs" / "smoke.yaml").read_text(encoding="utf-8"))
        base_budget = ActivationBudget(**cfg["budget"])
        analysis_budget = replace(base_budget, max_attention_density=1.0)
        vocab = int(cfg["model"]["vocab_size"])
        top_k = int(cfg["model"]["top_k"])
        num_experts = int(cfg["model"]["num_experts"])
        rows: list[dict[str, Any]] = []
        physical_skip_successes = 0
        physical_skip_trials = 0
        route_budget_effects = 0
        route_budget_trials = 0
        attention_guard_trials = 0
        attention_guard_postexec = 0
        memory_probe_rows: list[dict[str, Any]] = []

        for seed in SEEDS:
            torch.manual_seed(seed)
            model = CognitiveWeaveKernel(**cfg["model"])
            model.eval()
            # Populate memory deterministically once; memory probes later use identical stored rows.
            populate_tokens = tokens_for(2, 8, vocab)
            with torch.no_grad():
                model(populate_tokens, analysis_budget, read_memory=False, write_memory=True)

            for batch, seq in SHAPES:
                toks = tokens_for(batch, seq, vocab)
                total = batch * seq
                budgets = (
                    ("all_depth2", replace(analysis_budget, max_active_tokens=None, max_depth=2)),
                    (
                        "half_depth1",
                        replace(analysis_budget, max_active_tokens=max(1, total // 2), max_depth=1),
                    ),
                    (
                        "quarter_depth1",
                        replace(analysis_budget, max_active_tokens=max(1, total // 4), max_depth=1),
                    ),
                )
                reference_counts = None
                reference_gate = None
                for mode in MODES:
                    for budget_name, budget in budgets:
                        counter = Counter(model)
                        with torch.no_grad():
                            out = model(
                                toks,
                                budget,
                                read_memory=False,
                                write_memory=False,
                                controller_mode=mode,
                            )
                        counts = counter.as_dict()
                        counter.close()
                        gate = {
                            "active_fraction": float(
                                out.telemetry["controller_active_token_fraction"]
                            ),
                            "depth_fraction": float(out.telemetry["controller_depth_fraction"]),
                        }
                        if mode == "learned" and budget_name == "all_depth2":
                            reference_counts = counts
                            reference_gate = gate
                        elif reference_counts is not None:
                            gate_changed = gate != reference_gate
                            if gate_changed:
                                physical_skip_trials += 1
                                if (
                                    counts["shared_expert_rows"]
                                    < reference_counts["shared_expert_rows"]
                                    or counts["routed_expert_rows_total"]
                                    < reference_counts["routed_expert_rows_total"]
                                ):
                                    physical_skip_successes += 1
                        rows.append(
                            {
                                "seed": seed,
                                "batch": batch,
                                "sequence_length": seq,
                                "total_tokens": total,
                                "controller_mode": mode,
                                "budget_case": budget_name,
                                "active_fraction": gate["active_fraction"],
                                "depth_fraction": gate["depth_fraction"],
                                "counts": counts,
                            }
                        )

                # max_active_experts above top_k should be an actual governor if its name is literal.
                b_lo = replace(analysis_budget, max_active_experts=top_k)
                b_hi = replace(analysis_budget, max_active_experts=num_experts)
                with torch.no_grad():
                    out_lo = model(toks, b_lo, read_memory=False, write_memory=False)
                    out_hi = model(toks, b_hi, read_memory=False, write_memory=False)
                route_budget_trials += 1
                if not torch.equal(out_lo.route.indices, out_hi.route.indices):
                    route_budget_effects += 1

                # Deliberately fail below actual mask density; hook proves whether dense MHA ran first.
                actual_density = float(out_lo.telemetry["attention_density"])
                fail_budget = replace(
                    analysis_budget, max_attention_density=max(1e-6, actual_density * 0.5)
                )
                counter = Counter(model)
                failed = False
                try:
                    with torch.no_grad():
                        model(toks, fail_budget, read_memory=False, write_memory=False)
                except RuntimeError:
                    failed = True
                fail_counts = counter.as_dict()
                counter.close()
                attention_guard_trials += 1
                if (
                    failed
                    and fail_counts["attention_calls"] == 1
                    and fail_counts["attention_q_tokens"] == total
                ):
                    attention_guard_postexec += 1

                # Wrap memory.read: controller's token-level memory gate is produced after this call.
                calls: list[dict[str, int]] = []
                original_read = model.memory.read

                def wrapped_read(
                    self: Any,
                    queries: torch.Tensor,
                    max_reads: int,
                    _calls: list[dict[str, int]] = calls,
                    _original_read: Any = original_read,
                ):
                    _calls.append(
                        {
                            "query_rows": int(queries.numel() // queries.shape[-1]),
                            "max_reads": int(max_reads),
                        }
                    )
                    return _original_read(queries, max_reads)

                model.memory.read = types.MethodType(wrapped_read, model.memory)
                mem_budget = replace(
                    analysis_budget,
                    max_active_tokens=max(1, total // 4),
                    max_depth=1,
                    max_memory_reads=2,
                )
                with torch.no_grad():
                    mem_out = model(
                        toks,
                        mem_budget,
                        read_memory=True,
                        write_memory=False,
                        controller_mode="learned",
                    )
                model.memory.read = original_read
                memory_probe_rows.append(
                    {
                        "seed": seed,
                        "batch": batch,
                        "sequence_length": seq,
                        "total_tokens": total,
                        "memory_read_calls": calls,
                        "controller_memory_read_fraction": float(
                            mem_out.telemetry["controller_memory_read_fraction"]
                        ),
                        "memory_reads_per_query": int(mem_out.telemetry["memory_reads_per_query"]),
                    }
                )

        total_matrix_rows = len(rows)
        expert_expected = all(
            row["counts"]["shared_expert_rows"] == row["total_tokens"]
            and row["counts"]["routed_expert_rows_total"] == row["total_tokens"] * top_k
            for row in rows
        )
        memory_all_queries = all(
            item["memory_read_calls"]
            and item["memory_read_calls"][0]["query_rows"] == item["total_tokens"]
            for item in memory_probe_rows
        )
        payload = {
            "schema_version": "cwc.execution_reality_matrix.v1",
            "archive": str(args.archive),
            "archive_sha256": sha256(args.archive),
            "seeds": list(SEEDS),
            "shapes": [list(s) for s in SHAPES],
            "modes": list(MODES),
            "matrix_row_count": total_matrix_rows,
            "matrix_rows": rows,
            "active_depth_gate_changed_trials": physical_skip_trials,
            "active_depth_physical_skip_successes": physical_skip_successes,
            "all_matrix_expert_rows_equal_dense_token_topk_semantics": expert_expected,
            "max_active_experts_trials": route_budget_trials,
            "max_active_experts_route_effects": route_budget_effects,
            "attention_guard_trials": attention_guard_trials,
            "attention_executed_before_guard_trials": attention_guard_postexec,
            "memory_probe_rows": memory_probe_rows,
            "memory_read_received_all_query_rows": memory_all_queries,
            "verdict": {
                "active_depth": "SEMANTIC_GATE_ONLY"
                if physical_skip_trials > 0 and physical_skip_successes == 0
                else "UNRESOLVED",
                "max_active_experts": "LOWER_BOUND_CHECK_NOT_ACTIVE_EXPERT_GOVERNOR"
                if route_budget_effects == 0
                else "HAS_ROUTE_EFFECT",
                "attention_budget": "POST_EXECUTION_GUARD_NOT_GOVERNOR"
                if attention_guard_postexec == attention_guard_trials
                else "UNRESOLVED",
                "memory_gate": "POST_RETRIEVAL_MEMORY_GATE" if memory_all_queries else "UNRESOLVED",
                "overall": "REFERENCE_RUNTIME_CONTROL_IS_PRIMARILY_SEMANTIC_NOT_PHYSICAL_CONDITIONAL_EXECUTION",
            },
            "claim_boundary": (
                "This CPU hook matrix audits call/row semantics in the archived CWK reference only. "
                "It does not establish GPU timing, current nanochat behavior, or useful adaptive compute."
            ),
            "scientific_ascension_authority": False,
            "via_authority": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "matrix_rows": total_matrix_rows,
                    "gate_changed_trials": physical_skip_trials,
                    "physical_skip_successes": physical_skip_successes,
                    "route_budget_effects": route_budget_effects,
                    "route_budget_trials": route_budget_trials,
                    "attention_postexec": attention_guard_postexec,
                    "attention_trials": attention_guard_trials,
                    "memory_all_queries": memory_all_queries,
                    "verdict": payload["verdict"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    finally:
        temp.cleanup()


if __name__ == "__main__":
    main()
