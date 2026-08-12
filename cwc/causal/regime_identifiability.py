from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from statistics import NormalDist

import numpy as np


class AssumptionClass(str, Enum):
    """How an identifying assumption can be supported by the available channel."""

    EMPIRICALLY_FALSIFIABLE = "EMPIRICALLY_FALSIFIABLE"
    PARTIALLY_FALSIFIABLE = "PARTIALLY_FALSIFIABLE"
    PROVENANCE_REQUIRED = "PROVENANCE_REQUIRED"
    UNTESTABLE_FROM_FACTUAL_CHANNEL = "UNTESTABLE_FROM_FACTUAL_CHANNEL"


class AssumptionStatus(str, Enum):
    SURVIVED_AVAILABLE_TESTS = "SURVIVED_AVAILABLE_TESTS"
    VIOLATED = "VIOLATED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    NOT_TESTABLE_FROM_CHANNEL = "NOT_TESTABLE_FROM_CHANNEL"


@dataclass(frozen=True, slots=True)
class IdentifyingAssumption:
    assumption_id: str
    statement: str
    assumption_class: AssumptionClass
    status: AssumptionStatus
    witness: str


@dataclass(frozen=True, slots=True)
class InstrumentMoment:
    index: int
    cov_rx: float
    relevance_z: float
    beta_hat: float
    beta_se: float
    negative_control_z: float


@dataclass(frozen=True, slots=True)
class RegimeIVDecision:
    state: str
    beta_hat: float | None
    beta_se: float | None
    z_critical: float
    relevant_instruments: int
    instrument_moments: tuple[InstrumentMoment, ...]
    max_overidentification_z: float
    max_negative_control_z: float
    assumptions: tuple[IdentifyingAssumption, ...]
    causal_authority_granted: bool
    unresolved_assumption_debt: tuple[str, ...]


def _center(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=np.float64) - float(np.mean(x))


def _mean_se(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    if len(values) < 3:
        raise ValueError("at least three samples required")
    return float(np.std(values, ddof=1) / math.sqrt(len(values)))


def evaluate_regime_iv(
    *,
    regimes: np.ndarray,
    treatment: Sequence[float],
    outcome: Sequence[float],
    negative_control: Sequence[float],
    alpha: float = 0.01,
) -> RegimeIVDecision:
    """Evaluate a multi-regime linear-IV identifying contract.

    This is deliberately *not* a causal-truth oracle.  It checks observable
    implications of a declared IV-style assumption set:

    * relevance: at least two regime coordinates predict X;
    * partial exogeneity witness: regime coordinates are independent of a
      negative-control outcome W under the declared graph;
    * over-identification witness: independently induced Wald estimands agree.

    Exclusion and full exogeneity are not generally testable from (R, X, Y, W)
    alone.  Surviving the checks therefore returns only
    CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS and never grants causal authority.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be in (0,1)")
    R = np.asarray(regimes, dtype=np.float64)
    X = np.asarray(treatment, dtype=np.float64)
    Y = np.asarray(outcome, dtype=np.float64)
    W = np.asarray(negative_control, dtype=np.float64)
    if R.ndim != 2 or R.shape[1] < 2:
        raise ValueError("regimes must be n x k with k>=2")
    if not (len(X) == len(Y) == len(W) == R.shape[0]):
        raise ValueError("all arrays must have the same sample count")
    if len(X) < 32:
        raise ValueError("sample too small for the declared instrument")

    Xc, Yc, Wc = _center(X), _center(Y), _center(W)
    k = R.shape[1]
    pair_count = k * (k - 1) // 2
    family_tests = 2 * k + pair_count
    zcrit = NormalDist().inv_cdf(1.0 - alpha / (2.0 * family_tests))

    moments: list[InstrumentMoment] = []
    influence: list[np.ndarray | None] = []
    relevant: list[int] = []
    neg_violations: list[int] = []

    for j in range(k):
        r = _center(R[:, j])
        rx_samples = r * Xc
        cov_rx = float(np.mean(rx_samples))
        se_rx = _mean_se(rx_samples)
        relevance_z = math.inf if se_rx == 0 and cov_rx != 0 else (abs(cov_rx) / se_rx if se_rx > 0 else 0.0)

        rw_samples = r * Wc
        cov_rw = float(np.mean(rw_samples))
        se_rw = _mean_se(rw_samples)
        neg_z = math.inf if se_rw == 0 and cov_rw != 0 else (abs(cov_rw) / se_rw if se_rw > 0 else 0.0)

        if relevance_z > zcrit and abs(cov_rx) > 1e-15:
            ry = float(np.mean(r * Yc))
            beta = ry / cov_rx
            psi = r * (Yc - beta * Xc) / cov_rx
            beta_se = _mean_se(psi)
            relevant.append(j)
            influence.append(psi)
        else:
            beta = math.nan
            beta_se = math.inf
            influence.append(None)

        if neg_z > zcrit:
            neg_violations.append(j)
        moments.append(InstrumentMoment(j, cov_rx, relevance_z, float(beta), float(beta_se), neg_z))

    overid_zs: list[float] = []
    for a_pos, a in enumerate(relevant):
        for b in relevant[a_pos + 1 :]:
            psi_a = influence[a]
            psi_b = influence[b]
            assert psi_a is not None and psi_b is not None
            diff = moments[a].beta_hat - moments[b].beta_hat
            se_diff = _mean_se(psi_a - psi_b)
            z = math.inf if se_diff == 0 and diff != 0 else (abs(diff) / se_diff if se_diff > 0 else 0.0)
            overid_zs.append(z)

    overid_violation = bool(overid_zs) and max(overid_zs) > zcrit
    assumptions = [
        IdentifyingAssumption(
            "A1_RELEVANCE",
            "At least two observed regime coordinates shift treatment X.",
            AssumptionClass.EMPIRICALLY_FALSIFIABLE,
            AssumptionStatus.SURVIVED_AVAILABLE_TESTS if len(relevant) >= 2 else AssumptionStatus.VIOLATED,
            f"{len(relevant)}/{k} regime coordinates exceed multiplicity-controlled relevance threshold",
        ),
        IdentifyingAssumption(
            "A2_EXOGENEITY",
            "Regime assignment is independent of latent causes/noise of Y.",
            AssumptionClass.PARTIALLY_FALSIFIABLE,
            AssumptionStatus.VIOLATED if neg_violations else AssumptionStatus.NOT_ESTABLISHED,
            "negative-control association can falsify some violations but cannot prove full exogeneity",
        ),
        IdentifyingAssumption(
            "A3_EXCLUSION",
            "Regime affects Y only through X.",
            AssumptionClass.UNTESTABLE_FROM_FACTUAL_CHANNEL,
            AssumptionStatus.NOT_TESTABLE_FROM_CHANNEL,
            "coordinated direct effects can be observationally equivalent to a different causal coefficient",
        ),
        IdentifyingAssumption(
            "A4_EFFECT_INVARIANCE",
            "The causal coefficient beta is common across regime coordinates.",
            AssumptionClass.PARTIALLY_FALSIFIABLE,
            AssumptionStatus.VIOLATED if overid_violation else AssumptionStatus.SURVIVED_AVAILABLE_TESTS,
            "instrument-specific Wald estimands disagree"
            if overid_violation
            else "no multiplicity-controlled over-identification contradiction",
        ),
        IdentifyingAssumption(
            "A5_REGIME_MEASUREMENT",
            "Observed regime labels faithfully encode the assignment variable used by the identifying contract.",
            AssumptionClass.PROVENANCE_REQUIRED,
            AssumptionStatus.NOT_ESTABLISHED,
            "symmetric label corruption can preserve Wald ratios and is not excluded by the causal moments alone",
        ),
    ]

    max_neg = max((m.negative_control_z for m in moments), default=0.0)
    max_overid = max(overid_zs, default=0.0)
    violation = bool(neg_violations) or overid_violation

    beta_hat: float | None = None
    beta_se: float | None = None
    if relevant:
        weights = []
        vals = []
        for j in relevant:
            se = moments[j].beta_se
            if math.isfinite(se) and se > 0:
                weights.append(1.0 / (se * se))
                vals.append(moments[j].beta_hat)
        if weights:
            sw = sum(weights)
            beta_hat = float(sum(w * v for w, v in zip(weights, vals, strict=False)) / sw)
            beta_se = float(math.sqrt(1.0 / sw))

    if violation:
        state = "IDENTIFYING_ASSUMPTION_VIOLATED"
    elif len(relevant) < 2:
        state = "INSUFFICIENT_INFORMATION_BUDGET"
    else:
        state = "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"

    return RegimeIVDecision(
        state=state,
        beta_hat=beta_hat,
        beta_se=beta_se,
        z_critical=float(zcrit),
        relevant_instruments=len(relevant),
        instrument_moments=tuple(moments),
        max_overidentification_z=float(max_overid),
        max_negative_control_z=float(max_neg),
        assumptions=tuple(assumptions),
        causal_authority_granted=False,
        unresolved_assumption_debt=(
            "A2_EXOGENEITY_NOT_PROVEN_BY_NEGATIVE_CONTROL",
            "A3_EXCLUSION_NOT_TESTABLE_FROM_FACTUAL_CHANNEL",
            "LINEAR_HOMOGENEOUS_EFFECT_MODEL_CLASS",
            "A5_REGIME_MEASUREMENT_RELIABILITY_NOT_PROVEN",
        ),
    )


@dataclass(frozen=True, slots=True)
class CoordinatedExclusionCounterexample:
    beta_invalid: float
    beta_valid_reparameterized: float
    direct_effect_scale: float
    max_x_path_error: float
    max_y_path_error: float
    max_w_path_error: float


def coordinated_exclusion_counterexample(*, seed: int = 11, n: int = 4096) -> CoordinatedExclusionCounterexample:
    """Exact passive equivalence between invalid exclusion and a different beta.

    Invalid model:
      X = lambda'R + gamma U
      Y = beta X + delta U + kappa lambda'R + eps_y

    Because lambda'R = X-gamma U,
      Y = (beta+kappa)X + (delta-kappa*gamma)U + eps_y.

    The second expression has no direct R->Y edge but a different causal coefficient.
    Therefore all factual (R,X,Y,W) samples are pathwise identical although the causal
    interpretation differs.  No factual statistic can prove exclusion here.
    """
    rng = np.random.default_rng(seed)
    r = rng.choice(np.array([-1.0, 1.0]), size=(n, 2))
    u = rng.normal(size=n)
    eps_y = rng.normal(scale=0.7, size=n)
    eps_w = rng.normal(scale=0.4, size=n)
    lam = np.array([0.9, 0.5])
    gamma = 0.8
    beta = 0.8
    delta = 1.0
    kappa = 0.5
    x_a = r @ lam + gamma * u
    y_a = beta * x_a + delta * u + kappa * (r @ lam) + eps_y
    w_a = u + eps_w

    beta_b = beta + kappa
    delta_b = delta - kappa * gamma
    x_b = r @ lam + gamma * u
    y_b = beta_b * x_b + delta_b * u + eps_y
    w_b = u + eps_w
    return CoordinatedExclusionCounterexample(
        beta_invalid=beta,
        beta_valid_reparameterized=beta_b,
        direct_effect_scale=kappa,
        max_x_path_error=float(np.max(np.abs(x_a - x_b))),
        max_y_path_error=float(np.max(np.abs(y_a - y_b))),
        max_w_path_error=float(np.max(np.abs(w_a - w_b))),
    )
