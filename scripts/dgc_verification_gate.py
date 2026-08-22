"""Fail-closed verification and adversarial checks for the DGC governance layer."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

from cwc.governance.budget import BudgetLedger
from cwc.governance.certificate import DGCExecutionCertificate, StopReason
from cwc.governance.compute_governor import ComputeGovernor
from cwc.governance.compute_value import estimate_voc
from cwc.governance.contracts import CandidateOperation, ComputeDirective, Perturbation
from cwc.governance.loop_guard import LoopGuard
from cwc.governance.perturbation_policy import InterventionType, PerturbationTemplate
from cwc.governance.scheduler import ProviderLimits, SchedulerState, acquire
from cwc.governance.change_detection import bounded_conditional_mean_change_eprocess
from cwc.governance.restricted_sampling import certify_restricted_adaptive_policy
from cwc.governance.sampling_trace import SamplingSelectionCommit, certify_restricted_sampling_trace
from cwc.governance.covariate_shift import target_mean_lcb_under_covariate_shift
from cwc.governance.transport_geometry import certify_weighted_l1_transport_geometry
from cwc.governance.metareasoning import MetaOperation, MetaTransition
from cwc.governance.metareasoning_branch_bound import certify_meta_action_with_transition_bounds
from experiments.dgc_02_finance.analysis import evaluate_financial_gate

from cwc.governance.sequential import (
    SamplingMode,
    SequentialSamplingContract,
    stitched_hoeffding_confidence_sequence,
)

ROOT = Path(__file__).resolve().parents[1]
DEV_ARTIFACT = ROOT / "artifacts/dgc-01-dev"
FALSIFICATION_ARTIFACT = ROOT / "artifacts/dgc-01-falsification/verdict.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_fault_injections() -> dict[str, bool]:
    killed: dict[str, bool] = {}

    try:
        estimate_voc(
            operation_id="nan", gross_value=math.nan, total_cost=1,
            gross_lower=0, gross_upper=2, method="attack",
        )
        killed["DGC_SCORE_NAN"] = False
    except ValueError:
        killed["DGC_SCORE_NAN"] = True

    budget = BudgetLedger(hard_tokens=1, hard_money=1, hard_time=1)
    try:
        budget.spend(tokens=2)
        killed["DGC_BUDGET_BYPASS"] = False
    except RuntimeError:
        killed["DGC_BUDGET_BYPASS"] = True

    op = CandidateOperation("fake-cost", ComputeDirective.LOCAL_PROBE, estimated_cost=2.0)
    est = estimate_voc(
        operation_id="fake-cost", gross_value=10, total_cost=1.0,
        gross_lower=9, gross_upper=11, method="attack",
    )
    decision = ComputeGovernor.select(
        operations=[op], estimates={op.operation_id: est},
        budget=BudgetLedger(10, 10, 10), decision_digest="d",
    )
    killed["DGC_FAKE_COST"] = decision.directive is ComputeDirective.STOP

    p1 = Perturbation("p1", "x", "0", "1", "PARAMETER_SHIFT", "attack", 1.0)
    p2 = Perturbation("p2", "x", "0", "2", "PARAMETER_SHIFT", "attack", 1.0)
    killed["DGC_COUNTERMODEL_DROP"] = p1.digest != p2.digest

    try:
        PerturbationTemplate("x", ("1",), InterventionType.CAUSAL_INTERVENTION, "attack", 1.0)
        killed["DGC_CAUSAL_TEXT_ONLY"] = False
    except ValueError:
        killed["DGC_CAUSAL_TEXT_ONLY"] = True

    contract = SequentialSamplingContract(SamplingMode.ADAPTIVE, 0.0, 1.0, 0.05)
    try:
        stitched_hoeffding_confidence_sequence([0.5], contract=contract)
        killed["DGC_INVALID_OPTIONAL_STOPPING"] = False
    except ValueError:
        killed["DGC_INVALID_OPTIONAL_STOPPING"] = True

    cert = DGCExecutionCertificate(
        decision_id="d", selected_action="A", decision_gradient_digest="dg",
        compute_spent={"tokens": 1}, stop_reason=StopReason.DECISION_STABLE,
        world_set_digest="w", utility_digest="u", governor_digest="g",
        budget_before_digest="b0", budget_after_digest="b1", evidence_ids=("E1",),
    )
    killed["DGC_DECISION_DIGEST_TAMPER"] = not replace(cert, selected_action="B").verify()
    killed["DGC_UTILITY_MUTATION"] = not replace(cert, utility_digest="u2").verify()

    guard = LoopGuard(max_steps=1).advance()
    try:
        guard.advance()
        killed["DGC_UNBOUNDED_RECURSION"] = False
    except RuntimeError:
        killed["DGC_UNBOUNDED_RECURSION"] = True

    limits = ProviderLimits(max_concurrency=1, bucket_capacity=1.0, refill_per_second=0.0)
    first = acquire(SchedulerState(0, 1.0, 0.0), limits, now=0.0)
    retry = acquire(first.state, limits, now=0.0)
    killed["DGC_PROVIDER_RETRY_STORM"] = first.granted and not retry.granted

    high_saving_bad_quality = evaluate_financial_gate(
        reference_costs=[0.1] * 5000, dgc_core_costs=[0.01] * 5000,
        reference_losses=[0.0] * 5000, dgc_losses=[0.1] * 5000,
        governance_overhead_per_task=0.0, max_reference_cost=0.1,
        max_dgc_core_cost=0.01, max_loss=0.1,
    )
    killed["DGC_FINANCIAL_QUALITY_GAMING"] = not high_saving_bad_quality.threshold_met

    hidden_overhead = evaluate_financial_gate(
        reference_costs=[0.1] * 5000, dgc_core_costs=[0.05] * 5000,
        reference_losses=[0.0] * 5000, dgc_losses=[0.0] * 5000,
        governance_overhead_per_task=0.03, max_reference_cost=0.1,
        max_dgc_core_cost=0.05,
    )
    killed["DGC_FINANCIAL_OVERHEAD_HIDE"] = not hidden_overhead.threshold_met

    # Mathematical hardening v2d: these attacks must fail closed in the canonical DGC gate.
    try:
        bounded_conditional_mean_change_eprocess(
            [0.9], lower=0, upper=1, baseline_mean=0.5, tolerance=0.05,
            alpha=0.05, lambdas=[10.0], predictable_lambda_attested=False,
        )
        killed["DGC_V2D_OUTCOME_DEPENDENT_LAMBDA"] = False
    except ValueError:
        killed["DGC_V2D_OUTCOME_DEPENDENT_LAMBDA"] = True

    policy = certify_restricted_adaptive_policy(
        target_distribution={"a": 0.5, "b": 0.5}, minimum_propensity=0.2
    )
    try:
        certify_restricted_sampling_trace(
            policy,
            [SamplingSelectionCommit("a", 0.3, 5, 4, policy.policy_digest)],
            telemetry_chain_verified=True,
        )
        killed["DGC_V2D_POST_OUTCOME_PROPENSITY"] = False
    except ValueError:
        killed["DGC_V2D_POST_OUTCOME_PROPENSITY"] = True

    try:
        target_mean_lcb_under_covariate_shift(
            [1.0], [9.0], lower=0, upper=1, delta=0.05,
            max_density_ratio=2.0, ratio_induced_mean_error_budget=0.0,
            weight_authority_digest="w",
        )
        killed["DGC_V2D_UNBOUNDED_SHIFT_WEIGHT"] = False
    except ValueError:
        killed["DGC_V2D_UNBOUNDED_SHIFT_WEIGHT"] = True

    try:
        certify_weighted_l1_transport_geometry(
            feature_weights={"x": 0.0}, coordinate_lipschitz={"x": 1.0},
            feature_authority_digest="f",
        )
        killed["DGC_V2D_DEGENERATE_GEOMETRY"] = False
    except ValueError:
        killed["DGC_V2D_DEGENERATE_GEOMETRY"] = True

    try:
        certify_meta_action_with_transition_bounds(
            stop_value=0.0,
            operations=[MetaOperation("c", 0.0, (MetaTransition("s", 1.0),))],
            next_state_stop_values={"s": 1.0},
            next_state_value_upper={"s": 0.5},
            upper_bound_authority_digest="fake",
        )
        killed["DGC_V2D_FAKE_META_UPPER_BOUND"] = False
    except ValueError:
        killed["DGC_V2D_FAKE_META_UPPER_BOUND"] = True
    return killed


def validate() -> list[str]:
    errors: list[str] = []
    attacks = run_fault_injections()
    errors.extend(f"attack survived: {name}" for name, caught in attacks.items() if not caught)

    verdict_path = DEV_ARTIFACT / "verdict.json"
    manifest_path = DEV_ARTIFACT / "manifest.json"
    if not verdict_path.is_file() or not manifest_path.is_file():
        errors.append("development oracle evidence bundle missing")
        return errors

    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    if verdict.get("status") != "DEVELOPMENT_ONLY_NOT_CONFIRMATORY":
        errors.append("development verdict authority changed")
    if verdict.get("claim_promotion") != "PROHIBITED":
        errors.append("development evidence illegally permits claim promotion")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        path = DEV_ARTIFACT / name
        if not path.is_file() or _sha256(path) != expected:
            errors.append(f"development artifact hash mismatch: {name}")

    if not FALSIFICATION_ARTIFACT.is_file():
        errors.append("DGC misspecification falsification artifact missing")
    else:
        falsifier = json.loads(FALSIFICATION_ARTIFACT.read_text(encoding="utf-8"))
        if falsifier.get("status") != "COUNTEREXAMPLE_FOUND":
            errors.append("DGC misspecification boundary not demonstrated")

    claim_registry = json.loads((ROOT / "claim_registry.json").read_text(encoding="utf-8"))
    claims = {c["claim_id"]: c for c in claim_registry.get("claims", [])}
    dgc_claim = claims.get("CWC-DGC-H1")
    if dgc_claim is not None and dgc_claim.get("status") != "NOT_TESTED":
        errors.append("CWC-DGC-H1 promoted by development-only evidence")
    return errors


def main() -> int:
    attacks = run_fault_injections()
    for name, caught in sorted(attacks.items()):
        print(f"DGC-ATTACK: {'KILLED' if caught else 'SURVIVED'} {name}")
    errors = validate()
    if errors:
        for error in errors:
            print(f"DGC-GATE: FAIL {error}")
        return 1
    print(f"DGC-GATE: PASS ({len(attacks)}/{len(attacks)} injected faults killed; dev authority non-promoting)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
