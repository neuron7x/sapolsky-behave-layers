# WP18 — Real-Workload Identifiability PILOT (PREREGISTRATION)

**Act:** CWC-ASCEND-2026-01, gates **G3/G5/G7** (pilot stage only). Committed separately, before any
result exists. **Class ceiling: PILOT.** Per Act §7 step 4 this WP estimates oracle gap, variance,
MDE and route-decision cost **only**. It raises **no architecture claim** and cannot support L7.

## Scope actually available (declared up front, not discovered later)
Local, no cloud, no pretrained checkpoint, 4 GB consumer GPU. Therefore this is a **small-scale**
pilot: byte-level recurrent LMs trained from scratch. Any conclusion is bounded by that regime and
must say so. The Act's full G3 (≥5 independent real corpora at real scale) is **not** reachable
here; what is reachable is the *decision instrument* the Act asks for before approving cloud spend.

## Workloads — two distinct real task families
| id | family | source | split rule |
|---|---|---|---|
| `prose` | natural-language English | repo `docs/**/*.md` (real prose) | by content hash, immutable |
| `code` | Python source | repo `**/*.py` (real code) | by content hash, immutable |

Both are **real** data with genuinely different byte distributions. Each is split into disjoint
train / **5 held-out eval shards** by SHA-256 of the source file (deterministic, not random), so
eval bytes never appear in training. **Contamination test:** assert zero shared source files and
zero byte-window overlap between train and every eval shard; the check is part of the artifact.

## Design
- **Scales:** `d_model ∈ {32, 64}` (2 model scales).
- **Sequence-length regimes:** `T ∈ {32, 64}` (2 regimes).
- **Compute action:** `K ∈ {1,2,3}` shared-block iterations (same mechanism as WP5/WP6).
- **Difficulty signal:** bigram surprisal terciles (the stronger contextual signal WP14 used).
- **Seeds:** 3 per cell (pilot — the purpose is variance, not confirmation).

## Estimands (what is being measured)
1. `G_lo` — debiased lower confidence bound on the oracle gap (corrected certificate,
   `gap_lower_confidence_bound_corrected`, δ=0.05), per workload, aggregated over eval shards.
2. Between-shard and between-seed variance components.
3. **Prospective MDE and seed count**: from the pilot variance, the number of seeds/corpora a
   confirmatory study would need at power 0.80, α=0.05.
4. `c_route` — taken from WP17's *measured* encoder-router cost, converted to the same λ-penalty
   units as the certificate.

## Frozen decision rule
- A workload **passes G3** iff `G_lo > c_route` (identifiable *after* paying for the decision).
- **KILL RULE (Act WP18):** if **both** workloads have `G_lo ≤ c_route`, architecture work stops and
  the negative boundary is published. No re-running with new difficulty signals to hunt a positive —
  WP6 (unigram) and WP14 (bigram) already tested two signals; a third negative is a boundary, not
  an instrument problem.
- **Positive control (mandatory):** the synthetic AC1 certificate must be `> 0` in the same run.
  If the control fails, the whole result is `WP18_VOID` — no conclusion either way.

## Leakage / validity probes (all preregistered)
- **Surface probe:** predict the best K from surface features only (byte identity, position). Must
  be statistically indistinguishable from chance; if it predicts, the "difficulty" signal is surface
  leakage, not difficulty.
- **Shuffled-context null:** shuffle difficulty labels across tokens → the gap must vanish.
- Route decisions may use **pre-decision information only**.

## Kill rules (falsifiers)
- FAIL/VOID if the synthetic positive control does not certify.
- FAIL if train/eval contamination is detected.
- The negative outcome is the *expected* one given WP6/WP14; it will be **registered, not re-run
  away**. A positive would be the surprise and would need confirmatory replication before any claim.

## Prohibited extrapolations
- Real-workload compute-equivalent Pareto (**L7**) — untouched, still cloud-blocked.
- Any statement about large models or production workloads: this is a from-scratch small-model pilot.
- Any architecture claim whatsoever.
