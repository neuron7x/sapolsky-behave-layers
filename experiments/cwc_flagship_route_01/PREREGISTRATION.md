# CWC-FLAGSHIP-ROUTE-01 — Real-Data Adaptive-Depth Kill/Promotion Gate

Date frozen: 2026-08-11
Status: PREREGISTERED / NO CWC-FLAGSHIP-ROUTE-01 MODEL OUTPUTS OBSERVED
Tier: REAL-DATA / SMALL-MODEL / INTERNAL-CORPUS MECHANISM GATE

## Why this experiment exists

The programme's broad flagship question is whether a causally controlled adaptive-computation
mechanism can beat static/dynamic alternatives at equal resource budget. Existing WP18/WP19 data
are informative but do not directly decide that claim: they use an oracle-gap certificate, and the
WP18 programme stop rule is not a scientific equivalence test. In addition, `c_route` was measured
as a FLOP ratio while WP18 compared it to a utility-space lower confidence bound; this experiment
avoids that dimensional bridge entirely by comparing quality at **exactly matched logical FLOPs**.

This experiment is deliberately asymmetric:
- a PASS can only establish a narrow real-data small-model adaptive-depth result and cannot establish
  full L7/MoE/large-model superiority;
- a FAIL on either frozen real workload family kills this specific adaptive-depth branch in this
  regime and blocks promotion from it.

## Frozen data substrate

No new corpus is selected. The previously frozen WP18 real-data split is reused byte-for-byte.
Training data are never evaluation data. Evaluation cohorts are file-disjoint:

- CALIBRATION: `eval1 + eval2`
- PRIMARY: `eval3 + eval4`
- REPLICATION: `eval5`

### SHA-256 bindings

```text
c8908856e76dcaf9821388d027fb4ce4219bad01a92f9efcd4ae6a5242283d09  corpus_prose_train.txt
bc36bae46dd0611600691c5beeda4e7b75d0af90821ff3054005c9baf7664fbb  corpus_prose_eval1.txt
1d9839f79c24d8508d9341db8733fd459a5a75ff872a9332c4419a94efefc571  corpus_prose_eval2.txt
bf71b8544096e317f1557a932f4b299aa019cd8f1a414b94da88c3a63a108172  corpus_prose_eval3.txt
322caad772d06b92ec1b0af31f4f2798a4238032609c14c7378549e99d2e176f  corpus_prose_eval4.txt
9216ab79a57cb3d49cbbe06cfee9dfe3dd14145fa964a24128f52ee9a709d99f  corpus_prose_eval5.txt
1378a6448e492cb20ea9ec755cf7bab8cfe39bb782de83b37619c17e87898ca1  corpus_code_train.txt
5904959a4ba16dbed66d9aad4761aea52b51fd79874a59f3706c74d5794f50be  corpus_code_eval1.txt
30b083fe083da170761564210cc7c522dada9bed947a9ac936ae8d14f55024e3  corpus_code_eval2.txt
685749478c837bab57b1c1547d1f3efe54237c96e44aa2ec675ee5d16d3cdd5a  corpus_code_eval3.txt
74826093a986246141fe9b2ad19770573a394991ea6a919ff12628d912d03e8d  corpus_code_eval4.txt
1bd8b76723710d6115e9d381b9f4b01168e02212f22462efbef7f464bcfd5da0  corpus_code_eval5.txt
```

These are real prose and Python-code corpora collected from the repository, not external public
benchmarks. Therefore external-transfer authority is prohibited even on PASS.

## Frozen model

A fresh two-exit Transformer is trained from scratch for this experiment:

- byte vocabulary: 256
- sequence length: 64
- `d_model = 64`
- `n_head = 4`
- two independent Transformer blocks
- one shared LM head
- training objective: `0.5 * CE(exit1) + 0.5 * CE(exit2)`
- training steps: 400
- batch size: 16
- AdamW learning rate: `3e-3`
- weight decay: `0.01`
- training source alternates prose/code deterministically by step
- each batch's offsets are generated from the model seed only

Fresh model seeds:

- CALIBRATION: `74101`
- PRIMARY: `74201, 74202, 74203`
- REPLICATION: `74301, 74302, 74303`

No PRIMARY/REPLICATION seed may be replaced after any result is observed.

## Frozen evaluation cases

Each evaluation file contributes exactly 64 sequence windows. Window start offsets are determined
by SHA-256 of:

`CWC-FLAGSHIP-ROUTE-01 || cohort || family || file_sha256 || window_index`

No model seed, target byte, loss, or policy output may affect case membership.

A route decision is made **per entire 64-token window**, not per token. This makes the second block
physically skippable for a selected batch row and avoids pretending token-wise sparse execution is
free or architecturally trivial.

## Information boundary

At decision time the policy may observe only statistics of exit-1 logits computed from the input
window. Gold next bytes, exit-2 logits, losses, case IDs, file names, cohort labels and future
information are forbidden.

Exact candidate features, aggregated over the window:

1. mean predictive entropy;
2. p90 predictive entropy;
3. mean top1-top2 probability margin;
4. p10 top1-top2 probability margin;
5. known family indicator (`PROSE=0`, `CODE=1`).

The family indicator is allowed because workload family is known before inference. No finer source
identity is allowed.

## Frozen candidate policy

CALIBRATION only fits a ridge regression from the five pre-decision features to realized marginal
second-layer value:

`gain = mean_CE(exit1) - mean_CE(exit2)`.

Implementation is closed-form ridge with intercept, feature standardization from CALIBRATION only,
and fixed `alpha = 1e-3`. No model or threshold search is permitted.

For each family, CALIBRATION computes the fixed-depth quality/compute frontier slope between depth 1
and depth 2. On PRIMARY/REPLICATION, `DECISION_RELEVANT` continues a window iff predicted gain per
incremental dynamic FLOP exceeds that frozen calibration frontier slope. The final evaluator still
charges all actual dynamic FLOPs; the rule itself cannot waive router/intermediate-head cost.

## Frozen baselines

Every PRIMARY/REPLICATION seed/family cell must include:

1. `FIXED_DEPTH_1`;
2. `FIXED_DEPTH_2`;
3. `FIXED_FRONTIER` — convex mixture of depth1/depth2 at the candidate's exact total logical FLOPs;
4. `RANDOM_MATCHED` — deterministic SHA-based continuation of exactly the candidate continuation count;
5. `ENTROPY_MATCHED` — highest mean exit-1 entropy, same continuation count;
6. `MARGIN_MATCHED` — lowest mean exit-1 margin, same continuation count;
7. `ORACLE_MATCHED` — highest realized `loss1-loss2`, same continuation count, diagnostic upper bound only;
8. `DECISION_RELEVANT` — the frozen candidate.

`ORACLE_MATCHED` can never create promotion authority because it uses gold targets to allocate
compute. It exists only to distinguish "router failed" from "no allocation headroom exists".

## Exact resource accounting

Compute unit is logical forward FLOPs under `1 MAC = 2 FLOPs`.

For a window:

- `C1`: embedding lookup (0 dense FLOPs) + block1 + LM head;
- `C2`: block1 + block2 + one LM head;
- a dynamic halted window costs `C1 + C_router`;
- a dynamic continued window costs `C1 + C_router + block2 + LM_head`, because exit-1 logits were
  physically computed before the route decision and the post-block2 prediction requires another
  head evaluation;
- `C_router` is the exact five-feature linear-score cost and is always charged.

A dynamic policy is `OUTSIDE_FIXED_FRONTIER` if its mean compute exceeds `C2`; such a cell cannot
claim Pareto superiority and counts as a failed required endpoint.

Wall-clock is descriptive only. No wall-clock/energy promotion is allowed.

## Frozen endpoints

Evaluate PRIMARY and REPLICATION separately. Replication can never rescue PRIMARY.

For **every one of 3 model seeds in each of the two workload families**, all of the following must
hold:

1. candidate compute lies within `[C1, C2]`;
2. candidate mean CE is strictly lower than `FIXED_FRONTIER` at identical logical FLOPs;
3. candidate mean CE is strictly lower than `RANDOM_MATCHED`;
4. candidate mean CE is no worse than `ENTROPY_MATCHED`;
5. candidate mean CE is no worse than `MARGIN_MATCHED`;
6. `ORACLE_MATCHED` is no worse than candidate (semantic sanity check);
7. zero information-boundary violations;
8. exact candidate/baseline continuation counts match where required;
9. no train/eval file overlap and all frozen SHA-256 values match.

Cohort-level PASS additionally requires the median candidate advantage over `FIXED_FRONTIER` to be
strictly positive in both families. No p-value or token-as-independent-replicate claim is permitted;
model seed is the experimental unit.

### Verdicts

- `CWC_FLAGSHIP_ROUTE_01_SUPPORTED_NARROW` iff every frozen endpoint passes in PRIMARY and again in
  REPLICATION.
- `CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED` on any PRIMARY endpoint failure. Replication is still run
  for negative robustness but cannot rescue the verdict.
- `CWC_FLAGSHIP_ROUTE_01_PRIMARY_PASS_REPLICATION_FAIL` if PRIMARY fully passes but REPLICATION
  fails.
- `CWC_FLAGSHIP_ROUTE_01_VOID` on schema/hash/leakage/evaluator corruption.

A negative kills only this two-exit small-model adaptive-depth branch on these two frozen real
families. It does not prove adaptive compute impossible in general.

## Frozen semantic/null attacks

Before scientific execution, tests must kill mutations that:

- feed target bytes into candidate features;
- use exit-2 logits in a pre-decision feature;
- derive evaluation window offsets from model seed;
- omit the first LM-head cost from continued dynamic windows;
- omit router FLOPs;
- clamp an outside-frontier candidate to depth2 and call it matched;
- allow RANDOM/ENTROPY/MARGIN continuation counts to differ from candidate;
- allow ORACLE output to create promotion authority;
- fit ridge/scaling on PRIMARY or REPLICATION;
- change any frozen model seed;
- permit REPLICATION to rescue a PRIMARY failure;
- accept a corpus SHA mismatch.

Every injected mutation must fail its gate before PRIMARY execution.

## Non-promotion boundary

Even a full PASS does not establish:

- external benchmark transfer;
- MoD/MoE superiority;
- large pretrained-model scaling;
- token-wise sparse execution;
- latency/energy advantage;
- architecture-level L7 Pareto dominance;
- independent third-party replication;
- novelty.

It would only show that a real-data adaptive-depth mechanism can allocate a second block better than
fixed/random/generic uncertainty controls under exact logical-FLOP accounting in this frozen
small-model regime.
