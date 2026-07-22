# Threats to Validity & Red-Team Response

*The strongest attacks a hostile expert reviewer would make on this programme, each with an
evidence-based response: **addressed**, **conceded (scoped)**, or **cloud-blocked**. Every "see"
points to a committed, gated, checksummed artifact reproducible under `make -f Makefile.cwc verify`.*

## Summary posture

The programme makes **no architectural claim**. It is a value-of-information theory of adaptive
computation, validated on **two independent real trained mechanisms** (parameter-plasticity,
adaptive-compute), with **10 frozen negatives** and a **real-data boundary** that maps its own edge.
Its credibility rests on falsification discipline, not on positives. As of WP18 the programme's own
kill rule has **fired**: architecture work is stopped by evidence, not by budget (T11 below), and
WP19 then **falsified the author's own explanation** of that negative (T12).

## T1 — "It's all synthetic." (CONCEDED, scoped; partly ADDRESSED)

**Attack.** Every positive is on a synthetic benchmark; synthetic benchmarks can be engineered to
be identifiable.
**Response.** Conceded and central to the honest scope: tier labels say `SYNTHETIC` throughout.
But (a) the mechanisms are **real trained torch models**, not toy math; (b) we tested transfer to
**real data** three independent times and reported the **negatives**: WP6 (unigram difficulty,
`G_lo=−0.09`, control `+0.62`), WP14 (bigram difficulty — robust to the signal), and WP18 (**two
distinct task families**, prose + Python source, 1.07 MB, hash-split with 5 held-out eval shards
each, 2 scales x 2 sequence lengths, 24 models: `G_lo = −0.200 / −0.171` vs the *measured*
`c_route = 0.0006`). We do not hide the synthetic-ness; we mapped exactly where it breaks, and the
map is now the programme's governing constraint. `artifacts/wp6-real-lm/`,
`artifacts/wp14-real-lm-contextual/`, `artifacts/wp18-real-workload-pilot/`.

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

## T4 — "The certificate assumes per-context independence." (ADDRESSED)

**Attack.** The `sd/√|C|` deviation proxy assumes independence across contexts, never tested.
**Response.** WP9 Monte-Carlos the corrected bound's coverage under cross-context correlated noise:
FPR = 0.000 ≤ δ up to `ρ=0.9` (all shapes) — the independence assumption is **not load-bearing** for
validity (the `b`-slack over-covers even under strong correlation). `artifacts/wp9-independence/`.

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
**Response.** WP12 machine-verifies every prereg is a **strict Git ancestor** of its results: 14
experiments are `STRICT_ANCESTOR` (the two-mechanism arcs + WP6/7/8). Same-commit is allowed only if
**disclosed** — WP4 (DEBT_REGISTER) and the four rigor meta re-analyses (wp9/10/11/13), which this
run committed prereg+results together and which the gate itself caught and we disclosed (allowlist),
not hid. 0 undisclosed violations. `artifacts/wp12-prereg-integrity/`.

## T8 — "Same author, no independent replication." (CONCEDED — not self-certifiable)

**Attack.** One author; L8 replication is untested.
**Response.** Conceded; `CWC-L8-replication` is `NOT_TESTED` and explicitly "not self-certifiable".
We provide a clean-room reproduction protocol and a checksummed evidence capsule so a third party
*can* replicate. `docs/reproducibility/CLEAN_ROOM_REPRODUCTION_PROTOCOL.md`.

## T9 — "GPU nondeterminism / tiny models / tiny corpus." (ADDRESSED, scoped)

**Attack.** Results may be seed/hardware artifacts; models are tiny; the real corpus is 66 KB.
**Response.** Every analysis is deterministic given committed raw seeds; all utilities are frozen
and checksummed; verdicts reproduce under `verify-full` — including in a **clean-room venv built
from `uv.lock --frozen`, independent of the author's environment** (WP16: 9/9 gates, primary verdict
regenerated from scratch, hardware-gated tests recorded `NOT_MEASURED` never `PASS`). Corpus size is
no longer 66 KB: WP18 uses 1.07 MB across two task families with five held-out eval shards each and
an explicit contamination check. Model size remains a scope limit (stated). We claim nothing at
scale — that is L7. `artifacts/wp16-cleanroom-release/`.

## T10 — "No architectural advantage: this doesn't beat MoD/MoE." (CONCEDED — the whole point)

**Attack.** None of this shows an architecture that wins at equal compute.
**Response.** Correct and stated everywhere: `CWC-L7-pareto` is `NOT_TESTED` (cloud-blocked). The
programme is a **decision instrument and validated theory** for *whether* adaptive computation pays
on a given workload — the necessary groundwork *before* an L7 cloud run, not L7 itself. WP6 shows
that identifiability does not come free on real data, which is exactly why L7 is non-trivial.

## T11 — "The kill rule is a convenient excuse to stop." (ADDRESSED — it fired *against* the programme)

**Attack.** A self-authored programme that halts itself on its own negative is unfalsifiable
theatre: the author decides when to stop and calls it discipline.
**Response.** The rule was **frozen in a separate commit before any data existed** (`2798ea5`,
machine-verified strict-ancestor of the result commit by WP12), it names the exact numeric criterion
(`G_lo > c_route`, with `c_route` **measured** in WP17, not assumed), and it fires in the direction
that **stops the author's own architecture work** — the expensive, career-relevant, publishable
direction. A mandatory synthetic positive control certifies (`+0.6195`) in the same run, so the null
cannot be a dead estimator; instrument-sensitivity tests assert the certificate detects a planted
interaction and refuses a flat benchmark. `artifacts/wp18-real-workload-pilot/`.

## T12 — "The negative's explanation was an artifact of your own mechanism." (VALID — and we found it ourselves)

**Attack.** WP18 concluded "there is no context x resource interaction on real data", but every WP18
model was a **weight-tied** block cycled over K, which has an interior optimum by construction. The
finding could be an artifact of the mechanism, not a property of the data.
**Response.** **Correct, and WP19 confirmed the attack.** We re-ran the question on a structurally
different compute axis (**untied depth**: independent blocks, one separately trained model per
depth, no weight sharing; 18 models, same corpora/splits/eval shards/certificate). On real prose the
difficulty buckets do **not** all want the same compute — easy tokens prefer depth 2, harder tokens
depth 3. A genuine interaction **exists**. WP18's *explanation* is therefore falsified and narrowed
to the weight-tied axis (`CWC-RD3` note amended; `CWC-RD4` registered `SUPPORTED_NARROWED`).

What survived is the *decision*: `G_lo` fails `c_route` on **both** workloads on **both** axes, and
is *more* negative on the new axis (`−0.484 / −0.234`). The defensible statement is **not** "there
is no interaction on real data" — that is false — but **"the interaction is worth less than the
decision costs."** `artifacts/wp19-negative-robustness/`.

## Residual honest gaps (not defended — recorded)

- **A workload worth routing** — the *prior* gap that now gates everything: no real workload tested
  shows an interaction large enough to pay for its own routing decision. Until one exists, L7 and
  everything downstream is unfalsifiable ceremony.
- **L7** (real-workload compute-equivalent Pareto) — cloud-blocked **and** now evidence-blocked.
- **L8** (independent replication) — not self-certifiable. WP16's clean-room rebuild is *not* L8:
  a fresh environment is not a different operator.
- **Real-data identifiability at scale** — three negatives at pilot scale; a positive at scale
  remains untested.
- **Timing metrology** — the Act's `p95 ≤ 2%` / `CV ≤ 3%` gates are **not met** on the available
  consumer hardware (`CWC-RIGOR10`, frozen negative); median overhead does pass.
- **RI-optimal learned controllers** — only committed-greedy shown.

The programme's claim is exactly its evidence: a falsification-disciplined, two-mechanism-validated,
statistically-hardened theory of when adaptive computation is identifiable — and an honest map of
where it is not.
