# WP17 — Physical Metrology & Complete Cost Accounting (RESULTS)

**Act:** CWC-ASCEND-2026-01, gate **G2**. **Prereg:** `experiments/wp17_metrology/PREREGISTRATION.md`
(committed separately, `963ccd2`, before any measurement existed).
**Verdict:** `METROLOGY_LIMITED__PARETO_SURVIVES_PHYSICAL_ROUTE_COST`.

Mixed result, reported as measured. FLOP accounting is validated exactly; **timing metrology does
not reach the Act's specification on this host** and is frozen as a negative.

## Q1 — FLOP ledger vs profiler: **PASS (exact)**
Like-for-like (ledger's profiler-attributable subset vs `aten::mm`), all operating points:

| K | analytic (linear) | profiler `aten::mm` | rel. error |
|---|---|---|---|
| 1 | 19,660,800 | 19,660,800 | **0.0000%** |
| 2 | 38,535,168 | 38,535,168 | **0.0000%** |
| 3 | 57,409,536 | 57,409,536 | **0.0000%** |

**Instrument boundary (measured, disclosed):** `torch.profiler(with_flops=True)` attributes FLOPs to
`aten::mm` but **not** to `scaled_dot_product_attention` on CPU. The attention-core term
(1.1M–3.4M FLOPs, 5.60–5.85% of the forward) is therefore invisible to the profiler. Comparing the
*full* ledger against the *full* profiler total measures the **profiler's** coverage gap, not a
ledger error — both numbers are in `verdict.json`. The ledger arithmetic itself is exact.

## Q2 — Physical route-decision cost: **measured**
| controller | FLOPs / model-forward(K=1) | note |
|---|---|---|
| tabular AC2 (softmax over given context) | 0.000028 | presumes the context label is **given** — Act §8 forbids counting that as free |
| **encoder router** (must read input to infer difficulty) | **0.0006** | the deployable lower bound; wall-time ratio ≈ 0.19 |

WP6/WP14 established that on real data difficulty must be **inferred**, so the encoder router — not
the tabular table — is the honest `c_route`. Its cost is a **lower bound**: a realistic router on a
real workload is far more expensive.

## Q3 — Preregistered KILL-TEST on WP15: **PARETO_SURVIVES_PHYSICAL_ROUTE_COST**
Charging the measured route cost to the adaptive arm (fixed-K arms pay nothing):
adaptive advantage **+0.6249** at matched *total* compute **2.001** — above the frozen 0.05 survival
margin. `CWC-L7s-synthetic-pareto` stands; it was **not** an artefact of ignoring the controller.

**The kill-test was hardened after its own test caught it:** with a large route cost the comparison
silently *clamped* at the edge of the measured fixed-K frontier, so it could never kill — a test
that cannot fail. It now returns `PARETO_NOT_IDENTIFIED_BEYOND_MEASURED_FRONTIER` outside the
measured range (you cannot claim dominance over a baseline never measured at that budget). The
measured `rho` (0.0006) sits well inside the frontier, so the verdict above is unaffected.

## Q4/Q5 — Instrumentation overhead & latency stability: **FAIL on this host (frozen negative)**
Alternating `OFF→COUNTERS→COUNTERS→OFF`, fixed warm-up, 30 reps/window, **3 repeats** (a single run
of this gate is itself unstable — one lucky run is not evidence):

| metric | Act gate | batch 64 (preregistered) | batch 1024 (disclosed amendment) |
|---|---|---|---|
| overhead median | ≤1% | 0.70% ✅ | 0.35% ✅ |
| overhead p95 | ≤2% | 4.87% ❌ | 2.25% ❌ |
| latency CV (min/med/max over repeats) | ≤3% | 2.94 / 3.36 / **5.40%** ❌ | 0.64% (single) |

**Disclosed amendment:** batch 1024 was added because at batch 64 a step is sub-millisecond and p95
is dominated by OS/thermal jitter rather than instrumentation. The preregistered batch-64 result
**stands and is reported unchanged** — the amendment is additive, not a replacement.

**Honest conclusion:** the Act's timing gates (p95 ≤2%, CV ≤3%) are **not met** on this consumer
laptop (RTX 3050 Laptop, shared OS). The median-overhead gate *is* met. Timing metrology to Act
spec requires a quiesced, thermally-stable machine — recorded as a hardware boundary, exactly like
energy. Gate flakiness is reported by the instrument itself (`repeats` block in `verdict.json`).

## Q6 — Energy: **PASS (stays INSTRUMENT_INVALID)**
No validated meter on this host; the facade reports `available=False`. No zero-joule value was
synthesized.

## Scope / prohibited extrapolations
Real-workload compute-equivalent Pareto (**L7**) — unchanged, still cloud-blocked. Energy efficiency
of any kind. Generalisation of the measured `rho` beyond this model/host/batch regime.
