# DGC Financial Verification Contract v1

Status: **normative verification target; not a commercial performance claim**.

## 1. Economic hypothesis

DGC is valuable only if decision-aware compute admission reduces **total metered inference cost** without degrading decision quality relative to an admissible baseline.

The predeclared promotion target is:

\[
\mathrm{NetInferenceSavings} \ge 0.30
\]

subject to

\[
\Delta Q = Q_{DGC} - Q_{baseline} \ge 0.
\]

`30%` is a verification threshold, not an established property of DGC.

## 2. Cost boundary

For policy `p`, total inference cost per decision is

\[
C_p = C_{model}+C_{tokens}+C_{tools}+C_{retrieval}+C_{provider}+C_{governor}+C_{monitor}+C_{retry}+C_{latency\ penalty}.
\]

A cost component may be zero only when the execution trace establishes that no such resource was consumed. Moving work into an unmetered subsystem is an anti-gaming failure.

Synthetic development experiments use a declared scalar `diagnostic_cost` plus an explicit governance-overhead term. They do **not** establish production USD savings.

## 3. Primary economic estimand

For paired tasks and a reference baseline with positive mean cost:

\[
S_{net}=1-\frac{E[C_{DGC}]}{E[C_{ref}]}
       =\frac{E[C_{ref}-C_{DGC}]}{E[C_{ref}]}.
\]

The verification gate uses a conservative lower bound

\[
LCB(S_{net}) = \frac{LCB(E[C_{ref}-C_{DGC}])}{UCB(E[C_{ref}])}
\]

when the numerator lower bound and denominator upper bound are positive. Confidence budgets are split across numerator and denominator so the ratio bound inherits simultaneous coverage by union bound.

## 4. Quality gate

Higher `Q` is better. In loss-based tasks:

\[
Q=-E[L].
\]

Hence

\[
\Delta Q = E[L_{ref} - L_{DGC}].
\]

The strict target requires `LCB(DeltaQ) >= 0`. If the reference and DGC decisions are provably identical in quality on the declared task support, the equality may be established exactly rather than statistically.

Accuracy alone is insufficient when low-probability errors have heterogeneous consequence; expected/catastrophic regret remains a protected metric.

## 5. Reference baseline selection

The 30% claim may only be evaluated against a baseline that is **quality-admissible** for the same workload and coverage contract. A cheaper baseline that achieves lower decision quality cannot be used to make the savings claim harder or easier without reporting the quality trade-off explicitly.

The benchmark suite must still include strong routing/adaptive-compute baselines. Current DGC-01 development baselines are:

- B0 fixed compute;
- B1 uncertainty-gated compute;
- B2 cost/accuracy router;
- B3 DGC.

DGC-02 adds the financial gate and overhead sensitivity; it does not retroactively convert development data into confirmatory evidence.

## 6. Overhead and break-even

Let `h` be mean additional DGC governance cost per decision. The 30% threshold can hold only if

\[
h \le 0.70 E[C_{ref}] - E[C_{DGC,core}].
\]

This quantity is the **maximum admissible mean governance overhead** for the 30% target under the declared workload. It must be reported, not hidden.

## 7. Value-based commercial model

Only verified client savings can be monetized:

\[
VerifiedClientSavings = V\,(C_{baseline}-C_{DGC})
\]

for decision volume `V`, after quality and coverage gates.

For contractual share `alpha in [0,1]`:

\[
Revenue = alpha \cdot VerifiedClientSavings.
\]

ARR is therefore a function of measured client volume, baseline cost, DGC cost, retained quality, and contractual share. No ARR number is valid without those inputs.

## 8. Competitive differentiation gate

The absolute 30% target is **not** sufficient evidence of frontier superiority. LLMRouterBench (2026) reports performance-cost routing baselines and up to 31.7% CostSave while maintaining its Best-Single accuracy; an independent public reproduction reports 31.8% under the paper's metric. Those values are workload-specific and MUST NOT be compared numerically to DGC's synthetic workload. Their role is to establish the null hypothesis that strong routing can already produce ~30% savings in some settings.

Therefore any “DGC outperforms commercial/frontier routing” claim requires a same-workload Pareto comparison against strong router/adaptive-compute baselines. The differentiation gate is:

1. same task/query population;
2. same model/provider pool and price snapshot;
3. same quality/coverage definition;
4. all router/governor overhead included;
5. DGC lies on or improves the empirical cost-quality Pareto frontier with preregistered uncertainty analysis.

Sources: `https://arxiv.org/abs/2601.07206` and `https://github.com/lotusroot-kim/llmrouterbench-reproduction`.

## 9. Promotion states

- `R&D_TARGET`: threshold declared, not tested.
- `DEVELOPMENT_THRESHOLD_MET`: development workload clears the target; no market claim.
- `CONFIRMATORY_THRESHOLD_MET`: untouched preregistered workload clears the target with valid bounds.
- `CLIENT_VERIFIED`: live trace accounting reproduces the result on customer workload.
- `COMMERCIAL_CLAIM_ALLOWED`: only after `CLIENT_VERIFIED` and anti-gaming audit.

## 10. Kill conditions

The financial claim fails if any of the following occurs:

1. `LCB(NetInferenceSavings) < 0.30`;
2. `LCB(DeltaQ) < 0`;
3. catastrophic regret worsens beyond the frozen tolerance;
4. coverage/abstention changes are not priced;
5. governor, monitor, retry, retrieval, tool or latency costs are omitted;
6. the reference baseline is weak/strawman relative to available matched-quality alternatives;
7. model/provider prices are stale or selectively chosen;
8. the saving exists only on development-tuned workloads;
9. DGC estimator cost erases the downstream saving;
10. client traces cannot reproduce the metered result.
