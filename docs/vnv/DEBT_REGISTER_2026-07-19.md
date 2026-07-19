# CWC Technical and Theoretical Debt Register — 2026-07-19

This is the authoritative audit closeout for the first remediation pass.

## Resolved in code

| ID | Debt | Resolution |
|---|---|---|
| P0-VERIFY | canonical `verify` failed at 76.32% coverage | plasticity tests included; 96.59%, 215 coverage tests |
| P0-SEED | WP4 used process-randomized Python `hash()` | SHA-256-derived stable data seeds |
| P0-REPRO | reproduction overwrote canonical evidence | isolated temporary output; inherited environment preserved |
| P0-BOOT | experiment LCG produced degenerate bootstrap at n=8 | `random.Random` resampling + regression tests |
| P1-CI | WP4 serialized half-interval `[lower, null]` | v2 emits full two-sided CI |
| P1-COMPUTE | compute gate allowed 0.6-hop mismatch | v2 reports relative mismatch and requires <=1% |
| P1-DATA | checksums were treated as data validation | read-only semantic validator added to canonical gate |
| P1-EXACT | rounded static budget prevented exact compute pairing | exact-total input-blind allocator + exploratory pilot added |
| P1-HALT | malformed non-convergent graphs could silently exhaust the loop | adaptive halt now fails closed; adversarial cycle regression added |
| P1-HOLDOUT | first v3 control budget read realized holdout difficulty | run invalidated; prospective v3.1 frozen analytic budgets + untouched seeds used |

## Resolved epistemically

| ID | Debt | Resolution |
|---|---|---|
| T0-WP4 | same-sample identity described as independent prediction | claim narrowed; superseding correction published |
| T0-PARETO | approximate compute described as equal compute | withdrawn; v2 compute gate fails 3/4 regimes |
| T0-PREREG | same-commit protocols described as preregistered | reclassified; prospective integrity policy added |
| T1-THEORY | synthetic identity rhetorically elevated to architecture result | reframed as executable positive control |

## Open — cannot be solved by local refactoring

| Priority | Debt | Closure evidence required |
|---|---|---|
| P0-EXT | no real-workload external validity | >=2 real tasks, held-out distributions, strong baselines |
| P0-PARETO | no exact end-to-end compute Pareto result | controller cost charged; <=1% FLOP mismatch; quality/latency frontier |
| P0-REPL | no independent replication | clean-room third-party rerun |
| P1-POWER | no pilot-derived confirmatory sample-size calculation | frozen pilot, MDE, variance, prospective n |
| P1-RELATED | systematic literature review incomplete | databases, dates, search strings, inclusion/exclusion log |
| P1-ROBUST | halt signal is exact and privileged | noisy/partial/expensive halt interventions and OOD stress tests |
| P2-SCALE | no scaling law or multi-size robustness | preregistered model/data/sequence scale grid |

The open P0 items are scientific work, not documentation work. They must remain
open until new independently ordered evidence exists.

The exact-total-compute pilot narrowed engineering uncertainty but did not close
`P0-PARETO`. V3 was Git-ordered but invalidated for holdout-budget leakage. V3.1
used a separately committed amendment, frozen analytic budgets and untouched
seeds; it supports only an internal free-halt-oracle/operator-hop claim because
no external timestamp or independent operator exists.

V3.1 closes operator-hop matching under distribution-derived frozen budgets, but
does **not** close `P0-PARETO`: halt evaluations are 1.12–1.39 per billed hop and
are excluded from the primary ledger. End-to-end controller/halt cost remains open.
