# wp10_coherence — RESULTS

**Verdict: `COHERENCE_DECIRCULARIZED_0_CONTRADICTIONS`.** Tier: META — de-circularized coherence: recorded status vs certificate sign from real artifacts. Preregistration:
`experiments/wp10_coherence/PREREGISTRATION.md`. Full machine-readable result: `verdict.json` (this bundle).
Reproduce: `PYTHONPATH=. python -m experiments.wp10_coherence.src.*` then `make -f Makefile.cwc verify`.

## Result

Non-circular: every G_lo is recomputed from committed raw seeds (not a hand-encoded matrix). Both directions: SUPPORTED<->G_lo>0 and NOT_SUPPORTED<->G_lo<=0 (RD1 real-LM).

This is a rigor/meta artifact of the expert-hardening run (WP7-WP13); its numbers are asserted by
the experiment's tests and checksummed here. See `docs/publication/PROGRAMME_SUMMARY.md` §4 and
`docs/publication/THREATS_TO_VALIDITY_AND_RED_TEAM.md` for how it fits the whole programme.
