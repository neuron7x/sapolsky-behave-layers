# CSCA-03 instrument failure — legacy comparator depends on PYTHONHASHSEED

During adversarial reproducibility testing after the first recovered PRIMARY cohort,
the frozen `LEGACY_INDEPENDENT_MC` comparator was found to iterate a Python `set`
(`coalition`) while consuming RNG draws. Because set iteration order is hash-seed
dependent, the same declared experiment seed can map the same RNG stream to different
predecessor variables in different Python processes.

Concrete one-case diagnostic using identical model/data/estimator seed and only
changing `PYTHONHASHSEED` produced different credit vectors, including:

- hash seed 1: `{A:0.75, B:-0.25, C:0.25, D:0.25}`
- hash seed 2: `{A:0.75, B:-0.50, C:0.25, D:0.75}`
- hash seed 3: `{A:1.00, B:0.00, C:0.00, D:0.25}`
- hash seed 5: `{A:0.25, B:0.25, C:0.00, D:0.25}`

Therefore the confirmatory predicate comparing CRN against the historical comparator
is not hermetically reproducible in CSCA-03. The already executed CSCA-03 PRIMARY is
retained as non-authoritative evidence and may not qualify the estimator. The fix is
mechanical (`for member in sorted(coalition)`), but because PRIMARY was already seen,
the corrected comparator must be tested under a new experiment ID and fresh frozen
seeds (`CSCA-03R`).
