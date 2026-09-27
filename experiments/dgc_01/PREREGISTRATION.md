# DGC-01 Preregistration — Synthetic Oracle Compute Governance

**Status:** preregistered design; `NOT_TESTED`.  
**Primary hypothesis:** `DGC-H1`.  
**No result may alter this document after first execution without a dated protocol amendment.**

## Research question

Can a decision-relevant value-of-computation governor allocate a fixed inference budget better than fixed compute, uncertainty gating, and cost/quality routing on a synthetic environment with known ground truth?

## Arms

- `B0_FIXED`: fixed number/type of cognition operations.
- `B1_UNCERTAINTY`: additional compute triggered by preregistered uncertainty threshold.
- `B2_COST_QUALITY_ROUTER`: learned or rule-based cost/quality routing baseline with matched observable features and budget.
- `B3_DGC`: counterfactual-regret + conservative VOC compute admission.

All arms receive the same task set, action set, tools, total hard budget and scoring function. No arm receives oracle state except the evaluator.

## Frozen regimes

- A — high uncertainty, action invariant;
- B — low uncertainty, near decision boundary;
- C — high uncertainty, high consequence;
- D — structurally different worlds, same optimal action;
- E — low-probability / high-regret reversal.

The generator MUST include both positive and negative cases for "more compute is valuable". Task labels are hidden from governors.

## Primary endpoint

`NetDecisionValue = DecisionUtility - lambda_compute * TotalComputeCost`

`lambda_compute` and the utility scale MUST be frozen before execution. The primary comparison is `B3_DGC - max(B0,B1,B2)` on held-out tasks.

## Secondary endpoints

- decision accuracy;
- realized regret;
- catastrophic/worst-case regret;
- false-stop rate;
- false-escalation rate;
- abstention rate and task coverage;
- tokens input/output;
- wall time;
- API/tool/retrieval calls;
- GPU seconds where measurable;
- estimated monetary cost;
- `CostPerCorrectDecision`;
- calibration of predicted compute-worthwhile probability / observed reversal where that probability is explicitly modeled.

## Oracle diagnostics

For each task the true world and outcome of each legal diagnostic/computation are known to the evaluator. Compute:

- `OracleComputeValue(c|s)`;
- estimated `VOC(c|s)`;
- ranking agreement;
- false-stop / false-escalation;
- regret due specifically to governor admission errors.

AUROC MAY be reported for the binary oracle label `OracleVOC > 0`, but it is secondary and MUST NOT replace the primary utility endpoint.

## Sequential inference

The first confirmatory run MUST use either:

1. a frozen i.i.d. perturbation draw process with a time-uniform confidence sequence valid for bounded regret; or
2. a separately justified e-process/martingale confidence sequence valid under the actual adaptive perturbation policy.

A fixed-n CI reused after optional stopping is prohibited.

## Anti-gaming controls

Fail the run if any arm can improve score by:

- abstaining selectively without coverage penalty;
- mutating the utility function or cost meter;
- using evaluator/oracle labels;
- moving compute into an unmetered subsystem;
- dropping high-cost cases from denominator;
- reusing invalidated evidence;
- leaking task family/seed labels.

## Decision rule

`EXPERIMENTALLY_SUPPORTED` only if the preregistered uncertainty interval for the primary difference excludes zero in favor of DGC **and** coverage/catastrophic-regret guardrails do not fail.

Otherwise record `NOT_SUPPORTED` or `SUPPORTED_NARROWED`; no endpoint substitution and no post-hoc threshold tuning may promote the result.
