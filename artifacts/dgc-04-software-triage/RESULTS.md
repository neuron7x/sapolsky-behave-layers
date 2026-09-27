# DGC-04 Real Software-Engineering Release-Triage Pilot — Results

Status: **SOFTWARE_TRIAGE_SUPPORTED_NARROW**.

## Anchored primary results

| Policy | Release accuracy | False passes | Validator calls |
|---|---:|---:|---:|
| B0 FULL | 1.000000 | 0 | 55 |
| B1 PATH ROUTER | 1.000000 | 0 | 24 |
| B2 DGC | 1.000000 | 0 | 15 |

DGC validator-call savings:

- vs B0 FULL: **72.7273%**;
- vs B1 PATH ROUTER: **37.5000%**.

Observed wall-time savings in this shared runtime:

- vs B0: 64.6391%;
- vs B1: 17.1700%.

Wall time is secondary/environment-specific; validator-call count is the primary compute proxy.

## Decision semantics

All 11 tasks were executed. Every failing task produced `RELEASE_DENY` with at least one fatal validator finding before DGC stopped. `CLEAN` required all five relevant validators and passed. No false pass occurred.

This is real repository verification work on disposable mutated copies. It supports the narrow DGC claim that once a fatal result makes the release action invariant, continuing unrelated verification has zero value for that **release decision**. It does not establish complete fault enumeration, LLM token savings, client savings, or external-router superiority.
