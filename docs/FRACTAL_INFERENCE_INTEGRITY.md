# Fractal inference integrity

The same truth condition must survive at every scale:

| Scale | Executable invariant | Failure made visible |
|---|---|---|
| Request | typed, finite, vocabulary- and context-bounded inputs | ambiguous or impossible generation |
| Sampling | finite rank-2 logits and controlled stochasticity | NaN/Inf propagation or invalid probability surfaces |
| Cache | synchronized positions and bounded writes | silent KV corruption or overflow |
| Parameters | complete deterministic tensor inventory | missing, renamed, reshaped or retyped weights |
| Weight bytes | per-tensor and state-root SHA-256 | any content drift |
| Behaviour | seed reproducibility and greedy batch metamorphism | hidden dependence on seed or batch replication |
| Admission | focused tests required by local and GitLab gates | controls that exist but are never executed |

This is “fractal” in the operational sense: identity, finiteness, bounds and
reproducibility recur from individual scalar parameters through full model state
and generated sequences.

## Weight evidence

`nanochat.model_integrity.build_state_manifest(model.state_dict())` produces a
canonical sorted inventory containing each tensor's name, shape, dtype, element
count and SHA-256, plus a root digest over that inventory. Verification rebuilds
the manifest from live tensors and fails on inventory or byte-level drift.
New checkpoints embed this manifest in their metadata. Loading a manifested
checkpoint is fail-closed: any missing, renamed, reshaped, retyped or modified
tensor aborts before model construction. Legacy checkpoints remain readable
without retroactively claiming integrity evidence they never recorded.

The digest is an integrity commitment, not a quality score. Identical hashes do
not establish accuracy, calibration, safety or theoretical correctness.

## Inference claim boundary

The tests cover malformed inputs, non-finite logits, cache divergence/overflow,
weight tampering, deterministic greedy decoding and seeded sampling contracts.
They do not demonstrate semantic robustness, distribution-shift performance,
hardware-bitwise equivalence or empirical validity of research claims. Those
require separately registered datasets, metrics and falsification experiments.
