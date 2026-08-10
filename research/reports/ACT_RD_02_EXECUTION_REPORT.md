# ACT-R&D-02 — Execution Report / Pass 1

Date: 2026-08-10

## Scope

Implemented the operational evidence substrate and compute governor, then executed the first
hard gate `CSCA-01 — Counterfactual Credit Kernel Reproduction & Falsification`.

The result is intentionally bounded: this is an independent controlled mechanism test, **not** a
paper-level reproduction and not architecture integration.

## Phase 1 — evidence substrate

Implemented:

- immutable local source freezing with SHA-256 and revision events;
- source/claim/hypothesis machine records;
- automatic claim attack flags without autonomous causal verdicts;
- evidence graph;
- H4/H5 governance records;
- C0→C1→C2→C3 fail-closed compute governor;
- runtime telemetry and artifact hashing;
- CI `RESEARCH-OPS-GATE`.

A material boundary was discovered: the repository only carries a one-line S01 primary-source
snapshot, not the full primary-source bytes. The snapshot is immutable and hashed, but the source
gate is therefore `QUARANTINED`. Paper-level reproduction authority is withheld.

## Phase 2 — compute decision

`CSCA-01` passed C0 authorization and C1 CPU-pilot authorization. No GPU scale was requested.
The experiment can change the scientific decision at small scale; therefore C2/C3 would add cost
without resolving the current uncertainty.

## Phase 3/4 — CSCA-01 controlled reproduction and attacks

Frozen cohorts:

- PRIMARY: 32 seeds (`12000..12031`);
- independent seed replication: 32 seeds (`22000..22031`);
- 128 trajectories × 3 contexts per seed;
- three zero-cause null/stress families plus high-noise stress.

Total execution:

- 49,152 generated trajectories;
- 24,625,152 counted structural counterfactual evaluations;
- 6 measured CPU runs;
- 30.10 s wrapper wall time;
- measured coarse child-process peak RAM: 115,527,680 bytes;
- GPU time/VRAM: `UNKNOWN/NOT_APPLICABLE` because no GPU run was justified.

### Exact kernel

`EXACT_CF_SHAPLEY`:

- PRIMARY OOD causal-rank accuracy: 1.0 / 1.0;
- REPLICATION OOD causal-rank accuracy: 1.0 / 1.0;
- OOD false-credit mass: 0;
- Shapley efficiency error: <= 1e-12;
- destroyed-link / correlation-only / pure-noise nulls: exact candidate credit = 0.

Verdict: `CSCA_01_CONTROLLED_KERNEL_REPRODUCED`.

### Finite-budget approximation

`MC_CF_SHAPLEY_64` achieved OOD causal-rank accuracy 1.0 in both cohorts and therefore passed the
**frozen rank qualifier**.

However, its mean OOD normalized false-credit mass remained about 0.227 (PRIMARY) and 0.231
(REPLICATION). Even the 4-permutation approximation ranked the true cause perfectly while carrying
~0.515 false-credit mass. Therefore **rank accuracy is insufficient as a practical estimator
acceptance metric**. This is a post-result diagnostic; the frozen CSCA-01 criterion is not edited.
A future approximation gate must preregister calibration/false-credit and compute-value criteria.

### Simpler baselines

Across OOD contexts:

- observational association succeeded only in the weak-confounder context and failed under sign inversion;
- recency failed systematically;
- the delayed-error eligibility proxy largely failed;
- uniform/random credit did not provide invariant cause recovery.

These comparisons are mechanism controls, not claims about canonical TD implementations.

## Scientific boundary

Supported narrowly:

> Given a correct known SCM and valid counterfactual intervention model, exact counterfactual
> Shapley credit can separate the known delayed structural cause from correlated/temporal/random
> non-causes in this controlled environment, and this result reproduced on an independent seed
> cohort and survived zero-cause nulls.

Not supported:

- full reproduction of the external paper;
- learned causal discovery from observational data;
- correctness under counterfactual-model misspecification;
- benefit in a language model;
- replay or memory improvement;
- physical inference-compute savings;
- biological equivalence;
- architecture promotion.

## Next weakest link

The successful exact kernel consumes an oracle-quality structural counterfactual model. Therefore
the next hard question is not more scale. It is:

> **How much counterfactual-model error can the credit operator tolerate before it creates false
> causal credit or changes the action ranking?**

This becomes the next analytic/adversarial gate before real-model integration.
