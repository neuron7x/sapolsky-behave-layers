# Adaptive-Computation Admissibility Protocol — Specification v1.0

**Status.** Normative specification. Keywords **MUST**, **MUST NOT**, **SHALL**,
**SHOULD**, **MAY** are to be interpreted as in RFC 2119. Every normative clause is
bound to a machine-checkable verifier; a conforming implementation **MUST** pass the
conformance suite `experiments/common/admissibility_spec_conformance.py`
(`make -f Makefile.cwc experiment-tests`). This document specifies *the decision
procedure* for whether to deploy adaptive computation (the "Act J gate"); it does not
specify a model architecture.

---

## 1. Scope

This protocol decides, from a finite pilot, whether a context-adaptive controller can
deliver positive net value over the best context-blind policy on a target workload, with
a controlled false-positive rate. It formalises the information-market theory
(`docs/INFORMATION_MARKET_SYNTHESIS.md`) into an executable contract.

**In scope:** the admissibility decision and its error guarantee; the invariants any
conforming value-computation implementation must satisfy.
**Out of scope (non-goals):** an architecture; a claim that any specific system attains
the certified value on real data (that is `CWC-L7-pareto: NOT_TESTED`); cloud-scale
Pareto evaluation.

## 2. Normative references

`ADAPTIVE_COMPUTATION_VALUE_THEORY.md` (Thm 1–6), `VALUE_OF_INFORMATION_RATE_FUNCTION.md`
(V*(R), β, Thm 4′–4‴), `IDENTIFIABILITY_INFERENCE.md` (the certificate),
`MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md` (coherence, complexity), `NEURON_INFORMATION_BUDGET.md`
(the physical floor). The reference implementation is `experiments/common/*.py`.

## 3. Definitions and interface

A conforming caller **MUST** provide:

| symbol | meaning | constraint |
|---|---|---|
| `Û[c,a]` | pilot estimate of utility, mechanism `a` in context `c` | finite |
| `p[c]` | context prior | `p ≥ 0`, `Σ p = 1` |
| `K[a]` | compute cost of mechanism `a` | `K ≥ 0` |
| `se` | per-cell standard error of the pilot mean | `se ≥ 0` |
| `c_route` | route-decision cost (utility units) | `c_route ≥ 0`, `≥ k_B T` per nat physically |
| `δ` | admissible false-positive rate | `δ ∈ (0,1)` |
| `B` | compute budget (optional) | `B ≥ min_a K[a]` |

Derived quantities (reference impl in parentheses): oracle gap `G` (`oracle_gap`),
information ceiling `Δu√(I/2)` (`signal_value`), rate function `V*(R)` and price
`β=dV*/dR` (`optimal_value_at_rate_ri`, `marginal_value_of_information`), lower
confidence bound `G_lo` (`gap_lower_confidence_bound`).

## 4. Invariants (a conforming value implementation MUST satisfy)

* **INV-1 (non-negativity).** `G ≥ 0` for all inputs. *(Thm 1; `oracle_gap`.)*
* **INV-2 (dominance ⇔ zero value).** `G = 0` **iff** a mechanism weakly dominates.
  *(Thm 2.)*
* **INV-3 (master envelope).** `V(Z) ≤ min{ G, Δu√(I(C;Z)/2) }`, so
  `V_net ≤ min{G, Δu√(I/2)} − c_route`. *(Thm 6.)*
* **INV-4 (rate-function sharpness).** `V*(R)` computed by the reference solver equals
  the global optimum (concavity + revelation) and never exceeds the envelope; it
  **MUST NOT** undershoot an independent lower bound. *(§4b; `falsify_rate_function`.)*
* **INV-5 (certificate validity).** For sub-Gaussian pilot noise, `P(G ≥ G_lo) ≥ 1−δ`;
  the empirical false-positive rate on a null **MUST** be `≤ δ`. *(`falsify_inference`.)*
* **INV-6 (compute-axis non-negativity).** The constrained-oracle (adaptive) value is
  `≥` the best context-blind value at matched compute, for any `|A|`.
  *(`compute_matched_advantage.advantage ≥ 0`.)*
* **INV-7 (programme coherence).** Every recorded empirical verdict equals the sign of
  its certificate. *(`audit_ladder.coherent`.)*

An implementation that fails any INV is **non-conforming** and its admissibility output
is void.

## 5. The admissibility procedure (normative)

Given a conforming interface (§3), a conforming implementation **SHALL** execute:

```
1.  Validate inputs (§3); on violation → REJECT("malformed").         [MUST fail closed]
2.  G_hat  := plugin_gap(Û, p)
3.  G_lo   := gap_lower_confidence_bound(G_hat, se, |C|, |A|, δ)
        (an implementation MAY use the tie-safeguarded adaptive bound where it is
         valid; it MUST NOT report a bound with empirical FPR > δ on a null.)
4.  IF G_lo ≤ 0:
        RETURN NOT_IDENTIFIABLE
            with n_star := sample_complexity(target_gap, σ, |C|, |A|, δ)   [collect more, or redesign for anti-dominance under budget]
5.  IF G_lo > c_route:
        RETURN ADMISSIBLE(spend)     with guarantee  P(false ADMISSIBLE) ≤ δ
    ELSE:
        RETURN INADMISSIBLE(route cost ≥ certified value)
```

A conforming implementation **MUST NOT** return `ADMISSIBLE` when `G_lo ≤ c_route`, and
**MUST NOT** claim a false-positive rate below the one its certificate actually attains.

## 6. Guarantees

* **G1 (error control).** `P(RETURN ADMISSIBLE | true G ≤ c_route) ≤ δ`. Conservative by
  construction (typically ≪ δ).
* **G2 (decidability & cost).** The identifiability test is `Θ(|C||A|)` and optimal (§3
  of `MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md`); the pilot size to certify a true gap is
  `n* = ⌈(σK/G)²⌉` (`sample_complexity`).
* **G3 (physical floor).** `c_route ≥ k_B T` per nat of information the route reads
  (`utility_per_joule_ceiling`); an implementation **SHOULD** reject a `c_route` below
  the Landauer floor as unphysical.

## 7. Conformance

A conforming implementation **SHALL** pass every check in
`experiments/common/admissibility_spec_conformance.py::check_conformance`, which
mechanically verifies INV-1…INV-7 against the reference verifiers and confirms the
admissibility procedure (§5) obeys G1–G3 on a battery of nulls and alternatives. The
suite is wired into `make -f Makefile.cwc experiment-tests`; a non-conforming build
fails the gate.

## 8. Limitations

The certificate assumes sub-Gaussian pilot noise with a correctly-estimated `se`
(misspecifying `se` voids G1). Heavy-tailed pilots require a robust mean (untested;
`NEG-double-bootstrap` records that the double bootstrap does not help near ties). The
protocol decides *whether to attempt* the cloud-scale Pareto step, not its outcome.

## 9. Versioning

This is v1.0. Breaking changes to any normative clause (§3–§7) **MUST** increment the
major version; new invariants or tightened guarantees increment the minor version. The
conformance suite version **MUST** track this document.
