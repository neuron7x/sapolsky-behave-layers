# CSCA-06B-OP — Direct-Intervention Operator-Family Robustness

**Status:** PREREGISTERED BEFORE AUTHORITATIVE EXECUTION  
**Parent:** `CSCA-05-RUNTIME = DIRECT_INTERVENTION_SHADOW_RUNTIME_QUALIFIED_NARROWED`  
**Prior diagnostic:** SPACE/ZERO/0xFF/REVERSE top agreement 0.84375 and sign agreement 0.71875; diagnostic only, not reused as confirmatory data.  
**Authority before/after:** shadow measurement only; no active control.

## Kill question

Does the model-internal causal-credit ranking survive a declared family of *stochastic content-erasing soft interventions*, or was the CSCA-05 result primarily an artifact of the single ASCII-SPACE replacement operator?

## Epistemic correction before the experiment

SPACE, ZERO, 0xFF and REVERSE are **not** assumed to be equivalent realizations of one latent semantic `do()`. They alter different byte-level distributions and may correspond to different interventions. Therefore this experiment does not test "semantic equivalence" of arbitrary corruptions.

Instead it defines two explicit intervention kernels and asks for robustness across that declared family. Any positive result is `OPERATOR_FAMILY_ROBUSTNESS`, not semantic causality or causal-abstraction equivalence.

## Factual substrate

Reuse the three already-sealed CSCA-05 nanochat checkpoints only as frozen model substrates:

- calibration checkpoint seed 1301;
- PRIMARY checkpoint seed 2301;
- independent REPLICATION checkpoint seed 3301.

No training occurs in CSCA-06B. Prompt units are fresh deterministic offsets generated under a new `CSCA06B` namespace. A machine check must establish zero prompt-hash overlap with all CSCA-05 calibration/PRIMARY/REPLICATION prompt hashes.

Contexts remain PROSE and CODE. Each cohort has 24 fresh prompts per context (48 total).

## Causal variable and outcome

Players remain the four disjoint 4-byte spans:

`A_RECENT, B_PREV, C_MIDDLE, D_EARLY`.

For factual prompt `x`, target outcome remains pre-outcome/model-internal:

`y* = argmax P_model(next_token | x)`.

Utility for a stochastic intervention kernel `K` is

`v_K(S) = E_{r~K}[ log P_model(y* | do_K(kept=S, replacement=r)) ]`.

The expectation is represented by an exactly enumerated frozen empirical kernel with 8 deterministic donor assignments. Exact Shapley is computed on `v_K`, so there is no finite-Shapley estimator error in this gate.

## Admissible operator family

Two distinct, explicit soft-intervention kernels are tested:

1. `K_TRAIN_CONTIG8`: for every player and donor index, replace an ablated 4-byte span by a deterministic hash-selected contiguous 4-byte donor from the same-context **training corpus**.
2. `K_COHORT_CONTIG8`: same construction, but donors come from the same-context held-out cohort corpus used to draw fresh prompt units.

Donor selection is independent of model outputs and candidate credit. Exact donor bytes are frozen by hash namespace before evaluation. If a selected donor exactly equals the factual span, deterministic forward scanning chooses the next non-identical donor.

`ASCII_SPACE` is retained only as a legacy diagnostic and is not a member of the admissible family.

## Calibration

Calibration may determine only the credit-separation margin `delta`:

`delta = clip(0.25 * q10(min(gap_KTRAIN, gap_KCOHORT)), 1e-6, 0.25)`.

No confirmatory gate threshold below may be tuned by calibration.

## Per-prompt robust authority

For each prompt, let the exact Shapley vectors be `phi^train` and `phi^cohort`.

Return `OPERATOR_FAMILY_ROBUST_CONTEXT_ONLY(i,s)` only if:

1. the same candidate `i` is top-ranked by absolute credit under both kernels;
2. `sign(phi_i^train) = sign(phi_i^cohort) = s != 0`;
3. both within-kernel top gaps exceed frozen `delta`;
4. `min(|phi_i^train|, |phi_i^cohort|) > delta`.

Otherwise return `ABSTAIN_OPERATOR_DEPENDENT` or `ABSTAIN_UNRESOLVED_CREDIT`.

## Primary endpoints

For pooled, PROSE, and CODE strata independently:

- exact top-candidate agreement across K_TRAIN/K_COHORT >= 0.90;
- exact top-sign agreement across the two kernels >= 0.90;
- robust-authority coverage >= 0.50.

All three predicates must pass in PRIMARY and independently in REPLICATION.

Additional mandatory conditions:

- zero prompt-hash overlap with CSCA-05 prompt units;
- zero model-state mutation;
- no call may alter `Engine.generate`, logits, model weights, or sampling;
- all result-bearing artifacts checksum-bound.

## Diagnostics, not promotion criteria

Record:

- robust candidate distribution and `A_RECENT` fraction;
- number of robust non-recent cases;
- agreement of legacy ASCII_SPACE exact teacher with the robust family;
- credit-vector L1 distance between admissible kernels;
- physical forward calls and CPU wall time.

A recency-dominated positive does not establish architectural utility.

## Fail predicates

Any of the following gives `OPERATOR_FAMILY_ROBUSTNESS_NOT_QUALIFIED`:

- any PRIMARY stratum misses any 0.90 agreement threshold;
- any PRIMARY stratum has robust coverage <0.50;
- any REPLICATION stratum misses the same frozen gates;
- prompt overlap with CSCA-05 is nonzero;
- model state changes;
- result interpretation calls the two kernels a proven semantic intervention equivalence.

Replication cannot rescue PRIMARY.

## Promotion boundary

PASS may authorize only:

`DIRECT_INTERVENTION_OPERATOR_FAMILY_ROBUST_SHADOW_MEASUREMENT`.

PASS does **not** authorize semantic causality, graph truth, replay, amortized student credit, direct logit control, weight updates, or active causal control. A learned/amortized estimator receives a separate experiment ID only after this gate survives.
