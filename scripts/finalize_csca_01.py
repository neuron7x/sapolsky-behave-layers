from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from cwc.research_ops.evidence_graph import EvidenceGraph
from cwc.research_ops.governance import HumanDecision, write_human_decision
from cwc.research_ops.provenance import sha256_file

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/csca-01"
RESULT_DIR = ROOT / "research/results/CSCA-01"
REG = ROOT / "research/registry"

OOD_CONTEXTS = ("OOD_WEAK_CONFOUNDER", "OOD_SIGN_INVERSION")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def metric(summary: dict, method: str, context: str, key: str) -> float:
    return float(summary["summary"][method][context][key])


def exact_null_max(path: Path) -> float:
    rows = read_rows(path / "seed_results.csv")
    vals: list[float] = []
    for row in rows:
        if row["method"] != "EXACT_CF_SHAPLEY":
            continue
        vals.extend(abs(float(row[f"score_{p}"])) for p in ("A", "C", "D", "B"))
    return max(vals, default=0.0)


def max_efficiency(path: Path) -> float:
    rows = read_rows(path / "seed_results.csv")
    values = [
        abs(float(row["max_efficiency_error"]))
        for row in rows
        if row["method"] == "EXACT_CF_SHAPLEY" and row["max_efficiency_error"] not in {"", "None"}
    ]
    return max(values, default=0.0)


def main() -> int:
    primary = load_json(ART / "primary/summary.json")
    replication = load_json(ART / "replication/summary.json")
    null_paths = {
        "DESTROY_CAUSAL_LINK": ART / "null_destroy",
        "CORRELATION_ONLY": ART / "null_correlation",
        "PURE_NOISE": ART / "null_pure_noise",
    }

    predicates: dict[str, bool] = {}
    for label, payload in (("primary", primary), ("replication", replication)):
        for context in OOD_CONTEXTS:
            predicates[f"{label}_exact_rank_{context}"] = metric(payload, "EXACT_CF_SHAPLEY", context, "causal_rank_accuracy") == 1.0
            predicates[f"{label}_exact_false_mass_{context}"] = metric(payload, "EXACT_CF_SHAPLEY", context, "mean_false_credit_mass") <= 1e-12
            predicates[f"{label}_mc64_rank_{context}"] = metric(payload, "MC_CF_SHAPLEY_64", context, "causal_rank_accuracy") >= 0.95
    predicates["primary_efficiency"] = max_efficiency(ART / "primary") <= 1e-12
    predicates["replication_efficiency"] = max_efficiency(ART / "replication") <= 1e-12
    for name, path in null_paths.items():
        predicates[f"null_exact_zero_{name}"] = exact_null_max(path) <= 1e-12

    exact_keys = [key for key in predicates if "mc64" not in key]
    exact_pass = all(predicates[key] for key in exact_keys)
    approx_pass = all(value for key, value in predicates.items() if "mc64" in key)
    if not exact_pass:
        verdict = "CSCA_01_EXACT_KERNEL_NOT_REPRODUCED"
    elif not approx_pass:
        verdict = "CSCA_01_EXACT_REPRODUCED_APPROXIMATION_NOT_QUALIFIED"
    else:
        verdict = "CSCA_01_CONTROLLED_KERNEL_REPRODUCED"

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    telemetry = RESULT_DIR / "run_telemetry.jsonl"
    payload = {
        "experiment_id": "CSCA-01",
        "hypothesis_id": "H-CSCA-01",
        "scope": "controlled independent mechanism reproduction; not full-paper reproduction",
        "source_gate": load_json(REG / "rd02_pipeline_state.json")["source_gate"],
        "preregistration_sha256": sha256_file(ROOT / "experiments/csca_01/PREREGISTRATION.md"),
        "implementation_sha256": sha256_file(ROOT / "experiments/csca_01/run.py"),
        "predicates": predicates,
        "exact_pass": exact_pass,
        "approximation_pass": approx_pass,
        "verdict": verdict,
        "paper_reproduction_authority": False,
        "architecture_promotion_authority": False,
        "scale_decision": "DO_NOT_SCALE_C1_IS_DECISION_SUFFICIENT",
        "telemetry_sha256": sha256_file(telemetry),
        "remaining_uncertainty": [
            "full primary-source paper bytes/code unavailable in execution environment",
            "MC estimator is an independent finite-budget approximation, not asserted to match the paper estimator",
            "controlled synthetic SCM does not establish real-LM utility",
            "human H5 architecture integration review remains pending",
        ],
    }
    verdict_path = RESULT_DIR / "verdict.json"
    verdict_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Explicit H5 pending record prevents an autonomous model from converting a successful
    # mechanism test into architecture authority.
    h5 = HumanDecision(
        decision_id="H5-CSCA-01-PENDING",
        gate="H5_ARCHITECTURE_INTEGRATION",
        subject_id="CSCA-01",
        reviewer="UNASSIGNED_HUMAN_REVIEWER",
        reviewer_role="ADVERSARIAL_REVIEWER",
        decision="PENDING_HUMAN_REVIEW",
        rationale="Mechanism-level evidence is sealed, but source materialization and real-model utility remain unresolved; no integration authority is granted.",
        evidence_refs=(str(verdict_path.relative_to(ROOT)), "experiments/csca_01/PREREGISTRATION.md"),
        created_at="2026-08-10",
        architecture_authority=False,
    )
    write_human_decision(h5, ROOT / "research/governance")

    graph = EvidenceGraph()
    graph.add_node("S01", "Paper", gate_status=payload["source_gate"])
    graph.add_node("H-CSCA-01", "Hypothesis")
    graph.add_node("CSCA-01", "Experiment", preregistration_sha256=payload["preregistration_sha256"])
    graph.add_node("RESULT-CSCA-01", "Result", verdict=verdict, architecture_promotion_authority=False)
    graph.add_edge("S01", "DEPENDS_ON", "H-CSCA-01")
    graph.add_edge("H-CSCA-01", "IMPLEMENTED_BY", "CSCA-01")
    graph.add_edge("CSCA-01", "SUPPORTED_BY" if exact_pass else "FAILS_UNDER", "RESULT-CSCA-01")
    for null_name in null_paths:
        node = f"NULL-CSCA-01-{null_name}"
        graph.add_node(node, "NullModel")
        graph.add_edge("CSCA-01", "NULL_ATTACKED_BY", node)
    graph.write_json(REG / "rd02_evidence_graph_post_execution.json")

    state_path = REG / "rd02_pipeline_state.json"
    state = load_json(state_path)
    state.update({
        "status": "PHASE_4_COMPLETE_H5_PENDING" if exact_pass else "CSCA_01_KILLED",
        "csca_01_verdict": verdict,
        "csca_01_result": str(verdict_path.relative_to(ROOT)),
        "architecture_promotion_authority": False,
        "next": "HUMAN_H5_REVIEW_AND_REAL_MODEL_UTILITY_TEST" if exact_pass else "STORE_RUIN_AND_REFORMULATE_CAUSAL_CREDIT",
    })
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not exact_pass:
        ruin = {
            "ruin_id": "RUIN-CSCA-01",
            "hypothesis": "H-CSCA-01",
            "expected": "Exact counterfactual credit survives OOD and zero-cause nulls.",
            "observed": predicates,
            "failed_gate": "CSCA-01 exact primary predicates",
            "retest_condition": "Only after a mechanistic correction that directly addresses the failed predicate.",
            "status": "KILLED",
        }
        (ROOT / "research/ruins/RUIN-CSCA-01.json").write_text(json.dumps(ruin, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if exact_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
