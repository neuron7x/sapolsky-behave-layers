# The Information Market: a Unified Theory of Adaptive-Computation Value

**Status.** Synthesis. This note is the map of one coherent theory assembled and
verified across this work-line; every claim it summarises is proved and
falsification-tested in the modules it cites. It introduces no new result and touches
no `claim_registry.json` entry — it shows that the pieces are *one theory*.

> **Thesis.** Adaptive computation is an information market. A system should buy
> information about which mechanism a context needs **only when the decision value of
> that information exceeds its price** — and both sides of that trade are now
> computable, from the abstract decision down to the joule.

---

## 1. The single object

Every result below is a statement about one functional — the **value-of-information
rate function**

```
V*(R) = max{ V(Z) : I(C;Z) ≤ R } ,     R = bits (nats) of context signal purchased,
```

the most decision value a controller can extract from `R` nats about the context. All
the ceilings, certificates, and decisions are facets of `V*` and its slope
`β(R) = dV*/dR` (the marginal value of a nat = the market price of information).

## 2. The chain (how the pieces compose)

```
 Landauer floor  k_B T ln2  [J/bit]                         (physics; NEURON_INFORMATION_BUDGET)
      │  every nat costs ≥ k_B T joules
      ▼
 neuron budget  e_bit ≈ 2·10⁸ ATP/bit ≈ 10⁹–10¹⁰ floors     (biophysical substrate price)
      │  the physical price of a route decision c_route
      ▼
 master inequality  V_net ≤ min{ G, Δu√(I/2) } − c_route    (ADAPTIVE_COMPUTATION_VALUE_THEORY, Thm 6)
      │  the two ceilings are loose surrogates for …
      ▼
 rate function  V_net ≤ V*(I) − c_route                     (VALUE_OF_INFORMATION_RATE_FUNCTION)
      │  its shape splits by the prior margin m:
      ▼
 phase transition  regular: V*=Θ(R), Pinsker loose          (Thm 2 / small-rate dichotomy)
                   critical: V*=Θ(√R), Pinsker attained c=1  (Thm 4′; universal over |C|, Thm §4a–b)
      │  its slope β(R) = dV*/dR (concave, decreasing)
      ▼
 economic optimum  route iff β(0⁺) > κ ;  R* solves β(R*)=κ (Thm 4″; optimal_information_budget)
      │  but G is estimated from a finite pilot …
      ▼
 inference certificate  G_lo = Ĝ − bias − dev,  FPR ≤ δ     (IDENTIFIABILITY_INFERENCE)
      │  adaptive (bootstrap) debiasing recovers power
      ▼
 the decision  SPEND cloud compute iff  G_lo > c_route      (the Act J gate, with error control)
```

Read top-down it is a derivation from physics to a decision; read bottom-up it is the
justification of a decision all the way down to thermodynamics. The same trade —
*value versus cost* — recurs at every arrow. **That self-similarity is the theory.**

## 3. What each result contributes

| Result | Statement | Where |
|---|---|---|
| Routability bound | `V(Z) ≤ Δu√(I/2)` | `ROUTABILITY_INFORMATION_BOUND.md` |
| Master inequality | `V_net ≤ min{G, Δu√(I/2)} − c_route`; three vetoes | `ADAPTIVE_COMPUTATION_VALUE_THEORY.md` |
| Dominance ⇔ zero value | `G=0` iff a mechanism weakly dominates | Thm 2 |
| Data-processing ceiling | `0 ≤ V(Z) ≤ G` | Thm 3 |
| Sharp Pinsker | order-tight; TV step tight | Thm 4, Props 4.1–4.2 |
| Budgeted window | identifiable set bounded by `λ★=Δu/δ` | Thm 5 |
| Coherence + efficiency | every recorded verdict = sign of the certificate; predictor `Θ(|C||A|)` optimal | `MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md` |
| Neuron budget | `bits/s`, `J/bit`, non-linear network efficiency decline | `NEURON_INFORMATION_BUDGET.md` |
| Rate function `V*(R)` | the sharp object the ceilings bound | `VALUE_OF_INFORMATION_RATE_FUNCTION.md` |
| Phase transition | regular Θ(R)/loose vs critical Θ(√R)/tight; universal over `|C|` | §3–4a |
| Exact constant | Pinsker *attained* (`c=1`) at symmetric indifference | Thm 4′ |
| Sharp solver | rational inattention (Matějka–McKay) fixed point | `optimal_value_at_rate_ri` |
| Marginal value | `β=dV*/dR`, concavity, `value/joule ≤ β/(k_B T)` | §4c |
| Economic optimum | `β(R*)=κ`; route iff `β(0⁺)>κ` | Thm 4″ |
| Inference certificate | `G_lo`, FPR ≤ δ; sample complexity `n*` | `IDENTIFIABILITY_INFERENCE.md` |
| CWC application | the budget tunes routing-v2 to near-criticality (17× value) | §4e |

## 4. The one decision it produces

For the decisive Act J step, the theory reduces to a checklist with a validity proof:

1. **Pilot** the utility matrix `Û` and the per-cell noise; estimate `Ĝ`.
2. **Certify** `G_lo = Ĝ − bias − dev` (adaptive bootstrap where separated); false-
   positive rate `≤ δ`. If not certified, collect `n*` more samples or redesign for
   anti-dominance under budget.
3. **Price** the route decision `c_route` (cheap-probe vs oracle-probe gap) and the
   per-nat cost `κ`; the physical floor is `c_route ≥ (bits)·k_B T`.
4. **Decide**: acquire `R*` with `β(R*)=κ`, and **spend cloud compute iff
   `G_lo > c_route`**. Regular problems spend only if the sensitivity beats the cost;
   critical problems (near indifference — where the budget puts routing-v2) always have
   headroom.

## 5. Honest frontier

Proven and verified: everything in §3. **Not** claimed: any empirical CWC Pareto result
(`CWC-L7-pareto: NOT_TESTED` — this theory decides *whether to attempt* it, not its
outcome); the exact critical constant `c` off the symmetric locus; a less-conservative
inference certificate near the irregular boundary (double bootstrap / median-of-means);
heavy-tailed pilots. These are the next markets to price, not results in hand.

## 6. Provenance

Assembled over commits `b719f12 → 6574172 → 7eb367c → 1e3457e → 8f99088 → a4fb7eb →
b8987d5 → 72e0f5b → 7e9d86a → 3b933a3 → 122ad51 → 80b68da → e2839d3`, each a proved,
falsification-tested, gate-green increment. Reproduce the whole apparatus with
`make -f Makefile.cwc verify` and the `experiments/common/*` CLIs.
