from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from experiments.cwc_flagship_route_02 import core as r2

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "DGC-03-LOCAL-MODEL"
OUT = ROOT / "artifacts/dgc-03-local-model"
ALPHA = 0.10
SAVINGS_TARGET = 0.30
EPS = 1e-12


@dataclass(frozen=True, slots=True)
class CalibrationContract:
    seed: int
    fit_count: int
    bound_count: int
    residual_lower_offset: float
    lambda_loss_per_flop: dict[str, float]
    gain_model: dict[str, Any]
    calibration_diagnostics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PolicyMetric:
    name: str
    mean_loss: float
    logical_flops_per_window: float
    continue_rate: float
    savings_vs_depth2: float
    delta_quality_vs_depth2: float


def _split_bucket(case_id: str) -> int:
    raw = hashlib.sha256(f"{EXPERIMENT_ID}|{case_id}".encode("utf-8")).digest()
    return int.from_bytes(raw[:8], "big") % 3


def split_calibration(rows: Iterable[r2.EvalRow]) -> tuple[list[r2.EvalRow], list[r2.EvalRow]]:
    fit: list[r2.EvalRow] = []
    bound: list[r2.EvalRow] = []
    for row in rows:
        (bound if _split_bucket(row.case_id) == 2 else fit).append(row)
    if len(fit) < 20 or len(bound) < 10:
        raise r2.ProtocolViolation("insufficient deterministic FIT/BOUND calibration rows")
    return fit, bound


def conformal_lower_offset(residuals: Iterable[float], alpha: float = ALPHA) -> float:
    values = sorted(float(x) for x in residuals)
    if not values or not (0.0 < alpha < 1.0):
        raise ValueError("non-empty residuals and alpha in (0,1) required")
    if any(not math.isfinite(x) for x in values):
        raise ValueError("finite residuals required")
    k = max(1, math.floor(alpha * (len(values) + 1)))
    k = min(k, len(values))
    return values[k - 1]


def _rows_xy(rows: Iterable[r2.EvalRow]) -> tuple[np.ndarray, np.ndarray]:
    rs = list(rows)
    x = np.asarray([row.feature for row in rs], dtype=float)
    gain = np.asarray([row.gain for row in rs], dtype=float)
    return x, gain


def make_calibration(seed: int, calibration_rows: dict[str, list[r2.EvalRow]]) -> CalibrationContract:
    pooled = calibration_rows["PROSE"] + calibration_rows["CODE"]
    fit, bound = split_calibration(pooled)
    x_fit, y_fit = _rows_xy(fit)
    model = r2.fit_ridge(x_fit, y_fit, cohort="CALIBRATION")
    x_bound, y_bound = _rows_xy(bound)
    pred_bound = model.predict(x_bound)
    residuals = y_bound - pred_bound
    offset = conformal_lower_offset(residuals)
    empirical_coverage = float(np.mean(y_bound >= pred_bound + offset - 1e-15))

    f = r2.flop_contract()
    lambdas: dict[str, float] = {}
    family_diag: dict[str, Any] = {}
    for family in ("PROSE", "CODE"):
        fam_fit = [row for row in fit if row.family == family]
        if not fam_fit:
            raise r2.ProtocolViolation(f"no FIT rows for {family}")
        mean_l1 = float(np.mean([row.loss1 for row in fam_fit]))
        mean_l2 = float(np.mean([row.loss2 for row in fam_fit]))
        lambdas[family] = max(0.0, (mean_l1 - mean_l2) / f.block)
        family_diag[family] = {
            "fit_rows": len(fam_fit),
            "mean_loss1": mean_l1,
            "mean_loss2": mean_l2,
            "lambda_loss_per_flop": lambdas[family],
        }

    return CalibrationContract(
        seed=seed,
        fit_count=len(fit),
        bound_count=len(bound),
        residual_lower_offset=float(offset),
        lambda_loss_per_flop=lambdas,
        gain_model=model.to_dict(),
        calibration_diagnostics={
            "alpha": ALPHA,
            "bound_empirical_lower_coverage": empirical_coverage,
            "residual_min": float(np.min(residuals)),
            "residual_mean": float(np.mean(residuals)),
            "residual_max": float(np.max(residuals)),
            "family": family_diag,
        },
    )


def _policy_loss(loss1: np.ndarray, loss2: np.ndarray, mask: np.ndarray) -> float:
    return float(np.mean(np.where(mask, loss2, loss1)))


def _random_matched(case_ids: list[str], n: int) -> np.ndarray:
    scores = [int(hashlib.sha256(f"{EXPERIMENT_ID}|RANDOM|{cid}".encode()).hexdigest(), 16) for cid in case_ids]
    order = sorted(range(len(case_ids)), key=lambda i: (scores[i], case_ids[i]))
    out = np.zeros(len(case_ids), dtype=bool)
    for i in order[:n]:
        out[i] = True
    return out


def _select_top(scores: np.ndarray, n: int, case_ids: list[str]) -> np.ndarray:
    order = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), case_ids[i]))
    out = np.zeros(len(scores), dtype=bool)
    for i in order[:n]:
        out[i] = True
    return out


def _metric(name: str, mask: np.ndarray, loss1: np.ndarray, loss2: np.ndarray) -> PolicyMetric:
    f = r2.flop_contract()
    n = len(mask)
    n_cont = int(mask.sum())
    compute = r2.dynamic_compute(n_cont, n)
    loss = _policy_loss(loss1, loss2, mask)
    depth2 = float(np.mean(loss2))
    return PolicyMetric(
        name=name,
        mean_loss=loss,
        logical_flops_per_window=compute,
        continue_rate=n_cont / n,
        savings_vs_depth2=1.0 - compute / f.fixed_depth2,
        delta_quality_vs_depth2=depth2 - loss,
    )


def evaluate_cell(
    *,
    rows: list[r2.EvalRow],
    calibration: CalibrationContract,
    r2_policy: dict[str, Any],
) -> dict[str, Any]:
    if not rows:
        raise r2.ProtocolViolation("empty DGC-03 cell")
    family, cohort = rows[0].family, rows[0].cohort
    if cohort not in ("PRIMARY", "REPLICATION"):
        raise r2.ProtocolViolation("DGC-03 scientific rows must be PRIMARY/REPLICATION")
    if any(row.family != family or row.cohort != cohort for row in rows):
        raise r2.ProtocolViolation("mixed DGC-03 cell")

    x = np.asarray([row.feature for row in rows], dtype=float)
    gain = np.asarray([row.gain for row in rows], dtype=float)
    loss1 = np.asarray([row.loss1 for row in rows], dtype=float)
    loss2 = np.asarray([row.loss2 for row in rows], dtype=float)
    ids = [row.case_id for row in rows]
    model = r2.RidgeModel.from_dict(calibration.gain_model)
    pred = model.predict(x)
    lower = pred + calibration.residual_lower_offset
    f = r2.flop_contract()
    cost_threshold = calibration.lambda_loss_per_flop[family] * f.block

    dgc = lower > cost_threshold
    point_same = pred > cost_threshold

    r2_model = r2.RidgeModel.from_dict(r2_policy["gain_model"])
    r2_pred = r2_model.predict(x)
    r2_threshold = float(r2_policy["frontier"][family]["gain_per_flop"]) * f.block
    r2_mask = r2_pred > r2_threshold

    n_dgc = int(dgc.sum())
    masks = {
        "DGC_CONSERVATIVE_LCB": dgc,
        "POINT_SAME_SPLIT": point_same,
        "R2_FULL_CALIBRATION_POINT": r2_mask,
        "RANDOM_MATCHED": _random_matched(ids, n_dgc),
        "ORACLE_MATCHED": _select_top(gain, n_dgc, ids),
        "FIXED_DEPTH_1": np.zeros(len(rows), dtype=bool),
        "FIXED_DEPTH_2": np.ones(len(rows), dtype=bool),
    }
    metrics = {name: asdict(_metric(name, mask, loss1, loss2)) for name, mask in masks.items()}

    dgc_metric = metrics["DGC_CONSERVATIVE_LCB"]
    frontier_loss = r2.fixed_frontier_loss(
        float(np.mean(loss1)), float(np.mean(loss2)), float(dgc_metric["logical_flops_per_window"])
    )
    metrics["FIXED_FRONTIER_AT_DGC"] = {
        "name": "FIXED_FRONTIER_AT_DGC",
        "mean_loss": frontier_loss,
        "logical_flops_per_window": dgc_metric["logical_flops_per_window"],
        "continue_rate": dgc_metric["continue_rate"],
        "savings_vs_depth2": dgc_metric["savings_vs_depth2"],
        "delta_quality_vs_depth2": float(np.mean(loss2)) - frontier_loss,
    }

    lower_coverage = float(np.mean(gain >= lower - 1e-15))
    return {
        "seed": calibration.seed,
        "family": family,
        "cohort": cohort,
        "n_cases": len(rows),
        "coverage": 1.0,
        "cost_threshold_gain": cost_threshold,
        "residual_lower_offset": calibration.residual_lower_offset,
        "eval_lower_bound_coverage_diagnostic": lower_coverage,
        "metrics": metrics,
    }


def _pool_policy(cells: list[dict[str, Any]], policy: str) -> dict[str, float]:
    total_n = sum(int(c["n_cases"]) for c in cells)
    if total_n <= 0:
        raise r2.ProtocolViolation("empty cohort")
    mean_loss = sum(c["metrics"][policy]["mean_loss"] * c["n_cases"] for c in cells) / total_n
    flops = sum(c["metrics"][policy]["logical_flops_per_window"] * c["n_cases"] for c in cells) / total_n
    f = r2.flop_contract()
    depth2_loss = sum(c["metrics"]["FIXED_DEPTH_2"]["mean_loss"] * c["n_cases"] for c in cells) / total_n
    cont = sum(c["metrics"][policy]["continue_rate"] * c["n_cases"] for c in cells) / total_n
    return {
        "n": total_n,
        "mean_loss": mean_loss,
        "logical_flops_per_window": flops,
        "continue_rate": cont,
        "savings_vs_depth2": 1.0 - flops / f.fixed_depth2,
        "delta_quality_vs_depth2": depth2_loss - mean_loss,
    }


def cohort_summary(cells: list[dict[str, Any]], cohort: str) -> dict[str, Any]:
    if len(cells) != 6 or any(c["cohort"] != cohort for c in cells):
        raise r2.ProtocolViolation(f"{cohort}: expected six seed/family cells")
    policies = (
        "DGC_CONSERVATIVE_LCB", "POINT_SAME_SPLIT", "R2_FULL_CALIBRATION_POINT",
        "RANDOM_MATCHED", "ORACLE_MATCHED", "FIXED_DEPTH_1", "FIXED_DEPTH_2",
        "FIXED_FRONTIER_AT_DGC",
    )
    pooled = {p: _pool_policy(cells, p) for p in policies}
    dgc = pooled["DGC_CONSERVATIVE_LCB"]
    r2p = pooled["R2_FULL_CALIBRATION_POINT"]
    threshold_met = (
        dgc["savings_vs_depth2"] >= SAVINGS_TARGET - EPS
        and dgc["delta_quality_vs_depth2"] >= -EPS
        and all(abs(float(c["coverage"]) - 1.0) <= EPS for c in cells)
    )
    pareto_dom = (
        dgc["logical_flops_per_window"] <= r2p["logical_flops_per_window"] + EPS
        and dgc["mean_loss"] <= r2p["mean_loss"] + EPS
        and (
            dgc["logical_flops_per_window"] < r2p["logical_flops_per_window"] - EPS
            or dgc["mean_loss"] < r2p["mean_loss"] - EPS
        )
    )
    return {
        "cohort": cohort,
        "cells": len(cells),
        "policies": pooled,
        "local_model_30pct_met": threshold_met,
        "dgc_pareto_dominates_r2_point": pareto_dom,
        "minimum_eval_lower_bound_coverage_diagnostic": min(c["eval_lower_bound_coverage_diagnostic"] for c in cells),
    }


def final_verdict(primary: dict[str, Any], replication: dict[str, Any]) -> dict[str, str]:
    threshold = (
        "LOCAL_MODEL_30PCT_MET"
        if primary["local_model_30pct_met"] and replication["local_model_30pct_met"]
        else "LOCAL_MODEL_30PCT_NOT_SUPPORTED"
    )
    router = (
        "DGC_BEATS_INTERNAL_POINT_ROUTER"
        if primary["dgc_pareto_dominates_r2_point"] and replication["dgc_pareto_dominates_r2_point"]
        else "DGC_INTERNAL_POINT_ROUTER_SUPERIORITY_NOT_SUPPORTED"
    )
    return {"local_model_threshold": threshold, "internal_router": router}
