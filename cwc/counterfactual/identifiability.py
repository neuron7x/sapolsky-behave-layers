from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

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
    certificate = local_first_order_identifiability(matrix, rank_tolerance=rank_tolerance)
    return CounterfactualBasisIdentifiability(
        family=family,
        term_names=tuple(term.name for term in terms),
        rows=len(rows),
        certificate=certificate,
    )


@dataclass(frozen=True, slots=True)
class BasisOrthogonalityAudit:
    family: str
    rows: int
    columns: int
    expected_diagonal: float
    minimum_diagonal: float
    maximum_diagonal: float
    maximum_absolute_off_diagonal: float
    gram_condition_number: float
    orthogonal_equal_norm: bool


def audit_counterfactual_basis_orthogonality(
    family: str,
    rows: Sequence[Mapping[str, float]],
    *,
    tolerance: float = 1e-12,
) -> BasisOrthogonalityAudit:
    if not rows:
        raise ValueError("rows must be non-empty")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and >= 0")
    terms = counterfactual_terms(family)
    matrix = counterfactual_design_matrix(rows, terms)
    gram = matrix.T @ matrix
    diagonal = np.diag(gram)
    off = gram - np.diag(diagonal)
    expected = float(len(rows))
    orthogonal_equal_norm = bool(
        np.allclose(diagonal, expected, atol=tolerance, rtol=0.0) and np.allclose(off, 0.0, atol=tolerance, rtol=0.0)
    )
    singular = np.linalg.svd(gram, compute_uv=False)
    smallest = float(singular[-1])
    condition = float("inf") if smallest <= 0 else float(singular[0] / smallest)
    return BasisOrthogonalityAudit(
        family=family,
        rows=len(rows),
        columns=matrix.shape[1],
        expected_diagonal=expected,
        minimum_diagonal=float(np.min(diagonal)),
        maximum_diagonal=float(np.max(diagonal)),
        maximum_absolute_off_diagonal=float(np.max(np.abs(off))) if off.size else 0.0,
        gram_condition_number=condition,
        orthogonal_equal_norm=orthogonal_equal_norm,
    )
