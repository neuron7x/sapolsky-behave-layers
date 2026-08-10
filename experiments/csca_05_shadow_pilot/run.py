from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import resource
import statistics
import time
from typing import Iterable

import numpy as np

from cwc.credit.ablation_shapley import (
    antithetic_permutation_ablation_shapley,
    exact_ablation_shapley,
    ranked_by_absolute_credit,
)
from cwc.credit.context_authority import decide_context_direction
from cwc.inference.composed_authority import ShadowCreditPolicy, decide_shadow_credit
from cwc.inference.intervention_trace import InterventionCreditTrace
from nanochat.engine import Engine

from .direct_credit import (
    DirectModelCoalitionOracle,
    PLAYERS,
    PromptInterventionSpec,
    candidate_spans,
    l1_error,
    top_gap,
)
from .runtime_model import (
    BytePilotTokenizer,
    CODE_MARKER,
    PROSE_MARKER,
    file_sha256,
    load_checkpoint,
    state_dict_sha256,
    train_checkpoint,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "experiments/csca_05_shadow_pilot/protocol.json").read_text())
ART = ROOT / "artifacts/csca-05-runtime"
CAL_POLICY = ART / "calibration/frozen_policy.json"
WP18 = ROOT / "artifacts/wp18-real-workload-pilot"
CONTEXT_FILES = {
    "PROSE": {
        "train": WP18 / "corpus_prose_train.txt",
        "calibration": [WP18 / "corpus_prose_eval1.txt", WP18 / "corpus_prose_eval2.txt"],
        "primary": [WP18 / "corpus_prose_eval3.txt", WP18 / "corpus_prose_eval4.txt"],
        "replication": [WP18 / "corpus_prose_eval5.txt"],
    },
    "CODE": {
        "train": WP18 / "corpus_code_train.txt",
        "calibration": [WP18 / "corpus_code_eval1.txt", WP18 / "corpus_code_eval2.txt"],
        "primary": [WP18 / "corpus_code_eval3.txt", WP18 / "corpus_code_eval4.txt"],
        "replication": [WP18 / "corpus_code_eval5.txt"],
    },
}
MARKER = {"PROSE": PROSE_MARKER, "CODE": CODE_MARKER}
SEED = {"calibration": 1301, "primary": 2301, "replication": 3301}


def _json_dump(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _hash_jsonable(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _read_split(context: str, cohort: str) -> bytes:
    return b"\n".join(path.read_bytes() for path in CONTEXT_FILES[context][cohort])


def _prompt_specs(context: str, cohort: str) -> list[PromptInterventionSpec]:
    raw = _read_split(context, cohort)
    n = int(PROTOCOL["prompts_per_context"])
    content = int(PROTOCOL["prompt_content_bytes"])
    if len(raw) <= content:
        raise ValueError(f"insufficient {context}/{cohort} bytes")
    used: set[int] = set()
    specs = []
    for i in range(n):
        digest = hashlib.sha256(f"CSCA05:{cohort}:{context}:{i}".encode()).digest()
        offset = int.from_bytes(digest[:8], "big") % (len(raw) - content)
        while offset in used:
            offset = (offset + 1) % (len(raw) - content)
        used.add(offset)
        tokens = (MARKER[context], *raw[offset : offset + content])
        spans = candidate_spans(len(tokens))
        specs.append(PromptInterventionSpec(tuple(int(x) for x in tokens), context, spans))
    return specs


def _checkpoint_path(cohort: str) -> Path:
    return ART / "checkpoints" / f"{cohort}_seed{SEED[cohort]}.pt"


def ensure_checkpoint(cohort: str) -> dict:
    path = _checkpoint_path(cohort)
    meta_path = path.with_suffix(".meta.json")
    if path.exists() and meta_path.exists():
        return json.loads(meta_path.read_text())
    t = PROTOCOL["training"]
    meta = train_checkpoint(
        seed=SEED[cohort],
        prose_train=CONTEXT_FILES["PROSE"]["train"],
        code_train=CONTEXT_FILES["CODE"]["train"],
        steps=int(t["steps"]),
        batch_size=int(t["batch_size"]),
        learning_rate=float(t["learning_rate"]),
        weight_decay=float(t["weight_decay"]),
        checkpoint_path=path,
    )
    _json_dump(meta_path, meta)
    return meta


def _evaluate_exact(model, spec: PromptInterventionSpec):
    oracle = DirectModelCoalitionOracle(model, spec)
    started = time.perf_counter()
    estimate = exact_ablation_shapley(PLAYERS, oracle)
    wall = time.perf_counter() - started
    return estimate, oracle, wall


def _evaluate_approx(model, spec: PromptInterventionSpec, *, pairs: int, seed: int):
    oracle = DirectModelCoalitionOracle(model, spec)
    started = time.perf_counter()
    estimate = antithetic_permutation_ablation_shapley(
        PLAYERS, oracle, pairs=pairs, rng=random.Random(seed)
    )
    wall = time.perf_counter() - started
    return estimate, oracle, wall


def _exact_resolved(exact, delta: float) -> tuple[bool, str]:
    ranked = ranked_by_absolute_credit(exact.credits)
    return top_gap(exact.credits) > delta, ranked[0]


def _score_records(records: list[dict], *, delta: float, budget: int) -> dict:
    z = float(PROTOCOL["interval_z"])
    policy = ShadowCreditPolicy(
        version=f"CSCA05-CAL-v1-b{budget}",
        interval_z=z,
        delta=delta,
        max_unique_forward_evaluations=2 ** len(PLAYERS),
    )
    scored = []
    for row in records:
        approx = row["approx_by_budget"][str(budget)]
        from cwc.credit.ablation_shapley import AblationShapleyEstimate
        est = AblationShapleyEstimate(
            credits=approx["credits"],
            estimator_variance=approx["variance"],
            logical_evaluations=approx["logical_evaluations"],
            unique_forward_evaluations=approx["unique_forward_evaluations"],
            sampling_units=approx["sampling_units"],
            method=approx["method"],
        )
        decision = decide_shadow_credit(est, policy, context=row["context"])
        resolved, exact_top = _exact_resolved_obj(row["exact_credits"], delta)
        accepted = decision.state == "ACCEPT_SHADOW_CREDIT_CONTEXT_BOUND"
        correct = accepted and resolved and decision.candidate == exact_top
        false = accepted and not correct
        scored.append({
            "context": row["context"],
            "accepted": accepted,
            "resolved": resolved,
            "correct": correct,
            "false": false,
            "l1_error": l1_error(approx["credits"], row["exact_credits"]),
        })

    def metrics(rows: list[dict]) -> dict:
        accepted = sum(r["accepted"] for r in rows)
        resolved = sum(r["resolved"] for r in rows)
        correct = sum(r["correct"] for r in rows)
        false = sum(r["false"] for r in rows)
        return {
            "n": len(rows),
            "accepted": accepted,
            "exact_resolved": resolved,
            "coverage": accepted / max(resolved, 1),
            "selective_false_causal_authority": false / max(accepted, 1),
            "false_authority_count": false,
            "top_accuracy_given_accept": correct / max(accepted, 1),
            "median_credit_l1_error": float(statistics.median(r["l1_error"] for r in rows)),
        }

    return {
        "pooled": metrics(scored),
        "PROSE": metrics([r for r in scored if r["context"] == "PROSE"]),
        "CODE": metrics([r for r in scored if r["context"] == "CODE"]),
    }


def _exact_resolved_obj(credits: dict[str, float], delta: float) -> tuple[bool, str]:
    ranked = ranked_by_absolute_credit(credits)
    return top_gap(credits) > delta, ranked[0]


def run_calibration() -> dict:
    ART.mkdir(parents=True, exist_ok=True)
    meta = ensure_checkpoint("calibration")
    model = load_checkpoint(_checkpoint_path("calibration"))
    records: list[dict] = []
    gaps = []
    for context in ("PROSE", "CODE"):
        for idx, spec in enumerate(_prompt_specs(context, "calibration")):
            exact, exact_oracle, exact_wall = _evaluate_exact(model, spec)
            gap = top_gap(exact.credits)
            gaps.append(gap)
            approx_by_budget = {}
            for budget in PROTOCOL["antithetic_pair_budgets"]:
                approx, approx_oracle, approx_wall = _evaluate_approx(
                    model, spec, pairs=int(budget), seed=SEED["calibration"] * 100000 + idx * 100 + int(budget) + (0 if context == "PROSE" else 50000)
                )
                approx_by_budget[str(budget)] = {
                    "credits": approx.credits,
                    "variance": approx.estimator_variance,
                    "logical_evaluations": approx.logical_evaluations,
                    "unique_forward_evaluations": approx.unique_forward_evaluations,
                    "sampling_units": approx.sampling_units,
                    "method": approx.method,
                    "physical_forward_calls_including_factual": approx_oracle.forward_calls,
                    "wall_seconds": approx_wall,
                }
            records.append({
                "context": context,
                "index": idx,
                "prompt_hash": spec.prompt_hash,
                "exact_credits": exact.credits,
                "exact_gap": gap,
                "exact_unique_forward_evaluations": exact.unique_forward_evaluations,
                "exact_physical_forward_calls_including_factual": exact_oracle.forward_calls,
                "exact_wall_seconds": exact_wall,
                "approx_by_budget": approx_by_budget,
            })
    q10 = float(np.quantile(np.asarray(gaps, dtype=float), 0.10, method="linear"))
    delta = float(min(0.25, max(1e-6, 0.25 * q10)))
    median_gap = float(statistics.median(gaps))
    budget_results = {}
    chosen = None
    for budget in PROTOCOL["antithetic_pair_budgets"]:
        m = _score_records(records, delta=delta, budget=int(budget))
        budget_results[str(budget)] = m
        per_context_pass = all(
            m[stratum]["false_authority_count"] == 0
            and m[stratum]["top_accuracy_given_accept"] == 1.0
            and m[stratum]["coverage"] >= float(PROTOCOL["min_coverage"])
            for stratum in ("pooled", "PROSE", "CODE")
        )
        error_pass = m["pooled"]["median_credit_l1_error"] <= median_gap / 4.0
        if chosen is None and per_context_pass and error_pass:
            chosen = int(budget)
    payload = {
        "experiment_id": "CSCA-05-RUNTIME",
        "cohort": "CALIBRATION",
        "checkpoint": meta,
        "n_prompts": len(records),
        "delta_q10_exact_gap": q10,
        "delta": delta,
        "median_exact_top_gap": median_gap,
        "budget_metrics": budget_results,
        "chosen_budget": chosen,
        "calibration_pass": chosen is not None,
        "records_sha256": _hash_jsonable(records),
    }
    _json_dump(ART / "calibration/raw_records.json", records)
    _json_dump(ART / "calibration/calibration_result.json", payload)
    if chosen is not None:
        policy = {
            "experiment_id": "CSCA-05-RUNTIME",
            "policy_version": "CSCA05-SHADOW-v1",
            "delta": delta,
            "interval_z": float(PROTOCOL["interval_z"]),
            "chosen_antithetic_pairs": chosen,
            "max_unique_coalition_forwards": 2 ** len(PLAYERS),
            "min_coverage": float(PROTOCOL["min_coverage"]),
            "required_false_authority": 0.0,
            "required_accuracy_given_accept": 1.0,
            "calibration_records_sha256": payload["records_sha256"],
            "active_control": False
        }
        _json_dump(CAL_POLICY, policy)
    return payload


def _percentile(values: list[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), q, method="linear")) if values else 0.0


def _output_hash(output) -> str:
    return _hash_jsonable(output)


def run_confirmatory(cohort: str) -> dict:
    if cohort not in {"primary", "replication"}:
        raise ValueError(cohort)
    if not CAL_POLICY.exists():
        raise RuntimeError("frozen calibration policy missing")
    policy_raw = json.loads(CAL_POLICY.read_text())
    budget = int(policy_raw["chosen_antithetic_pairs"])
    delta = float(policy_raw["delta"])
    policy = ShadowCreditPolicy(
        version=policy_raw["policy_version"],
        interval_z=float(policy_raw["interval_z"]),
        delta=delta,
        max_unique_forward_evaluations=int(policy_raw["max_unique_coalition_forwards"]),
    )
    meta = ensure_checkpoint(cohort)
    model = load_checkpoint(_checkpoint_path(cohort))
    tokenizer = BytePilotTokenizer()
    engine = Engine(model, tokenizer)
    # warm the actual engine path once; not part of measured cohort
    warm = _prompt_specs("PROSE", cohort)[0]
    engine.generate_batch(list(warm.prompt_tokens), max_tokens=2, temperature=0.0, top_k=1, seed=1)
    traces = []
    score_rows = []
    baseline_times = []
    instrumented_times = []
    exact_times = []
    physical_probe_forwards = []
    output_mismatches = 0
    state_mutations = 0
    exact_by_context = {"PROSE": [], "CODE": []}
    trace_dir = ART / cohort / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    all_specs = [(context, idx, spec) for context in ("PROSE", "CODE") for idx, spec in enumerate(_prompt_specs(context, cohort))]
    for global_idx, (context, idx, spec) in enumerate(all_specs):
        generation_kwargs = {"max_tokens": 4, "temperature": 0.0, "top_k": 1, "seed": 900000 + global_idx}
        state_before = state_dict_sha256(model)
        # AB/BA order alternates to reduce systematic warm-cache timing bias.
        if global_idx % 2 == 0:
            t0 = time.perf_counter(); off = engine.generate_batch(list(spec.prompt_tokens), **generation_kwargs); baseline = time.perf_counter() - t0
            t0 = time.perf_counter(); on = engine.generate_batch(list(spec.prompt_tokens), **generation_kwargs)
            approx, approx_oracle, _ = _evaluate_approx(model, spec, pairs=budget, seed=SEED[cohort] * 100000 + global_idx)
            instrumented = time.perf_counter() - t0
        else:
            t0 = time.perf_counter(); on = engine.generate_batch(list(spec.prompt_tokens), **generation_kwargs)
            approx, approx_oracle, _ = _evaluate_approx(model, spec, pairs=budget, seed=SEED[cohort] * 100000 + global_idx)
            instrumented = time.perf_counter() - t0
            t0 = time.perf_counter(); off = engine.generate_batch(list(spec.prompt_tokens), **generation_kwargs); baseline = time.perf_counter() - t0
        state_after_sidecar = state_dict_sha256(model)
        if on != off:
            output_mismatches += 1
        if state_before != state_after_sidecar:
            state_mutations += 1

        decision = decide_shadow_credit(approx, policy, context=context)
        exact, exact_oracle, exact_wall = _evaluate_exact(model, spec)
        exact_times.append(exact_wall)
        exact_by_context[context].append(exact.credits)
        resolved, exact_top = _exact_resolved_obj(exact.credits, delta)
        accepted = decision.state == "ACCEPT_SHADOW_CREDIT_CONTEXT_BOUND"
        correct = accepted and resolved and decision.candidate == exact_top
        false = accepted and not correct
        score_rows.append({
            "context": context,
            "accepted": accepted,
            "resolved": resolved,
            "correct": correct,
            "false": false,
            "l1_error": l1_error(approx.credits, exact.credits),
            "exact_gap": top_gap(exact.credits),
            "approx_candidate": decision.candidate,
            "exact_candidate": exact_top,
            "decision_state": decision.state,
        })
        baseline_times.append(baseline)
        instrumented_times.append(instrumented)
        physical_probe_forwards.append(approx_oracle.forward_calls)
        trace = InterventionCreditTrace(
            trace_id=f"{cohort}-{context}-{idx:03d}",
            cohort=cohort.upper(),
            context=context,
            checkpoint_hash=meta["checkpoint_sha256"],
            model_state_hash_before=state_before,
            model_state_hash_after=state_after_sidecar,
            prompt_hash=spec.prompt_hash,
            base_output_hash=_output_hash(off),
            factual_top_token=approx_oracle.factual_top_token,
            candidate_spans=spec.spans,
            intervention_token=int(PROTOCOL["neutral_byte"]),
            estimator_method=approx.method,
            estimator_budget=budget,
            approximate_credits=approx.credits,
            approximate_variance=approx.estimator_variance,
            exact_credits=exact.credits,
            decision_state=decision.state,
            decision_candidate=decision.candidate,
            decision_sign=decision.sign,
            authority_scope="CONTEXT_ONLY",
            abstention_reason=decision.reason if not accepted else "NONE",
            logical_evaluations=approx.logical_evaluations,
            unique_forward_evaluations=approx.unique_forward_evaluations,
            runtime_telemetry={
                "baseline_generation_seconds": baseline,
                "instrumented_generation_plus_sidecar_seconds": instrumented,
                "approx_physical_forward_calls_including_factual": approx_oracle.forward_calls,
                "exact_evaluation_seconds_excluded_from_shadow_latency": exact_wall,
                "process_maxrss_kb": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            },
            active_control=False,
        )
        trace_payload = json.loads(trace.canonical_json())
        trace_payload["trace_sha256"] = trace.sha256()
        _json_dump(trace_dir / f"{trace.trace_id}.json", trace_payload)
        traces.append(trace_payload)

    def metrics(rows):
        accepted = sum(r["accepted"] for r in rows)
        resolved = sum(r["resolved"] for r in rows)
        false = sum(r["false"] for r in rows)
        correct = sum(r["correct"] for r in rows)
        return {
            "n": len(rows),
            "accepted": accepted,
            "exact_resolved": resolved,
            "coverage": accepted / max(resolved, 1),
            "false_authority_count": false,
            "selective_false_causal_authority": false / max(accepted, 1),
            "top_accuracy_given_accept": correct / max(accepted, 1),
            "median_credit_l1_error": float(statistics.median(r["l1_error"] for r in rows)),
            "median_exact_top_gap": float(statistics.median(r["exact_gap"] for r in rows)),
        }
    stratified = {
        "pooled": metrics(score_rows),
        "PROSE": metrics([r for r in score_rows if r["context"] == "PROSE"]),
        "CODE": metrics([r for r in score_rows if r["context"] == "CODE"]),
    }

    # Aggregate context scope from mean exact signed credit in each context.
    mean_by_context = {}
    for context, rows in exact_by_context.items():
        mean_by_context[context] = {p: float(np.mean([r[p] for r in rows])) for p in PLAYERS}
    context_decision = decide_context_direction(mean_by_context)

    per_context_pass = all(
        stratified[s]["false_authority_count"] == 0
        and stratified[s]["top_accuracy_given_accept"] == 1.0
        and stratified[s]["coverage"] >= float(policy_raw["min_coverage"])
        for s in ("pooled", "PROSE", "CODE")
    )
    noninterference = output_mismatches == 0 and state_mutations == 0
    passed = bool(per_context_pass and noninterference)
    payload = {
        "experiment_id": "CSCA-05-RUNTIME",
        "cohort": cohort.upper(),
        "checkpoint": meta,
        "policy": policy_raw,
        "metrics": stratified,
        "context_mean_exact_credit": mean_by_context,
        "context_scope": {
            "state": context_decision.state,
            "candidate": context_decision.candidate,
            "sign": context_decision.sign,
            "context_signs": context_decision.context_signs,
        },
        "noninterference": {
            "output_mismatch_count": output_mismatches,
            "model_state_mutation_count": state_mutations,
            "pass": noninterference,
        },
        "physical_cpu_telemetry": {
            "baseline_generation_p50_seconds": _percentile(baseline_times, 0.50),
            "baseline_generation_p95_seconds": _percentile(baseline_times, 0.95),
            "baseline_generation_p99_seconds": _percentile(baseline_times, 0.99),
            "instrumented_total_p50_seconds": _percentile(instrumented_times, 0.50),
            "instrumented_total_p95_seconds": _percentile(instrumented_times, 0.95),
            "instrumented_total_p99_seconds": _percentile(instrumented_times, 0.99),
            "median_overhead_ratio": float(statistics.median(i / max(b, 1e-12) for i, b in zip(instrumented_times, baseline_times, strict=True))),
            "median_approx_forward_calls_including_factual": float(statistics.median(physical_probe_forwards)),
            "gpu_available": False,
            "gpu_metrics": "NOT_MEASURED_CPU_ONLY_EXECUTION_ENVIRONMENT"
        },
        "trace_count": len(traces),
        "trace_manifest_sha256": _hash_jsonable([t["trace_sha256"] for t in traces]),
        "cohort_pass": passed,
        "active_control": False,
    }
    _json_dump(ART / cohort / "result.json", payload)
    _json_dump(ART / cohort / "score_rows.json", score_rows)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["calibration", "primary", "replication"])
    args = parser.parse_args()
    if args.phase == "calibration":
        payload = run_calibration()
    else:
        payload = run_confirmatory(args.phase)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
