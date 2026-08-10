# CSCA-06A Pre-execution Amendment 002

**Date:** 2026-08-10
**Timing:** before any authoritative CSCA-06A execution.

Static review found that an absolute alternative-mixture slope set centered around zero was asymmetric for the S3 candidate model with beta_M=+0.8 and omitted the true beta=0 alternative. No authoritative data had been executed.

Repair: define the normalized alternative mixture by offsets relative to the candidate model slope: beta_alt = beta_M + {-0.8,-0.4,+0.4,+0.8}. This preserves the M0 mixture exactly and makes the test symmetric around every candidate model. All alpha, nuisance bounds, families, budgets, block design, and seed cohorts remain unchanged.
