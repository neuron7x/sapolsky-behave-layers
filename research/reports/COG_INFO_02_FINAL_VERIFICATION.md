# COG-INFO-02 — Final Verification Record

**Date:** 2026-08-11

## Scientific boundary

Verdict: `DECISION_RELEVANT_INFORMATION_GOVERNOR_QUALIFIED_SYNTHETIC_NARROWED`.

Authority: `DECISION_INFORMATION_ALLOCATION_PRIMITIVE_ONLY`.

The qualified object is the decision-relevant information-allocation primitive over an
explicit surviving-world set, an explicit immediate decision map, and certified
per-action information-rate lower bounds. It is not a causal-model truth oracle and it
does not establish real-world planning value.

## Confirmatory evidence

Frozen design: 12 families D0-D11, 128 cases/family/cohort, PRIMARY seed namespace base
104201 and fresh internal REPLICATION base 204201, alpha 0.01, target power 0.95.

- All D0-D11 cells: 128/128 pass independently in PRIMARY and REPLICATION.
- D0 all-same-decision: zero acquisition in 256/256 pooled cases.
- D1 same-decision zero-rate trap: legacy model-maximin blocked 256/256; the
  decision-relevant governor selected the decisive probe 256/256.
- D2 cross-decision zero-rate: zero false spend.
- D11: strictly lower necessary-cost bound in 256/256 pooled cases; legacy/new median
  ratio 9.775411561777831, range 6.25391407446785 to 17.007066704565204.
- Semantic gate self-test: 6/6 frozen authority/novelty mutations killed.

## Integration verification

PASS:

- `python scripts/cog_info02_gate.py --self-test`.
- `python scripts/cog_info02_gate.py`.
- focused cognitive-core suite: 52 passed.
- full repository collection: 490 tests collected, zero collection errors.
- `make -f Makefile.cwc verify-evidence`: every checksum-bearing evidence bundle PASS.
- `scripts/cog_plan01_gate.py --self-test`: 7/7 killed.
- `scripts/cog_memory01_gate.py --self-test`: 6/6 killed.
- `scripts/cog_epistemic01_gate.py --self-test`: 6/6 killed.
- `scripts/doc_status_gate.py`: 67 claims, 67 hypotheses, zero orphans.
- `scripts/verdict_binding_gate.py`: PASS.
- `scripts/research_execution_gate.py`: PASS.
- `scripts/research_ops_gate.py`: PASS.
- `scripts/truth_gate.py`: PASS.
- `scripts/technical_quality_gate.py`: PASS.
- `git diff --check`: PASS.

Not claimed:

- a complete behavioral repository pytest PASS. A full `python -m pytest -q` run was
  attempted with a 300-second execution budget and timed out after the progress display
  had reached 14% and continued beyond it, with no final pytest summary. Therefore no
  full-suite PASS is asserted.

## Tooling defect discovered during verification

The legacy wrapper `scripts/cog_epistemic01r_gate.py` had drifted to an older R1 schema
and caused a stale test failure. The authoritative current gate
`scripts/cog_epistemic01_gate.py` was already correct. The legacy wrapper was repaired to
preserve the parent-negative checks while delegating current R1 semantic validation to
the canonical gate. `tests/test_cog_epistemic01r_gate.py` then passed 2/2. This was a
software-governance repair; no scientific result or frozen artifact was changed.

## Novelty / promotion boundary

Novelty remains `UNKNOWN_OVERLAP_CONCEDED`. The candidate flagship thesis must survive a
separate public matched-compute benchmark and external prior-art audit. Semantic causal
truth, real-world planning superiority, active causal control, large-model transfer,
production Pareto advantage and external third-party replication remain unqualified.
