"""Bounded, feedback-directed engineering falsification of EXP-06E.

Separate from the frozen scientific cohort: no calibration, promotion, control
authority, protocol tuning, source mutation on disk, or empirical claims.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import re
from typing import Callable

from experiments.cneh_exp_06e import quotient as q

SEED = "CNEH-06E-ASSURANCE-V2"
ROUNDS = 6
WIDTH = 16
TOL = F(1, 10**75)
TIMES = (0, 1, 3, 7, 18, 30, 60, 120)
DOMAIN = (
    (F(-1, 2), F(-1, 8)),
    (F(0), F(1, 4)),
    (F(0), F(1, 2)),
    (F(0), F(1, 4)),
    (F(1), F(2)),
    (F(0), F(1)),
    (F(100), F(120)),
)
SIMPLE = (F(-1, 3), F(1, 4), F(0), F(1, 4), F(1), F(0), F(100))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def case_values(case):
    return [str(x) for x in case]


def identity(case):
    return digest(canonical(case_values(case)))


def random_bytes(label):
    return hashlib.sha256(f"{SEED}:{label}".encode("ascii")).digest()


def fresh(label, slot):
    raw = random_bytes(label)
    values = [
        lo + (hi - lo) * F(int.from_bytes(raw[2*i:2*i+2], "big"), 65535)
        for i, (lo, hi) in enumerate(DOMAIN)
    ]
    if slot % 4 == 0:
        values[2] = F(0)
    elif slot % 4 == 1:
        values[2] = F(1, 2**40)
    return tuple(values)


def perturb(parent, label):
    raw = random_bytes(label)
    index = raw[0] % len(DOMAIN)
    lo, hi = DOMAIN[index]
    old = parent[index]
    choices = (lo, hi, (old + lo)/2, (old + hi)/2,
               lo + (hi-lo)/2**40, hi - (hi-lo)/2**40)
    result = list(parent)
    result[index] = choices[raw[1] % len(choices)]
    return tuple(result)


def validate(case):
    require(len(case) == len(DOMAIN), "candidate dimension")
    require(all(type(x) is F and lo <= x <= hi
                for x, (lo, hi) in zip(case, DOMAIN, strict=True)),
            "candidate outside engineering search box")


def decimal(x):
    return Decimal(x.numerator) / Decimal(x.denominator)


def reference_state(case):
    """Independent 120-digit evaluation; no target interval or lift calls."""
    with localcontext() as context:
        context.prec = 120
        w, a, n, g, gain, delay, tau = map(decimal, case)
        return tuple(map(F, (
            Decimal(5)/6 + w*(delay/200).exp(),
            a*(delay*2/5).exp(),
            n*(delay/tau).exp()/gain,
            g*(delay/6).exp(),
        )))


def reference_current(case, state, time):
    """Direct delayed KCL from the latent state, not the quotient expression."""
    with localcontext() as context:
        context.prec = 120
        w, a, n, g = map(decimal, state)
        gain, delay, tau = map(decimal, case[4:])
        elapsed = Decimal(time) + delay
        adapted = 20 + (24*w - 20)*(-elapsed/200).exp()
        ampa = a*Decimal("0.1")*(-elapsed*2/5).exp()
        nmda = n*Decimal("0.1")*(-elapsed/tau).exp()
        gaba = g*Decimal("0.5")*(-elapsed/6).exp()
        block = Decimal("3.57")/(Decimal("3.57") + Decimal("3.72").exp())
        value = (100 - 20*Decimal("-2.5").exp() + adapted
                 - 60*ampa - 60*block*gain*nmda + 10*gaba)
        return F(value)


@dataclass(frozen=True)
class Implementation:
    lift: Callable = q.decimal_lift
    trace: Callable = q.quotient_current
    key: Callable = q.quotient_key
    box: Callable = q.lift_box


BASE = Implementation()


def inspect(case, impl=BASE):
    validate(case)
    z, gain, delay, tau = case[:4], *case[4:]
    state = reference_state(case)
    actual = impl.lift(z, gain, delay, tau)
    require(len(actual) == 4, "target state dimension")
    lift_error = max(abs(x-y) for x, y in zip(state, actual, strict=True))
    faults = set()
    if lift_error > TOL:
        faults.add("LIFT_REFERENCE")
    if not all(0 <= x <= 1 for x in (*state, *actual)):
        faults.add("STATE_DOMAIN")

    for v in (F(-71), F(-70)):
        expected = (v, *z, tau if z[2] else None)
        if impl.key(v, z, tau) != expected:
            faults.add("KEY_REFERENCE")

    point = impl.box(z, (gain, gain), (delay, delay), (tau, tau))
    family = impl.box(z, DOMAIN[4], DOMAIN[5], DOMAIN[6])
    require(len(point) == len(family) == 4, "target enclosure dimension")
    clearances = []
    for x, (lo, hi), (outer_lo, outer_hi) in zip(state, point, family, strict=True):
        clearances.extend((x-lo, hi-x))
        if not (lo-TOL <= x <= hi+TOL and lo <= hi):
            faults.add("INTERVAL_EXCLUSION")
        if not (0 <= outer_lo <= lo <= hi <= outer_hi <= 1):
            faults.add("FAMILY_NESTING")
        if not outer_lo-TOL <= x <= outer_hi+TOL:
            faults.add("INTERVAL_EXCLUSION")

    errors = [
        abs(impl.trace(t, z, tau) - reference_current(case, state, t))
        for t in TIMES
    ]
    trace_error = max(errors)
    if trace_error > TOL:
        faults.add("TRACE_REFERENCE")
    return {
        "case": case,
        "id": identity(case),
        "faults": sorted(faults),
        "lift_error": lift_error,
        "trace_error_pA": trace_error,
        "min_point_clearance": min(clearances),
    }


def serialize(row):
    return {
        "id": row["id"], "case": case_values(row["case"]),
        "faults": row["faults"], "lift_error": str(row["lift_error"]),
        "trace_error_pA": str(row["trace_error_pA"]),
        "min_point_clearance": str(row["min_point_clearance"]),
    }


def priority(row):
    # Separate dimensions; select measured residual/clearance, never a
    # scientific verdict or an altered tolerance.
    return (row["trace_error_pA"]/TOL, row["lift_error"]/TOL,
            -row["min_point_clearance"], row["id"])


def complexity(case):
    return sum(abs(x.numerator).bit_length() + x.denominator.bit_length()
               for x in case)


def reduce_witness(case, fault, impl):
    require(fault in inspect(case, impl)["faults"], "not a failure witness")
    initial = case
    steps = []
    attempts = 0
    # Bounded coordinate reduction, not a claim of globally minimal witness.
    for _ in range(2):
        for index, (lo, hi) in enumerate(DOMAIN):
            for simple in (SIMPLE[index], lo, hi, (lo+hi)/2):
                trial = case[:index] + (simple,) + case[index+1:]
                if complexity(trial) >= complexity(case):
                    continue
                attempts += 1
                if fault in inspect(trial, impl)["faults"]:
                    steps.append({"from": identity(case), "to": identity(trial),
                                  "coordinate": index, "value": str(simple)})
                    case = trial
                    break
    result = inspect(case, impl)
    require(fault in result["faults"], "reduced witness lost failure")
    return {
        "original": case_values(initial), "original_id": identity(initial),
        "reduced": serialize(result), "retained_fault": fault,
        "attempts": attempts, "accepted_steps": steps,
        "original_complexity": complexity(initial),
        "reduced_complexity": complexity(case),
    }


def generation(round_id, parents, seen):
    cases = []
    for slot in range(WIDTH):
        for retry in range(32):
            label = f"{round_id}:{slot}:{retry}"
            if parents and slot < 12 and retry < 16:
                parent = parents[slot % len(parents)]["case"]
                candidate = perturb(parent, label)
                parent_id = identity(parent)
            else:
                candidate = fresh(label, slot)
                parent_id = None
            validate(candidate)
            if candidate not in seen:
                seen.add(candidate)
                cases.append((candidate, parent_id))
                break
        else:
            raise ValueError("unique candidate budget exhausted")
    return cases


def campaign():
    seen = set()
    all_rows = []
    parents = []
    rounds = []
    for index in range(ROUNDS):
        candidates = generation(index, parents, seen)
        rows = [inspect(case) for case, _ in candidates]
        rounds.append({
            "round": index,
            "parents": [r["id"] for r in parents],
            "evaluations": [
                {**serialize(row), "parent_id": parent_id}
                for row, (_, parent_id) in zip(rows, candidates, strict=True)
            ],
        })
        parents = sorted(rows, key=priority, reverse=True)[:4]
        all_rows.extend(rows)
    require(len(seen) == len(all_rows) == ROUNDS*WIDTH,
            "complete unique search roster")
    return all_rows, rounds


def mutant_roster():
    def no_gain(z, gain, delay, tau):
        return BASE.lift(z, F(1), delay, tau)

    def no_delay(z, gain, delay, tau):
        return BASE.lift(z, gain, F(0), tau)

    def flipped_adaptation(z, gain, delay, tau):
        w, a, n, g = BASE.lift(z, gain, delay, tau)
        return F(5, 3)-w, a, n, g

    def swapped_conductances(z, gain, delay, tau):
        w, a, n, g = BASE.lift(z, gain, delay, tau)
        return w, g, n, a

    def quantized_lift(z, gain, delay, tau):
        return tuple(F(round(x*2**32), 2**32)
                     for x in BASE.lift(z, gain, delay, tau))

    def drop_rate(v, z, tau):
        return (*BASE.key(v, z, tau)[:-1], None)

    def retain_rate(v, z, tau):
        return (*BASE.key(v, z, tau)[:-1], tau)

    def zero_voltage(v, z, tau):
        return (F(-71), *BASE.key(v, z, tau)[1:])

    def zero_mode(index):
        def mutant(v, z, tau):
            key = list(BASE.key(v, z, tau))
            key[index+1] = F(0)
            return tuple(key)
        return mutant

    def biased_trace(t, z, tau):
        return BASE.trace(t, z, tau) + F(1, 10**10)

    def fixed_rate(t, z, tau):
        return BASE.trace(t, z, F(100))

    def collapsed_box(z, gain, delay, tau):
        return tuple(((lo+hi)/2, (lo+hi)/2)
                     for lo, hi in BASE.box(z, gain, delay, tau))

    roster = [
        ("LIFT_NO_GAIN", "LIFT_REFERENCE", replace(BASE, lift=no_gain)),
        ("LIFT_NO_DELAY", "LIFT_REFERENCE", replace(BASE, lift=no_delay)),
        ("LIFT_FLIP_W", "LIFT_REFERENCE", replace(BASE, lift=flipped_adaptation)),
        ("LIFT_SWAP_AG", "LIFT_REFERENCE", replace(BASE, lift=swapped_conductances)),
        ("LIFT_QUANTIZE_32", "LIFT_REFERENCE", replace(BASE, lift=quantized_lift)),
        ("KEY_DROP_ACTIVE_RATE", "KEY_REFERENCE", replace(BASE, key=drop_rate)),
        ("KEY_KEEP_SILENT_RATE", "KEY_REFERENCE", replace(BASE, key=retain_rate)),
        ("KEY_ZERO_VOLTAGE", "KEY_REFERENCE", replace(BASE, key=zero_voltage)),
        *[(f"KEY_ZERO_MODE_{i}", "KEY_REFERENCE", replace(BASE, key=zero_mode(i)))
          for i in range(4)],
        ("TRACE_BIAS", "TRACE_REFERENCE", replace(BASE, trace=biased_trace)),
        ("TRACE_FIXED_RATE", "TRACE_REFERENCE", replace(BASE, trace=fixed_rate)),
        ("BOX_COLLAPSE", "INTERVAL_EXCLUSION", replace(BASE, box=collapsed_box)),
    ]
    require(len(roster) == len({row[0] for row in roster}) == 15,
            "mutation ratchet roster")
    return roster


def mutation_ratchet(rows):
    receipts = []
    for name, expected_fault, impl in mutant_roster():
        # Evaluate the same baseline-qualified cases. A runtime exception is
        # not a kill. Only the registered oracle discrepancy counts.
        evaluated = 0
        witness = None
        for row in rows:
            evaluated += 1
            finding = inspect(row["case"], impl)
            if expected_fault in finding["faults"]:
                witness = reduce_witness(row["case"], expected_fault, impl)
                break
        receipts.append({
            "mutant": name, "expected_fault": expected_fault,
            "cases_examined": evaluated,
            "status": "KILLED" if witness is not None else "SURVIVED",
            "witness": witness,
        })
    return receipts


def report():
    require(q.TOLERANCE == TOL, "frozen diagnostic tolerance changed")
    rows, rounds = campaign()
    failures = [serialize(row) for row in rows if row["faults"]]
    reduced = None
    mutations = []
    if failures:
        first = next(row for row in rows if row["faults"])
        reduced = reduce_witness(first["case"], first["faults"][0], BASE)
    else:
        mutations = mutation_ratchet(rows)
    killed = sum(row["status"] == "KILLED" for row in mutations)
    passed = not failures and len(mutations) == killed == 15
    return {
        "scope": "SUPPLEMENTAL_ENGINEERING_ASSURANCE_ONLY",
        "seed": SEED, "rounds": rounds, "unique_cases": len(rows),
        "reference_sample_checks": len(rows)*len(TIMES),
        "diagnostic_times_ms": list(TIMES), "tolerance": str(TOL),
        "selection": "TRACE_RESIDUAL_THEN_LIFT_RESIDUAL_THEN_LOW_CLEARANCE",
        "round_budget": ROUNDS, "width_budget": WIDTH,
        "baseline_failures": failures, "reduced_baseline_witness": reduced,
        "mutation_ratchet": mutations, "mutants_killed": killed,
        "mutation_status": "NOT_RUN_BASELINE_FAILURE" if failures else
                           ("PASS" if killed == 15 else "FAIL_SURVIVOR"),
        "status": "PASS" if passed else "FAIL",
        "historical_count_observability": "FAIL_PRESERVED",
        "historical_nominal_ood": "FAIL_PRESERVED",
        "historical_noise_width": "FAIL_PRESERVED",
        "historical_2ms_reachability": "FAIL_PRESERVED",
        "calibration": "NOT_TESTED", "scientific_promotion": "BLOCKED",
        "scientific_promotion_authorized": False,
        "source_action_authorized": False, "closed_loop_authorized": False,
        "closed_loop_efficacy": "BLOCKED", "blind_causal_cohort": "BLOCKED",
    }


# The governance contract is deliberately separate from campaign generation.
# Increasing a budget or changing a verdict requires reviewing this contract.
REQUIRED_MUTANTS = {
    "LIFT_NO_GAIN": "LIFT_REFERENCE",
    "LIFT_NO_DELAY": "LIFT_REFERENCE",
    "LIFT_FLIP_W": "LIFT_REFERENCE",
    "LIFT_SWAP_AG": "LIFT_REFERENCE",
    "LIFT_QUANTIZE_32": "LIFT_REFERENCE",
    "KEY_DROP_ACTIVE_RATE": "KEY_REFERENCE",
    "KEY_KEEP_SILENT_RATE": "KEY_REFERENCE",
    "KEY_ZERO_VOLTAGE": "KEY_REFERENCE",
    "KEY_ZERO_MODE_0": "KEY_REFERENCE",
    "KEY_ZERO_MODE_1": "KEY_REFERENCE",
    "KEY_ZERO_MODE_2": "KEY_REFERENCE",
    "KEY_ZERO_MODE_3": "KEY_REFERENCE",
    "TRACE_BIAS": "TRACE_REFERENCE",
    "TRACE_FIXED_RATE": "TRACE_REFERENCE",
    "BOX_COLLAPSE": "INTERVAL_EXCLUSION",
}
NEGATIVE_GATES = {
    "historical_count_observability": "FAIL_PRESERVED",
    "historical_nominal_ood": "FAIL_PRESERVED",
    "historical_noise_width": "FAIL_PRESERVED",
    "historical_2ms_reachability": "FAIL_PRESERVED",
    "calibration": "NOT_TESTED",
    "scientific_promotion": "BLOCKED",
    "closed_loop_efficacy": "BLOCKED",
    "blind_causal_cohort": "BLOCKED",
    "scientific_promotion_authorized": False,
    "source_action_authorized": False,
    "closed_loop_authorized": False,
}


def decode_case(values):
    require(type(values) is list and len(values) == 7,
            "receipt candidate dimension")
    require(all(type(v) is str and len(v) <= 512 for v in values),
            "receipt candidate encoding")
    case = tuple(F(v) for v in values)
    validate(case)
    require(case_values(case) == values, "noncanonical candidate")
    return case


def check_governance(result):
    """Audit the execution transcript, not just its claimed PASS bit."""
    require(result["scope"] == "SUPPLEMENTAL_ENGINEERING_ASSURANCE_ONLY",
            "invalid assurance scope")
    require(all(type(result.get(k)) is type(v) and result.get(k) == v
                for k, v in NEGATIVE_GATES.items()), "negative gate changed")
    require(result["status"] == "PASS" and result["mutation_status"] == "PASS"
            and result["baseline_failures"] == []
            and result["reduced_baseline_witness"] is None,
            "nonpassing assurance report")
    require(result["seed"] == "CNEH-06E-ASSURANCE-V2"
            and result["round_budget"] == 6 and result["width_budget"] == 16
            and result["diagnostic_times_ms"] == [0, 1, 3, 7, 18, 30, 60, 120]
            and result["tolerance"] == str(F(1, 10**75)),
            "assurance budget or tolerance changed")
    require(result["unique_cases"] == 96 and result["reference_sample_checks"] == 768
            and len(result["rounds"]) == 6, "campaign roster")
    by_id = {}
    ordered_ids = []
    previous = []
    for index, round_data in enumerate(result["rounds"]):
        require(round_data["round"] == index and len(round_data["evaluations"]) == 16,
                "round roster")
        # Independent reconstruction of the feedback selection from the
        # serialized metrics. A fabricated parent or duplicate is rejected.
        selected = sorted(previous, key=lambda row: (
            F(row["trace_error_pA"]), F(row["lift_error"]),
            -F(row["min_point_clearance"]), row["id"]), reverse=True)[:4]
        parents = [row["id"] for row in selected]
        require(round_data["parents"] == parents, "feedback parent selection")
        for row in round_data["evaluations"]:
            case = decode_case(row["case"])
            ident = identity(case)
            require(row["id"] == ident and ident not in by_id,
                    "duplicate or forged candidate identity")
            require(row["parent_id"] is None or row["parent_id"] in parents,
                    "unknown feedback parent")
            if row["parent_id"] is not None:
                parent_case = by_id[row["parent_id"]]
                require(sum(x != y for x, y in zip(case, parent_case, strict=True)) == 1,
                        "invalid single-coordinate mutation")
            require(row["faults"] == [] and
                    0 <= F(row["lift_error"]) <= TOL and
                    0 <= F(row["trace_error_pA"]) <= TOL and
                    F(row["min_point_clearance"]) >= -TOL,
                    "baseline oracle invariant")
            by_id[ident] = case
            ordered_ids.append(ident)
        previous = round_data["evaluations"]
    require(len(by_id) == 96, "unique candidate roster")
    mutants = result["mutation_ratchet"]
    require(len(mutants) == result["mutants_killed"] == len(REQUIRED_MUTANTS)
            and {row["mutant"] for row in mutants} == set(REQUIRED_MUTANTS),
            "mutation ratchet roster")
    implementations = {name: impl for name, _, impl in mutant_roster()}
    require(set(implementations) == set(REQUIRED_MUTANTS), "mutation implementation roster")
    for row in mutants:
        name = row["mutant"]
        fault = REQUIRED_MUTANTS[name]
        count = row["cases_examined"]
        require(row["status"] == "KILLED" and row["expected_fault"] == fault
                and type(count) is int and 1 <= count <= len(ordered_ids),
                "mutant admission")
        witness = row["witness"]
        original = decode_case(witness["original"])
        original_id = identity(original)
        require(witness["original_id"] == original_id == ordered_ids[count-1]
                and witness["retained_fault"] == fault,
                "mutation witness provenance")
        require(witness["original_complexity"] == complexity(original),
                "original witness complexity")
        steps = witness["accepted_steps"]
        require(type(witness["attempts"]) is int and
                len(steps) <= witness["attempts"] <= 56 and len(steps) <= 14,
                "witness reduction budget")
        case = original
        for step in steps:
            coordinate = step["coordinate"]
            require(type(coordinate) is int and 0 <= coordinate < 7
                    and step["from"] == identity(case), "witness chain origin")
            value = F(step["value"])
            trial = case[:coordinate] + (value,) + case[coordinate+1:]
            validate(trial)
            require(step["to"] == identity(trial) and complexity(trial) < complexity(case),
                    "witness chain reduction")
            case = trial
        reduced = witness["reduced"]
        require(case == decode_case(reduced["case"]) and
                witness["reduced_complexity"] == complexity(case),
                "reduced witness identity")
        impl = implementations[name]
        require(fault in inspect(original, impl)["faults"] and
                fault in inspect(case, impl)["faults"] and
                serialize(inspect(case, impl)) == reduced and
                not inspect(case)["faults"], "unreproducible mutation witness")


# Limit untrusted receipt input before allocating memory. The report is
# deterministic and finite; a missing, oversized or non-regular file is FAIL.
RECEIPT_LIMIT = 4 * 1024 * 1024


def check_directory(path, names, message):
    require(path.is_dir() and not path.is_symlink(), message)
    require({p.name for p in path.iterdir()} == names, message)


def read_receipt(path):
    require(path.is_file() and not path.is_symlink(), "nonregular receipt file")
    require(path.stat().st_size <= RECEIPT_LIMIT, "receipt size budget")
    with path.open("rb") as handle:
        raw = handle.read(RECEIPT_LIMIT + 1)
    require(len(raw) <= RECEIPT_LIMIT, "receipt size budget")
    return raw


def verify_regression_profiles(profiles, checkout):
    """Periodic regression does not authenticate expired scientific receipts."""
    from experiments.cneh_exp_06e import run
    expected = run.canonical(q.report())
    names = {"cneh06e-weekly-aarch64", "cneh06e-weekly-x86_64"}
    check_directory(profiles, names, "regression architecture roster")
    for name in sorted(names):
        root = profiles/name
        check_directory(root, {"payload.json", "SHA256SUMS", "SCOPE", "HEAD"},
                        "regression file roster")
        require(read_receipt(root/"HEAD") == (checkout+"\n").encode("ascii"),
                "regression checkout mismatch")
        require(read_receipt(root/"SCOPE") ==
                b"REGRESSION_ONLY_NOT_SCIENTIFIC_ADMISSION\n", "regression scope")
        raw = read_receipt(root/"payload.json")
        require(raw == expected, "regression raw reconstruction mismatch")
        require(read_receipt(root/"SHA256SUMS") ==
                (digest(raw)+"  payload.json\n").encode("ascii"),
                "regression manifest mismatch")
    print("REGRESSION_ONLY_NOT_SCIENTIFIC_ADMISSION: independent raw reconstruction PASS")


def verify_profiles(profiles, head, checkout, run_id, attempt):
    """Reconstruct the entire supplemental report and reject partial receipts."""
    expected = report()
    check_governance(expected)
    expected.update(head_sha=head, checkout_sha=checkout, run_id=run_id, run_attempt=attempt)
    expected_raw = canonical(expected)
    roster = {"assurance-cneh06e-x86_64", "assurance-cneh06e-aarch64"}
    check_directory(profiles, roster, "assurance architecture roster")
    for arch in sorted(roster):
        root = profiles/arch
        check_directory(root, {"primary", "replay"}, "assurance process roster")
        for name in ("primary", "replay"):
            folder = root/name
            check_directory(folder, {"report.json", "SHA256SUMS"},
                            "assurance file roster")
            raw = read_receipt(folder/"report.json")
            require(raw == expected_raw, "assurance raw reconstruction mismatch")
            require(read_receipt(folder/"SHA256SUMS") ==
                    (digest(raw)+"  report.json\n").encode("ascii"),
                    "assurance manifest mismatch")
    print(json.dumps({
        "scope": expected["scope"], "status": "PASS",
        "architecture_profiles": len(roster), "process_receipts": 4,
        "fresh_reconstructions": 1, "unique_cases": expected["unique_cases"],
        "mutants_killed": expected["mutants_killed"],
        "report_sha256": digest(expected_raw),
    }, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--profiles", type=Path)
    mode.add_argument("--regression-profiles", type=Path)
    parser.add_argument("--head", required=True)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    require(all(re.fullmatch(r"[0-9a-f]{40}", s)
                for s in (args.head, args.checkout)), "invalid commit identity")
    require(re.fullmatch(r"[1-9][0-9]*", args.run_id), "invalid run identity")
    require(re.fullmatch(r"[1-9][0-9]*", args.attempt), "invalid attempt identity")
    if args.regression_profiles is not None:
        verify_regression_profiles(args.regression_profiles, args.checkout)
        return 0
    if args.profiles is not None:
        verify_profiles(args.profiles, args.head, args.checkout, args.run_id, args.attempt)
        return 0
    args.out.mkdir(parents=True, exist_ok=False)
    result = None
    stage = "GENERATION"
    try:
        result = report()
        if result["status"] == "PASS":
            stage = "GOVERNANCE"
            check_governance(result)
    except Exception as exc:
        # A harness error is never a mutation kill or scientific evidence.
        result = {"scope": "SUPPLEMENTAL_ENGINEERING_ASSURANCE_ONLY",
                  "status": "HARNESS_ERROR", "error_type": type(exc).__name__,
                  "error": str(exc), "failure_stage": stage,
                  "unadmitted_observed_report": result, **NEGATIVE_GATES}
    result.update(head_sha=args.head, checkout_sha=args.checkout, run_id=args.run_id,
                  run_attempt=args.attempt)
    raw = canonical(result)
    (args.out/"report.json").write_bytes(raw)
    (args.out/"SHA256SUMS").write_text(digest(raw)+"  report.json\n", encoding="ascii")
    print(json.dumps({
        "status": result["status"], "unique_cases": result.get("unique_cases"),
        "reference_sample_checks": result.get("reference_sample_checks"),
        "mutants_killed": result.get("mutants_killed"),
        "report_sha256": digest(raw), "scope": result["scope"],
    }, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
