from __future__ import annotations

import hashlib
import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

CANDIDATES = ("A", "C", "D", "B")


@dataclass(frozen=True, slots=True)
class FeatureTerm:
    name: str
    players: tuple[str, ...] = ()
    context_power: int = 0

    def evaluate(self, row: Mapping[str, float]) -> float:
        value = float(row.get("context", 1.0)) ** self.context_power
        for player in self.players:
            value *= float(row[player])
        return value


@dataclass(frozen=True, slots=True)
class FittedCounterfactualModel:
    model_id: str
    family: str
    version: str
    terms: tuple[FeatureTerm, ...]
    coefficients: tuple[float, ...]
    train_config_counts: tuple[tuple[str, int], ...]
    train_rows: int
    fault: str = "NONE"

    def predict_one(self, row: Mapping[str, float]) -> float:
        return float(sum(c * t.evaluate(row) for c, t in zip(self.coefficients, self.terms, strict=True)))

    def predict(self, rows: Sequence[Mapping[str, float]]) -> np.ndarray:
        matrix = _design(rows, self.terms)
        return matrix @ np.asarray(self.coefficients, dtype=float)

    def exact_shapley_one(self, row: Mapping[str, float]) -> dict[str, float]:
        """Exact Shapley under independent symmetric {-1,+1} candidate baselines.

        Every fitted basis term is a multilinear monomial in candidate variables, optionally
        multiplied by context. A monomial involving k candidate players contributes its full
        factual term equally (1/k) to those k players. Terms with no candidate player have
        zero credit. This is algebraically identical to exhaustive coalition Shapley for the
        symmetric zero-mean intervention baseline and avoids Monte-Carlo noise.
        """
        out = dict.fromkeys(CANDIDATES, 0.0)
        for coefficient, term in zip(self.coefficients, self.terms, strict=True):
            if not term.players:
                continue
            factual = coefficient * term.evaluate(row)
            share = factual / len(term.players)
            for player in term.players:
                out[player] += share
        return out

    def mean_credit(self, rows: Sequence[Mapping[str, float]]) -> tuple[dict[str, float], dict[str, float]]:
        if not rows:
            return (dict.fromkeys(CANDIDATES, 0.0), dict.fromkeys(CANDIDATES, 0.0))
        phi = np.zeros((len(rows), len(CANDIDATES)), dtype=float)
        for coefficient, term in zip(self.coefficients, self.terms, strict=True):
            if not term.players:
                continue
            values = np.fromiter((term.evaluate(row) for row in rows), dtype=float, count=len(rows))
            share = coefficient * values / len(term.players)
            for player in term.players:
                phi[:, CANDIDATES.index(player)] += share
        return (
            {name: float(np.mean(np.abs(phi[:, i]))) for i, name in enumerate(CANDIDATES)},
            {name: float(np.mean(phi[:, i])) for i, name in enumerate(CANDIDATES)},
        )

    def intervention_effect(self, row: Mapping[str, float], candidate: str) -> float:
        if candidate not in CANDIDATES:
            raise KeyError(candidate)
        plus = dict(row)
        minus = dict(row)
        plus[candidate] = 1.0
        minus[candidate] = -1.0
        return 0.5 * (self.predict_one(plus) - self.predict_one(minus))

    def intervention_effects(self, rows: Sequence[Mapping[str, float]], candidates: Sequence[str]) -> np.ndarray:
        if len(rows) != len(candidates):
            raise ValueError("rows/candidates length mismatch")
        out = np.zeros(len(rows), dtype=float)
        for idx, (row, candidate) in enumerate(zip(rows, candidates, strict=True)):
            if candidate not in CANDIDATES:
                raise KeyError(candidate)
            total = 0.0
            for coefficient, term in zip(self.coefficients, self.terms, strict=True):
                if candidate not in term.players:
                    continue
                value = float(row.get("context", 1.0)) ** term.context_power
                for player in term.players:
                    if player != candidate:
                        value *= float(row[player])
                total += coefficient * value
            out[idx] = total
        return out

    def config_probability(self, row: Mapping[str, float]) -> float:
        key = config_key(row)
        counts = dict(self.train_config_counts)
        # Laplace smoothing over 2^5 candidate+context binary states.
        return (counts.get(key, 0) + 1.0) / (self.train_rows + 32.0)


def config_key(row: Mapping[str, float]) -> str:
    vals = [int(float(row[name]) > 0) for name in (*CANDIDATES, "context")]
    return "".join(map(str, vals))


def _terms(family: str) -> tuple[FeatureTerm, ...]:
    base = [FeatureTerm("intercept")]
    base.extend(FeatureTerm(name, (name,)) for name in CANDIDATES)
    base.append(FeatureTerm("context", (), 1))
    if family in {"CONTEXT", "NONLINEAR"}:
        base.extend(FeatureTerm(f"{name}:context", (name,), 1) for name in CANDIDATES)
    if family == "NONLINEAR":
        for left, right in itertools.combinations(CANDIDATES, 2):
            base.append(FeatureTerm(f"{left}:{right}", (left, right)))
    return tuple(base)


def _design(rows: Sequence[Mapping[str, float]], terms: Sequence[FeatureTerm]) -> np.ndarray:
    return np.asarray([[term.evaluate(row) for term in terms] for row in rows], dtype=float)


def counterfactual_terms(family: str) -> tuple[FeatureTerm, ...]:
    """Public structural basis for identifiability/preflight analysis."""
    return _terms(family)


def counterfactual_design_matrix(rows: Sequence[Mapping[str, float]], terms: Sequence[FeatureTerm]) -> np.ndarray:
    """Public design matrix; does not fit coefficients or grant model authority."""
    return _design(rows, terms)


def _stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _fit_single(
    rows: Sequence[Mapping[str, float]],
    y: Sequence[float],
    *,
    family: str,
    model_id: str,
    rng: np.random.Generator,
    bootstrap: bool,
    fault: str,
) -> FittedCounterfactualModel:
    terms = _terms(family)
    n = len(rows)
    if n < max(8, len(terms) + 2):
        raise ValueError("insufficient rows for counterfactual model fit")
    if bootstrap:
        idx = rng.integers(0, n, size=n)
        fit_rows = [rows[int(i)] for i in idx]
        fit_y = np.asarray([y[int(i)] for i in idx], dtype=float)
    else:
        fit_rows = list(rows)
        fit_y = np.asarray(y, dtype=float)
    matrix = _design(fit_rows, terms)
    coef, *_ = np.linalg.lstsq(matrix, fit_y, rcond=None)
    coefficients = {term.name: float(value) for term, value in zip(terms, coef, strict=True)}

    # Controlled misspecification attacks. These mutate the learned model, not the evaluator.
    if fault == "MISSING_TRUE_EDGE":
        for term in terms:
            if "A" in term.players:
                coefficients[term.name] = 0.0
    elif fault == "WRONG_COEFFICIENT":
        for term in terms:
            if "A" in term.players:
                coefficients[term.name] *= 0.25
    elif fault == "SIGN_ERROR":
        for term in terms:
            if "A" in term.players:
                coefficients[term.name] *= -1.0
    elif fault == "SHARED_SPURIOUS_EDGE":
        # +alpha*C - alpha*A preserves factual prediction when C≈A while creating
        # a strong false do(C) effect. This is the mandatory precisely-wrong ensemble null.
        alpha = 1.20
        if "C" in coefficients:
            coefficients["C"] += alpha
        if "A" in coefficients:
            coefficients["A"] -= alpha
    elif fault != "NONE":
        raise ValueError(f"unknown controlled model fault: {fault}")

    counts: dict[str, int] = {}
    for row in rows:
        key = config_key(row)
        counts[key] = counts.get(key, 0) + 1
    return FittedCounterfactualModel(
        model_id=model_id,
        family=family,
        version="CSCA-02-UA-v1",
        terms=terms,
        coefficients=tuple(coefficients[t.name] for t in terms),
        train_config_counts=tuple(sorted(counts.items())),
        train_rows=n,
        fault=fault,
    )


def fit_counterfactual_ensemble(
    rows: Sequence[Mapping[str, float]],
    y: Sequence[float],
    *,
    seed: int,
    fault: str = "NONE",
    bootstraps_per_family: int = 4,
) -> tuple[FittedCounterfactualModel, ...]:
    if len(rows) != len(y):
        raise ValueError("rows/y length mismatch")
    models: list[FittedCounterfactualModel] = []
    for family in ("LINEAR", "CONTEXT", "NONLINEAR"):
        for b in range(bootstraps_per_family):
            rng = np.random.default_rng(_stable_seed(seed, family, b, "bootstrap"))
            models.append(
                _fit_single(
                    rows,
                    y,
                    family=family,
                    model_id=f"{family}-B{b}",
                    rng=rng,
                    bootstrap=True,
                    fault=fault,
                )
            )
    return tuple(models)
