# CSCA-06A-IF — Execution Report

**Date:** 2026-08-10  
**Authoritative verdict:** `INTERVENTIONAL_FALSIFIABILITY_INSTRUMENT_NOT_QUALIFIED`

## Scientific question

Can a finite-cost intervention instrument falsify a declared causal model class while refusing to misattribute admissible latent confounding or aleatoric noise to graph topology?

## Formal result

The relevant separation object is not `I(M;do(X))`. For an intervention design `d`, the model-class separation is

`D_M(d) = inf_{Q in P_M} KL(P_*^d || Q^d)`, with cost-normalized rate `R_M(d)=D_M(d)/Cost(d)`.

If `R_M(d)=0`, the candidate class is interventionally indistinguishable under that design. Positive `R_M` permits evidence accumulation but is not by itself a finite-budget power guarantee.

The implemented test uses block e-values

`e_b = q(Y_b|d) / sup_{theta in P_M} p_theta(Y_b|d)`.

For every member of the declared composite null, `E[e_b|past] <= 1`, so the cumulative product is anytime-valid at threshold `1/alpha`. This validity is conditional on the nuisance envelope actually containing the data-generating nuisance process.

## Non-identifiability result

For `Y = beta do(X) + gamma U + epsilon`, `U~N(0,1)`, `epsilon~N(0,sigma^2)`, scalar intervention data identify only `tau^2=gamma^2+sigma^2`. Seventeen distinct `(gamma,sigma)` decompositions were constructed with total-variance spread `1.33e-15` (floating-point error). Thus latent-confounder variance and aleatoric variance are not separately identifiable from this observation channel without extra measurements or assumptions.

## Analytic intervention design

The minimax KL/cost search over `do(X) in {-1,0,+1}` selected the two extreme interventions with one sample each as the smallest rate-optimal design. A single `do(X=+1)` control had profiled KL `0`, because the shared nuisance intercept could exactly absorb the apparent slope. The engine therefore returns `UNRESOLVED_INTERVENTIONAL_EQUIVALENCE` before causal authority.

## PRIMARY — fresh seeds from 81000

In-envelope true-model families had zero false rejections:

- clean: `0/128`;
- latent-confounding: `0/128`;
- high-aleatoric: `0/128`;
- mixed nuisance: `0/128`.

Structural families:

- S1 missing positive edge: `127/128 = 0.9921875` rejected;
- S2 missing negative edge: `120/128 = 0.9375` rejected;
- S3 spurious candidate edge: `125/128 = 0.9765625` rejected.

The frozen qualification requirement was `>=0.95` for every structural family. S2 therefore failed. The threshold was not changed.

Weak-edge stress (`beta=0.15`) produced `0/128` rejections at the fixed cost, correctly ending as `ABSTAIN_INSUFFICIENT_INTERVENTION_BUDGET` rather than false causal acceptance.

## Independent REPLICATION — fresh seeds from 91000

- all four in-envelope null families: `0/128` false rejections each;
- S1: `125/128 = 0.9765625`;
- S2: `125/128 = 0.9765625`;
- S3: `124/128 = 0.96875`.

Replication passed the frozen gate, but the preregistration explicitly forbids replication from rescuing a failed PRIMARY.

## Boundary attack

The out-of-envelope noise family was never granted topology-specific falsification. This is essential: rejection of a graph+nuisance model class cannot, without independent nuisance-adequacy evidence, uniquely identify the graph as the failed component.

## Why the instrument failed qualification

The blockwise composite-null e-process is deliberately safe but pays a large power tax by re-profiling nuisance parameters independently inside every block. The PRIMARY S2 miss is therefore treated as a mechanism deficiency under the fixed cost, not sampling bad luck to be ignored.

The next admissible experiment must improve evidence efficiency **without increasing alpha, weakening the 0.95 power gate, increasing the cost ceiling, or reusing exposed seeds**. A candidate is a fixed-checkpoint global likelihood e-value: profile the shared nuisance parameters over all accumulated intervention observations at preregistered cost checkpoints and alpha-spend across those checkpoints. This preserves finite-sample composite-null validity while avoiding per-block nuisance reset.

## Governance incident disclosed

An accidental precommit execution exposed the original 61000/71000 cohorts after an import-path repair. Those outputs were sealed without interpretation as `INSTRUMENT_PROVENANCE_INVALID_PRECOMMIT_EXECUTION`; both cohorts were permanently burned. The authoritative run used untouched 81000/91000 cohorts.

## Authority

No graph-truth, shadow-inference promotion, replay, semantic causality, or active-control authority is granted.
