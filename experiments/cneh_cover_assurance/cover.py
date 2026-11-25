"""Bounded proof-carrying outer cover for the frozen H/I continuous model."""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache
import math

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical, sha
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import solver as legacy

SCOPE = "OUTER_COMPLETENESS_CONDITIONAL_ON_FROZEN_H_CONTINUOUS_MODEL"
MAX_NODES = 63
MAX_DEPTH = 6
EXP_GRID = 2**72
ROW_GRID = 2**56
STATE_GRID = 2**48
P_GRID = 2**32
SWEEPS = 2
PRIOR = legacy.PRIORS
NEGATIVE = dict(legacy.NEGATIVE)
OUTER = "OUTER_COVER_ONLY"
EXCLUDED = "CERTIFIED_INFEASIBLE"
UNCALIBRATED = "CALIBRATION_UNVERIFIED"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def singleton(x):
    return F(x), F(x)


def plus(x, y):
    return x[0]+y[0], x[1]+y[1]


def minus(x, y):
    return x[0]-y[1], x[1]-y[0]


def times(x, y):
    p = (x[0]*y[0], x[0]*y[1], x[1]*y[0], x[1]*y[1])
    return min(p), max(p)


def total(xs):
    lo = hi = F(0)
    for x in xs:
        lo += x[0]
        hi += x[1]
    return lo, hi


def outward(x, grid, pad=0):
    need(x[0] <= x[1], "invalid interval")
    return F(math.floor(x[0]*grid)-pad, grid), F(math.ceil(x[1]*grid)+pad, grid)


def box_wire(box):
    return [[a.q(lo), a.q(hi)] for lo, hi in box]


@lru_cache(maxsize=512)
def decay(u):
    """Independent alternating-series enclosure of exp(-u), u in [0,100]."""
    need(type(u) is F and 0 <= u <= 100, "decay domain")
    reductions = 0
    while u > F(1, 2):
        u /= 2
        reductions += 1
    term = partial = F(1)
    for k in range(1, 25):
        term *= -u/k
        partial += term
    # Even partial is an upper bound; next odd partial is a lower bound.
    bound = outward((partial-term*u/25, partial), EXP_GRID)
    for _ in range(reductions):
        bound = outward((bound[0]**2, bound[1]**2), EXP_GRID)
    return bound


def rate_range(elapsed, tau):
    need(0 < tau[0] <= tau[1], "positive rate denominator")
    return (decay(elapsed[1]/tau[0])[0], decay(elapsed[0]/tau[1])[1])


@lru_cache(maxsize=128)
def affine_rows(nuisance):
    gain, offset, drift, gamma, delay, tau = nuisance
    c0 = minus(singleton(120), times(singleton(20), decay(F(5, 2))))
    z = times(singleton(F(357, 100)), decay(F(93, 25)))
    block = z[0]/(1+z[0]), z[1]/(1+z[1])
    rows = []
    for t in h.TIMES:
        elapsed = (F(t)+delay[0], F(t)+delay[1]+h.J)
        ew = rate_range(elapsed, singleton(200))
        ea = rate_range(elapsed, singleton(F(5, 2)))
        en = rate_range(elapsed, tau)
        eg = rate_range(elapsed, singleton(6))
        c = plus(plus(times(gain, minus(c0, times(singleton(20), ew))), offset),
                 times(drift, singleton(F(t, 120))))
        coeffs = (times(singleton(24), ew), times(singleton(-6), ea),
                  times(times(times(singleton(-6), block), gamma), en),
                  times(singleton(5), eg))
        rows.append((outward(c, ROW_GRID, 2), *(outward(times(gain, x), ROW_GRID, 2)
                                               for x in coeffs)))
    return tuple(rows)


def preconditioner(rows):
    midpoint = [[(lo+hi)/2 for lo, hi in rows[h.TIMES.index(t)][1:]]
                for t in h.PRIMARY]
    try:
        inverse = a.inverse(midpoint)
        candidate = tuple(tuple(F(round(v*P_GRID), P_GRID) for v in row)
                          for row in inverse)
    except ValueError:
        candidate = ()
    if not candidate or any(abs(v) > 128 for row in candidate for v in row):
        return tuple((F(0),)*4 for _ in range(4))
    return candidate


def compile_system(rows, p, observed):
    targets = tuple((y-h.E, y+h.E) for y in observed)
    idx = tuple(h.TIMES.index(t) for t in h.PRIMARY)
    centered = tuple(minus(targets[k], rows[k][0]) for k in idx)
    rhs = tuple(total(times(singleton(p[i][j]), centered[j]) for j in range(4))
                for i in range(4))
    error = tuple(tuple(minus(singleton(int(i == k)), total(
        times(singleton(p[i][j]), rows[idx[j]][k+1]) for j in range(4)))
        for k in range(4)) for i in range(4))
    return targets, rhs, error


def contract(box, rhs, error):
    current = box
    for sweep in range(SWEEPS):
        candidates = tuple(outward(plus(rhs[i], total(
            times(error[i][k], current[k]) for k in range(4))), STATE_GRID)
            for i in range(4))
        refined = tuple((max(lo, lo2), min(hi, hi2))
                        for (lo, hi), (lo2, hi2) in zip(current, candidates, strict=True))
        for i, (lo, hi) in enumerate(refined):
            if lo > hi:
                return None, {"kind": "EMPTY_CONTRACTION", "sweep": sweep,
                              "coordinate": i, "intersection": [a.q(lo), a.q(hi)]}
        current = refined
    return current, None


def direct_exclusion(box, rows, targets):
    for t, row, target in zip(h.TIMES, rows, targets, strict=True):
        pred = plus(row[0], total(times(coef, x) for coef, x in
                                  zip(row[1:], box, strict=True)))
        if pred[1] < target[0] or target[1] < pred[0]:
            return {"kind": "DISJOINT_SAMPLE", "t_ms": t,
                    "prediction": box_wire((pred,))[0],
                    "measurement": box_wire((target,))[0]}
    return None


def search(physical, rows, p, observed, budget):
    targets, rhs, error = compile_system(rows, p, observed)
    nodes = 0
    frontier = []

    def retain(box, reason):
        frontier.append(box)
        return {"kind": "UNRESOLVED", "reason": reason, "box": box_wire(box)}

    def visit(box, depth):
        nonlocal nodes
        if nodes == budget:
            return retain(box, "BUDGET")
        nodes += 1
        refined, proof = contract(box, rhs, error)
        if proof is not None:
            return proof
        proof = direct_exclusion(refined, rows, targets)
        if proof is not None:
            return {"kind": "EXCLUDED", "contracted": box_wire(refined), "proof": proof}
        if depth == MAX_DEPTH:
            return retain(refined, "DEPTH")
        widths = [hi-lo for lo, hi in refined]
        k = max(range(4), key=lambda j: (widths[j], -j))
        if widths[k] == 0:
            return retain(refined, "POINT")
        lo, hi = refined[k]
        mid = (lo+hi)/2
        left = refined[:k]+((lo, mid),)+refined[k+1:]
        right = refined[:k]+((mid, hi),)+refined[k+1:]
        return {"kind": "SPLIT", "contracted": box_wire(refined),
                "coordinate": k, "mid": a.q(mid),
                "children": [visit(left, depth+1), visit(right, depth+1)]}

    return visit(physical, 0), tuple(frontier), nodes


def hull(frontier):
    if not frontier:
        return None
    return tuple((min(box[j][0] for box in frontier), max(box[j][1] for box in frontier))
                 for j in range(4))


def result(record, profile, budget, status, root, rows, p, tree, frontier, nodes):
    bound = hull(frontier)
    return {"scope": SCOPE, "record_sha256": sha(canonical(record)), "profile": profile,
            "node_budget": budget, "nodes": nodes, "status": status,
            "root": None if root is None else box_wire(root),
            "rows": None if rows is None else [box_wire(row) for row in rows],
            "preconditioner": None if p is None else [[a.q(v) for v in row] for row in p],
            "tree": tree, "frontier": [box_wire(box) for box in frontier],
            "physical_hull": None if bound is None else box_wire(bound),
            "max_width": None if bound is None else a.q(max(hi-lo for lo, hi in bound)),
            "joint_existence_established": False, **NEGATIVE}


def solve(record, profile="UNVERIFIED", budget=MAX_NODES):
    need(type(profile) is str and profile in ("UNVERIFIED", h.BOUNDED), "reference profile")
    need(type(budget) is int and 0 <= budget <= MAX_NODES, "node budget")
    _, observed, refs = h.parse(record)
    if profile == "UNVERIFIED":
        return result(record, profile, budget, UNCALIBRATED, PRIOR, None, None, None,
                      (PRIOR[:4],), 0)
    root, contradiction = legacy.root_box(refs)
    if contradiction is not None:
        return result(record, profile, budget, EXCLUDED, None, None, None,
                      {"kind": "REFERENCE_EMPTY", "proof": contradiction}, (), 0)
    rows = affine_rows(root[4:])
    p = preconditioner(rows)
    tree, frontier, nodes = search(root[:4], rows, p, observed, budget)
    return result(record, profile, budget, OUTER if frontier else EXCLUDED,
                  root, rows, p, tree, frontier, nodes)
