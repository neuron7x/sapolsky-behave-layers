"""Frozen finite panel, separate AND/OR oracle, and proof attacks."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from itertools import product

from experiments.cneh_exp_06k import kernel as k

EXPERIMENT = "CNEH-EXP-06K"
QUALIFIED = "PASS_FROZEN_FINITE_SYNTHETIC_GATE"
NEGATIVE = {"scientific_promotion_authorized": False,
            "scientific_promotion": "BLOCKED",
            "physical_reference_calibration": "NOT_TESTED",
            "physical_reference_independence": "NOT_TESTED",
            "continuous_joint_feasibility": "NOT_TESTED",
            "biological_validity": "NOT_TESTED",
            "multiscale_generalization": "NOT_TESTED",
            "statistical_generalization": "NOT_TESTED",
            "independent_external_replication": "NOT_TESTED",
            "independent_custodian": "NOT_TESTED",
            "closed_loop_efficacy": "NOT_TESTED"}


def oracle_worlds(model, signs, polarity):
    rows = []
    for sign in range(8):
        if not (signs // (2**sign)) % 2:
            continue
        s, l, r = sign // 4, sign // 2 % 2, sign % 2
        for es, el, er in product(range(2), repeat=3):
            if not (polarity // (2**es)) % 2:
                continue
            if model == "SHARED" and (es != el or es != er):
                continue
            # Rows are (target, four observable responses), not production masks.
            rows.append((l if s == 0 else r, es, (s+es)%2,
                         (l+el)%2, (r+er)%2))
    return tuple(sorted(set(rows)))


@lru_cache(maxsize=65536)
def can_resolve(rows, tests, depth):
    if not rows:
        return False
    if all(row[0] == rows[0][0] for row in rows):
        return True
    if depth == 0:
        return False
    for q in tests:
        remaining = tuple(t for t in tests if t != q)
        valid = True
        for answer in range(2):
            children = tuple(row for row in rows if row[q] == answer)
            if children and not can_resolve(children, remaining, depth-1):
                valid = False
                break
        if valid:
            return True
    return False


def exact_panel():
    cases = 0
    failures = []
    for model in ("SHARED", "INDEPENDENT"):
        for signs in range(1, 256):
            for polarity in range(1, 4):
                support = k.initial(model, signs, polarity)
                rows = oracle_worlds(model, signs, polarity)
                for available in range(16):
                    tests = tuple(q+1 for q in range(4) if available & (1 << q))
                    want = next((d for d in range(len(tests)+1)
                                 if can_resolve(rows, tests, d)), None)
                    got, query = k.optimum(support, available)
                    cases += 1
                    if got != want:
                        failures.append([model, signs, polarity, available, got, want])
                    elif got is not None and got > 0:
                        if query not in k.QUERIES:
                            failures.append(["missing query", model, signs, polarity, available])
                        else:
                            j = k.QUERIES.index(query)
                            rest = tuple(q for q in tests if q != j+1)
                            children = [tuple(row for row in rows if row[j+1] == bit)
                                        for bit in (0, 1)]
                            if j+1 not in tests or not all(children) or not all(
                                    can_resolve(child, rest, got-1) for child in children):
                                failures.append(["invalid policy", model, signs, polarity, available])
    return {"configurations": cases, "failures": failures}


def truth_label(world):
    s, l, r, _, _, _ = world
    return l if s == 0 else r


def observe(world, query):
    s, l, r, es, el, er = world
    return {"C": es, "T2": (s+es)%2, "T1": (l+el)%2,
            "T3": (r+er)%2}[query]


def run_world(model, polarity, budget, mode, world):
    recorded = []

    def read(query):
        bit = observe(world, query)
        recorded.append([query, bit])
        return bit

    receipt = k.execute(model, 255, polarity, budget, mode, read)
    k.need(k.verify(model, 255, polarity, budget, mode, recorded, receipt),
           "fresh replay")
    return receipt


def metric(rows, key):
    receipts = [row[key] for row in rows]
    return {"certified": sum(r["label"] is not None for r in receipts),
            "wrong": sum(r["label"] is not None and r["label"] != row["truth"]
                         for r, row in zip(receipts, rows, strict=True)),
            "max_spend": max(r["spent"] for r in receipts),
            "total_spend": sum(r["spent"] for r in receipts)}


def controls():
    world = (0, 0, 1, 0, 0, 0)
    receipt = run_world("SHARED", 3, 3, "ADAPTIVE", world)
    history = deepcopy(receipt["transcript"])
    results = {}

    def reject(name, proof, observed, model="SHARED"):
        try:
            k.verify(model, 255, 3, 3, "ADAPTIVE", observed, proof)
        except (ValueError, TypeError):
            results[name] = "REJECTED"
        else:
            results[name] = "ACCEPTED_INVALID_PROOF"

    changes = {"label": 1-receipt["label"], "support": [], "spent": 0,
               "sign_mask": 127, "polarity_mask": 1, "budget": 4,
               "mode": "PASSIVE", "scope": "FORGED", "extra": 1}
    for key, value in changes.items():
        bad = deepcopy(receipt)
        bad[key] = value
        reject(key, bad, history)
    reject("model", receipt, history, model="INDEPENDENT")
    bad = deepcopy(receipt)
    flag = next(key for key in bad if key == "scientific_promotion_authorized")
    bad[flag] = True  # adversarial fixture only, never a production write
    reject("authority_injection", bad, history)
    changed = deepcopy(history)
    changed[-1][1] = 1-changed[-1][1]
    reject("external_transcript", receipt, changed)
    changed = [history[0], history[0], history[-1]]
    reject("repeated_query", receipt, changed)
    changed = deepcopy(history)
    changed[0][1] = bool(changed[0][1])
    reject("boolean_outcome", receipt, changed)
    reject("premature_terminal", receipt, history[:-1])
    # A query after a certified terminal state is invalid even below budget.
    passive_world = (0, 0, 0, 0, 0, 0)
    terminal = k.execute("SHARED", 1, 3, 3, "ADAPTIVE",
                         lambda q: observe(passive_world, q))
    try:
        k.verify("SHARED", 1, 3, 3, "ADAPTIVE", [["C", 0]], terminal)
    except (ValueError, TypeError):
        results["after_terminal"] = "REJECTED"
    else:
        results["after_terminal"] = "ACCEPTED_INVALID_PROOF"
    return results


def report():
    exact = exact_panel()
    shared = []
    independent = []
    for world in product((0, 1), repeat=6):
        truth = truth_label(world)
        independent.append({"world": list(world), "truth": truth,
                            "adaptive": run_world("INDEPENDENT", 3, 4, "ADAPTIVE", world)})
        if world[3] != world[4] or world[4] != world[5]:
            continue
        naive = run_world("SHARED", 1, 3, "ADAPTIVE", world)
        shared.append({"world": list(world), "truth": truth,
                       "adaptive": run_world("SHARED", 3, 3, "ADAPTIVE", world),
                       "passive": run_world("SHARED", 3, 3, "PASSIVE", world),
                       "fixed": [run_world("SHARED", 3, 3, mode, world) for mode in k.FIXED],
                       "naive_raw": {"guess": naive["label"], "spent": naive["spent"],
                                     "transcript": naive["transcript"]}})
    fixed = [metric([{"truth": row["truth"], "fixed": row["fixed"][j]}
                     for row in shared], "fixed") for j in range(24)]
    metrics = {"adaptive": metric(shared, "adaptive"), "passive": metric(shared, "passive"),
               "fixed": fixed, "best_fixed": max(x["certified"] for x in fixed),
               "independent": metric(independent, "adaptive"),
               "naive_raw": {"guesses": sum(row["naive_raw"]["guess"] is not None for row in shared),
                             "wrong": sum(row["naive_raw"]["guess"] is not None and
                                          row["naive_raw"]["guess"] != row["truth"] for row in shared)}}
    rows = oracle_worlds("INDEPENDENT", 255, 3)
    ambiguity = [{"responses": list(bits),
                  "labels": sorted({row[0] for row in rows if row[1:] == bits})}
                 for bits in product((0, 1), repeat=4)]
    negative = controls()
    checks = {
        "oracle": exact["configurations"] == 24480 and not exact["failures"],
        "shared": len(shared) == 16 and metrics["adaptive"]["certified"] == 16 and
                  metrics["adaptive"]["wrong"] == 0 and metrics["adaptive"]["max_spend"] == 3,
        "fixed": len(fixed) == 24 and metrics["best_fixed"] <= 8 and
                 all(x["wrong"] == 0 and x["max_spend"] <= 3 for x in fixed),
        "passive": metrics["passive"]["certified"] == 0 and metrics["passive"]["max_spend"] == 0,
        "naive": metrics["naive_raw"]["wrong"] >= 1,
        "independent": len(independent) == 64 and metrics["independent"]["certified"] == 0 and
                       metrics["independent"]["total_spend"] == 0,
        "ambiguity": len(ambiguity) == 16 and all(x["labels"] == [0, 1] for x in ambiguity),
        "controls": len(negative) == 16 and set(negative.values()) == {"REJECTED"},
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {"experiment": EXPERIMENT, "scope": k.SCOPE,
            "qualification": QUALIFIED if not failures else "FAIL_FROZEN_GATE",
            "failures": failures, "checks": checks, "oracle": exact, "metrics": metrics,
            "shared_cases": shared, "independent_cases": independent,
            "full_response_ambiguities": ambiguity, "negative_controls": negative, **NEGATIVE}
