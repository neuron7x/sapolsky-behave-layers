# Decision-Gradient Computing (DGC) — Integration & Verification Protocol

**Programme priority:** P0 research objective for the next CWC implementation line.  
**Epistemic status:** `RESEARCH_HYPOTHESIS / ENGINEERING_CANDIDATE`.  
**Empirical status:** `NOT_TESTED`.  
**Safety posture:** fail closed; no production or high-stakes domain claim.

## 1. Intent

DGC extends CWC from deciding **whether information is worth buying** to deciding **whether the next cognition/compute operation is worth buying before its cost is paid**.

Canonical loop:

`admitted worlds -> decision boundary -> countermodel/self-falsification -> VOI -> VOC -> compute admission -> bounded scheduler -> external action -> certificate`

Central invariant:

`LLM stochasticity != governance stochasticity`.

The generator may be stochastic. Compute admission, budget enforcement, evidence binding and stop states MUST be machine-verifiable.

## 2. Verified existing state and non-duplication rule

CWC already contains:

- `cwc/epistemics/countermodel_search.py`;
- `cwc/epistemics/self_falsification.py`;
- `cwc/epistemics/information_acquisition.py`;
- proof-carrying planning;
- `VALUE_OF_INFORMATION_RATE_FUNCTION.md`;
- `ROUTABILITY_INFORMATION_BOUND.md`;
- `ADAPTIVE_COMPUTATION_VALUE_THEORY.md`;
- `ADAPTIVE_COMPUTATION_ADMISSIBILITY_SPEC.md`;
- claim/hypothesis registries, negative-result memory, V&V and engineering assurance.

The existing adaptive-computation admissibility protocol is a **pilot/programme gate**. DGC is an **online per-decision metareasoning governor**. The DGC implementation MUST reuse existing epistemic authority and MUST NOT fork it.

## 3. Formal decision object

Let `A` be legal external actions and `W_t` the admitted world/countermodel set. Existing CWC robust-planning authority remains superior to a naive posterior average: incompatible admitted worlds that imply different actions cannot be silently collapsed into authority.

For a baseline action `a0` and perturbation/countermodel `w'_i`:

\[
a_i^* = \arg\max_a U(w'_i,a),
\qquad
R_i = U(w'_i,a_i^*) - U(w'_i,a_0) \ge 0.
\]

Executable DGC sensitivity estimator:

\[
\widehat G_D = \frac{\sum_i q_i R_i}{\sum_i q_i}.
\]

This estimates **decision-relevant regret under the declared perturbation set**. It is not a differential gradient unless a perturbation metric/direction and normalization are added.

DGC MUST also retain `worst_case_regret` (and later, if preregistered, a tail-risk functional such as CVaR) because mean regret can erase low-probability catastrophic reversals.

## 4. Value of computation

For candidate cognition operation `c`:

\[
VOC(c\mid s) = E[V_{after\ c} - V_{before}] - Cost(c).
\]

Production-style admission rule is conservative:

`admit(c) iff LCB[VOC(c|s)] > risk_margin`.

The governor MUST NOT manufacture a confidence bound. Statistical validity belongs to the preregistered estimator/harness. If no valid bound is available, state is `INSUFFICIENT_EVIDENCE` or `ABSTAIN`, not `VOC>0` by assertion.

## 5. Uncertainty is not decision value

DGC explicitly falsifies the heuristic `uncertainty up -> compute up`.

- High uncertainty + invariant action => expected decision regret can be zero.
- Low uncertainty + nearby high-cost action reversal => additional compute can have high value.

The synthetic test matrix MUST contain both cases, otherwise DGC cannot be distinguished from an uncertainty router.

## 6. Architecture contract

New namespace: `cwc/governance/`.

Direction:

`cwc.governance -> cwc.epistemics` is permitted where required.  
`cwc.epistemics -> cwc.governance` is forbidden.

Governance may issue compute permission only. It MUST NOT generate task content, rewrite epistemic evidence, self-raise a hard budget, or mutate the utility definition used to evaluate its own decision.

## 7. Perturbation contract

Every perturbation MUST carry:

- id;
- target variable;
- baseline / perturbed value;
- intervention type;
- provenance;
- declared plausibility/scenario weight;
- causal dependencies;
- estimated evaluation cost.

Allowed initial classes:

`PARAMETER_SHIFT, MISSING_EVIDENCE, ASSUMPTION_REMOVAL, COUNTERMODEL, SENSOR_ERROR, DELAY, CORRELATED_FAILURE, CAUSAL_INTERVENTION, MODEL_MISSPECIFICATION`.

A text variation is not a causal countermodel. Causal interpretation requires an SCM/intervention contract or an equivalently explicit structural semantics.

## 8. Budgets and serving boundary

Independent hard budgets:

- tokens;
- money;
- wall time;
- optional GPU-seconds.

A reserved emergency budget MAY be used only by explicitly authorized escalation/abstention paths. No agent may increase its hard limit.

DGC compute admission and serving/runtime scheduling are separate. Provider rate limits, bounded concurrency, semaphores/token buckets, retry policy, KV-cache/memory scheduling and worker pools are serving constraints, not evidence that cognition has positive VOC.

## 9. Terminal states

A DGC episode MUST terminate in one of:

`DECISION_STABLE, VALUE_OF_COMPUTE_EXHAUSTED, BUDGET_EXHAUSTED, INSUFFICIENT_EVIDENCE, COUNTERMODEL_REVERSAL, HUMAN_ESCALATION_REQUIRED, ABSTAIN, SYSTEM_ERROR`.

Unbounded `while uncertain: think_more()` is prohibited.

## 10. Proof-carrying execution

Each external action MUST be bound to a machine-readable certificate containing at least:

- selected action;
- source-state digest;
- utility-model digest;
- perturbation ids/digests;
- weighted and worst-case regret;
- admitted operation / stop reason;
- predicted VOC interval and method id;
- budget before/after digest;
- evidence ids;
- governor version/digest.

Log decision metadata, not private hidden chain-of-thought.

## 11. Baselines

Minimum confirmatory arms:

- `B0_FIXED`;
- `B1_UNCERTAINTY_GATED`;
- `B2_COST_QUALITY_ROUTER`;
- `B3_DGC`.

A naive single LLM is not an adequate comparator. RouteLLM-class cost/quality routing is required as a strong baseline family.

## 12. Primary experiment

See `experiments/dgc_01/PREREGISTRATION.md`.

Primary endpoint:

`NetDecisionValue = DecisionUtility - lambda_compute * TotalComputeCost`.

Mandatory regimes: high-uncertainty/same-action; low-uncertainty/near-boundary; high-consequence; structurally distinct/action-invariant; low-probability/high-regret reversal.

The first experiment is synthetic with evaluator-only oracle state. Real-world pilot is blocked until the oracle experiment passes its preregistered gate.

## 13. Sequential stopping

Repeated perturbation evaluation changes the stopping time. Therefore DGC MUST use anytime-valid sequential inference appropriate to the actual data-generating/adaptive policy.

Initial safe route: bounded synthetic regret + frozen i.i.d. perturbation proposal + preregistered time-uniform confidence sequence. Adaptive perturbation selection requires a method valid under predictable/adaptive sampling; do not reuse an i.i.d. bound without proof.

## 14. Calibration

Any probability-like score (e.g. predicted probability that another operation reverses the decision) MUST be separately calibrated against observed outcomes. `ECE` MAY be used only with preregistered binning and sample-size rules; otherwise report reliability curves / proper scoring rules with uncertainty.

The weighted regret score itself does not become a probability by calibration rhetoric.

## 15. Cost accounting

Every run logs, where measurable:

`tokens_input, tokens_output, reasoning_tokens_if_available, GPU_seconds, wall_time, API_calls, retrieval_calls, tool_calls, estimated_USD`.

Derived metric: `CostPerCorrectDecision`. All cost conversion rates and timestamps MUST be stored with provenance.

## 16. Holistic evaluation

DGC is evaluated jointly on:

`DecisionQuality, Regret, Robustness, ComputeEfficiency, Calibration, Latency, Coverage/Abstention, Safety, OODGeneralization`.

No single accuracy number can promote the system.

## 17. Self-falsification and anti-gaming

`self_falsification.py` is used to search for the cheapest workload where `DGC < best_baseline`.

Explicit anti-gaming tests:

- selective abstention;
- coverage reduction;
- utility mutation;
- fake cost / unmetered compute;
- oracle/evaluation-label leakage;
- countermodel dropping;
- stale evidence reuse;
- NaN/Inf score injection;
- recursion/retry storms;
- decision digest tampering.

Every injected fault in the assurance suite must be detected before promotion.

## 18. Real-world pilot

First external domain: software-engineering triage only after synthetic oracle support.

Properties required: fast ground truth, low error cost, deterministic evaluation, controllable tools, measurable utility. Medicine, autonomous financial trading and physical robotics are explicitly out of the first pilot.

## 19. Promotion rules

`RESEARCH_ONLY -> EXPERIMENTALLY_SUPPORTED` only if the preregistered primary metric beats the best baseline under the frozen decision rule and no guardrail fails.

`SUPPORTED_GENERALIZING` additionally requires:

- untouched seeds;
- unseen workload family;
- unseen model;
- changed cost regime;
- changed perturbation generator.

Negative result rule: record `NOT_SUPPORTED` or `SUPPORTED_NARROWED`; never replace the primary endpoint or retune the hypothesis post hoc.

## 20. ACT execution order

### ACT-00 — Baseline freeze
Record main commit/tree, lock hash, current gates, claim registry and experiment state. No old claim changes.

### ACT-01 — Claim boundary
Maintain `docs/DGC_CLAIM_BOUNDARY.md`; DGC claim remains `NOT_TESTED` until evidence exists.

### ACT-02 — Architecture authority
Create `cwc/governance`; enforce directional imports with `engineering/architecture_contract.json`.

### ACT-03 — Perturbation contract
Provenance-bound typed perturbations; causal semantics are structural, not textual.

### ACT-04 — Local perturbation compiler
Deterministic cheap candidate generation before expensive model calls. Candidate counts are configuration, not scientific constants.

### ACT-05 — Decision-regret engine
Immutable certificate; deterministic tie-breaking; source/utility/perturbation digest binding.

### ACT-06 — Sequential perturbation
Anytime-valid stopping with assumptions frozen in preregistration.

### ACT-07 — Compute governor
Content-agnostic permission authority: STOP/PROBE/COUNTERMODEL/RETRIEVE/CRITIC/EXTERNAL_MODEL/TOOL/HUMAN/ABSTAIN.

### ACT-08 — Hard budgets
Separate token/money/time/GPU ledgers; no self-escalation.

### ACT-09 — Bounded concurrency
Serving implementation with explicit external-provider constraints; no limit bypass.

### ACT-10 — Strong baselines
B0/B1/B2/B3 with matched budget and observable information.

### ACT-11 — Preregistered primary experiment
Freeze endpoint, lambda/cost model, workloads, seeds, stop rule and analysis before run.

### ACT-12 — Oracle experiment
Compare `EstimatedVOC` with `OracleVOC`; diagnose false-stop, false-escalation and governor regret.

### ACT-13 — Calibration
Only probability-like outputs receive probability calibration.

### ACT-14 — Cost accounting
Meter every resource that can substitute for hidden compute.

### ACT-15 — Holistic evaluation
Joint decision-quality/robustness/efficiency/calibration/latency/coverage/safety/OOD report.

### ACT-16 — Self-falsification
Search specifically for counterexamples to DGC advantage.

### ACT-17 — Anti-gaming
Coverage, oracle leak, utility mutation, unmetered compute and evaluator exploitation tests.

### ACT-18 — Monitorability
Budgeted metadata monitor; no requirement to persist hidden reasoning traces.

### ACT-19 — Fault injection
Extend assurance with DGC-specific budget, cost, countermodel, recursion, digest and stale-evidence faults.

### ACT-20 — Stop conditions
Every episode reaches a typed terminal state under a hard bound.

### ACT-21 — DGC certificate
External actions are auditable transactions, not unaudited model outputs.

### ACT-22 — Real-world pilot gate
Blocked until ACT-12 passes.

### ACT-23 — Software triage pilot
Choose diagnostics based on marginal decision value; measure downstream patch/action quality and cost.

### ACT-24 — First promotion
Only preregistered primary superiority/non-inferiority rule can promote.

### ACT-25 — Generalization promotion
Require unseen workloads/models/costs/generator.

### ACT-26 — Negative-result rule
Preserve failed hypotheses and exact surviving scope.

### ACT-27 — Novelty review
No "first adaptive compute" claim. The narrow candidate contribution is specified in the related-work review and remains unproven until systematic search.

## 21. Initial executable slice in this change

Implemented now:

- immutable typed perturbation contract;
- deterministic weighted decision-regret estimator and digest binding;
- explicit VOC interval object that refuses to invent statistical validity;
- hard multi-resource budget ledger;
- fail-closed conservative compute governor;
- architecture boundary;
- targeted unit tests;
- preregistration and claim/novelty boundaries.

Not implemented in this slice:

- structural perturbation compiler;
- anytime-valid confidence-sequence engine;
- bounded-concurrency provider scheduler;
- full DGC execution certificate schema;
- DGC fault-injection mutations;
- synthetic oracle workload runner;
- real-world pilot.

These remain blocking ACTs, not implied capabilities.

## 22. Programme success criterion

The target is not token count, agent count, reasoning-trace length or countermodel count. The research quantity is decision value per total cognitive cost, subject to explicit tail-risk, coverage and safety constraints.

Final falsifiable question:

> Can the system reliably identify which next computation is worth its cost before paying that cost?

Until the preregistered experiments answer that question, DGC remains an engineering hypothesis.
