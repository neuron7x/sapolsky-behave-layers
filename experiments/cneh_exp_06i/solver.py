"""Proof-carrying joint compatibility under the frozen H synthetic contract."""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical, sha
from experiments.cneh_exp_06h import reference as h

NAMES = ("w", "ampa", "nmda", "gaba", "gain", "offset", "drift", "gamma", "delay", "tau")
PRIORS = ((h.PRIOR,)*4 + (h.GAIN, (F(-16), F(16)), (F(-1), F(1)),
                          h.GAMMA, h.DELAY, h.TAU))
MAX_NODES = 63
MAX_DEPTH = 6
GRID = 2**80
SCOPE = "JOINT_COMPATIBILITY_CONDITIONAL_ON_H_SYNTHETIC_INFORMATION_CONTRACT"
NEGATIVE = {k: v for k, v in h.NEGATIVE.items() if k != "joint_feasibility_proven"}
NEGATIVE["historical_H_joint_feasibility"] = "NOT_ESTABLISHED_IN_H"
WITNESS = "CERTIFIED_SYNTHETIC_FEASIBLE"
EXCLUDED = "CERTIFIED_SYNTHETIC_INFEASIBLE"
UNKNOWN = "UNKNOWN"
UNCALIBRATED = "CALIBRATION_UNVERIFIED"


def intersection(*intervals):
    return max(x[0] for x in intervals), min(x[1] for x in intervals)


def encode_box(box):
    return [a.encode(value) for value in box]


def root_box(refs):
    a.need(refs is not None, "missing independent references")
    r0, r1, r240, gamma, delay, tau = (refs[name] for name in h.REFS)
    b_constraints = (
        PRIORS[5], (r0-h.R, r0+h.R),
        (r1-h.R-128*h.GAIN[1], r1+h.R-128*h.GAIN[0]),
        (r240-h.R-2, r240+h.R+2),
    )
    b = intersection(*b_constraints)
    scalars = (
        ("offset", b, b_constraints),
        ("gamma", intersection(h.GAMMA, (gamma-h.R, gamma+h.R)),
         (h.GAMMA, (gamma-h.R, gamma+h.R))),
        ("delay", intersection(h.DELAY, (delay-h.R, delay+h.R)),
         (h.DELAY, (delay-h.R, delay+h.R))),
        ("tau", intersection(h.TAU, (tau-h.R, tau+h.R)),
         (h.TAU, (tau-h.R, tau+h.R))),
    )
    for name, bounds, constraints in scalars:
        if bounds[0] > bounds[1]:
            return None, {"kind": "JOINT_REFERENCE_EMPTY", "coordinate": name,
                          "lower": a.q(bounds[0]), "upper": a.q(bounds[1]),
                          "constraints": encode_box(constraints)}
    gain = intersection(h.GAIN, ((r1-h.R-b[1])/128, (r1+h.R-b[0])/128))
    drift = intersection(PRIORS[6], ((r240-h.R-b[1])/2, (r240+h.R-b[0])/2))
    a.need(gain[0] <= gain[1] and drift[0] <= drift[1], "reference projection invariant")
    return ((h.PRIOR,)*4 + (gain, b, drift, scalars[1][1],
                            scalars[2][1], scalars[3][1])), None


def reference_predictions(box):
    _, _, _, _, gain, b, drift, gamma, delay, tau = box
    return (b, a.add(a.mul(a.point(128), gain), b),
            a.add(b, a.mul(a.point(2), drift)), gamma, delay, tau)


def exp_range(value):
    return a.exponential(value[0])[0], a.exponential(value[1])[1]


@lru_cache(maxsize=256)
def coefficients(t, gamma, delay, tau, jitter):
    """Direct physical-state affine KCL, independent of H's inverse."""
    elapsed = a.add(a.add(a.point(t), delay), jitter)
    w_decay = exp_range(a.neg(a.div(elapsed, a.point(200))))
    a_decay = exp_range(a.neg(a.div(elapsed, a.point(F(5, 2)))))
    n_decay = exp_range(a.neg(a.div(elapsed, tau)))
    g_decay = exp_range(a.neg(a.div(elapsed, a.point(6))))
    base = a.sub(h.constant(), a.mul(a.point(20), w_decay))
    block = h.nmda_block()
    terms = (a.mul(a.point(24), w_decay), a.mul(a.point(-6), a_decay),
             a.mul(a.mul(a.mul(a.point(-6), block), gamma), n_decay),
             a.mul(a.point(5), g_decay))
    return a.outward(base, GRID), tuple(a.outward(x, GRID) for x in terms)


def forward(t, box, jitter=(F(0), h.J)):
    a.need(type(t) is int and t in h.TIMES, "sample time")
    gain, offset, drift, gamma, delay, tau = box[4:]
    base, row = coefficients(t, gamma, delay, tau, jitter)
    current = a.add(base, a.isum(a.mul(c, x) for c, x in zip(row, box[:4], strict=True)))
    return a.outward(a.add(a.add(a.mul(gain, current), offset),
                            a.mul(drift, a.point(F(t, 120)))), GRID)


def disjoint(x, y):
    return x[1] < y[0] or y[1] < x[0]


def prune_reason(box, observed, refs):
    for name, prediction in zip(h.REFS, reference_predictions(box), strict=True):
        measured = (refs[name]-h.R, refs[name]+h.R)
        if disjoint(prediction, measured):
            return {"kind": "REFERENCE_DISJOINT", "reference": name,
                    "prediction": a.encode(prediction), "measurement": a.encode(measured)}
    for t, y in zip(h.TIMES, observed, strict=True):
        prediction = forward(t, box)
        measured = (y-h.E, y+h.E)
        if disjoint(prediction, measured):
            return {"kind": "CURRENT_DISJOINT", "t_ms": t,
                    "prediction": a.encode(prediction), "measurement": a.encode(measured)}
    return None


def candidate_nuisance(root, refs):
    b = a.midpoint(root[5])
    gain = intersection(h.GAIN, ((refs["span_pA"]-h.R-b)/128,
                                (refs["span_pA"]+h.R-b)/128))
    drift = intersection(PRIORS[6], ((refs["late_zero_pA"]-h.R-b)/2,
                                    (refs["late_zero_pA"]+h.R-b)/2))
    a.need(gain[0] <= gain[1] and drift[0] <= drift[1], "joint reference midpoint invariant")
    return (a.midpoint(gain), b, a.midpoint(drift),
            *(a.midpoint(x) for x in root[7:]))


def project(value):
    # Candidate construction only; never use this projection as a proof.
    return max(F(0), min(F(1), F(round(value*2**40), 2**40)))


def least_squares(observed, nuisance):
    fixed = tuple(a.point(x) for x in nuisance)
    zero = (a.point(0),)*4+fixed
    matrix, rhs = [], []
    for t, y in zip(h.TIMES, observed, strict=True):
        offset = a.midpoint(forward(t, zero, a.point(0)))
        row = []
        for j in range(4):
            unit = tuple(a.point(int(i == j)) for i in range(4))+fixed
            row.append(a.midpoint(forward(t, unit, a.point(0)))-offset)
        matrix.append(row)
        rhs.append(y-offset)
    normal = [[sum((row[i]*row[j] for row in matrix), F(0))
               for j in range(4)] for i in range(4)]
    right = [sum((row[i]*y for row, y in zip(matrix, rhs, strict=True)), F(0))
             for i in range(4)]
    inverse = a.inverse(normal)
    return tuple(project(sum((coef*y for coef, y in zip(row, right, strict=True)), F(0)))
                 for row in inverse)


def witness_for(world, observed, refs):
    """Prove a single compatible world, without assuming a fit is correct."""
    if len(world) != len(PRIORS) or not all(
            type(x) is F and lo <= x <= hi for x, (lo, hi) in zip(world, PRIORS, strict=True)):
        return None
    box = tuple(a.point(x) for x in world)
    reference_errors = {}
    for name, prediction in zip(h.REFS, reference_predictions(box), strict=True):
        error = max(abs(refs[name]-x) for x in prediction)
        if error > h.R:
            return None
        reference_errors[name] = a.q(error)
    samples = []
    for t, y in zip(h.TIMES, observed, strict=True):
        for jitter in (F(0), h.J):
            interval = forward(t, box, a.point(jitter))
            error = max(abs(y-x) for x in interval)
            if error <= h.EPS:
                samples.append({"t_ms": t, "jitter_ms": a.q(jitter),
                                "clean_outer_pA": a.encode(interval),
                                "worst_analog_error_pA": a.q(error)})
                break
        else:
            return None
    return {"world": [a.q(x) for x in world], "coordinate_order": list(NAMES),
            "reference_errors": reference_errors, "samples": samples}


def propose(root, observed, refs, baseline):
    nuisance = candidate_nuisance(root, refs)
    states = []
    if baseline["normalized_bounds"] is not None:
        states.append(tuple(project(a.midpoint(tuple(map(F, x))))
                            for x in baseline["normalized_bounds"]))
    try:
        states.append(least_squares(observed, nuisance))
    except ValueError:
        # A failed candidate fit is not a proof of infeasibility.
        pass
    for state in states:
        witness = witness_for(state+nuisance, observed, refs)
        if witness is not None:
            return witness
    return None


def split_box(box):
    widths = tuple((hi-lo)/(prior[1]-prior[0])
                   for (lo, hi), prior in zip(box, PRIORS, strict=True))
    index = max(range(len(box)), key=lambda i: (widths[i], -i))
    if widths[index] == 0:
        return None
    lo, hi = box[index]
    mid = (lo+hi)/2
    return index, mid, (box[:index]+((lo, mid),)+box[index+1:],
                        box[:index]+((mid, hi),)+box[index+1:])


def search_tree(root, observed, refs, budget):
    a.need(type(budget) is int and 0 <= budget <= MAX_NODES, "node budget")
    nodes = 0

    def visit(box, depth):
        nonlocal nodes
        if nodes >= budget:
            return {"kind": "UNRESOLVED", "reason": "BUDGET"}
        nodes += 1
        reason = prune_reason(box, observed, refs)
        if reason is not None:
            return {"kind": "PRUNED", "reason": reason}
        split = split_box(box)
        if depth >= MAX_DEPTH or split is None:
            return {"kind": "UNRESOLVED", "reason": "DEPTH" if depth >= MAX_DEPTH else "POINT"}
        index, mid, children = split
        return {"kind": "SPLIT", "coordinate": NAMES[index], "mid": a.q(mid),
                "children": [visit(child, depth+1) for child in children]}

    return visit(root, 0), nodes


def verify_tree(root, observed, refs, budget, tree):
    """Validate an exact cover and every exclusion, without trusting search."""
    a.need(type(budget) is int and 0 <= budget <= MAX_NODES, "node budget")
    nodes = 0
    frontier = []

    def visit(box, depth, proof):
        nonlocal nodes
        a.need(type(proof) is dict and depth <= MAX_DEPTH, "invalid proof depth")
        kind = proof.get("kind")
        if kind == "UNRESOLVED" and proof.get("reason") == "BUDGET":
            a.need(set(proof) == {"kind", "reason"} and nodes >= budget,
                   "premature budget stop")
            frontier.append(box)
            return
        a.need(nodes < budget, "evaluated node budget exceeded")
        nodes += 1
        if kind == "PRUNED":
            a.need(set(proof) == {"kind", "reason"}, "prune schema")
            reason = prune_reason(box, observed, refs)
            a.need(reason is not None and proof["reason"] == reason, "invalid prune evidence")
            return
        split = split_box(box)
        if kind == "UNRESOLVED":
            a.need(set(proof) == {"kind", "reason"} and
                   ((proof["reason"] == "DEPTH" and depth == MAX_DEPTH) or
                    (proof["reason"] == "POINT" and split is None)),
                   "invalid unresolved leaf")
            frontier.append(box)
            return
        a.need(kind == "SPLIT" and set(proof) == {"kind", "coordinate", "mid", "children"}
               and depth < MAX_DEPTH and split is not None, "invalid split schema")
        index, mid, children = split
        a.need(proof["coordinate"] == NAMES[index] and proof["mid"] == a.q(mid) and
               type(proof["children"]) is list and len(proof["children"]) == 2,
               "incomplete split coverage")
        for child, certificate in zip(children, proof["children"], strict=True):
            visit(child, depth+1, certificate)

    visit(root, 0, tree)
    return frontier, nodes


def outer_from_frontier(frontier, baseline):
    if not frontier:
        return None
    hull = tuple((min(box[i][0] for box in frontier), max(box[i][1] for box in frontier))
                 for i in range(4))
    if baseline is not None and baseline["normalized_bounds"] is not None:
        clipped = tuple(intersection(x, tuple(map(F, y))) for x, y in
                        zip(hull, baseline["normalized_bounds"], strict=True))
        if all(lo <= hi for lo, hi in clipped):
            hull = clipped
    return encode_box(hull)


def common(record, budget, baseline):
    return {"scope": SCOPE, "record_sha256": sha(canonical(record)), "node_budget": budget,
            "H_status": None if baseline is None else baseline["status"], **NEGATIVE}


def solve(record, profile="UNVERIFIED", budget=MAX_NODES):
    a.need(type(profile) is str and profile in ("UNVERIFIED", h.BOUNDED), "unknown reference profile")
    a.need(type(budget) is int and 0 <= budget <= MAX_NODES, "node budget")
    _, observed, refs = h.parse(record)
    if profile == "UNVERIFIED":
        return {**common(record, budget, None), "status": UNCALIBRATED,
                "conditional_joint_witness_verified": False, "nodes": 0,
                "outer_bounds": encode_box((h.PRIOR,)*4), "certificate": None}
    root, contradiction = root_box(refs)
    baseline = h.estimate(record, h.BOUNDED)
    result = common(record, budget, baseline)
    if contradiction is not None:
        return {**result, "status": EXCLUDED, "conditional_joint_witness_verified": False,
                "nodes": 0, "outer_bounds": None, "certificate": contradiction}
    witness = propose(root, observed, refs, baseline) if budget else None
    if witness is not None:
        bounds = baseline["normalized_bounds"] or encode_box((h.PRIOR,)*4)
        x = tuple(map(F, witness["world"][:4]))
        a.need(all(F(lo) <= v <= F(hi) for v, (lo, hi) in zip(x, bounds, strict=True)),
               "H outer bound contradicts certified witness")
        a.need(baseline["normalized_bounds"] is not None, "H rejects certified witness")
        return {**result, "status": WITNESS, "conditional_joint_witness_verified": True,
                "nodes": 0, "outer_bounds": bounds,
                "certificate": {"kind": "WITNESS", "witness": witness}}
    tree, count = search_tree(root, observed, refs, budget)
    frontier, checked = verify_tree(root, observed, refs, budget, tree)
    a.need(count == checked, "proof node count")
    return {**result, "status": UNKNOWN if frontier else EXCLUDED,
            "conditional_joint_witness_verified": False, "nodes": count,
            "outer_bounds": outer_from_frontier(frontier, baseline),
            "certificate": {"kind": "COVER", "root": encode_box(root),
                            "tree": tree, "unresolved_leaves": len(frontier)}}


def verify(record, result, profile="UNVERIFIED", budget=MAX_NODES):
    """Reconstruct admission from a proposed result; reject all self-attestation."""
    a.need(type(profile) is str and profile in ("UNVERIFIED", h.BOUNDED), "unknown reference profile")
    a.need(type(budget) is int and 0 <= budget <= MAX_NODES, "node budget")
    a.need(type(result) is dict and all(type(result.get(k)) is type(v) and result[k] == v
                                      for k, v in NEGATIVE.items()), "negative evidence changed")
    _, observed, refs = h.parse(record)
    baseline = None if profile == "UNVERIFIED" else h.estimate(record, h.BOUNDED)
    metadata = common(record, budget, baseline)
    a.need(all(type(result.get(k)) is type(v) and result[k] == v
               for k, v in metadata.items()), "record or budget identity mismatch")
    a.need(set(result) == set(metadata)|{"status", "conditional_joint_witness_verified", "nodes",
                                         "outer_bounds", "certificate"}, "result schema")
    cert = result["certificate"]
    if profile == "UNVERIFIED":
        expected = {**metadata, "status": UNCALIBRATED, "conditional_joint_witness_verified": False,
                    "nodes": 0, "outer_bounds": encode_box((h.PRIOR,)*4), "certificate": None}
    else:
        root, contradiction = root_box(refs)
        if contradiction is not None:
            expected = {**metadata, "status": EXCLUDED, "conditional_joint_witness_verified": False,
                        "nodes": 0, "outer_bounds": None, "certificate": contradiction}
        elif type(cert) is dict and cert.get("kind") == "WITNESS":
            a.need(budget > 0 and set(cert) == {"kind", "witness"}, "witness certificate schema")
            witness = cert["witness"]
            world = tuple(a.decode(v) for v in witness["world"])
            computed = witness_for(world, observed, refs)
            a.need(computed is not None and computed == witness, "invalid compatibility witness")
            bounds = baseline["normalized_bounds"]
            a.need(bounds is not None and all(F(lo) <= v <= F(hi)
                   for v, (lo, hi) in zip(world[:4], bounds, strict=True)), "H enclosure conflict")
            expected = {**metadata, "status": WITNESS, "conditional_joint_witness_verified": True,
                        "nodes": 0, "outer_bounds": bounds, "certificate": cert}
        else:
            a.need(type(cert) is dict and cert.get("kind") == "COVER" and
                   set(cert) == {"kind", "root", "tree", "unresolved_leaves"} and
                   cert["root"] == encode_box(root), "cover root mismatch")
            frontier, nodes = verify_tree(root, observed, refs, budget, cert["tree"])
            a.need(cert["unresolved_leaves"] == len(frontier), "frontier count mismatch")
            expected = {**metadata, "status": UNKNOWN if frontier else EXCLUDED,
                        "conditional_joint_witness_verified": False, "nodes": nodes,
                        "outer_bounds": outer_from_frontier(frontier, baseline), "certificate": cert}
    a.need(canonical(result) == canonical(expected), "result verdict or enclosure mismatch")
    return True
