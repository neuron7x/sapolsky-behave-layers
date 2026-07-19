"""Falsification suite for the neural information-budget model.

Physical laws (Landauer floor, positivity), the three-route consistency oracle,
the non-linear network scaling laws, and the literature-band positive controls are
each checked so they *can* fail. Exactness assertions recompute every derived
quantity independently, so a mutant that rescales a bound or drops a term is killed.
Anchors are cross-checked against the primary sources cited in
``docs/NEURON_INFORMATION_BUDGET.md``.
"""
import math
from itertools import pairwise

import pytest

from experiments.common.neuron_information_budget import (
    ANCHORS,
    K_B,
    LN2,
    T_BODY_K,
    atp_per_bit,
    energy_per_bit_j,
    falsify_model,
    landauer_floor_j_per_bit,
    landauer_ratio,
    monte_carlo_budget,
    network_bits_per_joule,
    network_energy_watts,
    network_information_bits,
    network_information_ceiling,
    neuron_power_bottomup,
    neuron_power_topdown,
    single_neuron_bits_per_second,
    single_neuron_budget,
)


# ------------------------------- physical floor ---------------------------- #
def test_landauer_floor_exact_value():
    assert landauer_floor_j_per_bit(T_BODY_K) == pytest.approx(K_B * T_BODY_K * LN2, rel=0, abs=1e-30)
    assert landauer_floor_j_per_bit(310.15) == pytest.approx(2.968e-21, rel=1e-3)


def test_landauer_floor_scales_with_temperature():
    assert landauer_floor_j_per_bit(620.30) == pytest.approx(2.0 * landauer_floor_j_per_bit(310.15), rel=1e-12)


def test_all_monte_carlo_draws_respect_landauer_floor():
    rep = falsify_model(seed=1, trials=8000)
    assert rep["landauer_violations"] == 0
    assert float(rep["min_landauer_ratio"]) >= 1.0
    # biological spiking is many orders of magnitude above the floor (Laughlin 1998)
    assert float(rep["min_landauer_ratio"]) > 1e6


# ---------------------- three-route consistency oracle --------------------- #
def test_independent_power_routes_agree_at_the_anchor_medians():
    p_top = neuron_power_topdown(20.0, 8.6e10)   # top-down: 20 W / 86e9
    p_bot = neuron_power_bottomup(3.29e9, 9.1e-20)  # bottom-up: Attwell&Laughlin turnover
    ratio = max(p_top, p_bot) / min(p_top, p_bot)
    assert ratio < 1.5  # ~15% at the medians -> strong cross-check
    # both land in the canonical ~2e-10 W/neuron band
    assert 1e-10 < p_top < 4e-10
    assert 1e-10 < p_bot < 4e-10


def test_routes_agree_flag_holds_over_full_anchor_space():
    rep = falsify_model(seed=7, trials=8000)
    assert rep["route_disagreements"] == 0  # factor-4 window covers the analytic worst case


# --------------------------- exactness (anti-mutation) --------------------- #
def test_derived_quantities_are_exact_recomputations():
    b = single_neuron_budget(
        firing_rate_hz=4.0, bits_per_spike=2.0, brain_power_w=20.0, n_neurons=8.6e10,
        atp_per_second=3.29e9, delta_g_atp_j=9.1e-20,
    )
    assert float(b["bits_per_second"]) == pytest.approx(8.0, abs=1e-12)  # 4 Hz * 2 bits
    p_top, p_bot = float(b["power_topdown_w"]), float(b["power_bottomup_w"])
    assert float(b["power_w"]) == pytest.approx(math.sqrt(p_top * p_bot), rel=1e-12)  # geometric mean
    assert float(b["energy_per_bit_j"]) == pytest.approx(float(b["power_w"]) / 8.0, rel=1e-12)
    assert float(b["atp_per_bit"]) == pytest.approx(float(b["energy_per_bit_j"]) / 9.1e-20, rel=1e-12)
    assert float(b["landauer_ratio"]) == pytest.approx(
        float(b["energy_per_bit_j"]) / landauer_floor_j_per_bit(), rel=1e-12
    )


def test_energy_per_bit_and_atp_helpers_are_inverse_consistent():
    e = energy_per_bit_j(2.2e-10, 8.0)
    assert e == pytest.approx(2.2e-10 / 8.0, rel=1e-12)
    assert atp_per_bit(e, 9.1e-20) == pytest.approx(e / 9.1e-20, rel=1e-12)
    assert landauer_ratio(e) == pytest.approx(e / (K_B * T_BODY_K * LN2), rel=1e-12)


# ----------------- positive controls: literature-band agreement ------------ #
def test_single_neuron_throughput_in_literature_band():
    mc = monte_carlo_budget(seed=3, trials=8000)
    # cortical spiking neuron: ~a few to a few tens of bits/s
    assert 2.0 <= mc["bits_per_second"]["median"] <= 25.0
    # fast sensory neuron (fly H1, Strong et al. 1998, up to ~90 bits/s): tens-hundreds
    assert 40.0 <= mc["sensory_bits_per_second"]["median"] <= 300.0


def test_energy_cost_in_literature_band():
    mc = monte_carlo_budget(seed=3, trials=8000)
    # ~2e-10 W/neuron (20 W / 86e9 and Attwell&Laughlin agree)
    assert 1.0e-10 <= mc["power_w"]["median"] <= 3.0e-10
    # whole-neuron spiking ~1e8-1e9 ATP/bit (above Laughlin's 1e4 per-synapse graded)
    assert 5.0e7 <= mc["atp_per_bit"]["median"] <= 2.0e9
    # orders of magnitude above the thermodynamic minimum (Laughlin 1998)
    assert mc["landauer_ratio"]["median"] > 1e8


def test_anchor_ranges_are_ordered_and_positive():
    for name, (lo, mid, hi, _cite) in ANCHORS.items():
        assert 0.0 < lo <= mid <= hi, name


# ------------------- non-linear network scaling laws ----------------------- #
def test_zero_correlation_recovers_linear_information():
    for n in (1, 5, 50, 500):
        assert network_information_bits(n, 3.0, 0.0) == pytest.approx(3.0 * n, rel=1e-12)


def test_information_saturates_under_correlated_noise():
    rho, i1 = 0.1, 5.0
    per_neuron = [network_information_bits(n, i1, rho) / n for n in (1, 10, 100, 1000, 10000)]
    assert all(a >= b - 1e-12 for a, b in pairwise(per_neuron))  # non-increasing
    # asymptote is exactly I_1 / rho
    ceiling = network_information_ceiling(i1, rho)
    assert ceiling == pytest.approx(i1 / rho, rel=1e-12)
    assert network_information_bits(10**9, i1, rho) == pytest.approx(ceiling, rel=1e-3)


def test_energy_is_superlinear_and_efficiency_declines():
    kw = {"single_bits": 20.0, "single_power_w": 2e-10, "noise_correlation": 0.1,
          "wiring_fraction": 0.5, "alpha": 1.2}
    ns = [1, 10, 100, 1000, 10000, 100000]
    pow_per_neuron = [network_energy_watts(n, 2e-10, 0.5, 1.2) / n for n in ns]
    assert all(a <= b + 1e-18 for a, b in pairwise(pow_per_neuron))  # non-decreasing
    eff = [network_bits_per_joule(n, **kw)["bits_per_joule"] for n in ns]
    assert all(a >= b - 1e-6 for a, b in pairwise(eff))  # efficiency non-increasing
    assert eff[-1] < eff[0]  # strictly worse at scale


def test_alpha_one_no_wiring_growth_is_linear_energy():
    # alpha = 1 AND all-metabolic => exactly linear energy, constant per-neuron power
    p = [network_energy_watts(n, 1e-10, 0.0, 1.0) for n in (1, 10, 100)]
    assert p == pytest.approx([1e-10, 1e-9, 1e-8], rel=1e-12)


# --------------------------- bundled harness ------------------------------- #
def test_falsification_harness_holds():
    rep = falsify_model(seed=20260720, trials=10000)
    assert rep["all_invariants_hold"] is True
    for key in ("landauer_violations", "route_disagreements", "positivity_violations",
                "saturation_violations", "superlinear_violations", "efficiency_violations"):
        assert int(rep[key]) == 0, key


def test_monte_carlo_is_deterministic():
    a = monte_carlo_budget(seed=42, trials=2000)
    b = monte_carlo_budget(seed=42, trials=2000)
    assert a["energy_per_bit_j"]["median"] == b["energy_per_bit_j"]["median"]


# --------------------------- fail-closed validation ------------------------ #
@pytest.mark.parametrize(
    "fn,args",
    [
        (landauer_floor_j_per_bit, (-1.0,)),
        (single_neuron_bits_per_second, (-1.0, 2.0)),
        (neuron_power_topdown, (0.0, 1e10)),
        (neuron_power_bottomup, (1e9, 0.0)),
        (energy_per_bit_j, (2e-10, 0.0)),          # cannot price a bit at zero throughput
        (network_information_bits, (0, 3.0, 0.1)),  # n must be >= 1
        (network_energy_watts, (10, 1e-10, 0.5, 0.9)),  # alpha < 1 forbidden
    ],
)
def test_malformed_inputs_fail_closed(fn, args):
    with pytest.raises(ValueError):
        fn(*args)


def test_noise_correlation_domain_enforced():
    with pytest.raises(ValueError):
        network_information_bits(10, 3.0, 1.0)   # rho must be < 1
    with pytest.raises(ValueError):
        network_information_bits(10, 3.0, -0.1)  # rho must be >= 0
