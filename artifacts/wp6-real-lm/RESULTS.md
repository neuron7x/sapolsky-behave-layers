# WP6 Real-LM Boundary — RESULTS (a frozen negative that maps the framework's edge)

**Verdict: `WP6_REAL_LM_NOT_IDENTIFIABLE`.** Preregistration:
`experiments/wp6_real_lm/PREREGISTRATION.md`. Reproduce:
```
PYTHONPATH=. python -m experiments.wp6_real_lm.src.runner --seeds 0..4
PYTHONPATH=. python -m experiments.wp6_real_lm.src.analyze
```

## The clean synthetic identifiability does NOT transfer to real data

A byte-level recurrent LM trained on a frozen 66 KB corpus of real English prose, next-byte
prediction, difficulty = target-byte unigram-surprisal tercile, compute `K ∈ {1,2,3}`:

| | real-LM `G_lo` | real-LM `Ĝ` |
|---|---|---|
| `λ = 0.0` | **−0.090** | +0.000 |
| `λ = 0.3` | **−0.090** | +0.000 |
| **positive control (synthetic AC1)** | **+0.621** | — |

The oracle per-difficulty compute allocation has **no identifiable value** on real language data
(`G_lo ≤ 0` at every `λ`, plug-in gap ≈ 0). The **positive control** — the same certificate on the
synthetic AC1 shift task — returns `G_lo = +0.621`, proving the instrument detects a gap when one
exists. So the null is real, not an instrument failure.

## Why — and why it matters

On the synthetic shift task, compute `K=d` was *sharply* required (off-diagonal accuracy 0.06) —
that clean context×compute interaction is what made AC1 identifiable. On real byte-level LM
difficulty, **more compute helps all difficulty buckets roughly uniformly**, and on the hard bucket
it can even *hurt* (`K=3 > K=1` loss), so a fixed compute budget is as good as any per-difficulty
allocation. The sharp interaction the framework needs is a **property of the synthetic benchmarks,
not of real language-model per-token difficulty**.

This is the honest boundary of the whole programme: the identifiability→controller→rate-function
machinery is validated on two synthetic mechanisms (plasticity, compute), but its precondition —
an identifiable context×resource interaction — **does not automatically appear on real data**.
Establishing it on a real workload at scale is exactly the (cloud-blocked) L7 problem.

## Consequence for the claim ladder

`CWC-RD1-real-lm-boundary` is registered **NOT_SUPPORTED** (real-LM per-token compute identifiability),
a frozen negative. Scope is tight (byte-level, tiny model, unigram-surprisal difficulty); it does
**not** claim adaptive compute never helps real LMs — only that this identifiability signal is
absent here, with a positive control confirming the test works.

## Scope

Tier `REAL-DATA` (real prose; tiny byte-level model). Boundary result.
