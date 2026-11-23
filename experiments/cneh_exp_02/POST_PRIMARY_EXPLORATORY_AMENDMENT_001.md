# CNEH-EXP-02 — Post-primary exploratory analysis and estimator amendment 001

**Temporal integrity:** This file is written AFTER observing internal PRIMARY outcomes at the frozen 128-world execution in [GitHub Actions #45182747186](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45182747186). It is explicitly post-hoc and **MUST NOT** modify the primary hypothesis, thresholds, arms, code constants, seeds, or scientific tier. The parent preregistration commits `d760ef3cf3e2dbe5fa7bcd574292e358c4b84f6c` and `72d1c8abd2b33954fe60a48da26f3c061a60324c` predate implementation.

## Frozen first internal PRIMARY observations (not replication)

| Arm | Safe terminal goal success | Mean terminal goal error |
|---|---:|---:|
| FULL_INFORMATION_ORACLE (diagnostic) | 128/128 = 1.000000 | 0.019087 |
| COUPLED | 74/128 = 0.578125 | 0.169551 |
| CENTRAL_EMULATOR | 74/128 = 0.578125 | 0.169551 |
| NO_PROBE | 70/128 = 0.546875 | 0.167786 |
| SCRAMBLED_CONTENT | 69/128 = 0.539062 | 0.177535 |
| ONE_WAY_A_TO_B | 69/128 = 0.539062 | 0.177596 |
| DISCONNECTED | 67/128 = 0.523438 | 0.183596 |
| STATIC_FUSION | 63/128 = 0.492188 | 0.179329 |
| HOMOGENEOUS_VIEW (diagnostic) | 6/128 = 0.046875 | 0.629939 |

Paired COUPLED minus baseline and conservative exploratory one-sided lower confidence bounds:

| Contrast | Paired difference | Hoeffding LCB |
|---|---:|---:|
| CENTRAL_EMULATOR | +0.000000 | -0.261666 |
| STATIC_FUSION | +0.085938 | -0.175729 |
| SCRAMBLED_CONTENT | +0.039062 | -0.222604 |
| NO_PROBE | +0.031250 | -0.230416 |

Emulator parity: **exact** across all 128 paired worlds. Donor packet empirical time/stratum marginals: **exact** by permutation. Declared control-input effort proxy maximum: **33.61377308713**; algorithmic-operation proxy maximum: **10096**. All stayed under declared envelopes. None of the lower bounds licenses positive benefit; the only supported claim is **successful execution of the synthetic falsification instrument with no strict advantage over the exact monolithic emulator**.

## New non-primary mathematical diagnostics (no reward tuning)

Add a separate `linear_reference.py` and CWC cross-check tests to distinguish:
1. instantaneous sensor rank versus *temporal* observability;
2. physical-state controllability versus state observability;
3. both of those versus unknown-parameter information;
4. coordinate-invariant Hankel singular values versus invalid literal `W_o intersect W_c`.

These are **post-primary mathematical verification probes** only, not new CNEH-EXP-02 primary endpoints. Reference formulas are for fixed two-dimensional linear systems with independent Gaussian measurement noise. Open-loop parameter-Fisher information is not the Fisher information of an adaptive closed-loop agent. No theory of collective intelligence is proved here.

## Known weaknesses that remain

- Posterior parameter estimates are approximate, noisy, ridge/forgetting statistics, not a calibrated Bayesian posterior.
- Surprise-gated harmonic probe is a dual-control candidate, **not an optimal dual-control solution** and no persistent-excitation theorem is established.
- The synchronously permuted donor messages match pooled stratum/tick payload marginals, not the target-conditional distribution; source-target mismatch is intentional, but claims about PID, semantics or nonlinear mediation remain unsupported.
- The exact central emulator remains equal by construction, so strictly beating it is an invalid success metric under matched simulation assumptions.
- Current world is a deterministic-seeded synthetic physical plant, not BN-Syn/real neurons/real-world controller. Neither real FLOPs/joules nor external-blind replication are measured.

**No preregistered hypothesis was raised after reading PRIMARY. Any future mechanism improvement must use a separately frozen new protocol/lineage and fresh cohort seeds.**
