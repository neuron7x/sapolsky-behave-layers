# CWC-CDL-02 — Resolution-Aware Causal Debt

Status: PREREGISTERED / EXPERIMENTAL / NON-ASCENSION
Date: 2026-08-10
Parent negative result: `artifacts/causal-debt-v1/verdict.json`

## Why V2 exists

V1 failed because observational eligibility remained a permanent debt term even
after repeated zero-effect counterfactual probes. This caused replay starvation:
causally unsupported but observationally salient candidates could monopolize the
replay budget. V1 also contained an impossible strict false-credit improvement
criterion when matched counterfactual controls were already at the zero floor.

V2 is not a rewrite of V1. V1 remains sealed. V2 tests one explicit correction:
**negative causal evidence must discharge replay priority without being promoted
into a positive causal claim.**

## New algorithmic hypothesis

A resolution-aware debt score that decays observational eligibility with replay
count and shifts authority toward measured causal leverage will spend fewer probes
on interventionally dead correlates, while preserving fail-closed consolidation.

The V2 scheduler may change *priority only*. Consolidation thresholds and the
counterfactual operator remain matched to the V1 substrate.

## Adversarial benchmark suite

Two frozen acquisition mechanisms are required:

1. `proxy`: S is a noisy proxy of the invariant cause C. C is usually at least as
   observationally salient as S; this is the benign case where RPE replay is strong.
2. `descendant`: S is an observationally stronger descendant/proxy of Y in the
   acquisition context but has no causal effect on Y. This adversarial case tests
   whether negative intervention evidence can discharge a salient false candidate.

Held-out contexts decorrelate or reverse S while the C -> Y mechanism remains fixed.

## Acceptance principle

V2 must not win only because the benchmark was made hostile to RPE. Therefore it
must satisfy both:

- superiority on the combined suite against matched-CF controls;
- non-inferiority on the benign `proxy` environment.

False-credit is a safety/non-inferiority criterion, not a strict-improvement
criterion at a zero floor.

## Scope

Synthetic SCM control only. No neuroscience claim, no language-model claim, no
VIA ascension authority.
