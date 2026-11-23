"""CNEH-EXP-02: two independent predictive cortices and falsifiable OOD dual control.

Zero dependencies. All outcomes are synthetic, explorative and INTERNAL only.
A central emulator is deliberately an exact behavioural simulator of the two
cortices: beating it is not an admissible proof of collective emergence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ARMS = (
    "COUPLED", "CENTRAL_EMULATOR", "STATIC_FUSION", "SCRAMBLED_CONTENT",
    "NO_PROBE", "ONE_WAY_A_TO_B", "DISCONNECTED", "HOMOGENEOUS_VIEW",
    "FULL_INFORMATION_ORACLE",
)
BASELINES = ("CENTRAL_EMULATOR", "STATIC_FUSION", "SCRAMBLED_CONTENT", "NO_PROBE")
PACKET_FORMAT = "!IB4f11x"
assert struct.calcsize(PACKET_FORMAT) == 32


def canon(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def clip(value: float, bound: float) -> float:
    return max(-bound, min(bound, value))


@dataclass(frozen=True)
class Packet:
    tick: int
    origin: int
    state: float
    theta: float
    information: float
    surprise: float

    def to_bytes(self) -> bytes:
        raw = struct.pack(PACKET_FORMAT, self.tick, self.origin, self.state,
                          self.theta, self.information, self.surprise)
        assert len(raw) == 32
        return raw

    @staticmethod
    def from_bytes(raw: bytes) -> "Packet":
        if len(raw) != 32:
            raise ValueError("message envelope is not 32 bytes")
        t, origin, state, theta, information, surprise = struct.unpack(PACKET_FORMAT, raw)
        if not all(math.isfinite(x) for x in (state, theta, information, surprise)):
            raise ValueError("nonfinite message")
        if information < 0 or surprise < 0:
            raise ValueError("invalid evidence payload")
        return Packet(t, origin, state, theta, information, surprise)


def null_packet(tick: int) -> bytes:
    return Packet(tick, 255, 0.0, 0.0, 0.0, 0.0).to_bytes()


class Cortex:
    """Local observer/controller, never given the global x or unknown theta."""

    def __init__(self, axis: int, protocol: dict[str, Any]):
        self.axis = axis
        self.model = protocol["model"]
        self.cfg = protocol["agent"]
        self.sign = 1.0 if axis == 0 else -1.0
        self.a = self.model["a0"] if axis == 0 else self.model["a1"]
        self.last_obs: float | None = None
        self.last_other: float | None = None
        self.last_u = 0.0
        self.own_state = 0.0
        self.information = 0.0
        self.sufficient = 0.0
        self.theta_hat = self.model["theta_nominal"]
        self.surprise = 0.0
        self.alarm_tick: int | None = None
        self.energy = 0.0
        self.ops_proxy = 0

    def observe(self, observation: float, tick: int) -> bytes:
        """Past-only local innovation -> finite-memory causal parameter estimate."""
        if self.last_obs is None:
            self.own_state = observation
            self.ops_proxy += 24
        else:
            other = 0.0 if self.last_other is None else self.last_other
            prediction = (
                self.a * self.last_obs
                + self.sign * self.theta_hat * other
                + self.model["control_gain"] * self.last_u
            )
            residual = (
                observation - self.a * self.last_obs
                - self.model["control_gain"] * self.last_u
            )
            regressor = self.sign * other
            rho = self.cfg["forgetting_factor"]
            self.information *= rho
            self.sufficient *= rho
            if self.last_other is not None:
                self.information += regressor * regressor
                self.sufficient += regressor * residual
            prior = self.cfg["ridge_prior_precision"]
            self.theta_hat = clip(
                (prior * self.model["theta_nominal"] + self.sufficient)
                / (prior + self.information),
                self.cfg["theta_clip"],
            )
            discrepancy = abs(observation - prediction) / max(
                0.11, self.model["observation_sd"] * math.sqrt(2.0)
            )
            self.surprise = (
                self.cfg["surprise_decay"] * self.surprise
                + (1.0 - self.cfg["surprise_decay"]) * min(10.0, discrepancy)
            )
            if tick > 0 and self.surprise > 1.8 and self.alarm_tick is None:
                self.alarm_tick = tick
            w = self.cfg["state_filter_observation_weight"]
            self.own_state = w * observation + (1.0 - w) * prediction
            self.ops_proxy += 64
        self.last_obs = observation
        return Packet(
            tick, self.axis, self.own_state, self.theta_hat,
            self.information, self.surprise
        ).to_bytes()

    def act(
        self, tick: int, incoming_raw: bytes, target: tuple[float, float],
        policy: str, truth: tuple[float, float] | None = None,
        true_theta: float | None = None,
    ) -> float:
        """Infer peer state/parameter from packet and commit bounded own-axis action."""
        peer = Packet.from_bytes(incoming_raw)
        if peer.tick != tick:
            raise ValueError("packet must be contemporaneous")
        expected_origin = 1 - self.axis
        if peer.origin not in (expected_origin, 255):
            raise ValueError("wrong peer identity")

        if peer.origin == expected_origin:
            other = peer.state
            local_weight = self.cfg["ridge_prior_precision"] + self.information
            remote_weight = self.cfg["ridge_prior_precision"] + peer.information
            theta = (
                self.theta_hat * local_weight + peer.theta * remote_weight
            ) / (local_weight + remote_weight)
        else:
            other = 0.0
            theta = self.theta_hat
        if policy == "STATIC_FUSION":
            theta = self.model["theta_nominal"]
        if policy == "FULL_INFORMATION_ORACLE":
            if truth is None or true_theta is None:
                raise ValueError("oracle truth missing")
            other = truth[expected_origin]
            theta = true_theta
            own = truth[self.axis]
        else:
            own = self.own_state

        g_own, g_other = target[self.axis], target[expected_origin]
        b = self.model["control_gain"]
        # Local predictive model, not a centralized action selector.
        feedback = (g_own - self.a * own - self.sign * theta * other) / b
        feedforward = (
            (1.0 - self.a) * g_own - self.sign * theta * g_other
        ) / b
        u = self.cfg["control_gain"] * feedback + (
            1.0 - self.cfg["control_gain"]
        ) * feedforward

        if policy not in ("NO_PROBE", "FULL_INFORMATION_ORACLE"):
            amplitude = min(
                self.cfg["probe_max_amplitude"],
                self.cfg["probe_base_amplitude"]
                + self.cfg["probe_surprise_gain"] * self.surprise
                + self.cfg["probe_uncertainty_gain"] / (1.0 + self.information),
            )
            period = (
                self.cfg["probe_period_A"] if self.axis == 0
                else self.cfg["probe_period_B"]
            )
            phase = 0.0 if self.axis == 0 else math.pi / 2.0
            u += amplitude * math.sin(2 * math.pi * tick / period + phase)
        u = clip(u, self.model["action_abs"])
        # Each cortex has an independent, equal share of the total energy budget.
        cap = 0.5 * self.model.get("energy_budget", 36.0)
        remain = max(0.0, cap - self.energy)
        if u * u > remain:
            u = math.copysign(math.sqrt(remain), u)
        self.energy += u * u
        self.last_u = u
        self.last_other = other if peer.origin == expected_origin else None
        self.ops_proxy += 42
        return u


def make_world(seed: int, p: dict[str, Any]) -> dict[str, Any]:
    rng = random.Random(seed)
    x = [rng.uniform(-p["initial_abs"], p["initial_abs"]) for _ in range(2)]
    goal = tuple(rng.uniform(-p["goal_abs"], p["goal_abs"]) for _ in range(2))
    noise = [
        (rng.gauss(0.0, p["observation_sd"]),
         rng.gauss(0.0, p["observation_sd"]),
         rng.gauss(0.0, p["process_sd"]),
         rng.gauss(0.0, p["process_sd"]))
        for _ in range(p["horizon"])
    ]
    return {"x": x, "goal": goal, "noise": noise,
            "ood_theta": p["theta_ood"][seed % len(p["theta_ood"])]}


def evaluate_world(
    seed: int,
    policy: str,
    protocol: dict[str, Any],
    donor_packets: list[tuple[bytes, bytes]] | None = None,
) -> tuple[dict[str, Any], list[tuple[bytes, bytes]]]:
    if policy not in ARMS:
        raise ValueError(f"unknown arm {policy}")
    p = protocol["model"]
    world = make_world(seed, p)
    x = world["x"]
    goal = world["goal"]
    aa = Cortex(0, protocol)
    bb = Cortex(1, protocol)
    trace = []
    outbound: list[tuple[bytes, bytes]] = []
    safe = True
    bytes_sent = 0
    alarm_pre_shift = False
    for tick, (v0, v1, w0, w1) in enumerate(world["noise"]):
        theta = world["ood_theta"] if tick >= p["shift_step"] else p["theta_nominal"]
        y0, y1 = x[0] + v0, x[1] + v1
        if policy == "HOMOGENEOUS_VIEW":
            y1 = y0
        packet_a = aa.observe(y0, tick)
        packet_b = bb.observe(y1, tick)
        outbound.append((packet_a, packet_b))
        if policy == "SCRAMBLED_CONTENT":
            if donor_packets is None or len(donor_packets) != p["horizon"]:
                raise ValueError("contemporaneous cross-world donor missing")
            received_a = donor_packets[tick][1]
            received_b = donor_packets[tick][0]
        elif policy == "ONE_WAY_A_TO_B":
            received_a = null_packet(tick)
            received_b = packet_a
        elif policy == "DISCONNECTED":
            received_a = null_packet(tick)
            received_b = null_packet(tick)
        else:
            received_a, received_b = packet_b, packet_a
        bytes_sent += len(received_a) + len(received_b)
        raw = tuple(x) if policy == "FULL_INFORMATION_ORACLE" else None
        u0 = aa.act(
            tick, received_a, goal, policy, truth=raw,
            true_theta=theta if raw else None,
        )
        u1 = bb.act(
            tick, received_b, goal, policy, truth=raw,
            true_theta=theta if raw else None,
        )
        x0 = p["a0"] * x[0] + theta * x[1] + p["control_gain"] * u0 + w0
        x1 = -theta * x[0] + p["a1"] * x[1] + p["control_gain"] * u1 + w1
        x = [x0, x1]
        if max(abs(x0), abs(x1)) > p["safety_abs"]:
            safe = False
        if tick < p["shift_step"] and (
            aa.alarm_tick is not None or bb.alarm_tick is not None
        ):
            alarm_pre_shift = True
        trace.append((
            tick, round(u0, 11), round(u1, 11),
            round(x0, 11), round(x1, 11),
            sha(received_a), sha(received_b),
        ))
    terminal_error = math.hypot(x[0] - goal[0], x[1] - goal[1])
    effort = aa.energy + bb.energy
    operations = aa.ops_proxy + bb.ops_proxy
    memory = 256  # fixed instrumented scalar-state upper proxy per cortex
    bnd = protocol["resource_envelope"]
    budget_ok = (
        effort <= bnd["max_control_energy_proxy"] + 1e-9
        and operations <= bnd["max_controller_operation_proxy"]
        and bytes_sent <= bnd["max_communication_bytes"]
        and memory <= bnd["max_per_agent_memory_bytes"]
        and p["horizon"] <= bnd["max_steps"]
        and bnd["training_steps"] == 0
    )
    alarm_candidates = [
        v for v in (aa.alarm_tick, bb.alarm_tick) if v is not None
        and v >= p["shift_step"]
    ]
    alarm_delay = min(alarm_candidates) - p["shift_step"] if alarm_candidates else -1
    row = {
        "seed": seed, "stratum": seed % len(p["theta_ood"]), "arm": policy,
        "safe": int(safe), "budget_ok": int(budget_ok),
        "success": int(safe and budget_ok and terminal_error <= p["goal_tolerance"]),
        "goal_error": round(terminal_error, 11),
        "theta_abs_error_a": round(abs(aa.theta_hat - world["ood_theta"]), 11),
        "theta_abs_error_b": round(abs(bb.theta_hat - world["ood_theta"]), 11),
        "regressor_excitation_proxy": round(aa.information + bb.information, 11),
        "alarm_delay_steps": alarm_delay, "false_alarm_pre_shift": int(alarm_pre_shift),
        "control_energy_proxy": round(effort, 11),
        "operation_proxy": operations,
        "message_bytes": bytes_sent, "memory_proxy_bytes_per_cortex": memory,
        "trace_sha256": sha(canon(trace)),
        "outbound_message_sha256": sha(b"".join(a + b for a, b in outbound)),
    }
    return row, outbound


def donor_rotation(seeds: list[int], p: dict[str, Any]) -> dict[int, int]:
    groups: dict[int, list[int]] = {}
    for seed in sorted(seeds):
        groups.setdefault(seed % len(p["theta_ood"]), []).append(seed)
    if any(len(group) < 2 for group in groups.values()):
        raise ValueError("two world seeds per OOD stratum required for content-scramble")
    return {
        seed: group[(i + 1) % len(group)]
        for group in groups.values() for i, seed in enumerate(group)
    }


def evaluate(
    seeds: list[int], protocol: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not seeds or len(seeds) != len(set(seeds)) or any(type(s) is not int for s in seeds):
        raise ValueError("world seeds must be independent integers")
    p = protocol["model"]
    paired_coupled = {s: evaluate_world(s, "COUPLED", protocol) for s in seeds}
    source_map = donor_rotation(seeds, p)
    rows = []
    by: dict[tuple[int, str], dict[str, Any]] = {}
    for seed in seeds:
        for arm in ARMS:
            if arm == "COUPLED":
                row, _ = paired_coupled[seed]
            elif arm == "SCRAMBLED_CONTENT":
                row, _ = evaluate_world(
                    seed, arm, protocol, donor_packets=paired_coupled[source_map[seed]][1]
                )
            else:
                row, _ = evaluate_world(seed, arm, protocol)
            rows.append(row)
            by[seed, arm] = row
    emulator_equal = all(
        by[s, "COUPLED"]["trace_sha256"]
        == by[s, "CENTRAL_EMULATOR"]["trace_sha256"]
        and by[s, "COUPLED"]["success"]
        == by[s, "CENTRAL_EMULATOR"]["success"]
        and by[s, "COUPLED"]["operation_proxy"]
        == by[s, "CENTRAL_EMULATOR"]["operation_proxy"]
        for s in seeds
    )
    envelope_equal = all(
        by[s, "COUPLED"]["message_bytes"] ==
        by[s, "SCRAMBLED_CONTENT"]["message_bytes"] for s in seeds
    )
    # Exact multiset equality of DONOR packets against contemporaneous COUPLED
    # source packets within each precommitted theta/tick stratum.
    packet_marginals_equal = True
    for stratum in set(s % len(p["theta_ood"]) for s in seeds):
        group = [s for s in seeds if s % len(p["theta_ood"]) == stratum]
        for tick in range(p["horizon"]):
            for axis in (0, 1):
                original = Counter(paired_coupled[s][1][tick][axis] for s in group)
                permuted = Counter(
                    paired_coupled[source_map[s]][1][tick][axis] for s in group
                )
                if original != permuted:
                    packet_marginals_equal = False
    mean_success = {
        arm: sum(by[s, arm]["success"] for s in seeds) / len(seeds)
        for arm in ARMS
    }
    mean_goal_error = {
        arm: sum(by[s, arm]["goal_error"] for s in seeds) / len(seeds)
        for arm in ARMS
    }
    contrasts = {}
    for baseline in BASELINES:
        ds = [
            by[s, "COUPLED"]["success"] - by[s, baseline]["success"]
            for s in seeds
        ]
        # One-sided Hoeffding LCB for paired differences in [-1,1].
        lcb = sum(ds) / len(ds) - math.sqrt(
            2 * math.log(len(BASELINES) / protocol["alpha"]) / len(ds)
        )
        contrasts[baseline] = {
            "n_worlds": len(ds),
            "mean_paired_difference": sum(ds) / len(ds),
            "one_sided_lcb_exploratory_only": lcb,
        }
    summary = {
        "mean_success_by_arm": mean_success,
        "mean_goal_error_by_arm": mean_goal_error,
        "contrasts_exploratory": contrasts,
        "emulator_exact_trace_parity": emulator_equal,
        "scramble_current_tick_envelope_parity": envelope_equal,
        "scramble_donor_message_marginals_exact": packet_marginals_equal,
        "donor_rotation_sha256": sha(canon(source_map)),
        "all_world_budget_envelopes_pass": all(r["budget_ok"] for r in rows),
        "max_control_effort": max(r["control_energy_proxy"] for r in rows),
        "max_operation_proxy": max(r["operation_proxy"] for r in rows),
        "max_message_bytes": max(r["message_bytes"] for r in rows),
        "safety_by_arm": {
            arm: sum(by[s, arm]["safe"] for s in seeds) / len(seeds)
            for arm in ARMS
        },
    }
    return rows, summary


def render_csv(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        raise ValueError("empty output")
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def generate_payload(
    seeds: list[int], phase: str, p: dict[str, Any]
) -> dict[str, bytes]:
    rows, summary = evaluate(seeds, p)
    if (not summary["emulator_exact_trace_parity"]
        or not summary["scramble_current_tick_envelope_parity"]
        or not summary["scramble_donor_message_marginals_exact"]
        or not summary["all_world_budget_envelopes_pass"]):
        verdict = "INVALID"
    else:
        verdict = "EXPLORATORY_INTERNAL_ONLY"
    return {
        "protocol.json": (HERE / "protocol.json").read_bytes(),
        "preregistration.md": (HERE / "PREREGISTRATION.md").read_bytes(),
        "seeds.json": canon({"phase": phase, "seeds": seeds, "n_worlds": len(seeds)}),
        "episodes.csv": render_csv(rows),
        "diagnostics.json": canon(summary),
        "verdict.json": canon({
            "hypothesis_status": p["hypothesis_status"],
            "experiment": p["id"], "phase": phase, "verdict": verdict,
            "collective_emergence_established": False,
            "scientific_promotion_authorized": False,
            "independent_blind_replication": False,
            "basis": "new preregistered synthetic mechanism pilot; matched monolith exact",
            "unqualified": [
                "physical power and compute parity", "biological validity",
                "PID causal mediation", "actual parameter Fisher information",
                "independent replication", "general intelligence",
            ],
        }),
        "resource_measurement.json": canon({
            "envelopes": p["resource_envelope"],
            "max_control_energy_proxy": summary["max_control_effort"],
            "max_algorithmic_operation_proxy": summary["max_operation_proxy"],
            "max_logical_message_bytes": summary["max_message_bytes"],
            "physical_joules_verified": False, "hardware_flops_verified": False,
            "latency_benchmark_verified": False, "training_budget_verified": False,
        }),
        "ablation_contract.json": canon({
            "scramble_method": "same-tick same-theta-stratum bijective world-seed rotation",
            "same_time_packet_bytes": True,
            "donor_marginals_exact": summary["scramble_donor_message_marginals_exact"],
            "conditional_message_distribution_equivalence_claimed": False,
            "central_emulator_trace_parity": summary["emulator_exact_trace_parity"],
            "oracle_authority": "DIAGNOSTIC_ONLY",
        }),
    }


def write_bundle(out: Path, seeds: list[int], phase: str, p: dict[str, Any]) -> None:
    if out.exists() and any(out.iterdir()):
        raise FileExistsError("evidence bundle is immutable; use a fresh destination")
    payload = generate_payload(seeds, phase, p)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in payload.items():
        (out / name).write_bytes(content)
    (out / "SHA256SUMS").write_text(
        "".join(
            f"{sha(payload[name])}  {name}\n" for name in sorted(payload)
        ),
        encoding="ascii",
    )


def verify_bundle(out: Path, p: dict[str, Any]) -> None:
    if not out.is_dir() or out.is_symlink():
        raise ValueError("invalid evidence path")
    entries = list(out.iterdir())
    if any(not item.is_file() or item.is_symlink() for item in entries):
        raise ValueError("non-file evidence member")
    lines = (out / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    manifest = {}
    for line in lines:
        if line.count("  ") != 1:
            raise ValueError("invalid manifest record")
        h, name = line.split("  ", 1)
        if (name in manifest or len(h) != 64
                or any(c not in "0123456789abcdef" for c in h)
                or not name or "/" in name or "\\" in name):
            raise ValueError("noncanonical manifest entry")
        manifest[name] = h
    if list(manifest) != sorted(manifest):
        raise ValueError("unsorted manifest")
    actual = {item.name for item in entries if item.name != "SHA256SUMS"}
    if set(manifest) != actual:
        raise ValueError("unexpected/missing evidence artifact")
    for name, h in manifest.items():
        if sha((out / name).read_bytes()) != h:
            raise ValueError(f"SHA256 mismatch for {name}")
    seed_obj = json.loads((out / "seeds.json").read_text(encoding="utf-8"))
    seeds, phase = seed_obj["seeds"], seed_obj["phase"]
    if (len(seeds) != seed_obj.get("n_worlds") or
            len(seeds) != len(set(seeds)) or
            phase not in ("SMOKE", "PRIMARY")):
        raise ValueError("invalid cohort integrity")
    frozen = p["cohorts"]["smoke"] if phase == "SMOKE" else list(
        range(p["cohorts"]["primary_start"], p["cohorts"]["primary_start"] + p["cohorts"]["primary_count"])
    )
    if seeds != frozen:
        raise ValueError("not the frozen cohort")
    if p["source_sha256"] != sha(
        (HERE.parent / "cneh_exp_01" / "CNEH-04-DC_Formal_Specification.md").read_bytes()
    ):
        raise ValueError("canonical mathematics provenance changed")
    payload = generate_payload(seeds, phase, p)
    if set(payload) != actual:
        raise ValueError("unregistered evidence member")
    for name, value in payload.items():
        if (out / name).read_bytes() != value:
            raise ValueError(f"re-signed evidence fraud or non-replayable output: {name}")
    result = json.loads(payload["verdict.json"])
    if (result["scientific_promotion_authorized"] or
            result["collective_emergence_established"] or
            result["independent_blind_replication"]):
        raise ValueError("forbidden scientific promotion")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "primary"), default="smoke")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    opts = parser.parse_args()
    p = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    if (p["hypothesis_status"] != "FORMALIZED / EMPIRICAL VALIDATION PENDING"
        or p["scientific_promotion_allowed"] is not False
        or p["protocol_tier"] != "SYNTHETIC_MECHANISM_EXPLORATION_ONLY"):
        raise ValueError("scientific claim guard failed")
    if opts.verify:
        verify_bundle(opts.out, p)
        print("CNEH-EXP-02 verified: full replay, SHA256, sealed outcomes and no promotion")
        return
    c = p["cohorts"]
    seeds = c["smoke"] if opts.phase == "smoke" else list(
        range(c["primary_start"], c["primary_start"] + c["primary_count"])
    )
    write_bundle(opts.out, seeds, opts.phase.upper(), p)
    verify_bundle(opts.out, p)
    print(f"CNEH-EXP-02 {opts.phase.upper()}: evidence sealed, EXPLORATORY ONLY")


if __name__ == "__main__":
    main()
