"""Pinned BN-Syn observation/action adapter; exploratory integration smoke only.

No download or third-party import occurs on import. Run with an isolated environment
containing the versions in bnsyn_integration_contract.json and a local source snapshot.
The source tree is authenticated against a frozen SHA256 digest, not a caller label.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "bnsyn_integration_contract.json"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid(value: str) -> Any:
        raise ValueError(f"nonfinite JSON constant: {value}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite JSON number")
        return parsed

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite_float)


def source_manifest(source: Path) -> dict[str, str]:
    """Hash exactly the source/metadata scope; reject importable untracked additions."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError("source must be a real directory")
    paths = [source / "LICENSE", source / "pyproject.toml"]
    src = source / "src"
    if src.is_symlink() or not src.is_dir():
        raise ValueError("missing source directory")
    for path in src.rglob("*"):
        if path.is_symlink():
            raise ValueError("source symlink forbidden")
        if path.is_file():
            paths.append(path)
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise ValueError("source metadata missing or symlinked")
    return {path.relative_to(source).as_posix(): sha(path.read_bytes())
            for path in sorted(paths)}


def validate_source(source: Path, contract: dict[str, Any]) -> dict[str, str]:
    manifest = source_manifest(source)
    expected = contract["source"]
    if (len(manifest) != expected["file_count"]
            or sha(canonical(manifest)) != expected["files_sha256"]):
        raise ValueError("pinned BN-Syn source digest mismatch")
    return manifest


def bounded_action(observation: tuple[float, float], contract: dict[str, Any]) -> tuple[float, float]:
    """The policy receives only the declared two voltage measurements, in mV."""
    if len(observation) != 2 or any(type(x) not in (int, float) or not math.isfinite(x)
                                    for x in observation):
        raise ValueError("two finite voltage observations required")
    p = contract["smoke"]
    a, b = observation
    target, base = p["target_voltage_mV"], p["base_current_pA"]
    gain, cross, bound = (p["feedback_gain_pA_per_mV"], p["cross_gain_pA_per_mV"],
                          p["current_bound_pA"])
    return tuple(max(0.0, min(bound, base + gain * (target - own) + cross * (other - own)))
                 for own, other in ((a, b), (b, a)))


def load_runtime(source: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Import only after checking every source byte and dependency version."""
    validate_source(source, contract)
    if os.environ.get("BNSYN_USE_TORCH") == "1":
        raise ValueError("unregistered Torch backend")
    for package, expected in contract["dependencies"].items():
        if importlib.metadata.version(package) != expected:
            raise ValueError(f"dependency version mismatch: {package}")
    already_loaded = [name for name in sys.modules if name == "bnsyn" or name.startswith("bnsyn.")]
    source_path = (source / "src").resolve()
    for name in already_loaded:
        filename = getattr(sys.modules[name], "__file__", None)
        if filename is None or not Path(filename).resolve().is_relative_to(source_path):
            raise ValueError("BN-Syn import from an unqualified source")
    # Prevent writing bytecode into the verified snapshot. Existing bytecode is an
    # extra source member and fails the digest before any import.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source_path))
    np = importlib.import_module("numpy")
    network = importlib.import_module("bnsyn.sim.network")
    config = importlib.import_module("bnsyn.config")
    for name, module in list(sys.modules.items()):
        if name == "bnsyn" or name.startswith("bnsyn."):
            filename = getattr(module, "__file__", None)
            if filename is None or not Path(filename).resolve().is_relative_to(source_path):
                raise ValueError("BN-Syn module escaped pinned source")
    return {"np": np, "network": network, "config": config}


def _hex_array(array: Any) -> list[str]:
    values = [float(value) for value in array.ravel()]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("nonfinite neural trajectory")
    return [value.hex() for value in values]


def episode(seed: int, arm: str, contract: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    p = contract["smoke"]
    if type(seed) is not int or arm not in p["arms"]:
        raise ValueError("invalid neural smoke seed/arm")
    np, network, config = (runtime[key] for key in ("np", "network", "config"))
    neurons, half = p["neurons"], p["neurons"] // 2
    net = network.Network(network.NetworkParams(N=neurons, p_conn=p["p_conn"]),
                          config.AdExParams(), config.SynapseParams(), config.CriticalityParams(),
                          dt_ms=p["dt_ms"], rng=np.random.default_rng(seed), backend=p["backend"])
    initial = {"voltage_mV": _hex_array(net.state.V_mV),
               "W_exc_nS": _hex_array(net.W_exc.to_dense()),
               "W_inh_nS": _hex_array(net.W_inh.to_dense())}
    trace = []
    total_spikes = 0
    lo, hi = float(np.min(net.state.V_mV)), float(np.max(net.state.V_mV))
    for step in range(p["steps"]):
        observation = (float(np.mean(net.state.V_mV[:half])),
                       float(np.mean(net.state.V_mV[half:])))
        action = ((0.0, 0.0) if arm == "ZERO_ACTION" else bounded_action(observation, contract))
        currents = np.concatenate((np.full(half, action[0]), np.full(neurons - half, action[1])))
        metrics = net.step(external_current_pA=currents)
        if not all(math.isfinite(float(value)) for value in metrics.values()):
            raise ValueError("nonfinite neural metrics")
        total_spikes += int(np.sum(net.state.spiked))
        lo, hi = min(lo, float(np.min(net.state.V_mV))), max(hi, float(np.max(net.state.V_mV)))
        trace.append({"step": step, "observation_mV": [value.hex() for value in observation],
                      "action_pA": [value.hex() for value in action],
                      "voltage_mV": _hex_array(net.state.V_mV),
                      "adaptation_pA": _hex_array(net.state.w_pA),
                      "g_ampa_nS": _hex_array(net.g_ampa), "g_nmda_nS": _hex_array(net.g_nmda),
                      "g_gabaa_nS": _hex_array(net.g_gabaa),
                      "spikes": [int(value) for value in net.state.spiked],
                      "metrics": {key: float(value).hex() for key, value in metrics.items()},
                      "rng_sha256": sha(canonical(net.rng.bit_generator.state))})
    payload = {"initial": initial, "trace": trace}
    response = [{key: value for key, value in row.items()
                 if key not in ("action_pA", "observation_mV", "rng_sha256", "step")}
                for row in trace]
    return {"seed": seed, "arm": arm, "trace_sha256": sha(canonical(payload)),
            "response_sha256": sha(canonical(response)), "total_spikes": total_spikes,
            "voltage_range_mV": hi - lo, "payload": payload}


def check_episodes(episodes: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    expected = [(seed, arm) for seed in contract["smoke"]["seeds"] for arm in contract["smoke"]["arms"]]
    if [(row["seed"], row["arm"]) for row in episodes] != expected:
        raise ValueError("wrong neural cohort/arm roster")
    by = {(row["seed"], row["arm"]): row for row in episodes}
    for row in episodes:
        if sha(canonical(row["payload"])) != row["trace_sha256"]:
            raise ValueError("neural trace hash mismatch")
    for seed in contract["smoke"]["seeds"]:
        coupled, central, zero = [by[(seed, arm)] for arm in contract["smoke"]["arms"]]
        if coupled["trace_sha256"] != central["trace_sha256"]:
            raise ValueError("neural central emulator parity violation")
        if coupled["response_sha256"] == zero["response_sha256"]:
            raise ValueError("neural action responsiveness absent")
        if (coupled["total_spikes"] < contract["acceptance"]["minimum_total_spikes"]
                or coupled["voltage_range_mV"] <= contract["acceptance"]["minimum_voltage_range_mV"]):
            raise ValueError("inactive neural substrate")


def execute(source: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    contract = strict_json(CONTRACT.read_bytes())
    manifest = validate_source(source, contract)
    runtime = load_runtime(source, contract)
    episodes = [episode(seed, arm, contract, runtime)
                for seed in contract["smoke"]["seeds"] for arm in contract["smoke"]["arms"]]
    check_episodes(episodes, contract)
    for row in episodes:
        replay = episode(row["seed"], row["arm"], contract, runtime)
        if canonical(replay) != canonical(row):
            raise ValueError("neural deterministic replay mismatch")
    if validate_source(source, contract) != manifest:
        raise ValueError("source changed during neural execution")
    distributions = {dist.metadata["Name"]: dist.version
                     for dist in importlib.metadata.distributions() if dist.metadata["Name"]}
    report = {"schema": "cneh-bnsyn-integration-report-v1", "status": "INTEGRATION_SMOKE_ONLY",
              "scientific_promotion_authorized": False, "physical_cost_qualified": False,
              "independent_replication": False, "neural_efficacy_qualified": False,
              "source": contract["source"], "source_file_sha256": manifest,
              "adapter_sha256": sha(Path(__file__).read_bytes()),
              "contract_sha256": sha(CONTRACT.read_bytes()),
              "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                          "installed_distributions": distributions},
              "checks": {"source_verified": True, "finite_trajectories": True,
                         "emulator_exact_parity": True, "all_arm_exact_replay": True,
                         "active_spiking": True, "action_responsiveness": True},
              "episodes": [{key: value for key, value in row.items() if key != "payload"}
                           for row in episodes], "limitations": contract["limitations"]}
    return report, episodes


def write_bundle(out: Path, report: dict[str, Any], episodes: list[dict[str, Any]]) -> None:
    if out.exists():
        raise FileExistsError("refuse overwrite of neural evidence")
    out.mkdir(parents=True)
    files = {"report.json": canonical(report), "contract.json": CONTRACT.read_bytes(),
             "traces.json.gz": gzip.compress(canonical(episodes), mtime=0)}
    for name, payload in files.items():
        (out / name).write_bytes(payload)
    (out / "SHA256SUMS").write_text("".join(f"{sha(files[name])}  {name}\n" for name in sorted(files)),
                                    encoding="ascii")


def verify_bundle(out: Path, source: Path) -> dict[str, Any]:
    names = {"report.json", "contract.json", "traces.json.gz", "SHA256SUMS"}
    if out.is_symlink() or not out.is_dir():
        raise ValueError("invalid neural evidence directory")
    if {path.name for path in out.iterdir()} != names or any(
            path.is_symlink() or not path.is_file() for path in out.iterdir()):
        raise ValueError("neural evidence membership mismatch")
    expected = "".join(f"{sha((out / name).read_bytes())}  {name}\n" for name in sorted(names - {"SHA256SUMS"}))
    if (out / "SHA256SUMS").read_text(encoding="ascii") != expected:
        raise ValueError("neural evidence manifest mismatch")
    if (out / "contract.json").read_bytes() != CONTRACT.read_bytes():
        raise ValueError("neural contract drift")
    report, episodes = execute(source)
    if canonical(strict_json((out / "report.json").read_bytes())) != canonical(report):
        raise ValueError("neural report replay mismatch")
    saved = strict_json(gzip.decompress((out / "traces.json.gz").read_bytes()))
    if canonical(saved) != canonical(episodes):
        raise ValueError("neural trace replay mismatch")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        report = verify_bundle(args.out, args.source)
    else:
        if args.out.exists():
            raise FileExistsError("refuse overwrite of neural evidence")
        report, episodes = execute(args.source)
        write_bundle(args.out, report, episodes)
    print(json.dumps({"status": report["status"], "checks": report["checks"],
                      "scientific_promotion_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
