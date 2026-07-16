# ⊛ STATUTE OF THE COGNITIVE WEAVE KERNEL

**Normative identifier:** `CWK-STATUTE-1.0`  
**Authority state:** canonical candidate  
**Founder and Principal Architect:** Ярослав Василенко  
**Scope:** architecture, implementation, experimentation, evidence and claims

## Article 1 — Purpose

CWK exists to design, implement and falsify a resource-rational architecture for digital cognitive objects. The programme investigates whether intelligence-relevant functions can be produced more efficiently when computation is organized as a dynamically routed, sparsely activated, modular and plastic fabric rather than a uniformly activated monolith.

The programme optimizes no single metric. It seeks a defensible Pareto frontier across:

- task capability;
- activated computation;
- communication volume;
- memory footprint and memory traffic;
- latency and throughput;
- adaptation cost;
- robustness under perturbation;
- calibration and uncertainty;
- reproducibility;
- safety and provenance.

## Article 2 — Scientific position

1. Biological neuroscience is a source of constraints and hypotheses, not proof of architectural correctness.
2. Terms such as *brain-like*, *plastic*, *memory*, *expert*, *attention* and *cognitive* are operational labels and SHALL NOT be treated as biological equivalence.
3. Small-world organization, wiring economy, conditional computation, memory augmentation and test-time adaptation are distinct mechanisms. Their coexistence does not establish synergy; synergy must be measured.
4. The primary scientific object is not model scale but **functional yield per activated resource**.
5. Absence of improvement, instability, routing collapse or negative transfer are valid results and SHALL be preserved.

## Article 3 — Core thesis

Let a digital cognitive object be a tuple

```text
DCO = (F, R, E, M, P, B, W, V)
```

where:

- `F` is the adaptive cognitive fabric;
- `R` is the transit governor;
- `E` is the expert ecology;
- `M` is memory stratigraphy;
- `P` is the structural plasticity cycle;
- `B` is the activation budget contract;
- `W` is the world coupling port;
- `V` is the evidence and verification layer.

The central hypothesis is that jointly constrained routing and topology can increase capability per resource relative to matched dense, static-sparse and conventional MoE baselines.

## Article 4 — Canonical optimization objective

For task distribution `D`, parameters `θ`, topology `G`, router state `ρ`, memory state `μ`, and resource budget `b`:

```text
J = E_D[L_task]
  + λ_wire    · C_wire(G)
  + λ_active  · C_active(θ, ρ)
  + λ_comm    · C_comm(G, ρ)
  + λ_memory  · C_memory(μ)
  + λ_latency · C_latency
  + λ_route   · C_route_instability(ρ)
  + λ_redun   · C_expert_redundancy(E)
  + λ_forget  · C_catastrophic_forgetting
  + λ_risk    · C_safety_violation
```

Every cost SHALL be dimensionless or normalized against a declared baseline. No weighted scalar result may conceal a dominated metric. All primary reports SHALL publish both the scalar objective and the complete metric vector.

## Article 5 — Architectural invariants

The following invariants are mandatory:

1. **Budget observability:** every forward pass reports active experts, routed tokens, attention edges, memory reads/writes and estimated cost.
2. **Fail-closed routing:** invalid, empty or over-budget routes fall back to a declared safe path; silent token loss is forbidden.
3. **Shared-path availability:** at least one shared expert or residual path remains available to every token.
4. **Topology identity:** topology version and hash are attached to every experiment.
5. **Memory provenance:** every persistent memory item has source identity, write time, retention policy and deletion path.
6. **Plasticity boundaries:** structural rewiring is forbidden during evaluation unless test-time adaptation is the preregistered intervention.
7. **No hidden baseline drift:** baseline code, tokenizer, data split, precision and compute budget are frozen before comparison.
8. **Claim–evidence binding:** every released quantitative claim resolves to an evidence bundle.
9. **Negative-result retention:** failed runs and null findings cannot be deleted solely because they weaken the thesis.
10. **Reproducible randomness:** every stochastic process receives an independently derived seed recorded in evidence.
11. **Capability-Threshold Gate:** any structural plasticity operator or routing configuration that increases active node count, `max_active_experts`, or depth ceiling beyond a preregistered threshold MUST NOT be enabled for evaluation until `Q_robust` and `Q_agency` (ADR-0007) are measured at that threshold and pass their preregistered bounds. This is a precondition, structurally identical to Budget-first (§3.1 of CWC-SPEC-001), not a post-hoc penalty term.

## Article 6 — Original functional components

### 6.1 Adaptive Cognitive Fabric

A typed, weighted, spatially embedded graph. Nodes represent computational modules; edges represent allowed communication. Edge cost may incorporate geometric distance, bandwidth, synchronization and measured transfer cost. The fabric may contain local clusters, sparse long-range bridges and protected global control channels.

### 6.2 Activation Budget Contract

A machine-readable contract specifying ceilings and targets for active parameters, expert fan-out, attention density, memory operations, latency, peak memory and adaptation steps. Exceeding a hard ceiling invalidates the run unless the breach itself is the preregistered test.

### 6.3 Transit Governor

A router producing a route decision and a confidence distribution. It SHALL expose entropy, capacity use, token drops, route churn and expert utilization. It SHALL support deterministic replay.

### 6.4 Expert Ecology

An ecology contains shared experts, routed experts and optional modality-specific adapters. Expertise is not inferred from names. It is quantified through intervention, routing selectivity, representational similarity, transfer and ablation.

### 6.5 Memory Stratigraphy

- **Working memory:** bounded current-state activations.
- **Episodic memory:** retrievable traces with explicit retention and provenance.
- **Persistent memory:** learned parameters or durable external state.

Memory gain must exceed retrieval cost and distraction harm under matched context budgets.

### 6.6 Structural Plasticity Cycle

A controlled four-stage cycle:

```text
observe → propose → validate → commit
```

Candidate edges are pruned or grown from measured utility, not aesthetic graph targets. Every committed topology delta is reversible and versioned.

### 6.7 Metacognitive Budget Governor

Selects compute depth and resource budget from uncertainty, expected value and risk. It cannot rewrite task outputs directly; it controls resource allocation and records the decision basis.

### 6.8 World Coupling Port

Provides typed observations and actions. It separates perception, state estimation, planning and actuation. Simulated embodiment and real-world embodiment SHALL be reported separately.

### 6.9 Evidence Spine

Captures immutable run identity, source revision, environment, dependency lock, data hashes, configuration, seeds, topology, metrics, logs and artifacts.

### 6.10 Claim Firewall

Rejects claims when evidence is missing, post-hoc, underpowered, non-reproducible or incompatible with the stated population. It distinguishes:

- observation;
- benchmark result;
- replicated result;
- bounded scientific claim;
- generalization claim.

## Article 7 — Falsification obligations

Every mechanism SHALL be tested against:

1. parameter-count-matched dense baseline;
2. activated-FLOP-matched baseline;
3. static sparse baseline;
4. conventional MoE baseline where applicable;
5. shuffled or randomized routing control;
6. frozen-router ablation;
7. memory-off and memory-random controls;
8. topology-preserving weight randomization where meaningful;
9. seed and data-split sensitivity;
10. out-of-distribution transfer.

A proposed mechanism is rejected for the tested scope when it fails preregistered minimum effects or violates resource ceilings.

## Article 8 — Authority and change control

The Founder and Principal Architect owns the research direction and may approve canonical changes. No architectural decision becomes canonical without:

- an Architecture Decision Record;
- explicit alternatives;
- measurable consequences;
- compatibility statement;
- migration or rollback procedure;
- validation evidence.

## Article 9 — Prohibited practices

The project forbids:

- retroactively changing success thresholds after viewing results;
- comparing unmatched compute or data while implying architectural superiority;
- presenting proxy cost as measured energy without qualification;
- selecting only favorable seeds;
- claiming biological fidelity from metaphor;
- treating benchmark contamination as capability;
- using generated citations without source verification;
- silently modifying data, prompts or evaluation scripts;
- declaring novelty without a documented search boundary;
- declaring intelligence, consciousness or agency from surface behavior.

## Article 10 — Definition of success

Success is not a dramatic narrative. Success is a replicated, resource-matched result demonstrating a non-trivial Pareto improvement, with transparent failure boundaries, independently executable code and a claim narrower than the evidence.
