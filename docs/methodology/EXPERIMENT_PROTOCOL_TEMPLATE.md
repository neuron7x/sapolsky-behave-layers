# CWC Experiment Protocol Template

Copy to `experiments/<exp>/PREREGISTRATION*.md` and commit **before** the confirmatory
run (the run timestamp must be after the preregistration commit). Existing
preregistrations (`experiments/wp2_routing_v2/PREREGISTRATION_*.md`,
`experiments/wp4_adaptive_depth/PREREGISTRATION.md`) are conforming instances.

## Required sections
1. **protocol_id** and immutable **version**
2. **research_question** (link RQ-*)
3. **H0 / H1** (link hypothesis_id in HYPOTHESIS_REGISTRY.yaml)
4. **estimand** — the quantity the run actually estimates
5. **independent variables**
6. **dependent variables**
7. **controlled variables**
8. **confounders** (and how neutralized)
9. **experimental unit** (default: model seed, paired)
10. **model & data populations**
11. **inclusion / exclusion rules**
12. **datasets & split hashes** (link DATASET_REGISTER.yaml)
13. **baseline selection** (from the baseline taxonomy)
14. **compute parity** statement
15. **metrics** (link METRIC_DEFINITIONS)
16. **statistical tests** (link STATISTICAL_ANALYSIS_PLAN)
17. **power / sample size**
18. **seed policy** (model / data / eval / router seeds separated)
19. **stopping rule**
20. **failure rule** (fail-closed)
21. **deviation procedure** (link PROTOCOL_AMENDMENT_AND_DEVIATION_POLICY)
22. **expected artifacts** (the Level-D bundle)
23. **acceptance gate** (the exact decision rule)
24. **prohibited interpretation** (what a positive/negative does NOT license)

## Acceptance
No confirmatory run may start without a schema-valid protocol and a preregistration
commit preceding the run timestamp. Pilot runs are labelled and excluded from
confirmatory inference.
