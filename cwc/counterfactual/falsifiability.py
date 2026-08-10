from __future__ import annotations

from dataclasses import dataclass
import itertools
import math
from typing import Iterable, Mapping, Sequence


def normal_logpdf(y: float, mean: float, sd: float) -> float:
    if not math.isfinite(sd) or sd <= 0:
        raise ValueError("sd must be finite and >0")
    z = (float(y) - float(mean)) / float(sd)
    return -math.log(float(sd)) - 0.5 * math.log(2.0 * math.pi) - 0.5 * z * z


def _clip(x: float, lo: float, hi: float) -> float:
    if lo > hi:
        raise ValueError("invalid interval")
    return min(max(float(x), float(lo)), float(hi))


def logsumexp(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("values required")
    m = max(values)
    if not math.isfinite(m):
        return m
    return m + math.log(sum(math.exp(v - m) for v in values))


@dataclass(frozen=True, slots=True)
class NuisanceEnvelope:
    intercept_min: float
    intercept_max: float
    sd_min: float
    sd_max: float

    def __post_init__(self) -> None:
        if self.intercept_min > self.intercept_max:
            raise ValueError("invalid intercept envelope")
        if self.sd_min <= 0 or self.sd_min > self.sd_max:
            raise ValueError("invalid sd envelope")


@dataclass(frozen=True, slots=True)
class InterventionDesign:
    counts: Mapping[float, int]
    costs: Mapping[float, float]

    def __post_init__(self) -> None:
        if not self.counts or sum(int(v) for v in self.counts.values()) <= 0:
            raise ValueError("non-empty counts required")
        for a, n in self.counts.items():
            if int(n) < 0:
                raise ValueError(f"negative count for action {a}")
            if a not in self.costs or float(self.costs[a]) <= 0:
                raise ValueError(f"positive cost missing for action {a}")

    @property
    def actions(self) -> tuple[float, ...]:
        out: list[float] = []
        for action in sorted(self.counts):
            out.extend([float(action)] * int(self.counts[action]))
        return tuple(out)

    @property
    def sample_count(self) -> int:
        return sum(int(v) for v in self.counts.values())

    @property
    def cost(self) -> float:
        return sum(float(self.costs[a]) * int(n) for a, n in self.counts.items())

    @property
    def distinct_actions(self) -> int:
        return sum(int(n) > 0 for n in self.counts.values())


@dataclass(frozen=True, slots=True)
class GaussianInterventionalLaw:
    slope: float
    intercept: float
    sd: float

    def __post_init__(self) -> None:
        if self.sd <= 0:
            raise ValueError("sd must be >0")

    def mean(self, action: float) -> float:
        return self.slope * float(action) + self.intercept


@dataclass(frozen=True, slots=True)
class ProfiledNullFit:
    intercept: float
    sd: float
    log_likelihood: float


def profile_gaussian_null(
    outcomes: Sequence[float],
    actions: Sequence[float],
    *,
    model_slope: float,
    nuisance: NuisanceEnvelope,
) -> ProfiledNullFit:
    if len(outcomes) != len(actions) or not outcomes:
        raise ValueError("outcomes/actions must have equal nonzero length")
    residuals = [float(y) - float(model_slope) * float(a) for y, a in zip(outcomes, actions)]
    intercept = _clip(sum(residuals) / len(residuals), nuisance.intercept_min, nuisance.intercept_max)
    rss = sum((r - intercept) ** 2 for r in residuals)
    mle_sd = math.sqrt(rss / len(residuals)) if rss > 0 else nuisance.sd_min
    sd = _clip(mle_sd, nuisance.sd_min, nuisance.sd_max)
    ll = sum(normal_logpdf(y, float(model_slope) * a + intercept, sd) for y, a in zip(outcomes, actions))
    return ProfiledNullFit(intercept=intercept, sd=sd, log_likelihood=ll)


def profiled_kl_to_model_class(
    true_law: GaussianInterventionalLaw,
    design: InterventionDesign,
    *,
    model_slope: float,
    nuisance: NuisanceEnvelope,
) -> tuple[float, ProfiledNullFit]:
    """Exact KL from an iid Gaussian intervention block to the closest null member.

    The null family is Y|do(X=a) ~ N(model_slope*a+h, tau^2), with one shared h,tau
    over the whole block. This is the information available to falsify the *model class*,
    not a decomposition of hidden-confounder variance versus aleatoric variance.
    """
    actions = design.actions
    target_residual_means = [
        (true_law.slope - float(model_slope)) * a + true_law.intercept for a in actions
    ]
    h = _clip(
        sum(target_residual_means) / len(target_residual_means),
        nuisance.intercept_min,
        nuisance.intercept_max,
    )
    mean_sq = sum((m - h) ** 2 for m in target_residual_means) / len(target_residual_means)
    tau_unclipped = math.sqrt(true_law.sd * true_law.sd + mean_sq)
    tau = _clip(tau_unclipped, nuisance.sd_min, nuisance.sd_max)
    kl = 0.0
    for action, target in zip(actions, target_residual_means):
        delta = target - h
        kl += (
            math.log(tau / true_law.sd)
            + (true_law.sd * true_law.sd + delta * delta) / (2.0 * tau * tau)
            - 0.5
        )
    fit = ProfiledNullFit(intercept=h, sd=tau, log_likelihood=float("nan"))
    return float(max(kl, 0.0)), fit


def separation_rate_per_cost(
    true_law: GaussianInterventionalLaw,
    design: InterventionDesign,
    *,
    model_slope: float,
    nuisance: NuisanceEnvelope,
) -> float:
    kl, _ = profiled_kl_to_model_class(true_law, design, model_slope=model_slope, nuisance=nuisance)
    return kl / design.cost


def optimize_minimax_design(
    *,
    actions: Sequence[float],
    costs: Mapping[float, float],
    alternative_laws: Sequence[GaussianInterventionalLaw],
    model_slope: float,
    nuisance: NuisanceEnvelope,
    max_samples: int,
    min_distinct_actions: int = 2,
) -> tuple[InterventionDesign, list[dict[str, float | dict[str, int]]]]:
    if max_samples < 1:
        raise ValueError("max_samples must be positive")
    actions = tuple(float(a) for a in actions)
    rows: list[dict[str, float | dict[str, int]]] = []
    best: InterventionDesign | None = None
    best_score = -1.0
    for counts in itertools.product(range(max_samples + 1), repeat=len(actions)):
        total = sum(counts)
        if total < 2 or total > max_samples:
            continue
        mapping = {a: int(n) for a, n in zip(actions, counts)}
        design = InterventionDesign(mapping, costs)
        if design.distinct_actions < min_distinct_actions:
            continue
        rates = [
            separation_rate_per_cost(
                law, design, model_slope=model_slope, nuisance=nuisance
            )
            for law in alternative_laws
        ]
        score = min(rates)
        rows.append({
            "counts": {str(a): int(mapping[a]) for a in actions},
            "cost": design.cost,
            "min_separation_rate_per_cost": float(score),
            "mean_separation_rate_per_cost": float(sum(rates) / len(rates)),
        })
        key = (score, -design.sample_count, -design.cost)
        best_key = (best_score, -(best.sample_count if best else 10**9), -(best.cost if best else float("inf")))
        if best is None or key > best_key:
            best = design
            best_score = score
    if best is None:
        raise RuntimeError("no admissible design")
    rows.sort(key=lambda r: (-float(r["min_separation_rate_per_cost"]), float(r["cost"])))
    return best, rows


@dataclass(frozen=True, slots=True)
class AlternativeComponent:
    slope: float
    intercept: float
    sd: float


class CompositeNullEProcess:
    """Anytime-valid e-process for a composite Gaussian null class.

    For each predeclared block, e = q(y|a) / sup_{theta in M} p_theta(y|a).
    Since sup_theta p_theta >= p_theta0 pointwise for every theta0 in M and q is a
    normalized density, E_theta0[e | past] <= 1. Products therefore form a test
    supermartingale under every member of the null family. Reject at E >= 1/alpha.

    The result falsifies the *declared model+nuisance class*. It does not logically prove
    that topology rather than an omitted nuisance mechanism is wrong.
    """

    def __init__(
        self,
        *,
        model_slope: float,
        nuisance: NuisanceEnvelope,
        alternative: Sequence[AlternativeComponent],
        alpha: float,
        max_cost: float,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be in (0,1)")
        if max_cost <= 0:
            raise ValueError("max_cost must be positive")
        if not alternative:
            raise ValueError("alternative mixture required")
        self.model_slope = float(model_slope)
        self.nuisance = nuisance
        self.alternative = tuple(alternative)
        self.alpha = float(alpha)
        self.max_cost = float(max_cost)
        self.log_e = 0.0
        self.cost = 0.0
        self.blocks = 0
        self.rejected = False

    @property
    def threshold_log_e(self) -> float:
        return math.log(1.0 / self.alpha)

    def _alternative_log_density(self, outcomes: Sequence[float], actions: Sequence[float]) -> float:
        terms = []
        for component in self.alternative:
            terms.append(sum(
                normal_logpdf(y, component.slope * a + component.intercept, component.sd)
                for y, a in zip(outcomes, actions)
            ))
        return logsumexp(terms) - math.log(len(terms))

    def step(self, outcomes: Sequence[float], design: InterventionDesign) -> dict[str, float | int | bool]:
        if self.rejected:
            raise RuntimeError("cannot update after rejection")
        if self.cost + design.cost > self.max_cost + 1e-12:
            raise RuntimeError("compute/intervention budget exceeded")
        actions = design.actions
        if len(outcomes) != len(actions):
            raise ValueError("outcome count does not match design")
        null_fit = profile_gaussian_null(
            outcomes, actions, model_slope=self.model_slope, nuisance=self.nuisance
        )
        log_q = self._alternative_log_density(outcomes, actions)
        increment = log_q - null_fit.log_likelihood
        self.log_e += increment
        self.cost += design.cost
        self.blocks += 1
        self.rejected = self.log_e >= self.threshold_log_e
        return {
            "block": self.blocks,
            "log_e_increment": float(increment),
            "log_e": float(self.log_e),
            "e_value_capped": float(math.exp(min(self.log_e, 700.0))),
            "cost": float(self.cost),
            "rejected": bool(self.rejected),
            "profiled_null_intercept": float(null_fit.intercept),
            "profiled_null_sd": float(null_fit.sd),
        }


def latent_aleatoric_equivalence(total_sd: float, *, points: int = 11) -> tuple[tuple[float, float], ...]:
    """Construct observationally/interventionally equivalent variance decompositions.

    In Y=beta*do(X)+gamma*U+eps, U~N(0,1), eps~N(0,sigma^2), only
    gamma^2+sigma^2 is identified from scalar Y when no proxy for U is observed.
    """
    if total_sd <= 0 or points < 2:
        raise ValueError("positive total_sd and points>=2 required")
    out = []
    for i in range(points):
        gamma = total_sd * i / (points - 1)
        sigma = math.sqrt(max(total_sd * total_sd - gamma * gamma, 0.0))
        out.append((float(gamma), float(sigma)))
    return tuple(out)


def model_class_falsifiability_state(
    *,
    separation_rate: float,
    observed_rejection: bool,
    nuisance_scope_certified: bool,
    budget_exhausted: bool,
) -> str:
    if separation_rate <= 1e-15:
        return "UNRESOLVED_INTERVENTIONAL_EQUIVALENCE"
    if observed_rejection:
        if nuisance_scope_certified:
            return "GRAPH_COMPONENT_FALSIFIED_CONDITIONAL_ON_NUISANCE_CLASS"
        return "MODEL_CLASS_FALSIFIED_NUISANCE_ATTRIBUTION_UNRESOLVED"
    if budget_exhausted:
        return "ABSTAIN_INSUFFICIENT_INTERVENTION_BUDGET"
    return "RETAIN_NOT_FALSIFIED_NO_CAUSAL_AUTHORITY"


class FixedCheckpointCompositeEValue:
    """Composite-null e-values evaluated only at preregistered checkpoints.

    For each checkpoint t, E_t = q(Y_1:t|A_1:t) / sup_theta p_theta(Y_1:t|A_1:t)
    is an e-value under every theta in the declared null class. The sequence {E_t}
    is not assumed to be a supermartingale, so optional stopping is NOT claimed.
    Instead, with K predeclared checkpoints, reject if any E_t >= K/alpha.
    Bonferroni then controls P(false rejection) <= alpha without independence.
    """

    def __init__(
        self,
        *,
        model_slope: float,
        nuisance: NuisanceEnvelope,
        alternative: Sequence[AlternativeComponent],
        alpha: float,
        checkpoints_cost: Sequence[float],
        max_cost: float,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be in (0,1)")
        cps = tuple(float(x) for x in checkpoints_cost)
        if not cps or any(x <= 0 for x in cps) or tuple(sorted(set(cps))) != cps:
            raise ValueError("checkpoints must be strictly increasing positive costs")
        if cps[-1] > max_cost + 1e-12:
            raise ValueError("checkpoint exceeds max cost")
        if not alternative:
            raise ValueError("alternative mixture required")
        self.model_slope = float(model_slope)
        self.nuisance = nuisance
        self.alternative = tuple(alternative)
        self.alpha = float(alpha)
        self.checkpoints_cost = cps
        self.max_cost = float(max_cost)
        self.outcomes: list[float] = []
        self.actions: list[float] = []
        self.cost = 0.0
        self.rejected = False
        self.checked: list[dict[str, float | bool]] = []

    @property
    def checkpoint_alpha(self) -> float:
        return self.alpha / len(self.checkpoints_cost)

    @property
    def threshold_log_e(self) -> float:
        return math.log(len(self.checkpoints_cost) / self.alpha)

    def _alternative_log_density(self) -> float:
        terms = []
        for component in self.alternative:
            terms.append(sum(
                normal_logpdf(y, component.slope * a + component.intercept, component.sd)
                for y, a in zip(self.outcomes, self.actions)
            ))
        return logsumexp(terms) - math.log(len(terms))

    def add_block(self, outcomes: Sequence[float], design: InterventionDesign) -> dict[str, float | bool | None]:
        if self.rejected:
            raise RuntimeError("cannot update after rejection")
        if self.cost + design.cost > self.max_cost + 1e-12:
            raise RuntimeError("compute/intervention budget exceeded")
        actions = design.actions
        if len(outcomes) != len(actions):
            raise ValueError("outcome count does not match design")
        self.outcomes.extend(float(y) for y in outcomes)
        self.actions.extend(actions)
        self.cost += design.cost
        is_checkpoint = any(abs(self.cost - cp) <= 1e-12 for cp in self.checkpoints_cost)
        if not is_checkpoint:
            return {"cost": self.cost, "checkpoint": False, "log_e": None, "rejected": False}
        fit = profile_gaussian_null(
            self.outcomes, self.actions, model_slope=self.model_slope, nuisance=self.nuisance
        )
        log_e = self._alternative_log_density() - fit.log_likelihood
        self.rejected = log_e >= self.threshold_log_e
        record = {
            "cost": float(self.cost),
            "checkpoint": True,
            "log_e": float(log_e),
            "rejected": bool(self.rejected),
            "profiled_null_intercept": float(fit.intercept),
            "profiled_null_sd": float(fit.sd),
        }
        self.checked.append(record)
        return record

@dataclass(frozen=True, slots=True)
class InformationBudgetCertificate:
    """Necessary information budget for a level-alpha, target-power falsifier.

    This is a converse, never a sufficiency certificate.  If a reject/retain test T
    has type-I error <= alpha for every member of the composite null and power
    >= target_power under P*, data processing through the binary decision T implies

        inf_Q KL(P* || Q) >= kl(target_power || alpha).

    For a fixed repeated intervention design with separation rate R [nat/cost],
    total cost C must therefore satisfy C*R >= kl(target_power || alpha).
    """

    alpha: float
    target_power: float
    separation_rate_per_cost: float
    required_information_nats: float
    necessary_cost_lower_bound: float
    available_cost: float
    state: str


def binary_relative_entropy(p: float, q: float) -> float:
    """KL(Bernoulli(p) || Bernoulli(q)) in nats, including boundary cases."""
    p = float(p)
    q = float(q)
    if not 0.0 <= p <= 1.0 or not 0.0 <= q <= 1.0:
        raise ValueError("Bernoulli probabilities must be in [0,1]")
    if (p > 0.0 and q == 0.0) or (p < 1.0 and q == 1.0):
        return math.inf
    out = 0.0
    if p > 0.0:
        out += p * math.log(p / q)
    if p < 1.0:
        out += (1.0 - p) * math.log((1.0 - p) / (1.0 - q))
    return float(out)


def necessary_information_for_falsification(*, alpha: float, target_power: float) -> float:
    """Necessary KL information for the requested binary test operating point.

    For target_power > alpha this is kl(target_power || alpha).  It follows from
    KL data processing under the measurable reject indicator.  It does not assert
    that attaining this amount is sufficient for a particular finite-sample test.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if not 0.0 < target_power < 1.0:
        raise ValueError("target_power must be in (0,1)")
    if target_power <= alpha:
        raise ValueError("target_power must exceed alpha for a nontrivial falsification target")
    return binary_relative_entropy(target_power, alpha)


def information_budget_certificate(
    *,
    alpha: float,
    target_power: float,
    separation_rate_per_cost: float,
    available_cost: float,
) -> InformationBudgetCertificate:
    """Return a fail-closed *necessary*, not sufficient, compute-budget certificate."""
    if separation_rate_per_cost < 0.0:
        raise ValueError("separation rate cannot be negative")
    if available_cost < 0.0:
        raise ValueError("available cost cannot be negative")
    required = necessary_information_for_falsification(alpha=alpha, target_power=target_power)
    rate = float(separation_rate_per_cost)
    necessary_cost = math.inf if rate <= 0.0 else required / rate
    if rate <= 0.0:
        state = "INTERVENTIONALLY_UNFALSIFIABLE_AT_THIS_DESIGN"
    elif available_cost + 1e-12 < necessary_cost:
        state = "BUDGET_BELOW_NECESSARY_INFORMATION_BOUND"
    else:
        state = "BUDGET_NOT_RULED_OUT_BY_INFORMATION_CONVERSE"
    return InformationBudgetCertificate(
        alpha=float(alpha),
        target_power=float(target_power),
        separation_rate_per_cost=rate,
        required_information_nats=float(required),
        necessary_cost_lower_bound=float(necessary_cost),
        available_cost=float(available_cost),
        state=state,
    )
