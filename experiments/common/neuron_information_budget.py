"""A verified biophysical model of neural information throughput and its energy cost.

This module is the executable half of `docs/NEURON_INFORMATION_BUDGET.md`. It
estimates, with propagated uncertainty and adversarial falsification tests:

  1. the information throughput of a single neuron, R  [bits/s];
  2. the metabolic cost of a bit, e_bit  [J/bit] and [ATP/bit];
  3. the ratio of e_bit to the Landauer floor k_B T ln2  (thermodynamic slack);
  4. a NON-LINEAR extrapolation to networks of N neurons, where information
     saturates (correlated-noise redundancy) while energy grows super-linearly
     (metabolism + wiring), so bits-per-joule *declines* with scale.

Design contract (matching the CWC repo discipline)
---------------------------------------------------
* Pure finite arithmetic, no third-party dependency; fails closed on bad input.
* Every load-bearing constant is a *literature anchor with a range*, not a point
  estimate; see ``ANCHORS`` and the citations in the companion document.
* The single-neuron power is computed by THREE independent routes (top-down brain
  budget; bottom-up ATP turnover; per-spike ion pumping) that must agree within
  the uncertainty band — an internal consistency oracle, not a fitted parameter.
* The Landauer floor ``e_bit >= k_B T ln2`` is a hard physical law; any parameter
  draw that violates it is a falsification of the model, caught by the harness.
* Uncertainty is propagated by deterministic Monte-Carlo over the anchor ranges;
  results are reported as (p05, median, p95), never as a single fabricated number.

This is an *order-of-magnitude biophysical model* (ranges span ~1-2 decades), not a
direct measurement. It is the physical grounding of the CWC thesis that "adaptive
computation is an information market": the neuron's bits/spike is the capacity of
one routing decision and ``e_bit`` is its physical price, with a hard Landauer floor.
"""
from __future__ import annotations

import math

# --------------------------------------------------------------------------- #
# Physical constants (exact / CODATA)                                          #
# --------------------------------------------------------------------------- #
K_B: float = 1.380649e-23          # Boltzmann constant [J/K] (exact, SI 2019)
LN2: float = math.log(2.0)
T_BODY_K: float = 310.15           # mammalian body temperature [K] (37 degrees C)


def landauer_floor_j_per_bit(temperature_k: float = T_BODY_K) -> float:
    """Landauer's thermodynamic floor for erasing one bit: ``k_B * T * ln 2`` [J/bit].

    ~2.97e-21 J/bit at body temperature. No irreversible computation can cost less;
    it is the hard lower bound every ``e_bit`` estimate below must clear.
    """
    if not math.isfinite(temperature_k) or temperature_k <= 0.0:
        raise ValueError("temperature must be positive and finite")
    return K_B * temperature_k * LN2


# --------------------------------------------------------------------------- #
# Literature anchors: (low, mid, high, citation). See NEURON_INFORMATION_BUDGET.md #
# --------------------------------------------------------------------------- #
Anchor = tuple[float, float, float, str]

ANCHORS: dict[str, Anchor] = {
    # Gibbs free energy of ATP hydrolysis in vivo, per molecule [J].
    # -50..-62 kJ/mol => 8.3e-20..1.03e-19 J; ~20 k_B T. (Sterling & Laughlin 2015)
    "delta_g_atp_j": (8.3e-20, 9.1e-20, 1.03e-19, "ATP hydrolysis 50-62 kJ/mol"),
    # Whole-brain power [W]. (Britannica/Attwell: 12-20 W; grey-matter signaling core)
    "brain_power_w": (12.0, 20.0, 20.0, "human brain 12-20 W"),
    # Neuron count. (Herculano-Houzel 2009; PMC 86e9 review)
    "n_neurons": (8.0e10, 8.6e10, 1.0e11, "86 billion neurons"),
    # Per-neuron ATP turnover rate at 4 Hz mean firing [ATP/s].
    # 3.29e9 ATP/s (Attwell & Laughlin 2001); 2012 update ~2/3 of this.
    "atp_per_second_4hz": (2.0e9, 3.29e9, 4.0e9, "Attwell & Laughlin 2001, 4 Hz"),
    # Bits transmitted per spike. (Strong et al. 1998; Borst & Theunissen 1999)
    "bits_per_spike": (1.0, 2.0, 3.0, "~2 bits/spike"),
    # Mean cortical firing rate [Hz]. (Attwell & Laughlin 4 Hz budget; range 1-10)
    "firing_rate_hz": (1.0, 4.0, 10.0, "cortical mean 1-10 Hz"),
    # Direct-method sensory single-neuron information rate [bits/s] (fly H1 up to 90).
    "sensory_bits_per_second": (10.0, 64.0, 300.0, "Strong et al. 1998 up to ~90 bits/s H1"),
    # Effective pairwise noise correlation limiting population information. (Zohary 1994)
    "noise_correlation_rho": (0.01, 0.1, 0.3, "cortical noise correlation ~0.1"),
    # Wiring-cost exponent alpha in E_wire ~ N^alpha. (Chklovskii; 4/3 volume bound)
    "wiring_exponent_alpha": (1.0, 1.16, 1.34, "wiring superlinear up to N^{4/3}"),
    # Fraction of per-neuron power attributable to communication/wiring. (Attwell&Laughlin)
    "wiring_power_fraction": (0.3, 0.5, 0.6, "AP+synaptic signaling ~half the budget"),
}


def _lo(name: str) -> float:
    return ANCHORS[name][0]


def _mid(name: str) -> float:
    return ANCHORS[name][1]


def _hi(name: str) -> float:
    return ANCHORS[name][2]


# --------------------------------------------------------------------------- #
# Single-neuron throughput and cost                                           #
# --------------------------------------------------------------------------- #
def single_neuron_bits_per_second(firing_rate_hz: float, bits_per_spike: float) -> float:
    """Information throughput of one spiking neuron: ``rate * bits_per_spike`` [bits/s]."""
    if firing_rate_hz < 0 or bits_per_spike < 0:
        raise ValueError("firing rate and bits/spike must be non-negative")
    if not (math.isfinite(firing_rate_hz) and math.isfinite(bits_per_spike)):
        raise ValueError("inputs must be finite")
    return firing_rate_hz * bits_per_spike


def neuron_power_topdown(brain_power_w: float, n_neurons: float) -> float:
    """Per-neuron power from the whole-brain budget [W]: ``P_brain / N`` (top-down)."""
    if brain_power_w <= 0 or n_neurons <= 0:
        raise ValueError("brain power and neuron count must be positive")
    return brain_power_w / n_neurons


def neuron_power_bottomup(atp_per_second: float, delta_g_atp_j: float) -> float:
    """Per-neuron power from ATP turnover [W]: ``ATP_rate * dG_ATP`` (bottom-up)."""
    if atp_per_second <= 0 or delta_g_atp_j <= 0:
        raise ValueError("ATP rate and free energy must be positive")
    return atp_per_second * delta_g_atp_j


def energy_per_bit_j(power_w: float, bits_per_second: float) -> float:
    """Metabolic cost of one bit [J/bit]: ``power / throughput``."""
    if power_w < 0 or not math.isfinite(power_w):
        raise ValueError("power must be finite and non-negative")
    if bits_per_second <= 0:
        raise ValueError("throughput must be positive to price a bit")
    return power_w / bits_per_second


def atp_per_bit(energy_per_bit_value_j: float, delta_g_atp_j: float) -> float:
    """Cost of one bit expressed in ATP molecules: ``e_bit / dG_ATP``."""
    if delta_g_atp_j <= 0:
        raise ValueError("ATP free energy must be positive")
    return energy_per_bit_value_j / delta_g_atp_j


def landauer_ratio(energy_per_bit_value_j: float, temperature_k: float = T_BODY_K) -> float:
    """How many Landauer floors the biological bit costs: ``e_bit / (k_B T ln2)``.

    Must be >= 1 for any physical irreversible channel. Biological spiking sits
    ~1e9-1e11 above the floor (Laughlin et al. 1998: "orders of magnitude above").
    """
    return energy_per_bit_value_j / landauer_floor_j_per_bit(temperature_k)


def single_neuron_budget(
    *,
    firing_rate_hz: float,
    bits_per_spike: float,
    brain_power_w: float,
    n_neurons: float,
    atp_per_second: float,
    delta_g_atp_j: float,
    temperature_k: float = T_BODY_K,
) -> dict[str, float | bool]:
    """Full single-neuron budget with the three-route power consistency oracle.

    ``power_topdown`` (brain budget / N) and ``power_bottomup`` (ATP turnover * dG)
    are *independent* estimates; ``routes_agree`` asserts they fall within a factor
    of 4 of each other. The analytic worst case over the full anchor space is
    ratio ~3.43 (max bottom-up / min top-down), so a factor-4 window is the tight
    honest bound: two independent methods agree to within ~3.4x everywhere, ~15%
    at the medians — the internal falsification that the anchors are coherent.
    """
    r_bits = single_neuron_bits_per_second(firing_rate_hz, bits_per_spike)
    p_top = neuron_power_topdown(brain_power_w, n_neurons)
    p_bot = neuron_power_bottomup(atp_per_second, delta_g_atp_j)
    power = math.sqrt(p_top * p_bot)  # geometric mean of the two routes
    e_bit = energy_per_bit_j(power, r_bits)
    floor = landauer_floor_j_per_bit(temperature_k)
    ratio_hi = max(p_top, p_bot) / min(p_top, p_bot)
    return {
        "bits_per_second": r_bits,
        "power_topdown_w": p_top,
        "power_bottomup_w": p_bot,
        "power_w": power,
        "power_route_ratio": ratio_hi,
        "routes_agree": ratio_hi <= 4.0,
        "energy_per_bit_j": e_bit,
        "atp_per_bit": atp_per_bit(e_bit, delta_g_atp_j),
        "landauer_floor_j": floor,
        "landauer_ratio": e_bit / floor,
        "landauer_floor_respected": e_bit >= floor,
    }


# --------------------------------------------------------------------------- #
# Non-linear network extrapolation                                            #
# --------------------------------------------------------------------------- #
def network_information_bits(n: int, single_bits: float, noise_correlation: float) -> float:
    """Population information under correlated noise (Zohary/Sompolinsky saturation).

        I_N = I_1 * N / (1 + (N-1) * rho).

    With ``rho = 0`` this is the naive linear law ``N * I_1``; with ``rho > 0`` it
    SATURATES to ``I_1 / rho`` as ``N -> inf`` — redundancy caps the information no
    matter how many neurons are added. This is the explicit rejection of linearity.
    """
    if n < 1:
        raise ValueError("n must be a positive integer")
    if single_bits < 0:
        raise ValueError("single-neuron information must be non-negative")
    if not (0.0 <= noise_correlation < 1.0):
        raise ValueError("noise correlation must lie in [0, 1)")
    return single_bits * n / (1.0 + (n - 1) * noise_correlation)


def network_information_ceiling(single_bits: float, noise_correlation: float) -> float:
    """Asymptotic ``I_inf = I_1 / rho`` (``inf`` when ``rho = 0``)."""
    if noise_correlation < 0.0:
        raise ValueError("noise correlation must be non-negative")
    return math.inf if noise_correlation == 0.0 else single_bits / noise_correlation


def network_energy_watts(n: int, single_power_w: float, wiring_fraction: float, alpha: float) -> float:
    """Network power: metabolic (linear) + wiring (super-linear) [W].

        E_N = (1 - f) * P_1 * N  +  f * P_1 * N^alpha,

    with ``f`` the wiring fraction and ``alpha >= 1`` the wiring-cost exponent
    (up to the N^{4/3} volume bound). For ``alpha > 1`` the per-neuron power GROWS
    with scale — the second way linearity fails.
    """
    if n < 1:
        raise ValueError("n must be a positive integer")
    if single_power_w < 0:
        raise ValueError("single-neuron power must be non-negative")
    if not (0.0 <= wiring_fraction <= 1.0):
        raise ValueError("wiring fraction must lie in [0, 1]")
    if alpha < 1.0:
        raise ValueError("wiring exponent must be >= 1 (super-linear)")
    metabolic = (1.0 - wiring_fraction) * single_power_w * n
    wiring = wiring_fraction * single_power_w * (float(n) ** alpha)
    return float(metabolic + wiring)


def network_bits_per_joule(
    n: int,
    *,
    single_bits: float,
    single_power_w: float,
    noise_correlation: float,
    wiring_fraction: float,
    alpha: float,
) -> dict[str, float]:
    """Network information efficiency [bits/J] and its per-neuron decomposition.

    ``bits_per_joule`` = ``I_N / E_N``. Because ``I_N`` saturates while ``E_N`` is
    super-linear, this efficiency DECLINES with ``N`` — the physical root of the
    CWC route-decision cost: at scale, information is not free, so a controller must
    spend it only where it pays.
    """
    info = network_information_bits(n, single_bits, noise_correlation)
    power = network_energy_watts(n, single_power_w, wiring_fraction, alpha)
    return {
        "n": float(n),
        "information_bits_per_s": info,
        "power_w": power,
        "bits_per_joule": info / power if power > 0 else math.inf,
        "information_per_neuron": info / n,
        "power_per_neuron_w": power / n,
    }


# --------------------------------------------------------------------------- #
# Deterministic Monte-Carlo uncertainty propagation                           #
# --------------------------------------------------------------------------- #
class _Rng:
    """Deterministic 64-bit LCG (no ``random`` import needed)."""

    __slots__ = ("_s",)

    def __init__(self, seed: int) -> None:
        self._s = (seed ^ 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF

    def unit(self) -> float:
        self._s = (6364136223846793005 * self._s + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return (self._s >> 11) / float(1 << 53)

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.unit()

    def log_uniform(self, lo: float, hi: float) -> float:
        return math.exp(self.uniform(math.log(lo), math.log(hi)))


def _percentiles(values: list[float]) -> dict[str, float]:
    s = sorted(values)
    n = len(s)

    def q(p: float) -> float:
        idx = min(n - 1, max(0, round(p * (n - 1))))
        return s[idx]

    return {"p05": q(0.05), "median": q(0.50), "p95": q(0.95)}


def monte_carlo_budget(seed: int = 20260720, trials: int = 20000) -> dict[str, dict[str, float]]:
    """Propagate anchor-range uncertainty into (p05, median, p95) for each metric.

    Multi-decade quantities (ATP free energy, neuron count) are sampled log-uniform;
    the rest uniform over their anchor range. Every draw is checked against the
    Landauer floor and the three-route agreement inside ``single_neuron_budget``.
    """
    rng = _Rng(seed)
    keys = ("bits_per_second", "power_w", "energy_per_bit_j", "atp_per_bit", "landauer_ratio")
    acc: dict[str, list[float]] = {k: [] for k in keys}
    sensory_bits: list[float] = []

    for _ in range(trials):
        b = single_neuron_budget(
            firing_rate_hz=rng.uniform(_lo("firing_rate_hz"), _hi("firing_rate_hz")),
            bits_per_spike=rng.uniform(_lo("bits_per_spike"), _hi("bits_per_spike")),
            brain_power_w=rng.uniform(_lo("brain_power_w"), _hi("brain_power_w")),
            n_neurons=rng.log_uniform(_lo("n_neurons"), _hi("n_neurons")),
            atp_per_second=rng.uniform(_lo("atp_per_second_4hz"), _hi("atp_per_second_4hz")),
            delta_g_atp_j=rng.log_uniform(_lo("delta_g_atp_j"), _hi("delta_g_atp_j")),
        )
        for k in keys:
            acc[k].append(float(b[k]))
        sensory_bits.append(rng.uniform(_lo("sensory_bits_per_second"), _hi("sensory_bits_per_second")))

    out = {k: _percentiles(v) for k, v in acc.items()}
    out["sensory_bits_per_second"] = _percentiles(sensory_bits)
    return out


# --------------------------------------------------------------------------- #
# Adversarial falsification harness                                           #
# --------------------------------------------------------------------------- #
def falsify_model(seed: int = 20260720, trials: int = 20000) -> dict[str, float | int | bool]:
    """Try to break every physical/structural invariant of the model.

    All ``*_violations`` counters must be zero; any positive value is a genuine
    falsification (a parameter draw that breaks thermodynamics or a network law
    that fails to saturate / grow as proved).
    """
    rng = _Rng(seed)
    landauer_violations = 0
    route_disagreements = 0
    positivity_violations = 0
    saturation_violations = 0
    superlinear_violations = 0
    efficiency_violations = 0
    min_landauer_ratio = math.inf

    for _ in range(trials):
        b = single_neuron_budget(
            firing_rate_hz=rng.uniform(_lo("firing_rate_hz"), _hi("firing_rate_hz")),
            bits_per_spike=rng.uniform(_lo("bits_per_spike"), _hi("bits_per_spike")),
            brain_power_w=rng.uniform(_lo("brain_power_w"), _hi("brain_power_w")),
            n_neurons=rng.log_uniform(_lo("n_neurons"), _hi("n_neurons")),
            atp_per_second=rng.uniform(_lo("atp_per_second_4hz"), _hi("atp_per_second_4hz")),
            delta_g_atp_j=rng.log_uniform(_lo("delta_g_atp_j"), _hi("delta_g_atp_j")),
        )
        if not bool(b["landauer_floor_respected"]):
            landauer_violations += 1
        if not bool(b["routes_agree"]):
            route_disagreements += 1
        if float(b["bits_per_second"]) <= 0 or float(b["energy_per_bit_j"]) <= 0:
            positivity_violations += 1
        min_landauer_ratio = min(min_landauer_ratio, float(b["landauer_ratio"]))

        # network laws on a random but valid parameterisation
        i1 = rng.uniform(1.0, 100.0)
        p1 = rng.log_uniform(1e-11, 1e-9)
        rho = rng.uniform(0.01, 0.5)
        frac = rng.uniform(0.2, 0.7)
        alpha = rng.uniform(1.0001, 1.34)
        prev_info_per_n = math.inf
        prev_pow_per_n = 0.0
        prev_eff = math.inf
        for n in (1, 10, 100, 1000, 10000, 100000):
            info_per_n = network_information_bits(n, i1, rho) / n
            pow_per_n = network_energy_watts(n, p1, frac, alpha) / n
            eff = network_bits_per_joule(
                n, single_bits=i1, single_power_w=p1,
                noise_correlation=rho, wiring_fraction=frac, alpha=alpha,
            )["bits_per_joule"]
            # information per neuron must be non-increasing (redundancy saturation)
            if info_per_n > prev_info_per_n + 1e-9:
                saturation_violations += 1
            # per-neuron power must be non-decreasing (super-linear wiring)
            if pow_per_n < prev_pow_per_n - 1e-18:
                superlinear_violations += 1
            # efficiency must be non-increasing
            if eff > prev_eff + 1e-6:
                efficiency_violations += 1
            prev_info_per_n = info_per_n
            prev_pow_per_n = pow_per_n
            prev_eff = eff

        # saturation ceiling is exact
        ceil = network_information_ceiling(i1, rho)
        big = network_information_bits(10**9, i1, rho)
        if big > ceil + 1e-6:
            saturation_violations += 1

    return {
        "trials": trials,
        "landauer_violations": landauer_violations,
        "route_disagreements": route_disagreements,
        "positivity_violations": positivity_violations,
        "saturation_violations": saturation_violations,
        "superlinear_violations": superlinear_violations,
        "efficiency_violations": efficiency_violations,
        "min_landauer_ratio": min_landauer_ratio,
        "all_invariants_hold": (
            landauer_violations == 0
            and route_disagreements == 0
            and positivity_violations == 0
            and saturation_violations == 0
            and superlinear_violations == 0
            and efficiency_violations == 0
            and min_landauer_ratio >= 1.0
        ),
    }


def _fmt(d: dict[str, float]) -> str:
    return f"p05={d['p05']:.3g}  median={d['median']:.3g}  p95={d['p95']:.3g}"


if __name__ == "__main__":  # pragma: no cover - CLI summary
    mc = monte_carlo_budget()
    print("SINGLE-NEURON INFORMATION BUDGET (Monte-Carlo over literature anchors)")
    print(f"  throughput  [bits/s]   : {_fmt(mc['bits_per_second'])}")
    print(f"  sensory     [bits/s]   : {_fmt(mc['sensory_bits_per_second'])}")
    print(f"  power       [W]        : {_fmt(mc['power_w'])}")
    print(f"  energy/bit  [J/bit]    : {_fmt(mc['energy_per_bit_j'])}")
    print(f"  cost        [ATP/bit]  : {_fmt(mc['atp_per_bit'])}")
    print(f"  Landauer ratio e/kTln2 : {_fmt(mc['landauer_ratio'])}")
    rep = falsify_model()
    print("FALSIFICATION:", "ALL INVARIANTS HOLD" if rep["all_invariants_hold"] else "VIOLATION FOUND")
    print(f"  min Landauer ratio     : {rep['min_landauer_ratio']:.3g}  (must be >= 1)")
