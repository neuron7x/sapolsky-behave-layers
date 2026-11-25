"""Finite, exact decision-sufficiency research oracle; not an action runtime."""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache
from itertools import combinations, product
import json

MAX_WORLDS, MAX_ACTIONS, MAX_TESTS = 8, 4, 8
SCOPE = "FINITE_DETERMINISTIC_SYNTHETIC_DECISION_SUFFICIENCY"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def exact(x):
    need(type(x) in (F, int), "exact rational required")
    return F(x)


def q(x):
    return None if x is None else str(F(x))


def subsets(items, *, empty=False):
    return tuple(s for k in range(0 if empty else 1, len(items)+1)
                 for s in combinations(items, k))


def loss_matrix(matrix):
    need(type(matrix) in (tuple, list) and 1 <= len(matrix) <= MAX_WORLDS,
         "world count")
    need(all(type(row) in (tuple, list) for row in matrix), "loss row")
    m = len(matrix[0])
    need(1 <= m <= MAX_ACTIONS and all(len(row) == m for row in matrix),
         "action count or ragged matrix")
    return tuple(tuple(exact(x) for x in row) for row in matrix)


def regret(matrix):
    return tuple(tuple(x-min(row) for x in row) for row in loss_matrix(matrix))


def decisions(matrix, epsilon=0):
    eps = exact(epsilon)
    need(eps >= 0, "negative tolerance")
    r = regret(matrix)
    worst = tuple(max(row[a] for row in r) for a in range(len(r[0])))
    return tuple(i for i, value in enumerate(worst) if value <= eps)


def direct_intersection(matrix, epsilon=0):
    m = loss_matrix(matrix)
    eps = exact(epsilon)
    need(eps >= 0, "negative tolerance")
    common = set(range(len(m[0])))
    for row in m:
        common.intersection_update(i for i, value in enumerate(row)
                                   if value <= min(row)+eps)
    return tuple(sorted(common))


def minimal_obstructions(matrix, epsilon=0):
    m = loss_matrix(matrix)
    result = []
    for w in subsets(tuple(range(len(m)))):
        if not any(set(x).issubset(w) for x in result) and not decisions(
                tuple(m[i] for i in w), epsilon):
            result.append(w)
    return tuple(result)


def validate_model(matrix, tests, epsilon):
    m = loss_matrix(matrix)
    eps = exact(epsilon)
    need(eps >= 0 and type(tests) in (tuple, list) and len(tests) <= MAX_TESTS,
         "test count or epsilon")
    catalog = []
    for t in tests:
        need(type(t) in (tuple, list) and len(t) == 3, "test record")
        name, cost, outputs = t
        cost = exact(cost)
        need(type(name) is str and 1 <= len(name) <= 32 and cost > 0, "test identity or cost")
        need(type(outputs) in (tuple, list) and len(outputs) == len(m) and
             all(type(y) is int for y in outputs), "test outcomes")
        catalog.append((name, cost, tuple(outputs)))
    need(len({t[0] for t in catalog}) == len(catalog), "duplicate test identity")
    return m, tuple(catalog), eps


def partition(w, output):
    return tuple((y, tuple(i for i in w if output[i] == y))
                 for y in sorted({output[i] for i in w}))


def optimal(matrix, tests, epsilon=0, *, full_id=False):
    m, ts, eps = validate_model(matrix, tests, epsilon)

    @lru_cache(None)
    def dp(w, remaining):
        allowed = decisions(tuple(m[i] for i in w), eps)
        if (len(w) == 1 if full_id else bool(allowed)):
            return F(0), {"action": allowed[0]}
        best = None, None
        for i in remaining:
            name, cost, output = ts[i]
            children = partition(w, output)
            if len(children) < 2:
                continue
            rest = tuple(j for j in remaining if j != i)
            results = [(y, dp(child, rest)) for y, child in children]
            if any(value is None for _, (value, _) in results):
                continue
            total = cost+max(value for _, (value, _) in results)
            if best[0] is None or total < best[0]:
                best = total, {"test": name, "branches": [
                    {"outcome": y, "node": node} for y, (_, node) in results]}
        return best

    return dp(tuple(range(len(m))), tuple(range(len(ts))))


def brute_force_cost(matrix, tests, epsilon=0, *, full_id=False):
    """Independent nonmemoized exhaustive recursion over test ordering."""
    m, ts, eps = validate_model(matrix, tests, epsilon)

    def visit(w, remaining):
        if len(w) == 1 if full_id else bool(direct_intersection([m[i] for i in w], eps)):
            return F(0)
        candidates = []
        for t in remaining:
            branches = {value: tuple(i for i in w if t[2][i] == value)
                        for value in {t[2][i] for i in w}}
            if len(branches) == 1:
                continue
            values = [visit(child, tuple(x for x in remaining if x != t))
                      for child in branches.values()]
            if all(v is not None for v in values):
                candidates.append(t[1]+max(values))
        return min(candidates, default=None)
    return visit(tuple(range(len(m))), ts)


def replay(matrix, tests, cost, policy, epsilon=0, *, full_id=False):
    """Recompute every reachable branch, leaf action and total cost."""
    m, ts, eps = validate_model(matrix, tests, epsilon)
    catalog = {t[0]: t for t in ts}

    def visit(w, remaining, node):
        need(type(node) is dict, "invalid policy node")
        if set(node) == {"action"}:
            a = node["action"]
            need(type(a) is int and a in direct_intersection([m[i] for i in w], eps),
                 "inadmissible leaf action")
            need(not full_id or len(w) == 1, "false full identification")
            return F(0)
        need(set(node) == {"test", "branches"} and node["test"] in remaining,
             "unknown or repeated test")
        name, price, outputs = catalog[node["test"]]
        expected = partition(w, outputs)
        branches = node["branches"]
        need(type(branches) is list and len(expected) >= 2 and len(branches) == len(expected),
             "incomplete or nonsplitting policy")
        values = []
        for branch, (outcome, child) in zip(branches, expected, strict=True):
            need(type(branch) is dict and set(branch) == {"outcome", "node"} and
                 type(branch["outcome"]) is int and branch["outcome"] == outcome,
                 "impossible or missing outcome")
            values.append(visit(child, remaining-{name}, branch["node"]))
        return price+max(values)

    need(cost is not None and exact(cost) == visit(tuple(range(len(m))), set(catalog), policy),
         "policy cost mismatch")
    return True


def static_analysis(matrix, tests, epsilon=0, *, full_id=False):
    m, ts, eps = validate_model(matrix, tests, epsilon)
    obligations = (tuple(combinations(range(len(m)), 2)) if full_id
                   else minimal_obstructions(m, eps))
    rows, optimal_cost = [], None
    for chosen in subsets(ts, empty=True):
        fibers = {}
        for i in range(len(m)):
            key = tuple(t[2][i] for t in chosen)
            fibers.setdefault(key, []).append(i)
        terminal = all((len(w) == 1 if full_id else bool(
            direct_intersection([m[i] for i in w], eps))) for w in fibers.values())
        covered = all(any(len({t[2][i] for i in obstruction}) > 1 for t in chosen)
                      for obstruction in obligations)
        need(terminal == covered, "obstruction cover theorem counterexample")
        cost = sum((t[1] for t in chosen), F(0))
        if terminal and (optimal_cost is None or cost < optimal_cost):
            optimal_cost = cost
        rows.append({"tests": [t[0] for t in chosen], "cost": q(cost), "terminal": terminal})
    return optimal_cost, rows


def greedy(matrix, tests, epsilon=0):
    """Myopic worst-case regret reduction per unit cost; abstain if no gain."""
    m, ts, eps = validate_model(matrix, tests, epsilon)
    r = regret(m)

    def value(w):
        return min(max(r[i][a] for i in w) for a in range(len(m[0])))

    def visit(w, remaining):
        allowed = direct_intersection([m[i] for i in w], eps)
        if allowed:
            return F(0)
        scored = []
        for t in remaining:
            children = partition(w, t[2])
            score = (value(w)-max(value(child) for _, child in children))/t[1]
            if len(children) > 1 and score > 0:
                scored.append((score, t))
        if not scored:
            return None
        _, t = max(scored, key=lambda item: item[0])
        values = [visit(child, tuple(x for x in remaining if x != t))
                  for _, child in partition(w, t[2])]
        return None if any(v is None for v in values) else t[1]+max(values)
    return visit(tuple(range(len(m))), ts)


def budget_disposition(matrix, tests, budget, epsilon=0):
    cap = exact(budget)
    need(cap >= 0, "negative budget")
    cost, policy = optimal(matrix, tests, epsilon)
    if cost is None or cost > cap:
        return "ABSTAIN"
    need(replay(matrix, tests, cost, policy, epsilon), "unverified budget plan")
    return "CONDITIONAL_PLAN_AVAILABLE"


def binary_family(kind):
    worlds = tuple(product(range(2), repeat=3))
    labels = tuple(x^y if kind == "XOR" else (y if x == 0 else z) for x, y, z in worlds)
    matrix = tuple(tuple(int(a != y) for a in range(2)) for y in labels)
    tests = tuple((name, 1, tuple(w[i] for w in worlds)) for i, name in enumerate(("x", "y", "z")))
    if kind == "XOR":
        tests += (("direct_label", 5, labels),)
    return matrix, tests


def report():
    cases, nested, obstruction_checks = 0, 0, 0
    ws = subsets((0, 1, 2))
    for bits in product(range(2), repeat=9):
        m = tuple(bits[i:i+3] for i in range(0, 9, 3))
        for eps in (0, 1):
            values = {}
            for w in ws:
                local = tuple(m[i] for i in w)
                allowed = decisions(local, eps)
                need(allowed == direct_intersection(local, eps), "decision theorem mismatch")
                values[w] = set(allowed)
                obstructions = minimal_obstructions(local, eps)
                need(bool(obstructions) == (not allowed) and all(
                    len(o) <= len(local[0]) for o in obstructions), "obstruction bound")
                cases += 1
                obstruction_checks += 1
            for w in ws:
                for v in ws:
                    if set(v).issubset(w):
                        need(values[w].issubset(values[v]), "refinement monotonicity")
                        nested += 1
    m = ((0, 10), (100, 99))
    r = regret(m)
    shifted = ((0, 10), (0, -1))
    need(r == regret(shifted) and not decisions(m), "loss shift or common optimum")
    loss_winner = min(range(2), key=lambda a: max(row[a] for row in m))
    regret_winner = min(range(2), key=lambda a: max(row[a] for row in r))
    shifted_winner = min(range(2), key=lambda a: max(row[a] for row in shifted))
    need((loss_winner, regret_winner, shifted_winner) == (1, 0, 0), "loss-regret counterexample")
    overlap = ((0, 0, 1), (1, 0, 0), (0, 1, 0))
    need(minimal_obstructions(overlap) == ((0, 1, 2),), "triple obstruction")
    families = {}
    for name, expected in (("XOR", (F(2), F(2), F(3))), ("SELECTOR", (F(2), F(3), F(3)))):
        matrix, tests = binary_family(name)
        cost, policy = optimal(matrix, tests)
        static, table = static_analysis(matrix, tests)
        full, full_policy = optimal(matrix, tests, full_id=True)
        need((cost, static, full) == expected, "acquisition cost counterexample")
        need(cost == brute_force_cost(matrix, tests) and full == brute_force_cost(
            matrix, tests, full_id=True), "independent recursion mismatch")
        need(replay(matrix, tests, cost, policy) and replay(matrix, tests, full, full_policy, full_id=True),
             "policy verification")
        families[name] = {"adaptive": q(cost), "static": q(static), "full_id_adaptive": q(full),
                          "greedy": q(greedy(matrix, tests)), "policy": policy,
                          "full_id_policy": full_policy, "static_subsets": table}
    need(families["XOR"]["greedy"] == "5", "greedy counterexample")
    impossible = ((0, 1), (1, 0))
    tests = (("constant", 1, (0, 0)),)
    need(optimal(impossible, tests) == (None, None) and
         brute_force_cost(impossible, tests) is None and
         static_analysis(impossible, tests)[0] is None, "false feasibility")
    budget = budget_disposition(*binary_family("XOR"), 0)
    need(budget == "ABSTAIN" and cases == 7168, "frozen case count or zero budget")
    return {"scope": SCOPE, "cases": cases, "nested_checks": nested,
            "obstruction_checks": obstruction_checks, "loss_winner": loss_winner,
            "regret_winner": regret_winner, "shifted_loss_winner": shifted_winner,
            "triple_obstruction": [0, 1, 2], "families": families,
            "indistinguishable_impossible": True, "zero_budget_nonterminal": budget,
            "scientific_promotion_authorized": False, "source_action_authorized": False,
            "closed_loop_authorized": False, "external_novelty": "NOT_ESTABLISHED"}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode("ascii")


if __name__ == "__main__":
    print(canonical(report()).decode("ascii"), end="")
