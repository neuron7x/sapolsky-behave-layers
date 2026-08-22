from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IdentifiabilityStatus(str, Enum):
    CERTIFIED_FOR_DECLARED_QUERY = "CERTIFIED_FOR_DECLARED_QUERY"
    NOT_IDENTIFIED = "NOT_IDENTIFIED"


@dataclass(frozen=True, slots=True)
class CausalIdentifiabilityCertificate:
    status: IdentifiabilityStatus
    structural_model_digest: str | None
    intervention_declared: bool
    outcome_mapping_declared: bool
    no_hidden_confounding_asserted: bool
    transport_assumptions_declared: bool
    reason: str


def certify_declared_interventional_query(
    *,
    structural_model_digest: str | None,
    intervention_declared: bool,
    outcome_mapping_declared: bool,
    no_hidden_confounding_asserted: bool,
    transport_required: bool,
    transport_assumptions_declared: bool,
) -> CausalIdentifiabilityCertificate:
    """Fail-closed obligation checker, not a general do-calculus solver."""
    digest_ok = bool(structural_model_digest and structural_model_digest.strip())
    transport_ok = (not transport_required) or transport_assumptions_declared
    ok = all((digest_ok, intervention_declared, outcome_mapping_declared, no_hidden_confounding_asserted, transport_ok))
    reason = "DECLARED_QUERY_OBLIGATIONS_SATISFIED" if ok else "CAUSAL_IDENTIFIABILITY_OBLIGATIONS_INCOMPLETE"
    return CausalIdentifiabilityCertificate(
        status=IdentifiabilityStatus.CERTIFIED_FOR_DECLARED_QUERY if ok else IdentifiabilityStatus.NOT_IDENTIFIED,
        structural_model_digest=structural_model_digest,
        intervention_declared=bool(intervention_declared),
        outcome_mapping_declared=bool(outcome_mapping_declared),
        no_hidden_confounding_asserted=bool(no_hidden_confounding_asserted),
        transport_assumptions_declared=bool(transport_assumptions_declared),
        reason=reason,
    )
