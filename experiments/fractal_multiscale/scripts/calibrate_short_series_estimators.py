from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections.abc import Callable
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC = PKG_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cwc_fractal.metrics import compute_fractal_metrics  # noqa: E402


def iid(rng: random.Random, n: int) -> list[float]:
    return [rng.gauss(0.0, 1.0) for _ in range(n)]


def ar1(rng: random.Random, n: int, phi: float = 0.8) -> list[float]:
    sigma = math.sqrt(max(1e-12, 1.0 - phi * phi))
    x = rng.gauss(0.0, 1.0)
    out = []
    for _ in range(n):
        x = phi * x + sigma * rng.gauss(0.0, 1.0)
        out.append(x)
    return out


def random_walk(rng: random.Random, n: int) -> list[float]:
    x = 0.0
    out = []
    for _ in range(n):
        x += rng.gauss(0.0, 1.0)
        out.append(x)
    return out


def trend_noise(rng: random.Random, n: int) -> list[float]:
    slope = rng.choice((-1.0, 1.0)) * 2.0 / max(n - 1, 1)
    return [slope * i + rng.gauss(0.0, 0.7) for i in range(n)]


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    pos = q * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "sd": statistics.pstdev(values),
        "q025": quantile(values, 0.025),
        "q10": quantile(values, 0.10),
        "median": quantile(values, 0.50),
        "q90": quantile(values, 0.90),
        "q975": quantile(values, 0.975),
        "interval95_width": quantile(values, 0.975) - quantile(values, 0.025),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replicates", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.replicates < 500:
        raise SystemExit("replicates must be >= 500")

    generators: dict[str, Callable[[random.Random, int], list[float]]] = {
        "iid_gaussian": iid,
        "ar1_phi_0p8": ar1,
        "random_walk": random_walk,
        "linear_trend_plus_noise": trend_noise,
    }
    lengths = (32, 64, 128)
    cells = {}
    rng = random.Random(args.seed)
    for process, generator in generators.items():
        for n in lengths:
            hurst: list[float] = []
            box: list[float] = []
            rough: list[float] = []
            entropy1: list[float] = []
            for _ in range(args.replicates):
                metrics = compute_fractal_metrics(generator(rng, n))
                hurst.append(metrics.hurst)
                box.append(metrics.box_dimension)
                rough.append(metrics.roughness)
                entropy1.append(metrics.multiscale_entropy.get(1, 0.0))
            cells[f"{process}:n={n}"] = {
                "hurst_rs": summarize(hurst),
                "box_counting_dimension": summarize(box),
                "roughness": summarize(rough),
                "binary_sign_entropy_scale1": summarize(entropy1),
            }

    # A practical fragility diagnostic: overlap of the central 95% intervals between iid and AR(1).
    overlap = {}
    for n in lengths:
        iid_h = cells[f"iid_gaussian:n={n}"]["hurst_rs"]
        ar_h = cells[f"ar1_phi_0p8:n={n}"]["hurst_rs"]
        lower = max(iid_h["q025"], ar_h["q025"])
        upper = min(iid_h["q975"], ar_h["q975"])
        overlap[f"n={n}"] = max(0.0, upper - lower)

    payload = {
        "schema_version": "cwc.fractal.estimator_calibration.v1",
        "replicates_per_cell": args.replicates,
        "cell_count": len(generators) * len(lengths),
        "total_simulated_series": args.replicates * len(generators) * len(lengths),
        "seed": args.seed,
        "cells": cells,
        "iid_vs_ar1_hurst_95_interval_overlap": overlap,
        "verdict": "SHORT_SERIES_FRACTAL_METRICS_DIAGNOSTIC_ONLY",
        "claim_boundary": (
            "This Monte Carlo calibrates the repository's finite-sample estimators. It does not "
            "establish theoretical consistency, fractality of CWC traces, or a universal threshold."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "total_simulated_series": payload["total_simulated_series"],
                "overlap": overlap,
                "verdict": payload["verdict"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
