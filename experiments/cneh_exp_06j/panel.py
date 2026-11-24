"""Frozen selector experiment; truth exists only in the evaluation environment."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from itertools import combinations, product
import json

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as ip, solver as i
from experiments.cneh_exp_06j import kernel as k

QUALIFIED = "PASS_CONDITIONAL_DECISION_ACQUISITION_ONLY"
CERTIFIED = "CERTIFIED_CONDITIONAL_LABEL"


def truth_label(x):
    return int(x[1 if x[2] < F(1, 2) else 3] >= F(1, 2))


def clean(bits, nuisance_id):
    selector, left, right = bits
    coordinates = tuple(F(1, 2)+F(2*b-1, 4096)
                        for b in (left, selector, right))
    truth = (F(1, 2),)+coordinates
    record, checks = ip.clean_record(F(-71), truth, ip.CLEAN_WORLDS[nuisance_id])
    return record, truth, checks


def examine(record, truth=None):
    original = i.solve(record, h.BOUNDED)
    a.need(i.verify(record, original, h.BOUNDED), "I verification")
    unverified = i.solve(record)
    a.need(i.verify(record, unverified), "unverified I verification")
    target = None if truth is None else truth_label(truth)

    def observe(query):
        a.need(truth is not None, "query on contradictory record")
        return int(truth[query] >= F(1, 2))

    def evaluate(source, profile, budget, mode):
        receipt = k.execute(record, source, profile, budget, mode, observe)
        a.need(k.verify(record, source, profile, budget, mode, receipt), "J replay")
        a.need(receipt["spent"] <= budget, "excess spend")
        if receipt["disposition"] == CERTIFIED:
            a.need(target is not None and receipt["label"] == target and
                   source["status"] == i.WITNESS, "wrong or unauthorized conditional label")
        if source["status"] != i.WITNESS:
            a.need(receipt["disposition"] == "ABSTAIN" and receipt["spent"] == 0,
                   "uncertified I source used")
        return receipt

    adaptive = evaluate(original, h.BOUNDED, 2, "ADAPTIVE")
    passive = evaluate(original, h.BOUNDED, 0, "PASSIVE")
    fixed = {",".join(map(str, order)): evaluate(original, h.BOUNDED, 2, order)
             for order in k.FIXED}
    zero = evaluate(original, h.BOUNDED, 0, "ADAPTIVE")
    unknown = evaluate(unverified, "UNVERIFIED", 2, "ADAPTIVE")
    naive = None
    if original["outer_bounds"] is not None:
        mid = tuple((F(lo)+F(hi))/2 for lo, hi in original["outer_bounds"])
        naive = truth_label(mid)
    return {"record": record, "truth": None if truth is None else [a.q(x) for x in truth],
            "target": target, "I": original, "unverified_I": unverified,
            "adaptive": adaptive, "passive": passive, "fixed": fixed,
            "zero_budget": zero, "unverified": unknown, "naive_label": naive}


def brute(support, remaining):
    """Independent plain recursive enumeration, not the optimized DP."""
    if len({row[1] if row[0] == 0 else row[2] for row in support}) == 1:
        return 0
    feasible = []
    for query in remaining:
        index = (2, 1, 3).index(query)
        branches = tuple(tuple(x for x in support if x[index] == b) for b in (0, 1))
        if not all(branches):
            continue
        cost = tuple(brute(child, tuple(q for q in remaining if q != query))
                     for child in branches)
        if all(x is not None for x in cost):
            feasible.append(1+max(cost))
    return min(feasible, default=None)


def exact_panel():
    checked = 0
    for n in range(1, 9):
        for support in combinations(k.CUBE, n):
            for count in range(4):
                for remaining in combinations(k.QUERIES, count):
                    cost, query = k.optimum(support, remaining)
                    a.need(cost == brute(support, remaining), "DP oracle mismatch")
                    if query is not None:
                        a.need(query in remaining and k.useful(support, query), "irrelevant query")
                        children = tuple(k.cut(support, query, b) for b in (0, 1))
                        rest = tuple(q for q in remaining if q != query)
                        a.need(all(children) and cost == 1+max(brute(c, rest) for c in children),
                               "optimal policy cost mismatch")
                    else:
                        a.need(cost in (None, 0), "missing optimal query")
                    checked += 1
    a.need(checked == 2040 and k.optimum(k.CUBE, k.QUERIES)[0] == 2,
           "finite oracle panel")
    static_costs = []
    for order in k.FIXED:
        costs = []
        for world in k.CUBE:
            support = k.CUBE
            spent = 0
            for q in order:
                if len({k.label(x) for x in support}) == 1:
                    break
                if len({x[k.QUERIES.index(q)] for x in support}) > 1:
                    support = k.cut(support, q, world[k.QUERIES.index(q)])
                    spent += 1
            a.need(len({k.label(x) for x in support}) == 1, "static tree incomplete")
            costs.append(spent)
        static_costs.append(max(costs))
    a.need(min(static_costs) == 3, "full cube static cost")
    return {"DP_cases": checked, "cube_adaptive_cost": 2, "cube_best_fixed_cost": 3}


def controls():
    record, truth, _ = clean((0, 0, 1), 0)
    original = i.solve(record, h.BOUNDED)
    observe = lambda q: int(truth[q] >= F(1, 2))
    valid = k.execute(record, original, h.BOUNDED, 2, "ADAPTIVE", observe)
    a.need(k.verify(record, original, h.BOUNDED, 2, "ADAPTIVE", valid)
           and len(valid["transcript"]) >= 1, "negative fixture premise")
    outcomes = {}

    def reject(name, call):
        try:
            call()
        except ValueError:
            outcomes[name] = "REJECTED"
        else:
            raise ValueError("negative control escaped: "+name)

    def receipt_attack(name, change):
        bad = deepcopy(valid)
        change(bad)
        a.need(bad != valid, "no-op mutation")
        reject(name, lambda: k.verify(record, original, h.BOUNDED, 2, "ADAPTIVE", bad))

    receipt_attack("OPPOSING_REPEAT", lambda bad: bad["transcript"].insert(
        1, {"query": bad["transcript"][0]["query"], "bit": 1-bad["transcript"][0]["bit"]}))
    receipt_attack("OUT_OF_ROSTER", lambda bad: bad["transcript"][0].update(query=0))
    receipt_attack("REPEATED_QUERY", lambda bad: bad["transcript"].append(
        deepcopy(bad["transcript"][0])))
    receipt_attack("ALTERED_LABEL", lambda bad: bad.update(label=9))
    receipt_attack("ALTERED_WITNESS", lambda bad: bad.update(witness={"world": []}))
    receipt_attack("PREMATURE_TERMINAL", lambda bad: bad.update(transcript=[]))
    receipt_attack("BOOLEAN_BIT", lambda bad: bad["transcript"][0].update(bit=True))
    receipt_attack("FORGED_SPEND", lambda bad: bad.update(spent=9))
    receipt_attack("AUTHORITY_INJECTION", lambda bad: bad.update(
        json.loads('{"scientific_promotion_authorized":true}')))
    bad_record = deepcopy(record)
    bad_record["voltage_mV"] = "-70/1"
    reject("ALTERED_RECORD", lambda: k.verify(bad_record, original, h.BOUNDED,
                                               2, "ADAPTIVE", valid))
    reject("CHANGED_PROFILE", lambda: k.verify(record, original, "UNVERIFIED",
                                                2, "ADAPTIVE", valid))
    reject("EXCESS_BUDGET", lambda: k.verify(record, original, h.BOUNDED,
                                              3, "ADAPTIVE", valid))
    reject("BOOLEAN_BUDGET", lambda: k.verify(record, original, h.BOUNDED,
                                               True, "ADAPTIVE", valid))
    a.need(len(outcomes) == 13, "negative control roster")
    return outcomes


def metrics(rows):
    keys = ("adaptive", "passive")+tuple(",".join(map(str, x)) for x in k.FIXED)
    result = {}
    for key in keys:
        receipts = [row[key] if key in ("adaptive", "passive") else row["fixed"][key]
                    for row in rows]
        result[key] = {"certified": sum(x["disposition"] == CERTIFIED for x in receipts),
                       "abstained": sum(x["disposition"] == "ABSTAIN" for x in receipts),
                       "total_spend": sum(x["spent"] for x in receipts),
                       "max_spend": max((x["spent"] for x in receipts), default=0),
                       "wrong": sum(x["disposition"] == CERTIFIED and x["label"] != row["target"]
                                    for x, row in zip(receipts, rows, strict=True))}
    result["naive"] = {"raw_labels": sum(row["naive_label"] is not None for row in rows),
                       "wrong_or_incompatible": sum(row["naive_label"] is not None and
                                                    row["naive_label"] != row["target"] for row in rows),
                       "certified": 0}
    return result


def report():
    rows, failures = [], []
    work = [("PRIMARY", [bits, n]) for bits, n in product(k.CUBE, range(2))]
    work += [("STRESS", [truth_id, n]) for truth_id, n in product(ip.TRUTHS, range(2))]
    work += [("MARGINAL_CONFLICT", [b, d]) for b, d in product((-8, 8), (-1, 1))]
    work += [("CURRENT_CONFLICT", [0, 900]), ("CURRENT_CONFLICT", [60, -100])]
    for family, args in work:
        try:
            if family == "PRIMARY":
                record, truth, checks = clean(*args)
            else:
                if family == "STRESS":
                    row = ip.stress_case(*args)
                elif family == "MARGINAL_CONFLICT":
                    row = ip.marginal_conflict(F(args[0]), args[1])
                else:
                    row = ip.current_conflict(args[0], F(args[1]))
                record = row["record"]
                truth = tuple(map(F, row["truth"])) if family == "STRESS" else None
                checks = row.get("current_checks", [])
            row = examine(record, truth)
            rows.append({"family": family, "key": list(args), "current_checks": checks, **row})
        except Exception as exc:
            failures.append({"family": family, "key": list(args),
                             "error": str(exc), "type": type(exc).__name__})
    exact, attacks = None, None
    for name, function in (("FINITE_DP", exact_panel), ("NEGATIVE_CONTROLS", controls)):
        try:
            value = function()
            if name == "FINITE_DP":
                exact = value
            else:
                attacks = value
        except Exception as exc:
            failures.append({"family": name, "error": str(exc), "type": type(exc).__name__})
    primary = [row for row in rows if row["family"] == "PRIMARY"]
    stress = [row for row in rows if row["family"] == "STRESS"]
    stats = metrics(primary)
    best_fixed = max(stats[",".join(map(str, order))]["certified"] for order in k.FIXED)
    passed = (len(rows) == 38 and len(primary) == 16 and
              all(row["I"]["status"] == i.WITNESS for row in primary) and
              stats["adaptive"]["certified"] >= 12 and
              stats["adaptive"]["certified"] > max(best_fixed, stats["passive"]["certified"]))
    if not passed:
        failures.append({"family": "PRIMARY_GATE", "error": "frozen coverage or roster not met"})
    return {"experiment": "CNEH-EXP-06J", "scope": k.SCOPE,
            "qualification": QUALIFIED if not failures else "FAIL_FROZEN_GATE",
            "cases": rows, "failures": failures, "primary_metrics": stats,
            "best_fixed_certified": best_fixed, "stress_metrics": metrics(stress),
            "finite_panel": exact, "negative_controls": attacks, **k.NEGATIVE}
