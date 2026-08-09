"""Fail-closed synthesis gate for CWC-FRACTAL-ADV-01..03.

This gate derives narrow implementation/evidence claims from sealed diagnostic artifacts. It never
confers VIA authority and never upgrades the legacy "fractal cognition" terminology into a scientific
capability claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "artifacts" / "fractal-adversarial-v1"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"artifact must be JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def derive(evidence_dir: Path) -> dict[str, Any]:
    required = {
        "synthetic": evidence_dir / "synthetic_controls.json",
        "replication": evidence_dir / "replication_audit.json",
        "execution": evidence_dir / "execution_reality_matrix.json",
        "topology": evidence_dir / "topology_semantics.json",
        "estimators": evidence_dir / "estimator_calibration.json",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise ValueError(f"missing evidence: {missing}")
    docs = {name: _load(path) for name, path in required.items()}

    synthetic_ok = docs["synthetic"].get("calibration_pass") is True
    replication = docs["replication"]
    multiscale_replication_supported = (
        synthetic_ok
        and replication.get("replication_veto_triggered") is False
        and int(replication.get("variable_trace_pass_count", 0)) >= 2
    )

    execution = docs["execution"]
    physical_skip_supported = not (
        int(execution.get("active_depth_gate_changed_trials", 0)) > 0
        and int(execution.get("active_depth_physical_skip_successes", -1)) == 0
        and execution.get("verdict", {}).get("active_depth") == "SEMANTIC_GATE_ONLY"
    )
    attention_governor_supported = not (
        int(execution.get("attention_guard_trials", 0)) > 0
        and int(execution.get("attention_executed_before_guard_trials", -1))
        == int(execution.get("attention_guard_trials", 0))
    )
    active_expert_governor_supported = int(execution.get("max_active_experts_route_effects", 0)) > 0
    memory_gate_pre_retrieval = execution.get("memory_read_received_all_query_rows") is False

    topology = docs["topology"]
    graph_distance_fractality_supported = not (
        topology.get("exact_global1_formula_all_match") is True
        and topology.get("undirected_diameter_le_2_for_scaling_range") is True
    )

    estimators = docs["estimators"]
    estimator_calibration_complete = (
        int(estimators.get("replicates_per_cell", 0)) == 5000
        and int(estimators.get("total_simulated_series", 0)) == 60000
        and estimators.get("verdict") == "SHORT_SERIES_FRACTAL_METRICS_DIAGNOSTIC_ONLY"
    )
    estimator_claim_authorized = False

    claims = {
        "synthetic_statistical_gate_calibrated": synthetic_ok,
        "multiscale_replication_supported": multiscale_replication_supported,
        "physical_conditional_execution_supported": physical_skip_supported,
        "attention_budget_is_preexecution_governor": attention_governor_supported,
        "max_active_experts_is_effective_governor_above_top_k": active_expert_governor_supported,
        "controller_memory_gate_precedes_retrieval_work": memory_gate_pre_retrieval,
        "graph_distance_fractality_supported": graph_distance_fractality_supported,
        "short_series_estimator_calibration_complete": estimator_calibration_complete,
        "short_series_fractal_estimators_claim_authorized": estimator_claim_authorized,
    }
    negative_boundaries = [
        "multiscale_replication_supported",
        "physical_conditional_execution_supported",
        "attention_budget_is_preexecution_governor",
        "max_active_experts_is_effective_governor_above_top_k",
        "controller_memory_gate_precedes_retrieval_work",
        "graph_distance_fractality_supported",
        "short_series_fractal_estimators_claim_authorized",
    ]
    all_expected_boundaries_negative = all(claims[name] is False for name in negative_boundaries)
    programme_verdict = (
        "ADVERSARIAL_BOUNDARIES_ESTABLISHED_NO_ASCENSION"
        if synthetic_ok and estimator_calibration_complete and all_expected_boundaries_negative
        else "ADVERSARIAL_PROGRAMME_INCOMPLETE_OR_CONTRADICTORY"
    )
    return {
        "schema_version": "cwc.fractal_adversarial.verdict.v1",
        "programme_verdict": programme_verdict,
        "claims": claims,
        "counts": {
            "fresh_trace_records": 408,
            "prespecified_trace_seeds": 3,
            "variable_trace_passes": int(replication.get("variable_trace_pass_count", 0)),
            "variable_trace_total": int(replication.get("variable_trace_total", 0)),
            "fixed_shape_identifiable": int(replication.get("fixed_shape_identifiable_count", 0)),
            "fixed_shape_total": int(replication.get("fixed_shape_total", 0)),
            "synthetic_null_iterations_per_control": int(
                docs["synthetic"].get("results", {}).get("endogenous", {}).get("null_evaluation", {}).get("iterations", 0)
            ),
            "pooled_replication_null_iterations": int(
                replication.get("pooled_null_diagnostic", {}).get("iterations", 0)
            ),
            "estimator_simulated_series": int(estimators.get("total_simulated_series", 0)),
            "execution_matrix_rows": int(execution.get("matrix_row_count", 0)),
            "execution_gate_changed_trials": int(execution.get("active_depth_gate_changed_trials", 0)),
            "execution_physical_skip_successes": int(execution.get("active_depth_physical_skip_successes", 0)),
            "topology_sequence_lengths": len(topology.get("lengths", [])),
        },
        "diagnostics": {
            "pooled_replication_observed": replication.get("pooled_null_diagnostic", {}).get("observed"),
            "pooled_replication_familywise_p": replication.get("pooled_null_diagnostic", {}).get("familywise_p_value"),
            "pooled_replication_delta_vs_max_null_mean": replication.get("pooled_null_diagnostic", {}).get("delta_vs_max_null_mean"),
            "topology_edge_count_loglog_slope": topology.get("edge_count_loglog_slope"),
            "topology_density_loglog_slope": topology.get("density_loglog_slope"),
            "iid_vs_ar1_hurst_95_interval_overlap": estimators.get("iid_vs_ar1_hurst_95_interval_overlap"),
        },
        "evidence_hashes": {name: _sha256(path) for name, path in required.items()},
        "claim_boundary": (
            "The programme establishes narrow evidence and implementation boundaries only. It does not "
            "show absence of all multiscale organization, does not establish or refute intelligence in "
            "general, and does not provide VIA-V2+ authority."
        ),
        "scientific_ascension_authority": False,
        "via_authority": False,
    }


def audit(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("programme_verdict") != "ADVERSARIAL_BOUNDARIES_ESTABLISHED_NO_ASCENSION":
        errors.append(f"unexpected programme verdict: {payload.get('programme_verdict')}")
    claims = payload.get("claims", {})
    if claims.get("synthetic_statistical_gate_calibrated") is not True:
        errors.append("synthetic statistical gate calibration did not pass")
    if claims.get("short_series_estimator_calibration_complete") is not True:
        errors.append("estimator calibration incomplete")
    for name in (
        "multiscale_replication_supported",
        "physical_conditional_execution_supported",
        "attention_budget_is_preexecution_governor",
        "max_active_experts_is_effective_governor_above_top_k",
        "controller_memory_gate_precedes_retrieval_work",
        "graph_distance_fractality_supported",
        "short_series_fractal_estimators_claim_authorized",
    ):
        if claims.get(name) is not False:
            errors.append(f"negative boundary not established for {name}: {claims.get(name)!r}")
    if payload.get("via_authority") is not False:
        errors.append("VIA authority must remain false")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    payload = derive(args.evidence_dir)
    errors = audit(payload)
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            print(f"FRACTAL-ADVERSARIAL FAIL: {error}")
        return 1
    print(
        "FRACTAL-ADVERSARIAL PASS: evidence boundaries are coherent; "
        "no scientific/VIA ascension authorized."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
