# CSCA-06 — Final Verification and Seven-Phase Decision Record

**Date:** 2026-08-10  
**Programme status:** `PASS_WITH_BOUNDARIES`  
**Broad causal authority:** BLOCKED  
**Student/replay/active control:** BLOCKED

## Phase 1 — Identifiability before inference

Implemented a composite intervention-model representation with explicit nuisance envelope. The central correction is that there is no universal scalar threshold `I(M;do(X))` that proves graph falsity. The operational design object is

`D_M(d) = inf_{Q in P_M} KL(P_*^d || Q^d)`

and its cost-normalized rate

`R_M(d) = D_M(d)/Cost(d)`.

A design with `R_M(d)=0` is interventionally non-separating for at least one member of the candidate class.

The scalar Gaussian control additionally proves an identifiability boundary: in

`Y = beta do(X) + gamma U + epsilon`,

only total variance `gamma^2+sigma^2` is identified from scalar Y; latent-confounder variance and aleatoric variance are not separately recoverable without another measurement channel or assumption.

## Phase 2 — Composite-null falsifier

`CSCA-06A-IF` implemented a blockwise anytime-valid composite-null e-process with explicit interventions, nuisance profiling, equivalence abstention, fixed alpha and fixed maximum intervention cost.

Safety controls passed, but PRIMARY S2 reached only `120/128=0.9375` against the frozen `>=0.95` power gate. Independent replication passed. By protocol, replication could not rescue PRIMARY.

Verdict: `INTERVENTIONAL_FALSIFIABILITY_INSTRUMENT_NOT_QUALIFIED`.

## Phase 3 — Failure retained, not patched

The failed parent remains immutable as a negative claim. Its defect was localized to evidence efficiency: nuisance parameters were re-profiled independently inside each block, discarding information that nuisance is shared across the full run.

An accidental precommit execution in the parent line was separately burned and never treated as evidence.

## Phase 4 — Shared-nuisance global evidence

`CSCA-06A-R1` received a new preregistration and fresh cohorts. It evaluates a whole-data composite e-value only at exactly three preregistered cumulative-cost checkpoints `{64,128,256}` and rejects at `K/alpha=300` for `K=3`, `alpha=0.01`.

PRIMARY:

- N0/N1/N2/N3/E0: `0/128` rejected per family;
- S1/S2/S3: `128/128` rejected per family, median cost 64;
- O1: zero topology-specific rejection.

Independent REPLICATION reproduces the same S1/S2/S3 `128/128` and N0-N3/E0 `0/128` pattern.

Verdict: `GLOBAL_CHECKPOINT_FALSIFIABILITY_QUALIFIED_NARROWED`.

This is composite **model-class** falsification conditional on the nuisance envelope, not graph truth.

## Phase 5 — Information/compute converse

A necessary information bound was added directly to the executable instrument. If a test has type-I error `<=alpha` and target power `p`, KL data processing through the binary reject decision requires

`inf_Q KL(P_* || Q) >= kl(p || alpha)`.

For a fixed intervention design with rate `R_M`:

`Cost >= kl(p || alpha)/R_M`

is necessary, not sufficient.

At the frozen operating point `alpha=0.01`, `p=0.95`:

`kl(0.95||0.01)=4.176898950135489 nats`.

Strong S1/S2/S3 rate `0.2243809569 nat/cost` gives necessary cost `>=18.6152`, below the available 256.

Weak W1 rate `0.00985793158 nat/cost` gives necessary cost `>=423.7095`, **above** the available 256. Thus the requested 0.95 power is information-theoretically impossible for W1 at the frozen budget under the declared model family; the correct action is abstention rather than threshold relaxation or more of the same within-budget sampling.

E0 has zero separation and infinite necessary cost under the non-separating design.

## Phase 6 — Real-model intervention semantics

`CSCA-06B-OP` rejected the assumption that arbitrary SPACE/ZERO/0xFF/REVERSE corruptions are automatically equivalent interventions. It instead declared two explicit stochastic soft-intervention kernels using same-context contiguous donor spans.

Fresh nanochat PRIMARY and independent REPLICATION both show pooled/PROSE/CODE:

- top agreement = `1.0`;
- sign agreement = `1.0`;
- robust coverage = `1.0`;
- zero model-state mutation;
- zero prior-prompt overlap.

But all `48/48 + 48/48` robust cases select `A_RECENT`; robust non-recent count is zero.

Verdict: `OPERATOR_FAMILY_ROBUSTNESS_QUALIFIED_NARROWED`, with architectural utility blocked by recency domination.

## Phase 7 — Position/content falsification

`CSCA-06C-PC` was intentionally invalidated after one performance-smoke boolean exposed a would-be PRIMARY unit. The entire namespace was burned. `CSCA-06C-R1` used fresh prompt hashes and the same frozen scientific thresholds.

Each original candidate content block was cyclically moved through every candidate position while the original base next-token target remained fixed.

PRIMARY fully resolved `16/24=0.6667` prompts:

- `PositionTracking=1.0`;
- `ContentTracking=0.25`.

Independent REPLICATION fully resolved `11/24=0.4583`:

- every resolved case again has `PositionTracking=1.0`;
- `ContentTracking=0.25`;
- but PROSE resolution `4/12=0.3333` and pooled `11/24=0.4583` are below the frozen `>=0.50` coverage gate.

Therefore:

- content-specific causal credit: **NOT SUPPORTED**;
- position/locality explanation: strong resolved-case pattern, but **NOT PROMOTED** because independent-replication coverage fails;
- final mechanism verdict: `POSITION_CONTENT_MECHANISM_UNRESOLVED`.

## Current causal authority boundary

Allowed:

- controlled composite model-class falsification under declared nuisance support;
- information-theoretic pre-veto of impossible intervention budgets;
- narrow shadow-only direct-intervention measurement;
- operator-family robustness as an audit quantity.

Blocked:

- graph truth;
- arbitrary hidden-confounder exclusion;
- semantic causal authority;
- content-specific cognitive causal credit;
- learned/amortized causal-credit student;
- replay control;
- active causal control.

## Next hard gate

The next benchmark must orthogonalize **content identity** from **distance to the prediction boundary** by construction while maintaining non-degenerate intervention-family support. It must be possible for the same content identity to appear at multiple distances and for multiple content identities to appear at the same distance without changing the predeclared outcome semantics. Until that exists, training a student on current credit labels would mostly compress the already-visible locality signal.

## Verification

Focused CSCA-06 tests: `16 passed`.

Full collection: `407 tests collected`, zero collection errors.

PASS machine gates observed after final results:

- CSCA-06A negative binding;
- CSCA-06A-R1 positive narrowed binding;
- CSCA-06 information converse;
- CSCA-06B;
- CSCA-06C;
- CSCA-05;
- CSCA-04;
- CSCA-03R;
- RD03;
- research-ops / research-execution / research-ingestion;
- causal-debt;
- VIA;
- architecture;
- hermeticity;
- complexity;
- inference-integrity;
- doc-status;
- verdict-binding;
- technical-quality;
- truth-gate.

Registry: `59 claims / 59 hypotheses / 0 orphans`.

A full behavioral `pytest -q` was attempted. The environment/tool execution was interrupted after the progress display reached approximately 17%; it is therefore **not** reported as a full-suite PASS.
