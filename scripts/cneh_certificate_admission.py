"""Bounded, type-exact wire admission for frozen CNEH-I/J proof objects.

This is the admission boundary for new consumers, not a rewrite of historical
experiments. It checks the existing synthetic contract only. The arithmetic
trusted base is unchanged; no cryptographic issuer or scientific authority.
"""
from __future__ import annotations

import json

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import solver as i
from experiments.cneh_exp_06j import kernel as j
from scripts.cneh_promotion_gate import reject_positive_claims

MAX_BYTES = 256 * 1024
MAX_DEPTH = 32
MAX_ITEMS = 8192
MAX_STRING = 256
MAX_INT = 2**31-1


class CertificateError(ValueError):
    """Rejected or malformed evidence, not a scientific infeasibility verdict."""


def require(condition, reason):
    if not condition:
        raise CertificateError(reason)


def check_nesting(raw):
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            require(depth <= MAX_DEPTH, "wire depth budget")
        elif byte in (93, 125):
            depth -= 1
            require(depth >= 0, "invalid wire nesting")
    require(depth == 0 and not quoted, "incomplete wire object")


def pairs(items):
    value = {}
    for key, item in items:
        require(key not in value, "duplicate wire key")
        value[key] = item
    return value


def integer(token):
    require(len(token) <= 11, "wire integer length")
    value = int(token)
    require(abs(value) <= MAX_INT, "wire integer budget")
    return value


def reject_number(_):
    raise CertificateError("noninteger wire number")


def strict_load(raw):
    """Bound hostile serialized inputs before any expensive proof computation."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "wire byte budget")
    check_nesting(raw)
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs,
                           parse_int=integer, parse_float=reject_number,
                           parse_constant=reject_number)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CertificateError("invalid proof JSON") from exc
    require(type(value) is dict, "wire object required")
    stack = [value]
    count = 0
    while stack:
        item = stack.pop()
        count += 1
        require(count <= MAX_ITEMS, "wire item budget")
        if type(item) is dict:
            require(all(type(key) is str and len(key) <= MAX_STRING for key in item),
                    "wire key budget")
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
        elif type(item) is str:
            require(len(item) <= MAX_STRING, "wire string budget")
        else:
            require(item is None or type(item) in (bool, int), "wire scalar type")
    require(canonical(value) == raw, "noncanonical proof bytes")
    reject_positive_claims(value)
    return value


def exact_match(actual, expected, reason):
    # Python dict/list equality treats False == 0 and True == 1, including
    # nested values. Compare independently reconstructed serialized objects.
    require(canonical(actual) == canonical(expected), reason)


def verify_i_objects(record, result, profile, budget):
    require(type(profile) is str and profile in ("UNVERIFIED", h.BOUNDED),
            "reference profile")
    require(type(budget) is int and 0 <= budget <= i.MAX_NODES, "node budget")
    _, observed, refs = h.parse(record)
    if profile != "UNVERIFIED":
        root, contradiction = i.root_box(refs)
        cert = result.get("certificate")
        if contradiction is not None:
            exact_match(cert, contradiction, "reference contradiction differs")
        else:
            require(type(cert) is dict, "certificate object")
            if cert.get("kind") == "WITNESS":
                require(set(cert) == {"kind", "witness"} and budget > 0,
                        "witness envelope")
                witness = cert["witness"]
                require(type(witness) is dict and
                        set(witness) == {"world", "coordinate_order", "reference_errors", "samples"},
                        "witness schema")
                world = witness["world"]
                require(type(world) is list and len(world) == len(i.PRIORS),
                        "witness coordinate roster")
                computed = i.witness_for(tuple(a.decode(v) for v in world), observed, refs)
                require(computed is not None, "no compatible world")
                exact_match(cert, {"kind": "WITNESS", "witness": computed},
                            "type-exact witness differs")
            else:
                require(cert.get("kind") == "COVER", "unknown certificate kind")
                # Admit only the deterministic frozen solver's cover. Do not
                # echo the untrusted tree into the expected proof.
                tree, count = i.search_tree(root, observed, refs, budget)
                frontier, checked = i.verify_tree(root, observed, refs, budget, tree)
                require(count == checked, "reconstructed cover count")
                exact_match(cert, {"kind": "COVER", "root": i.encode_box(root),
                                   "tree": tree, "unresolved_leaves": len(frontier)},
                            "type-exact cover differs")
    require(i.verify(record, result, profile, budget) is True, "legacy semantic check failed")
    return True


def verify_i(record_raw, proof_raw, *, profile="UNVERIFIED", budget=i.MAX_NODES):
    """Return True only on bounded canonical and semantically rechecked I proof."""
    try:
        return verify_i_objects(strict_load(record_raw), strict_load(proof_raw), profile, budget)
    except (ValueError, KeyError, IndexError, TypeError, OverflowError,
            ZeroDivisionError, RecursionError) as exc:
        raise CertificateError("I certificate rejected: " + str(exc)) from exc


def verify_j(record_raw, proof_raw, receipt_raw, *, profile, budget, mode):
    """Check original I bytes before replaying the frozen J receipt."""
    try:
        require(type(mode) is str and mode in ("ADAPTIVE", "PASSIVE") or
                type(mode) is tuple and len(mode) == len(j.QUERIES) and
                all(type(q) is int for q in mode) and mode in j.FIXED,
                "type-exact policy mode")
        require(type(budget) is int and 0 <= budget <= 2, "query budget")
        record, proof, receipt = map(strict_load, (record_raw, proof_raw, receipt_raw))
        verify_i_objects(record, proof, profile, i.MAX_NODES)
        require(j.verify(record, proof, profile, budget, mode, receipt) is True,
                "J replay failed")
        return True
    except (ValueError, KeyError, IndexError, TypeError, OverflowError,
            ZeroDivisionError, RecursionError) as exc:
        raise CertificateError("J certificate rejected: " + str(exc)) from exc
