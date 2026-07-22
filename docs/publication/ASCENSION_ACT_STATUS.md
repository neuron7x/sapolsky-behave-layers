# Ascension Act CWC-ASCEND-2026-01 — Execution Status

*Closure record for the technical ascension act. Machine-checkable: every row below points at a
committed, checksummed evidence bundle. Ledger: [`claim_registry.json`](../../claim_registry.json).
Adversarial review: [`THREATS_TO_VALIDITY_AND_RED_TEAM.md`](THREATS_TO_VALIDITY_AND_RED_TEAM.md).
Synthesis: [`PROGRAMME_SUMMARY.md`](PROGRAMME_SUMMARY.md).*

**Entry commit:** `5a0924c`. **Status commit:** this document's commit.
**Programme state: HALTED BY ITS OWN KILL RULE at WP18** — see §2.

## 1. Work-package status

| WP | Title | Gate | Status | Evidence |
|---|---|---|---|---|
| 16 | Clean-room release & reproduction spine | G0/G1 | ✅ **DONE** | `artifacts/wp16-cleanroom-release/` |
| 17 | Physical metrology & cost accounting | G2 | ✅ **DONE (mixed)** | `artifacts/wp17-metrology/` |
| 18 | Real-workload identifiability programme | G3/G5/G7 | ⛔ **KILL RULE FIRED** | `artifacts/wp18-real-workload-pilot/` |
| 19 | *(act: baseline matrix)* → executed as **negative-robustness** | — | ✅ **DONE** | `artifacts/wp19-negative-robustness/` |
| 20 | Causal autonomous controller | G4 | 🚫 **BLOCKED** (WP18 kill rule) | — |
| 21 | Physical sparse execution | G2/G6 | 🚫 **BLOCKED** (WP18 kill rule) | — |
| 22 | Confirmatory L7 Pareto trial | CWC-L7 | 🚫 **BLOCKED** (kill rule + cloud) | — |
| 23 | Scaling law / held-out prediction | — | 🚫 **BLOCKED** (depends on WP22) | — |
| 24 | Adversarial robustness / fail-closed | — | 🚫 **BLOCKED** (depends on WP20/21) | — |
| 25 | Independent replication | CWC-L8 | 🚫 **NOT SELF-EXECUTABLE** — requires a different operator | — |
| 26 | External standardization & adoption | L9 | 🚫 **NOT SELF-EXECUTABLE** — requires external users | — |

**Deviation from the act, declared:** WP19 was specified as the strong compute-matched baseline
matrix (MoD/MoE/recursive/etc.). Building that matrix *after* WP18's kill rule would have been
ceremony — a baseline comparison is only meaningful on a workload where routing can pay for itself.
The WP19 slot was therefore spent attacking the negative that halted the programme, which the act's
own §8 (`no post-test redesign`, adversarial discipline) makes the higher-value move. This is
recorded as a deviation, not presented as compliance.

## 2. Why the programme is halted

The act's WP18 kill rule, frozen in a separate commit before any data existed:

> *if both real workloads have `G_lo ≤ c_route`, stop architecture work and publish the negative
> boundary.*

| workload | axis A (weight-tied K) | axis B (untied depth) | `c_route` (measured, WP17) |
|---|---|---|---|
| prose (English, 158 KB train) | `−0.2004` | `−0.4841` | `0.0006` |
| code (Python, 908 KB train) | `−0.1709` | `−0.2338` | `0.0006` |
| synthetic positive control | `+0.6195` ✅ certifies | `+0.6195` ✅ certifies | — |

Two task families × two compute axes × two model scales × two sequence lengths × five held-out eval
shards. The certificate certifies the synthetic control in the same runs, so the null is real rather
than a dead estimator. **The halt is caused by evidence, not by budget.**

WP19 additionally **falsified the author's own explanation** of the halt (see T12 in the threats
doc): a genuine context × resource interaction *does* exist on real prose under an untied-depth
axis. What survives is the decision, not the story:

> **The interaction is worth less than the decision costs.**

## 3. What the act asked for and what was actually achieved

| Act requirement | Achieved | Honest gap |
|---|---|---|
| Reproduce from a clean checkout, no author environment | ✅ WP16: fresh `uv.lock --frozen` venv, 9/9 gates, primary verdict regenerated | Second independent host `NOT_MEASURED` (single-host) |
| Complete cost accounting incl. controller/dispatch | ✅ WP17: route cost **measured**, charged, and used as the WP18 threshold | `rho` is a lower bound (cheapest honest router) |
| FLOP ledger vs profiler ≤ 1% | ✅ **0.0000%** like-for-like at every operating point | profiler does not attribute SDPA FLOPs — disclosed, analytic-only term |
| Overhead p95 ≤ 2%, latency CV ≤ 3% | ❌ **not met on this hardware** (`CWC-RIGOR10`, frozen negative) | median overhead ≤ 1% does pass |
| Energy only with a validated meter | ✅ stays `INSTRUMENT_INVALID`; no zero-joule value synthesized | no meter available |
| ≥ 2 real workloads, immutable splits, contamination tests | ✅ WP18: 2 families, hash-split per source file, 5 eval shards each, contamination clean | pilot scale, both corpora from one repository |
| Prospective MDE / power / seed count before spending | ✅ WP18: sd, MDE, `n` needed, variance components recorded | — |
| Strong compute-matched baselines (MoD/MoE/...) | ❌ **not built** — blocked by the kill rule (deviation declared above) | — |
| Causal controller, sparse execution, L7 Pareto, replication, adoption | ❌ **not attempted** | blocked / not self-executable |

## 4. Level claim — stated plainly

The act's own criterion for anything above Principal is a **real compute-equivalent Pareto result
plus independent replication**. Neither exists. Therefore:

- **Claimed:** a falsification-disciplined, clean-room-reproducible, physically cost-accounted
  research programme that **halted itself on its own preregistered evidence** and then falsified its
  own explanation of that halt.
- **Not claimed:** Principal+ / Distinguished / Fellow standing, architectural advantage, energy
  efficiency, independent replication, or any statement about large pretrained models.

## 5. The prior question that now gates everything

> **Find a real workload whose context × resource interaction is large enough to pay for its own
> routing decision.**

Until such a workload exists, WP20–WP24 are unfalsifiable ceremony and WP25–WP26 are unreachable.
Candidate directions (none attempted; all beyond a 4 GB consumer GPU): tasks whose *per-instance*
compute demand varies by orders of magnitude — multi-step reasoning, retrieval-conditioned
generation, mixed-modality batches — rather than per-token byte prediction, where the measured
interaction is ~0.001 nats, the same order as the cost of deciding.
