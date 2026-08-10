# CSCA-04-SA — Pre-calibration Amendment 001

**Time:** before frozen calibration, PRIMARY, or replication cohorts.  
**Development-only seed:** `80001`; permanently excluded from all authoritative cohorts.

During implementation debugging, the initially written per-cell ratio divided each cell by its own very small split-noise estimate. At low cell counts this created unstable heavy-tailed ratios dominated by a near-zero random denominator rather than structural error.

The implementation is corrected **before frozen calibration**:

- global IDR denominator remains `0.25 * mean((d1-d2)^2)` over the audited intervention set;
- each cell numerator is normalized by that same independently estimated global noise floor;
- `max_cell_idr` is therefore a maximum of comparable standardized cell errors, not a maximum of ratios with independent noisy denominators.

Primary intervention policy is frozen as `BALANCED`: every candidate × context cell receives the same number of probes. This follows the safety/identifiability requirement that shared model-class misspecification can have near-zero ensemble disagreement; disagreement-only allocation is therefore not allowed to determine primary structural authority. `DISAGREEMENT_ONLY`, `CREDIT_PRIORITY`, and `COVERAGE_PLUS_DISAGREEMENT` remain predeclared secondary diagnostics and cannot upgrade the primary verdict.

No authoritative calibration/confirmatory result existed when this amendment was frozen.
