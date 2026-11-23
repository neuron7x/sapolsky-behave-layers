# CNEH-EXP-01 — prospective preregistration

**Canonical hypothesis:** CNEH-04-DC, SHA-256 `5250113e580fd5d63f5f96fde19f8b1cb5a21a76a1d39f126d1f5182b298556a` (20,247-byte source document, retained outside this repository; not a substitute for publishing/reviewing the source).
**Hypothesis status:** `FORMALIZED / EMPIRICAL VALIDATION PENDING`.
**Registration authority:** `RESEARCH_ONLY`. This is a *new* experimental lineage, not a resurrection of CWC-FLAGSHIP-ROUTE-02 or any frozen negative result.
**Repository:** `neuron7x/sapolsky-behave-layers`, branch `research/cneh-exp-01`.
**Normative parent:** `docs/methodology/CWC_MASTER_METHODOLOGY.md`; its fail-closed and negative-results rules take precedence.

## Primary question

At identical physical observation/action interfaces and an auditable *vector* of physical/computational budgets, can semantic bidirectional interaction between two partially observing controllers increase **safe terminal goal success** on predeclared out-of-distribution (OOD) structural changes over (a) a fully faithful resource-matched **centralized emulator**, (b) static fusion, and (c) scrambled, envelope-matched messages?

The universal claim is **not mathematically admissible** if the centralized architecture can simulate the distributed architecture at equal or lower cost: `Pi_distributed(B) subseteq Pi_central(B)`. A strict distributed > faithful-emulator result is then **a falsification alarm** (implementation, measurement, leakage, or unequal constraints), not evidence for an impossible theorem. The primary experiment deliberately retains this negative control. A separate bounded comparator claim can be preregistered later, with an independently justified restricted monolith, but cannot inherit this experiment's authority.

## Estimands and frozen decision

For each independent world seed `s`, compare matched terminal binary success `Y_a(s) = 1{goal reached AND all states safe}`. The world noise, physical sensors, actuators, goal family, horizon and starting state generator are matched across arms using common random numbers. Contrast `D_{a,b}(s)=Y_a(s)-Y_b(s)` is in [-1,1]. Primary estimands:
- `delta_central=E[D_coupled,central_emulator]`
- `delta_static=E[D_coupled,static_fusion]`
- `delta_scramble=E[D_coupled,scrambled_matched_traffic]`

`material_effect=0.05`. To control familywise error across three contrasts in both cohorts, use a conservative one-sided Hoeffding LCB `LCB=mean(D)-sqrt(2*ln(6/0.05)/N)`, with `N` independent WORLD SEEDS, not time steps or tokens. Positive primary evidence requires all three `LCB>0.05` on PRIMARY and again on independently executed blind REPLICATION. This construction is intentionally conservative; failing to cross it with poor power is `INCONCLUSIVE`, not `FALSIFIED_IN_SCOPE`.

No early stopping, tuning or replacing seeds based on cohort results. Observed primary values must not alter `material_effect`, comparator list or thresholds.

## Design

Physical synthetic plant is a bounded 2-state linear recurrence with an undisclosed-to-controller cross-coupling shift at step `t_shift=6`. Define unknown `theta` as the off-diagonal parameter of the post-shift plant. Controls see only noisy channel observations and history. OOD holdout shifts are new magnitudes/signs relative to the controller's nominal parameter. No controller sees ground truth `theta`, latent states, heldout seed file or future noise. No external-neuroscience claim.

Arms: `COUPLED`, `CENTRAL_EMULATOR`, `STATIC_FUSION`, `SCRAMBLED_MATCHED_TRAFFIC`, `A_ONLY`, `B_ONLY`, `PARALLEL_NO_MESSAGES`, `ONE_WAY`, `HOMOGENEOUS_DUPLICATES`; `FULL_INFORMATION_ORACLE` is diagnostic-only and excluded from fair comparisons. The emulator runs the *exact same* controller update with the *same* inputs and random stream as COUPLED, without a network boundary; paired action/state equality is a mandatory invariant. This avoids unfairly weakening the monolith.

All-arm budgets are a fixed envelope (not a license to ignore marginal cost). Record control-input L2² proxy, message bytes, algorithmic operation proxy, memory proxy and latency/horizon. **No measured joules or verified hardware FLOPs are claimed.** Training cost is zero in the synthetic zero-training preflight; any learned follow-up requires separate frozen training budget and seed allocation. Non-verified cost dimensions disallow `SUPPORTED_NARROW`.

## Cohorts and blinding

- DEVELOPMENT/SMOKE: no scientific promotion.
- PRIMARY: 128 independent world seeds `51001..51128`, fixed before outcome observation; each arm receives the same exogenous streams. This is only a *synthetic internal* assessment, not independent replication.
- REPLICATION: 128 new world seeds selected, committed by SHA-256, held by **another operator** before receiving any PRIMARY outcomes; seed-to-arm labels are blinded in evaluation. The independent operator executes the frozen commit and publishes the commitment, raw results, reveal and SHA256SUMS. Absence of independent operator or hidden seed commitment means `REPLICATION_NOT_TESTED`.

No results from one cohort are inputs into any policy in the other cohort. Any fabricated or self-labelled independent replication is a hard FAIL.

## Synthetic safety and science boundaries

State must remain inside `max(|x_j|)<=2.5` at every step; terminal distance to target must not exceed `0.25`. The primary outcome is terminal success AND safety. Input per dimension clipped at 0.8; horizon 24. These are toy simulation limits, NOT physical or stochastic chance-constrained guarantees. No criticality or PID claims are licensed: optional Fisher/PID/Gramian diagnostics require a separate frozen estimator, target, units, numerical tolerances and intervention ablations.

## Failure predicates

- `CENTRAL_EMULATOR` diverges in action/state trace from `COUPLED` => `MEASUREMENT_INVALID`.
- Physical sensors or actuators differ, future truth leaks, cohorts overlap, comparator is artificially handicapped, traffic/control budget cannot be verified => `INVALID`.
- Any preregistered contrast missing or any hash mismatch => `INVALID`.
- Strict improvement over an unrestricted faithful simulator => `STRUCTURAL_CONTRADICTION`, investigate; never `SUPPORTED`.
- Missing independent blind replication => `REPLICATION_NOT_TESTED`.
- Confidence limits straddle material effect => `INCONCLUSIVE`.
- Sufficiently powered failure under a predeclared equivalence/futility bound (not included in this pilot) is required before `FALSIFIED_IN_SCOPE`.

Allowed terminal dispositions: `NOT_TESTED`, `INCONCLUSIVE`, `INVALID`, `UNIDENTIFIABLE`, `SAFETY_UNQUALIFIED`, `FALSIFIED_IN_SCOPE`, `SUPPORTED_NARROW`, `STRUCTURALLY_UNTESTABLE_UNDER_SIMULATION_DOMINANCE`. **Default: `NOT_TESTED`.**

## Artifact and cryptographic chain

First commit freezes `PREREGISTRATION.md`, `protocol.json`, `frozen_sources.lock` before running the runner. Later commit adds implementation, traceable negative controls, test suite and generated *exploratory* evidence. Each evidence bundle must contain `protocol.json`, `preregistration.md`, `frozen_sources.lock`, `seeds.json`, `budget.json`, `safety.json`, `negative_controls.json`, `verdict.json`, `SHA256SUMS`, plus `primary.csv`/`replication.csv` only when their execution authority actually exists. `SHA256SUMS` excludes itself, lists all other generated files, and verification must fail closed on unexpected/missing files.

**Independent replication and external scientific validation are not completed by writing this preregistration.**
