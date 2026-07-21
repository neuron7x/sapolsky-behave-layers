# wp14_real_lm_contextual — RESULTS

**Verdict: `WP14_REAL_LM_NOT_IDENTIFIABLE_ROBUST`.** Tier: REAL-DATA — robustness of the WP6 boundary to a contextual (bigram) difficulty signal. Preregistration:
`experiments/wp14_real_lm_contextual/PREREGISTRATION.md`.
Reproduce: runner --seeds 0..4 then analyze.

## Result

| lambda | real-LM (bigram) G_lo | positive control (AC1) |
|---|---|---|
| 0.0 | -0.1824 | +0.6213 |
| 0.3 | -0.1824 | (>0) |

With a stronger contextual (bigram) difficulty signal the real-LM per-token compute allocation is STILL not identifiable (G_lo<=0), while the synthetic positive control >0. The WP6 negative is robust to the difficulty definition -- hard tokens are hard because inherently unpredictable, not because they need more compute (more compute even hurts them).

Robustifies the WP6 boundary (CWC-RD1): the real-data non-identifiability is not an artifact of the
crude unigram difficulty proxy. See docs/publication/PROGRAMME_SUMMARY.md.
