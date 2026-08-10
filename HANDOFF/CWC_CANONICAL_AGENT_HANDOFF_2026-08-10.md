# CWC CANONICAL AGENT HANDOFF — 2026-08-10

## Authority

This file is a navigation/handoff artifact, not a scientific result. Scientific authority remains, in descending order:

1. immutable/result-bearing evidence under `artifacts/` and `research/results/`, bound by SHA-256 ledgers;
2. preregistrations and experiment code frozen in Git before authoritative runs;
3. machine-readable registries / claim ledger / hypothesis ledger;
4. verification reports and `SYSTEM.md` / `README.md` summaries;
5. this handoff document.

Never overwrite a frozen negative or reinterpret a sealed verdict to fit a later hypothesis. Create a new experiment ID and preserve the parent failure.

## Canonical repository state at handoff

Evidence HEAD before this handoff-only commit:

`dec58d26711d2ce523fbd240bd9ab927f321f509`

Latest scientific boundary:

`CSCA-07-PR = PASSIVE_REPLAY_IDENTIFIABILITY_BOUNDARY_QUALIFIED`

Authority granted:

`PASSIVE_PREDICTIVE_FALSIFICATION_ONLY`

Authority explicitly NOT granted:

- true causal abstraction from passive traces;
- semantic causality;
- broad shadow causal authority;
- replay control;
- active causal control;
- large-scale/Pareto architecture promotion;
- independent external replication.

## Programme objective

CWC is an evidence-first programme investigating whether causally controlled adaptive computation can beat static Transformer/MoE/dynamic-compute systems at equal budget. The repository is a measurement substrate, falsification harness, evidence/governance system, mathematical theory layer, and a sequence of controlled experiments. It is not a deployed autonomous intelligence system and does not have a proven large-scale Pareto advantage.

## Causal-credit / world-model line — exact state

### CSCA-01 — controlled exact causal credit

Exact counterfactual Shapley separated a controlled true cause from confounders/non-causes on synthetic SCMs. This qualified the exact operator narrowly, not a deployable estimator or world model.

### CSCA-02-UA — uncertainty/abstention

Global uncertainty/abstention did NOT qualify. Low predictive error and model agreement were shown insufficient for causal structural adequacy. Broad shadow inference stayed blocked.

### CSCA-03R — finite-budget estimator

CRN / antithetic Counterfactual Shapley qualified on controlled SCMs. Variance-only causal authority was falsified: a low-variance estimator can be precisely wrong if the counterfactual world model is structurally wrong.

### CSCA-04-SA — structural adequacy

Prospective direct-intervention structural-adequacy testing qualified synthetically. Interventional discrepancy detected controlled model misspecification that factual fit and Graph Structural Sensitivity could miss. Context-varying mechanisms were scoped as `CONTEXT_CONDITIONAL_ONLY`.

### CSCA-05-RUNTIME — direct-model shadow measurement

A narrow direct-intervention shadow path was qualified on independently trained small nanochat GPTs. The model was re-executed under an explicit span intervention and the causal sidecar did not mutate base output/state. This did NOT establish semantic causality, replay value, GPU efficiency or active control. Operator sensitivity remained significant and CPU sidecar overhead was about 4x p50 in that environment.

### CSCA-06 — intervention semantics / position-content boundary

Intervention-operator robustness improved under explicitly defined soft-intervention kernels, but a position×content attack showed resolved causal credit tracking position/locality rather than content identity. Content-specific causal credit was `NOT_SUPPORTED`; semantic causal authority and amortized student promotion remained blocked.

### CSCA-07-PR — passive replay identifiability boundary

Central theorem implemented and tested:

If two candidate latent models induce exactly the same law on every factual trace,

`P(D_fact | M=0) = P(D_fact | M=1)`, then `I(M;D_fact)=0`.

No passive statistic can identify which latent causal semantics is true without an additional identifying information channel or explicit structural assumption. Jacobian spectral stability, local replay contraction, internal context invariance and zero within-model fiber entropy were all shown insufficient by constructive counterexamples.

The passive e-process can reject a wrong *observable transition law*. Non-rejection cannot certify a latent causal graph.

Confirmatory CSCA-07 facts:

- alpha: `0.01`;
- target power: `0.95`;
- transitions per trace: `256`;
- fresh seeds per family per cohort: `128`;
- N0 true observed law rejection: PRIMARY `1/128`, REPLICATION `1/128`;
- S1 wrong dynamics rejection: `128/128` in both cohorts;
- S2 wrong sign rejection: `128/128` in both cohorts;
- W1 weak misspecification: `6/128` and `14/128` because the information converse requires at least `745.8748` transitions for the declared target power at its information rate;
- required information at alpha=.01, power=.95: `4.1768989501` nats;
- observational equivalence rate `R=0` implies necessary cost `infinity`.

## Load-bearing epistemic invariants

- observation != association != prediction != intervention != causal mechanism;
- factual prediction quality does not certify causal structure;
- estimator precision does not certify world-model validity;
- model agreement does not certify structural correctness;
- replay stability does not certify environment causality;
- compression / fiber entropy does not break an observational equivalence class by itself;
- more compute cannot create information absent from the observational channel;
- a positive result never permits authority above the frozen gate;
- `UNKNOWN` must never silently become `CAUSAL`;
- failed hypotheses are retained as evidence, not deleted.

## Verification boundary at scientific HEAD dec58d2

Recorded in `research/reports/CSCA_07_FINAL_VERIFICATION.md`:

- CSCA-07 semantic gate self-test: 4/4 authority mutations killed;
- CSCA-07 focused tests: 7 PASS;
- focused CSCA-07 + replay/uncertainty set: 11 PASS;
- full repository collection: 414 tests, zero collection errors;
- evidence checksum verification: PASS, including CSCA-07 bundles;
- `git diff --check`: PASS;
- selected 81-test research/VIA run exceeded the 300-second execution window, therefore no full behavioral-suite PASS is claimed.

## Resume rule

Do NOT spend the next iteration on larger replay, a learned variational credit student, semantic labels, or active runtime control. The weakest causal link is now the observational-identifiability assumption itself.

The next admitted programme is `CSCA-08`: choose one explicit observational identifying assumption, formalize exactly what it licenses, construct the closest observationally equivalent alternatives, and try to destroy the assumption before any causal abstraction is promoted.
