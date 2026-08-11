from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


ELIGIBLE_CANDIDATE_STATE = "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"


@dataclass(frozen=True, slots=True)
class ReducedFormGaussian:
    """Observed linear-Gaussian reduced form for (X,Y)|R.

    X = intercept_x + lambda_x' R + eps_x
    Y = intercept_y + delta_y' R + eps_y

    The residual covariance is an observed-law object.  A structural decomposition
    into beta/direct effects/latent confounding is *not* identified by this object
    without additional restrictions.
    """

    intercept_x: float
    intercept_y: float
    lambda_x: tuple[float, ...]
    delta_y: tuple[float, ...]
    residual_var_x: float
    residual_cov_xy: float
    residual_var_y: float
    n: int
    regime_rank: int


@dataclass(frozen=True, slots=True)
class StructuralAssumptionBounds:
    """Explicit structural restrictions defining an admitted countermodel class.

    These are assumptions, not facts inferred by the search.  The search may show
    that a candidate is unique *inside* these bounds; that never upgrades the bounds
    themselves to empirical truth.
    """

    max_direct_effect_l2: float | None = None
    max_abs_latent_corr: float | None = None

    def __post_init__(self) -> None:
        if self.max_direct_effect_l2 is not None:
            if not math.isfinite(self.max_direct_effect_l2) or self.max_direct_effect_l2 < 0:
                raise ValueError("max_direct_effect_l2 must be finite and >= 0")
        if self.max_abs_latent_corr is not None:
            if not math.isfinite(self.max_abs_latent_corr) or not (0 <= self.max_abs_latent_corr <= 1):
                raise ValueError("max_abs_latent_corr must be in [0,1]")


@dataclass(frozen=True, slots=True)
class LinearGaussianCountermodel:
    beta: float
    direct_effect: tuple[float, ...]
    direct_effect_l2: float
    latent_cov_xy: float
    latent_var_x: float
    latent_var_y: float
    latent_corr_xy: float
    observational_kl_nats: float
    max_path_reconstruction_error: float
    causal_shift: float
    within_declared_bounds: bool


@dataclass(frozen=True, slots=True)
class CountermodelSearchDecision:
    state: str
    reference_beta: float
    min_causal_shift: float
    total_examined: int
    exact_equivalent_count: int
    constrained_survivor_count: int
    pareto_frontier: tuple[LinearGaussianCountermodel, ...]
    nearest_constrained_countermodel: LinearGaussianCountermodel | None
    nearest_unrestricted_countermodel: LinearGaussianCountermodel | None
    causal_authority_granted: bool
    reason: str


def fit_reduced_form(
    *,
    regimes: np.ndarray,
    treatment: Sequence[float],
    outcome: Sequence[float],
) -> ReducedFormGaussian:
    """Fit the observable reduced form using OLS with an intercept.

    This function estimates only the factual conditional law.  It deliberately does
    not label any reduced-form coefficient as causal.
    """
    R = np.asarray(regimes, dtype=np.float64)
    X = np.asarray(treatment, dtype=np.float64)
    Y = np.asarray(outcome, dtype=np.float64)
    if R.ndim != 2 or R.shape[1] < 1:
        raise ValueError("regimes must be an n x k matrix")
    if len(X) != R.shape[0] or len(Y) != R.shape[0]:
        raise ValueError("regimes, treatment and outcome must have equal sample count")
    if len(X) < max(16, 4 * (R.shape[1] + 1)):
        raise ValueError("insufficient samples for reduced-form fit")
    if not (np.all(np.isfinite(R)) and np.all(np.isfinite(X)) and np.all(np.isfinite(Y))):
        raise ValueError("all inputs must be finite")

    design = np.column_stack((np.ones(R.shape[0], dtype=np.float64), R))
    rank = int(np.linalg.matrix_rank(design))
    if rank != design.shape[1]:
        raise ValueError("regime design is rank deficient")
    coef_x = np.linalg.lstsq(design, X, rcond=None)[0]
    coef_y = np.linalg.lstsq(design, Y, rcond=None)[0]
    ex = X - design @ coef_x
    ey = Y - design @ coef_y
    var_x = float(np.mean(ex * ex))
    cov_xy = float(np.mean(ex * ey))
    var_y = float(np.mean(ey * ey))
    if var_x <= 1e-15 or var_y <= 1e-15:
        raise ValueError("degenerate reduced-form residual variance")

    return ReducedFormGaussian(
        intercept_x=float(coef_x[0]),
        intercept_y=float(coef_y[0]),
        lambda_x=tuple(float(v) for v in coef_x[1:]),
        delta_y=tuple(float(v) for v in coef_y[1:]),
        residual_var_x=var_x,
        residual_cov_xy=cov_xy,
        residual_var_y=var_y,
        n=len(X),
        regime_rank=rank,
    )


def _within_bounds(
    *,
    direct_l2: float,
    latent_corr: float,
    bounds: StructuralAssumptionBounds | None,
) -> bool:
    if bounds is None:
        return True
    if bounds.max_direct_effect_l2 is not None and direct_l2 > bounds.max_direct_effect_l2 + 1e-12:
        return False
    if bounds.max_abs_latent_corr is not None and abs(latent_corr) > bounds.max_abs_latent_corr + 1e-12:
        return False
    return True


def construct_exact_countermodel(
    *,
    reduced_form: ReducedFormGaussian,
    beta: float,
    reference_beta: float,
    regimes: np.ndarray | None = None,
    treatment: Sequence[float] | None = None,
    outcome: Sequence[float] | None = None,
    bounds: StructuralAssumptionBounds | None = None,
) -> LinearGaussianCountermodel:
    """Construct an observationally equivalent structural decomposition for any beta.

    For the fitted reduced form

      X = a_x + lambda'R + eps_x
      Y = a_y + delta'R + eps_y,

    define

      eta_beta = delta - beta*lambda,
      U_x = eps_x,
      U_y = eps_y - beta*eps_x.

    Then Y = beta*X + (a_y-beta*a_x) + eta_beta'R + U_y exactly,
    while the induced factual law of (R,X,Y) is unchanged.  Therefore beta is not
    identified by the factual reduced form when direct R->Y effects and latent
    X-Y dependence are unrestricted.
    """
    if not math.isfinite(beta) or not math.isfinite(reference_beta):
        raise ValueError("beta values must be finite")
    lam = np.asarray(reduced_form.lambda_x, dtype=np.float64)
    delta = np.asarray(reduced_form.delta_y, dtype=np.float64)
    eta = delta - beta * lam
    var_x = reduced_form.residual_var_x
    cov_xy = reduced_form.residual_cov_xy
    var_y = reduced_form.residual_var_y
    latent_cov = cov_xy - beta * var_x
    latent_var_y = var_y - 2.0 * beta * cov_xy + beta * beta * var_x
    # Algebraically this is Var(eps_y-beta eps_x) and cannot be negative in the
    # population.  Tiny negative values can appear from floating-point roundoff.
    if latent_var_y < -1e-10:
        raise ValueError("invalid residual covariance produced negative latent variance")
    latent_var_y = max(0.0, latent_var_y)
    denom = math.sqrt(max(var_x * latent_var_y, 0.0))
    if denom <= 1e-15:
        latent_corr = 0.0 if abs(latent_cov) <= 1e-12 else math.copysign(1.0, latent_cov)
    else:
        latent_corr = max(-1.0, min(1.0, latent_cov / denom))

    max_err = 0.0
    if regimes is not None or treatment is not None or outcome is not None:
        if regimes is None or treatment is None or outcome is None:
            raise ValueError("regimes, treatment and outcome must be supplied together")
        R = np.asarray(regimes, dtype=np.float64)
        X = np.asarray(treatment, dtype=np.float64)
        Y = np.asarray(outcome, dtype=np.float64)
        if R.shape != (len(X), len(lam)) or len(Y) != len(X):
            raise ValueError("raw arrays do not match fitted reduced form")
        ex = X - (reduced_form.intercept_x + R @ lam)
        ey = Y - (reduced_form.intercept_y + R @ delta)
        uy = ey - beta * ex
        y_reconstructed = (
            beta * X
            + (reduced_form.intercept_y - beta * reduced_form.intercept_x)
            + R @ eta
            + uy
        )
        x_reconstructed = reduced_form.intercept_x + R @ lam + ex
        max_err = float(max(np.max(np.abs(X - x_reconstructed)), np.max(np.abs(Y - y_reconstructed))))

    direct_l2 = float(np.linalg.norm(eta, ord=2))
    return LinearGaussianCountermodel(
        beta=float(beta),
        direct_effect=tuple(float(v) for v in eta),
        direct_effect_l2=direct_l2,
        latent_cov_xy=float(latent_cov),
        latent_var_x=float(var_x),
        latent_var_y=float(latent_var_y),
        latent_corr_xy=float(latent_corr),
        observational_kl_nats=0.0,
        max_path_reconstruction_error=max_err,
        causal_shift=abs(float(beta) - float(reference_beta)),
        within_declared_bounds=_within_bounds(direct_l2=direct_l2, latent_corr=latent_corr, bounds=bounds),
    )


def _dominates(a: LinearGaussianCountermodel, b: LinearGaussianCountermodel) -> bool:
    av = (a.direct_effect_l2, abs(a.latent_corr_xy), a.causal_shift)
    bv = (b.direct_effect_l2, abs(b.latent_corr_xy), b.causal_shift)
    return all(x <= y + 1e-12 for x, y in zip(av, bv)) and any(x < y - 1e-12 for x, y in zip(av, bv))


def pareto_frontier(models: Sequence[LinearGaussianCountermodel]) -> tuple[LinearGaussianCountermodel, ...]:
    """Return non-dominated assumption-debt alternatives.

    No universal scalar cost is fabricated: direct-effect debt, latent-confounding
    debt and causal displacement remain separate axes.  A downstream governor may
    scalarize them only if an explicit cost policy is preregistered.
    """
    out: list[LinearGaussianCountermodel] = []
    for m in models:
        if any(_dominates(other, m) for other in models if other is not m):
            continue
        out.append(m)
    return tuple(sorted(out, key=lambda m: (m.direct_effect_l2, abs(m.latent_corr_xy), -m.causal_shift, m.beta)))


def search_countermodels(
    *,
    regimes: np.ndarray,
    treatment: Sequence[float],
    outcome: Sequence[float],
    reference_beta: float,
    beta_grid: Sequence[float],
    min_causal_shift: float,
    candidate_state: str = ELIGIBLE_CANDIDATE_STATE,
    bounds: StructuralAssumptionBounds | None = None,
) -> CountermodelSearchDecision:
    """Search an exact observational-equivalence class for causal countermodels.

    The search is intentionally adversarial: any beta separated from the reference
    by `min_causal_shift` is eligible if the factual reduced-form law can be preserved.
    In the admitted linear-Gaussian class the reparameterization is exact; structural
    restrictions are tracked as assumptions rather than silently treated as data.
    """
    if candidate_state != ELIGIBLE_CANDIDATE_STATE:
        return CountermodelSearchDecision(
            state="UPSTREAM_CANDIDATE_NOT_ELIGIBLE",
            reference_beta=float(reference_beta),
            min_causal_shift=float(min_causal_shift),
            total_examined=0,
            exact_equivalent_count=0,
            constrained_survivor_count=0,
            pareto_frontier=(),
            nearest_constrained_countermodel=None,
            nearest_unrestricted_countermodel=None,
            causal_authority_granted=False,
            reason="Countermodel search cannot upgrade an upstream state that is not an assumption-conditional causal candidate.",
        )
    if not math.isfinite(min_causal_shift) or min_causal_shift <= 0:
        raise ValueError("min_causal_shift must be finite and >0")
    grid = tuple(float(v) for v in beta_grid)
    if not grid or any(not math.isfinite(v) for v in grid):
        raise ValueError("beta_grid must contain finite values")

    rf = fit_reduced_form(regimes=regimes, treatment=treatment, outcome=outcome)
    models: list[LinearGaussianCountermodel] = []
    for beta in grid:
        if abs(beta - reference_beta) + 1e-12 < min_causal_shift:
            continue
        models.append(
            construct_exact_countermodel(
                reduced_form=rf,
                beta=beta,
                reference_beta=reference_beta,
                regimes=regimes,
                treatment=treatment,
                outcome=outcome,
                bounds=bounds,
            )
        )
    if not models:
        return CountermodelSearchDecision(
            state="NO_CAUSALLY_DISTINCT_SEARCH_POINT",
            reference_beta=float(reference_beta),
            min_causal_shift=float(min_causal_shift),
            total_examined=0,
            exact_equivalent_count=0,
            constrained_survivor_count=0,
            pareto_frontier=(),
            nearest_constrained_countermodel=None,
            nearest_unrestricted_countermodel=None,
            causal_authority_granted=False,
            reason="The frozen search grid contains no beta separated enough from the reference conclusion.",
        )

    exact = [m for m in models if m.observational_kl_nats <= 1e-15 and m.max_path_reconstruction_error <= 1e-10]
    constrained = [m for m in exact if m.within_declared_bounds]
    frontier = pareto_frontier(exact)
    nearest_unrestricted = min(exact, key=lambda m: (m.causal_shift, m.direct_effect_l2, abs(m.latent_corr_xy), m.beta)) if exact else None
    nearest_constrained = min(constrained, key=lambda m: (m.causal_shift, m.direct_effect_l2, abs(m.latent_corr_xy), m.beta)) if constrained else None

    if constrained:
        state = "OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES"
        reason = "At least one causally distinct exact factual-law countermodel survives the declared structural bounds; consolidation is blocked."
    elif exact:
        state = "ASSUMPTION_CONDITIONAL_IDENTIFICATION_COUNTERMODELS_OUTSIDE_BOUNDS"
        reason = "Exact factual-law countermodels exist, but all violate the declared structural bounds. Uniqueness is conditional on those assumptions, not causal truth."
    else:
        state = "NO_EXACT_COUNTERMODEL_FOUND_IN_FROZEN_SEARCH_CLASS"
        reason = "No exact alternative was found in the frozen finite search class; this is not proof that none exists outside it."

    return CountermodelSearchDecision(
        state=state,
        reference_beta=float(reference_beta),
        min_causal_shift=float(min_causal_shift),
        total_examined=len(models),
        exact_equivalent_count=len(exact),
        constrained_survivor_count=len(constrained),
        pareto_frontier=frontier,
        nearest_constrained_countermodel=nearest_constrained,
        nearest_unrestricted_countermodel=nearest_unrestricted,
        causal_authority_granted=False,
        reason=reason,
    )
