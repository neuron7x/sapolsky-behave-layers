# ADR-0002 — WP-2 routing gate mechanism & training/eval compute regime

Status: ACCEPTED (2026-07-16). Scope: first causal block-routing experiment
(`experiments/wp2_routing_v1/`). Governs Act Phase D.

## Decision 1 — one gate mechanism: straight-through top-K
Act D4 requires exactly one mechanism. Chosen: **straight-through hard top-K**
over per-block execute scores.

Alternatives weighed:
- Hard-concrete / L0 gates: give a soft budget in expectation, not an *exact*
  per-sequence K. Act D3 demands a hard budget (FAIL_CLOSED on violation);
  exact K is native to top-K, awkward for hard-concrete.
- Gumbel-softmax sampling: stochastic at inference; Act D4 wants deterministic
  eval and a simple negative control. Top-K argmax is deterministic.

Straight-through top-K wins on all four Act D4 criteria: hard evaluation,
exact budget, deterministic inference, simple negative control (freeze the
same controller → E2), low controller cost (one small MLP scoring L blocks).

Forward (train): `g = hard_topk_mask + (p − p.detach())`, `p = softmax(scores)`;
`h_{l+1} = h_l + g_l · F_l(h_l)`. Gradient reaches the controller through `p`.
Forward (eval): hard top-K, skipped blocks are not computed at all (real skip),
`h_{l+1} = h_l` exactly (residual identity, Act D5).

## Decision 2 — equalized training compute, matched eval compute
The failure condition "candidate wins only via a larger train budget" (Act C3)
is structurally eliminated: **during training all K-budget configs
(random/frozen/learned/fixed_depth) compute all L blocks and gate the
contribution to exactly K** — so their training FLOPs are identical by
construction, differing only in *where* the K-hot mask points and whether a
controller learned it. **At evaluation all four actually skip to exactly K
blocks** (real compute saving), so eval active-FLOPs match exactly. The causal
claim rests on eval quality at matched eval-compute; the selection policy is
the only free variable. Dense (E0) runs all L at train and eval — quality
ceiling, not a compute-matched comparator.

Consequence: training compute is NOT the saving; the saving is at inference.
This is stated openly in RESULTS and is the standard train-dense/infer-sparse
regime. It makes the comparison strictly fairer, not weaker.

## Decision 3 — per-sequence routing, controller interface
Routing granularity is sequence × block (Act D1), not token-level (deferred to
a later phase). The controller is a small MLP scoring each block from
`[pooled_hidden_summary, normalized_layer_index]`; the remaining-budget
constraint from the Act D2 interface is realized exactly by the global top-K
(pick K of L). `pooled_hidden_summary` = mean over sequence positions of the
embedded input, computed once per sequence → controller FLOPs are tiny and are
counted against the candidate in parity.

## Invariants enforced by tests (Act §13)
dense == plain forward (bit-exact); skip == identity; budget never exceeded
(==K); random deterministic by seed; frozen has no grad/updates; learned params
do update; controller FLOPs counted; routing counters correct; eval
deterministic; checkpoint round-trips controller state.
