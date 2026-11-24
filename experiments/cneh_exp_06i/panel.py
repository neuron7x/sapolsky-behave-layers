"""Frozen I evaluation: existence, contradiction and bounded abstention."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from itertools import product

from experiments.cneh_exp_06c import algebra as a, fixtures
from experiments.cneh_exp_06f import panel as f
from experiments.cneh_exp_06h import panel as hp, reference as h
from experiments.cneh_exp_06i import solver as s

TRUTHS = (0, 3, 6, 9, 12, 15, 16, 31)
CLEAN_WORLDS = ((F(1), F(0), F(0), F(3, 2), F(1, 2), F(110)),
                (F(7, 8), F(8), F(1), F(1), F(0), F(100)))
STRESS_WORLDS = ((hp.worlds()[-1], -1), (hp.worlds()[0], 1))
QUALIFIED = "PASS_CONDITIONAL_JOINT_FEASIBILITY_ASSURANCE_ONLY"


def clean_record(v, x, nuisance):
    """Independent Decimal generator with exact outward truth checks."""
    gain, offset, drift, gamma, delay, tau = nuisance
    world = x+nuisance
    fixed = tuple(a.point(value) for value in world)
    samples, checks = [], []
    for t in h.TIMES:
        analog = gain*fixtures.current(F(t)+delay, x, tau_n=tau,
                                       nmda_gain=gamma)+offset+drift*F(t, 120)
        certified = s.forward(t, fixed, a.point(0))
        a.need(certified[0] <= analog <= certified[1], "independent clean KCL mismatch")
        code = f.quantize(analog, h.STEP)
        worst = max(abs(code-q) for q in certified)
        a.need(worst <= h.EPS, "clean code not compatible")
        samples.append({"t_ms": t, "current_pA": a.q(code)})
        checks.append({"t_ms": t, "clean_outer_pA": a.encode(certified),
                       "worst_error_pA": a.q(worst)})
    truths = (offset, 128*gain+offset, offset+2*drift, gamma, delay, tau)
    refs = {name: a.q(f.quantize(value, h.STEP)) for name, value in
            zip(h.REFS, truths, strict=True)}
    a.need(all(abs(F(refs[name])-v) <= h.R for name, v in
               zip(h.REFS, truths, strict=True)), "clean reference incompatibility")
    return {"schema": h.SCHEMA, "voltage_mV": a.q(v),
            "samples": samples, "references": refs}, checks


def assess(record, truth=None, expected=None, budget=s.MAX_NODES):
    baseline = h.estimate(record, h.BOUNDED)
    result = s.solve(record, h.BOUNDED, budget)
    a.need(s.verify(record, result, h.BOUNDED, budget), "proof verification")
    unknown = s.solve(record)
    a.need(s.verify(record, unknown), "unverified proof verification")
    a.need(unknown["status"] == s.UNCALIBRATED and
           unknown["outer_bounds"] == s.encode_box((h.PRIOR,)*4), "uncalibrated fallback")
    if expected is not None:
        a.need(result["status"] == expected, "unexpected solver disposition: "+result["status"])
    if truth is not None:
        a.need(result["status"] != s.EXCLUDED and result["outer_bounds"] is not None and
               all(F(lo) <= v <= F(hi) for v, (lo, hi) in
                   zip(truth, result["outer_bounds"], strict=True)), "compatible truth excluded")
    return {"record": record, "H": baseline, "I": result, "unverified": unknown}


def clean_case(index, world_index):
    v, x = fixtures.truth(index)
    nuisance = CLEAN_WORLDS[world_index]
    record, checks = clean_record(v, x, nuisance)
    return {"family": "CLEAN", "truth_id": index, "world_id": world_index,
            "truth": [a.q(q) for q in x], "current_checks": checks,
            **assess(record, x, s.WITNESS)}


def stress_case(index, world_index):
    nuisance, sign = STRESS_WORLDS[world_index]
    row = hp.panel_case(index, nuisance, sign)
    x = tuple(map(F, row["truth"]))
    return {"family": "STRESS", "truth_id": index, "world_id": world_index,
            "truth": row["truth"], "current_checks": row["current_certificates"],
            **assess(row["record"], x)}


def marginal_conflict(b, direction):
    x = (F(1, 2),)*4
    gain = h.GAIN[0] if direction == 1 else h.GAIN[1]
    nuisance = (gain, b, F(direction), F(3, 2), F(1, 2), F(110))
    record, _ = clean_record(F(-71), x, nuisance)
    record["references"].update({
        "zero_pA": a.q(b),
        "span_pA": a.q(128*gain+b-direction*h.R),
        "late_zero_pA": a.q(b+2*direction+direction*(h.R+h.STEP)),
    })
    _, _, refs = h.parse(record)
    a.need(h.reference_intervals(refs) is not None, "marginal reference premise")
    result = assess(record, expected=s.EXCLUDED)
    a.need(result["H"]["status"] == "CONDITIONAL_NARROW_ENCLOSURE",
           "H narrow-marginal counterexample not reproduced")
    proof = result["I"]["certificate"]
    a.need(proof["kind"] == "JOINT_REFERENCE_EMPTY" and proof["coordinate"] == "offset" and
           F(proof["lower"])-F(proof["upper"]) == h.STEP,
           "exact shared-offset contradiction not certified")
    return {"family": "MARGINAL_CONFLICT", "b0": a.q(b), "direction": direction,
            **result}


def current_conflict(t, value):
    record, _ = clean_record(F(-71), (F(1, 2),)*4, CLEAN_WORLDS[0])
    record["samples"][h.TIMES.index(t)]["current_pA"] = a.q(value)
    result = assess(record, expected=s.EXCLUDED)
    proof = result["I"]["certificate"]
    a.need(proof["kind"] == "COVER" and proof["unresolved_leaves"] == 0,
           "current contradiction not covered")
    return {"family": "CURRENT_CONFLICT", "time_ms": t, "code_pA": a.q(value), **result}


def negative_controls():
    record, _ = clean_record(F(-71), (F(1, 2),)*4, CLEAN_WORLDS[0])
    valid = s.solve(record, h.BOUNDED)
    zero = s.solve(record, h.BOUNDED, 0)
    a.need(s.verify(record, valid, h.BOUNDED) and valid["status"] == s.WITNESS,
           "positive witness control")
    a.need(s.verify(record, zero, h.BOUNDED, 0) and zero["status"] == s.UNKNOWN and
           zero["nodes"] == 0, "zero budget must abstain")
    _, observed, refs = h.parse(record)
    root, contradiction = s.root_box(refs)
    a.need(contradiction is None, "unexpected reference contradiction")
    tree, nodes = s.search_tree(root, observed, refs, 3)
    frontier, checked = s.verify_tree(root, observed, refs, 3, tree)
    a.need(nodes == checked == 3 and len(frontier) > 0 and tree["kind"] == "SPLIT",
           "three-node unresolved cover")
    controls = {"ZERO_BUDGET": s.UNKNOWN, "THREE_NODE_COVER": s.UNKNOWN}

    def reject(name, call):
        try:
            call()
        except ValueError:
            controls[name] = "REJECTED"
        else:
            raise ValueError("negative control escaped: "+name)

    forged = deepcopy(valid)
    forged["scientific_promotion_authorized"] = True
    reject("FORGED_AUTHORITY", lambda: s.verify(record, forged, h.BOUNDED))
    forged = deepcopy(valid)
    forged["conditional_joint_witness_verified"] = False
    reject("WITNESS_STATUS_TAMPER", lambda: s.verify(record, forged, h.BOUNDED))
    forged = deepcopy(valid)
    forged["record_sha256"] = "0"*64
    reject("WRONG_RECORD_DIGEST", lambda: s.verify(record, forged, h.BOUNDED))
    forged = deepcopy(valid)
    forged["certificate"]["witness"]["world"][7] = "2/1"
    reject("WRONG_GAMMA_WITNESS", lambda: s.verify(record, forged, h.BOUNDED))
    forged = deepcopy(valid)
    forged["certificate"]["witness"]["samples"][0]["worst_analog_error_pA"] = "0/1"
    reject("FORGED_ANALOG_RECEIPT", lambda: s.verify(record, forged, h.BOUNDED))
    forged = deepcopy(valid)
    forged["certificate"]["witness"]["reference_errors"]["gamma"] = "1/1"
    reject("FORGED_REFERENCE_RECEIPT", lambda: s.verify(record, forged, h.BOUNDED))
    forged_tree = deepcopy(tree)
    forged_tree["children"].pop()
    reject("MISSING_CHILD", lambda: s.verify_tree(root, observed, refs, 3, forged_tree))
    forged_tree = deepcopy(tree)
    forged_tree["mid"] = "0/1"
    reject("WRONG_SPLIT", lambda: s.verify_tree(root, observed, refs, 3, forged_tree))
    reject("FORGED_PRUNE", lambda: s.verify_tree(root, observed, refs, 3,
                                                {"kind": "PRUNED", "reason": {}}))
    reject("PREMATURE_BUDGET_STOP", lambda: s.verify_tree(root, observed, refs, 3,
                                                        {"kind": "UNRESOLVED", "reason": "BUDGET"}))
    reject("EXCESS_BUDGET", lambda: s.solve(record, h.BOUNDED, 64))
    reject("BOOLEAN_BUDGET", lambda: s.solve(record, h.BOUNDED, True))
    reject("UNSUPPORTED_PROFILE", lambda: s.solve(record, "CALIBRATED"))
    reject("CROSS_PROFILE_RECEIPT", lambda: s.verify(record, valid))
    a.need(len(controls) == 16, "negative control roster")
    return {"controls": controls, "three_node_tree": tree,
            "three_node_frontier": [s.encode_box(box) for box in frontier]}


def report():
    rows, failures = [], []
    work = []
    for i, j in product(TRUTHS, range(2)):
        work.append(("CLEAN", [i, j], clean_case))
        work.append(("STRESS", [i, j], stress_case))
    for b, direction in product((-8, 8), (-1, 1)):
        work.append(("MARGINAL_CONFLICT", [F(b), direction], marginal_conflict))
    work.extend((("CURRENT_CONFLICT", [0, F(900)], current_conflict),
                 ("CURRENT_CONFLICT", [60, F(-100)], current_conflict)))
    for name, args, operation in work:
        try:
            rows.append(operation(*args))
        except Exception as exc:
            failures.append({"family": name, "args": [str(v) for v in args],
                             "error_type": type(exc).__name__, "error": str(exc)})
    controls = None
    try:
        controls = negative_controls()
    except Exception as exc:
        failures.append({"family": "NEGATIVE_CONTROLS",
                         "error_type": type(exc).__name__, "error": str(exc)})
    counts = {}
    for row in rows:
        family = row["family"]
        key = row["I"]["status"]
        counts.setdefault(family, {})
        counts[family][key] = counts[family].get(key, 0)+1
    if not failures:
        a.need(len(rows) == 38 and counts["CLEAN"] == {s.WITNESS: 16} and
               counts["MARGINAL_CONFLICT"] == {s.EXCLUDED: 4} and
               counts["CURRENT_CONFLICT"] == {s.EXCLUDED: 2} and
               sum(counts["STRESS"].values()) == 16 and s.EXCLUDED not in counts["STRESS"],
               "frozen evaluation roster")
    return {"experiment": "CNEH-EXP-06I", "scope": s.SCOPE,
            "qualification": "FAIL_ENGINEERING_GATE" if failures else QUALIFIED,
            "cases": rows, "failures": failures, "counts": counts,
            "negative_controls": controls, **s.NEGATIVE}
