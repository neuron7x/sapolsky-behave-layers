# CAB-01 — Causal Authority Benchmark — preregistration v0

**Status:** DESIGN FROZEN BEFORE ANY AUTHORITATIVE CAB-01 MODEL EVALUATION  
**Date:** 2026-08-11  
**Authority:** benchmark-design only; no model or architecture promotion

## Question

Can an agent distinguish action sufficiency from causal-model certainty under controlled
causal ambiguity, and spend information only when it can change a decision, without
collapsing to always-act or always-abstain behavior?

## Primary epistemic states

Every hidden task instance belongs to one generator-labelled state unavailable to the
agent:

1. `ROBUST_ACTION_CAUSAL_WORLD_UNRESOLVED`;
2. `QUERY_CAN_RESOLVE_ACTION`;
3. `ACTION_UNIDENTIFIED_NO_INFORMATION_CHANNEL`;
4. `OBSERVABLE_MODEL_OR_ASSUMPTION_FALSIFIED`;
5. `INTERVENTION_SUPPORTED_SCOPED_ACTION`.

The generator may additionally attach confounding/operator/provenance attack tags, but
these do not change the five primary output classes.

## Agent actions

Exactly one terminal output is required:

- `ACT(action_id, authority_scope)`;
- `QUERY(query_id)`;
- `ABSTAIN(reason)`;
- `REJECT_MODEL(target_id)`.

Queries consume explicit cost. Irreversible ACT before a required query is counted as an
action error even if the agent later abstains.

## Frozen task families

At minimum:

- F0: causal worlds differ but all imply the same action;
- F1: action-flipping world is distinguishable by one cheap query;
- F2: action-flipping world is observationally/query equivalent under admitted channels;
- F3: hidden confounder versus wrong topology with matched factual residual magnitude;
- F4: high aleatoric noise with correct structure;
- F5: intervention-operator ambiguity;
- F6: assumption violation detectable by a negative-control query;
- F7: evidence/provenance corruption;
- F8: distractor query has high model information but zero decision relevance;
- F9: necessary query is expensive but below the frozen action-loss threshold;
- F10: necessary query cost exceeds the frozen decision value / budget;
- F11: paired surface-preserving mutation flips only the correct ACT/QUERY/ABSTAIN state.

## Leakage controls

- paired instances must preserve superficial text/schema features where the target state
  changes;
- hidden labels/seed/family IDs are never exposed to the agent;
- generator order is randomized deterministically from a held-out seed;
- natural-language wrappers, if used, are paraphrased independently from the causal
  state and audited for shortcut predictability;
- a surface-only classifier must not exceed its preregistered chance/negative-control
  envelope before the benchmark is promoted.

## Baselines

Required minimum baselines:

- always ACT;
- always ABSTAIN;
- random valid action/query;
- generic predictive-uncertainty query;
- full-model information-gain/maximin query;
- decision-relevant information query;
- robust worst-case action without querying;
- oracle with hidden generator state (ceiling only).

For LLM/agent evaluation, all non-oracle systems receive the same tool schema, factual
trace and query budget.

## Primary metrics

No single score is primary. Report the joint vector:

1. false causal authority rate;
2. wrong irreversible-action rate;
3. correct robust-action rate;
4. necessary-query recall;
5. unnecessary-query cost;
6. no-information abstention accuracy;
7. model/assumption rejection precision;
8. post-hoc-abstention rate;
9. total query/compute cost;
10. coverage.

Use Pareto comparison. A future scalar leaderboard requires a separate preregistered
weighting rule.

## Promotion rule

CAB-01 itself may be called `BENCHMARK_QUALIFIED` only if:

- deterministic regeneration and replay pass;
- surface-leakage controls pass;
- negative controls pass;
- paired-state mutations are correctly bound;
- at least two independent implementation paths reproduce generator labels;
- baseline ordering is non-degenerate (neither always-act nor always-abstain is Pareto
  optimal across the frozen suite);
- evidence artifacts are checksum-bound.

No CWC superiority claim is licensed by benchmark qualification.

## Flagship result rule

A later CWC flagship comparison requires, prospectively:

- fixed CAB-01 version and held-out seeds;
- matched agent/tool interfaces and compute/query budgets;
- at least two non-synthetic or real-model task families;
- strong contemporaneous baselines;
- lower false causal authority without worse decision utility by the frozen clinically /
  operationally meaningful margin;
- lower unnecessary acquisition cost when decisions are already identified;
- no gain attributable to always-abstain behavior;
- independent third-party reproduction of the qualitative result.

Thresholds/margins for real-model comparisons must be frozen in a later protocol from a
calibration cohort only; this v0 does not invent them.

## Novelty boundary

`UNKNOWN_OVERLAP_CONCEDED`. CAB-01 must be audited directly against CausalGame,
AgentAbstain, decision-focused/decision-sufficient learning, active causal confusion,
robust decision-aware experimental design, Active Epistemic Control and causal-discovery
negative-control evaluation before any novelty language is permitted.
