# FAILED_RUN_001 — execution-reality matrix

Command:

`python experiments/fractal_multiscale/scripts/audit_execution_reality_matrix.py --output artifacts/fractal-adversarial-v1/execution_reality_matrix.json`

Failure:

`RuntimeError: attention density exceeded Activation Budget Contract`

Cause: the archived smoke budget freezes `max_attention_density=0.45`, while the prespecified short
shape used by the matrix can have a larger semantic local/global mask density. This is unrelated to
the active-token/depth/expert execution question being audited.

Disposition: preserve this failure. The normal execution-matrix path is changed to use an explicit
`max_attention_density=1.0` analysis budget so all prespecified shapes are legal. The separate
attention-budget probe still deliberately sets a threshold below the actual density and remains the
claim-bearing guard-order test. No output from this failed run is used as evidence.
