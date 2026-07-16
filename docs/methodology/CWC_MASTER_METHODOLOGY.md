# CWC Master Methodology

**Normative constitution of the CWC research programme.** Every active experiment
must have an unambiguous place here and must not introduce its own inconsistent rules
of proof. Governs `claim_registry.json`, `HYPOTHESIS_REGISTRY.yaml`, and all
`experiments/*/PREREGISTRATION*.md`.

## 1. Research topic
Whether a **causally-controlled adaptive-computation** architecture can beat static
Transformers / MoE / dynamic-compute systems **at equal budget**.

## 2. Main goal
Move from mechanistic prototype to a **causally-validated, resource-measured,
independently-reproducible** result — or falsify the hypothesis and preserve the
negative.

## 3. Research questions
- **RQ-measure:** are the resource measurements deterministic and valid?
- **RQ-identifiable:** does a benchmark with a real adaptive-compute advantage exist?
- **RQ-routing:** can a learned controller route causally without leakage?
- **RQ-allocation:** does adaptive allocation beat best-static by the predicted amount?
- **RQ-reuse / RQ-plasticity / RQ-multiscale:** are the auxiliary mechanisms real & novel?
- **RQ-pareto:** compute-equivalent Pareto advantage on real workloads?
- **RQ-replication:** does an independent operator reproduce the primary result?

## 4. Theoretical model
Oracle gap `G = 𝔼_c[max_a(β_a+γ_{c,a})] − max_a β_a`; value of control is the
context×choice interaction `γ`, identifiable only under a **binding budget**.
Realized value discounts the route-decision cost: `V_realized = G − c_route`
(`docs/IDENTIFIABILITY_THEORY.md`).

## 5. Operational definitions
Each construct (routing, adaptive allocation, functional reuse, plasticity,
identifiability) has a machine-checkable operationalization in its experiment's
`PREREGISTRATION` and `verdict.json`. No construct is claimed without one.

## 6. Claim ladder
L0 measurement → L1 identifiability → L2 routing causality → L2′ allocation →
L3 reuse → L4 plasticity → L7 Pareto → L8 replication. **No claim may sit above its
gate.** Ladder state is `claim_registry.json` and `SYSTEM.md`.

## 7. Evidence hierarchy
preregistration < code+tests (verification) < single-seed run < multi-seed
confirmatory run with controls < independent replication. A claim's status is bounded
by the highest tier that supports it.

## 8. Exploratory vs confirmatory
Confirmatory claims require a preregistration committed **before** the run timestamp.
Exploratory findings (e.g. the plasticity λ≈1 revival) are labelled `EXPLORATORY` and
cannot be reported as confirmatory without a new preregistered run.

## 9–10. Unit of analysis / experimental unit
The **experimental unit is the model seed** (paired across compared systems), not the
token. Statistical hierarchy: init → training corpus → eval corpus → task family →
example. Tokens of one run are not independent units.

## 11. Control taxonomy
random (compute-matched), frequency-matched random, frozen controller, reinitialized
controller, constant-mean controller, route-shuffled, forced-correct, forced-wrong,
anti-route, module-swap, score-permutation, input-feature ablation.

## 12. Baseline taxonomy
dense; best-fixed policy; static prune; random depth; MoD; budget-conditioned dynamic
depth; recursive/shared-parameter; static MoE; sparse MoE; CWC. Compute-matched.

## 13. Intervention taxonomy
oracle-supervised (DIAGNOSTIC_ONLY), counterfactual value distillation (not autonomous),
end-to-end (only this licenses an autonomous-routing claim).

## 14. Benchmark-identifiability gate
Before training any controller: prove `LCB95(oracle − best_fixed) > 0` and run the
surface-leakage probe. A benchmark a surface probe can classify is `BENCHMARK_INVALID`.

## 15. Compute-parity rules
No advantage claim without identical task, dataset, training budget, hardware class,
precision, evaluation protocol, hyperparameter-search budget, and **complete controller +
dispatch cost** included.

## 16. Stopping rules
Confirmatory runs stop at the preregistered seed count / step budget — never at a
favorable seed. Pilot seeds are excluded from confirmatory inference.

## 17. Failure rules (fail-closed)
Ambiguity, insufficient power, measurement invalidity, or protocol deviation →
`INVALID`/`BLOCKED`, never a silent pass. Energy on this hardware is
`INSTRUMENT_INVALID` and is excluded.

## 18. Negative-results policy
Every negative is frozen immutably (`artifacts/history/`, SHA256SUMS) and registered.
Frozen negatives are **never recomputed** and never deleted.

## 19. Protocol amendment rules
A claim may **not** be raised after inspecting test/holdout evidence without a recorded
amendment (`PROTOCOL_AMENDMENT_AND_DEVIATION_POLICY.md`). Narrowing a claim is always
permitted and is recorded.

## 20. Publication & release boundaries
No paper/System-Card claim may exceed `claim_registry.json`. Prohibited final
statements (full validation, independent replication, scale Pareto, external approval,
deployment-readiness) are listed in `SYSTEM.md` and enforced by the doc-status gate.
