# DGC Mathematical Hardening v2e-v2f

Status: narrow executable mathematics with explicit authority boundaries; not general metareasoning, causal transport, or client validation.

## P21 — Authenticated statistical authority

A positive VOC interval is not production authority by itself. In strict mode the estimate must be bound to a statistical certificate and that certificate must be authenticated by a configured trusted issuer. The current implementation uses HMAC-SHA256 over `issuer_id || certificate_digest`; wrong issuer, wrong key, swapped estimate, drift-invalidated authority or unsigned authority fail closed.

This provides integrity/authenticity inside a shared-secret trust domain. It is not public-key non-repudiation and does not validate the statistical assumptions encoded by the certificate.

## P22 — Calibration lifecycle after drift

Calibration authority has states `ACTIVE -> INVALIDATED_DRIFT -> SHADOW_RECALIBRATION -> ACTIVE(generation+1)`. Initial activation requires preregistration, risk-control pass and independent holdout pass. Drift invalidation prevents minting new statistical authority. Promotion requires a distinct source trace, new preregistration, new calibration/risk-control artifacts, fresh drift guard and disjoint-source attestation.

The lifecycle is governance mathematics; detector power and client-distribution validity remain external empirical obligations.

## P23 — Density-ratio normalization boundary

For covariate shift `w=dQ/dP`, normalization implies `E_P[w]=1`; therefore a claimed global upper bound `W<1` is impossible. The v2e contract rejects `max_density_ratio < 1`. Bounded-weight Hoeffding remains valid only under the declared bounded-ratio/error-budget assumptions. Recent work on robust conformal inference under unbounded covariate shifts further motivates retaining this boundary rather than silently clipping without accounting for undercoverage/error.

## P24 — Bounded finite-horizon metareasoning planner

For a finite declared metalevel MDP with stop value `D(s)` and an externally admissible state upper bound `U(s) >= V_h*(s)`, unexpanded leaves use `[D,U]`. Bellman expectation with nonnegative transition probabilities propagates intervals, giving

`L_d(s) <= V_h*(s) <= U_d(s)`.

`U_d-L_d` is a certified residual optimality gap. Full expansion (`d=h`) solves the declared finite model exactly. This does not solve infinite-horizon, unknown-model or intervention-changing computation spaces.

Validation includes 100 deterministic-random finite models plus an independent exact-rational model checker over 144 exhaustively enumerated two-state models and 2,016 planner certificates.

## P25 — Restricted causal transportability

DGC now implements exact DAG d-separation by ancestral moralization and a sound restricted S-admissibility transport certificate. For the declared subcase, source `P(Y|do(X),Z)` and target `P*(Z)` must exist, `Z` must contain no descendants of `X`, and in the selection diagram mutilated by `do(X)` the solver must verify

`Y independent of S | X,Z`.

Only then does it license

`P*(Y|do(X)) = sum_Z P_source(Y|do(X),Z) P_target(Z)`.

This is a sufficient subcase of the transportability framework of Bareinboim and Pearl; it is explicitly not their complete transport algorithm or general do-calculus.

The d-separation implementation is cross-checked exhaustively on all 64 order-DAGs with four nodes, all ordered singleton X/Y queries and all conditioning subsets against an independent active-path oracle.

## P26 — Complete five-bit software-triage family theorem

DGC-04 executed CLEAN plus 10 nonempty fault combinations; DGC-05 executed the remaining 21 nonempty A/H/C/S/I combinations. Their union is the complete 32-state Boolean fault family.

Anchored aggregate validator calls over the full family are:

- full verification `B0 = 160`;
- path router `B1 = 85`;
- DGC stop-on-fatal `B2 = 36`.

Therefore validator-call savings on this finite family are exactly `77.5%` vs full verification and `57.6471%` vs the path router, while the underlying experiments retain 100% release-decision accuracy and zero false passes. The removable-call function `max(0, |faults|-1)` has tight Lipschitz constant 1 under unit Hamming/weighted-L1 geometry.

This is complete finite-family evidence for one repository validator topology, not arbitrary software, client, model-family or provider generalization.

## External mathematical foundations / novelty boundary

The following are treated as prior art, not DGC inventions:

- rational metareasoning/value of computation: Russell/Wefald and Hay, Russell, Tolpin & Shimony;
- time-uniform confidence sequences/e-process reasoning: Howard, Ramdas, McAuliffe & Sekhon and related sequential-testing literature;
- conformal risk control: Angelopoulos et al., ICLR 2024;
- conformal/weighted methods under covariate shift: Tibshirani et al. 2019 and subsequent weighted-risk-control work;
- Wasserstein distributionally robust optimization: Mohajerin Esfahani & Kuhn;
- causal transportability and selection diagrams: Pearl/Bareinboim and subsequent complete transportability results.

DGC's current contribution is the executable composition, provenance/authority contracts, domain-specific certificates and falsification boundaries, not ownership of those theorem families.
