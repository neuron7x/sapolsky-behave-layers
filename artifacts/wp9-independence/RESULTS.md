# wp9_independence — RESULTS

**Verdict: `INDEPENDENCE_ROBUST`.** Tier: META — corrected-bound coverage under cross-context correlation. Preregistration:
`experiments/wp9_independence/PREREGISTRATION.md`. Full machine-readable result: `verdict.json` (this bundle).
Reproduce: `PYTHONPATH=. python -m experiments.wp9_independence.src.*` then `make -f Makefile.cwc verify`.

## Result

Corrected-bound FPR on a tied null under cross-context correlated noise. FPR<=delta up to rho=0.9 => the per-context independence assumption is not load-bearing for validity (the b-slack over-covers). Worst case is the tied null.

This is a rigor/meta artifact of the expert-hardening run (WP7-WP13); its numbers are asserted by
the experiment's tests and checksummed here. See `docs/publication/PROGRAMME_SUMMARY.md` §4 and
`docs/publication/THREATS_TO_VALIDITY_AND_RED_TEAM.md` for how it fits the whole programme.
