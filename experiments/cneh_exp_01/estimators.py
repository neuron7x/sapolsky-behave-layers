"""Analytic component qualification; not causal estimation on neural samples.

Definitions and limits are frozen in qualification_contract.json. No sample-based
PID, nonlinear observability, or closed-loop likelihood is inferred here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _number(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("expected finite real number, excluding bool")
    return float(value)


def _matrix(value: list[list[float]]) -> list[list[float]]:
    if not isinstance(value, list) or not value or not isinstance(value[0], list) or not value[0]:
        raise ValueError("expected nonempty matrix")
    width = len(value[0])
    if any(not isinstance(row, list) or len(row) != width for row in value):
        raise ValueError("ragged matrix")
    return [[_number(x) for x in row] for row in value]


def _finite_matrix(value: list[list[float]]) -> list[list[float]]:
    if any(not math.isfinite(x) for row in value for x in row):
        raise ValueError("numerical overflow in estimator")
    return value


def gaussian_mean_fisher(sensitivities: list[list[float]], variance: float) -> list[list[float]]:
    """J.T J / variance for independent N(mu_i(theta), variance) observations."""
    j = _matrix(sensitivities)
    variance = _number(variance)
    if variance <= 0:
        raise ValueError("variance must be positive")
    n = len(j[0])
    return _finite_matrix([[math.fsum(row[a] * row[b] for row in j) / variance
                            for b in range(n)] for a in range(n)])


def observability_gramian(a: list[list[float]], c: list[list[float]], horizon: int) -> list[list[float]]:
    """Discrete LTI W_o(T), observing t=0 through T-1; no stability assumption."""
    a, c = _matrix(a), _matrix(c)
    n = len(a)
    if any(len(row) != n for row in a) or len(c[0]) != n:
        raise ValueError("incompatible LTI dimensions")
    if type(horizon) is not int or horizon < 1 or horizon > 10000:
        raise ValueError("horizon must be an integer in [1,10000]")
    w = [[0.0] * n for _ in range(n)]
    ca = c
    for t in range(horizon):
        for i in range(n):
            for k in range(n):
                w[i][k] += math.fsum(row[i] * row[k] for row in ca)
        if t + 1 < horizon:
            ca = _finite_matrix([[math.fsum(row[k] * a[k][j] for k in range(n))
                                  for j in range(n)] for row in ca])
    return _finite_matrix(w)


def pid_imin(pmf: dict[tuple[int, int, int], float]) -> dict[str, float]:
    """Williams-Beer I_min for exact p(source1, source2, target), in bits.

    This is a named redundancy functional, not a unique definition of synergy
    and not an intervention-based causal estimator. Probabilities are not fitted.
    """
    if not isinstance(pmf, dict) or not pmf:
        raise ValueError("nonempty exact PMF required")
    p = {}
    for key, value in pmf.items():
        if not isinstance(key, tuple) or len(key) != 3 or any(type(x) is not int for x in key):
            raise ValueError("PMF keys must be triples of integer labels")
        value = _number(value)
        if value < 0 or value > 1:
            raise ValueError("invalid probability")
        if value:
            p[key] = value
    if not math.isclose(math.fsum(p.values()), 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError("PMF must sum to one without implicit normalization")
    py: dict[int, float] = {}
    for (_, _, y), v in p.items():
        py[y] = py.get(y, 0.0) + v

    def specific(indices: tuple[int, ...]) -> tuple[dict[int, float], float]:
        ps, psy = {}, {}
        for key, v in p.items():
            s, y = tuple(key[i] for i in indices), key[2]
            ps[s] = ps.get(s, 0.0) + v
            psy[s, y] = psy.get((s, y), 0.0) + v
        iy = {y: math.fsum((v / py[y]) * math.log2((v / py[y]) / ps[s])
                           for (s, yy), v in psy.items() if yy == y) for y in py}
        return iy, math.fsum(py[y] * iy[y] for y in py)

    i1, mi1 = specific((0,))
    i2, mi2 = specific((1,))
    _, joint = specific((0, 1))
    redundancy = math.fsum(py[y] * min(i1[y], i2[y]) for y in py)
    result = {"redundancy_bits": redundancy, "unique_1_bits": mi1 - redundancy,
              "unique_2_bits": mi2 - redundancy,
              "synergy_bits": joint - mi1 - mi2 + redundancy,
              "joint_information_bits": joint}
    if any(not math.isfinite(v) or v < -1e-12 for v in result.values()):
        raise ValueError("invalid numerical PID decomposition")
    return {k: 0.0 if abs(v) < 1e-15 else v for k, v in result.items()}


def qualify() -> dict:
    contract = json.loads((HERE / "qualification_contract.json").read_text())
    tol = contract["numerics"]
    checks = {}

    def close(name: str, actual: float, expected: float) -> None:
        checks[name] = {"actual": actual, "expected": expected,
                        "pass": math.isclose(actual, expected,
                                             abs_tol=tol["absolute_tolerance"],
                                             rel_tol=tol["relative_tolerance"])}

    close("gaussian_location", gaussian_mean_fisher([[1.0]] * 8, 4.0)[0][0], 2.0)
    close("variance_rescaling", gaussian_mean_fisher([[1.0]] * 8, 16.0)[0][0], 0.5)
    close("fisher_zero_sensitivity", gaussian_mean_fisher([[0.0]], 1.0)[0][0], 0.0)
    f = gaussian_mean_fisher([[1.0, 2.0], [2.0, 4.0]], 1.0)
    close("fisher_rank_deficiency", f[0][0] * f[1][1] - f[0][1] ** 2, 0.0)
    close("scalar_gramian", observability_gramian([[0.5]], [[2.0]], 5)[0][0],
          4 * (1 - 0.25 ** 5) / (1 - 0.25))
    close("zero_observation", observability_gramian([[0.5]], [[0.0]], 5)[0][0], 0.0)
    w = observability_gramian([[0.5, 0.0], [0.0, 0.75]], [[1.0, 0.0]], 5)
    close("unobserved_coordinate", w[1][1], 0.0)
    for name, pmf, expected in (
        ("xor", {(a, b, a ^ b): 0.25 for a in (0, 1) for b in (0, 1)}, (0, 0, 0, 1)),
        ("duplicate", {(0, 0, 0): 0.5, (1, 1, 1): 0.5}, (1, 0, 0, 0)),
        ("independent", {(a, b, y): 0.125 for a in (0, 1) for b in (0, 1) for y in (0, 1)}, (0, 0, 0, 0)),
    ):
        pid = pid_imin(pmf)
        for key, value in zip(("redundancy_bits", "unique_1_bits", "unique_2_bits", "synergy_bits"), expected):
            close(f"{name}_{key}", pid[key], value)
        close(f"{name}_reconstruction", sum(v for k, v in pid.items() if k != "joint_information_bits"),
              pid["joint_information_bits"])
    # Independent output-energy identity (not another Gramian calculation).
    a, c, x = [[0.7, 0.2], [-0.1, 0.8]], [[1.0, -0.25]], [0.3, -0.7]
    w = observability_gramian(a, c, 7)
    quadratic = sum(x[i] * w[i][j] * x[j] for i in range(2) for j in range(2))
    energy = 0.0
    for _ in range(7):
        energy += sum(c[0][i] * x[i] for i in range(2)) ** 2
        x = [sum(a[i][j] * x[j] for j in range(2)) for i in range(2)]
    close("gramian_trajectory_energy", quadratic, energy)
    asymmetric = {(0, 0, 0): 0.2, (1, 0, 1): 0.3, (1, 1, 1): 0.5}
    direct = pid_imin(asymmetric)
    swapped = pid_imin({(b, a, y): v for (a, b, y), v in asymmetric.items()})
    for k in ("synergy_bits", "redundancy_bits", "joint_information_bits"):
        close(f"source_permutation_{k}", direct[k], swapped[k])
    close("source_permutation_unique", direct["unique_1_bits"], swapped["unique_2_bits"])
    return {"schema": "cneh-analytic-qualification-v1",
            "status": "PASS" if all(v["pass"] for v in checks.values()) else "FAIL",
            "authority": "ANALYTIC_COMPONENTS_ONLY", "causal_attribution_qualified": False,
            "neural_estimators_qualified": False, "scientific_promotion_authorized": False,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "contract_sha256": hashlib.sha256((HERE / "qualification_contract.json").read_bytes()).hexdigest(),
            "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = qualify()
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(result["status"] + ": analytic components only; causal attribution UNIDENTIFIABLE")
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
