# wp11_pinsker — RESULTS

**Verdict: `PINSKER_DICHOTOMY_CERTIFIED`.** Tier: META — Pinsker small-rate dichotomy certified over a random sample (de-curated). Preregistration:
`experiments/wp11_pinsker/PREREGISTRATION.md`. Full machine-readable result: `verdict.json` (this bundle).
Reproduce: `PYTHONPATH=. python -m experiments.wp11_pinsker.src.*` then `make -f Makefile.cwc verify`.

## Result

Regular random instances -> exponent ~1 (Theta(R)); constructed critical -> ~0.5 (Theta(sqrt R)). Addresses the 'curated numerics' critique with a random sample. Analytic note: for regular problems beta(0+)=sigma<inf follows from concavity + a strictly positive prior-optimal gap; the finiteness on the measure-zero critical manifold is where the sqrt law takes over. Still a numerical certification, not a closed proof of the general dichotomy.

This is a rigor/meta artifact of the expert-hardening run (WP7-WP13); its numbers are asserted by
the experiment's tests and checksummed here. See `docs/publication/PROGRAMME_SUMMARY.md` §4 and
`docs/publication/THREATS_TO_VALIDITY_AND_RED_TEAM.md` for how it fits the whole programme.
