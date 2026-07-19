# WP-3 Plasticity v1 — AMG oracle-gap gate — RETROSPECTIVE PROTOCOL

> Historical-status correction (2026-07-19): this protocol, implementation and
> results first entered Git in the same commit. It is not independently
> timestamped preregistration evidence.

Registered 2026-07-16. Authority: CWC Adaptive Metaplasticity Governor spec v1.0,
Phase G+H. This is a BENCHMARK-VALIDITY gate (spec §11.4), not a governor claim:
it decides whether a learned metaplasticity governor may be trained at all.

## Hypothesis under test (identifiability)
There exists a continual benchmark where different task families are best adapted
by DIFFERENT parameter groups, so a per-task ORACLE plasticity allocation beats
every FIXED allocation. Without this gap, training a governor is prohibited.

## Design
Model: small named-group transformer (embed/attn.qkv/attn.proj/mlp.fc/mlp.proj/
head). Pretrain on BASE (identity). Tasks: LEXICAL (fixed symbol permutation),
RELATIONAL (position shift). For each task × single-group allocation
{attn, mlp, head, embed}, reset to pretrained, adapt ONLY that group via the
plasticity optimizer, measure new-task accuracy AND retained BASE accuracy.
Utility = new_acc − α·retention_drop (α=1). 5 seeds.

## Gate (spec §11.4)
IDENTIFIABLE iff mean(oracle_gap) ≥ 0.05 AND LCB95 > 0, where
oracle_gap = mean_task[max_group utility] − max_group[mean_task utility].
Else PLASTICITY_BENCHMARK_NOT_IDENTIFIABLE → learned governor BLOCKED (§21).
Do not alter the architecture to force a positive result (§11.4).

## Prior expectation (honest)
Small models tend to have substitutable groups (cf. routing v1 collapse). If one
group (likely attention, the only position-mixing locus) is best for every task,
the gap is ~0 and the verdict is NOT_IDENTIFIABLE — a valid fail-closed outcome
that says: don't build the governor at this scale/task set yet.
