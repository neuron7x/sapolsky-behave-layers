"""Bounded exact policies, mixture certificates, and coherent continuation values."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import combinations, product

from cwc.epistemics.evidence_value import EvidenceProbe, _exact, _value

Scalar = int | Fraction
Vector = tuple[Fraction, ...]
Matrix = tuple[Vector, ...]


def _probabilities(values: Sequence[Scalar]) -> Vector:
    vector = tuple(map(_exact, values))
    if not vector or min(vector) < 0 or sum(vector) != 1:
        raise ValueError("invalid probability vector")
    return vector


def _worlds(utilities: Sequence[Sequence[Scalar]], weights: Sequence[Scalar]) -> tuple[Matrix, Vector]:
    matrix = tuple(tuple(map(_exact, row)) for row in utilities)
    nominal = _probabilities(weights)
    if not 2 <= len(matrix) <= 8 or len(matrix) != len(nominal) or 0 not in nominal:
        raise ValueError("invalid world or challenge roster")
    if not 1 <= len(matrix[0]) <= 4 or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError("invalid action roster")
    return matrix, nominal


def _dot(left: Sequence[Fraction], right: Sequence[Fraction]) -> Fraction:
    return sum((a * b for a, b in zip(left, right, strict=True)), Fraction(0))


def prior_vertices(weights: Sequence[Scalar], radius: Scalar) -> tuple[Vector, ...]:
    """Extreme distributions of the single, persistent countermodel mixture."""
    nominal = _probabilities(weights)
    amount = _exact(radius)
    if not 2 <= len(nominal) <= 8 or 0 not in nominal or not 0 <= amount <= 1:
        raise ValueError("invalid uncertainty set")
    result = [nominal]
    for stress, weight in enumerate(nominal):
        if weight == 0 and amount:
            result.append(tuple((1 - amount) * p + (amount if index == stress else 0)
                                for index, p in enumerate(nominal)))
    return tuple(result)


def posterior_vertices(
    weights: Sequence[Scalar], likelihoods: Sequence[Scalar], radius: Scalar,
) -> tuple[Vector, ...]:
    """Condition the original uncertainty set on a complete observed history."""
    likelihood = tuple(map(_exact, likelihoods))
    if len(likelihood) != len(weights) or not all(0 <= p <= 1 for p in likelihood):
        raise ValueError("invalid history likelihoods")
    result = []
    for prior in prior_vertices(weights, radius):
        joint = tuple(a * b for a, b in zip(prior, likelihood, strict=True))
        mass = sum(joint)
        if mass:
            result.append(tuple(p / mass for p in joint))
    if not result:
        raise ValueError("history is impossible under all permitted distributions")
    return tuple(dict.fromkeys(result))


def continuation_gain(
    original: Sequence[Scalar], revision: Sequence[Scalar], conditioned: Sequence[Vector],
) -> Fraction:
    """Compare continuation values with common sunk costs already excluded."""
    if not conditioned:
        raise ValueError("a continuation requires reachable history")
    delta = tuple(_exact(after) - _exact(before)
                  for before, after in zip(original, revision, strict=True))
    return min(_dot(p, delta) for p in conditioned)


def _solve_active(rows: Sequence[Vector], rhs: Sequence[Fraction]) -> Vector | None:
    matrix = [[*row, value] for row, value in zip(rows, rhs, strict=True)]
    n = len(matrix)
    for column in range(n):
        pivot = next((k for k in range(column, n) if matrix[k][column]), None)
        if pivot is None:
            return None
        matrix[pivot], matrix[column] = matrix[column], matrix[pivot]
        divisor = matrix[column][column]
        matrix[column] = [x / divisor for x in matrix[column]]
        for k, row in enumerate(matrix):
            if k != column:
                factor = row[column]
                matrix[k] = [x - factor * y for x, y in zip(row, matrix[column], strict=True)]
    return tuple(row[-1] for row in matrix)


def mixture_certificate(profiles: Sequence[Sequence[Scalar]], target: Scalar) -> Vector | None:
    """Return an exact feasible mixture over at most four fixed gain profiles."""
    if not 1 <= len(profiles) <= 4:
        raise ValueError("expected one to four policies")
    columns = tuple(tuple(map(_exact, profile)) for profile in profiles)
    threshold = _exact(target)
    if not 1 <= len(columns[0]) <= 32 or any(len(row) != len(columns[0]) for row in columns):
        raise ValueError("invalid or oversized constraint roster")
    n = len(columns)
    one = (Fraction(1),) * n
    inequalities = [(tuple(Fraction(i == j) for i in range(n)), Fraction(0)) for j in range(n)]
    inequalities.extend((row, threshold) for row in zip(*columns, strict=True))
    for active in combinations(inequalities, n-1):
        witness = _solve_active((one, *(row for row, _ in active)),
                                (Fraction(1), *(rhs for _, rhs in active)))
        if witness is not None and all(_dot(row, witness) >= rhs for row, rhs in inequalities):
            return witness
    return None


@dataclass(frozen=True, slots=True)
class MixedRadius:
    lower: Fraction
    upper: Fraction
    lower_witness: Vector


def mixture_radius_bounds(
    *, utilities: Sequence[Sequence[Scalar]], weights: Sequence[Scalar],
    policy_payoffs: Sequence[Sequence[Scalar]], target: Scalar, steps: int = 10,
) -> MixedRadius | None:
    matrix, nominal = _worlds(utilities, weights)
    threshold = _exact(target)
    payoffs = tuple(tuple(map(_exact, policy)) for policy in policy_payoffs)
    if not 1 <= len(payoffs) <= 4 or any(len(p) != len(matrix) for p in payoffs):
        raise ValueError("invalid policy payoff roster")
    if type(steps) is not int or not 0 <= steps <= 12 or threshold <= 0:
        raise ValueError("invalid search depth or target")

    def at(radius: Fraction) -> Vector | None:
        vertices = prior_vertices(nominal, radius)
        comparators = tuple(zip(*matrix, strict=True))
        return mixture_certificate(
            [tuple(_dot(vertex, p) - _dot(vertex, a) for vertex in vertices for a in comparators)
             for p in payoffs], threshold,
        )

    low, high = Fraction(0), Fraction(1)
    witness = at(low)
    if witness is None:
        return None
    full = at(high)
    if full is not None:
        return MixedRadius(high, high, full)
    for _ in range(steps):
        midpoint = (low + high) / 2
        candidate = at(midpoint)
        if candidate is None:
            high = midpoint
        else:
            low, witness = midpoint, candidate
    return MixedRadius(low, high, witness)


@dataclass(frozen=True, slots=True)
class ObservationBranch:
    probe_id: str
    zero: Tree
    one: Tree


Tree = int | ObservationBranch


@dataclass(frozen=True, slots=True)
class TreeChoice:
    tree: Tree
    radius: Fraction
    nominal_advantage: Fraction


@dataclass(frozen=True, slots=True)
class TreeComparison:
    adaptive: TreeChoice | None
    fixed: TreeChoice | None
    greedy: TreeChoice | None


def _options(probes: tuple[str, ...], actions: int, depth: int) -> tuple[Tree, ...]:
    result: list[Tree] = list(range(actions))
    if depth:
        for probe in probes:
            rest = tuple(x for x in probes if x != probe)
            subtasks = _options(rest, actions, depth-1)
            result.extend(ObservationBranch(probe, a, b) for a, b in product(subtasks, repeat=2))
    return tuple(result)


def _fixed(tree: Tree) -> bool:
    if isinstance(tree, int):
        return True
    second = {node.probe_id for node in (tree.zero, tree.one) if isinstance(node, ObservationBranch)}
    return len(second) <= 1


def select_evidence_trees(
    *, utilities: Sequence[Sequence[Scalar]], weights: Sequence[Scalar],
    probes: Sequence[EvidenceProbe], target: Scalar, depth: int = 2,
) -> TreeComparison:
    """Exact bounded two-step search under conditional independence given each world."""
    matrix, nominal = _worlds(utilities, weights)
    threshold = _exact(target)
    if threshold <= 0 or type(depth) is not int or not 1 <= depth <= 2 or not 1 <= len(probes) <= 3:
        raise ValueError("invalid target, depth, or probe roster")
    if any(type(p.probe_id) is not str or not p.probe_id.strip() for p in probes):
        raise ValueError("nonempty probe ids required")
    choices = {p.probe_id: p for p in probes}
    if len(choices) != len(probes):
        raise ValueError("duplicate probe ids")
    costs = {name: _exact(p.cost) for name, p in choices.items()}
    laws = {name: tuple(map(_probabilities, p.laws)) for name, p in choices.items()}
    if (any(cost < 0 for cost in costs.values()) or
            any(len(rows) != len(matrix) or any(len(row) != 2 for row in rows) for rows in laws.values())):
        raise ValueError("invalid cost or binary observation matrix")

    @cache
    def payoff(tree: Tree) -> Vector:
        if isinstance(tree, int):
            return tuple(row[tree] for row in matrix)
        return tuple(a*p0+b*p1-costs[tree.probe_id] for a,b,(p0,p1) in zip(
            payoff(tree.zero), payoff(tree.one), laws[tree.probe_id], strict=True,
        ))

    names = tuple(sorted(choices))
    best_free = max(_dot(nominal, a) for a in zip(*matrix, strict=True))
    one_step: dict[str, Fraction] = {}
    for tree in _options(names, len(matrix[0]), 1):
        if isinstance(tree, ObservationBranch):
            net = _dot(nominal, payoff(tree)) - best_free
            one_step[tree.probe_id] = max(net, one_step.get(tree.probe_id, net))
    greedy_root = min(names, key=lambda name: (-one_step[name], name))
    best: dict[str, TreeChoice] = {}
    for tree in _options(names, len(matrix[0]), depth):
        value = _value(matrix, nominal, payoff(tree), threshold)
        if value is None:
            continue
        candidate = TreeChoice(tree, *value)
        allowed = ["adaptive"]
        if _fixed(tree):
            allowed.append("fixed")
        if isinstance(tree, int) or tree.probe_id == greedy_root:
            allowed.append("greedy")
        for mode in allowed:
            incumbent = best.get(mode)
            if incumbent is None or value > (incumbent.radius, incumbent.nominal_advantage):
                best[mode] = candidate
    return TreeComparison(best.get("adaptive"), best.get("fixed"), best.get("greedy"))
