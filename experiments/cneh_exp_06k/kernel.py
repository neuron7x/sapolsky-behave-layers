"""Exact finite conditional decisions under explicitly correlated reference faults."""
from __future__ import annotations

from functools import lru_cache
from itertools import permutations, product
import json

QUERIES = ("C", "T2", "T1", "T3")
FIXED = tuple(permutations(QUERIES))
MODELS = ("SHARED", "INDEPENDENT")
SCOPE = "CONDITIONAL_FINITE_CORRELATED_REFERENCE_FAULT_MODEL"
WORLDS = tuple(product((0, 1), repeat=6))
ALL = (1 << len(WORLDS))-1


def need(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def label(world):
    return world[2] if world[0] else world[1]


def response(world, query):
    if query == "C":
        return world[3]
    j = QUERIES.index(query)-1
    return world[j] ^ world[j+3]


LABEL_ONE = sum(1 << n for n, w in enumerate(WORLDS) if label(w))
ONE = tuple(sum(1 << n for n, w in enumerate(WORLDS) if response(w, q))
            for q in QUERIES)


def validate(model, signs, polarity, budget, mode):
    need(type(model) is str and model in MODELS, "model")
    need(type(signs) is int and 0 <= signs <= 255, "sign mask")
    need(type(polarity) is int and 1 <= polarity <= 3, "polarity mask")
    need(type(budget) is int and 0 <= budget <= 4, "budget")
    need((type(mode) is str and mode in ("ADAPTIVE", "PASSIVE")) or
         (type(mode) is tuple and mode in FIXED), "mode")


def initial(model, signs, polarity):
    validate(model, signs, polarity, 0, "PASSIVE")
    result = 0
    for n, (s, l, r, es, el, er) in enumerate(WORLDS):
        if signs & (1 << (4*s+2*l+r)) and polarity & (1 << es):
            if model == "INDEPENDENT" or es == el == er:
                result |= 1 << n
    return result


def unanimous(support):
    if not support:
        return None
    if not support & LABEL_ONE:
        return 0
    if not support & (ALL ^ LABEL_ONE):
        return 1
    return None


def cut(support, query, bit):
    mask = ONE[QUERIES.index(query)]
    return support & (mask if bit else ALL ^ mask)


@lru_cache(maxsize=65536)
def optimum(support, remaining):
    if not support:
        return None, None
    if unanimous(support) is not None:
        return 0, None
    best = None, None
    for j, query in enumerate(QUERIES):
        if not remaining & (1 << j):
            continue
        zero, one = cut(support, query, 0), cut(support, query, 1)
        if not zero or not one:
            continue
        rest = remaining ^ (1 << j)
        x, y = optimum(zero, rest)[0], optimum(one, rest)[0]
        if x is None or y is None:
            continue
        cost = 1+max(x, y)
        if best[0] is None or cost < best[0]:
            best = cost, query
    return best


def state(support, remaining, budget, mode):
    if not support:
        return "ABSTAIN", "EMPTY_SUPPORT", None, None
    value = unanimous(support)
    if value is not None:
        return "CERTIFIED_CONDITIONAL_LABEL", "UNIVERSAL_LABEL", value, None
    if budget == 0 or mode == "PASSIVE":
        return "ABSTAIN", "BUDGET_OR_PASSIVE", None, None
    if mode == "ADAPTIVE":
        cost, query = optimum(support, remaining)
        if cost is None or cost > budget:
            return "ABSTAIN", "NO_BOUNDED_PLAN", None, None
    else:
        query = next((q for q in mode if remaining & (1 << QUERIES.index(q))
                      and cut(support, q, 0) and cut(support, q, 1)), None)
        if query is None:
            return "ABSTAIN", "NO_SPLITTING_QUERY", None, None
    return "QUERY", "AMBIGUOUS_LABEL", None, query


def advance(support, remaining, budget, mode, item):
    need(type(item) is list and len(item) == 2, "transcript item")
    query, bit = item
    need(type(query) is str and query in QUERIES and
         type(bit) is int and bit in (0, 1), "transcript types")
    disposition, _, _, expected = state(support, remaining, budget, mode)
    need(disposition == "QUERY" and query == expected, "unexpected query")
    result = cut(support, query, bit)
    need(bool(result), "incompatible observation")
    return result, remaining ^ (1 << QUERIES.index(query))


def assemble(model, signs, polarity, budget, mode, transcript, support, terminal):
    disposition, reason, value, query = terminal
    need(disposition != "QUERY" and query is None, "premature terminal")
    return {"scope": SCOPE, "model": model, "sign_mask": signs,
            "polarity_mask": polarity, "budget": budget,
            "mode": mode if type(mode) is str else list(mode),
            "transcript": [list(item) for item in transcript],
            "support": [n for n in range(64) if support & (1 << n)],
            "spent": len(transcript), "disposition": disposition,
            "reason": reason, "label": value,
            "scientific_promotion_authorized": False}


def replay(model, signs, polarity, budget, mode, observed):
    validate(model, signs, polarity, budget, mode)
    need(type(observed) is list and len(observed) <= budget, "transcript budget")
    support, remaining = initial(model, signs, polarity), 15
    for j, item in enumerate(observed):
        support, remaining = advance(support, remaining, budget-j, mode, item)
    terminal = state(support, remaining, budget-len(observed), mode)
    return assemble(model, signs, polarity, budget, mode, observed, support, terminal)


def execute(model, signs, polarity, budget, mode, observe):
    validate(model, signs, polarity, budget, mode)
    support, remaining = initial(model, signs, polarity), 15
    history = []
    while True:
        terminal = state(support, remaining, budget-len(history), mode)
        if terminal[0] != "QUERY":
            return assemble(model, signs, polarity, budget, mode, history, support, terminal)
        query = terminal[3]
        item = [query, observe(query)]
        support, remaining = advance(support, remaining, budget-len(history), mode, item)
        history.append(item)


def verify(model, signs, polarity, budget, mode, observed, receipt):
    expected = replay(model, signs, polarity, budget, mode, observed)
    need(type(receipt) is dict and canonical(receipt) == canonical(expected),
         "receipt identity or proof mismatch")
    return True
