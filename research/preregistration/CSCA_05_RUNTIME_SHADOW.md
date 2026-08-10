# CSCA-05-RUNTIME — Composed Causal Authority on the Nanochat Runtime (PREREGISTRATION)

**Date frozen:** 2026-08-10
**Authority before run:** RESEARCH_ONLY
**Target:** `SHADOW_RUNTIME_PATH_QUALIFIED_NARROWED`
**Forbidden claims:** semantic real-world causality, biological causality, pretrained-LLM utility, replay benefit, active token control, GPU efficiency.

## Scientific question

Can finite-budget counterfactual credit be computed from **direct interventions on the actual nanochat model runtime** (not a learned surrogate world-model), while preserving exact-teacher causal attribution on accepted cases and provably not changing base generation?

This experiment deliberately removes the learned-world-model structural-error term for the narrow causal domain:

`THIS MODEL × THIS INPUT INTERVENTION × THIS NEXT-TOKEN DISTRIBUTION`.

It does not solve external-environment causal modelling.

## Runtime substrate

- actual `nanochat.gpt.GPT` implementation;
- actual `nanochat.engine.Engine.generate_batch` path;
- byte-level tokenizer adapter used only to avoid unavailable tokenizer dependencies;
- training data: frozen WP18 prose/code corpora already sealed in the repository;
- three independently initialized/trained small GPT checkpoints: calibration, primary, replication.

The model is deliberately small and trained from scratch. Results may qualify the runtime mechanism, not general language-model capability.

## Contexts

`PROSE` and `CODE` are explicit contexts. No global causal direction may be asserted if credit identity/direction changes across contexts.

## Candidate interventions

For a fixed-length prompt, four disjoint 4-byte spans are defined prospectively:

- `A_RECENT`: final 4 content bytes;
- `B_PREV`: bytes -12:-8;
- `C_MIDDLE`: centered 4-byte span;
- `D_EARLY`: first 4 content bytes after the context marker.

Intervention semantics: replace the selected span with byte `0x20` (ASCII space). Candidate definitions are frozen and do not depend on observed effects.

## Causal outcome

Let `y* = argmax P_base(next_token | prompt)` under the factual prompt. For any coalition assignment `S`, define

`v(S) = log P(next_token=y* | do(prompt_spans=S))`.

`y*` is determined before counterfactual evaluation. No future observed token is used. Thus the causal domain is support for the model's **current internal action preference**, not post-outcome credit.

## Exact teacher and finite estimator

- exact teacher: `exact_resampling_shapley` using direct model re-execution;
- candidate runtime estimator: `ANTITHETIC_CRN_MC`;
- budgets in calibration: 2, 4, 8, 16 antithetic pairs;
- estimator uncertainty: sampling variance of the mean already emitted by `ShapleyEstimate`.

## Prospective authority rule

For each prompt, let the provisional top candidate be the largest estimated signed credit. A shadow causal decision may be accepted only if:

1. estimator variance is estimable;
2. the 99.9% normal interval of the top credit is strictly separated from every other interval by frozen `delta`;
3. exact teacher is itself resolved by the same `delta`;
4. accepted approximate top candidate equals exact-teacher top candidate (evaluation only; exact teacher is not available to runtime authority);
5. all intervention definitions and trace hashes are present;
6. context is attached to the decision;
7. sidecar does not mutate base output or model state.

### Calibration of delta

`delta = 0.25 × Q10(exact_top_gap)` on the calibration split, clipped to `[1e-6, 0.25]`.
This deterministic formula is frozen before calibration data are observed.

### Budget selection

Choose the **smallest** budget in `[2,4,8,16]` satisfying on calibration:

- selective false causal authority = 0;
- causal top accuracy given accept = 1.0;
- coverage >= 0.20;
- median approximate-vs-exact absolute credit error <= median exact top gap / 4.

If no budget passes, CSCA-05 stops before PRIMARY.

## Confirmatory cohorts

- CALIBRATION checkpoint seed: 1301; prompt split: eval1+eval2;
- PRIMARY checkpoint seed: 2301; prompt split: eval3+eval4;
- REPLICATION checkpoint seed: 3301; prompt split: eval5.

32 prompts per context per cohort, deterministic offsets from SHA256 of `(cohort, context, index)`.

## Training contract

Each checkpoint:

- same architecture/configuration;
- same frozen train corpora;
- same number of optimizer steps;
- only initialization/minibatch seed differs;
- checkpoint and training metadata are hash-bound.

Training hyperparameters are code constants frozen with this preregistration. Training loss is diagnostic, not a qualification metric.

## Primary metrics

1. `selective_false_causal_authority` — fraction of accepted approximate decisions whose top candidate differs from exact teacher;
2. `coverage` — accepted / exact-resolved cases;
3. `top_accuracy_given_accept`;
4. `credit_L1_error` and maximum false-credit deviation vs exact teacher;
5. context scope decision;
6. shadow ON/OFF generation equality;
7. model-state hash equality before/after sidecar;
8. physical CPU wall-time p50/p95/p99 and forward-evaluation count.

## Qualification

PRIMARY and independent REPLICATION must both satisfy:

- selective false causal authority = 0;
- top accuracy given accept = 1.0;
- coverage >= 0.20;
- shadow output mismatch = 0;
- model-state mutations = 0;
- no unscoped global authority when contexts disagree;
- all traces checksum-bound;
- frozen budget/delta unchanged.

If PRIMARY fails, replication may be executed diagnostically but cannot rescue the claim.

## Interpretation boundary

PASS means only: a direct-intervention, finite-budget causal-credit sidecar can operate on this actual nanochat runtime path without changing generation and can match an exact counterfactual teacher on accepted cases for these controlled byte-level workloads.

PASS does not authorize replay, logit modification, weight updates, or active causal control.
