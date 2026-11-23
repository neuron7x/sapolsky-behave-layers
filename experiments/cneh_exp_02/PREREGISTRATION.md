# CNEH-EXP-02 — Prospective mechanistic protocol: Two-Cortex Dual Control

**Scientific status:** `FORMALIZED / EMPIRICAL VALIDATION PENDING`.
**Protocol authority:** `SYNTHETIC_MECHANISM_EXPLORATION_ONLY`; no human/neural empirical claims or independent replication.
**Parent:** CNEH-04-DC source SHA-256 `5250113e580fd5d63f5f96fde19f8b1cb5a21a76a1d39f126d1f5182b298556a`; CNEH-EXP-01 is frozen, separate, and NOT retroactively promoted.
**Repository:** neuron7x/sapolsky-behave-layers (stacked research/cneh-exp-02 atop research/cneh-exp-01).
**Conflict resolution:** normative CWC methodology takes precedence; no claims above evidence tier.

## Primary mechanistic problem

Test whether **two distinct stateful causal estimators** with partially separated sensor streams, bidirectional, time-aligned communication and prediction-error-triggered parameter exploration yield a causal benefit under a sudden unannounced change to a plant's cross-coupling coefficient. Distinguish (i) raw information fusion, (ii) adaptive model updating, (iii) content-specific communication, (iv) active probing, and (v) unrestricted centralized emulation. Explicitly preserve the simulation-dominance theorem: unrestricted central emulator MUST reproduce COUPLED trajectory and outcome. A strict improvement against this emulator is an experimental INVALIDITY trigger, NEVER an emergence proof.

## Controlled world and unknown parameter

Two-dimensional partially observed discrete-time plant, horizon=48:
`x[t+1] = [[0.83, theta_t],[-theta_t,0.86]] x[t] + 0.43*u[t] + w[t]`;
`yA[t]=x0[t]+vA[t]`, `yB[t]=x1[t]+vB[t]`.
Initially `theta_t=0.03`, switching at step `t*=12` to one of `[-0.44,-0.31,+0.33,+0.46]`, assigned by world-seed stratum, concealed from controllers. Gaussian process SD 0.015 and measurement SD 0.055; terminal target uniform in [-0.52,+0.52]², initial state uniform in [-0.65,+0.65]². Actuator box [-0.65,+0.65]. Safe region `max(abs(x))<=2.0`; success if the entire trajectory remains safe and terminal Euclidean target error <=0.18. Goal vector known to both agents. All simulation noise streams paired across arms. 128 primary world seeds `61001..61128` are public and frozen now (diagnostic internal PRIMARY only).

## Cognitive mechanism

A ("homeostatic axis-0 cortex") and B ("active-inference axis-1 cortex") each possess ONLY their local noisy sensor; each has independent local causal parameter statistics, a finite memory, previous action, prediction innovation and anomaly accumulator. They exchange time-stamped `state_estimate,theta_estimate,information_proxy,surprise` packets. At each tick use past-only observations to update ridge/forgetting parameter statistics, select a bounded stabilizing action and optional bounded two-frequency precision/surprise-gated probe. No planner/agent may read the hidden state, theta, shift time, future samples or reward from future steps. Output trace includes causal world seed, arm, per-step action/state, packet source identity, SHA256 and cost proxies.

## Preregistered arms

`COUPLED` (real two-view, two-way messages, active probe), `CENTRAL_EMULATOR` (bitwise same paired computation/observations/action, no forced monolith handicap), `STATIC_FUSION` (same current messages, nominal parameter used for action), `SCRAMBLED_CONTENT` (current-tick donor packet from another world in the SAME hidden-theta stratum and tick, deterministic cyclic seed permutation, empirically identical donor-message marginal over seeds; same message byte and time envelope), `NO_PROBE` (adaptive estimates but zero exploratory input), `ONE_WAY_A_TO_B`, `DISCONNECTED`, `HOMOGENEOUS_VIEW` (both axes see yA, diagnostic insufficient sensor diversity), `FULL_INFORMATION_ORACLE` (truth aware, diagnostic ceiling, NOT fair baseline).

The scramble permutation uses contemporaneous COUPLED packets generated under the same frozen seed cohort and shift stratum. Packet age is preserved. The baseline compares target-aligned packets vs independent cross-world packet contents; donor-world state distributions may differ conditionally on the target state, and only **marginal** time-stratified source distributions are guaranteed to match. The experiment must not describe this as equal conditional information or a proof of PID synergy.

## Estimands / decision

Primary outcome per independent world seed: binary safe-goal success. Paired comparisons COUPLED versus STATIC_FUSION, SCRAMBLED_CONTENT and NO_PROBE; `CENTRAL_EMULATOR` exact trace parity is a mandatory falsifier.

**No positive scientific promotion is possible in this pilot**, independently of effect size. Exploratory contrasts and one-sided Hoeffding lower bounds are reported but do not authorize an emergence claim. For a future preregistered, independently replicated confirmatory study the minimum effect candidate is `delta_min = 0.05`; 128 pilot seeds must not be retrospectively relabeled confirmatory. The unit of analysis is world seed, not time-step or neural packet. Alpha and inference units cannot be changed after seeing outcomes.

Other predeclared diagnostics: final absolute theta error for A/B (evaluator-only truth), data/controls leakage gate, intervention effort `sum u²`, communication payload bytes, fixed algorithmic-operation proxy and causal re-identification proxy `sum(regressor²)`. The latter is NOT the exact Fisher information of the partially observed adaptive controller. Geometric O/Wc/Hankel analyses and PID decomposition are deferred until an estimator-specific calibration/independent baseline exists.

## Cost and evidence ceiling

Envelopes: 48 ticks, per-axis action magnitude<=0.65; sum input u² <=36; payload bytes <=8192; operation proxy <=15000; state-memory proxy<=4096; no offline training, no external API tokens. JOULES, actual FLOPs, GPU time and end-to-end latency are NOT measured. Unequal physical throughput and central simulator overhead prevent a compute-equivalent Pareto claim. JSON and CSV artifacts hash pinned via SHA256SUMS, frozen source contract and replay verification. Tamper after rehash must be detected by execution-backed replay, not mere checksum matching.

## Stopping/negative rules

No adaptive tuning after first PRIMARY run. Missing code integrity, timestamp drift, action/state divergence for emulator, any hidden-state leakage outside oracle, unknown comparator semantics, unbounded cost, invalid data dependency or mismatched seed strata => INVALID; invalidity never transformed into evidence. Lack of positive effect => NEGATIVE_EXPLORATORY or INCONCLUSIVE, not a general impossibility theorem. Prior frozen negatives stay immutable.

## Replication

Another operator, not the code author or this GPT session, commits a concealed non-overlapping seed list by SHA256 before execution. Run with a pinned commit and the same frozen protocol, release results then reveal seeds; verify all execution artifacts and SHA256SUMS independently. Merely running CI or rerunning PRIMARY is INTERNAL REPLAY, not independent blind replication. No LLM-generated "independent" certification. 
