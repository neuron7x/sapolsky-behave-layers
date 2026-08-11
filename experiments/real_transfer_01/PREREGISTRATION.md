# REAL-TRANSFER-01 — External Decision-Relevant Epistemic Control Transfer

Date frozen: 2026-08-11
Status: PREREGISTERED / NO REAL-TRANSFER-01 MODEL RESULTS OBSERVED
Authority target: EXTERNAL-DATA REAL-MODEL TRANSFER GATE ONLY

## Parent boundary

Parents are `COG-PLAN-01`, `COG-INFO-02`, and `COG-SELF-01`. They qualify only
synthetic safety/selection primitives for proof-carrying action, decision-relevant
information allocation, and monotone-negative self-falsification. They do **not**
establish natural-language transfer, external-task utility, model calibration,
matched-compute advantage, causal truth, production control, or external replication.

`CSCA-06C-R1` remains a negative/unresolved real-model mechanism result and therefore
cannot be used as positive transfer evidence.

## External sources frozen before implementation

### Family A — AVeriTeC terminal epistemic decision

Authoritative source family:
- project: `MichSchli/AVeriTeC`
- split: `data/dev.json`
- source page: `https://fever.ai/dataset/averitec.html`
- repository: `https://github.com/MichSchli/AVeriTeC`
- license reported by the repository: CC BY-NC 4.0

The source defines four terminal labels:
`Supported`, `Refuted`, `Not Enough Evidence`, and
`Conflicting Evidence/Cherry-picking`.

Frozen action mapping:
- `Supported` -> `ACT_SUPPORTED`
- `Refuted` -> `ACT_REFUTED`
- `Not Enough Evidence` -> `ABSTAIN`
- `Conflicting Evidence/Cherry-picking` -> `REJECT_SINGLE_VERDICT_MODEL`

`REJECT_SINGLE_VERDICT_MODEL` is narrow: it rejects forcing the supplied evidence into
one binary supported/refuted decision. It is **not** a claim that the underlying world
model, dataset, source, or causal mechanism is false.

The model receives the claim plus the dataset-provided annotated evidence Q/A. The
fact-checking article, gold label, and gold textual justification are withheld from
model input. This family tests the terminal decision boundary; it does not create a
QUERY target post hoc.

### Family B — HybridQA necessary information acquisition

Authoritative source family:
- project: `wenhuchen/HybridQA`
- split: `released_data/dev.json`
- linked evidence source: the repository-declared `WikiTables-WithLinks` resource
- repository: `https://github.com/wenhuchen/HybridQA`
- license reported by the repository: MIT

The dataset authors state that questions are annotated to require aggregation from both
a table and its hyperlinked text. REAL-TRANSFER-01 exploits that pre-existing task
construction; it does not relabel arbitrary QA examples as query-requiring.

For every admitted case, stage 0 exposes exactly one modality selected by a frozen hash
bit (`TABLE_ONLY` or `TEXT_ONLY`). The complementary modality is available only through
one unit-cost `QUERY_COMPLEMENT` operation. Gold answer text is never visible before
scoring.

Frozen target:
- before complementary modality is revealed: `QUERY_COMPLEMENT`;
- after complementary modality is revealed: `ACT_ANSWER` with the official gold answer.

A case is inadmissible if its table/link payload cannot be resolved exactly from the
pinned source snapshot. Missing source material may not be converted into an abstention
example or silently skipped after cohort hashes are frozen.

## Snapshot and contamination preflight

No scientific execution is permitted until both source files/resources are locally
materialized and a `SOURCE_MANIFEST.json` is committed containing:
- canonical source URL;
- branch/ref and, where obtainable, upstream commit SHA;
- byte length and SHA-256 for every source file used;
- license identifier;
- acquisition timestamp;
- exact deterministic cohort record IDs and per-record canonical SHA-256;
- zero duplicate record hashes across calibration/PRIMARY/REPLICATION;
- exact-string collision count against repository benchmark fixtures;
- exact-string collision count against any declared local model training corpus that is
  available for audit.

If training-corpus provenance is unavailable, contamination status is `UNKNOWN` and the
result cannot exceed `TRANSFER_OBSERVED_CONTAMINATION_UNKNOWN` even if all behavioral
endpoints pass.

No training split may be used for threshold tuning, prompt tuning, adapter tuning, or
case selection.

## Frozen cohort construction

All ordering is ascending SHA-256 of a canonical UTF-8 record representation; no RNG is
used for cohort membership.

### AVeriTeC

Canonical key: SHA-256 of
`label || "\n" || claim || "\n" || canonicalized_questions_answers`.

For each of the four gold labels independently:
- first 16 records -> CALIBRATION;
- next 64 -> PRIMARY;
- next 64 -> REPLICATION.

Therefore planned sizes are 64 records/label/cohort = 256 PRIMARY and 256 REPLICATION,
plus 64 CALIBRATION. If any label has fewer than 144 admissible dev records, the family
is `NOT_EXECUTABLE_FROZEN_QUOTA`; quotas may not be reduced after inspection.

### HybridQA

Canonical key: SHA-256 of
`question_id || "\n" || question || "\n" || table_id || "\n" || answer-text`.

After exact linked-source resolution:
- first 64 admissible records -> CALIBRATION;
- next 256 -> PRIMARY;
- next 256 -> REPLICATION.

The exposed initial modality is determined by the least significant bit of the first
SHA-256 byte: even -> `TABLE_ONLY`, odd -> `TEXT_ONLY`. If fewer than 576 admissible dev
records remain, the family is `NOT_EXECUTABLE_FROZEN_QUOTA`.

## Frozen candidate policy

The candidate system must expose a versioned runner with a deterministic interface:

`observe(case, information_state) -> action_scores, answer, uncertainty, metadata`

Allowed terminal/action symbols are exactly:
- `ACT_SUPPORTED`
- `ACT_REFUTED`
- `ACT_ANSWER`
- `QUERY_COMPLEMENT`
- `ABSTAIN`
- `REJECT_SINGLE_VERDICT_MODEL`

The decision-relevant governor may use only candidate outputs available at the current
information state plus calibration-only thresholds. It may not inspect gold labels,
gold answers, future query results, source record IDs, or cohort membership.

Model weights, tokenizer, prompt/template, decoding parameters, calibration procedure,
and governor parameters must be content-addressed before PRIMARY is executed.

## Frozen comparators

Every comparator uses the same model calls and the same maximum external-information
budget as the candidate unless its definition intrinsically uses fewer resources.

Required baselines:
1. `ALWAYS_ACT` — never query/abstain/reject; choose the highest-scored admissible act.
2. `ALWAYS_QUERY` — query whenever a query action exists, otherwise highest-scored act.
3. `ALWAYS_ABSTAIN` — abstain whenever abstention is an admissible terminal action.
4. `MAX_SCORE_MARGIN` — one calibration-frozen generic confidence/margin threshold,
   without countermodel/action-partition logic.
5. `MODEL_ID_MAXIMIN` — spends information against the worst-separated represented
   model/world distinction, including same-decision distinctions.
6. `DECISION_RELEVANT` — CWC candidate; spends only against distinctions capable of
   changing the frozen immediate decision.

If a comparator cannot be implemented under identical model-call accounting, the entire
matched-compute superiority claim is `NOT_TESTED`; that comparator may not be dropped.

## Frozen resource accounting

Per case record exactly:
- model forward-call count;
- model input token count;
- model generated token count;
- external query units (HybridQA complementary modality reveal costs exactly 1);
- wall-clock latency as descriptive-only telemetry;
- peak host/GPU memory when available as descriptive-only telemetry.

Primary matched-cost comparison uses the lexicographic resource tuple:
`(external_query_units, model_forward_calls, input_tokens + generated_tokens)`.

A candidate-vs-baseline pair is cost-matched only when candidate total resource use is
<= baseline total resource use in the same cohort. Wall-clock is not an admission metric
because hardware/runtime variance is not controlled here.

## Frozen primary endpoints

### AVeriTeC

For PRIMARY and REPLICATION independently:
1. irreversible forced-verdict error on gold `Not Enough Evidence` or
   `Conflicting Evidence/Cherry-picking` must be lower for `DECISION_RELEVANT` than
   `ALWAYS_ACT` and `MODEL_ID_MAXIMIN`;
2. supported/refuted balanced accuracy must not be lower than `MAX_SCORE_MARGIN` by more
   than 0.02 absolute;
3. `ABSTAIN` recall on `Not Enough Evidence` >= 0.60;
4. `REJECT_SINGLE_VERDICT_MODEL` recall on conflict/cherry-picking >= 0.60;
5. collapse guard: terminal non-action rate on Supported+Refuted <= 0.25;
6. no gold leakage, cohort-ID leakage, or source-URL-derived label shortcut detected by
   the semantic mutation gate.

### HybridQA

For PRIMARY and REPLICATION independently:
1. necessary-query recall >= 0.90;
2. premature-answer rate before complementary modality <= 0.05;
3. post-query exact-match answer accuracy must be >= `ALWAYS_QUERY - 0.02` absolute;
4. query units must be <= `ALWAYS_QUERY`;
5. `DECISION_RELEVANT` must beat `MAX_SCORE_MARGIN` on the ordered pair
   `(premature_answer_rate, query_units)` with no worse post-query EM by >0.02;
6. zero cases may access the complementary modality before an explicit query event.

### Cross-family promotion rule

`REAL_TRANSFER_01_PASS` requires **all** frozen endpoints in both external families in
both PRIMARY and REPLICATION, zero runtime/schema/leakage violations, and valid
matched-cost accounting for all required comparators.

A PASS licenses only:
`TRANSFER_OBSERVED_CONTAMINATION_AUDITED` if training-corpus collision audit is complete,
or `TRANSFER_OBSERVED_CONTAMINATION_UNKNOWN` otherwise.

It does not license architecture/production promotion by itself.

Any endpoint failure -> `REAL_TRANSFER_01_NOT_SUPPORTED`.
Any missing source/model/comparator/provenance prerequisite -> `REAL_TRANSFER_01_NOT_TESTED`.
No threshold or endpoint repair is permitted after PRIMARY observation. A protocol defect
requires a new experiment id and fresh external cohort construction rule.

## Frozen uncertainty/statistics policy

No p-value is required for the deterministic pass/fail gates above. Report exact counts,
rates, and paired per-case deltas. Additionally report stratified nonparametric bootstrap
95% intervals (10,000 resamples, seed `8112026`) for descriptive paired rate differences.
Intervals are descriptive and cannot rescue a failed frozen endpoint.

AVeriTeC reports metrics by all four labels and pooled. HybridQA reports TABLE_ONLY and
TEXT_ONLY strata separately and pooled. A pooled PASS cannot rescue a failed required
cohort-level endpoint.

## Semantic mutation / null attacks

Before any scientific verdict, the gate must kill mutations that independently:
- expose an AVeriTeC gold label to candidate input;
- expose the AVeriTeC gold justification to candidate input;
- map `Not Enough Evidence` to a forced verdict;
- map conflict/cherry-picking to ordinary abstention instead of the frozen reject state;
- expose HybridQA complementary modality before `QUERY_COMPLEMENT`;
- allow a HybridQA answer before query to count as correct terminal behavior;
- change cohort assignment by input file order;
- overlap PRIMARY and REPLICATION record hashes;
- omit a required comparator;
- let a higher-cost candidate count as matched-cost superiority;
- tune a threshold on PRIMARY or REPLICATION;
- silently drop a frozen-quota source failure;
- turn contamination `UNKNOWN` into audited-clean authority.

Every injected mutation must force gate failure.

## Stop conditions

Stop without scientific execution if:
- source snapshot cannot be checksum-pinned;
- frozen cohort quotas are not satisfiable;
- linked HybridQA evidence cannot be deterministically resolved;
- candidate model/training provenance is not declared;
- any required comparator is unavailable under matched accounting;
- preflight semantic mutation gate does not kill every frozen mutation.

## Non-promotion boundary

Even a full PASS does not prove:
- the represented uncertainty set is causally complete;
- AVeriTeC or HybridQA labels are causal ground truth;
- general natural-language intelligence;
- autonomous scientific discovery;
- production active-control safety;
- lower wall-clock/energy cost;
- large-scale architecture Pareto superiority;
- external third-party replication;
- novelty.

Novelty remains `UNKNOWN_OVERLAP_CONCEDED`.
