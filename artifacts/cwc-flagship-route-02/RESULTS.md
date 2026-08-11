# CWC-FLAGSHIP-ROUTE-02 — Final Rescue Results

Date: 2026-08-11
Scientific verdict: `CWC_FLAGSHIP_ROUTE_02_NOT_SUPPORTED`
Programme decision: **CURRENT TWO-EXIT LEARNED ADAPTIVE-DEPTH SUBPROGRAMME CLOSED; NO R3 RESCUE.**

## Frozen question

Does per-model CALIBRATION-only routing remove the cross-seed coordinate failure identified after R1 strongly enough to produce robust compute-matched Pareto improvement across every fresh PROSE/CODE model seed and again in replication?

## Temporal provenance

- R2 preregistration commit: `c17d6894050c9a9b96fc868bb1cf9e55c3ef68fb`.
- implementation commit: `9e7a7272451c2d05c203bc529715ed9e2c5ccb1b`.
- frozen per-model calibration/checkpoint commit: `7b1f777229005fa8875d500ff5486111dd487a03`.
- no R2 PRIMARY/REPLICATION outputs existed before the calibration commit.

## Confirmatory execution

| Cohort | Family | Seed | Continue rate | Advantage vs fixed frontier (CE) | Cell |
|---|---|---:|---:|---:|---|
| PRIMARY | PROSE | 74401 | 0.546875 | +0.0029852851 | PASS |
| PRIMARY | CODE | 74401 | 0.671875 | +0.0025385440 | PASS |
| PRIMARY | PROSE | 74402 | 0.460938 | +0.0017897494 | PASS |
| PRIMARY | CODE | 74402 | 0.523438 | +0.0080106402 | PASS |
| PRIMARY | PROSE | 74403 | 0.484375 | -0.0000499135 | FAIL |
| PRIMARY | CODE | 74403 | 0.453125 | +0.0134575445 | PASS |
| REPLICATION | PROSE | 74501 | 0.578125 | +0.0043847324 | FAIL |
| REPLICATION | CODE | 74501 | 0.484375 | +0.0057446065 | PASS |
| REPLICATION | PROSE | 74502 | 0.593750 | +0.0031716485 | FAIL |
| REPLICATION | CODE | 74502 | 0.562500 | +0.0067385932 | PASS |
| REPLICATION | PROSE | 74503 | 0.453125 | +0.0053832960 | PASS |
| REPLICATION | CODE | 74503 | 0.515625 | +0.0088404798 | PASS |

PRIMARY: **5/6 cells PASS**; cohort verdict FAIL.
REPLICATION: **4/6 cells PASS**; cohort verdict FAIL.

Family anatomy: CODE passes `6/6` seed-cohort cells; PROSE passes `3/6`.
PRIMARY median fixed-frontier advantage remains positive in both families (`PROSE +0.0017897494`, `CODE +0.0080106402`), but the preregistered conjunction requires every cell and replication cannot rescue a PRIMARY failure.

## Failure anatomy

- `PRIMARY/PROSE/seed74403`: failed `beats_fixed_frontier, beats_random_matched`; advantage `-0.0000499135`.
- `REPLICATION/PROSE/seed74501`: failed `beats_difficulty_matched`; advantage `+0.0043847324`.
- `REPLICATION/PROSE/seed74502`: failed `beats_difficulty_matched`; advantage `+0.0031716485`.

The R2 mechanism repair materially improved R1: per-model calibration removed most cross-seed raw-coordinate pathology and made CODE robust. It did **not** make decision-relevant gain prediction robust on PROSE: one PRIMARY cell fails the fixed/random frontier, and two REPLICATION cells lose to the matched difficulty predictor despite beating the fixed frontier. Therefore marginal-value prediction is not stably better than generic difficulty prediction across the frozen real-data families.

## What is killed

The current two-exit learned adaptive-depth lineage consisting of R1 shared-router and R2 per-model-calibrated linear gain routing is closed. Under the preregistered R2 programme rule there is no R3 feature/threshold/router rescue. Any future adaptive-compute work must be a materially different architecture and a new hypothesis lineage.

## What is not killed

- CWC as a falsification/evidence runtime;
- the decision-equivalence / decision-relevant information hypothesis (`COG-INFO-02`);
- external `REAL-TRANSFER-01`, still `NOT_TESTED`;
- adaptive computation as a general field or impossibility claim;
- broad L7 as a logical claim, though it now has **no surviving CWC adaptive-depth candidate** and architecture promotion is blocked.

## Independent verification

`scripts/verify_cwc_flagship_route_02.py` recomputes every scientific cell from frozen checkpoint bytes, per-model policy bytes and cohort windows without calling the R2 evaluator. It reproduces PRIMARY `5/6`, REPLICATION `4/6`, and the negative verdict. Its serialized-result mutation test kills `5/5` attacks.

