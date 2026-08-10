# CSCA-05-RUNTIME — Composed Causal Authority & Nanochat Runtime Shadow Pilot

**Date:** 2026-08-10  
**Verdict:** `DIRECT_INTERVENTION_SHADOW_RUNTIME_QUALIFIED_NARROWED`  
**Authority:** shadow runtime path only; active control remains forbidden.

## Why this experiment changed the causal strategy

CSCA-03R showed that estimator error can be made small while a wrong counterfactual world-model remains precisely wrong. CSCA-04 showed that direct interventions can expose controlled structural misspecification. CSCA-05 therefore removes the learned counterfactual world-model from the first runtime exposure entirely: the actual nanochat model is re-executed under an explicitly declared input intervention and acts as the intervention oracle for the narrow causal domain `THIS MODEL × THIS INTERVENTION × THIS OUTCOME`.

This does **not** solve external world-model causality. It prevents a learned surrogate from silently acquiring causal authority before it can be checked against direct interventions.

## P0 engineering defect found before the experiment

The actual `Engine.generate` path could not run a normal `GPT` instance whose vocabulary size lives on `model.config`: `getattr(self.model.config, "vocab_size", self.model.vocab_size)` eagerly evaluated the missing fallback attribute. A regression test was added and the engine now resolves the config value before any fallback lookup. This was an actual runtime-contract defect, not an experiment result.

## Pre-execution estimator correction

The first CSCA-05 draft named the CSCA-03R symmetric {-1,+1} resampling estimator. Analytic review before any authoritative calibration found this changed the estimand because CSCA-05 defines a deterministic `do(span=ASCII_SPACE)` intervention. The frozen amendment therefore introduced:

- `EXACT_ABLATION_SHAPLEY` over the 16 keep/ablate coalitions;
- `ANTITHETIC_PERMUTATION_ABLATION_SHAPLEY` with reverse-permutation pairing and coalition caching.

No result had been observed when this amendment was frozen.

## Actual model/runtime substrate

Three independent nanochat GPT checkpoints were trained from scratch using the repository's frozen WP18 prose and code corpora. Architecture: 2 layers, 4 heads, embedding width 64, byte-level vocabulary plus context/special tokens. Each checkpoint used 800 AdamW steps; only initialization/minibatch seed differed.

Training is not a qualification endpoint. It exists only to produce an actual learned model using the real `nanochat.gpt.GPT` and `nanochat.engine.Engine` paths.

Checkpoint seeds:

- calibration: 1301;
- PRIMARY: 2301;
- independent REPLICATION: 3301.

## Causal variable and outcome

Four frozen, disjoint 4-byte prompt spans were candidates: recent, previous, middle and early. `do(span)` replaces that span with ASCII space.

The outcome is pre-outcome/model-internal:

`y* = argmax P_base(next token | factual prompt)`

and coalition utility is:

`v(S) = log P(y* | do(kept spans = S))`.

No future observed target token is used. Shapley credit therefore means support or inhibition of the model's **current next-token preference** under the declared intervention operator.

## Calibration

64 calibration prompts (32 PROSE, 32 CODE) were evaluated with an exact 16-coalition teacher and antithetic budgets 1/2/4/8 pairs.

The preregistered formula produced:

- exact-gap Q10 = `0.019217907016476`;
- frozen `delta = 0.004804476754119`;
- smallest passing authority-bearing budget = **2 antithetic pairs**.

At budget 2 calibration had:

- pooled coverage `0.9375`;
- PROSE coverage `0.9375`;
- CODE coverage `0.9375`;
- false authority `0` in every stratum;
- accepted top accuracy `1.0` in every stratum.

The policy was committed before PRIMARY execution.

## PRIMARY

64 fresh prompts from different WP18 evaluation documents and an independently trained checkpoint:

- exact-resolved: 63/64;
- accepted: 61;
- coverage: `0.9682539683`;
- selective false causal authority: `0`;
- top accuracy given accept: `1.0`;
- median credit L1 error: `0.0104493`;
- base-generation output mismatches with shadow ON/OFF: `0/64`;
- model-state mutations: `0/64`.

Context-stratified qualification also passed: PROSE coverage `0.9375`, CODE coverage `1.0`, with zero false authority in both.

## Independent replication

A third independently initialized/trained checkpoint and the held-out eval5 documents produced:

- exact-resolved: 64/64;
- accepted: 63;
- coverage: `0.984375`;
- selective false causal authority: `0`;
- top accuracy given accept: `1.0`;
- median credit L1 error: `0.00415274`;
- shadow output mismatches: `0/64`;
- model-state mutations: `0/64`.

PROSE and CODE each independently passed the frozen coverage/accuracy rules.

## Physical CPU measurement

This environment has no CUDA device, so no GPU qualification is claimed.

PRIMARY paired CPU timing:

- base generation p50 `4.52 ms`;
- generation + finite-budget sidecar p50 `18.40 ms`;
- median overhead ratio `4.01×`.

REPLICATION:

- base p50 `3.53 ms`;
- instrumented p50 `14.85 ms`;
- median overhead ratio `4.19×`.

The selected estimator used a median 13 model forward calls including the factual query. The intervention sidecar is therefore **not** production-latency qualified. Shadow correctness passed; compute efficiency did not become a positive claim.

## Adversarial interpretation attack

The positive result is much narrower than "causal reasoning works".

### Recency baseline

An `ALWAYS_A_RECENT` baseline already matches the exact top candidate in:

- PRIMARY: `61/64 = 0.953125`;
- REPLICATION: `63/64 = 0.984375`.

Thus most of this byte-level task is recency-dominated. The finite estimator did correctly resolve the rare non-recent exact cases when it accepted them, but no semantic-abstraction claim follows.

### Intervention-operator sensitivity

On 32 fresh post-confirmatory diagnostic prompts, exact Shapley was recomputed under SPACE, ZERO-byte, 0xFF and within-span REVERSE perturbations:

- same top candidate across all four operators: `0.84375`;
- same sign across all four: `0.71875`.

Therefore the causal statement cannot be generalized from `do(span=SPACE)` to a latent semantic variable. Intervention semantics are now the next weak link.

## Scientific interpretation

Supported narrowly:

1. direct model re-execution can serve as a structural teacher for model-internal causal attribution, eliminating learned-surrogate structural error from the first shadow stage;
2. the frozen two-pair antithetic estimator matched exact ablation-Shapley on every accepted PRIMARY and replication case;
3. the sidecar did not alter any base-generation output or model parameter state;
4. abstention remained non-degenerate.

Not supported:

- real-world semantic causality;
- a generally adequate counterfactual world model;
- pretrained/large-model transfer;
- replay benefit;
- physical GPU efficiency;
- active control.

## Resulting architectural boundary

A new **shadow-only direct-intervention path** is qualified narrowly. The negative ACT-R&D-03 result is not rewritten: learned uncertainty surfaces remain insufficient for broad causal authority. CSCA-05 bypasses that failed component for a narrowly specified direct-intervention domain.

The next hard gate is `CSCA-06`: test invariance across admissible intervention operators and train any amortized/student counterfactual estimator only against the direct-intervention teacher, with structural abstention when student predictions diverge from direct probes.
