# CWC Statistical Analysis Plan (SAP)

Project-wide statistical rules. Binds every confirmatory experiment. Reflects the
methods actually used in the shipped experiments (paired seeds, bootstrap CIs,
worst-seed reporting).

## Estimand & unit
- Primary estimand per claim is declared in its hypothesis (`HYPOTHESIS_REGISTRY.yaml`).
- **Statistical unit = model seed**, paired across compared systems. Tokens of one run
  are NOT independent units.
- Seed streams are separated: `model_seed`, `data_seed`, `evaluation_seed`,
  `router_seed`, `bootstrap_seed`.

## Confirmatory design
- Pilot seeds are **excluded** from confirmatory inference.
- Minimum **8 paired model seeds** (shipped experiments use 8).
- Real evaluation corpora ≥ 5 is REQUIRED for real-workload claims (`NOT_TESTED` today).
- Paired systems share data order, token budget, checkpoint rule, and
  hyperparameter-search budget.

## Inference
- Paired comparison of the primary metric; **flat paired bootstrap with the seed as
  the resampling unit** for CIs (the synthetic benchmarks have no corpus/example
  hierarchy to resample, so the unit is the seed); fixed `bootstrap_seed` for
  determinism. As implemented: `analyze_r3c_reinforce.py` resamples over seeds;
  `analyze_surface_matched.py` reports the per-seed paired arms directly (no
  resampling). A hierarchical seed→corpus→example bootstrap is reserved for a future
  real-workload evaluation where those levels exist.
- Report **median, dispersion (MAD), 95% CI, and worst-seed** result — never best seed.
- Report **collapse probability** and separate **conditional vs unconditional** utility.

## Thresholds
- `alpha = 0.05`, target **power ≥ 0.80**, minimum detectable effect declared in the
  protocol **before** the run.
- Decision uses the CI bound, not the point estimate (e.g. paired diff 95% upper bound
  `< 0`, AUROC lower bound `> 0.5`).

## Power & sample size
See `POWER_AND_SAMPLE_SIZE_PLAN.md`. For synthetic mechanism experiments the effect
sizes are large and near-deterministic (e.g. Jensen gap error 0.0000), so 8 seeds is
amply powered; real-workload claims require a pre-run power analysis.

## Multiplicity & data handling
- Primary hypotheses are few and preregistered; secondary comparisons use Holm
  correction.
- Test set is never used for threshold selection (validation only).
- Failed-run and missing-data policies are declared per protocol; all exclusions are
  reported.
