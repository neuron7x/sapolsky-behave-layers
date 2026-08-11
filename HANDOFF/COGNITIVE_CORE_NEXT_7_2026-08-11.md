# CWC — NEXT 7 DEEP COGNITIVE-CORE TASKS

These are sequential unless explicitly marked parallel. The goal is to strengthen executable cognition, not add conceptual modules without causal authority.

## 1. CSCA-08 — Assumption-Typed Causal Candidate [STARTED / SYNTHETIC NARROW PASS]
Make identifying assumptions machine-readable objects with testability class, provenance, falsifiers and unresolved debt. The runtime must distinguish `candidate under assumptions` from `causal authority`. CSCA-08A/B now supplies the first executable instance.

## 2. COG-INFO-01 — Information Acquisition Governor [KERNEL IMPLEMENTED / QUALIFICATION PENDING]
For the unresolved model equivalence class, choose the next admissible observation/test by maximin certified `KL-information / acquisition-cost`, not heuristic curiosity. Zero information rate must veto extra compute. Next: bind rate lower bounds to measured experiment families rather than hand-supplied test fixtures.

## 3. COG-COUNTERMODEL-01 — Autonomous Countermodel Generator [R1 SYNTHETIC NARROW PASS; PARENT DESIGN-NEGATIVE PRESERVED]
Given a surviving causal candidate, automatically search for the cheapest alternative SCM/latent realization that preserves current factual constraints but changes the causal conclusion. Objective: minimize observable divergence subject to causal disagreement. A candidate cannot consolidate while a low-divergence countermodel survives.

## 4. COG-EPISTEMIC-01 — Epistemic Type Lattice [NEXT P0]
Replace string-level statuses with a runtime type/state machine for `OBSERVED`, `PREDICTIVE`, `ASSUMPTION_CONDITIONAL`, `INTERVENTION_SUPPORTED`, `FALSIFIED`, `UNIDENTIFIED`, `OOD`, `ABSTAIN`. Illegal transitions such as `UNKNOWN -> CAUSAL` must be impossible by construction and mutation-tested.

## 5. COG-MEMORY-01 — Assumption-Aware Consolidation [BLOCKED BY 3+4]
Memory entries carry causal support, countermodel set, context scope, assumption IDs and evidence hashes. Consolidation requires disappearance/rejection of relevant countermodels; otherwise the item remains unresolved causal debt. Retractions must propagate to dependent memories.

## 6. COG-PLAN-01 — Counterfactual Planning with Proof-Carrying Branches [BLOCKED BY 4+5]
Each simulated plan branch carries which model/assumptions generated it, uncertainty, OOD/support state and predicted intervention effect. Planning can compare branches under ambiguity but cannot silently collapse incompatible models into one world-state.

## 7. COG-SELF-01 — Self-Falsification / Reconfiguration Governor [SYNTHETIC NARROW PASS]
The runtime now selects certified decision-relevant attacks against action-flipping worlds, binds them to the current proof/memory dependency graph, rejects stale or irrelevant targets, and permits only monotone-negative authority updates. PRIMARY and REPLICATION passed all 12 frozen families at 128/128. Remaining debt: real-model/public matched-compute transfer, independently authored attacks/rate certificates, natural-language contamination resistance, and external reproduction.
