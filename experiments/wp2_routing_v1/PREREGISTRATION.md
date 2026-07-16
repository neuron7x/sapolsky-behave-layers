# WP-2 Routing v1 — PREREGISTRATION

Registered 2026-07-16, BEFORE any router/model code is written (Act Phase C).
Protocol authority: CWC Claude Fable Execution Act v1.0.0 §6–§11.
This document is committed before Phase D; its hypotheses, controls, metrics,
and stopping rules are frozen. Deviations are appended to `deviations.jsonl`,
never edited in retrospectively.

## Preconditions (all met at registration)
- BASELINE_INTEGRITY = PASS (master == 92d63d4e).
- WP1_METROLOGY = PASS_WITH_ENERGY_EXCLUDED (overhead gate cleared; energy
  INSTRUMENT_INVALID → energy is NOT a metric in this experiment).
- Only after these did this experiment open (Act §2 ordering).

## Central causal question (one question, Act §17)
At an equal active-compute budget of K executed blocks out of L, does a
**learned** controller that chooses *which* K blocks to run achieve lower
validation loss than (a) a **random** compute-matched controller and (b) a
**frozen** (untrained, same-init) controller?

### H1 (primary)
`val_loss(learned) < val_loss(random)` AND `val_loss(learned) < val_loss(frozen)`,
paired across seeds, after active-FLOP parity within 1% and counting controller
FLOPs against the candidate.

### H2 (secondary)
The learned controller forms a stable, non-collapsed block-selection policy
(normalized routing entropy not at either extreme; no dead-layer fraction = 1;
seed-stable utilization) without controller overhead erasing the benefit.

### Failure conditions (H1 NOT supported if any hold) — Act C3
- learned ≈ random (paired 95% CI of the delta includes 0);
- learned ≈ frozen (same);
- quality gain vanishes after FLOP normalization;
- controller overhead ≥ the compute saving it buys;
- router collapse (all sequences pick the same K blocks → equivalent to fixed-depth);
- delta unstable across seeds (sign flips);
- candidate wins only via a larger training budget.

A NULL result (learned no better than controls) is a **valid negative
completion** and will be reported as `ROUTING_NOT_SUPPORTED`, not hidden.

## Task (fixed) — in-context associative recall (induction)
Rationale: this task provably requires composing information across ≥2
specific layers (induction-head mechanism), so *which* blocks execute is
causally load-bearing — the strongest available mechanism for block-choice to
matter, on a fast, reproducible, no-external-data synthetic distribution.
This is an ALGORITHMIC task; generalization to natural language (Act L5) is
explicitly OUT OF SCOPE. Claim ceiling: "learned block-routing helps / does
not help on this task at this scale."

- Vocabulary: `vocab_size = 64` symbols (special tokens included).
- Each sequence: a stream of `(key, value)` pairs drawn i.i.d., followed by a
  query key that appeared earlier; the target at the query position is that
  key's most-recent value. Non-query positions predict next-token as usual;
  loss is reported BOTH as full-sequence next-token CE and as query-position
  CE (the discriminative metric).
- `seq_len = 128`, pairs use disjoint key/value symbol ranges, query is marked
  by a dedicated token. Generator is seeded and hashed into the manifest.
- Train/val split by generator seed stream; val is 2000 fixed sequences.

## Model (fixed) — minimal self-contained transformer
DEVIATION (recorded, argued): the experiment uses a minimal self-contained
pre-norm transformer block (RMSNorm + causal MHA + MLP, standard residual),
NOT nanochat's production `Block` (which carries smear/backout/rotary/GQA/FA3
scaffolding that would make dense-equivalence and exact-identity-skip hard to
prove and adds FA3-hardware skips). Act D1's intent — fixed-topology adaptive
*block* routing with real compute skip and residual identity — is satisfied by
a standard transformer block. The nanochat baseline is untouched (Act §3.2).
The WP-1 instrumentation being leveraged (FLOP ledger, routing counters,
RunMeter) is the real, qualified one.

- `L = 8` blocks, `d_model = 128`, `n_head = 4`, `d_ff = 512`, `seq_len = 128`.
- Budget `K = 4` active blocks per sequence (50% compute).
- Skip = exact residual identity `h_{l+1} = h_l`; execute = `h_l + F_l(h_l)`.

## Controller (fixed) — one gate mechanism
Straight-through top-K over per-block execute scores (Act D4 picks ONE
mechanism; ADR-0002 records the choice and why). Input per block: pooled
hidden summary, normalized layer index, remaining budget. Hard top-K selects
exactly K blocks per sequence (hard budget, FAIL_CLOSED on violation, Act D3).
Inference is deterministic (argmax top-K, no sampling).

## Controls (Act §8) — same backbone init, data order, optimizer, tokens, K
- **E0 dense**: all L blocks active. Quality ceiling / Pareto reference (NOT
  compute-matched — uses full L).
- **E1 random**: exactly K blocks, chosen by a fixed per-(seed,sequence-hash)
  RNG. Tests adaptivity vs random thinning.
- **E2 frozen**: learned-controller architecture, same init, weights FROZEN.
  Isolates the contribution of *learning* the policy.
- **E3 learned**: same backbone, same K, controller trainable. Candidate.
- **E4 fixed-depth**: deterministic fixed K blocks (first K). Tests adaptivity
  vs a static depth cut.

## Compute equivalence (Act §9)
Primary comparators E1/E2/E3/E4 share identical hard budget K, so backbone
active FLOPs match exactly by construction. Controller FLOPs are counted into
E2/E3 and reported; E1/E4 have ~0 controller FLOPs. Parity criterion
`|C_A − C_B| / max(C_A,C_B) ≤ 0.01` is checked on total active inference FLOPs
including controller. Reported: total/trainable/active/controller params.

## Seeds & runs (Act §10)
- Pilot (this session): **3 seeds** {0,1,2}, `claimable = no` (pipeline
  validation + effect direction).
- Claim tier: **≥5 seeds**. If local hardware/time insufficient → deliver
  implementation + 3-seed pilot + cloud-ready launch pack, verdict `PILOT_ONLY`.
- Fixed training budget per run (identical tokens across all configs),
  preregistered in `protocol.yaml`. Checkpoint selection: lowest val loss.

## Metrics (Act §10 G4)
quality: full-seq val CE, query-position val CE (primary discriminator).
compute: logical active FLOPs, controller FLOPs, active blocks/sequence.
systems: GPU + E2E latency, peak VRAM allocated/reserved, throughput.
routing: normalized entropy, Gini, per-layer utilization, dead-layer fraction,
budget violations (must be 0), seed stability of utilization.
energy: EXCLUDED (INSTRUMENT_INVALID).

## Statistics (Act §11)
Unit of inference = seed. Per config: raw per-seed val losses, mean, median,
sd, bootstrap 95% CI. Paired deltas learned−random, learned−frozen,
learned−fixed. Effect size (paired). `ROUTING_SUPPORTED` only if Act H3's
seven conditions all hold. Verdict ∈ {ROUTING_SUPPORTED, ROUTING_NOT_SUPPORTED,
ROUTER_COLLAPSE, COMPUTE_MISMATCH, INSUFFICIENT_SEEDS, MEASUREMENT_INVALID,
PILOT_ONLY}.

## Stopping rules
- Any Act §15 fail-closed condition → stop, report, do not advance.
- Budget violation > 0 in any run → MEASUREMENT_INVALID for that config.
- No threshold is chosen or altered after seeing final results.
