# CWC Legend-Key Meta-Analysis — 2026-08-11

## Objective

This document is not a scientific claim and not a reputation claim. It asks a narrower
engineering question: what single public result could compress the existing CWC research
programme into something an external researcher can understand, attack, reproduce and
reuse?

## Reverse search over the current programme

The internal architecture already contains many components: causal-credit estimation,
structural adequacy attacks, passive-identifiability impossibility results, assumption-
typed identification, surviving countermodel sets, a typed epistemic lattice,
authority-preserving memory, proof-carrying planning and decision-relevant information
allocation. Adding another private subsystem has diminishing external value unless it
creates a crisp failure mode or benchmark.

The strongest current compression is therefore not "CWC is a new cognitive architecture".
That claim is unsupported. The strongest candidate is a benchmarkable epistemic-control
problem:

> **When causal worlds remain unresolved, can an agent know whether to ACT, QUERY,
> ABSTAIN, or REJECT a model without silently converting decision sufficiency into causal
> truth?**

## Why the first candidate thesis is not enough

`COG-INFO-02` established synthetically that causal-model identification and immediate
decision identification can separate. However, the abstract principle has substantial
prior-art overlap with value of information, decision-focused learning, decision-
sufficient representations, robust/multivalued decision models, decision-aware
experimental design and active epistemic control. It must not be marketed as a broad
novel theorem.

The potentially distinctive object is the **joint executable evaluation surface**:

1. observationally equivalent causal worlds;
2. hidden confounding and structural misspecification;
3. action-invariant causal ambiguity;
4. action-flipping ambiguity with a discriminating query;
5. action-flipping ambiguity with no admissible information channel;
6. operator/intervention-semantic ambiguity;
7. evidence/provenance corruption;
8. irreversible-action timing and post-hoc abstention.

The agent is scored not only for task success, but for whether the *authority level of its
claim/action is justified by the available evidence*.

## Closest literature pressure

This direction overlaps materially with at least:

- decision-focused learning and decision-sufficient representations;
- robust / multivalued online decision making;
- robust Bayesian decision-aware experimental design;
- Active Epistemic Control for query-efficient verified planning;
- causal-confusion benchmarks and active sampling;
- CausalGame for causal thinking of LLM agents;
- AgentAbstain for act-vs-abstain behavior;
- CRL sanity-check benchmarks showing large synthetic-to-real gaps;
- negative-control evaluation for causal discovery.

Therefore the novelty status is `UNKNOWN_OVERLAP_CONCEDED` until a dedicated claim-by-
claim prior-art audit is complete.

## Candidate public object

Working name: `CAB-01 — Causal Authority Benchmark`.

Each generated task hides the causal world but exposes a controlled factual trace and a
bounded set of admissible information actions. The agent must return exactly one of:

- `ACT(action, authority_scope)`;
- `QUERY(query_id)`;
- `ABSTAIN(reason)`;
- `REJECT_MODEL(model_or_assumption_id)`.

If it acts, it must separately state whether the action is robust across surviving worlds
or depends on a causal assumption. It may never use "true causal model" as a scoreable
shortcut.

## Primary metrics

Report a vector, never one vanity score:

- false causal authority rate;
- wrong irreversible-action rate;
- correct robust-action rate;
- necessary-query recall;
- unnecessary-query cost;
- correct no-information abstention rate;
- assumption-violation discrimination;
- post-hoc-abstention rate;
- evidence/provenance violation rate;
- total information / compute cost.

A Pareto frontier is primary. Any scalar leaderboard score must preregister weights.

## Kill conditions

The candidate flagship is killed if any of the following holds:

1. a prior benchmark already measures the same joint state/action/authority problem with
   comparable causal ambiguity and cost accounting;
2. simple baselines match the proposed benchmark ceiling;
3. task generators leak the intended epistemic state through surface cues;
4. the CWC policy wins only because it receives privileged generator structure;
5. results do not transfer beyond the synthetic generator;
6. external agents cannot reproduce the qualitative ordering;
7. false-authority reductions are purchased only by trivial always-abstain behavior.

## What would constitute a real external result

A defensible flagship result requires a public, contamination-resistant generator,
matched interfaces and compute budgets, strong baselines, at least two non-synthetic or
real-model task families, frozen preregistration, independent reproduction and a result
that survives the kill conditions above.

Until then: strong research substrate, candidate thesis, no legend claim.
