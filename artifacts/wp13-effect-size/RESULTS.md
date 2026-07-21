# wp13_effect_size — RESULTS

**Verdict: `EFFECT_SIZES_CI_POSITIVE`.** Tier: META — effect sizes, bootstrap CIs, retrospective power for the positives. Preregistration:
`experiments/wp13_effect_size/PREREGISTRATION.md`. Full machine-readable result: `verdict.json` (this bundle).
Reproduce: `PYTHONPATH=. python -m experiments.wp13_effect_size.src.*` then `make -f Makefile.cwc verify`.

## Result

Seed-bootstrap 95% CI of the oracle gap complements the one-sided G_lo. Both positives have CI lower bound > 0 and n_seeds >= sample-complexity n*. Standardized effect = gap/sigma.

This is a rigor/meta artifact of the expert-hardening run (WP7-WP13); its numbers are asserted by
the experiment's tests and checksummed here. See `docs/publication/PROGRAMME_SUMMARY.md` §4 and
`docs/publication/THREATS_TO_VALIDITY_AND_RED_TEAM.md` for how it fits the whole programme.
