# CSCA-03 DEBUG-001 — wrong direction estimand

Pre-primary debugging showed that raw local `phi_A` in the centered-binary sign-flip family changes with both the causal coefficient and factual sign of `A`, so it can incorrectly appear globally stable. The corrected controlled-family directional estimand is `phi_A/A = phi_A*A`. This correction was frozen before PRIMARY and does not generalize automatically to arbitrary variables.
