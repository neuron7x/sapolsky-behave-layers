# CSCA-02-UA — Counterfactual Model Uncertainty, Structural Misspecification & Abstention

**Status:** FROZEN BEFORE IMPLEMENTATION/EXECUTION  
**Act:** ACT-R&D-03  
**Authority target:** `UNCERTAINTY_QUALIFIED` only. A PASS does not authorize active inference control.

## Question

Can a counterfactual-credit system detect when its learned counterfactual model is structurally unsupported and abstain before wrong model structure becomes false causal authority?

## Epistemic states

The implementation must emit one state per evaluation case:

- `ACCEPT_CAUSAL_CREDIT`
- `ABSTAIN_UNCERTAIN_MODEL`
- `ABSTAIN_OOD`
- `ABSTAIN_INSUFFICIENT_INTERVENTION_SUPPORT`
- `ABSTAIN_UNRESOLVED_CREDIT`
- `FALSIFIED_NO_LEVERAGE`
- `OBSERVATIONAL_ONLY`

`ABSTAIN_UNRESOLVED_CREDIT` is included because ACT-R&D-03 section 11 explicitly requires it when credit intervals overlap.

## Data and structural-family split

The synthetic evaluator knows the true SCM; the counterfactual subsystem never receives the graph label.

Calibration structural families (threshold selection only):

- `M0_CORRECT_STRUCTURE`
- `M1_SPURIOUS_EDGE`
- `M2_MISSING_TRUE_EDGE`
- `M3_WRONG_COEFFICIENT`
- `M4_SIGN_ERROR`
- `M5_NONLINEAR_INTERACTION`
- `N0_ZERO_CAUSE`

Held-out confirmatory structural families (never used to choose thresholds):

- `M6_REDUNDANT_CAUSES`
- `M7_SYNERGISTIC_CAUSES`
- `M8_VARIABLE_DELAY`
- `M9_LATENT_CONFOUNDER_SHIFT`
- `M10_CONTEXT_DEPENDENT_CAUSALITY`
- `M11_SHARED_MODEL_CLASS_MISSPECIFICATION`
- `N0_ZERO_CAUSE` as a mandatory repeated null, with disjoint seeds.

Frozen cohorts:

- CALIBRATION seeds: `31000..31031`
- PRIMARY HELD-OUT seeds: `41000..41031`
- INDEPENDENT REPLICATION seeds: `51000..51031`

Per case:

- 256 observational training rows;
- 64 paired intervention-support rows per candidate;
- 128 evaluation rows;
- candidates: `A,C,D,B`.

## Counterfactual model ensemble

Fit, without ground-truth graph access:

1. linear main-effects models;
2. context-interaction models;
3. nonlinear pairwise-interaction models;
4. bootstrap variants of each family.

The ensemble must retain family identity. Parameter/data uncertainty and model-family/structural uncertainty must be reported separately.

`M11_SHARED_MODEL_CLASS_MISSPECIFICATION` must inject the same wrong structural edge into every model after fitting. Model disagreement alone is therefore expected to fail; the intervention adequacy check must catch the shared error.

## Counterfactual credit

For each model, exact Shapley credit over the four binary candidate variables is computed analytically from the fitted polynomial basis under a symmetric Rademacher intervention baseline. Each candidate receives a model-distribution of signed and absolute credit.

The credit envelope stores mean, lower/upper interval, sign stability, rank stability, model-family disagreement and context stability. No single scalar confidence field is permitted.

## Intervention adequacy

Intervention-support observations are paired `do(X=-1)` / `do(X=+1)` outcomes with shared exogenous state. They are not used as direct ground-truth labels for credit ranking. They are used only to test whether the learned model predicts held-out intervention effects within a calibrated error budget.

Insufficient support must force abstention.

## Calibration policy

Thresholds are selected on CALIBRATION only by a deterministic grid search.

Candidate policies vary:

- credit-separation margin `delta`;
- maximum normalized intervention-prediction error;
- maximum model disagreement;
- minimum rank stability;
- maximum OOD surprisal;
- minimum intervention support (fixed at 32 paired probes/candidate).

The selected policy is the highest-coverage policy satisfying ALL calibration constraints:

1. selective false causal authority `<= 0.025`;
2. causal-rank accuracy given accept `>= 0.95`;
3. `N0_ZERO_CAUSE` acceptance count `= 0`;
4. coverage `>= 0.20`.

Tie-break order: lower false authority → lower accepted false-credit mass → lower compute complexity → lexical parameter order.

The selected policy and its SHA-256 are frozen before PRIMARY execution. No policy change after primary outcomes are observed.

## Primary metric

`SELECTIVE_FALSE_CAUSAL_AUTHORITY` = fraction of all cases in which the selective system emits `ACCEPT_CAUSAL_CREDIT` for a candidate outside the evaluator's true causal set.

It is always reported with coverage.

Comparator: `NO_ABSTENTION_MEAN_CREDIT`, which always chooses the candidate with largest mean ensemble credit.

## Secondary metrics

- coverage;
- causal-rank accuracy given accept;
- false-credit mass given accept;
- abstention-state distribution;
- intervention calibration error;
- OOD score;
- credit interval width;
- model disagreement;
- structural evaluations;
- wall-clock cost.

## Mandatory null attacks

The experiment must explicitly cover:

- zero causal effect;
- correlation-only signal;
- destroyed true link;
- spurious structural edge;
- common wrong structure across the entire ensemble;
- unseen causal topology;
- factual fit good while counterfactual structure is wrong;
- high observational association with zero intervention effect;
- insufficient intervention support;
- context sign inversion.

## Confirmatory qualification rule

`UNCERTAINTY_AWARE_CREDIT_QUALIFIED` only if PRIMARY and INDEPENDENT REPLICATION both satisfy:

1. selective false causal authority is strictly lower than no-abstention;
2. selective false causal authority `<= 0.05`;
3. causal-rank accuracy given accept `>= 0.90`;
4. coverage `>= 0.20`;
5. zero-cause acceptance count `= 0`;
6. all `M11_SHARED_MODEL_CLASS_MISSPECIFICATION` cases either abstain or reject leverage;
7. no held-out structural family produces false-authority rate `> 0.10`;
8. the frozen policy hash matches the calibration artifact;
9. independent replication has the same PASS/FAIL decision.

If factual prediction is good but structural error survives as confident false authority, verdict is `UNCERTAINTY_MODEL_NOT_CAUSALLY_ADEQUATE`.

## Failure boundary

A PASS is synthetic mechanism qualification only. It does not establish paper reproduction, biological equivalence, real-LM utility, physical compute savings, replay utility, or active causal control.
