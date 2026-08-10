# Deferred Causal Credit — Program Execution Report

Date: 2026-08-10

## Implemented core

The repository now contains an executable deferred-causal-credit substrate:

`eligibility -> debt -> replay -> counterfactual evidence -> cross-context invariance -> consolidation gate`.

Observational association is explicitly non-authoritative. Positive causal credit
requires replay evidence across contexts; insufficient evidence, sign instability,
or low precision remains fail-closed.

## Iteration 1 — negative result preserved

`CAUSAL_DEBT_CONTROL_NOT_QUALIFIED`.

The first scheduler repeatedly spent replay budget on an observationally salient
spurious candidate even after zero-effect interventions. Aggregate invariant-cause
recall was 0.18, versus 0.48 for uniform-CF and 0.84 for RPE-CF. The result exposed
a first-principles defect: causal debt must be dischargeable by negative evidence.

The V1 protocol also contained an impossible strict-improvement false-credit gate
when both matched controls were already at the zero floor. This defect is documented
and not retroactively repaired.

## Iteration 2 — bounded positive synthetic control

A separately preregistered V2 added `resolution_aware_debt()` while retaining the V1
method unchanged. The new rule decays observational eligibility as interventions
accumulate and lets measured causal leverage dominate replay priority.

Frozen result over 20 seeds, 4 budgets and 2 SCM environments:

- mean paired OOS vs uniform-CF: +0.16650390625;
- mean paired OOS vs RPE-CF: +0.193157958984375;
- exact max-T FWER p: 1.9073486328125e-06 / 9.5367431640625e-07;
- aggregate invariant-cause recall: 0.85625 vs 0.4375 / 0.36875;
- false-credit rate: 0 for all matched-CF policies;
- benign proxy median OOS matched the RPE control;
- adversarial descendant environment beat RPE at 4/4 frozen budgets.

Verdict: `CAUSAL_DEBT_V2_CONTROL_QUALIFIED` — synthetic control only.

## Mechanism ablation

Exploratory only; no claim-upgrade authority.

- debt + balanced contexts mean OOS: 0.83268;
- debt + random contexts: 0.82501;
- uniform + random contexts: 0.65962;
- RPE + random contexts: 0.65070.

Exploratory contrasts:

- resolution-aware debt vs uniform under random contexts: +0.16539;
- resolution-aware debt vs RPE under random contexts: +0.17432;
- balanced-context contribution inside debt condition: +0.00767.

This suggests the dominant effect is the corrected debt scheduler rather than the
least-covered-context heuristic, but this attribution is post-confirmatory.

## Robustness sweep

Exploratory 16-setting descendant sweep over acquisition size, outcome noise and
spurious-observation noise at matched replay budget 16. V2 had higher mean OOS than
each matched control in 15/16 settings. Non-superiority settings are retained:

- n=256, outcome noise 0.05, spurious noise 0.10: RPE-CF > V2;
- n=256, outcome noise 0.10, spurious noise 0.10: uniform-CF exceeds V2 by ~4.9e-5.

Therefore the scheduler is not universally dominant.

## Verification

- causal-debt gate: PASS;
- VIA gate: PASS with scientific ascension still blocked at VIA-V1;
- architecture/hermeticity/complexity/inference-integrity: PASS;
- doc gate: 49 claims / 49 hypotheses / 0 orphans;
- verdict-binding self-test: 4 injected defects detected;
- verdict-binding: 47 sealed bindings + 2 NOT_TESTED;
- evidence validation: PASS;
- causal-debt + VIA focused suite: 71 PASS;
- broad environment-available suite: 270 PASS, 23 SKIP; mutation meta-test remains
  environment-blocked because `hypothesis` is missing;
- full pytest collection remains blocked by missing `rustbpe`, `tomli`, `hypothesis`,
  and `pyarrow` in this execution environment.

## Scientific boundary

What is now supported: a computational mechanism can defer credit, use intervention
evidence to discharge spurious observational debt, and improve replay allocation in
a controlled synthetic regime-shift benchmark.

What is not supported: that brains implement this mechanism; that hippocampal replay
performs counterfactual falsification; that the method improves a real LM; that it
saves inference compute; or that it authorizes VIA ascension.

## Next admissible experiment

The next step is not another synthetic scheduler. It is a prospective real-model
memory/replay pilot with immutable candidate IDs, matched replay budgets, raw
pre-consolidation outcomes, regime shifts, and a physical replay-cost ledger. The
current synthetic positive result is sufficient to justify such a pilot, not to
claim the pilot will succeed.
