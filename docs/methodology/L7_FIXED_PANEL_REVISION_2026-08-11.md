# L7 Fixed-Panel Revision — 2026-08-11

Status: MASTER-HYPOTHESIS REPAIR / NO L7-R1 EXECUTION AUTHORITY.

## Defect in historical H-L7 wording

Historical H-L7 states that CWC Pareto-dominates MoD/MoE at equal budget on `>=2 real workloads`.
Without a closed workload panel frozen before outcomes, this is an open existential target: a finite
negative set cannot falsify it because failed workloads can always be replaced. That wording is
therefore unsuitable as the final confirmatory kill/promotion rule.

H-L7 remains historically `NOT_TESTED`; this document narrows the next admissible test rather than
retroactively changing old evidence.

## Fixed panel

The first architecture-level L7 revision uses exactly two external families already named by
`REAL-TRANSFER-01`:

1. AVeriTeC — terminal evidence-sensitive fact-verification decisions;
2. HybridQA — heterogeneous table + linked-text information acquisition / answering.

No workload may be substituted, added, dropped or reweighted after any L7-R1 model outcome is
observed. Failure of either family is a panel failure.

Exact source bytes, upstream refs, licenses and per-record cohort hashes MUST be frozen in a
checksum-bound source manifest before execution. Until those bytes exist locally, L7-R1 is
`NOT_TESTED`, not failed and not partially supported.

## Candidate identity

L7-R1 cannot execute until a model manifest freezes, at minimum:

- base model/checkpoint bytes and SHA-256;
- tokenizer bytes and SHA-256;
- CWC runtime/route-policy implementation paths and SHA-256;
- prompt / decoding / tool schemas;
- parameter count and trainable-parameter policy;
- all calibration data and seeds;
- exact inference resource-accounting convention.

No candidate checkpoint or routing policy may be replaced after PRIMARY starts.

## Comparator panel

The same base-model family and task interface MUST expose:

1. `STATIC_FIXED` — non-adaptive fixed compute;
2. `GENERIC_DYNAMIC` — matched-sensor uncertainty/difficulty compute allocation;
3. `MOD_MATCHED` — Mixture-of-Depths-style depth allocation under matched accounting;
4. `MOE_MATCHED` — sparse expert routing under matched accounting;
5. `CWC_CANDIDATE` — the frozen CWC mechanism stack.

A named comparator without checksum-bound executable implementation is `NOT_EXECUTABLE`; it cannot
be approximated by a label or omitted from a positive L7 verdict.

## Sequential fail-closed gate

L7-R1 is intentionally sequential so compute is not spent proving superiority against strong
comparators when the candidate cannot clear a weaker necessary condition.

### Gate A — provenance / contamination

Both external snapshots, model identity, comparator implementations and calibration partitions are
checksum-bound; contamination state is declared. Any missing binding => `NOT_TESTED`.

### Gate B — static necessary condition

In every PRIMARY seed/family cell, CWC must be strictly better in task utility at a resource budget
no greater than the best `STATIC_FIXED` Pareto envelope. A failure in any cell =>
`L7_R1_NOT_SUPPORTED_STATIC_NECESSARY_CONDITION` and MoD/MoE execution is not required.

### Gate C — generic dynamic control

If Gate B passes, CWC must strictly beat `GENERIC_DYNAMIC` under the same observable sensor boundary
and matched total resource budget. Any failure => `L7_R1_NOT_SUPPORTED_GENERIC_DYNAMIC`.

### Gate D — MoD/MoE direct comparison

If Gates B/C pass, CWC must Pareto-dominate both `MOD_MATCHED` and `MOE_MATCHED` on each fixed family
under the frozen primary quality/resource vector. Any family/comparator failure =>
`L7_R1_NOT_SUPPORTED_STRONG_BASELINE`.

### Gate E — replication

The full PRIMARY conclusion must reproduce under fresh frozen REPLICATION seeds/cohorts. Replication
can invalidate a PRIMARY success but can never rescue a PRIMARY failure.

Only Gates A-E passing authorizes `L7_R1_SUPPORTED_NARROW_FIXED_PANEL`.

## Required resource vector

At minimum the promotion vector records, for every system/seed/family:

- task utility / safety endpoint defined by the task preregistration;
- logical model FLOPs;
- model/tool calls;
- generated + consumed tokens where applicable;
- peak resident accelerator/CPU memory when measurable;
- wall-clock only as a secondary physical diagnostic unless the hardware/instrument contract is
  independently qualified.

No scalar weighted score may hide a dominated dimension for a Pareto claim.

## Relation to CWC-FLAGSHIP-ROUTE-01/02

`CWC-FLAGSHIP-ROUTE-01` is `NOT_SUPPORTED` on the internal frozen PROSE/CODE panel. Its post-hoc
same-model calibration diagnostic identified cross-seed hidden-coordinate transfer as a concrete
failure mode, so one final preregistered rescue was allowed: `CWC-FLAGSHIP-ROUTE-02` fitted the same
fixed ridge rule separately on each model's CALIBRATION windows while keeping the model, training,
resource accounting, frontier and matched-control semantics fixed and using R1-disjoint evaluation
offsets. R2 improved to PRIMARY `5/6` and REPLICATION `4/6` but still failed the frozen all-cell rule.
Its preregistration explicitly forbids R3 rescue. The current two-exit learned adaptive-depth lineage
is therefore terminated and cannot be nominated as L7-R1.

## Current state

`L7-R1 = NOT_TESTED / BLOCKED`.

The broad L7 logical claim is not globally falsified because the external fixed-panel MoD/MoE
comparison never executed. However, there is now no surviving adaptive-depth CWC candidate authorized
for that promotion path. Programme continuation is narrowed to the independent decision-relevant
epistemic-control flagship and `REAL-TRANSFER-01`; see `docs/vnv/CWC_PROGRAM_DECISION_2026-08-11.md`.
