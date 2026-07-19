# The Information Budget of a Neuron — a Verified Biophysical Model

**Status.** Biophysical model, order-of-magnitude. Every number below is produced
by `experiments/common/neuron_information_budget.py`, propagated with uncertainty
over cited literature ranges, and adversarially falsification-tested by
`experiments/common/tests/test_neuron_information_budget.py` (physical laws,
consistency oracles, non-linear scaling, literature-band positive controls). This
is a *model that assembles measured constants and enforces the laws that relate
them* — not a new measurement and not an empirical CWC claim; it adds no entry to
`claim_registry.json`.

**Question (as posed).** Estimate (i) the information throughput of a single
biological neuron in bits/second, (ii) the energy cost of a bit, and (iii)
extrapolate both to networks of varying scale **without assuming linearity**.

**One-line answer.** A cortical spiking neuron carries **≈10 bits/s** (fast sensory
neurons up to ~150–300 bits/s) at **≈2×10⁻¹⁰ W**, i.e. **≈2×10⁻¹¹ J/bit ≈ 2×10⁸
ATP/bit** — about **10⁹–10¹⁰ times the Landauer floor**. Scaled to networks,
information **saturates** while energy grows **super-linearly**, so bits-per-joule
**declines with size**: information is not free, and it is progressively less free
at scale.

---

## 0. Why this belongs in CWC (the fractal link)

The CWC value theory (`docs/ADAPTIVE_COMPUTATION_VALUE_THEORY.md`) proves that
adaptive computation pays only when the *value* of a routing decision exceeds its
*cost*: `V_net ≤ min{G, Δu·√(I(C;Z)/2)} − c_route`. That theory is about bits and
abstract cost. This note supplies the **physical substrate constants** underneath
it — for the biological system CWC is modelled on (`sapolsky-behave-layers`):

* the neuron's **bits/spike** is the channel capacity `I(C;Z)` of one decision;
* **`e_bit`** (J/bit) is the physical price of the route-decision cost `c_route`;
* the Landauer floor `k_B T ln2` is the *hardest possible* lower bound on `c_route`;
* the network **efficiency decline** is *why* a controller must spend information
  selectively — the biophysical root of the route-decision-cost discount.

The same inequality — value must beat cost — recurs at the scale of one ion channel
and at the scale of a cortex. That self-similarity is the point.

---

## 1. Model of single-neuron throughput

A spiking neuron's information rate is the product of its firing rate and the
information each spike carries:

```
R = r · b        [bits/s],   r = firing rate [Hz],   b = bits/spike.
```

**Anchors (with ranges).**

| Quantity | low | mid | high | Source |
|---|---:|---:|---:|---|
| firing rate `r` [Hz] | 1 | 4 | 10 | Attwell & Laughlin 2001 (4 Hz budget); cortical 1–10 |
| bits/spike `b` | 1 | 2 | 3 | Strong et al. 1998; Rieke et al. 1997; Borst & Theunissen 1999 |
| sensory `R` [bits/s] | 10 | 64 | 300 | Strong et al. 1998 (fly H1 up to ~90, within 2× of the spike-train entropy limit) |

**Result (Monte-Carlo over the ranges):** cortical `R ≈ 10 bits/s`
(p05–p95 ≈ 2.6–23), sensory `R ≈ 150 bits/s` (p05–p95 ≈ 24–285). The two regimes
are reported separately because they differ by an order of magnitude — collapsing
them into one number would be dishonest.

---

## 2. Model of the energy cost of a bit

`e_bit = P / R`, where `P` is per-neuron power. `P` is estimated by **three
independent routes** that must agree — the model's internal falsification:

* **Top-down:** `P = P_brain / N = 20 W / 8.6×10¹⁰ ≈ 2.3×10⁻¹⁰ W`
  (brain 12–20 W; N ≈ 86×10⁹ — Herculano-Houzel 2009).
* **Bottom-up:** `P = (ATP/s)·ΔG_ATP = 3.29×10⁹ · 9.1×10⁻²⁰ ≈ 3.0×10⁻¹⁰ W`
  (per-neuron ATP turnover at 4 Hz — Attwell & Laughlin 2001; ΔG_ATP ≈ 50–62 kJ/mol
  ≈ 20 k_B T — Sterling & Laughlin 2015).
* **Per-spike:** ion pumping after each action potential (~2×10⁸–2×10⁹ ATP/AP;
  Attwell & Laughlin 2001, updated by Howarth, Gleeson & Attwell 2012).

The top-down and bottom-up estimates land within **~15% at the medians** and within
a factor of **~3.4 across the entire anchor space** (analytic worst case
`max bottom-up / min top-down`). Two independent methods agreeing to a factor of a
few is the evidence that the budget is real, not an artefact of one calculation.

**Result:** `P ≈ 2.2×10⁻¹⁰ W`, `e_bit ≈ 2.2×10⁻¹¹ J/bit ≈ 2.4×10⁸ ATP/bit`
(p05–p95 ≈ 1×10⁸–9×10⁸). This sits above Laughlin et al.'s ~10⁴ ATP/bit for
*per-synapse graded* signalling — as expected, because it prices the *whole
spiking neuron* including maintenance, not a single efficient analog synapse.

**Landauer comparison.** The floor is `k_B T ln2 = 2.97×10⁻²¹ J/bit` at 310 K.
The biological bit costs `e_bit / (k_B T ln2) ≈ 7×10⁹` floors (p05–p95 ≈
3×10⁹–3×10¹⁰) — quantitatively confirming Laughlin's "orders of magnitude above the
thermodynamic minimum". The gap is the price of reliability, speed, and
noise-immunity in a warm, wet, irreversible medium.

---

## 3. Non-linear extrapolation to networks

Linearity is explicitly rejected on **both** axes.

**Information saturates (redundancy).** With homogeneous pairwise noise correlation
`ρ`, the population information about a stimulus is
`I_N = I_1 · N / (1 + (N−1)ρ)` (linear-Fisher form; Zohary, Shadlen & Newsome 1994;
Sompolinsky et al. 2001; Averbeck, Latham & Pouget 2006). It has an **exact
ceiling** `I_∞ = I_1/ρ`: correlated noise caps the information no matter how many
neurons are added. Only at `ρ = 0` does it reduce to the naive linear `N·I_1`.

**Energy grows super-linearly (wiring).** `E_N = (1−f)·P_1·N + f·P_1·N^α`, with `f`
the communication/wiring fraction (~0.5; Attwell & Laughlin 2001) and `α ∈ (1, 4/3]`
the wiring-volume exponent (Chklovskii, Schikorski & Stevens 2002; the 4/3 bound
from three-dimensional wire packing). For `α > 1`, per-neuron power **rises** with
scale.

**Consequence — efficiency decline.** `η_N = I_N / E_N` (bits/J) has a saturating
numerator over a super-linear denominator, so it is **monotonically non-increasing**
in `N` and `→ 0`. This is a proved, tested property, not an assumption:

```
I_N/N     ↓  (saturation)        E_N/N     ↑  (super-linear)        η_N = I_N/E_N ↓
```

The physical meaning: a bigger brain buys *less* information per joule, so at scale
the only way to stay efficient is to **route** — spend the expensive bits where they
change a decision. That is the CWC master inequality (§0) rediscovered from
thermodynamics and graph geometry.

---

## 4. Verification and falsification

Everything above is checked so it *can* fail:

* **Physical floor.** `e_bit ≥ k_B T ln2` for **every** Monte-Carlo draw (0
  violations over 10⁴; `min_landauer_ratio ≈ 1.9×10⁹ ≥ 1`). The floor value equals
  `k_B T ln2` recomputed independently in the test (a dropped `ln2` is killed).
* **Three-route oracle.** Top-down vs bottom-up power agree within a factor of 4
  across the full anchor space (0 disagreements); ~15% at the medians.
* **Positive controls.** Throughput, power, ATP/bit, and Landauer-ratio medians all
  fall inside their independently-sourced literature bands (§1–2).
* **Network laws.** `I_N/N` non-increasing, `I_∞ = I_1/ρ` exact, `E_N/N`
  non-decreasing, `η_N` non-increasing, `ρ=0 ⟹` linear — each an assertion, each
  verified over thousands of random valid parameterisations.
* **Exactness (anti-mutation).** Derived quantities (`e_bit`, `ATP/bit`, Landauer
  ratio, geometric-mean power, network ceiling) are recomputed independently in the
  suite; confirmed that dropping `ln2` and dropping the super-linear wiring term
  both fail the suite.
* **Fail-closed.** Negative rates, zero throughput, `ρ ∉ [0,1)`, `α < 1`, and
  non-positive constants all raise.

Reproduce:

```bash
PYTHONPATH=. .venv/bin/python experiments/common/neuron_information_budget.py
PYTHONPATH=. .venv/bin/python -m pytest -q experiments/common/tests/test_neuron_information_budget.py
```

---

## 5. Epistemic status and limitations

* **Order of magnitude, not precision.** Ranges span ~1–2 decades; report the band,
  never a false-precision point. The value of the model is the *enforced
  consistency* between throughput, energy, the Landauer floor, and the scaling laws,
  cross-checked against independent measurements.
* **Assumptions that could move the numbers.** bits/spike depends on temporal
  resolution and stimulus statistics; firing rates vary by area and state; ATP/AP
  depends on cell geometry and channel overlap (Howarth 2012 revised A&L down by
  ~1/3); `ρ` and `α` are homogeneous-population idealisations. All are exposed as
  anchors — widen a range and the Monte-Carlo band widens honestly.
* **What is *not* claimed.** No claim that a neuron *is* a bits/s channel in any
  complete sense (dendritic computation, plasticity, and neuromodulation are outside
  a Shannon-rate model), and no claim about artificial-vs-biological efficiency
  beyond the numbers shown. This is the substrate budget, not a theory of cognition.

## References (primary anchors)

* Attwell & Laughlin (2001), *An energy budget for signaling in the grey matter of
  the brain*, J. Cereb. Blood Flow Metab. 21:1133. (per-neuron ATP turnover; 4 Hz)
* Laughlin, de Ruyter van Steveninck & Anderson (1998), *The metabolic cost of
  neural information*, Nat. Neurosci. 1:36. (ATP/bit; orders above thermodynamic min)
* Strong, Koberle, de Ruyter van Steveninck & Bialek (1998), *Entropy and
  information in neural spike trains*, PRL 80:197. (direct-method bits/s and bits/spike)
* Borst & Theunissen (1999), *Information theory and neural coding*, Nat. Neurosci.
  2:947. (review of single-neuron information rates)
* Howarth, Gleeson & Attwell (2012), *Updated energy budgets…*, J. Cereb. Blood Flow
  Metab. 32:1222. (revised AP energy)
* Herculano-Houzel (2009) / 86-billion-neuron count reviews. (N)
* Zohary, Shadlen & Newsome (1994), *Correlated neuronal discharge…*, Nature
  370:140; Averbeck, Latham & Pouget (2006), Nat. Rev. Neurosci. 7:358. (noise
  correlation → information saturation)
* Chklovskii, Schikorski & Stevens (2002), *Wiring optimization in cortical
  circuits*, Neuron 34:341. (super-linear wiring cost)
* Sterling & Laughlin (2015), *Principles of Neural Design*, MIT Press. (ΔG_ATP;
  design principles)
* Landauer (1961), *Irreversibility and heat generation…*, IBM J. Res. Dev. 5:183.
  (`k_B T ln2` floor)
