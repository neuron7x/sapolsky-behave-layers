# COG-COUNTERMODEL-01R — Final Verification Record

**Scientific verdict:** `SET_VALUED_COUNTERMODEL_GUARD_QUALIFIED_SYNTHETIC_NARROWED`  
**Authority:** `COUNTERMODEL_SET_GUARD_ONLY`

## Immutable parent

`COG-COUNTERMODEL-01` remains `AUTONOMOUS_COUNTERMODEL_GENERATOR_NOT_QUALIFIED` because its frozen hidden-truth/Pareto recovery predicate failed:

- PRIMARY `32/64 = 0.50`;
- REPLICATION `41/64 = 0.640625`;
- required `>=0.95` in each cohort.

R1 used a new experiment ID, new preregistration commit, and fresh seeds.

## R1 confirmatory result

Fresh 64-seed PRIMARY and 64-seed independent REPLICATION cohorts were run for four synthetic families with 4096 factual rows/seed.

Every eligible family (`R0_VALID`, `R1_COORDINATED_EXCLUSION`, `R2_ALEATORIC_HIGH`) in both cohorts achieved:

- `ALL_REAL_BETA_UNDER_UNRESTRICTED_REPARAMETERIZATION`: `64/64`;
- materially distinct exact countermodel survival: `64/64`;
- finite diagnostic ambiguity diameter >=1.0: `64/64`;
- non-empty Pareto frontier: `64/64`;
- zero unconditional causal authority.

Worst Pareto-frontier factual path reconstruction error across all eligible confirmatory cells: `3.552713678800501e-15`.

For VALID and COORDINATED_EXCLUSION under the declared direct-effect L2 bound `0.15`, the analytic beta interval existed, remained narrower than the material displacement `0.40`, contained no materially shifted beta, and produced the assumption-conditional state in `64/64` seeds for each cohort/family.

Median widths:

- PRIMARY VALID `0.2890530497070867`;
- PRIMARY COORDINATED `0.2906719163516095`;
- REPLICATION VALID `0.2909056456568293`;
- REPLICATION COORDINATED `0.2904916680482502`.

The upstream-invalid regime-confounding family was refused `64/64` in both cohorts.

## Verification

PASS:

- `scripts/cog_countermodel01_gate.py --self-test`: `5/5` authority/truth-selection mutations killed;
- `scripts/cog_countermodel01_gate.py`;
- `scripts/csca08_gate.py --self-test`: `5/5` mutations killed;
- CSCA-08 gate;
- documentation gate: `63 claims / 63 hypotheses / 0 orphans`;
- verdict-binding self-test and gate;
- evidence semantic validation;
- `make -f Makefile.cwc verify-evidence`, including parent and R1 countermodel bundles;
- truth, research-ingestion, research-execution, research-ops, architecture, hermeticity, complexity, inference-integrity and technical-quality gates;
- focused countermodel/CSCA-08 tests: `24 passed`;
- full repository collection: `438 tests collected`, zero collection errors;
- `py_compile` on all new modules/runners/gate;
- `git diff --check`.

Not claimed:

- full behavioral repository pytest PASS was not run in this final verification;
- `mypy` and `ruff` are unavailable in the execution environment, so no new static-analysis PASS is claimed from those tools.

## Epistemic boundary

The qualified object is a **set-valued cognitive guard**. It can prove that multiple causal interpretations are observationally compatible inside the declared model class and can compute how an explicit structural assumption narrows that set. It cannot prove that the assumption is true, identify semantic causality on real traces, authorize replay control, active control, or architecture promotion.

Next hard gate: `COG-EPISTEMIC-01` — replace string-level authority states with a typed transition lattice so that illegal upgrades are impossible by construction.
