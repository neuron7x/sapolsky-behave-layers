# WP-2 Routing v2 — Typed Semantic Routing — PREREGISTRATION

Registered 2026-07-16 before the full runs; committed before analysis. Authority:
CWC Typed Semantic Routing Integration Act v2.0. Builds a NEW experiment (v1 is
frozen; `artifacts/wp2-routing-v1_1/FINAL_CLAIM_BOUNDARY.json`).

## Objective
A hard-budget controller must route structurally-simple inputs through a cheap
direct path and semantically-complex inputs through a typed semantic path,
preserving meaning, spending the expensive path only where causally necessary.

## Benchmark (§3-5)
Semantic tuple (subject, relation, object, polarity). Canonical target
[subj, rel, obj, pol]. EASY_DIRECT: canonical order at positions 0-3 (local-
solvable). HARD_SEMANTIC: passive / distractor-prefix / negation putting fields
beyond a local window. Two PHYSICALLY different paths: DirectPath (local window
w=1, reads positions 0-3 -> structurally fails HARD); SemanticPath (global
parser -> 4 supervised field heads -> renderer from state only). Compositional
split: test tuples never appear in training.

## §9 oracle-gap gate (identifiability — checked BEFORE the learned controller)
PASS iff, over 5 seeds: lower 95% CI of relative oracle gain > 0; mean gain
>= 10%; oracle HARD exact - best-fixed HARD exact >= 10 pp; oracle budget
violations = 0; oracle EASY >= 95%; oracle HARD >= 99.9%. FAIL -> verdict
BENCHMARK_NOT_IDENTIFIABLE (redesign task, NOT the controller).

## §10 isolation gates
Parser subject/relation/object/polarity >= 99%, tuple >= 97%; renderer (gt
state) >= 99%; DirectPath EASY >= 99%, HARD <= 70%.

## §11-12 routing causality (8 seeds; controller trained label-free)
Controller need_score regresses (direct_loss - sem_loss) (uses path losses,
never task_kind). PASS iff: route balanced acc >= 0.85; AUROC >= 0.90; NMI lower
95% CI >= 0.25; CRE (forced-wrong/forced-correct) lower CI > 0; shuffling-loss
ratio lower CI > 0; learned < random AND learned < shuffled (paired CI < 0);
budget violations = 0. Else ROUTING_CAUSALITY_NOT_SUPPORTED.

## §13 lesions (aphasia analogues)
renderer_off (Broca-like): tuple stays, canonical exact drops. semantic_state_
permuted (Wernicke-like): syntax valid, semantics wrong, FNR up. subject_object_
swapped (conduction-like): meaning wrong in the predicted direction.

## Blocked (§18)
No RCFR / memory / adaptive depth / plasticity / joint controller / Pareto claim
until ROUTING_CAUSALITY_SUPPORTED. Energy excluded (INSTRUMENT_INVALID).
No threshold changed after seeing results. A negative result is a valid outcome.
