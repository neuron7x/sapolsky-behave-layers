# CNEH-EXP-02 — Two-Cortex Predictive Causal Control

**STATUS: FORMALIZED / EMPIRICAL VALIDATION PENDING.**
**EXECUTION TIER: EXPLORATORY INTERNAL SYNTHETIC ONLY.**

This is a *new preregistered* synthetic OOD study, not a rescue or reclassification
of CNEH-EXP-01 or the prior CWC adaptive-depth negative experiments.

- **Cortex A:** local axis-0 sensor, finite-memory predictive innovations, estimated coupling,
  per-agent control-energy ledger and action.
- **Cortex B:** independent axis-1 sensor, independent causal estimator and control.
- **Communication:** fixed-length 32-byte timestamped binary evidence packets.
- **Interventions:** source-aligned coupled, central emulator, static fusion, same-tick
  theta-stratified donor-message permutation, no-probe, unidirectional, disconnected,
  homogeneous sensing and truth-aware diagnostic oracle.
- **Decision:** each cortex selects its own bounded action from its own observation
  and the received packet; no omniscient aggregator.
- **Physical truth:** synthetic evaluator only; outside the controller interface.

## Run (Python 3.12, stdlib only)

\`\`\`sh
python -m unittest discover -s tests -p test_cneh_exp_02.py -v
python experiments/cneh_exp_02/run.py --phase smoke --out /tmp/cneh02-smoke
python experiments/cneh_exp_02/run.py --out /tmp/cneh02-smoke --verify
python experiments/cneh_exp_02/run.py --phase primary --out /tmp/cneh02-primary
python experiments/cneh_exp_02/run.py --out /tmp/cneh02-primary --verify
(cd /tmp/cneh02-primary && sha256sum --check SHA256SUMS)
\`\`\`

Full replay, source hash lock, immutable cohort, SHA256 manifest and re-signed
forged evidence tests are enforced. A changed compiled program can defeat a
self-verifier: independent operator/implementation + pinned signed commit are
still necessary for external trust. No claim that SHA256SUMS itself is a
digital signature.

**Key epistemic boundary:** CENTRAL_EMULATOR exactly reproduces the coupled
controller and cannot be strictly beaten by definition. This is a *positive
control for simulation fidelity*, not an intentionally weak centralized
baseline. \`SCRAMBLED_CONTENT\` preserves packet tick/envelope and empirical
source-message marginals within OOD strata, but not conditional information.
There is no \`PID\` estimate, credible hardware energy measurement or neural
biological validation. The algorithmic-operation count and per-agent memory
numbers are *explicit proxies*, not measured CPU FLOPs/peak RSS.

The first 128-world internal cohort is preregistered but not an independently
replicated confirmatory result. \`scientific_promotion_authorized=false\`
irrespective of measured exploratory score. Archive negatives.
