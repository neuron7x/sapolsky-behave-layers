# WP16 — Clean-room Release & Reproduction Spine (PREREGISTRATION)

**Act:** CWC-ASCEND-2026-01, gates G0/G1. **Commit:** built from `5a0924c`.
**Class ceiling:** this WP raises NO scientific claim tier. It is a *reproduction* gate — it can
only establish that the existing evidence reproduces from a clean checkout without the author's
local `.venv`. It cannot support L7/L8.

## Question
Does the CWC evidence programme reproduce its non-hardware verdict invariants when the full
canonical gate set is re-run in a **fresh environment built from `uv.lock --frozen`**, independent
of the author's on-disk `.venv`? (This closes the Act §1 audit boundary: the capsule shipped
without an exact `.venv`, so the stored test/coverage numbers had never been independently re-run.)

## Procedure (frozen before running)
1. Build a clean-room venv from `uv.lock --frozen` (gpu/cu128 extra, matching evidence provenance)
   plus the pinned `cwc-requirements-dev.txt`. No author cache, no undeclared wheels.
2. Run the canonical gates with the clean-room interpreter: `lint, typecheck, test, mutation,
   experiment-tests, validate-evidence, doc-gate, reproduce-primary`.
3. Emit a machine-readable `reproduction_report.json`: host, GPU, driver, CUDA, PyTorch, seeds,
   per-gate exit code + wall time, pytest skip counts **with reason codes**.
4. Regenerate `RELEASE_MANIFEST.json`, `SBOM.spdx.json`, `CITATION.cff` — machine-derived from
   `git` + `claim_registry.json` + `uv.lock` (no hand-maintained lists; fixes the drift the audit
   flagged).

## Acceptance gates (decision rule, frozen)
- **PASS** iff every non-hardware gate exits 0 in the clean-room venv AND `reproduce-primary`
  regenerates the primary verdict inside preregistered tolerance.
- Any skipped hardware (CUDA/GPU) test is recorded as **NOT_MEASURED**, never PASS.
- A **second independent host** is out of scope here (single-host environment) and is recorded
  NOT_MEASURED — it does not count toward or against the verdict.

## Kill rule (falsifier)
FAIL if reproduction requires author intervention, a local cache, a mutable dataset, an undeclared
dependency, or any undocumented manual step; or if any non-hardware verdict invariant changes.

## Prohibited extrapolations
- "independently replicated" (that is L8 — needs a *different operator*, not a fresh venv).
- any real-workload / L7 conclusion.
