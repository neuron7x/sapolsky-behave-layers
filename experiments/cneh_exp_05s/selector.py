"""Exact finite selector diagnostic. No native or deployed controller."""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
import json
from pathlib import Path

from experiments.cneh_exp_05i import causal

T = 10
H = 3
WAIT = (-1,) * H
PLANS = tuple(product((-1, 0, 1), repeat=H))
ALL = (0, 1, 2, 3)
COST = 200


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


@dataclass(frozen=True)
class Fixture:
    name: str
    modes: tuple
    adaptation: tuple
    drives: tuple
    masks: tuple
    windows: tuple
    budget: int


def tape(pair):
    return (pair,) * H


def fixture(name, w=(0,), drives=((0, 0),), masks=((0, 0),),
            windows=(), budget=600, modes=ALL):
    return Fixture(name, modes, tuple(product(w, repeat=2)),
                   tuple(tape(x) for x in drives), tuple(tape(x) for x in masks),
                   windows, budget)


FIXTURES = (
    fixture("INFORMATIVE"),
    fixture("SILENT", w=(20,)),
    fixture("RECOVERY", w=(8,), budget=200),
    fixture("ALIAS_NO_BUDGET", drives=((4, 4),), budget=0),
    fixture("REVIVAL", windows=((13, 13),)),
    fixture("HIDDEN_WINDOW", w=(0, 8), drives=((0, 0), (4, 0)),
            masks=((0, 0), (1, 0), (0, 1), (1, 1)), windows=((11, 11),), budget=400),
    fixture("SINGLETON", modes=(0,)),
    fixture("ERASED", masks=((1, 1),)),
)


def paths(f):
    result = set()

    def visit(states):
        if len(states) == H + 1:
            result.add(tuple(x[0] for x in states))
            return
        for nxt in causal.successors(states[-1], T + len(states), f.windows):
            visit(states + (nxt,))

    for mode in f.modes:
        visit(((mode, 0),))
    # Independent explicit enumeration (does not call the automaton).
    oracle = set()
    for path in product(ALL, repeat=H + 1):
        if path[0] not in f.modes:
            continue
        used = set()
        for k in range(1, H + 1):
            if path[k] == path[k - 1]:
                continue
            windows = [w for w in f.windows if w[0] <= T + k <= w[1]]
            if len(windows) != 1 or windows[0] in used:
                break
            used.add(windows[0])
        else:
            oracle.add(path)
    need(result == oracle and result, "finite path enumeration disagreement")
    return tuple(sorted(result))


def roster(f):
    need(type(f.budget) is int and f.budget >= 0, "invalid budget")
    values = tuple(product(paths(f), f.adaptation, f.drives, f.masks))
    need(values and len(values) == len(set(values)), "empty or duplicate scenario roster")
    return values


def observe(scenario, plan):
    path, adaptation, drive, mask = scenario
    need(plan in PLANS and len(path) == H + 1, "invalid scenario or plan")
    w = adaptation
    observations = []
    for k, action in enumerate(plan):
        bits = tuple(int(drive[k][j] + 6 * (action == j) >= 4 + w[j])
                     for j in range(2))
        count = sum(b * x for b, x in zip(bits, causal.MODES[path[k]], strict=True))
        observations.append(tuple(None if mask[k][j] else bits[j] for j in range(2)) + (count,))
        w = tuple(w[j] // 2 + 4 * bits[j] for j in range(2))
    return tuple(observations), w


def supports(scenarios, plan):
    need(scenarios and len(set(scenarios)) == len(scenarios), "invalid scenario roster")
    observations = [observe(s, plan)[0] for s in scenarios]
    classes = defaultdict(set)
    for s, obs in zip(scenarios, observations, strict=True):
        classes[obs].add(s[0][-1])
    result = []
    # Independent comparison of every scenario with every other scenario;
    # not a second lookup of the class dictionary.
    for i, (s, obs) in enumerate(zip(scenarios, observations, strict=True)):
        support = tuple(sorted(classes[obs]))
        oracle = tuple(sorted({other[0][-1] for other, o in
                               zip(scenarios, observations, strict=True) if o == observations[i]}))
        need(support == oracle and s[0][-1] in support, "equivalence class falsified")
        result.append(support)
    return tuple(result)


def ambiguity(support):
    need(isinstance(support, tuple) and support and all(type(m) is int and m in ALL for m in support)
         and len(set(support)) == len(support), "invalid mode support")
    return len(support) * (len(support) - 1) // 2


def charge(plan):
    need(plan in PLANS and all(type(x) is int for x in plan), "invalid plan")
    return COST * sum(x != -1 for x in plan)


def choose(rows, budget):
    """Rank an explicitly finite synthetic roster, never an authority receipt."""
    need(type(budget) is int and budget >= 0, "invalid budget")
    by = {}
    for plan, gain, cost in rows:
        need(plan in PLANS and plan not in by, "invalid or duplicate plan")
        need(type(gain) is int and -6 <= gain <= 6, "invalid gain")
        need(type(cost) is int and cost == charge(plan), "invalid charge")
        by[plan] = (gain, cost)
    need(set(by) == set(PLANS) and by[WAIT] == (0, 0), "incomplete roster or invalid WAIT")
    eligible = [(plan, gain, cost) for plan, (gain, cost) in by.items()
                if 0 < cost <= budget and gain > 0]
    if not eligible:
        return WAIT
    return min(eligible, key=lambda x: (-Fraction(x[1], x[2]), x[2], PLANS.index(x[0])))[0]


def evaluate(f, scenarios=None):
    expected = roster(f)
    actual = expected if scenarios is None else tuple(scenarios)
    need(len(actual) == len(expected) and set(actual) == set(expected), "incomplete scenario roster")
    base = tuple(map(ambiguity, supports(actual, WAIT)))
    rows = []
    output = []
    for plan in PLANS:
        other = tuple(map(ambiguity, supports(actual, plan)))
        gain = min(a - b for a, b in zip(base, other, strict=True))
        cost = charge(plan)
        rows.append((plan, gain, cost))
        score = Fraction(gain, cost) if cost else None
        output.append({"plan": list(plan), "worst_paired_gain": gain, "charge_pA_ms": cost,
                       "gain_per_charge": None if score is None else [score.numerator, score.denominator]})
    selected = choose(rows, f.budget)
    need(selected == choose(tuple(reversed(rows)), f.budget), "rank order dependence")
    return {"fixture": f.name, "scenarios": len(actual), "plan_count": len(PLANS),
            "equivalence_pair_checks": len(PLANS) * len(actual) ** 2,
            "budget_pA_ms": f.budget, "selected": list(selected), "plans": output}


def report():
    results = [evaluate(f) for f in FIXTURES]
    selections = {x["fixture"]: tuple(x["selected"]) for x in results}
    need(all(selections[k] == WAIT for k in ("SILENT", "REVIVAL", "SINGLETON", "ALIAS_NO_BUDGET")),
         "negative-control selection failed")
    need(selections["RECOVERY"] == (-1, -1, 0), "adaptation recovery fixture failed")
    return {"experiment": "CNEH-EXP-05S", "scientific_promotion_authorized": False,
            "scientific_promotion": "BLOCKED", "scope": "EXACT_FINITE_SYNTHETIC_MODEL_ONLY",
            "native_replay": "NOT_TESTED", "physical_control": "NOT_TESTED",
            "fixtures": results, "total_scenarios": sum(x["scenarios"] for x in results),
            "total_equivalence_pair_checks": sum(x["equivalence_pair_checks"] for x in results)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    payload = (json.dumps(report(), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    if args.verify:
        need(args.out.is_file() and not args.out.is_symlink() and args.out.read_bytes() == payload,
             "exact report replay mismatch")
    else:
        with args.out.open("xb") as handle:
            handle.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
