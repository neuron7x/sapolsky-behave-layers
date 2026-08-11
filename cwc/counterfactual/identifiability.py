from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from cwc.causal.observability import LocalIdentifiabilityCertificate, local_first_order_identifiability
from cwc.counterfactual.model import counterfactual_design_matrix, counterfactual_terms


@dataclass(frozen=True, slots=True)
class CounterfactualBasisIdentifiability:
    family: str
    term_names: tuple[str, ...]
    rows: int
    certificate: LocalIdentifiabilityCertificate


def certify_counterfactual_basis(
    family: str,
    rows: Sequence[Mapping[str, float]],
    *,
    rank_tolerance: float | None = None,
) -> CounterfactualBasisIdentifiability:
    if not rows:
        raise ValueError("rows must be non-empty")
    terms = counterfactual_terms(family)
    matrix = counterfactual_design_matrix(rows, terms)
    certificate = local_first_order_identifiability(
        matrix, rank_tolerance=rank_tolerance
    )
    return CounterfactualBasisIdentifiability(
        family=family,
        term_names=tuple(term.name for term in terms),
        rows=len(rows),
        certificate=certificate,
    )
