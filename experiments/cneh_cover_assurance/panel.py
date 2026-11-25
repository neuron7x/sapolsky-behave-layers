"""Frozen panel: exact compatible worlds, contradictions and cover mutations."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from itertools import product
import json

from experiments.cneh_exp_06c import algebra as a, fixtures
from experiments.cneh_exp_06f import panel as f
from experiments.cneh_exp_06f.run import canonical
from experiments.cneh_exp_06h import panel as hp, reference as h
from experiments.cneh_exp_06i import panel as ip, solver as old
from experiments.cneh_cover_assurance import cover as c, verifier as v

QUALIFIED = "PASS_CONDITIONAL_OUTER_COVER_ASSURANCE_ONLY"
STATES = ((F(0),)*4, (F(1),)*4, (F(0), F(1), F(0), F(1)),
          (F(1, 2)-F(1, 4096), F(1, 2), F(1, 2)+F(1, 4096), F(1, 2)))
NUISANCE = ((F(7, 8), F(-16), F(-1), F(1), F(0), F(100)),
            (F(9, 8), F(16), F(1), F(2), F(1), F(120)),
            ip.CLEAN_WORLDS[0])


def inside_cell(code, interval):
    k = code/h.STEP
    a.need(k.denominator == 1, "quantizer grid")
    lower, upper = code-h.STEP/2, code+h.STEP/2
    if k.numerator % 2 == 0:
        return lower <= interval[0] <= interval[1] <= upper
    return lower < interval[0] <= interval[1] < upper


def certify_world(record, world, signs, noise_scale):
    """Independent exact quantization and shared-reference compatibility."""
    _, observed, refs = h.parse(record)
    x = world[:4]
    gain, offset, drift, gamma, delay, tau = world[4:]
    reference_truths = (offset, 128*gain+offset, offset+2*drift, gamma, delay, tau)
    a.need(all(abs(refs[k]-truth) <= h.R for k, truth in
               zip(h.REFS, reference_truths, strict=True)), "reference truth excluded")
    for t, y, sign in zip(h.TIMES, observed, signs, strict=True):
        jitter = h.J if sign > 0 else F(0)
        noise = sign*noise_scale*h.EPS
        clean = hp.exact_channel(t, jitter, x, gain, gamma, delay, tau, offset, drift)
        shifted = a.add(clean, a.point(noise))
        a.need(inside_cell(y, shifted), "known noisy world not certified by quantizer cell")
        a.need(y-h.E <= clean[0] <= clean[1] <= y+h.E,
               "necessary relaxed cell excluded compatible world")


def boundary_record(x, nuisance, sign):
    gain, offset, drift, gamma, delay, tau = nuisance
    rows = []
    signs = tuple(sign*(-1)**k for k in range(len(h.TIMES)))
    for t, polarity in zip(h.TIMES, signs, strict=True):
        j = h.J if polarity > 0 else F(0)
        y = gain*fixtures.current(F(t)+delay+j, x, tau_n=tau,
                                   nmda_gain=gamma)+offset+drift*F(t, 120)
        q = f.quantize(y+polarity*h.EPS, h.STEP)
        rows.append({"t_ms": t, "current_pA": a.q(q)})
    reference_truths = (offset, 128*gain+offset, offset+2*drift, gamma, delay, tau)
    record = {"schema": h.SCHEMA, "voltage_mV": "-71/1", "samples": rows,
              "references": {k: a.q(f.quantize(y, h.STEP)) for k, y in
                             zip(h.REFS, reference_truths, strict=True)}}
    certify_world(record, x+nuisance, signs, F(1))
    return record


def contains(box, point):
    return len(box) == len(point) and all(F(lo) <= value <= F(hi)
                    for (lo, hi), value in zip(box, point, strict=True))


def subset(child, parent):
    return len(child) == len(parent) and all(
        F(a0) <= F(b0) <= F(b1) <= F(a1) for (a0, a1), (b0, b1) in
        zip(parent, child, strict=True))


def compatible_case(case_id, record, world, budgets):
    receipts = []
    for budget in budgets:
        proof = c.solve(record, h.BOUNDED, budget)
        a.need(v.verify(record, proof, h.BOUNDED, budget), "cover verifier")
        a.need(proof["status"] == c.OUTER and contains(proof["root"], world) and
               any(contains(box, world[:4]) for box in proof["frontier"]),
               "compatible world removed")
        a.need(proof["joint_existence_established"] is False, "outer cover overclaim")
        if budget == 1:
            a.need(F(proof["max_width"]) <= h.WIDTH, "one-node width target")
        if receipts:
            a.need(all(any(subset(box, parent) for parent in receipts[-1]["frontier"])
                       for box in proof["frontier"]), "budget refinement not nested")
        receipts.append(proof)
    return {"id": case_id, "record": record, "known_world": [a.q(q) for q in world],
            "proofs": receipts}


def legacy_case(index, world_index, stress):
    voltage, x = fixtures.truth(index)
    if stress:
        nuisance, sign = ip.STRESS_WORLDS[world_index]
        gain, gamma, delay, tau = nuisance
        offset, drift = F(16*sign), F(-sign)
        world = x+(gain, offset, drift, gamma, delay, tau)
        record, _, _ = hp.make_record(voltage, x, gain, gamma, delay, tau, offset, drift, sign)
        certify_world(record, world, tuple(sign*(-1)**k for k in range(len(h.TIMES))), F(3, 4))
    else:
        world = x+ip.CLEAN_WORLDS[world_index]
        record, _ = ip.clean_record(voltage, x, ip.CLEAN_WORLDS[world_index])
        certify_world(record, world, (0,)*len(h.TIMES), F(0))
    return compatible_case(["STRESS" if stress else "CLEAN", index, world_index],
                           record, world, (0, 1, 7))


def extreme_case(state_id, nuisance_id, sign):
    x, nuisance = STATES[state_id], NUISANCE[nuisance_id]
    record = boundary_record(x, nuisance, sign)
    budgets = (0, 1, 7, 63) if (state_id, nuisance_id, sign) in (
        (0, 0, -1), (3, 2, 1)) else (0, 1, 7)
    return compatible_case(["EXTREME", state_id, nuisance_id, sign], record,
                           x+nuisance, budgets)


def contradiction_case(case_id, record):
    proof = c.solve(record, h.BOUNDED, 1)
    a.need(v.verify(record, proof, h.BOUNDED, 1) and proof["status"] == c.EXCLUDED
           and proof["frontier"] == [] and proof["physical_hull"] is None,
           "infeasibility not independently certified")
    return {"id": case_id, "record": record, "proof": proof}


def subtle_case(sign):
    record, _ = ip.clean_record(F(-71), (F(1, 2),)*4, ip.CLEAN_WORLDS[0])
    target = record["samples"][h.TIMES.index(60)]
    target["current_pA"] = a.q(F(target["current_pA"])+sign)
    _, observed, refs = h.parse(record)
    root, contradiction = old.root_box(refs)
    a.need(contradiction is None and old.prune_reason(root, observed, refs) is None,
           "subtle contradiction legacy root premise")
    tree, nodes = old.search_tree(root, observed, refs, 1)
    frontier, checked = old.verify_tree(root, observed, refs, 1, tree)
    a.need(nodes == checked == 1 and bool(frontier), "legacy one-node not unresolved")
    return {**contradiction_case(["SUBTLE", sign], record),
            "legacy": {"status": old.UNKNOWN, "nodes": nodes, "tree": tree,
                       "unresolved_leaves": len(frontier)}}


def quantizer_panel():
    checks = []
    for k, side, perturbation in product(range(-4, 5), (-1, 1), (-1, 0, 1)):
        center = k*h.STEP
        y = center+side*h.STEP/2+perturbation*h.STEP/16
        code = f.quantize(y, h.STEP)
        a.need(inside_cell(center, (y, y)) == (code == center), "quantizer endpoint parity")
        if perturbation == 0:
            a.need((code == center) == (k % 2 == 0), "ties-to-even failure")
            a.need(abs(y-center) <= h.STEP/2, "closed relaxation lost a tie")
        for noise in (-h.EPS, h.EPS):
            clean = y-noise
            a.need(abs(clean-code) <= h.E, "noise/quantization relaxation unsound")
        checks.append([k, side, perturbation, a.q(code)])
    a.need(len(checks) == 54, "quantizer roster")
    return checks


def controls():
    record, _ = ip.clean_record(F(-71), (F(1, 2),)*4, ip.CLEAN_WORLDS[0])
    valid = c.solve(record, h.BOUNDED, 1)
    a.need(v.verify(record, valid, h.BOUNDED, 1) and valid["tree"]["kind"] == "SPLIT",
           "positive cover fixture")
    names = ("lost_frontier", "missing_child", "wrong_split", "boolean_coordinate",
             "reversed_bounds", "narrow_coefficient", "changed_preconditioner",
             "false_exclusion", "wrong_record", "wrong_profile", "wrong_budget",
             "wrong_count", "missing_row", "extra_field", "forged_authority",
             "false_existence", "float_node", "oversized_string", "malformed_scalar",
             "lost_root")
    dispositions = {}
    for name in names:
        proof = deepcopy(valid)
        if name == "lost_frontier":
            proof["frontier"].pop()
        elif name == "missing_child":
            proof["tree"]["children"].pop()
        elif name == "wrong_split":
            proof["tree"]["mid"] = "0/1"
        elif name == "boolean_coordinate":
            proof["tree"]["coordinate"] = bool(proof["tree"]["coordinate"])
        elif name == "reversed_bounds":
            proof["frontier"][0][0].reverse()
        elif name == "narrow_coefficient":
            proof["rows"][0][1] = ["0/1", "0/1"]
        elif name == "changed_preconditioner":
            proof["preconditioner"] = [["0/1"]*4 for _ in range(4)]
        elif name == "false_exclusion":
            proof["status"] = c.EXCLUDED
        elif name == "wrong_record":
            proof["record_sha256"] = "0"*64
        elif name == "wrong_profile":
            proof["profile"] = "UNVERIFIED"
        elif name == "wrong_budget":
            proof["node_budget"] = 0
        elif name == "wrong_count":
            proof["nodes"] = 0
        elif name == "missing_row":
            proof["rows"].pop()
        elif name == "extra_field":
            proof["extra"] = None
        elif name == "forged_authority":
            proof.update(json.loads('{"scientific_promotion_authorized":true}'))
        elif name == "false_existence":
            proof["joint_existence_established"] = True
        elif name == "float_node":
            proof["nodes"] = 1.0
        elif name == "oversized_string":
            proof["scope"] = "x"*257
        elif name == "malformed_scalar":
            proof["rows"][0][0][0] = True
        else:
            proof["root"].pop()
        a.need(canonical(proof) != canonical(valid), "vacuous mutation: "+name)
        try:
            v.verify(record, proof, h.BOUNDED, 1)
        except ValueError:
            dispositions[name] = "REJECTED"
        else:
            raise ValueError("forged cover admitted: "+name)
    for name, value in (("excess_budget", 64), ("boolean_budget", True)):
        try:
            c.solve(record, h.BOUNDED, value)
        except ValueError:
            dispositions[name] = "REJECTED"
        else:
            raise ValueError("invalid budget admitted")
    unverified = c.solve(record)
    a.need(v.verify(record, unverified) and unverified["status"] == c.UNCALIBRATED and
           unverified["root"] == c.box_wire(old.PRIORS) and unverified["nodes"] == 0,
           "unverified fallback")
    zero = c.solve(record, h.BOUNDED, 0)
    a.need(v.verify(record, zero, h.BOUNDED, 0) and zero["nodes"] == 0 and
           zero["frontier"] == [zero["root"][:4]], "zero budget lost root")
    return {"mutations": dispositions, "unverified": unverified, "zero": zero}


def report():
    cases, failures = [], []
    jobs = []
    for index, j, stress in product(ip.TRUTHS, range(2), (False, True)):
        jobs.append((["STRESS" if stress else "CLEAN", index, j],
                     lambda index=index, j=j, stress=stress: legacy_case(index, j, stress)))
    for i, j, sign in product(range(4), range(3), (-1, 1)):
        jobs.append((["EXTREME", i, j, sign],
                     lambda i=i, j=j, sign=sign: extreme_case(i, j, sign)))
    for b, sign in product((-8, 8), (-1, 1)):
        jobs.append((["REFERENCE", b, sign], lambda b=b, sign=sign:
                     contradiction_case(["REFERENCE", b, sign], ip.marginal_conflict(F(b), sign)["record"])))
    for t, y in ((0, 900), (60, -100)):
        jobs.append((["GROSS", t, y], lambda t=t, y=y:
                     contradiction_case(["GROSS", t, y], ip.current_conflict(t, F(y))["record"])))
    for sign in (-1, 1):
        jobs.append((["SUBTLE", sign], lambda sign=sign: subtle_case(sign)))
    for key, operation in jobs:
        try:
            row = operation()
            a.need(row["id"] == key, "case identity")
            cases.append(row)
        except Exception as exc:
            failures.append({"id": key, "error_type": type(exc).__name__, "error": str(exc)})
    extra = {}
    for key, operation in (("quantizer_panel", quantizer_panel), ("controls", controls)):
        try:
            extra[key] = operation()
        except Exception as exc:
            failures.append({"id": [key], "error_type": type(exc).__name__, "error": str(exc)})
    compatible = [x for x in cases if "proofs" in x]
    negative = [x for x in cases if "proof" in x]
    if not failures:
        a.need(len(compatible) == 56 and len(negative) == 8 and len(cases) == 64,
               "frozen roster")
    return {"experiment": "CNEH-COVER-01", "scope": c.SCOPE,
            "qualification": "FAIL_FROZEN_GATE" if failures else QUALIFIED,
            "cases": cases, "failures": failures,
            "compatible_cases": len(compatible), "contradictions": len(negative),
            "cover_checks": sum(len(x["proofs"]) for x in compatible),
            "max_one_node_width": a.q(max((F(x["proofs"][1]["max_width"])
                                           for x in compatible), default=F(0))),
            "evaluated_nodes": sum(p["nodes"] for x in compatible for p in x["proofs"])+
                               sum(x["proof"]["nodes"] for x in negative),
            **extra, **c.NEGATIVE}
