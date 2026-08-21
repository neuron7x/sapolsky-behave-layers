# Research Roadmap

## P0 — Decision-Gradient Computing (DGC)

DGC is the primary next implementation/research objective. Status: `RESEARCH_HYPOTHESIS / ENGINEERING_CANDIDATE`; empirical claim `CWC-DGC-H1` is `NOT_TESTED`. The programme must execute the ordered ACT-00..ACT-27 contract in `docs/DGC_INTEGRATION_AND_VERIFICATION_PROTOCOL.md`, starting with the synthetic oracle preregistration in `experiments/dgc_01/PREREGISTRATION.md`.

Promotion is blocked until DGC beats the best preregistered fixed/uncertainty/cost-quality baseline on the frozen primary endpoint under matched budget, with anti-gaming and catastrophic-regret guardrails intact. Existing CWC epistemic authority is reused; DGC is an online compute-governance layer, not a replacement for `cwc.epistemics` or the existing programme-level adaptive-computation admissibility gate.

## Phase 0 — Repository authority

Exit criteria:

- normative documents complete;
- schemas validate;
- deterministic smoke test passes;
- CI and local commands agree;
- no scientific performance claim.

## Phase 1 — Causal microbenchmarks

Executed against the `karpathy/nanochat` control organism per
`research/EXPERIMENTAL_SUBSTRATE_NANOCHAT.md` (`CWC-EXPSUB-NANOCHAT-001`). WP-0 baseline fixation
is executed; WP-1 through WP-7 are preregistered and pending. Local hardware (RTX 3050, 4 GB) bounds
execution to smoke and micro-experiments — see that document's hardware boundary section before
claiming any reproduced result.

Mechanisms tested separately:

1. local–global sparse communication;
2. conditional expert routing;
3. bounded episodic memory;
4. wiring-cost regularization;
5. prune–grow structural adaptation.

Each mechanism must beat or match a budget-equivalent baseline on at least one preregistered task without degrading the protected metrics beyond tolerance.

## Phase 2 — Pairwise composition

Test interaction terms:

- topology × routing;
- routing × memory;
- memory × adaptive budget;
- topology × plasticity.

A composed system is retained only when the interaction is non-negative or its trade-off is explicitly useful.

## Phase 3 — Integrated kernel

Train a compact language or multimodal sequence model under the complete resource objective. Required reports:

- Pareto frontier;
- route stability;
- expert specialization;
- memory utility;
- topology evolution;
- robustness;
- calibration;
- total training and inference cost.

## Phase 4 — Agentic world coupling

Add typed tools and simulated environment actions. Separate language quality from state estimation, planning and actuation. Require rollback, permissions and action provenance.

## Phase 5 — External reproduction

Freeze the protocol, publish artifact hashes and obtain independent execution. No broad architectural superiority claim before this phase.
