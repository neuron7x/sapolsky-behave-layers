# CSCA-08A — Exploratory regime-identifiability pilot

**Status:** EXPLORATORY / NON-AUTHORITATIVE  
**Seeds:** 1000..1063 (reserved pilot-only)  
**Rows/seed:** 4096  
**Purpose:** verify code path and choose a confirmatory sample regime before freezing CSCA-08A/B.

The candidate passive identifying structure is a two-coordinate observed regime vector `R=(R1,R2)` acting as an IV-style auxiliary channel for treatment `X` in the presence of latent confounding `U` between `X` and `Y`. A negative-control outcome `W` provides only a partial exogeneity falsifier. Agreement of instrument-specific Wald estimands provides only a partial exclusion/effect-invariance falsifier.

Pilot state counts over 64 seeds/family:

| family | state counts | median |beta_hat-beta_true| |
|---|---:|---:|
| V0_VALID | 63 candidate / 1 assumption violation | 0.0111 |
| V1_DIRECT_NONPROPORTIONAL | 64 assumption violation | 0.4738 |
| V2_R_U_CONFOUNDING | 64 assumption violation | 0.3932 |
| V3_ALEATORIC_HIGH | 63 candidate / 1 assumption violation | 0.0306 |
| V4_SELECTION_BIAS | 64 assumption violation | 0.3087 |
| V5_WEAK_RELEVANCE | 64 insufficient-information | 0.2893 |
| V6_COORDINATED_EXCLUSION | 63 candidate / 1 assumption violation | 0.5044 |
| V7_LABEL_CORRUPTION | 64 candidate | 0.0224 |

The V6 result is the load-bearing negative: coordinated direct effects proportional to regime strength can pass over-identification while changing the causal coefficient. The exact pathwise counterexample in `coordinated_exclusion_counterexample()` shows why surviving observable checks cannot prove exclusion. Therefore the runtime state is deliberately `CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS`, never causal truth/authority.

No pilot number may be used as confirmatory evidence. Confirmatory cohorts must use disjoint seeds and thresholds frozen in a strict Git ancestor.
