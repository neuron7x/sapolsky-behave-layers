# CSCA-06A-R1 — Global Fixed-Checkpoint Composite E-Value

**Frozen before confirmatory execution:** 2026-08-10  
**Parent:** `CSCA-06A-IF = NOT_QUALIFIED` because PRIMARY S2 power was 0.9375 < frozen 0.95.  
**Mechanism change:** evidence aggregation only. Alpha, cost ceiling, nuisance envelope, structural families and power gate remain unchanged.

## Failure diagnosis

The parent multiplied block e-values whose null nuisance parameters were re-profiled independently in every 16-sample block. This is valid but discards the fact that the nuisance intercept and interventional variance are shared across the experiment. The next test must recover that information without weakening error control.

## New test

At predeclared cumulative costs `64, 128, 256`, compute

`E_t = q(Y_1:t | A_1:t) / sup_{theta in P_M} p_theta(Y_1:t | A_1:t)`.

For each fixed checkpoint and every `theta in P_M`, `E_theta[E_t] <= 1` by the same pointwise likelihood-envelope argument. We do **not** claim `{E_t}` is a supermartingale. There are exactly K=3 predeclared looks, so reject when

`E_t >= K/alpha = 300`

at any checkpoint. By Markov + union bound, family-wise false rejection across the three looks is <= alpha=0.01, regardless of dependence between looks.

This is a fixed-checkpoint sequential design, not arbitrary optional stopping.

## Frozen design

- same two extreme interventions and 8+8 sample block;
- same cost ceiling 256;
- same composite nuisance envelope;
- same normalized alternative mixture, centered on candidate model slope;
- same null/structural/weak/out-of-envelope/equivalence families as parent;
- same gates: pooled in-envelope null false rejection <=0.01; each structural S1/S2/S3 rejection >=0.95 independently in PRIMARY and REPLICATION; E0 unresolved; O1 never topology-attributed.

Fresh cohorts:
- PRIMARY seeds from 151000;
- independent REPLICATION from 161000;
- 128 seeds per family.

The parent, burned cohorts, and an exploratory post-negative mechanism diagnostic are excluded from confirmatory metrics.

## Kill rule

If PRIMARY again has any S1/S2/S3 rejection rate <0.95 at cost 256, the global-checkpoint mechanism is `NOT_QUALIFIED`; replication cannot rescue it. No threshold/budget increase is allowed after execution.

## Authority boundary

PASS qualifies a finite-budget model-class falsification **instrument** on the controlled Gaussian family. It does not identify the true graph, separate latent confounding from aleatoric variance, or promote real-model shadow/replay/active inference.
