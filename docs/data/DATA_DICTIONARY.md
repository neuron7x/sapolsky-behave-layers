# Data Dictionary

Fields produced by the synthetic generators (see `DATASET_REGISTER.yaml`).

## semantic-route (`task_semantic_route.py`)
| field | type | meaning |
|---|---|---|
| tokens | int[B,L] | token ids of the S-R-O sentence |
| gt | SemanticState | ground-truth subject/relation/object/polarity |
| canon | int[B,L,V] | canonical target logits |
| kind | int | TaskKind.EASY_* / HARD_SEMANTIC |

## surface-matched-duplicate (`surface_matched_task.py`)
| field | type | meaning |
|---|---|---|
| tokens | int[B,16] | sequence with exactly one duplicated value |
| target | int[B] | the duplicated value (the answer) |
| is_far | bool[B] | True = duplicate pair distance > window (needs global) |

## hop-funnel (`task_hops.py`)
| field | type | meaning |
|---|---|---|
| x | graph | funnel-graph pointer-chase instance |
| m(x) | int | number of hops to the absorbing fixed point (difficulty) |

Full field-level semantics live in each generator's docstring and the experiment's
`PREREGISTRATION`. Benchmark-level construct/leakage/scope are in the benchmark cards
(`docs/data/cards/benchmarks/`).
