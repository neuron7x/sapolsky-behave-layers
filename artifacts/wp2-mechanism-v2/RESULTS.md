# WP-2 Mechanism-Separable Routing — RESULTS (Act v2.0 A2+A3)

8 seeds {0..7}, two stages. Task: mechanism-separable LOCAL/FAR, K=1 of
{E_A local, E_B far}. Data `raw_runs/`, stats `statistics/analysis.json`.
Preregistered: `../../experiments/wp2_mechanism_v2/PREREGISTRATION.md` (before run).

## A2 — Oracle-separation gate: **PASS** (both stages)
| Stage | mean relative oracle gain | 95% CI | oracle acc | best-fixed acc | acc gap |
|---|---:|---|---:|---:|---:|
| A (marker) | 0.999 | [0.999, 0.999] | 1.000 | 0.517 | 48.3 pp |
| B (inferred) | 0.999 | [0.999, 0.999] | 1.000 | 0.515 | 48.5 pp |

The benchmark is **validly mechanism-separable** — the first CWC routing task
where a fixed route provably fails one family (fixed-E_A: LOCAL 1.00 / FAR 0.00;
fixed-E_B: LOCAL 0.05 / FAR 1.00; oracle: 1.00 / 1.00). Routing is now
**identifiable**. This is exactly what WP-2 v1/v1.1 lacked.

## A3 — Routing causality: **NOT_SUPPORTED at claim tier (reliability), but
mechanism causally demonstrated on the majority of seeds**

### Per-config (mean over 8 seeds, answer-CE / accuracy)
| Config | Stage A ce | Stage A acc | Stage B ce | Stage B acc |
|---|---:|---:|---:|---:|
| dense (ceiling) | 0.002 | 1.000 | 0.002 | 1.000 |
| random | 2.089 | 0.510 | 2.085 | 0.510 |
| frozen | 1.975 | 0.517 | 1.980 | 0.515 |
| fixed | 2.530 | 0.475 | 2.511 | 0.479 |
| oracle | 0.002 | 1.000 | 0.002 | 1.000 |
| **learned** | **0.608** | **0.829** | **0.398** | **0.892** |

Learned beats random, frozen, and fixed on the mean (paired CIs below 0), but
the distribution is **bimodal**:

### The decisive finding — bimodal convergence
| Stage | learned solved (acc>0.9) | collapsed |
|---|---|---|
| A (marker) | **5/8** seeds | 3/8 |
| B (inferred) | **6/8** seeds | 2/8 |

**On solved seeds, routing causality is complete and decisive:**
- normalized MI `I_norm(R;T) = 1.000` (route fully determined by task);
- route↔label agreement `= 1.000` (matches the oracle exactly);
- permutation-test `p = 0.001`;
- **interventions** (Stage A solved seeds): force-correct ce 0.004 (≈oracle),
  force-**incorrect** ce 8.28 → ratio **2218×**; module-swap (E_A↔E_B, keep
  routes) ce 8.28 (predicted catastrophic failure); route-permute ce 4.02
  (destroys the advantage). Every causal criterion is met.

On the collapsed seeds the controller degenerates to a constant policy
(I_norm ≈ 0, permutation p = 1.0), identical to frozen.

### Why A3 does not pass at claim tier
Act A3 requires effect consistency in ≥80% of seeds and permutation p ≤ 0.01
on the aggregate. Consistency is 62.5% (Stage A) / 75% (Stage B) — below 80% —
and the collapsed seeds push `max permutation p` to 1.0. Verdict:
**NOT_SUPPORTED (reliability)**. The failure mode is **optimization** (a
straight-through top-1 collapse attractor), not the routing mechanism: where
the controller escapes the basin, routing is causally real and perfect.

This is a qualitative advance over WP-2 v1/v1.1, where learned routing NEVER
routed adaptively (route divergence ≈ 0 on every seed). Here it achieves
oracle-equivalent adaptive routing on the majority of seeds.

## Claim boundary
### Supported
- The benchmark is mechanism-separable (oracle gap 99.9%, 48 pp).
- Learned adaptive routing is causally real where the controller converges
  (I_norm=1.0, interventions confirm, matches oracle) — the FIRST positive
  routing signal in this programme.
### Not supported (yet)
- RELIABLE routing causality at claim tier — 25–37% of seeds collapse.
- Any Pareto/efficiency claim (no compute-equivalent evaluation vs MoE/MoD).
### Prohibited wording
- "CWC routing works" (unqualified) — it works on a majority of seeds, not all.

## Next decisive experiment (to pass A3, then unblock RCFR)
Add a load-balancing / entropy-regularization auxiliary loss (the standard
MoE anti-collapse fix) and/or controller-init changes, then re-run 8 seeds. A3
passes iff ≥80% of seeds converge to adaptive routing with the interventions
still confirming causality. Only then does Act A4 (RCFR) unblock.
