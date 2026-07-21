# wp12_prereg_integrity — RESULTS

**Verdict: `PREREG_INTEGRITY_CLEAN`.** Tier: META — preregistration integrity across all experiments (git ancestry). Preregistration:
`experiments/wp12_prereg_integrity/PREREGISTRATION.md`. Full machine-readable result: `verdict.json` (this bundle).
Reproduce: `PYTHONPATH=. python -m experiments.wp12_prereg_integrity.src.*` then `make -f Makefile.cwc verify`.

## Result

Prereg first-add must be a strict git ancestor of the first result commit. Same-commit allowed only if disclosed (DEBT_REGISTER T0-PREREG). Any undisclosed same-commit or result-before-prereg is a violation.

This is a rigor/meta artifact of the expert-hardening run (WP7-WP13); its numbers are asserted by
the experiment's tests and checksummed here. See `docs/publication/PROGRAMME_SUMMARY.md` §4 and
`docs/publication/THREATS_TO_VALIDITY_AND_RED_TEAM.md` for how it fits the whole programme.
