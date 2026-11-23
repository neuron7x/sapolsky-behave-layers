"""CNEH-EXP-01: deterministic dependency-free SYNTHETIC preflight.

THIS IS NOT independent or blind scientific replication. No neural-data claim.
Physical plant/sensors/actions are identical across all randomized arms.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ARMS = (
    "COUPLED", "CENTRAL_EMULATOR", "STATIC_FUSION",
    "SCRAMBLED_MATCHED_TRAFFIC", "A_ONLY", "B_ONLY",
    "PARALLEL_NO_MESSAGES", "ONE_WAY", "HOMOGENEOUS_DUPLICATES",
    "FULL_INFORMATION_ORACLE",
)
PRIMARY_BASELINES = ("CENTRAL_EMULATOR", "STATIC_FUSION", "SCRAMBLED_MATCHED_TRAFFIC")
EVIDENCE_FORMAT_VERSION = 2
CONTROLLER_MEMORY_PROXY_BYTES = 256  # Frozen algorithmic proxy, NOT measured RAM.


def canonical(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: str | bytes) -> Any:
    """Reject ambiguous objects and all nonfinite JSON numbers, including overflow."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def number(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite JSON number")
        return parsed

    def constant(value: str) -> None:
        raise ValueError(f"nonfinite JSON constant: {value}")

    return json.loads(data, object_pairs_hook=pairs, parse_float=number,
                      parse_constant=constant)


def trace_digest(actions_states: list[list[float]]) -> str:
    """Exact binary64 values, including signed zero; no decimal rounding."""
    if any(not math.isfinite(v) for row in actions_states for v in row):
        raise ValueError("nonfinite action/state trace")
    return digest(canonical([[v.hex() for v in row] for row in actions_states]))


def validate_seeds(seeds: list[int]) -> None:
    if (type(seeds) is not list or not seeds
            or any(type(seed) is not int or seed < 0 for seed in seeds)):
        raise ValueError("world seeds must be a nonempty list of nonnegative integers")
    if len(seeds) != len(set(seeds)):
        raise ValueError("duplicate world seeds")


def validate_cohort(phase: str, seeds: list[int], protocol: dict[str, Any]) -> None:
    validate_seeds(seeds)
    if phase not in ("SMOKE", "PRIMARY"):
        raise ValueError("unapproved cohort phase")
    if phase == "PRIMARY":
        cohort = protocol["cohorts"]["primary"]
        frozen = list(range(cohort["seed_first"], cohort["seed_last"] + 1))
        if seeds != frozen or len(seeds) != cohort["n_world_seeds"]:
            raise ValueError("confirmatory cohort diverges from preregistration")


def clamp(value: float, bound: float) -> float:
    return max(-bound, min(bound, value))


@dataclass
class Controller:
    nominal_theta: float = 0.02
    theta_hat: float = 0.02
    previous: tuple[float, float] | None = None
    previous_action: tuple[float, float] = (0.0, 0.0)

    def act(self, t: int, sensed: tuple[float, float], goal: tuple[float, float],
            arm: str, plant: dict[str, Any], true_state: tuple[float, float] | None = None,
            true_theta: float | None = None) -> tuple[float, float]:
        if arm == "FULL_INFORMATION_ORACLE":
            assert true_state is not None and true_theta is not None
            x0, x1 = true_state
            th = true_theta
        else:
            x0, x1 = sensed
            th = self.theta_hat if arm in ("COUPLED", "CENTRAL_EMULATOR", "SCRAMBLED_MATCHED_TRAFFIC") else self.nominal_theta
            if self.previous is not None and arm in ("COUPLED", "CENTRAL_EMULATOR", "SCRAMBLED_MATCHED_TRAFFIC"):
                p0, p1 = self.previous
                u0_prev, u1_prev = self.previous_action
                r0 = x0 - plant["A_base_diagonal"][0] * p0 - plant["actuator_gain"] * u0_prev
                r1 = x1 - plant["A_base_diagonal"][1] * p1 - plant["actuator_gain"] * u1_prev
                theta_instant = clamp((r0 * p1 - r1 * p0) / (p0 * p0 + p1 * p1 + 0.35), 0.5)
                self.theta_hat = 0.80 * self.theta_hat + 0.20 * theta_instant
                th = self.theta_hat
        g0, g1 = goal
        a0, a1 = plant["A_base_diagonal"]
        b = plant["actuator_gain"]
        feed0 = (g0 - a0*g0 - th*g1)/b
        feed1 = (g1 - a1*g1 + th*g0)/b
        # Precommitted bounded harmonic probe; this does NOT prove persistent excitation.
        probe0 = 0.07 * math.sin(2.0 * math.pi * t / 7.0)
        probe1 = 0.07 * math.cos(2.0 * math.pi * t / 9.0)
        u0 = clamp(feed0 - 1.35 * (x0 - g0) + probe0, plant["actuator_bound"])
        u1 = clamp(feed1 - 1.35 * (x1 - g1) + probe1, plant["actuator_bound"])
        if arm == "A_ONLY":
            u1 = 0.0
        if arm == "B_ONLY":
            u0 = 0.0
        if arm == "PARALLEL_NO_MESSAGES":
            u0 = clamp((g0-a0*g0)/b - 1.35*(x0-g0)+probe0, plant["actuator_bound"])
            u1 = clamp((g1-a1*g1)/b - 1.35*(x1-g1)+probe1, plant["actuator_bound"])
        if arm == "ONE_WAY":
            u1 = clamp((g1-a1*g1)/b - 1.35*(x1-g1)+probe1, plant["actuator_bound"])
        if arm != "FULL_INFORMATION_ORACLE":
            self.previous = sensed
            self.previous_action = (u0, u1)
        return (u0, u1)


def simulate(seed: int, arm: str, protocol: dict[str, Any]) -> dict[str, Any]:
    """One paired episode; controller never receives latent theta except oracle arm."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm}")
    validate_seeds([seed])
    canonical(protocol)  # Refuse NaN/Infinity in the model or budget before control.
    p = protocol["model"]
    budget = protocol["resource_envelope"]
    rng = random.Random(int(seed))
    x0, x1 = (rng.uniform(-p["initial_state_abs_bound"], p["initial_state_abs_bound"]) for _ in range(2))
    goal = tuple(rng.uniform(-p["goal_abs_bound"], p["goal_abs_bound"]) for _ in range(2))
    shift = p["ood_cross_coupling_set"][int(seed) % len(p["ood_cross_coupling_set"])]
    noises = [(rng.gauss(0, p["observation_noise_sd"]),
               rng.gauss(0, p["observation_noise_sd"]),
               rng.gauss(0, p["process_noise_sd"]),
               rng.gauss(0, p["process_noise_sd"])) for _ in range(p["step_horizon"])]
    controller = Controller(nominal_theta=p["cross_coupling_nominal"], theta_hat=p["cross_coupling_nominal"])
    history_y0: list[float] = []
    history_y1: list[float] = []
    actions_states: list[list[float]] = []
    safe = max(abs(x0), abs(x1)) <= p["safety_abs_bound"]
    energy = 0.0
    message_bytes = 0
    compute_proxy = 0
    for t, (n0, n1, w0, w1) in enumerate(noises):
        th = shift if t >= p["change_step"] else p["cross_coupling_nominal"]
        y0, y1 = x0 + n0, x1 + n1
        history_y0.append(y0)
        history_y1.append(y1)
        sensed = (y0, y1)
        if arm == "A_ONLY":
            sensed = (y0, 0.0)
        elif arm == "B_ONLY":
            sensed = (0.0, y1)
        elif arm == "HOMOGENEOUS_DUPLICATES":
            sensed = (y0, y0)
        elif arm == "SCRAMBLED_MATCHED_TRAFFIC":
            sensed = (history_y0[t-3] if t >= 3 else 0.0,
                      history_y1[t-3] if t >= 3 else 0.0)
        if arm in ("COUPLED", "SCRAMBLED_MATCHED_TRAFFIC"):
            message_bytes += 16  # two fixed-size 8-byte envelopes per tick
        elif arm == "ONE_WAY":
            message_bytes += 8
        u0, u1 = controller.act(t, sensed, goal, arm, p,
                                 true_state=(x0, x1) if arm == "FULL_INFORMATION_ORACLE" else None,
                                 true_theta=th if arm == "FULL_INFORMATION_ORACLE" else None)
        if not all(math.isfinite(v) for v in (u0, u1)):
            raise ValueError("nonfinite controller action")
        if max(abs(u0), abs(u1)) > p["actuator_bound"]:
            raise ValueError("controller action exceeds physical interface bound")
        # Deterministic algorithmic proxy; not measured FLOPs or wall-clock latency.
        compute_proxy += 64 if arm in ("COUPLED", "CENTRAL_EMULATOR", "SCRAMBLED_MATCHED_TRAFFIC") else 48
        energy += u0*u0 + u1*u1
        next_x0 = p["A_base_diagonal"][0]*x0 + th*x1 + p["actuator_gain"]*u0 + w0
        next_x1 = -th*x0 + p["A_base_diagonal"][1]*x1 + p["actuator_gain"]*u1 + w1
        x0, x1 = next_x0, next_x1
        if not all(math.isfinite(v) for v in (x0, x1, energy)):
            raise ValueError("nonfinite plant state or control effort")
        actions_states.append([u0, u1, x0, x1])
        if max(abs(x0), abs(x1)) > p["safety_abs_bound"]:
            safe = False
    terminal_error = math.hypot(x0-goal[0], x1-goal[1])
    budget_ok = (energy <= budget["control_energy_proxy_max"] and
                 compute_proxy <= budget["controller_compute_proxy_ops_max"] and
                 message_bytes <= budget["message_bytes_max"] and
                 CONTROLLER_MEMORY_PROXY_BYTES <= budget["controller_memory_proxy_bytes_max"] and
                 p["step_horizon"] <= budget["latency_steps_max"] and
                 budget["training_steps_max"] == 0)
    return {"seed": int(seed), "arm": arm,
            "success": int(safe and budget_ok and terminal_error <= p["goal_tolerance_l2"]),
            "safe": int(safe), "budget_ok": int(budget_ok),
            "terminal_error": round(terminal_error, 12), "control_energy_proxy": round(energy, 12),
            "controller_compute_proxy_ops": compute_proxy, "message_bytes": message_bytes,
            "controller_memory_proxy_bytes": CONTROLLER_MEMORY_PROXY_BYTES,
            "latency_steps": p["step_horizon"],
            "trace_sha256": trace_digest(actions_states)}


def lower_bound(diffs: list[int], protocol: dict[str, Any]) -> float:
    if not diffs:
        raise ValueError("empty cohort")
    # Hoeffding for D in [-1,1]; six tests are three contrasts x two cohorts.
    return sum(diffs)/len(diffs)-math.sqrt(2*math.log(protocol["number_family_tests"]/protocol["alpha_fwer"])/len(diffs))


def evaluate(seeds: list[int], protocol: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_seeds(seeds)
    rows = [simulate(seed, arm, protocol) for seed in seeds for arm in ARMS]
    by = {(r["seed"], r["arm"]): r for r in rows}
    emu_identical = all(by[(s, "COUPLED")]["trace_sha256"] == by[(s, "CENTRAL_EMULATOR")]["trace_sha256"] for s in seeds)
    traffic_identical = all(by[(s, "COUPLED")]["message_bytes"] == by[(s, "SCRAMBLED_MATCHED_TRAFFIC")]["message_bytes"] for s in seeds)
    paired = {}
    for baseline in PRIMARY_BASELINES:
        diffs = [by[(s, "COUPLED")]["success"]-by[(s, baseline)]["success"] for s in seeds]
        paired[baseline] = {"n_world_seeds": len(diffs), "mean_paired_difference": sum(diffs)/len(diffs),
                            "one_sided_lcb": lower_bound(diffs, protocol),
                            "passes_material_effect": lower_bound(diffs, protocol)>protocol["material_effect"]}
    budget_pass = all(r["budget_ok"] for r in rows)
    safe_rate = {arm:sum(by[(s,arm)]["safe"] for s in seeds)/len(seeds) for arm in ARMS}
    success_rate = {arm:sum(by[(s,arm)]["success"] for s in seeds)/len(seeds) for arm in ARMS}
    metrics = {"comparisons": paired, "emulator_trace_parity": emu_identical,
               "scrambled_traffic_envelope_parity": traffic_identical,
               "all_budget_envelopes_pass": budget_pass, "safe_rates": safe_rate,
               "success_rates": success_rate,
               "note": "message values not distribution-matched; only byte count/envelope/time are matched; energy is synthetic L2 input proxy"}
    return rows, metrics


def derived_artifacts(phase: str, seeds: list[int], protocol: dict[str, Any],
                      rows: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    """Complete, closed schemas for derived evidence; no unchecked claim fields."""
    budget = {"budget_envelope": protocol["resource_envelope"],
              "observed_max_control_energy_proxy": max(r["control_energy_proxy"] for r in rows),
              "observed_max_controller_compute_proxy_ops": max(r["controller_compute_proxy_ops"] for r in rows),
              "observed_max_message_bytes": max(r["message_bytes"] for r in rows),
              "observed_max_controller_memory_proxy_bytes": max(r["controller_memory_proxy_bytes"] for r in rows),
              "observed_max_latency_steps": max(r["latency_steps"] for r in rows),
              "all_within_declared_envelope": metrics["all_budget_envelopes_pass"],
              "hardware_flops_verified": False, "physical_joules_verified": False,
              "external_training_budget_verified": False}
    safety = {"synthetic_safe_rates": metrics["safe_rates"],
        "physical_safety_qualified": False, "chance_constraint_verified": False, "gate": "SYNTHETIC_ONLY"}
    negative_controls = {
        "central_emulator_trace_parity": metrics["emulator_trace_parity"],
        "scrambled_envelope_parity": metrics["scrambled_traffic_envelope_parity"],
        "semantic_distribution_matching_verified": False,
        "central_simulation_dominance_applies": True,
        "outcome": ("NO_STRICT_MONOLITH_ADVANTAGE_POSSIBLE" if metrics["emulator_trace_parity"]
                    else "MEASUREMENT_INVALID")}
    invalid = (not metrics["emulator_trace_parity"] or
               not metrics["scrambled_traffic_envelope_parity"] or
               not metrics["all_budget_envelopes_pass"])
    disposition = "INVALID" if invalid else "REPLICATION_NOT_TESTED"
    verdict = {"experiment": "CNEH-EXP-01", "hypothesis_status": protocol["hypothesis_status"],
        "phase": phase, "verdict": disposition, "scientific_promotion_authorized": False,
        "independent_blind_replication": False,
        "primary_comparisons": metrics["comparisons"], "rates": metrics["success_rates"],
        "policy_boundary": "unrestricted centralized emulator dominates in expressivity; parity is mandatory; cannot claim stronger coupled architecture",
        "limitations": ["synthetic rather than empirical neurodynamic substrate",
            "unverified physical compute/latency/energy", "blind replication not performed",
            "no PID/Gramian/parameter-FIM measurement", "not an independent implementation"]}
    return {
        "seeds.json": {"phase": phase, "n_world_seeds": len(seeds), "seeds": seeds,
                       "source": "public fixed prereg seeds" if phase == "PRIMARY"
                       else "internal engineering smoke; not blind replication"},
        "implementation.json": {
            "evidence_format_version": EVIDENCE_FORMAT_VERSION,
            "runner_sha256": digest(Path(__file__).read_bytes()),
            "trace_encoding": "canonical JSON of float.hex binary64 action/state rows",
            "verification_scope": "same-implementation deterministic replay; not independent replication",
        },
        "budget.json": budget,
        "safety.json": safety,
        "negative_controls.json": negative_controls,
        "verdict.json": verdict,
    }


def write_bundle(out: Path, phase: str, seeds: list[int], protocol: dict[str, Any]) -> Path:
    frozen_protocol = strict_json((HERE / "protocol.json").read_bytes())
    if canonical(protocol) != canonical(frozen_protocol):
        raise ValueError("writer protocol diverges from frozen preregistration")
    validate_cohort(phase, seeds, protocol)
    if out.is_symlink():
        raise ValueError("refuse symlink evidence directory")
    if out.exists():
        raise FileExistsError("refuse overwrite: evidence bundles are immutable")
    rows, metrics = evaluate(seeds, protocol)
    artifacts = derived_artifacts(phase, seeds, protocol, rows, metrics)
    # Exclusive reservation closes concurrent writers' check-then-write race.
    # A failed write leaves an incomplete, non-admissible bundle for diagnosis.
    out.mkdir(parents=True, exist_ok=False)
    for name, src in (("protocol.json", "protocol.json"),
                      ("preregistration.md", "PREREGISTRATION.md"),
                      ("frozen_sources.lock", "frozen_sources.lock")):
        (out / name).write_bytes((HERE / src).read_bytes())
    for name, artifact in artifacts.items():
        (out / name).write_bytes(canonical(artifact))
    with (out / ("primary.csv" if phase == "PRIMARY" else "pilot.csv")).open(
            "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    payload_files = sorted(p for p in out.iterdir() if p.is_file() and p.name!="SHA256SUMS")
    (out/"SHA256SUMS").write_text("".join(f"{digest(p.read_bytes())}  {p.name}\n" for p in payload_files), encoding="ascii")
    return out


def verify_bundle(out: Path, *, require_valid: bool = False) -> dict[str, Any]:
    """Fail closed on re-signed CSV lies, drifted source contracts, or invalid claims.

    Deterministic replay is an *internal* check, not an independent replication
    or an adversary-resistant signature of the code that performs this check.
    Authentic negative bundles remain auditable. ``require_valid`` also checks
    engineering admission; neither mode can authorize scientific promotion.
    """
    if not out.is_dir() or out.is_symlink():
        raise ValueError("invalid bundle directory")
    entries = list(out.iterdir())
    if any(not p.is_file() or p.is_symlink() for p in entries):
        raise ValueError("unexpected directory or symlink in evidence bundle")
    if not (out / "SHA256SUMS").is_file():
        raise ValueError("missing hash manifest")
    expected = {}
    manifest_lines = (out / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    for line in manifest_lines:
        if line.count("  ") != 1:
            raise ValueError("invalid SHA256SUMS record")
        h, name = line.split("  ", 1)
        if (name in expected or not name or "/" in name or "\\" in name
                or len(h) != 64 or any(c not in "0123456789abcdef" for c in h)):
            raise ValueError("invalid SHA256SUMS entry")
        expected[name] = h
    if list(expected) != sorted(expected):
        raise ValueError("noncanonical hash manifest order")
    actual = {p.name for p in entries if p.name != "SHA256SUMS"}
    if set(expected) != actual:
        raise ValueError("evidence file membership mismatch")
    for name, sha in expected.items():
        if digest((out / name).read_bytes()) != sha:
            raise ValueError(f"SHA mismatch: {name}")
    frozen = {"protocol.json": "protocol.json",
              "preregistration.md": "PREREGISTRATION.md",
              "frozen_sources.lock": "frozen_sources.lock"}
    for bundle_name, source_name in frozen.items():
        if (out / bundle_name).read_bytes() != (HERE / source_name).read_bytes():
            raise ValueError(f"resigned protocol/source drift: {bundle_name}")
    p = strict_json((out / "protocol.json").read_bytes())
    if p.get("hypothesis_status") != "FORMALIZED / EMPIRICAL VALIDATION PENDING" or p.get("claim_promotion_allowed") is not False:
        raise ValueError("canonical scientific authority lock violated")
    expected_spec_hash = digest((HERE / "CNEH-04-DC_Formal_Specification.md").read_bytes())
    if p.get("source_spec_sha256") != expected_spec_hash:
        raise ValueError("original CNEH-04-DC specification hash mismatch")

    seed_obj = strict_json((out / "seeds.json").read_bytes())
    if type(seed_obj) is not dict or "seeds" not in seed_obj:
        raise ValueError("invalid independent world-seed list")
    seeds = seed_obj["seeds"]
    phase = seed_obj.get("phase")
    validate_cohort(phase, seeds, p)
    expected_names = {"protocol.json", "preregistration.md", "frozen_sources.lock",
                      "seeds.json", "budget.json", "safety.json",
                      "negative_controls.json", "verdict.json", "implementation.json",
                      "primary.csv" if phase == "PRIMARY" else "pilot.csv"}
    if actual != expected_names:
        raise ValueError("wrong phase artifact roster")

    csv_name = "primary.csv" if phase == "PRIMARY" else "pilot.csv"
    with (out / csv_name).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    replay_rows, replay_metrics = evaluate(seeds, p)
    if len(rows) != len(replay_rows):
        raise ValueError("missing or extra arm rows")
    expected_columns = list(replay_rows[0])
    if reader.fieldnames != expected_columns:
        raise ValueError("unexpected CSV columns")
    for actual_row, replay_row in zip(rows, replay_rows):
        if actual_row != {k: str(v) for k, v in replay_row.items()}:
            raise ValueError(f"raw trajectory/reward/cost mismatch in re-signed CSV for seed={replay_row['seed']} arm={replay_row['arm']}")
    expected_artifacts = derived_artifacts(phase, seeds, p, replay_rows, replay_metrics)
    for name, expected_artifact in expected_artifacts.items():
        actual_artifact = strict_json((out / name).read_bytes())
        # Canonical bytes distinguish True from 1, False from 0, and 1 from 1.0;
        # plain dict equality would silently accept these evidence type changes.
        if canonical(actual_artifact) != canonical(expected_artifact):
            raise ValueError(f"derived evidence mismatch: {name}")
    verdict = expected_artifacts["verdict.json"]
    if require_valid and verdict["verdict"] == "INVALID":
        raise ValueError("authentic negative evidence: engineering qualification INVALID")
    return verdict


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--phase",choices=("smoke","primary"),default="smoke")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    if args.verify:
        verify_bundle(args.out, require_valid=True)
        print("SHA256SUMS verified; paired contrasts recomputed; no unsupported promotion")
        return
    protocol=strict_json((HERE/"protocol.json").read_bytes())
    if protocol["hypothesis_status"]!="FORMALIZED / EMPIRICAL VALIDATION PENDING" or protocol["claim_promotion_allowed"] is not False:
        raise RuntimeError("canonical claim lock violated")
    if args.phase=="primary":
        c=protocol["cohorts"]["primary"]
        seeds=list(range(c["seed_first"],c["seed_last"]+1))
        if len(seeds)!=c["n_world_seeds"]:
            raise RuntimeError("seed lock mismatch")
        phase="PRIMARY"
    else:
        seeds=[3001,3002,3003,3004]
        phase="SMOKE"
    write_bundle(args.out,phase,seeds,protocol)
    verify_bundle(args.out, require_valid=True)
    print(f"{phase} bundle: {args.out} (verdict: REPLICATION_NOT_TESTED; SHA256 verified)")


if __name__=="__main__":
    main()
