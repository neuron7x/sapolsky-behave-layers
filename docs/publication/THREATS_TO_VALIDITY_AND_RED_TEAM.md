# Threats to Validity & Red-Team Response

*The strongest attacks a hostile expert reviewer would make on this programme, each with an
evidence-based response: **addressed**, **conceded (scoped)**, or **cloud-blocked**. Every "see"
points to a committed, gated, checksummed artifact reproducible under `make -f Makefile.cwc verify`.*

## Summary posture

The programme makes **no architectural claim**. It is a value-of-information theory of adaptive
computation, validated on **two independent real trained mechanisms** (parameter-plasticity,
adaptive-compute), with **7 frozen negatives** and a **real-data boundary** that maps its own edge.
Its credibility rests on falsification discipline, not on positives.

## T1 — "It's all synthetic." (CONCEDED, scoped; partly ADDRESSED)

**Attack.** Every positive is on a synthetic benchmark; synthetic benchmarks can be engineered to
be identifiable.
**Response.** Conceded and central to the honest scope: tier labels say `SYNTHETIC` throughout.
But (a) the mechanisms are **real trained torch models**, not toy math; (b) we tested transfer to
**real data** (WP6) and reported the **negative** — the clean identifiability does NOT appear on
real byte-level LM per-token difficulty (`G_lo=−0.09`, positive control `+0.62`). We do not hide the
synthetic-ness; we mapped exactly where it breaks. `artifacts/wp6-real-lm/`.

## T2 — "Multiple comparisons: 17 positives at δ=0.05." (ADDRESSED)

**Attack.** Family-wise error inflates to ~0.56 over 17 tests.
**Response.** WP8 applies Bonferroni (family and ultra-conservative all-30) + Holm on top of the
proof-complete bound; every certificate positive survives (L4 `+0.029` at δ/30, AC1 `+0.619`).
Family-wise FPR ≤ 0.05 worst-case. `artifacts/wp8-family-wise-error/`.

## T3 — "The inference-certificate proof has a gap." (ADDRESSED)

**Attack.** The coverage proof budgets only `b+d`, missing the oracle-term concentration.
**Response.** Self-flagged in our own audit, then closed: WP7 implements the proof-complete
`b+2d` bound (both deviation terms union-bounded), Monte-Carlo FPR `≤ δ`, positives survive.
`docs/IDENTIFIABILITY_INFERENCE.md` (gap-closed note); `artifacts/wp7-certificate-hardening/`.

## T4 — "The certificate assumes per-context independence." (ADDRESSED — see P4)

**Attack.** The `sd/√|C|` deviation proxy assumes independence across contexts, never tested.
**Response.** Robustness Monte-Carlo under correlated per-context noise
(`artifacts/wp9-independence-robustness/`): the corrected bound's FPR is reported under violation;
independence is shown [load-bearing / not] with the measured coverage.

## T5 — "Some theorems are numerical, not proved." (ADDRESSED / CONCEDED, labeled)

**Attack.** "Six theorems proved" oversells; the coherence check is circular and the Pinsker
dichotomy is a sketch.
**Response.** Relabeled honestly in the audit: Theorems 1–5, 4′, RI-optimality, Efficiency-E are
**genuine proofs**; coherence "Theorem C" → **Audit C** (internal-consistency, de-circularized in
`artifacts/wp10-coherence/`); the Pinsker small-rate dichotomy is now **certified over N random
regular+critical instances** (`artifacts/wp11-pinsker/`), not four curated ones. What remains a
sketch is labeled a sketch.

## T6 — "Committed-greedy controllers, not rational-inattention optimal." (CONCEDED, documented)

**Attack.** The governors realise `V*(R)` only at high information; at low info they abstain and
fall well below the RI optimum (compute: 0.33 saturation at `I=0.085`).
**Response.** Documented, not gated: the ceiling `V*` holds everywhere; the low-info gap
(committed ≠ RI, widening with contexts) is reported in `artifacts/wp5-adaptive-compute-ratebridge/`.
A RI-trained controller would close it; we did not claim it.

## T7 — "Preregistration could be retrospective (HARKing)." (ADDRESSED / CONCEDED per case)

**Attack.** Preregs may be committed with results.
**Response.** A machine gate verifies every prereg is a **strict Git ancestor** of its results
(`artifacts/wp12-prereg-integrity/`); the honest exceptions (WP4, R3C) are labeled
`RETROSPECTIVE_PROTOCOL` in `DEBT_REGISTER`, not hidden. The two-mechanism arcs were all
preregistered-before-run.

## T8 — "Same author, no independent replication." (CONCEDED — not self-certifiable)

**Attack.** One author; L8 replication is untested.
**Response.** Conceded; `CWC-L8-replication` is `NOT_TESTED` and explicitly "not self-certifiable".
We provide a clean-room reproduction protocol and a checksummed evidence capsule so a third party
*can* replicate. `docs/reproducibility/CLEAN_ROOM_REPRODUCTION_PROTOCOL.md`.

## T9 — "GPU nondeterminism / tiny models / tiny corpus." (ADDRESSED, scoped)

**Attack.** Results may be seed/hardware artifacts; models are tiny; the real corpus is 66 KB.
**Response.** Every analysis is deterministic given committed raw seeds; all utilities are frozen
and checksummed; verdicts reproduce under `verify`. Model/corpus size is a scope limit
(stated), and the effect sizes are large relative to seed variance (WP5-P5 CIs). We claim nothing
at scale — that is L7.

## T10 — "No architectural advantage: this doesn't beat MoD/MoE." (CONCEDED — the whole point)

**Attack.** None of this shows an architecture that wins at equal compute.
**Response.** Correct and stated everywhere: `CWC-L7-pareto` is `NOT_TESTED` (cloud-blocked). The
programme is a **decision instrument and validated theory** for *whether* adaptive computation pays
on a given workload — the necessary groundwork *before* an L7 cloud run, not L7 itself. WP6 shows
that identifiability does not come free on real data, which is exactly why L7 is non-trivial.

## Residual honest gaps (not defended — recorded)

- **L7** (real-workload compute-equivalent Pareto) — cloud-blocked; the one decisive missing piece.
- **L8** (independent replication) — not self-certifiable.
- **Real-data identifiability at scale** — WP6 is a small negative; a positive at scale is L7.
- **RI-optimal learned controllers** — only committed-greedy shown.

The programme's claim is exactly its evidence: a falsification-disciplined, two-mechanism-validated,
statistically-hardened theory of when adaptive computation is identifiable — and an honest map of
where it is not.
