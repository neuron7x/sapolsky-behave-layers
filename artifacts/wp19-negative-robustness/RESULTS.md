# WP19 — Robustness of the WP18 Negative (RESULTS)

**Act:** CWC-ASCEND-2026-01. **Prereg:** `bc18e68`, committed before any result.
**Verdict:** `NEGATIVE_IS_MECHANISM_SPECIFIC` — **the outcome that goes against my own prior
conclusion.** It is registered as it came out.

## What was tested
WP18 halted architecture work on a negative whose stated mechanism was *"the modal best compute
budget is the same in every difficulty bucket — there is no context × resource interaction."*
That finding came entirely from a **weight-tied block cycled over K ∈ {1,2,3}**, which has an
obvious interior optimum by construction. WP19 re-ran the question on a structurally different
compute axis, everything else held fixed:

| | axis A (WP18) | axis B (WP19) |
|---|---|---|
| compute | weight-tied block applied K times | **untied depth**: L independent blocks |
| models | 1 model trained on all K | **one separately trained model per depth** |
| weight sharing | yes | **none** |
| corpora / splits / eval shards / difficulty signal / certificate / `c_route` | identical | identical |

18 independently trained models (2 workloads × 3 depths × 3 seeds), same 5 held-out eval shards.

## Result — the two findings must be separated
| workload | `G_lo` (λ=0) | `G_lo` (λ=0.3) | vs `c_route` 0.0006 | modal best depth by bucket |
|---|---|---|---|---|
| prose | −0.4841 | −0.4864 | fails | **easy = 2, med = 3, hard = 3** ← *differs* |
| code | −0.2338 | −0.2318 | fails | easy = 3, med = 3, hard = 3 (same) |
| positive control (synthetic AC1) | **+0.6195** | — | certifies ✅ | — |

**1. WP18's mechanism explanation is FALSIFIED (narrowed).** On prose with untied depth the
difficulty buckets do **not** all want the same compute: easy tokens are best served by depth 2,
medium and hard by depth 3. A genuine context × resource interaction exists on this axis. The
sentence *"there is no context × resource interaction"* was a property of the **weight-tied** axis,
not of the data, and is hereby narrowed to that axis.

**2. WP18's DECISION is unchanged — and reinforced.** The frozen G3 criterion is
`G_lo > c_route`, and it fails on **both** workloads on **both** axes. On the new axis the
certified gap is in fact *more* negative (−0.484 / −0.234 vs −0.200 / −0.171). The interaction that
exists is far too small and too noisy to certify: it cannot pay for the route decision, which is
the only thing the kill rule ever asked.

## Consequence for the ledger
- `CWC-RD3-real-workload-pilot` keeps status **NOT_SUPPORTED** — the claim it denies (a certifiable
  gap exceeding `c_route`) failed again, on an independent compute axis. Its *note* is amended: the
  "no interaction" explanation is narrowed to the weight-tied axis.
- The **WP18 kill rule stands as written.** Architecture work remains stopped, now on two
  structurally different compute axes rather than one.
- New claim `CWC-RD4-negative-robustness` records the split outcome precisely: decision robust,
  explanation axis-specific.

## Honest reading
This is a case where attacking my own negative changed something real: the *story* I told about why
real workloads are not identifiable was partly an artifact of my mechanism. A small interaction does
exist on real prose. It is simply worth far less than the decision costs — which is a different, and
more defensible, statement than "there is no interaction at all."

## Scope
No architecture claim. No L7 statement. Pilot-scale, from-scratch byte models on two corpora; this
says nothing about large pretrained models.
