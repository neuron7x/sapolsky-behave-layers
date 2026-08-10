from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

import numpy as np


SQRT_2PI = math.sqrt(2.0 * math.pi)


def _normal_logpdf(y: float, mean: float, sd: float) -> float:
    if not math.isfinite(sd) or sd <= 0:
        raise ValueError("sd must be finite and > 0")
    z = (float(y) - float(mean)) / float(sd)
    return -math.log(float(sd) * SQRT_2PI) - 0.5 * z * z


def _logsumexp(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("non-empty values required")
    m = max(values)
    return m + math.log(sum(math.exp(v - m) for v in values))


def binary_kl(p: float, q: float) -> float:
    """Binary relative entropy kl(Ber(p)||Ber(q)) in nats."""
    if not (0.0 <= p <= 1.0 and 0.0 < q < 1.0):
        raise ValueError("require p in [0,1], q in (0,1)")
    if p == 0.0:
        return -math.log1p(-q)
    if p == 1.0:
        return -math.log(q)
    return p * math.log(p / q) + (1.0 - p) * math.log((1.0 - p) / (1.0 - q))


@dataclass(frozen=True, slots=True)
class AR1Law:
    coefficient: float
    innovation_sd: float

    def __post_init__(self) -> None:
        if abs(self.coefficient) >= 1.0:
            raise ValueError("stationary AR(1) requires |coefficient| < 1")
        if self.innovation_sd <= 0 or not math.isfinite(self.innovation_sd):
            raise ValueError("innovation_sd must be finite and > 0")

    @property
    def stationary_variance(self) -> float:
        return self.innovation_sd**2 / (1.0 - self.coefficient**2)

    def transition_logpdf(self, previous: float, current: float) -> float:
        return _normal_logpdf(current, self.coefficient * previous, self.innovation_sd)


def ar1_relative_entropy_rate(true: AR1Law, candidate: AR1Law) -> float:
    """Exact KL-rate D(P_true || P_candidate) per stationary transition.

    Both processes are zero-mean stationary Gaussian AR(1).  This is observational
    distinguishability of transition laws, not causal/topological distinguishability.
    """
    var_x = true.stationary_variance
    s0 = true.innovation_sd
    s1 = candidate.innovation_sd
    delta_a = true.coefficient - candidate.coefficient
    return (
        math.log(s1 / s0)
        + (s0 * s0 + delta_a * delta_a * var_x) / (2.0 * s1 * s1)
        - 0.5
    )


@dataclass(frozen=True, slots=True)
class PassiveInformationCertificate:
    required_information_nats: float
    information_rate_nats_per_transition: float
    necessary_transitions: float
    available_transitions: int
    state: str


def passive_information_certificate(
    *,
    alpha: float,
    target_power: float,
    information_rate_nats_per_transition: float,
    available_transitions: int,
) -> PassiveInformationCertificate:
    if not (0 < alpha < target_power < 1):
        raise ValueError("require 0 < alpha < target_power < 1")
    if information_rate_nats_per_transition < 0:
        raise ValueError("information rate cannot be negative")
    if available_transitions < 1:
        raise ValueError("available_transitions must be positive")
    required = binary_kl(target_power, alpha)
    if information_rate_nats_per_transition == 0.0:
        return PassiveInformationCertificate(
            required,
            0.0,
            math.inf,
            available_transitions,
            "PASSIVELY_UNFALSIFIABLE_OBSERVATIONAL_EQUIVALENCE",
        )
    needed = required / information_rate_nats_per_transition
    state = (
        "BUDGET_NOT_RULED_OUT_BY_INFORMATION_CONVERSE"
        if needed <= available_transitions
        else "BUDGET_BELOW_NECESSARY_INFORMATION_BOUND"
    )
    return PassiveInformationCertificate(required, information_rate_nats_per_transition, needed, available_transitions, state)


class AR1MixtureEProcess:
    """Anytime-valid passive falsifier for one declared AR(1) transition law.

    The null is the candidate transition density p_M.  The numerator q_t is a
    predictable Bayesian mixture of predeclared alternative AR(1) laws.  Therefore
    q_t/p_M is a non-negative martingale increment under M, and the product is an
    e-process.  Crossing 1/alpha rejects the *observational transition law* only.
    It never identifies a latent causal graph.
    """

    def __init__(
        self,
        *,
        candidate: AR1Law,
        alternatives: Sequence[AR1Law],
        alpha: float,
    ) -> None:
        if not alternatives:
            raise ValueError("at least one alternative required")
        if not (0.0 < alpha < 1.0):
            raise ValueError("alpha must lie in (0,1)")
        self.candidate = candidate
        self.alternatives = tuple(alternatives)
        self.alpha = float(alpha)
        self._log_weights = [-math.log(len(self.alternatives))] * len(self.alternatives)
        self.log_e = 0.0
        self.transitions = 0
        self.rejected = False
        self.reject_transition: int | None = None

    def update(self, previous: float, current: float) -> float:
        log_alt = [
            w + law.transition_logpdf(previous, current)
            for w, law in zip(self._log_weights, self.alternatives)
        ]
        log_q = _logsumexp(log_alt)
        log_p = self.candidate.transition_logpdf(previous, current)
        self.log_e += log_q - log_p
        norm = _logsumexp(log_alt)
        self._log_weights = [v - norm for v in log_alt]
        self.transitions += 1
        if not self.rejected and self.log_e >= math.log(1.0 / self.alpha):
            self.rejected = True
            self.reject_transition = self.transitions
        return self.log_e

    def run(self, trace: Sequence[float]) -> dict[str, float | int | bool | None]:
        if len(trace) < 2:
            raise ValueError("trace needs at least two observations")
        for x0, x1 in zip(trace[:-1], trace[1:]):
            self.update(float(x0), float(x1))
        return {
            "rejected": self.rejected,
            "reject_transition": self.reject_transition,
            "transitions": self.transitions,
            "log_e": self.log_e,
            "e_value": math.exp(min(self.log_e, 700.0)),
        }


def simulate_ar1(law: AR1Law, *, transitions: int, seed: int) -> np.ndarray:
    if transitions < 1:
        raise ValueError("transitions must be positive")
    rng = np.random.default_rng(seed)
    x = np.empty(transitions + 1, dtype=np.float64)
    x[0] = rng.normal(0.0, math.sqrt(law.stationary_variance))
    eps = rng.normal(0.0, law.innovation_sd, size=transitions)
    for t in range(transitions):
        x[t + 1] = law.coefficient * x[t] + eps[t]
    return x


@dataclass(frozen=True, slots=True)
class SpectralTopologyCounterexample:
    eigenvalues_a: tuple[float, float]
    eigenvalues_b: tuple[float, float]
    adjacency_a: tuple[tuple[int, int], tuple[int, int]]
    adjacency_b: tuple[tuple[int, int], tuple[int, int]]
    max_observation_path_error: float
    spectral_distance: float


def spectral_topology_counterexample(*, seed: int = 7, steps: int = 256) -> SpectralTopologyCounterexample:
    """Two linearly similar latent realizations: same observations/spectrum, different edges."""
    A = np.array([[0.7, 0.4], [0.0, 0.2]], dtype=np.float64)
    T = np.array([[1.0, 0.0], [1.0, 1.0]], dtype=np.float64)
    Ti = np.linalg.inv(T)
    B = T @ A @ Ti
    C = np.array([[1.0, 0.3]], dtype=np.float64)
    D = C @ Ti
    rng = np.random.default_rng(seed)
    z = rng.normal(size=2)
    w = T @ z
    errors = []
    for _ in range(steps):
        errors.append(abs((C @ z).item() - (D @ w).item()))
        noise = rng.normal(scale=0.1, size=2)
        z = A @ z + noise
        w = B @ w + T @ noise
    ea = np.sort(np.linalg.eigvals(A).real)
    eb = np.sort(np.linalg.eigvals(B).real)
    adjacency_a = tuple(tuple(int(abs(A[i, j]) > 1e-12) for j in range(2)) for i in range(2))
    adjacency_b = tuple(tuple(int(abs(B[i, j]) > 1e-12) for j in range(2)) for i in range(2))
    return SpectralTopologyCounterexample(
        eigenvalues_a=(float(ea[0]), float(ea[1])),
        eigenvalues_b=(float(eb[0]), float(eb[1])),
        adjacency_a=adjacency_a,  # type: ignore[arg-type]
        adjacency_b=adjacency_b,  # type: ignore[arg-type]
        max_observation_path_error=max(errors),
        spectral_distance=float(np.max(np.abs(ea - eb))),
    )


@dataclass(frozen=True, slots=True)
class HiddenAutocatalyticFixedPoint:
    fixed_point: float
    local_jacobian: float
    spectral_radius: float
    context_derivative: float
    observational_information_about_hidden_state: float


def hidden_autocatalytic_fixed_point(*, kappa: float = 0.4, bias: float = 0.8) -> HiddenAutocatalyticFixedPoint:
    """A stable hidden replay attractor that is exactly absent from the observation map."""
    h = 0.1
    for _ in range(10000):
        predicate = 1.0 if h > 0.0 else 0.0
        nxt = math.tanh(kappa * h + bias * predicate)
        if abs(nxt - h) < 1e-15:
            h = nxt
            break
        h = nxt
    predicate = 1.0 if h > 0.0 else 0.0
    arg = kappa * h + bias * predicate
    jac = kappa * (1.0 - math.tanh(arg) ** 2)
    return HiddenAutocatalyticFixedPoint(
        fixed_point=h,
        local_jacobian=jac,
        spectral_radius=abs(jac),
        context_derivative=0.0,
        observational_information_about_hidden_state=0.0,
    )


@dataclass(frozen=True, slots=True)
class FiberAmbiguityCounterexample:
    per_model_fiber_entropy_bits: float
    mixture_fiber_entropy_bits: float
    mutual_information_model_trace_bits: float


def fiber_ambiguity_counterexample() -> FiberAmbiguityCounterexample:
    """Each model has H(Z|X,M)=0, while passive X contains zero bits about which model is true.

    M=0 uses Z=X; M=1 uses Z=1-X; M and X are independent fair bits.  Thus each
    candidate representation is perfectly compressed/invertible internally, but the model
    index remains completely unidentified by factual observations.
    """
    return FiberAmbiguityCounterexample(
        per_model_fiber_entropy_bits=0.0,
        mixture_fiber_entropy_bits=1.0,
        mutual_information_model_trace_bits=0.0,
    )


def replay_authority_state(*, passive_rejected: bool, causal_assumptions_identified: bool) -> str:
    if passive_rejected:
        return "REJECT_REPLAY_PREDICTIVE_LAW"
    if not causal_assumptions_identified:
        return "PASSIVE_EQUIVALENCE_UNRESOLVED_CAUSAL_AUTHORITY_BLOCKED"
    return "CAUSAL_CANDIDATE_UNDER_EXPLICIT_IDENTIFYING_ASSUMPTIONS"
