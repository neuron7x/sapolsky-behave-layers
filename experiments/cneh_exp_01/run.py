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


def canonical(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    safe = True
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
        # Deterministic algorithmic proxy; not measured FLOPs or wall-clock latency.
        compute_proxy += 64 if arm in ("COUPLED", "CENTRAL_EMULATOR", "SCRAMBLED_MATCHED_TRAFFIC") else 48
        energy += u0*u0 + u1*u1
        next_x0 = p["A_base_diagonal"][0]*x0 + th*x1 + p["actuator_gain"]*u0 + w0
        next_x1 = -th*x0 + p["A_base_diagonal"][1]*x1 + p["actuator_gain"]*u1 + w1
        x0, x1 = next_x0, next_x1
        actions_states.append([round(u0, 12), round(u1, 12), round(x0, 12), round(x1, 12)])
        if max(abs(x0), abs(x1)) > p["safety_abs_bound"]:
            safe = False
    terminal_error = math.hypot(x0-goal[0], x1-goal[1])
    budget_ok = (energy <= budget["control_energy_proxy_max"] and
                 compute_proxy <= budget["controller_compute_proxy_ops_max"] and
                 message_bytes <= budget["message_bytes_max"] and
                 p["step_horizon"] <= budget["latency_steps_max"] and
                 budget["training_steps_max"] == 0)
    return {"seed": int(seed), "arm": arm,
            "success": int(safe and budget_ok and terminal_error <= p["goal_tolerance_l2"]),
            "safe": int(safe), "budget_ok": int(budget_ok),
            "terminal_error": round(terminal_error, 12), "control_energy_proxy": round(energy, 12),
            "controller_compute_proxy_ops": compute_proxy, "message_bytes": message_bytes,
            "controller_memory_proxy_bytes": 256, "latency_steps": p["step_horizon"],
            "trace_sha256": digest(canonical(actions_states))}


def lower_bound(diffs: list[int], protocol: dict[str, Any]) -> float:
    if not diffs:
        raise ValueError("empty cohort")
    # Hoeffding for D in [-1,1]; six tests are three contrasts x two cohorts.
    return sum(diffs)/len(diffs)-math.sqrt(2*math.log(protocol["number_family_tests"]/protocol["alpha_fwer"])/len(diffs))


def evaluate(seeds: list[int], protocol: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(seeds) != len(set(seeds)):
        raise ValueError("duplicate world seeds")
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


def write_bundle(out: Path, phase: str, seeds: list[int], protocol: dict[str, Any]) -> Path:
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("refuse overwrite: evidence bundles are immutable")
    out.mkdir(parents=True, exist_ok=True)
    rows, metrics = evaluate(seeds, protocol)
    for name, src in (("protocol.json","protocol.json"),("preregistration.md","PREREGISTRATION.md"),("frozen_sources.lock","frozen_sources.lock")):
        (out/name).write_bytes((HERE/src).read_bytes())
    (out/"seeds.json").write_bytes(canonical({"phase": phase, "n_world_seeds": len(seeds),
        "seeds": seeds, "source": "public fixed prereg seeds" if phase=="PRIMARY" else "external seed commitment/reveal required"}))
    header = list(rows[0].keys())
    with (out/("primary.csv" if phase=="PRIMARY" else "pilot.csv")).open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    budget = {"budget_envelope": protocol["resource_envelope"],
              "observed_max_control_energy_proxy": max(r["control_energy_proxy"] for r in rows),
              "observed_max_controller_compute_proxy_ops": max(r["controller_compute_proxy_ops"] for r in rows),
              "observed_max_message_bytes": max(r["message_bytes"] for r in rows),
              "all_within_declared_envelope": metrics["all_budget_envelopes_pass"],
              "hardware_flops_verified": False, "physical_joules_verified": False,
              "external_training_budget_verified": False}
    (out/"budget.json").write_bytes(canonical(budget))
    (out/"safety.json").write_bytes(canonical({"synthetic_safe_rates": metrics["safe_rates"],
        "physical_safety_qualified": False, "chance_constraint_verified": False, "gate": "SYNTHETIC_ONLY"}))
    (out/"negative_controls.json").write_bytes(canonical({
        "central_emulator_trace_parity": metrics["emulator_trace_parity"],
        "scrambled_envelope_parity": metrics["scrambled_traffic_envelope_parity"],
        "semantic_distribution_matching_verified": False,
        "central_simulation_dominance_applies": True,
        "outcome": "NO_STRICT_MONOLITH_ADVANTAGE_POSSIBLE"}))
    invalid = (not metrics["emulator_trace_parity"] or
               not metrics["scrambled_traffic_envelope_parity"] or
               not metrics["all_budget_envelopes_pass"])
    disposition = "INVALID" if invalid else "REPLICATION_NOT_TESTED"
    verdict = {"experiment": "CNEH-EXP-01", "hypothesis_status": protocol["hypothesis_status"],
        "phase": phase, "verdict": disposition, "scientific_promotion_authorized": False,
        "independent_blind_replication": False,
        "primary_comparisons": metrics["comparisons"], "rates": metrics["success_rates"],
        "policy_boundary": "unrestricted centralized emulator dominates in expressivity; exact matched traces observed; cannot claim stronger coupled architecture",
        "limitations": ["synthetic rather than empirical neurodynamic substrate",
            "unverified physical compute/latency/energy", "blind replication not performed",
            "no PID/Gramian/parameter-FIM measurement", "not an independent implementation"]}
    (out/"verdict.json").write_bytes(canonical(verdict))
    payload_files = sorted(p for p in out.iterdir() if p.is_file() and p.name!="SHA256SUMS")
    (out/"SHA256SUMS").write_text("".join(f"{digest(p.read_bytes())}  {p.name}\n" for p in payload_files), encoding="ascii")
    return out


def verify_bundle(out: Path) -> None:
    expected = {}
    for line in (out/"SHA256SUMS").read_text(encoding="ascii").splitlines():
        h, name = line.split("  ", 1)
        if name in expected or "/" in name or "\\" in name or len(h)!=64:
            raise ValueError("invalid SHA256SUMS entry")
        expected[name]=h
    actual = {p.name for p in out.iterdir() if p.is_file() and p.name!="SHA256SUMS"}
    if set(expected)!=actual:
        raise ValueError("evidence file membership mismatch")
    for name, sha in expected.items():
        if digest((out/name).read_bytes())!=sha:
            raise ValueError(f"SHA mismatch: {name}")
    p=json.loads((out/"protocol.json").read_text())
    with (out/("primary.csv" if (out/"primary.csv").exists() else "pilot.csv")).open(encoding="utf-8") as handle:
        rows=list(csv.DictReader(handle))
    seeds=json.loads((out/"seeds.json").read_text())["seeds"]
    by={(int(r["seed"]),r["arm"]):r for r in rows}
    if len(rows)!=len(seeds)*len(ARMS) or len(by)!=len(rows):
        raise ValueError("missing or duplicate arm rows")
    if any(by[(s,"COUPLED")]["trace_sha256"]!=by[(s,"CENTRAL_EMULATOR")]["trace_sha256"] for s in seeds):
        raise ValueError("central emulator parity fail")
    verdict=json.loads((out/"verdict.json").read_text())
    for baseline in PRIMARY_BASELINES:
        ds=[int(by[(s,"COUPLED")]["success"])-int(by[(s,baseline)]["success"]) for s in seeds]
        got=verdict["primary_comparisons"][baseline]
        if (abs(got["mean_paired_difference"]-sum(ds)/len(ds))>1e-12 or
            abs(got["one_sided_lcb"]-lower_bound(ds,p))>1e-12):
            raise ValueError("metric recomputation mismatch")
    if verdict["scientific_promotion_authorized"] or verdict["independent_blind_replication"]:
        raise ValueError("unsupported scientific promotion")


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--phase",choices=("smoke","primary"),default="smoke")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    if args.verify:
        verify_bundle(args.out)
        print("SHA256SUMS verified; paired contrasts recomputed; no unsupported promotion")
        return
    protocol=json.loads((HERE/"protocol.json").read_text(encoding="utf-8"))
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
    verify_bundle(args.out)
    print(f"{phase} bundle: {args.out} (verdict: REPLICATION_NOT_TESTED; SHA256 verified)")


if __name__=="__main__":
    main()
