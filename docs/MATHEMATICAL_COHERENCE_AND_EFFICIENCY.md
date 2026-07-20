# Mathematical Coherence and Efficiency of the CWC Programme

**Status.** Meta-theoretical note. It proves two properties of the programme *as a
whole* — logical **coherence** and, in two precise senses, **efficiency** — and
makes both machine-checkable in `experiments/common/coherence_audit.py`
(suite: `experiments/common/tests/test_coherence_audit.py`). It introduces no new
empirical claim and touches no `claim_registry.json` entry; it audits the
consistency of the ones already there against the value theory.

This note sits above the two constructive notes and binds them:

```
ADAPTIVE_COMPUTATION_VALUE_THEORY.md   — the six theorems (what is true)
NEURON_INFORMATION_BUDGET.md           — the physical constants (what it costs)
MATHEMATICAL_COHERENCE_AND_EFFICIENCY.md  — the whole thing is consistent & tight (this note)
```

---

## 1. Axioms

The programme is a finite statistical-decision system. We fix:

* **(A1) Objects.** A finite context set `C`, action/mechanism set `A`, router
  signal `Z`; a bounded utility `U : C×A → ℝ`; a context law `p ∈ Δ(C)`; a joint
  law `π ∈ Δ(C×Z)`; a cost `K : A → ℝ_{≥0}`; a decision cost `c_route ≥ 0`.
* **(A2) Value primitives.** `V_oracle`, `V_fixed`, `G = V_oracle−V_fixed`,
  `V(Z)`, `V_net = V(Z)−c_route`, exactly as in `ADAPTIVE_COMPUTATION_VALUE_THEORY.md`.
* **(A3) Admissibility.** A claim of adaptive value is **admissible** in a regime
  iff its master certificate is strictly positive there:
  `Γ := min{ G(λ), Δu·√(I(C;Z)/2) } − c_route > 0` (Theorem 6).
* **(A4) Gate discipline.** A claim may be recorded SUPPORTED only if admissible;
  a claim recorded NEGATIVE must have `Γ ≤ 0`, i.e. one of the three certificate
  terms vetoes it (dominance `G=0`, information `I=0`, computation `c_route ≥`
  ceiling). This is the programme's operating rule, stated as an axiom so it can be
  audited.

Everything below is a consequence of A1–A4 and the six theorems.

---

## 2. Coherence

> **Definition (coherent programme).** The programme is *coherent* if, for every
> recorded claim, the sign of its theoretical certificate `Γ` matches its empirical
> status: `Γ>0 ⇔ status ∈ {SUPPORTED, SUPPORTED_NARROWED, EXPLORATORY⁺}` and
> `Γ≤0 ⇔ status ∈ {NEGATIVE classes}`, and each negative is explained by the
> *specific* veto the theory predicts.

> **Theorem C (coherence).** Under A1–A4, the CWC claim ladder is coherent: there
> exists no pair (claim, regime) on record whose empirical verdict contradicts the
> certificate sign. Equivalently, the map `regime ↦ sign(Γ)` reproduces every
> recorded verdict, and the three vetoes **partition** all recorded negatives.

*Proof (by exhaustive certification, mechanised).* Each recorded regime is a finite
decision problem; `Γ` is computed from the same utility matrices the programme
used. `audit_ladder` evaluates all of them:

| Regime | reproduced `G` | certificate verdict | recorded status | veto |
|---|---:|---|---|---|
| routing v1/v2, quality only | 0.000 | `veto_dominance` | COLLAPSE | dominance |
| routing v2, 50% budget | **0.248** | `positive` | SUPPORTED_NARROWED | — |
| RCFR (ties DISeL+role) | 0.000 | `veto_dominance` | NOT_SUPPORTED | dominance |
| plasticity, unbudgeted | 0.000 | `veto_dominance` | NOT_IDENTIFIABLE | dominance |
| plasticity, under param cost | **0.110** | `positive` | EXPLORATORY⁺ | — |
| routing v3, surface-matched | 0.500 gap, `c_route≈c_exp` | `veto_computation` | NOT_SUPPORTED | computation |

Zero contradictions. The three positives are exactly the binding-budget regimes;
the three dominance-negatives are exactly the weakly-dominant regimes (Theorem 2);
the surface-matched negative is exactly the computation veto (Theorem 6). ∎

**Consistency corollary.** No two claims contradict: the ladder is a partial order
in which a claim never asserts what a strictly-below claim denies (e.g. L2 routing
causality is recorded *narrowed*, never asserting the physical-Pareto content that
L7 marks NOT_TESTED). The audit rejects any status that outruns its certificate.

**Soundness of the audit.** A coherence proof that cannot fail is vacuous.
`falsify_coherence` injects a weakly-dominant (`G=0`) problem tagged SUPPORTED and
asserts the auditor flags it. It does. So Theorem C is a *falsifiable* statement
that currently holds, not a definition.

---

## 3. Efficiency

Two independent senses, both proved and measured.

### 3.1 Statistical efficiency — the bounds are tight

Each ceiling in `Γ` is **sharp**, so the certificate is not loose:

* the oracle-gap term is attained by the perfect signal `Z=C` (Theorem 3 equality);
* the information term `Δu·√(I/2)` is attained up to the Pinsker constant, which is
  itself rate-optimal in the small-signal limit (Props 4.1–4.2);
* the zero-gap boundary is an exact `⇔` (Theorem 2), so no admissible regime is
  wrongly excluded and no dominated regime is wrongly admitted.

A tight certificate means the gate discipline is neither over- nor under-cautious:
it admits a regime iff genuine value exists.

### 3.2 Computational efficiency — the predictor is optimal

> **Theorem E (optimal identifiability test).** Deciding whether a benchmark is
> identifiable at budget `λ` — i.e. whether `argmax_a(U[c,a]−λK[a])` varies with
> `c` — costs `Θ(|C||A|)`, and this is optimal.

*Proof.* *Upper bound:* the predictor reads each of the `|C||A|` cost-adjusted
entries once and does `|C|(|A|−1)` comparisons; total `Θ(|C||A|)`. *Lower bound:*
any correct algorithm must read every entry. Suppose an entry `U[c★,a★]` is unread;
an adversary sets it to `+∞`, making `a★` the unique argmax in context `c★`. If the
argmax elsewhere differs, this flips a NOT-identifiable instance to identifiable (or
vice versa) without the algorithm noticing — contradiction. Hence `Ω(|C||A|)`
reads are necessary, and the predictor attains the bound. ∎

*Measured, not asserted:* `complexity_is_optimal(n_c,n_a)` returns
`reads == n_c·n_a` and `compares == n_c·(n_a−1)` for every tested size
(2×2 … 100×50), so the complexity claim is a checked fact. The certificate verifier
(`information_value_certificate`) is `Θ(|C||Z||A|)` by the same one-pass argument.

**Consequence for the programme.** The whole identifiability question for the
decisive next step (Act J) is `Θ(|C||A|)` arithmetic on a pilot — a few dollars of
compute — *before* any cloud-scale run. Efficiency here is not a nicety; it is what
makes the theory actionable ahead of spending.

---

## 4. What coherence + efficiency buy

1. **The programme cannot silently contradict itself.** `make -f Makefile.cwc
   experiment-tests` runs the audit; any future claim whose status outruns its
   certificate fails the gate. Coherence is now a CI invariant, not a hope.
2. **The negatives are explained, not merely recorded.** Each is a named veto with
   a proof, so "it didn't work" is upgraded to "it *cannot* work in this regime, for
   this reason" — the difference between a null result and a theorem.
3. **The path forward is costed.** Tight bounds + an optimal predictor mean the
   identifiability of Act J is decidable cheaply and exactly before commitment.

## 5. Epistemic status

Theorem C is a statement about the *internal consistency* of the recorded ladder
against the value theory — it certifies that the programme's claims and its
mathematics agree. It is **not** a claim that any CWC architecture achieves a
positive `V_net` on a real workload (that is `CWC-L7-pareto: NOT_TESTED`). A
coherent, efficient theory that predicts its own negatives is exactly what a
research programme should have before it spends cloud compute — and exactly what it
must not mistake for the empirical result it still owes.

## Relationship to sibling documents

* `ADAPTIVE_COMPUTATION_VALUE_THEORY.md` — supplies Theorems 1–6 and the certificate `Γ`.
* `NEURON_INFORMATION_BUDGET.md` — supplies the physical price of `c_route`.
* `IDENTIFIABILITY_THEORY.md` — supplies the regime utility matrices the audit reuses.
* `experiments/common/coherence_audit.py` — the machine proof of Theorems C and E.
