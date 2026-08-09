# VIA-V1Q — Attention-Horizon Mechanism Qualification

**Class:** controlled mechanism qualification
**Ascension authority:** false
**Outcome inspection before protocol freeze:** prohibited

## Hypothesis

A compute axis based on visible attention horizon has a non-empty cost-sensitive opportunity region
when the workload contains both local and long-range dependency regimes.

This is a structural/mechanistic hypothesis only. It is not a claim about trained transformers or
real workloads.

## Dataset

Enumerate every binary prefix of length 8 (`2^8 = 256`) in each of two regimes:

- `local`: target is prefix[-1]
- `long`: target is prefix[0]

Total independent controlled units: 512.

## Actions

- `short`: horizon H=2, compute proxy 2 visible symbols
- `full`: horizon H=8, compute proxy 8 visible symbols

The action predictor may use only the last H prefix symbols. When the target dependency is outside
that visible set, it predicts the fixed symbol 0. Complete enumeration makes its accuracy exactly the
Bayes-balanced 0.5 on the hidden first bit; no sampling luck is involved.

## Quality

Per-unit quality is exact-match accuracy in {0,1}. Quality and compute remain separate. The analysis
evaluates `U_lambda = quality - lambda * compute` only at exact action-ranking critical points and
one representative per interval.

## Controller cost

Primary qualification uses `controller_compute=0` to estimate the mechanism's gross envelope. The
report must also state the maximum controller-compute allowance implied by the opportunity curve.
No claim is made that visible-symbol units equal FLOPs, milliseconds, or joules.

## Primary gate

PASS candidate qualification iff:

- replay contract complete;
- information ordering holds at every sampled lambda;
- a positive regime-opportunity interval exists for lambda > 0;
- max controller-compute allowance > 0;
- both actions become regime-optimal in the positive opportunity region;
- no scientific/ascension authorization is emitted.

## Kill rule

Any primary-gate failure rejects this candidate mechanism. Do not modify task priors, horizons,
target definitions, or lambda evaluation after seeing the result.

## Prohibited inference

No real-workload, transformer, GPU, routing, latency, energy, or architecture claim may be derived
from this qualification.
