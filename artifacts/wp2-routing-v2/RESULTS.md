# WP-2 Typed Semantic Routing — RESULTS (Integration Act v2.0)

Oracle-gap 5 seeds, final 8 seeds. Preregistered before analysis
(`preregistration.md`). Data `oracle-gap/`, `final/`. Verdict `final/verdict.json`.

## VERDICT: `ROUTING_CAUSALITY_SUPPORTED`
The first full routing-causality pass in the CWC programme — the Act's central
objective, achieved at claim tier with the complete metric suite, causal
interventions, and lesion dissociations.

## §9 Oracle-gap gate — PASS (benchmark identifiable)
| Metric | Value | Gate |
|---|---:|---|
| mean relative oracle gain | 0.998 | ≥0.10 ✓ |
| gain 95% CI (lower) | 0.998 | >0 ✓ |
| oracle HARD − best-fixed HARD | 41 pp | ≥10 pp ✓ |
| oracle EASY exact | 1.000 | ≥0.95 ✓ |
| oracle HARD exact | 1.000 | ≥0.999 ✓ |
| oracle budget violations | 0 | =0 ✓ |

DIRECT_ONLY solves EASY (1.00) but **fails HARD structurally** (0.004) — the
local-window-1 path cannot reach the displaced fields. The two paths are
physically, not just indexically, different.

## §10 Isolation gates — PASS
parser subject/relation/object/polarity ≥ 0.99, tuple 1.00 (≥0.97); renderer
(gt state) ≥ 0.99; DirectPath EASY 1.00 (≥0.99), HARD 0.004 (≤0.70). Each
function verified in isolation before integrated routing.

## §12 Routing causality — PASS (8 seeds, controller trained label-free)
| Metric | Value | Gate |
|---|---:|---|
| route balanced accuracy | 1.000 | ≥0.85 ✓ |
| route AUROC | 1.000 | ≥0.90 ✓ |
| NMI(R;T) 95% CI (lower) | 1.000 | ≥0.25 ✓ |
| CRE (forced-wrong/forced-correct) | 1813× | CI>0 ✓ |
| shuffling-loss ratio | 873× | CI>0 ✓ |
| learned − random (paired CI) | [−0.475, −0.475] | <0 ✓ |
| learned − shuffled (paired CI) | [−0.458, −0.458] | <0 ✓ |
| budget violations | 0 | =0 ✓ |

The controller was trained **without task labels** — `need_score` regresses the
per-sample loss reduction the semantic path buys `(direct_loss − sem_loss)`, so
top-K spends the scarce semantic budget on exactly the HARD inputs. Learned
routing matches the oracle (learned loss 0.009 vs oracle ~0.001, random ~0.48),
and every causal intervention confirms the route — not stable selection —
produces the benefit: forcing the wrong route is 1813× worse; permuting the
learned decisions (same frequencies) is 873× worse.

## §13 Lesions — causally separable (comprehension / transmission / production)
| Lesion | analogue | syntax valid | tuple correct | signature |
|---|---|---:|---:|---|
| none (intact) | — | 1.000 | 1.000 | baseline |
| renderer_off | Broca-like (production) | **0.000** | 0.000 | production destroyed, parser tuple intact |
| semantic_state_permuted | Wernicke-like | **1.000** | 0.003 | fluent syntax, wrong meaning (high FNR) |
| subject_object_swapped | conduction-like | 1.000 | 0.000 | meaning wrong in the predicted direction |
| polarity_corrupted | targeted | 1.000 | 0.000 | polarity flipped, else valid |

The dissociation is clean: **every semantic lesion keeps syntax valid while
destroying meaning; the production lesion (renderer_off) destroys syntax.**
This proves functional separation of comprehension, transmission, and
production in the typed path.

## Compute (§15)
Semantic path cost > direct path; controller overhead / total ≤ 5%; the four
K-budget modes are FLOP-matched by construction (identical K). Energy EXCLUDED
(INSTRUMENT_INVALID upstream).

## Claim boundary
### Supported (claim tier)
"The controller learned input-dependent allocation between a cheap direct path
and a costly semantic path under a binding compute capacity, and causal
interventions confirmed that the routing decision — not merely stable selection
— produced the measured benefit." Meaning is preserved (deterministic output
→ tuple round-trip) and expensive computation is spent only where necessary.
### Not supported / not tested
- Compute-equivalent Pareto vs MoE / MoD / dynamic-depth (Act A7) — NOT_TESTED.
- Transfer across representations, continual adaptation (A6) — NOT_TESTED.
- RCFR (A4-5) — BLOCKED until now; UNBLOCKS with this verdict (§18).
- Independent replication (A8) — not self-certifiable.
- Energy efficiency — prohibited (INSTRUMENT_INVALID).

## Next isolated task (§18, now unblocked)
Sequence-level RCFR with a fixed low-rank primitive bank
`ΔW(r) = Σ_m c_m(r) U_m V_mᵀ` (controller emits only the coefficients c(r)) —
NOT full token-level generation of A(r), B(r). Governed by
`docs/RCFR_FALSIFICATION_CONTRACT.md`.
