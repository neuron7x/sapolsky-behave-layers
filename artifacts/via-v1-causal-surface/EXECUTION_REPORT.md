# CWC-VIA-01 — Execution Report

**Implementation commit:** `2d703c173bb07ec4f6fce6470ba7c695787863bd`
**Execution date (UTC):** 2026-08-09
**Execution class:** retrospective method validation; no scientific ascension authority.

## 1. Executed scope

The repository was modified on branch `agent/cwc-via-v1-execution` to add a fail-closed causal
identification substrate and a machine-checkable VIA dependency gate. No VIA-V2–VIA-V7 runtime
mechanism was implemented because the pre-existing WP18 kill rule remains binding.

The implementation adds:

- exhaustive potential-outcome replay contracts;
- randomized intervention assignment;
- context/action causal utility aggregation;
- IPS and doubly-robust policy-value estimators;
- group-preserving cross-fitting;
- interaction-destroyed and collapsed-context structural nulls;
- deterministic context-permutation diagnostics;
- a retrospective adapter over sealed WP18/WP19/AC1 evidence;
- a VIA dependency-DAG status resolver;
- a fail-closed VIA gate.

## 2. Re-analysis result

| bundle | plugin gap | corrected `G_lo` | measured `c_route` | routable by frozen rule |
|---|---:|---:|---:|---|
| WP18 prose / tied K | +0.000000 | -0.200420 | 0.000600 | No |
| WP18 code / tied K | +0.000000 | -0.170896 | 0.000600 | No |
| WP19 prose / untied depth | +0.003706 | -0.484098 | 0.000600 | No |
| WP19 code / untied depth | +0.000000 | -0.233799 | 0.000600 | No |
| AC1 synthetic positive | +0.624146 | +0.619550 | 0.000600 | Yes |

The new causal implementation reproduces the frozen real-workload certificate direction exactly.
Both structural nulls have zero oracle gap to numerical tolerance. The synthetic positive control
remains positive.

**Verdict:** `VIA_V1_METHOD_VALIDATED_ASCENSION_BLOCKED`.

This means the engineering method is internally coherent against existing sealed evidence. It does
**not** mean VIA-V1 has scientifically passed. A new admissible, preregistered causal study is still
required.

## 3. Verification executed

### New VIA tests

`python -m pytest -q tests/via`

Result: **14 passed**.

### Existing programme gates

- `scripts/architecture_gate.py` — PASS
- `scripts/hermeticity_gate.py` — PASS
- `scripts/complexity_gate.py` — PASS
- `scripts/inference_integrity_gate.py` — PASS
- `python -m scripts.verdict_binding_gate` — PASS
- `scripts/via_gate.py` — PASS

### Existing regression tests executed

- readiness oracle: 17 passed
- verdict-binding tests: 9 passed
- technical-quality gate tests: 4 passed
- truth-gate tests: 2 passed
- data-asset audit tests: 9 passed
- adaptive-value theory: 21 passed
- admissibility conformance: 8 passed
- coherence audit: 14 passed
- neuron information budget: 24 passed
- value-information tests: 8 passed

Total explicitly completed in this execution record: **130 tests passed**.

## 4. Environment limitations

Execution container:

- Python `3.13.5`
- Torch `2.10.0+cpu`
- CUDA unavailable

The repository itself targets a different frozen environment, including `torch==2.13.0`. Therefore
this container was used only for code-level, statistical, artifact, and CPU-compatible verification;
it is **not** evidence for GPU conditional execution or production inference behavior.

An attempted full non-CUDA pytest collection was blocked by environment dependencies absent from the
container (`rustbpe`, `tomli`, `hypothesis`, `pyarrow`). An attempted `uv sync --frozen` could not
repair the environment because the execution container had no external DNS/network access. These are
reported as **UNEXECUTED/ENVIRONMENT_BLOCKED**, not repository test failures.

## 5. Epistemic timing note

During development, the retrospective re-analysis was executed before the implementation commit was
created. Therefore the new `PREREGISTRATION.md` is **not represented as a prospective blind
preregistration**. This is harmless for the stated class—method validation against already known,
sealed evidence—but it would be invalid to use this run as new confirmatory evidence.

Any future VIA-V1 scientific run must commit/freeze its protocol before outcomes are inspected.

## 6. Scientific frontier after execution

```
VIA-V1  BLOCKED — method ready; no new admissible positive causal evidence
VIA-V2  BLOCKED_BY_ANCESTOR
VIA-V3  BLOCKED_BY_ANCESTOR
VIA-V4  BLOCKED_BY_ANCESTOR
VIA-V5  BLOCKED_BY_ANCESTOR
VIA-V6  BLOCKED_BY_ANCESTOR
VIA-V7  BLOCKED_BY_ANCESTOR
```

The correct next action is not to implement the hierarchy. It is to define one scientifically
distinct candidate mechanism/workload family, freeze it prospectively, run a cheap causal pilot,
and apply the existing routability economics before any architecture spend.
