# PREREGISTRATION — L4h Generalization to More Contexts

**Committed before the run.** L4/L4a/L4b used 2 contexts (lexical, relational). Does
identifiability and governor recovery **generalize** as the number of contexts grows? To
separate a genuine context-interference limit from mere budget dilution, the per-context
training budget is **held constant**.

## Design (frozen)

- Parametric specialization benchmark, `|C| ∈ {2, 3, 4, 6}` contexts, `|A| = |C|` arms. Each
  context `c` has its own best arm (mean `1.0`), a runner-up (mean `1 − Δ`, `Δ = 0.20`), and the
  rest `0`. Reward noise `σ = 0.10` (measured plasticity scale). Best arms differ across contexts
  (routing genuinely needs the context).
- Governor: per-context softmax REINFORCE, **constant per-context budget** `3000` episodes (total
  `3000·|C|`), so `|C|` is the only thing varied. 8 controller seeds; train/eval by a held-out
  reward split.
- Metrics per `|C|`: certificate `G_lo` (δ=0.05) and worst-of-8 governor held-out recovery.

## Decision rule (FROZEN)

- **L4H_GENERALIZES** iff, for all `|C| ∈ {2,3,4,6}`: `G_lo > 0` (identifiable) AND worst
  governor recovery `≥ 0.8` (recovered). Contexts do not interfere at constant per-context budget.
- **L4H_CONTEXT_INTERFERENCE** — some `|C|` drops `G_lo ≤ 0` or recovery `< 0.8`: adding contexts
  hurts even at matched per-context budget (a real generalization limit to record).

## Scope / prohibited

Tier `SYNTHETIC-PARAMETRIC`. A generalization/scaling check of the identifiability + governor
result to more contexts (not the real benchmark, which has 2 tasks). New claim
`CWC-L4h-context-scaling`. Does not establish real-workload behavior, L7, energy/latency, or
independent replication.
