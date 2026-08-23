from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class Factor:
    name: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        name = self.name.strip()
        values = tuple(str(value).strip() for value in self.values)
        if not name:
            raise ValueError("factor name required")
        if not values or any(not value for value in values):
            raise ValueError("factor values must be non-empty")
        if len(set(values)) != len(values):
            raise ValueError("factor values must be unique")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "values", values)


@dataclass(frozen=True, slots=True)
class FactorSchema:
    factors: tuple[Factor, ...]

    def __post_init__(self) -> None:
        factors = tuple(sorted(self.factors, key=lambda factor: factor.name))
        if not factors:
            raise ValueError("at least one factor required")
        names = [factor.name for factor in factors]
        if len(names) != len(set(names)):
            raise ValueError("factor names must be unique")
        object.__setattr__(self, "factors", factors)

    @property
    def digest(self) -> str:
        return _digest([(factor.name, factor.values) for factor in self.factors])

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(factor.name for factor in self.factors)


@dataclass(frozen=True, slots=True)
class CoverageCase:
    case_id: str
    values: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id required")
        normalized = tuple(sorted((str(name).strip(), str(value).strip()) for name, value in self.values))
        if any(not name or not value for name, value in normalized):
            raise ValueError("assignment names/values must be non-empty")
        if len({name for name, _ in normalized}) != len(normalized):
            raise ValueError("each factor assigned exactly once")
        object.__setattr__(self, "values", normalized)

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self.values)


@dataclass(frozen=True, slots=True)
class CombinatorialCoverageCertificate:
    schema_digest: str
    strength: int
    case_count: int
    interaction_universe: int
    covered_interactions: int
    coverage_fraction: float
    missing_interaction_count: int
    missing_interactions_digest: str
    case_population_digest: str
    complete: bool


def _validate_cases(schema: FactorSchema, cases: tuple[CoverageCase, ...]) -> None:
    if not cases:
        raise ValueError("non-empty test population required")
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("case_id must be unique")
    allowed = {factor.name: set(factor.values) for factor in schema.factors}
    expected = set(schema.names)
    for case in cases:
        mapping = case.mapping
        if set(mapping) != expected:
            raise ValueError(f"case {case.case_id} must assign every and only frozen factor")
        for name, value in mapping.items():
            if value not in allowed[name]:
                raise ValueError(f"case {case.case_id} value outside frozen factor domain: {name}={value}")


def certify_t_way_coverage(
    schema: FactorSchema,
    cases: tuple[CoverageCase, ...],
    *,
    strength: int,
) -> CombinatorialCoverageCertificate:
    """Measure exact unconstrained t-way interaction coverage of a frozen factor space."""
    if strength <= 0 or strength > len(schema.factors):
        raise ValueError("strength must be in [1, number of factors]")
    _validate_cases(schema, cases)

    universe = set()
    covered = set()
    for factor_subset in itertools.combinations(schema.factors, strength):
        names = tuple(factor.name for factor in factor_subset)
        for values in itertools.product(*(factor.values for factor in factor_subset)):
            universe.add(tuple(zip(names, values)))
        for case in cases:
            mapping = case.mapping
            covered.add(tuple((name, mapping[name]) for name in names))

    if not covered.issubset(universe):
        raise AssertionError("internal coverage construction escaped interaction universe")
    missing = tuple(sorted(universe - covered))
    total = len(universe)
    hit = len(covered)
    rows = tuple(sorted((case.case_id, case.values) for case in cases))
    return CombinatorialCoverageCertificate(
        schema_digest=schema.digest,
        strength=strength,
        case_count=len(cases),
        interaction_universe=total,
        covered_interactions=hit,
        coverage_fraction=hit / total,
        missing_interaction_count=len(missing),
        missing_interactions_digest=_digest(missing),
        case_population_digest=_digest(rows),
        complete=not missing,
    )


def require_coverage(
    certificate: CombinatorialCoverageCertificate,
    *,
    min_fraction: float,
    require_complete: bool = False,
) -> None:
    threshold = float(min_fraction)
    if not 0 <= threshold <= 1:
        raise ValueError("min_fraction must be in [0,1]")
    if certificate.coverage_fraction + 1e-12 < threshold:
        raise ValueError(
            f"combinatorial coverage below threshold: {certificate.coverage_fraction:.6f} < {threshold:.6f}"
        )
    if require_complete and not certificate.complete:
        raise ValueError(
            f"complete {certificate.strength}-way coverage required; missing={certificate.missing_interaction_count}"
        )
