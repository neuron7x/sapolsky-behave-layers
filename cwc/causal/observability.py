from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

import numpy as np

ModelName = str
ActionName = str
Outcome = Hashable


@dataclass(frozen=True, slots=True)
class PairSeparation:
    model_a: ModelName
    model_b: ModelName
    best_action: ActionName | None
    max_total_variation: float


@dataclass(frozen=True, slots=True)
class FiniteIdentifiabilityCertificate:
    state: str
    tolerance: float
    selected_actions: tuple[ActionName, ...]
    minimum_pair_separation: float
    pair_separations: tuple[PairSeparation, ...]
    unresolved_pairs: tuple[tuple[ModelName, ModelName], ...]
    causal_authority_granted: bool = False


@dataclass(frozen=True, slots=True)
class SeparatingDesign:
    state: str
    actions: tuple[ActionName, ...]
    total_cost: float | None
    certificate: FiniteIdentifiabilityCertificate


@dataclass(frozen=True, slots=True)
class LocalIdentifiabilityCertificate:
    state: str
    parameter_count: int
    observable_count: int
    numerical_rank: int
    rank_tolerance: float
    singular_values: tuple[float, ...]
    smallest_singular_value: float
    condition_number: float
    nullspace_basis: tuple[tuple[float, ...], ...]
    information_min_eigenvalue: float | None
    information_condition_number: float | None
    causal_authority_granted: bool = False


def _validate_tolerance(tolerance: float) -> float:
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and >= 0")
    return tolerance


def _normalize_law(law: Mapping[Outcome, float], *, atol: float = 1e-12) -> dict[Outcome, float]:
    if not law:
        raise ValueError("probability law must be non-empty")
    out: dict[Outcome, float] = {}
    total = 0.0
    for outcome, probability in law.items():
        p = float(probability)
        if not math.isfinite(p) or p < 0.0:
            raise ValueError("probabilities must be finite and >= 0")
        out[outcome] = p
        total += p
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=atol):
        raise ValueError(f"probabilities must sum to 1; got {total}")
    return out


def total_variation_distance(law_a: Mapping[Outcome, float], law_b: Mapping[Outcome, float]) -> float:
    a = _normalize_law(law_a)
    b = _normalize_law(law_b)
    support = set(a) | set(b)
    return 0.5 * sum(abs(a.get(y, 0.0) - b.get(y, 0.0)) for y in support)


def _validate_family(
    family: Mapping[ModelName, Mapping[ActionName, Mapping[Outcome, float]]],
) -> tuple[tuple[ModelName, ...], tuple[ActionName, ...], dict[ModelName, dict[ActionName, dict[Outcome, float]]]]:
    if len(family) < 2:
        raise ValueError("at least two candidate models are required")
    models = tuple(sorted(str(name) for name in family))
    actions: set[str] | None = None
    normalized: dict[str, dict[str, dict[Outcome, float]]] = {}
    for model in models:
        raw_actions = family[model]
        if not raw_actions:
            raise ValueError(f"model {model!r} has no interventions")
        model_actions = {str(action) for action in raw_actions}
        if actions is None:
            actions = model_actions
        elif model_actions != actions:
            missing = sorted((actions or set()) - model_actions)
            extra = sorted(model_actions - (actions or set()))
            raise ValueError(
                f"all models must define the same actions; model={model!r} missing={missing} extra={extra}"
            )
        normalized[model] = {str(action): _normalize_law(raw_actions[action]) for action in raw_actions}
    assert actions is not None
    return models, tuple(sorted(actions)), normalized


def finite_identifiability_certificate(
    family: Mapping[ModelName, Mapping[ActionName, Mapping[Outcome, float]]],
    *,
    selected_actions: Sequence[ActionName] | None = None,
    tolerance: float = 1e-12,
) -> FiniteIdentifiabilityCertificate:
    tolerance = _validate_tolerance(tolerance)
    models, all_actions, normalized = _validate_family(family)
    if selected_actions is None:
        actions = all_actions
    else:
        actions = tuple(sorted({str(a) for a in selected_actions}))
        if not actions:
            raise ValueError("selected_actions must be non-empty")
        unknown = sorted(set(actions) - set(all_actions))
        if unknown:
            raise ValueError(f"unknown actions: {unknown}")

    rows: list[PairSeparation] = []
    unresolved: list[tuple[str, str]] = []
    for model_a, model_b in combinations(models, 2):
        action_scores = [
            (
                action,
                total_variation_distance(normalized[model_a][action], normalized[model_b][action]),
            )
            for action in actions
        ]
        best_action, max_tv = max(action_scores, key=lambda item: (item[1], item[0]))
        if max_tv <= tolerance:
            unresolved.append((model_a, model_b))
            best: str | None = None
        else:
            best = best_action
        rows.append(
            PairSeparation(
                model_a=model_a,
                model_b=model_b,
                best_action=best,
                max_total_variation=float(max_tv),
            )
        )

    minimum = min(row.max_total_variation for row in rows)
    state = (
        "FINITE_IDENTIFIABLE_UNDER_DECLARED_CHANNEL" if not unresolved else "NOT_IDENTIFIABLE_UNDER_DECLARED_CHANNEL"
    )
    return FiniteIdentifiabilityCertificate(
        state=state,
        tolerance=tolerance,
        selected_actions=actions,
        minimum_pair_separation=float(minimum),
        pair_separations=tuple(rows),
        unresolved_pairs=tuple(unresolved),
    )


def minimum_cost_separating_design(
    family: Mapping[ModelName, Mapping[ActionName, Mapping[Outcome, float]]],
    *,
    costs: Mapping[ActionName, float],
    tolerance: float = 1e-12,
) -> SeparatingDesign:
    tolerance = _validate_tolerance(tolerance)
    _models, all_actions, _normalized = _validate_family(family)
    if set(costs) != set(all_actions):
        missing = sorted(set(all_actions) - set(costs))
        extra = sorted(set(costs) - set(all_actions))
        raise ValueError(f"cost keys must equal action keys; missing={missing} extra={extra}")
    validated_costs: dict[str, float] = {}
    for action in all_actions:
        cost = float(costs[action])
        if not math.isfinite(cost) or cost <= 0:
            raise ValueError("intervention costs must be finite and > 0")
        validated_costs[action] = cost

    full = finite_identifiability_certificate(family, tolerance=tolerance)
    if full.unresolved_pairs:
        return SeparatingDesign(
            state="NOT_IDENTIFIABLE_UNDER_DECLARED_CHANNEL",
            actions=(),
            total_cost=None,
            certificate=full,
        )

    candidates: list[tuple[float, int, tuple[str, ...], FiniteIdentifiabilityCertificate]] = []
    for size in range(1, len(all_actions) + 1):
        for subset in combinations(all_actions, size):
            certificate = finite_identifiability_certificate(family, selected_actions=subset, tolerance=tolerance)
            if certificate.unresolved_pairs:
                continue
            total_cost = sum(validated_costs[action] for action in subset)
            candidates.append((float(total_cost), size, subset, certificate))
    if not candidates:
        raise RuntimeError("full action set was identifiable but no separating subset was found")
    total_cost, _size, actions, certificate = min(candidates, key=lambda row: row[:3])
    return SeparatingDesign(
        state="FINITE_IDENTIFIABLE_UNDER_DECLARED_CHANNEL",
        actions=actions,
        total_cost=total_cost,
        certificate=certificate,
    )


def _svd_rank_tolerance(matrix: np.ndarray, singular_values: np.ndarray) -> float:
    if singular_values.size == 0:
        return 0.0
    return float(max(matrix.shape) * np.finfo(np.float64).eps * singular_values[0])


def local_first_order_identifiability(
    jacobian: Sequence[Sequence[float]] | np.ndarray,
    *,
    covariance: Sequence[Sequence[float]] | np.ndarray | None = None,
    rank_tolerance: float | None = None,
) -> LocalIdentifiabilityCertificate:
    J = np.asarray(jacobian, dtype=np.float64)
    if J.ndim != 2 or J.shape[0] < 1 or J.shape[1] < 1:
        raise ValueError("jacobian must be a non-empty 2D matrix")
    if not np.all(np.isfinite(J)):
        raise ValueError("jacobian must be finite")

    _u, singular_values, vh = np.linalg.svd(J, full_matrices=True)
    default_tol = _svd_rank_tolerance(J, singular_values)
    tolerance = default_tol if rank_tolerance is None else _validate_tolerance(rank_tolerance)
    rank = int(np.sum(singular_values > tolerance))
    parameter_count = int(J.shape[1])
    observable_count = int(J.shape[0])
    full_column_rank = rank == parameter_count

    if rank < parameter_count:
        null_basis_arr = vh[rank:, :]
        nullspace = tuple(tuple(float(x) for x in row) for row in null_basis_arr)
    else:
        nullspace = ()

    smallest = float(singular_values[-1]) if singular_values.size else 0.0
    condition = float("inf") if smallest <= 0 else float(singular_values[0] / smallest)

    info_min: float | None = None
    info_condition: float | None = None
    if covariance is not None:
        sigma = np.asarray(covariance, dtype=np.float64)
        if sigma.shape != (observable_count, observable_count):
            raise ValueError("covariance shape must match observable dimension")
        if not np.all(np.isfinite(sigma)) or not np.allclose(sigma, sigma.T, atol=1e-12, rtol=0.0):
            raise ValueError("covariance must be finite and symmetric")
        eig_sigma = np.linalg.eigvalsh(sigma)
        if np.any(eig_sigma <= 0):
            raise ValueError("covariance must be positive definite")
        whitened = np.linalg.solve(np.linalg.cholesky(sigma), J)
        information = whitened.T @ whitened
        eig_info = np.linalg.eigvalsh(information)
        info_min = float(eig_info[0])
        info_max = float(eig_info[-1])
        info_condition = float("inf") if info_min <= 0 else float(info_max / info_min)

    state = "LOCAL_FIRST_ORDER_IDENTIFIABLE" if full_column_rank else "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE"
    return LocalIdentifiabilityCertificate(
        state=state,
        parameter_count=parameter_count,
        observable_count=observable_count,
        numerical_rank=rank,
        rank_tolerance=float(tolerance),
        singular_values=tuple(float(x) for x in singular_values),
        smallest_singular_value=smallest,
        condition_number=condition,
        nullspace_basis=nullspace,
        information_min_eigenvalue=info_min,
        information_condition_number=info_condition,
    )
