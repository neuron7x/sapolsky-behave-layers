# CSCA-06A-R1 — Global Fixed-Checkpoint Composite-Null Falsifiability

**Date:** 2026-08-10  
**Parent:** `CSCA-06A-IF = INTERVENTIONAL_FALSIFIABILITY_INSTRUMENT_NOT_QUALIFIED`  
**Authoritative verdict:** `GLOBAL_CHECKPOINT_FALSIFIABILITY_QUALIFIED_NARROWED`

## Question

Can the failed CSCA-06A instrument recover finite-budget power without relaxing alpha, increasing the maximum intervention cost, changing the nuisance envelope, weakening the structural-power gate, or reusing exposed confirmatory seeds?

## Mechanism change

The failed parent formed an anytime-valid product of blockwise composite-null e-values. Each block independently re-profiled the nuisance parameters. This was safe but discarded cross-block evidence that the nuisance is shared.

R1 instead evaluates the whole accumulated intervention sample only at three preregistered cumulative-cost checkpoints:

`C = {64, 128, 256}`.

At checkpoint `t`,

`E_t = q(Y_1:t | A_1:t) / sup_{theta in P_M} p_theta(Y_1:t | A_1:t)`.

For every `P_theta` in the declared composite null, pointwise domination gives `E_theta[E_t] <= 1` at a fixed checkpoint. With exactly `K=3` preregistered looks, Markov plus the union bound gives

`P_M(max_t E_t >= K/alpha) <= alpha`.

With `alpha=0.01`, the frozen rejection threshold is therefore `E_t >= 300`. This is a fixed-checkpoint multiple-look test. It is **not** claimed to be an arbitrary-time e-process or a confidence sequence.

## What did not change from the failed parent

- nuisance envelope: shared intercept `h in [-0.75,0.75]`, total SD `tau in [0.5,2.5]`;
- intervention actions: `do(X) in {-1,+1}` with unit cost;
- maximum total cost: `256`;
- alpha: `0.01`;
- structural qualification threshold: rejection rate `>=0.95` independently for S1, S2 and S3;
- null-family false-rejection ceilings;
- equivalence control and out-of-envelope abstention boundary;
- graph-truth/replay/shadow/active-control prohibition.

Only evidence aggregation changed.

## Provenance boundary

An exploratory diagnostic of global shared-nuisance aggregation was performed only after the negative parent result and is disclosed in `research/design_pilots/CSCA_06A_R1_EXPLORATORY_BOUNDARY.md`. R1 was assigned a new experiment ID, new preregistration, and fresh confirmatory cohorts before authoritative execution.

Authoritative cohorts:

- PRIMARY seeds: `151000..151127` per family;
- independent REPLICATION seeds: `161000..161127` per family.

No parent or exploratory cohort was reused.

## PRIMARY

In-envelope null and equivalence controls:

- N0 clean: `0/128` rejected;
- N1 latent-confounding: `0/128` rejected;
- N2 aleatoric: `0/128` rejected;
- N3 mixed nuisance: `0/128` rejected;
- E0 single-action interventional equivalence: `0/128` rejected and all `UNRESOLVED_INTERVENTIONAL_EQUIVALENCE`.

Structural alternatives:

- S1 missing positive edge: `128/128 = 1.0`, median rejection cost `64`;
- S2 missing negative edge: `128/128 = 1.0`, median rejection cost `64`;
- S3 spurious candidate edge: `128/128 = 1.0`, median rejection cost `64`.

Out-of-envelope O1 received zero topology-specific rejections and remained `ABSTAIN_INSUFFICIENT_INTERVENTION_BUDGET` in all `128/128` cases.

Weak-edge stress W1 (`|delta beta|=0.15`) produced `1/128` rejection at cost 256 and `127/128` abstentions. W1 is a preregistered stress surface, not a qualification endpoint; the single conditional falsification is retained rather than hidden.

**PRIMARY: PASS.**

## Independent REPLICATION

- N0/N1/N2/N3: `0/128` rejected in every family;
- E0: `0/128` rejected;
- S1: `128/128 = 1.0`;
- S2: `128/128 = 1.0`;
- S3: `128/128 = 1.0`;
- O1: `0/128` topology-specific rejection;
- W1: `0/128` rejection.

**REPLICATION: PASS.**

## Parent-to-R1 comparison

The parent failed because PRIMARY S2 reached only `120/128 = 0.9375`, below its frozen `0.95` gate, despite replication passing. R1 reaches `128/128` on S2 in both new cohorts under the same alpha, same maximum cost and same nuisance family. The improvement is therefore attributable to the changed evidence-aggregation mechanism within this controlled benchmark, not to a relaxed decision rule.

This does not prove that global fixed-checkpoint aggregation is universally more powerful. It qualifies it only on the frozen CSCA-06A model family and tested alternatives.

## The deeper identifiability result remains negative

For scalar

`Y = beta do(X) + gamma U + epsilon`, with `U~N(0,1)` and `epsilon~N(0,sigma^2)`,

only `tau^2 = gamma^2 + sigma^2` is visible in the marginal intervention law. Latent-confounder variance and aleatoric variance therefore remain observationally/interventionally aliased in this channel. R1 does not solve that decomposition.

Likewise, rejection means only:

`P_*^d not in declared graph-component + nuisance model class at the tested intervention design and evidence level`.

It does **not** imply that topology is uniquely the failed component if the true nuisance mechanism lies outside the declared envelope.

## Information-theoretic object

The operational design quantity remains

`D_M(d) = inf_{Q in P_M} KL(P_*^d || Q^d)`

and

`R_M(d) = D_M(d) / Cost(d)`.

`R_M(d)=0` means no amount of repeated data from that same intervention design can distinguish the truth from at least one member of the candidate model class. `R_M(d)>0` is asymptotic separability per unit cost, not a finite-budget rejection certificate. The finite-budget decision is supplied separately by the calibrated evidence test.

## Scientific verdict

`GLOBAL_CHECKPOINT_FALSIFIABILITY_QUALIFIED_NARROWED`

Qualified object: a **finite-checkpoint composite model-class falsifier** for the declared controlled Gaussian intervention family, with explicit nuisance envelope, explicit cost, explicit alpha, exact equivalence abstention and independent fresh-seed replication.

Not qualified:

- graph truth;
- arbitrary hidden-confounder exclusion;
- latent-vs-aleatoric decomposition;
- universal `I(M;do(X))` threshold;
- real-language-model structural adequacy;
- semantic causal authority;
- replay control;
- active causal control.

## Next hard gate

`CSCA-06B` must return to the real nanochat shadow path and attack the weak link exposed by CSCA-05: **intervention semantics**. It must define an admissible intervention-operator equivalence class before testing invariance. Arbitrary byte corruptions such as SPACE/ZERO/0xFF/REVERSE must not be treated as interchangeable implementations of one latent semantic `do()` without proof.
