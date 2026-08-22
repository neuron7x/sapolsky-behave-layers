from __future__ import annotations

from collections.abc import Mapping, Sequence

from cwc.governance.budget import BudgetLedger
from cwc.governance.compute_value import VOCAuthority, ValueOfComputationEstimate
from cwc.governance.contracts import CandidateOperation, ComputeDecision, ComputeDirective, RiskClass
from cwc.governance.statistical_authority import StatisticalInferenceCertificate


class ComputeGovernor:
    """Fail-closed admission authority for the next cognition/compute operation."""

    @staticmethod
    def select(
        *,
        operations: Sequence[CandidateOperation],
        estimates: Mapping[str, ValueOfComputationEstimate],
        budget: BudgetLedger,
        decision_digest: str,
        risk_class: RiskClass = RiskClass.NORMAL,
        safety_margin: float = 0.0,
        require_robust_estimate: bool = False,
        statistical_certificates: Mapping[str, StatisticalInferenceCertificate] | None = None,
        production_strict_math: bool = False,
    ) -> ComputeDecision:
        if safety_margin < 0:
            raise ValueError("safety_margin must be >= 0")
        candidates: list[tuple[float, str, CandidateOperation, ValueOfComputationEstimate]] = []
        certs = statistical_certificates or {}
        for operation in operations:
            estimate = estimates.get(operation.operation_id)
            if estimate is None or estimate.operation_id != operation.operation_id:
                continue
            if require_robust_estimate and estimate.authority is not VOCAuthority.ROBUST_AMBIGUITY_BOUND:
                continue
            if production_strict_math:
                cert = certs.get(operation.operation_id)
                if cert is None or not cert.admits(estimate):
                    continue
            if abs(estimate.total_cost - operation.estimated_cost) > 1e-12:
                continue
            if not budget.can_spend(
                tokens=operation.token_cost,
                money=operation.money_cost,
                time=operation.time_cost,
                gpu=operation.gpu_cost,
                emergency=operation.directive in {ComputeDirective.HUMAN_ESCALATE, ComputeDirective.ABSTAIN},
            ):
                continue
            threshold = safety_margin
            if risk_class is RiskClass.CATASTROPHIC:
                threshold = max(threshold, 1e-12)
            if estimate.lower_bound > threshold:
                candidates.append((estimate.lower_bound, operation.operation_id, operation, estimate))

        if not candidates:
            return ComputeDecision(
                directive=ComputeDirective.STOP,
                operation_id=None,
                reason_code="STOP_NO_POSITIVE_CONSERVATIVE_VOC_OR_BUDGET",
                predicted_voc=None,
                predicted_voc_lower=None,
                predicted_voc_upper=None,
                budget_digest=budget.digest,
                decision_digest=decision_digest,
            )

        _, _, operation, estimate = max(candidates, key=lambda item: (item[0], -item[2].estimated_cost, item[1]))
        return ComputeDecision(
            directive=operation.directive,
            operation_id=operation.operation_id,
            reason_code="ADMIT_MAX_LOWER_BOUND_VOC_STRICT_MATH" if production_strict_math else "ADMIT_MAX_LOWER_BOUND_VOC",
            predicted_voc=estimate.voc,
            predicted_voc_lower=estimate.lower_bound,
            predicted_voc_upper=estimate.upper_bound,
            budget_digest=budget.digest,
            decision_digest=decision_digest,
        )
