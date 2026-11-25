"""Independent reconstruction of every cover proof obligation.

Uses frozen C/I outward interval primitives rather than the producer's
alternating-series or contraction/search implementation. This is independent
code reconstruction within the same project, not external replication.
"""
from __future__ import annotations

from fractions import Fraction as F

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical, sha
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import solver as old
from experiments.cneh_cover_assurance import cover as c

MAX_ITEMS = 20000
MAX_DEPTH = 24
MAX_STRING = 256


def bounded(value):
    """Bound the in-memory JSON-shaped proof before serializing it."""
    stack = [(value, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        a.need(count <= MAX_ITEMS and depth <= MAX_DEPTH, "proof resource budget")
        if type(item) is dict:
            a.need(all(type(k) is str and len(k) <= MAX_STRING for k in item),
                   "proof key schema")
            a.need(len(item) <= MAX_ITEMS-count-len(stack), "proof object budget")
            stack.extend((v, depth+1) for v in item.values())
        elif type(item) is list:
            a.need(len(item) <= MAX_ITEMS-count-len(stack), "proof list budget")
            stack.extend((v, depth+1) for v in item)
        elif type(item) is str:
            a.need(len(item) <= MAX_STRING, "proof string budget")
        else:
            a.need(item is None or type(item) is bool or
                   type(item) is int and abs(item) <= 2**31-1, "proof scalar schema")


def encode(box):
    return [a.encode(x) for x in box]


def overlap(*ranges):
    return max(x[0] for x in ranges), min(x[1] for x in ranges)


def span(y):
    return y-h.R, y+h.R


def reconstruct_root(refs):
    a.need(type(refs) is dict and set(refs) == set(h.REFS), "reference roster")
    # Independent projection of b from three linear reference strips.
    constraints = (old.PRIORS[5], span(refs["zero_pA"]),
                   a.sub(span(refs["span_pA"]), a.mul(a.point(128), h.GAIN)),
                   a.sub(span(refs["late_zero_pA"]), a.mul(a.point(2), old.PRIORS[6])))
    b = overlap(*constraints)
    scalar_ranges = (
        ("offset", b, constraints),
        ("gamma", overlap(h.GAMMA, span(refs["gamma"])), (h.GAMMA, span(refs["gamma"]))),
        ("delay", overlap(h.DELAY, span(refs["delay_ms"])), (h.DELAY, span(refs["delay_ms"]))),
        ("tau", overlap(h.TAU, span(refs["tau_ms"])), (h.TAU, span(refs["tau_ms"]))),
    )
    for name, interval, sources in scalar_ranges:
        if interval[0] > interval[1]:
            return None, {"kind": "JOINT_REFERENCE_EMPTY", "coordinate": name,
                          "lower": a.q(interval[0]), "upper": a.q(interval[1]),
                          "constraints": encode(sources)}
    g = overlap(h.GAIN, a.div(a.sub(span(refs["span_pA"]), b), a.point(128)))
    d = overlap(old.PRIORS[6], a.div(a.sub(span(refs["late_zero_pA"]), b), a.point(2)))
    a.need(g[0] <= g[1] and d[0] <= d[1], "reference projection contradiction")
    return (h.PRIOR,)*4+(g, b, d, scalar_ranges[1][1],
                          scalar_ranges[2][1], scalar_ranges[3][1]), None


def decode_rows(wire, root):
    a.need(type(wire) is list and len(wire) == len(h.TIMES), "row roster")
    gain, b, drift, gamma, delay, tau = root[4:]
    rows = []
    for t, wire_row in zip(h.TIMES, wire, strict=True):
        a.need(type(wire_row) is list and len(wire_row) == 5, "row dimension")
        row = []
        for cell in wire_row:
            a.need(type(cell) is list and len(cell) == 2, "coefficient interval")
            lo, hi = map(a.decode, cell)
            a.need(-256 <= lo <= hi <= 256 and
                   all((v*c.ROW_GRID).denominator == 1 for v in (lo, hi)),
                   "coefficient interval domain")
            row.append((lo, hi))
        base, coeffs = old.coefficients(t, gamma, delay, tau, (F(0), h.J))
        expected = (a.add(a.add(a.mul(gain, base), b),
                          a.mul(drift, a.point(F(t, 120)))),
                    *(a.mul(gain, coef) for coef in coeffs))
        for actual, reference in zip(row, expected, strict=True):
            a.need(actual[0] <= reference[0] <= reference[1] <= actual[1],
                   "independent affine enclosure not contained")
        rows.append(tuple(row))
    return tuple(rows)


def decode_preconditioner(wire):
    a.need(type(wire) is list and len(wire) == 4, "preconditioner dimensions")
    p = []
    for row in wire:
        a.need(type(row) is list and len(row) == 4, "preconditioner row")
        values = tuple(a.decode(v) for v in row)
        a.need(all(abs(v) <= 128 and (v*c.P_GRID).denominator == 1 for v in values),
               "preconditioner rational domain")
        p.append(values)
    return tuple(p)


def transformed(rows, p, observed):
    targets = [(y-h.E, y+h.E) for y in observed]
    primary = [h.TIMES.index(t) for t in h.PRIMARY]
    selected_rows = [rows[k] for k in primary]
    y = [a.sub(targets[k], rows[k][0]) for k in primary]

    def dot(row, column):
        return a.isum(a.mul(a.point(v), x) for v, x in zip(row, column, strict=True))

    rhs = tuple(dot(row, y) for row in p)
    errors = tuple(tuple(a.sub(a.point(int(i == j)),
                        dot(p[i], [row[j+1] for row in selected_rows]))
                   for j in range(4)) for i in range(4))
    return targets, rhs, errors


def reconstruct_tree(initial, rows, p, observed, budget):
    """Independently compute a complete proof tree, never echo caller nodes."""
    targets, rhs, errors = transformed(rows, p, observed)
    count = 0
    leaves = []

    def unresolved(box, reason):
        leaves.append(box)
        return {"kind": "UNRESOLVED", "reason": reason, "box": encode(box)}

    def visit(parent, depth):
        nonlocal count
        if count >= budget:
            return unresolved(parent, "BUDGET")
        count += 1
        box = parent
        for sweep in range(c.SWEEPS):
            next_box = []
            for j in range(4):
                residual = a.add(rhs[j], a.isum(a.mul(errors[j][k], box[k])
                                               for k in range(4)))
                next_box.append(overlap(box[j], a.outward(residual, c.STATE_GRID)))
            for j, candidate in enumerate(next_box):
                if candidate[0] > candidate[1]:
                    return {"kind": "EMPTY_CONTRACTION", "sweep": sweep,
                            "coordinate": j, "intersection": a.encode(candidate)}
            box = tuple(next_box)
        for t, row, target in zip(h.TIMES, rows, targets, strict=True):
            predicted = a.isum([row[0]]+[a.mul(v, x) for v, x in zip(row[1:], box, strict=True)])
            if predicted[0] > target[1] or predicted[1] < target[0]:
                return {"kind": "EXCLUDED", "contracted": encode(box),
                        "proof": {"kind": "DISJOINT_SAMPLE", "t_ms": t,
                                  "prediction": a.encode(predicted),
                                  "measurement": a.encode(target)}}
        if depth >= c.MAX_DEPTH:
            return unresolved(box, "DEPTH")
        widths = tuple(hi-lo for lo, hi in box)
        index = widths.index(max(widths))
        if widths[index] == 0:
            return unresolved(box, "POINT")
        lo, hi = box[index]
        midpoint = a.midpoint(box[index])
        left, right = list(box), list(box)
        left[index], right[index] = (lo, midpoint), (midpoint, hi)
        return {"kind": "SPLIT", "contracted": encode(box), "coordinate": index,
                "mid": a.q(midpoint),
                "children": [visit(tuple(left), depth+1), visit(tuple(right), depth+1)]}

    return visit(initial, 0), tuple(leaves), count


def expected(record, profile, budget, status, root, rows, p, tree, frontier, nodes):
    bounds = None if not frontier else tuple(
        (min(x[j][0] for x in frontier), max(x[j][1] for x in frontier)) for j in range(4))
    return {"scope": c.SCOPE, "record_sha256": sha(canonical(record)), "profile": profile,
            "node_budget": budget, "nodes": nodes, "status": status,
            "root": None if root is None else encode(root),
            "rows": None if rows is None else [encode(row) for row in rows],
            "preconditioner": None if p is None else [[a.q(v) for v in row] for row in p],
            "tree": tree, "frontier": [encode(box) for box in frontier],
            "physical_hull": None if bounds is None else encode(bounds),
            "max_width": None if bounds is None else a.q(max(hi-lo for lo, hi in bounds)),
            "joint_existence_established": False, **c.NEGATIVE}


def verify(record, proof, profile="UNVERIFIED", budget=c.MAX_NODES):
    a.need(type(profile) is str and profile in ("UNVERIFIED", h.BOUNDED), "profile")
    a.need(type(budget) is int and 0 <= budget <= c.MAX_NODES, "node budget")
    a.need(type(proof) is dict, "proof object")
    bounded(proof)
    _, observed, refs = h.parse(record)
    if profile == "UNVERIFIED":
        out = expected(record, profile, budget, c.UNCALIBRATED, old.PRIORS,
                       None, None, None, (old.PRIORS[:4],), 0)
    else:
        root, contradiction = reconstruct_root(refs)
        if contradiction is not None:
            out = expected(record, profile, budget, c.EXCLUDED, None, None, None,
                           {"kind": "REFERENCE_EMPTY", "proof": contradiction}, (), 0)
        else:
            a.need("rows" in proof and "preconditioner" in proof, "missing coefficient proof")
            rows = decode_rows(proof["rows"], root)
            p = decode_preconditioner(proof["preconditioner"])
            tree, leaves, nodes = reconstruct_tree(root[:4], rows, p, observed, budget)
            out = expected(record, profile, budget, c.OUTER if leaves else c.EXCLUDED,
                           root, rows, p, tree, leaves, nodes)
    a.need(canonical(proof) == canonical(out), "cover certificate or disposition mismatch")
    return True
