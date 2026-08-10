# CSCA-07-PR — Passive Replay Identifiability & Hallucination Boundary

**Date:** 2026-08-10  
**Authoritative verdict:** `PASSIVE_REPLAY_IDENTIFIABILITY_BOUNDARY_QUALIFIED`  
**Authority:** passive predictive falsification only; causal promotion remains blocked.

## Question

Can an internally stable, perturbation-invariant replay abstraction be distinguished from a self-consistent generative hallucination using only a passive factual trace and no new environment intervention?

## Exact boundary

No universal passive certificate exists. If two latent candidates induce the same law on every factual trace,

`P(D_fact | M=0) = P(D_fact | M=1)`, 

then the factual trace contains zero information about the model index: `I(M;D_fact)=0`. Every passive decision rule has the same distribution under the two candidates. A Jacobian spectrum, replay-attractor stability or within-model compression statistic cannot override this observational-equivalence boundary unless additional identifying assumptions connect that statistic to the environment.

The operational object is therefore not "causal truth from replay" but **passive falsifiability of the observable law**.

## P1 — Jacobian-spectrum counterexample

Two linearly similar 2-state dynamical realizations were constructed. Their latent transition graphs differ:

- realization A adjacency: `[[1,1],[0,1]]`;
- realization B adjacency: `[[1,1],[1,1]]`.

Yet:

- Jacobian eigenvalues A: `[0.2, 0.7]`;
- Jacobian eigenvalues B: `[0.20000000000000007, 0.7]`;
- spectral distance: `5.55e-17`;
- maximum observable sample-path discrepancy over 512 steps: `4.44e-16`.

Thus the latent Jacobian spectrum is not a sufficient causal-topology identifier. Similarity can preserve the entire observable realization and eigen-spectrum while changing latent edge sparsity.

## P2 — Stable autocatalytic hidden replay

A hidden predicate-supported coordinate converged to:

- fixed point `h*=0.8087881753`;
- local Jacobian `0.1383446750`;
- spectral radius `<1`;
- context derivative exactly `0`;
- observational information about this hidden coordinate exactly `0` by construction.

Therefore local contraction and perfect internal context-invariance are compatible with a completely observationally invisible replay attractor. Stability proves stability, not environment causality.

## P3 — fiber-entropy counterexample

Let factual `X` and model index `M` be independent fair bits. Candidate M=0 defines `Z=X`; candidate M=1 defines `Z=1-X`.

- each model has `H(Z|X,M)=0`;
- cross-model `H(Z|X)=1 bit`;
- `I(M;X)=0`.

So zero fiber entropy *inside each model* does not identify which latent semantics is environment-real. The epistemic object is uncertainty over the observational-equivalence class, not compression inside one chosen representation.

## P4 — passive e-process

A predeclared Bayesian-mixture likelihood ratio was used as an anytime-valid e-process against a candidate Gaussian AR(1) transition law. Crossing `e >= 100` corresponds to `alpha=0.01`. Under the declared candidate law, the numerator is a predictable normalized density, so rejection targets only the observable transition law.

This instrument cannot infer a latent causal graph from non-rejection.

## P5 — confirmatory execution

Each cohort used 128 fresh seeds per family and 256 factual transitions per trace. PRIMARY and REPLICATION seed blocks were disjoint.

| family | PRIMARY rejection | REPLICATION rejection | exact information rate (nat/transition) |
|---|---:|---:|---:|
| N0 true observed law | 1/128 = 0.0078125 | 1/128 = 0.0078125 | 0 |
| S1 wrong dynamics (`.75 -> .25`) | 128/128 = 1.0 | 128/128 = 1.0 | 0.2857142857 |
| S2 wrong sign (`.75 -> -.40`) | 128/128 = 1.0 | 128/128 = 1.0 | 1.5114285714 |
| W1 weak misspecification (`.75 -> .68`) | 6/128 = 0.046875 | 14/128 = 0.109375 | 0.0056 |

All frozen qualification predicates passed. The W1 low-power outcome is not a failure of the instrument: the predeclared information converse says the target 0.95 power at alpha .01 needs at least `745.8748` transitions, greater than the available `256`.

## P6 — information/cost law

For a rejection event with type-I probability at most `alpha` and desired power `p`, data processing yields the necessary information:

`D >= kl(p || alpha)`.

At `alpha=.01`, `p=.95`, this is `4.1768989501` nats. If the passive relative-entropy rate is `R`, then

`n >= kl(p||alpha) / R`

is a necessary, not sufficient, sample-cost condition.

Observed certificates:

- S1: necessary `14.6191` transitions;
- S2: necessary `2.76354`;
- W1: necessary `745.8748 > 256`;
- observationally equivalent causal models: `R=0 -> necessary cost = infinity`.

The last line is the decisive boundary. Unlimited replay compute cannot manufacture information that is absent from the factual channel.

## P7 — runtime authority

The only admissible states are:

- predictive law contradicted -> `REJECT_REPLAY_PREDICTIVE_LAW`;
- predictive law not contradicted, no identifying assumptions -> `PASSIVE_EQUIVALENCE_UNRESOLVED_CAUSAL_AUTHORITY_BLOCKED`;
- causal candidate only under separately justified identifying assumptions -> `CAUSAL_CANDIDATE_UNDER_EXPLICIT_IDENTIFYING_ASSUMPTIONS`.

The experiment does **not** authorize semantic causality, shadow causal authority, replay control or active control.

## Scientific interpretation

The strongest result is negative and architectural: **passive factual fit can falsify a bad predictive replay model, but cannot in general certify that a self-consistent latent abstraction is the environment's true causal abstraction.** Spectral stability and fiber compression are useful diagnostics only after identifiability assumptions are established. The next admissible research step is to search for an explicit observational identifying structure (e.g. valid grouping, temporal/noise asymmetry, known exogenous regime labels, instruments) and preregister the exact assumptions before any causal promotion.
