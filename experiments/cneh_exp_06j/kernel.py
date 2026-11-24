"""Conditional decision acquisition over a verified continuous I enclosure."""
from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache
from itertools import permutations, product

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical, sha
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import solver as i

QUERIES = (2, 1, 3)
CUBE = tuple(product((0, 1), repeat=3))
FIXED = tuple(permutations(QUERIES))
SCOPE = "CONDITIONAL_SYNTHETIC_SAME_RECORD_THRESHOLD_REFERENCES"
HALF = F(1, 2)
NEGATIVE = dict(i.NEGATIVE)


def label(bits):
    return bits[1] if bits[0] == 0 else bits[2]


def cut(support, query, bit):
    j = QUERIES.index(query)
    return tuple(x for x in support if x[j] == bit)


def useful(support, query):
    j = QUERIES.index(query)
    return any(label(x) != label(y) and x[j] != y[j]
               for x in support for y in support)


@lru_cache(maxsize=4096)
def optimum(support, remaining):
    """Exact minimax cost to label unanimity, not full identification."""
    if not support:
        return None, None
    if len({label(x) for x in support}) == 1:
        return 0, None
    best = None, None
    for query in remaining:
        if not useful(support, query):
            continue
        rest = tuple(q for q in remaining if q != query)
        children = [cut(support, query, bit) for bit in (0, 1)]
        values = [optimum(child, rest)[0] for child in children if child]
        if len(values) != 2 or any(v is None for v in values):
            continue
        cost = 1+max(values)
        if best[0] is None or cost < best[0]:
            best = cost, query
    return best


def bounds_support(result):
    choices = []
    for q in QUERIES:
        lo, hi = map(F, result["outer_bounds"][q])
        a.need(0 <= lo <= hi <= 1, "invalid outer bounds")
        choices.append(tuple(bit for bit, possible in
                             ((0, lo < HALF), (1, hi >= HALF)) if possible))
    return tuple(product(*choices))


def bit_at(world, query):
    return int(world[query] >= HALF)


def joint_witness(record, original, transcript):
    _, observed, refs = h.parse(record)
    world = tuple(map(F, original["certificate"]["witness"]["world"]))
    values = list(world)
    for query, bit in transcript:
        if bit_at(values, query) != bit:
            values[query] = HALF if bit else HALF-F(1, 2**40)
    if any(bit_at(values, q) != bit for q, bit in transcript):
        return None
    return i.witness_for(tuple(values), observed, refs)


def validate_inputs(record, original, profile, budget, mode):
    a.need(type(budget) is int and 0 <= budget <= 2, "query budget")
    a.need(mode in ("ADAPTIVE", "PASSIVE") or
           type(mode) is tuple and mode in FIXED, "policy mode")
    a.need(i.verify(record, original, profile), "unverified I result")


def state(record, original, budget, mode, history):
    """Evaluate a prefix from original proof and observed bits only."""
    if original["status"] != i.WITNESS:
        return {"disposition": "ABSTAIN", "reason": original["status"],
                "support": [], "witness": None, "label": None, "query": None}
    support = bounds_support(original)
    for q, bit in history:
        support = cut(support, q, bit)
    witness = joint_witness(record, original, history) if support else None
    result = {"support": [list(x) for x in support], "witness": witness,
              "label": None, "query": None}
    if not support or witness is None:
        return {**result, "disposition": "ABSTAIN", "reason": "NO_JOINT_WITNESS"}
    labels = {label(x) for x in support}
    if len(labels) == 1:
        return {**result, "disposition": "CERTIFIED_CONDITIONAL_LABEL",
                "reason": "UNIVERSAL_OUTER_LABEL", "label": min(labels)}
    if mode == "PASSIVE" or len(history) == budget:
        return {**result, "disposition": "ABSTAIN", "reason": "BUDGET_OR_PASSIVE"}
    used = {q for q, _ in history}
    remaining = tuple(q for q in QUERIES if q not in used)
    if mode == "ADAPTIVE":
        cost, query = optimum(support, remaining)
        if cost is None or cost > budget-len(history):
            return {**result, "disposition": "ABSTAIN", "reason": "NO_BOUNDED_PLAN"}
    else:
        query = next((q for q in mode if q in remaining and
                      len({x[QUERIES.index(q)] for x in support}) == 2), None)
        if query is None:
            return {**result, "disposition": "ABSTAIN", "reason": "NO_SPLITTING_QUERY"}
    return {**result, "disposition": "QUERY", "reason": "AMBIGUOUS_LABEL", "query": query}


def assemble(record, original, profile, budget, mode, history, terminal):
    return {"scope": SCOPE, "record_sha256": sha(canonical(record)),
            "I_sha256": sha(canonical(original)), "profile": profile,
            "budget": budget, "mode": mode if type(mode) is str else list(mode),
            "transcript": [{"query": q, "bit": b} for q, b in history],
            "spent": len(history), **terminal, **NEGATIVE}


def execute(record, original, profile, budget, mode, observe):
    validate_inputs(record, original, profile, budget, mode)
    history = []
    while True:
        current = state(record, original, budget, mode, history)
        if current["disposition"] != "QUERY":
            return assemble(record, original, profile, budget, mode, history, current)
        query = current["query"]
        bit = observe(query)
        a.need(type(bit) is int and bit in (0, 1), "invalid comparator bit")
        history.append((query, bit))


def verify(record, original, profile, budget, mode, receipt):
    validate_inputs(record, original, profile, budget, mode)
    a.need(type(receipt) is dict and type(receipt.get("transcript")) is list and
           len(receipt["transcript"]) <= budget, "transcript schema or budget")
    history = []
    for item in receipt["transcript"]:
        a.need(type(item) is dict and set(item) == {"query", "bit"} and
               type(item["query"]) is int and item["query"] in QUERIES and
               type(item["bit"]) is int and item["bit"] in (0, 1), "invalid transcript item")
        current = state(record, original, budget, mode, history)
        a.need(current["disposition"] == "QUERY" and current["query"] == item["query"],
               "unexpected or repeated query")
        history.append((item["query"], item["bit"]))
    terminal = state(record, original, budget, mode, history)
    a.need(terminal["disposition"] != "QUERY", "premature terminal receipt")
    expected = assemble(record, original, profile, budget, mode, history, terminal)
    a.need(canonical(receipt) == canonical(expected), "receipt identity or proof mismatch")
    return True
