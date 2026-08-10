# ACT-R&D-03 — UNCERTAINTY-AWARE COUNTERFACTUAL INFERENCE QUALIFICATION

**CLASS:** Research Mechanism → Runtime Inference Boundary
**MODE:** FAIL-CLOSED · SELECTIVE-INFERENCE · ABSTENTION-FIRST · NO SILENT AUTHORITY
**PRECONDITION:** `ACT-R&D-02 = PASS_WITH_BOUNDARIES`
**CURRENT AUTHORITY:** `RESEARCH_ONLY`
**TARGET AUTHORITY:** `SHADOW_INFERENCE_QUALIFIED`

---

# 1. CENTRAL PROBLEM

CSCA-01 established:

```
correct counterfactual model
→ exact counterfactual operator
→ correct structural credit

```

CSCA-01A established:

```
wrong counterfactual model
→ exact counterfactual operator
→ precisely wrong structural credit

```

Therefore:

[
\text{Credit validity}
\le
\text{Counterfactual-model validity}
]

The next research target is **not a more accurate Shapley estimator**.

The next target is:

> determine when the system has enough epistemic authority to issue causal credit, and force it to abstain everywhere else.

---

# 2. PRIMARY INVARIANT

No causal estimate may affect runtime behavior unless:

```
MODEL_SUPPORT
AND UNCERTAINTY_CALIBRATED
AND INTERVENTION_SUPPORTED
AND CROSS_MODEL_STABLE
AND OOD_RISK_ACCEPTABLE
AND CREDIT_SEPARATION_RESOLVED

```

Otherwise:

```
ABSTAIN

```

`ABSTAIN` is a successful inference state, not an error.

---

# 3. REQUIRED DECISION SPACE

The causal layer must return exactly one epistemic state:

```
ACCEPT_CAUSAL_CREDIT
ABSTAIN_UNCERTAIN_MODEL
ABSTAIN_OOD
ABSTAIN_INSUFFICIENT_INTERVENTION_SUPPORT
FALSIFIED_NO_LEVERAGE
OBSERVATIONAL_ONLY

```

There must be no implicit conversion:

```
UNKNOWN → CAUSAL

```

---

# 4. P0 — CLOSE EXECUTION-HERMETICITY DEBT

Before any new experiment:

## Required fix

A clean unpacked repository must execute:

```
python scripts/research_ops_gate.py

```

without:

```
PYTHONPATH=.
editable install
shell-specific environment state
developer workstation state

```

Required invariant:

```
CLEAN_ARCHIVE
→ COMMAND
→ SAME_GATE_RESULT

```

Add a clean-tree CI test that:

1. copies repository into a temporary directory;
2. removes caches and local virtual-environment assumptions;
3. executes research gates from that copy;
4. fails on import-path dependence.

## Dependency boundary

Resolve or explicitly isolate:

```
rustbpe
tomli
hypothesis
pyarrow

```

Full test collection must become executable before inference promotion.

**Gate:**

```
P0_HERMETIC_EXECUTION = PASS

```

or ACT-R&D-03 stops.

---

# 5. BUILD `CounterfactualPredictionEnvelope`

A counterfactual model must never return only:

```
prediction = y_hat

```

It must return an evidence envelope containing:

```
prediction
epistemic_uncertainty
aleatoric_uncertainty
training_support
intervention_support
ood_score
model_family
model_version
data_version

```

No scalar `confidence` field is sufficient.

Different uncertainty sources must remain separately inspectable.

---

# 6. STRUCTURAL UNCERTAINTY, NOT ONLY PARAMETER UNCERTAINTY

A bootstrap ensemble of the same wrong architecture can be:

```
precisely wrong

```

Therefore uncertainty must attack at least:

```
PARAMETER uncertainty
DATA uncertainty
MODEL-FAMILY uncertainty
STRUCTURAL uncertainty
CONTEXT/OOD uncertainty
INTERVENTION-SUPPORT uncertainty

```

The system must explicitly test the failure case:

```
all ensemble members share the same wrong edge

```

If all models confidently agree on the wrong causal structure and the uncertainty mechanism does not detect the failure:

```
UNCERTAINTY_GATE_NOT_QUALIFIED

```

This null is mandatory.

---

# 7. EXPERIMENT — `CSCA-02-UA`

**Name:** Counterfactual Uncertainty & Abstention Qualification

## Objective

Determine whether uncertainty-aware abstention prevents model misspecification from becoming false causal authority.

## Ground truth

Use synthetic SCM families where the evaluator knows the true graph but the learned counterfactual model does not.

The credit system receives only the learned model.

---

# 8. MISSPECIFICATION MATRIX

Generate independent environment families containing:

```
M0 CORRECT_STRUCTURE
M1 SPURIOUS_EDGE
M2 MISSING_TRUE_EDGE
M3 WRONG_COEFFICIENT
M4 SIGN_ERROR
M5 NONLINEAR_INTERACTION
M6 REDUNDANT_CAUSES
M7 SYNERGISTIC_CAUSES
M8 VARIABLE_DELAY
M9 LATENT_CONFOUNDER_SHIFT
M10 CONTEXT_DEPENDENT_CAUSALITY
M11 SHARED_MODEL_CLASS_MISSPECIFICATION

```

Training and evaluation graph families must be separated before execution.

No estimator may see held-out structural families during threshold calibration.

---

# 9. COUNTERFACTUAL MODEL FAMILY

Do not select one model and declare it canonical.

Compare at minimum:

```
simple structural model
nonlinear learned model
bootstrap/ensemble model
heterogeneous model-family ensemble

```

The purpose is not leaderboard performance.

The question is:

> Which uncertainty surface predicts when causal credit itself is unsafe?

---

# 10. CREDIT DISTRIBUTION

For candidate (i), each admissible counterfactual model (m) produces:

[
\phi\_i^{(m)}
]

The system derives:

[
\mu\_i = E\_m[\phi\_i^{(m)}]
]

and an uncertainty interval:

[
[L\_i,U\_i]
]

Do not collapse this immediately to a point estimate.

Also record:

```
sign_stability_i
rank_stability_i
model_disagreement_i
context_stability_i

```

---

# 11. ABSTENTION RULE

Let (i^\*) be the candidate with highest provisional credit.

Authority is allowed only when:

[
L\_{i^*} >*
*\max\_{j\neq i^*} U\_j + \delta
]

and simultaneously:

```
calibration_valid = true
OOD_gate = PASS
intervention_support = PASS
model_adequacy_gate = PASS

```

(\delta) is frozen from a calibration partition before confirmatory evaluation.

It may not be tuned after observing test outcomes.

If the intervals overlap:

```
ABSTAIN_UNRESOLVED_CREDIT

```

---

# 12. PRIMARY METRIC

Do **not** use ranking accuracy as the primary metric again.

Primary:

```
SELECTIVE_FALSE_CAUSAL_AUTHORITY

```

Definition:

> probability that the system issues non-abstained causal authority to an incorrect candidate.

Secondary metrics:

```
coverage
causal_rank_accuracy_given_accept
false_credit_mass_given_accept
abstention_rate
calibration_error
OOD detection performance
credit interval width
structural evaluations
wall-clock cost

```

The safety metric and coverage must always be reported together.

Otherwise:

```
ABSTAIN_ALWAYS

```

would appear optimal.

---

# 13. NULL ATTACKS

Mandatory:

```
NULL-01 zero causal effect
NULL-02 correlation-only
NULL-03 destroyed true link
NULL-04 spurious structural edge
NULL-05 common wrong structure across entire ensemble
NULL-06 unseen causal topology
NULL-07 factual fit good / causal model wrong
NULL-08 high observational association / zero intervention effect
NULL-09 intervention outside training support
NULL-10 context sign inversion

```

The most important attack is:

```
FACTUAL_PREDICTION_GOOD
+
COUNTERFACTUAL_STRUCTURE_WRONG

```

because low factual loss must never be treated as proof of causal adequacy.

---

# 14. QUALIFICATION RULE

`CSCA-02-UA` receives:

```
UNCERTAINTY_AWARE_CREDIT_QUALIFIED

```

only if all conditions hold:

```
1. false causal authority decreases relative to no-abstention;
2. accepted cases retain causal discrimination;
3. coverage is non-degenerate;
4. zero-cause nulls do not receive causal authority;
5. spurious-edge attacks trigger abstention or correct rejection;
6. held-out structural OOD does not silently create confident wrong credit;
7. result replicates on frozen independent seeds;
8. thresholds were frozen before confirmatory evaluation.

```

If uncertainty merely tracks prediction error but misses structural causal error:

```
UNCERTAINTY_MODEL_NOT_CAUSALLY_ADEQUATE

```

Store as ruin.

---

# 15. DO NOT INTEGRATE INTO TOKEN SAMPLING

Even after `CSCA-02-UA PASS`, do **not** modify:

```
logits
temperature
top_k
token sampling
model weights

```

The first real inference exposure must be observational.

---

# 16. INFERENCE STAGE I — SHADOW MODE

Add an immutable observer around the existing inference path:

```
nanochat.engine.Engine.generate

```

The causal subsystem may receive:

```
prompt/context identity
generated prefix
candidate events
logit-derived observables
runtime context

```

but its output cannot modify generation.

Required architecture:

```
BASE INFERENCE
      │
      ├────────────→ normal output
      │
      └────────────→ InferenceTrace
                         ↓
                  causal sidecar
                         ↓
                 ACCEPT / ABSTAIN
                         ↓
                    audit log

```

Any causal-sidecar failure must leave base inference unchanged.

---

# 17. `InferenceTrace`

Every shadow inference record must bind:

```
run_id
model_commit
checkpoint_hash
tokenizer_hash
prompt_hash
generation_seed
sampling_parameters
candidate_ids
counterfactual_model_version
credit_estimator_version
uncertainty_state
abstention_reason
runtime telemetry

```

No untraceable causal decision.

---

# 18. REAL-MODEL PILOT — `CWC-INF-01`

Purpose:

> establish whether counterfactual credit contains useful information on an actual model inference trace without granting it runtime control.

Use controlled internal interventions only.

Examples:

```
remove context segment
replace semantic span
mask candidate memory item
remove replay candidate
perturb controlled internal feature where intervention semantics are explicit

```

Do not label an intervention as causal unless the manipulated variable is exactly specified.

---

# 19. REAL-MODEL OUTCOME

For each intervention measure effects on predeclared runtime quantities such as:

```
next-token distribution divergence
sequence loss
selected tool/action
memory retrieval decision
routing decision

```

Do not simultaneously search many outcomes and promote whichever becomes significant.

Primary outcome must be preregistered.

---

# 20. IMPORTANT SEMANTIC BOUNDARY

`CWC-INF-01` may establish:

> changing internal/input variable X changes model behavior Y.

It does **not** establish:

```
human cognitive causality
real-world semantic causality
biological mechanism

```

The causal domain is initially:

```
THIS MODEL
THIS INTERVENTION
THIS RUNTIME
THIS MEASURED OUTCOME

```

---

# 21. INFERENCE STAGE II — REPLAY GOVERNOR

Only after shadow qualification may causal credit influence:

```
which unresolved candidate receives offline replay compute

```

It still may not modify immediate token generation.

Allowed transition:

```
credit envelope
→ uncertainty gate
→ replay priority

```

Forbidden:

```
credit envelope
→ direct logit manipulation

```

This makes the first architecture intervention:

```
reversible
bounded
observable
non-destructive

```

---

# 22. COMPARE AGAINST CURRENT MECHANISM

At fixed counterfactual-compute budget compare:

```
UNCERTAINTY_AWARE_CF_CREDIT
RESOLUTION_AWARE_DEBT
RPE_PROXY
RECENCY
UNCERTAINTY_ONLY
UNIFORM
RANDOM

```

Primary question:

> Does uncertainty-aware causal credit resolve the correct causal candidate faster without increasing false consolidation?

Not:

> Does it produce prettier attribution scores?

---

# 23. VALUE FUNCTION

Measure runtime utility as a vector:

[
\mathbf U =
(
\text{causal resolution},
-\text{false authority},
-\text{compute},
-\text{latency},
-\text{memory},
\text{coverage}
)
]

Do not collapse it into one scalar until trade-off weights are preregistered.

Use Pareto comparison first.

---

# 24. PHYSICAL COMPUTE VALIDATION

After real-model shadow/replay qualification, run on actual target hardware.

Measure:

```
baseline inference latency
instrumented inference latency
p50
p95
p99
counterfactual evaluations/request
CPU RAM
GPU VRAM
GPU time
energy if NVML measurement is available
tokens/second

```

All numbers must come from runtime telemetry.

No extrapolated hardware claims.

The overhead budget is frozen from a baseline SLO **before** enabling the causal layer.

---

# 25. FAIL-CLOSED LATENCY CONTROL

Inference must have a hard compute budget.

If counterfactual evaluation exceeds the request budget:

```
ABSTAIN_COMPUTE_BUDGET

```

Never:

```
continue calculating indefinitely

```

Inference latency is part of correctness.

---

# 26. REQUIRED MODULE BOUNDARIES

Create isolated components:

```
cwc/counterfactual/
    model.py
    uncertainty.py
    adequacy.py

cwc/credit/
    estimator.py
    envelope.py

cwc/inference/
    trace.py
    abstention.py
    shadow_observer.py

cwc/replay/
    causal_governor.py

```

Research experiment code must not become runtime implementation by direct import.

Promote through a separately tested production module.

---

# 27. REQUIRED TEST SURFACES

```
test_counterfactual_uncertainty.py
test_structural_misspecification.py
test_abstention_gate.py
test_zero_cause_authority.py
test_ood_abstention.py
test_shadow_mode_noninterference.py
test_inference_trace_binding.py
test_compute_budget_abstention.py
test_replay_governor.py
test_clean_archive_execution.py

```

Critical invariant:

```
SHADOW MODE ON
vs
SHADOW MODE OFF

```

must produce identical base-generation outputs under identical seeds.

---

# 28. MUTATION TARGETS

Mutation tests must attempt to:

```
ABSTAIN → ACCEPT
UNKNOWN → CAUSAL
OOD_FAIL → PASS
false-credit threshold bypass
remove uncertainty check
remove intervention-support check
rewrite verdict
rewrite evidence hash
allow shadow observer to mutate logits

```

Every mutation must be killed.

---

# 29. PROMOTION LADDER

```
RESEARCH_ONLY
↓
UNCERTAINTY_QUALIFIED
↓
SHADOW_INFERENCE_QUALIFIED
↓
REAL_MODEL_REPLAY_QUALIFIED
↓
PHYSICAL_COMPUTE_QUALIFIED
↓
H5_INFERENCE_ADVISORY_REVIEW

```

Not yet permitted:

```
ACTIVE_CAUSAL_CONTROL

```

That requires a later act.

---

# 30. REQUIRED ARTIFACTS

Produce:

```
11_COUNTERFACTUAL_MODEL_REGISTRY.yaml
12_UNCERTAINTY_CALIBRATION.json
13_ABSTENTION_POLICY.yaml
14_CSCA_02_PREREGISTRATION.md
15_CSCA_02_RESULTS.json
16_STRUCTURAL_MISSPECIFICATION_MATRIX.csv
17_INFERENCE_TRACE_SCHEMA.json
18_REAL_MODEL_REPLAY_PREREGISTRATION.md
19_PHYSICAL_COMPUTE_REPORT.json
20_INFERENCE_PROMOTION_DECISION.md

```

All result-bearing artifacts checksum-bound.

---

# 31. THE CENTRAL KILL QUESTION

The entire next act is reduced to one question:

> **Can the system reliably know when its own counterfactual model is too uncertain or structurally unsupported to issue causal authority?**

If no:

```
Shapley remains OFFLINE_ORACLE_ONLY

```

If yes:

```
causal credit becomes candidate inference primitive

```

Only then test whether it improves real-model replay.

---

# 32. FINAL GATE

`ACT-R&D-03 = PASS` only if:

```
clean archive is hermetic;
full relevant test collection executes;
model uncertainty is represented explicitly;
structural misspecification is attacked;
abstention is calibrated prospectively;
false causal authority is measured directly;
zero-cause nulls survive;
held-out causal topology is tested;
shadow mode cannot mutate inference;
real-model pilot remains bounded to model-internal causality;
physical compute is measured;
architecture authority remains human-gated.

```

Otherwise:

```
PASS_WITH_BOUNDARIES
or
FAIL

```

never silent promotion.

---

# EXECUTION ORDER

```
P0  FIX CLEAN-TREE HERMETICITY
↓
P1  FREEZE H4 FOR CSCA-02-UA
↓
P2  BUILD UNCERTAINTY ENVELOPE
↓
P3  BUILD ABSTENTION GATE
↓
P4  ATTACK STRUCTURAL MISSPECIFICATION
↓
P5  CONFIRMATORY CSCA-02-UA
↓
P6  SHADOW-MODE REAL INFERENCE
↓
P7  REAL-MODEL OFFLINE REPLAY PILOT
↓
P8  PHYSICAL COMPUTE VALIDATION
↓
P9  H5 INFERENCE PROMOTION REVIEW

```

**NEXT HARD GATE:**
`CSCA-02-UA — Counterfactual Model Uncertainty, Structural Misspecification & Abstention`.

**CURRENT EVAL:** `PASS_WITH_BOUNDARIES`.

**INFERENCE AUTHORITY:** `BLOCKED`.

**REASON:** causal-credit operator is qualified only conditional on model adequacy; the system does not yet possess a verified mechanism for knowing when that condition is violated.