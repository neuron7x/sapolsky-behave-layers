# PREREGISTRATION — WP6 Real-LM Boundary (does the framework transfer off synthetic?)

**Committed before the confirmatory run.** A scout showed the oracle gap on real language-model
per-token difficulty is ≈0. This preregisters the confirmatory test of a **negative boundary**:
the clean identifiability the framework enjoys on synthetic mechanisms (AC1 shift task, oracle gap
0.62) does NOT transfer to real data. Landing a negative honestly requires preregistration + a
positive control that the certificate can detect a gap when one exists.

## Design (frozen)

- **Real data:** a frozen corpus (`artifacts/wp6-real-lm/corpus.txt`, 66 KB of the repo's stable
  upstream/methodology/vision docs — real English prose). Byte-level (`VOCAB=256`), next-byte
  prediction. Committed so the corpus cannot drift.
- **Mechanism (same as WP5):** a weight-tied recurrent block, `K ∈ {1,2,3}` iterations = compute.
- **Difficulty context:** the target byte's **unigram-surprisal tercile** (`easy/med/hard`) — an
  independent signal, not the model's own loss.
- **Seeds:** 5. Utility `U_λ[bucket][K] = −loss[bucket][K] − λ·K/3`, `λ ∈ {0.0, 0.3}`.
- **Certificate** `G_lo` (`identifiability_inference`, δ=0.05) over the 5 seeds.
- **POSITIVE CONTROL:** the same certificate on the synthetic AC1 raw runs (`acc[d][K]`), which has
  a real gap — must return `G_lo > 0`, proving the instrument detects a gap when present.

## Decision rule (FROZEN)

- **WP6_REAL_LM_NOT_IDENTIFIABLE** iff real-LM `G_lo ≤ 0` at **every** `λ` AND the positive control
  `G_lo > 0`. The framework's clean identifiability is a property of the synthetic benchmarks, not
  of real language-model per-token compute allocation.
- **WP6_REAL_LM_IDENTIFIABLE** — real-LM `G_lo > 0` at some `λ` (the framework transfers to real
  data — a stronger, surprising positive).
- **WP6_VOID** — the positive control fails (`G_lo ≤ 0`): the certificate cannot detect even the
  known synthetic gap, so no conclusion.

## Scope / prohibited

Tier `REAL-DATA` (real prose, tiny byte-level model). A **boundary** result. It does NOT claim
adaptive compute never helps real LMs — only that, for this byte-level model and unigram-surprisal
difficulty, more compute helps all difficulty levels roughly uniformly, so per-difficulty
allocation has no identifiable value. New claim `CWC-RD1-real-lm-boundary`. No L7.
