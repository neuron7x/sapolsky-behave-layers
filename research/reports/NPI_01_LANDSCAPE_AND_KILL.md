# NPI-01 — Landscape, Falsification, and Ruin Memory

Date: 2026-08-12
Canonical hypothesis: `H-NPI-01`
Verdict: `NPI_01_FIRST_ORDER_CERTIFICATE_NOT_SUPPORTED`

## Problem selected

**Nullspace-Projected Inhibitory Control (NPI):** use the structural-identifiability nullspace of a causal model as an internal inhibitory control object. The proposed first-order gate would suppress/withhold action only when observationally invisible causal directions are locally action-relevant.

The ambition is not to improve generic uncertainty estimation. It is to connect three normally separate levels:

1. which latent causal directions observations cannot identify;
2. which of those directions can change the current action;
3. whether the agent should inhibit execution or acquire an intervention.

## Targeted 2025-2026 landscape

The pre-execution and post-result searches found strong adjacent literatures but no exact formulation matching the NPI-01 certificate:

- structural identifiability/nullspace analysis: Stigter & Molenaar, *A fast algorithm to assess local structural identifiability*, Automatica 58 (2015), 118-124;
- neural/contextual suppression: *Latent circuit inference from heterogeneous neural responses during cognitive tasks*, Nature Neuroscience (2025), which identifies inhibition of irrelevant sensory representations in RNNs and primate PFC;
- mental-computation selection: *Learning to select computations in recurrent neural circuits* (2026), metareasoning via learned mental actions;
- decision-relevant information gathering: *Interpretable abstractions of artificial neural networks predict behavior and neural activity during human information gathering*, Nature Neuroscience (2026);
- agentic abstention: *Agentic Abstention: Do Agents Know When to Stop Instead of Act?*, arXiv:2606.28733;
- null-space safety steering: *AlphaSteer: Learning Refusal Steering with Principled Null-Space Constraint*, ICLR 2026, which uses an activation null-space constraint for refusal steering rather than a structural-identifiability nullspace to certify action invariance.

**Novelty status:** `PROVISIONAL / NOT EXHAUSTIVELY PROVEN`. The exact coupling searched here was not found, but absence from targeted search is not a global novelty theorem.

## Frozen strong claim

Given observation Jacobian `J`, a basis `N` of `ker J`, current positive action margin `Delta`, and projected first-order action sensitivity

`S = ||N^T grad Delta||`,

NPI-01 hypothesized that `S=0` plus positive margin is sufficient to derive a strictly positive action-safe radius from first-order local information alone.

## Constructive kill

Let `theta=(u,v)`, observation `y=u`, and therefore `ker J = span(e_v)`.

Use

`Delta_K(u,v) = 1 - K v^2`.

At `theta0=(0,0)`, for every `K>0`:

- observation = 0;
- `J=[1,0]`;
- nullspace = `span(e_v)`;
- action margin = 1;
- action-value gradient = `(0,0)`;
- NPI score = 0.

For any proposed positive radius `r`, choose `K=8/r^2` and the observationally equivalent point `theta'=(0,r/2)`. It lies strictly inside `r`, yet

`Delta_K(theta') = -1` exactly.

Thus the preferred action reverses while the complete first-order certificate at the reference point is unchanged. Because `K` can grow as `r` shrinks, no positive radius determined only by the frozen first-order certificate can be universal.

## Execution evidence

Frozen radii:

- `1`
- `1e-1`
- `1e-2`
- `1e-4`
- `1e-8`

Result: **5/5 constructive reversals**.

Preregistered harness mutations: **6/6 killed**.

Independent post-result verifier: PASS; it does not import the falsifier and recomputes the exact rational identities from the sealed artifact.

## What died

The universal first-order sufficiency claim died.

A zero local action-gradient projection onto the structural-identifiability nullspace is not enough to authorize execution. First-order invisibility can hide higher-order action instability.

## What survived

The broader research problem survives in a sharper form:

> Can an agent inhibit only *decision-dangerous non-identifiability* using a certificate that controls higher-order variation over the observational equivalence set?

Any successor must carry at least one of:

- a certified Hessian/curvature bound along the nullspace;
- a Lipschitz bound on the action-value gradient;
- exact/set-valued robust action analysis over an observational equivalence class;
- an intervention that contracts the dangerous equivalence set before execution.

A successor that merely replaces the first-order score with a learned scalar without a falsifiable higher-order bound is prohibited by this negative.

## Ruin memory

Do not resurrect `S=0 => safe` under another name. The counterexample is analytic, scale-free across the frozen radii, and independent of estimator error, finite-sample noise, neural-network training, or benchmark selection.
